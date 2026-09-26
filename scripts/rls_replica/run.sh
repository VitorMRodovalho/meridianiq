#!/usr/bin/env bash
# Throwaway local replica of the Supabase database, for exercising migration
# 034 (organization RLS, owner-only project reads, read-only client
# privileges) the way the client roles reach it.
#
# It never contacts a remote database. The container runs with
# --network none, is reached only through `docker exec`, and is removed on
# exit. Nothing here holds a credential: the stock image uses local trust
# authentication, and the Supabase image gets a random password that lives
# only for the container's lifetime.
#
# Usage:
#   scripts/rls_replica/run.sh                                # postgres:17
#   scripts/rls_replica/run.sh supabase/postgres:17.6.1.084   # Supabase image
#
# With postgres:17, bootstrap_stock.sql creates the Supabase roles (postgres
# NOSUPERUSER BYPASSRLS; anon; authenticated; service_role BYPASSRLS;
# supabase_auth_admin), an auth schema with auth.users and auth.uid(), and
# Supabase's default privileges. With the Supabase image those already
# exist; bootstrap_supabase_image.sql adds two auth.users columns.
#
# Stages: replay 001-033 (the known replay errors are compared exactly),
# load fixtures, CONTROL ARM (must reproduce the recursion), apply 034 twice
# (the second apply must not change the catalog), probe reads/writes/RPCs as
# the client roles, a signup after 034, then negative controls that must
# make 034 abort. Each check prints PASS, FAIL or INFO. Exit status is 0 only
# when every stage ran and no check failed.

set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd "$here/../.." && pwd)
migrations="$repo/supabase/migrations"
m034="$migrations/034_org_rls_rewrite.sql"
image="${1:-postgres:17}"
name="mq-rls-replica-$$-$RANDOM"
password=$(od -An -N12 -tx1 /dev/urandom | tr -d ' \n')
work=$(mktemp -d)
failures=0

cleanup() {
    docker stop "$name" >/dev/null 2>&1 || true
    rm -rf "$work"
}
trap cleanup EXIT

stage() { printf '\n### %s\n' "$*"; }
fail() { printf 'FAIL  %s\n' "$*"; failures=$((failures + 1)); }
pass() { printf 'PASS  %s\n' "$*"; }

# psql_as <role> [psql args...] -- SQL on stdin.
psql_as() {
    local role=$1
    shift
    docker exec -i -e PGPASSWORD="$password" "$name" psql -X -q -U "$role" -d postgres "$@"
}

# Print a probe transcript and add its failures to the tally. A statement
# that errored instead of printing PASS/FAIL/INFO (a psql "ERROR:" line)
# counts as a failure too.
tally() {
    local log=$1 n_pass n_fail n_info n_err
    cat "$log"
    n_pass=$(grep -c '^PASS' "$log" || true)
    n_fail=$(grep -c '^FAIL' "$log" || true)
    n_info=$(grep -c '^INFO' "$log" || true)
    n_err=$(grep -c 'ERROR:' "$log" || true)
    echo "-- $(basename "$log"): pass=$n_pass fail=$n_fail info=$n_info statement_errors=$n_err"
    failures=$((failures + n_fail + n_err))
}

case "$image" in
    supabase/postgres:*) kind=supabase ;;
    *) kind=stock ;;
esac

stage "start $image ($kind) as $name, no network"
if [[ $kind == stock ]]; then
    docker run -d --rm --name "$name" --network none \
        -e POSTGRES_USER=supabase_admin -e POSTGRES_DB=postgres \
        -e POSTGRES_HOST_AUTH_METHOD=trust "$image" >/dev/null
else
    docker run -d --rm --name "$name" --network none \
        -e POSTGRES_PASSWORD="$password" "$image" >/dev/null
fi
# The image's entrypoint first runs a socket-only server for initialisation,
# then restarts. Ready means: the final server answers (listen_addresses set).
ready=""
for _ in $(seq 1 120); do
    ready=$(psql_as supabase_admin -Atc "SHOW listen_addresses" 2>/dev/null || true)
    [[ -n $ready ]] && break
    sleep 1
done
if [[ -z $ready ]]; then
    echo "not measured: the server did not become ready" >&2
    exit 2
fi
psql_as supabase_admin -Atc "SELECT 'server ' || version()"

stage "bootstrap ($kind)"
psql_as supabase_admin -v ON_ERROR_STOP=1 < "$here/bootstrap_$( [[ $kind == stock ]] && echo stock || echo supabase_image ).sql"
psql_as supabase_admin -Atc "SELECT 'role ' || rolname || ' super=' || rolsuper || ' bypassrls=' || rolbypassrls FROM pg_roles WHERE rolname IN ('postgres', 'anon', 'authenticated', 'service_role') ORDER BY 1"

stage "replay migrations before 034 as postgres (errors tolerated, then compared)"
: > "$work/replay_errors.txt"
for f in "$migrations"/*.sql; do
    base=$(basename "$f")
    [[ $base < 034_ ]] || continue
    out=$(psql_as postgres -v ON_ERROR_STOP=0 < "$f" 2>&1 || true)
    grep -o 'ERROR: .*' <<< "$out" | sed "s|^|$base: |" >> "$work/replay_errors.txt" || true
done
cat > "$work/replay_expected.txt" <<'EOF'
006_cleanup_orphan_uploads.sql: ERROR:  column "xer_storage_path" does not exist
014_security_rpcs.sql: ERROR:  policy "Users see own programs" for table "programs" already exists
014_security_rpcs.sql: ERROR:  policy "Users insert own programs" for table "programs" already exists
014_security_rpcs.sql: ERROR:  policy "Users update own programs" for table "programs" already exists
EOF
cat "$work/replay_errors.txt"
if diff -u "$work/replay_expected.txt" "$work/replay_errors.txt"; then
    pass "replay produced exactly the 4 known errors ($(wc -l < "$work/replay_errors.txt"))"
else
    fail "replay errors differ from the known set; the harness is not trusted past this point"
    exit 1
fi

stage "fixtures (signups through the auth role, then org/project rows)"
psql_as supabase_admin < "$here/034/fixtures.sql"

stage "CONTROL ARM: before 034"
cat "$here/probe_lib.sql" "$here/034/control.sql" | psql_as supabase_admin > "$work/control.log" 2>&1
tally "$work/control.log"

stage "apply 034 as postgres (1st)"
rc=0
psql_as postgres -v ON_ERROR_STOP=1 < "$m034" > "$work/apply1.log" 2>&1 || rc=$?
grep -E 'ERROR|WARNING' "$work/apply1.log" || true
if [[ $rc -eq 0 ]]; then pass "034 apply #1 rc=0"; else fail "034 apply #1 rc=$rc"; cat "$work/apply1.log"; exit 1; fi
fp1=$(psql_as supabase_admin < "$here/fingerprint.sql")
echo "$fp1"

stage "apply 034 as postgres (2nd, must be a no-op)"
rc=0
psql_as postgres -v ON_ERROR_STOP=1 < "$m034" > "$work/apply2.log" 2>&1 || rc=$?
if [[ $rc -eq 0 ]]; then pass "034 apply #2 rc=0"; else fail "034 apply #2 rc=$rc"; cat "$work/apply2.log"; fi
fp2=$(psql_as supabase_admin < "$here/fingerprint.sql")
echo "$fp2"
if [[ -n $fp1 && $fp1 == "$fp2" ]]; then pass "catalog fingerprint unchanged by the 2nd apply"; else fail "catalog fingerprint changed by the 2nd apply"; fi

stage "AFTER 034: reads, writes, RPCs as the client roles"
cat "$here/probe_lib.sql" "$here/034/after.sql" | psql_as supabase_admin > "$work/after.log" 2>&1
tally "$work/after.log"

stage "signup after 034"
psql_as supabase_admin < "$here/034/signup_after.sql"
cat "$here/probe_lib.sql" "$here/034/after_signup.sql" | psql_as supabase_admin > "$work/signup.log" 2>&1
tally "$work/signup.log"

stage "negative controls: 034 must abort (each in a rolled-back transaction)"
[[ $(grep -c '^BEGIN;$' "$m034") -eq 1 && $(grep -c '^COMMIT;$' "$m034") -eq 1 ]] \
    || { fail "034 does not have exactly one BEGIN; and one COMMIT; line"; exit 1; }
sed -e '/^BEGIN;$/d' -e '/^COMMIT;$/d' "$m034" > "$work/034_body.sql"

# negative <label> <expected rc: 0|nonzero> <regex expected in the output> <setup SQL>
negative() {
    local label=$1 want=$2 regex=$3 setup=$4 rc=0
    {
        printf '\\set ON_ERROR_STOP on\nBEGIN;\n%s\nSET ROLE postgres;\n' "$setup"
        cat "$work/034_body.sql"
        printf 'ROLLBACK;\n'
    } | psql_as supabase_admin > "$work/neg.log" 2>&1 || rc=$?
    local hit
    hit=$(grep -Eo "$regex" "$work/neg.log" | head -1 || true)
    if [[ $want == 0 && $rc -eq 0 ]] || [[ $want == nonzero && $rc -ne 0 && -n $hit ]]; then
        pass "$label  =>  rc=$rc ${hit:+| $hit}"
    else
        fail "$label  =>  rc=$rc, expected rc $want and /$regex/"
        tail -5 "$work/neg.log"
    fi
}

negative "n0 unmodified body inside BEGIN/ROLLBACK applies (harness control)" 0 '' ''
negative "n1 helper owner subject to RLS on memberships (NOBYPASSRLS + FORCE RLS)" nonzero \
    'owner postgres of public.is_org_member is subject to RLS on public.memberships' \
    'ALTER ROLE postgres NOBYPASSRLS; ALTER TABLE public.memberships FORCE ROW LEVEL SECURITY;'
negative "n2 helper owner without BYPASSRLS but table owner, FORCE off (guard must pass)" 0 '' \
    'ALTER ROLE postgres NOBYPASSRLS;'
negative "n3 an extra permissive read policy on a project table" nonzero \
    'unexpected permissive read policies: activities\.probe_open_read' \
    'CREATE POLICY probe_open_read ON public.activities FOR SELECT USING (true);'
negative "n4 a policy that reads memberships directly" nonzero \
    'policies still read public.memberships directly: reports\.probe_member_read' \
    'CREATE POLICY probe_member_read ON public.reports FOR SELECT USING (user_id IN (SELECT m.user_id FROM public.memberships AS m));'
negative "n5 another is_org_member overload" nonzero \
    'unexpected function public\.is_org_member\(uuid\)' \
    "CREATE FUNCTION public.is_org_member(uuid) RETURNS boolean LANGUAGE sql AS 'SELECT true'; ALTER FUNCTION public.is_org_member(uuid) OWNER TO postgres;"
negative "n6 a policy cycle projects -> project_shares -> projects (restrictive, so only planning sees it)" nonzero \
    'planning a read of public\.[a-z_]+ as authenticated failed: infinite recursion detected in policy for relation "[a-z_]+"' \
    'CREATE POLICY probe_cycle ON public.projects AS RESTRICTIVE FOR SELECT TO authenticated USING (id IN (SELECT ps.project_id FROM public.project_shares AS ps));'

fp3=$(psql_as supabase_admin < "$here/fingerprint.sql")
if [[ $fp3 == "$fp2" ]]; then pass "catalog unchanged by the negative controls"; else fail "negative controls changed the catalog"; fi

stage "summary ($image)"
echo "failures=$failures"
[[ $failures -eq 0 ]]
