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
# load fixtures, the read-only census 034/preflight.sql (clean, then with
# drift and client-written rows planted, which it must report), CONTROL ARM
# (must reproduce the recursion), apply 034 twice (the second apply must not
# change the catalog), probe reads/writes/RPCs as the client roles, the
# read-only 034/postcheck.sql (clean, then after re-running 008 and 009,
# which it must report), a signup after 034, then negative controls that
# must make 034 abort. Each check prints PASS, FAIL or INFO (the census
# also REVIEW). Exit status is 0 only when every stage ran and no check
# failed.

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
# REVIEW (census rows a person should look at) also counts as a failure:
# the replica's fixtures are synthetic and must leave nothing to review.
tally() {
    local log=$1 n_pass n_fail n_info n_review n_err
    cat "$log"
    n_pass=$(grep -c '^PASS' "$log" || true)
    n_fail=$(grep -c '^FAIL' "$log" || true)
    n_info=$(grep -c '^INFO' "$log" || true)
    n_review=$(grep -c '^REVIEW' "$log" || true)
    n_err=$(grep -c 'ERROR:' "$log" || true)
    echo "-- $(basename "$log"): pass=$n_pass fail=$n_fail review=$n_review info=$n_info statement_errors=$n_err"
    failures=$((failures + n_fail + n_review + n_err))
}

# expect_lines <log> <label> <regex>... : each regex must match a line of the
# log (used where a check is expected to report FAIL or REVIEW).
expect_lines() {
    local log=$1 label=$2 re
    shift 2
    for re in "$@"; do
        if grep -Eq -- "$re" "$log"; then
            pass "$label: $(grep -Eo -- "$re" "$log" | head -1)"
        else
            fail "$label: no line matches /$re/"
        fi
    done
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

stage "preflight census before 034 (read-only)"
psql_as supabase_admin -At < "$here/034/preflight.sql" > "$work/preflight.log" 2>&1
tally "$work/preflight.log"

stage "preflight census must report drift and client-written rows (planted in a rolled-back transaction)"
rc=0
{
    cat <<'SQL'
\set ON_ERROR_STOP on
BEGIN;
ALTER TABLE public.activities OWNER TO supabase_admin;
GRANT INSERT ON public.reports TO service_role WITH GRANT OPTION;
SET ROLE service_role;
GRANT INSERT ON public.reports TO authenticated;
RESET ROLE;
SET ROLE postgres;
CREATE TABLE public.probe_extra (id int);
ALTER TABLE public.probe_extra ENABLE ROW LEVEL SECURITY;
CREATE VIEW public.probe_members_v AS SELECT org_id, user_id FROM public.memberships;
RESET ROLE;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres GRANT INSERT ON TABLES TO authenticated;
CREATE SCHEMA private AUTHORIZATION supabase_admin;
CREATE FUNCTION public.is_org_member(uuid) RETURNS boolean LANGUAGE sql AS 'SELECT true';
ALTER ROLE postgres NOBYPASSRLS;
ALTER TABLE public.memberships FORCE ROW LEVEL SECURITY;
CREATE SCHEMA supabase_migrations;
CREATE TABLE supabase_migrations.schema_migrations (version text PRIMARY KEY);
INSERT INTO supabase_migrations.schema_migrations
    SELECT to_char(n, 'FM000') FROM generate_series(1, 33) AS n WHERE n NOT BETWEEN 20 AND 29;
INSERT INTO public.projects (id, upload_id, user_id, project_name, storage_path) VALUES
    ('30000000-0000-4000-8000-0000000000e1', '40000000-0000-4000-8000-0000000000c4',
     'a0000000-0000-4000-8000-000000000001', 'planted',
     'd0000000-0000-4000-8000-000000000004/40000000-0000-4000-8000-0000000000c4/delta.xer');
INSERT INTO public.organizations (id, name, slug, created_by) VALUES
    ('10000000-0000-4000-8000-0000000000e2', 'planted', 'planted', 'a0000000-0000-4000-8000-000000000001');
SQL
    cat "$here/034/preflight.sql"
    printf 'ROLLBACK;\n'
} | psql_as supabase_admin -At > "$work/preflight_planted.log" 2>&1 || rc=$?
cat "$work/preflight_planted.log"
if [[ $rc -ne 0 ]]; then fail "planted census run rc=$rc"; fi
expect_lines "$work/preflight_planted.log" "census reports" \
    '^FAIL +pf04 .*activities \(supabase_admin\)' \
    '^FAIL +pf05 .*reports \(authenticated by service_role\)' \
    '^REVIEW +pf03 .*probe_extra \(kind r, owner postgres\).*probe_members_v \(kind v, owner postgres\)' \
    '^FAIL +pf06 .*probe_extra \(anon\)' \
    '^FAIL +pf07 .*probe_members_v \(kind v, anon\)' \
    '^FAIL +pf08 .*INSERT to authenticated' \
    '^FAIL +pf10 .*owner supabase_admin' \
    '^FAIL +pf11 .*public\.is_org_member\(uuid\)' \
    '^FAIL +pf12 .*bypassrls=f .*force=t' \
    '^REVIEW +pf13 .*recorded 23 \(001 \.\. 033\), missing: 020, 021, 022, 023, 024, 025, 026, 027, 028, 029$' \
    '^REVIEW +pf20 .*=>  1 30000000-0000-4000-8000-0000000000e1$' \
    '^REVIEW +pf21 .*=>  1 30000000-0000-4000-8000-0000000000e1$' \
    '^REVIEW +pf22 .*=>  1 10000000-0000-4000-8000-0000000000e2$'
if grep -q 'ERROR:' "$work/preflight_planted.log"; then fail "planted census run had a statement error"; fi

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

stage "postcheck after 034 (read-only)"
psql_as supabase_admin -At < "$here/034/postcheck.sql" > "$work/postcheck.log" 2>&1
tally "$work/postcheck.log"

stage "postcheck must report a re-run of 008 and 009 (in a rolled-back transaction)"
rc=0
{
    cat "$here/probe_lib.sql"
    printf '\\set ON_ERROR_STOP on\nBEGIN;\nSET ROLE postgres;\n'
    cat "$migrations/008_value_milestones.sql" "$migrations/009_forensic_workspace.sql"
    printf 'RESET ROLE;\n'
    cat "$here/034/postcheck.sql"
    cat <<'SQL'
SELECT pg_temp.info('rerun B (member of X, not the owner) value_milestones / forensic_timelines',
    pg_temp.run_as('authenticated', :B, 'SELECT (SELECT count(*) FROM public.value_milestones) || ''/'' || (SELECT count(*) FROM public.forensic_timelines)'));
ROLLBACK;
SQL
} | psql_as supabase_admin -At > "$work/postcheck_rerun.log" 2>&1 || rc=$?
if [[ $rc -ne 0 ]]; then fail "postcheck re-run rc=$rc"; fi
grep -E '^(PASS|FAIL|INFO)|ERROR:' "$work/postcheck_rerun.log" || true
expect_lines "$work/postcheck_rerun.log" "postcheck reports" \
    '^FAIL +pc01 .*value_milestones\.Org members can view value milestones' \
    '^FAIL +pc01 .*forensic_timelines\.Users can view accessible timelines' \
    '^FAIL +pc02 .*value_milestones\.Org members can view value milestones'
if grep -q 'ERROR:' "$work/postcheck_rerun.log"; then fail "re-run of 008/009 had a statement error"; fi

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
    'owner postgres of private\.is_org_member is subject to RLS on public\.memberships' \
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
negative "n5c client USAGE on schema private" nonzero \
    'client roles have USAGE or CREATE on schema private' \
    'GRANT USAGE ON SCHEMA private TO authenticated;'
negative "n5b another is_org_member in schema private" nonzero \
    'unexpected function private\.is_org_member\(uuid\)' \
    "CREATE FUNCTION private.is_org_member(uuid) RETURNS boolean LANGUAGE sql AS 'SELECT true'; ALTER FUNCTION private.is_org_member(uuid) OWNER TO postgres;"
negative "n6 a policy cycle projects -> project_shares -> projects (restrictive, so only planning sees it)" nonzero \
    'planning a read of public\.[a-z_]+ as authenticated failed: infinite recursion detected in policy for relation "[a-z_]+"' \
    'CREATE POLICY probe_cycle ON public.projects AS RESTRICTIVE FOR SELECT TO authenticated USING (id IN (SELECT ps.project_id FROM public.project_shares AS ps));'
negative "n7 a table outside the list that clients can write" nonzero \
    'client roles can write: probe_extra \(anon, owner postgres\)' \
    'CREATE TABLE public.probe_extra (id int); ALTER TABLE public.probe_extra OWNER TO postgres; ALTER TABLE public.probe_extra ENABLE ROW LEVEL SECURITY; GRANT INSERT, UPDATE ON public.probe_extra TO anon, authenticated;'
negative "n8 a listed table owned by another role: the REVOKE only warns" nonzero \
    'client roles can write: activities \(authenticated, owner supabase_admin\)' \
    'ALTER TABLE public.activities OWNER TO supabase_admin; GRANT INSERT ON public.activities TO authenticated;'
negative "n9 a client ACL entry granted by a role other than the owner survives the owner's REVOKE" nonzero \
    'client roles can write: reports \(authenticated, owner postgres\)' \
    'GRANT INSERT ON public.reports TO service_role WITH GRANT OPTION; SET ROLE service_role; GRANT INSERT ON public.reports TO authenticated; RESET ROLE;'
negative "n10 a column-level UPDATE grant on a table outside the list" nonzero \
    'client roles can write: probe_col \(authenticated, owner postgres\)' \
    'CREATE TABLE public.probe_col (id int, note text); ALTER TABLE public.probe_col OWNER TO postgres; ALTER TABLE public.probe_col ENABLE ROW LEVEL SECURITY; REVOKE ALL ON public.probe_col FROM anon, authenticated; GRANT SELECT, UPDATE (note) ON public.probe_col TO authenticated;'
negative "n11 a view over memberships that runs as its owner" nonzero \
    'client roles can read rows that RLS does not filter: probe_members_v \(anon\), probe_members_v \(authenticated\)' \
    'CREATE VIEW public.probe_members_v AS SELECT org_id, user_id FROM public.memberships; ALTER VIEW public.probe_members_v OWNER TO postgres; REVOKE ALL ON public.probe_members_v FROM anon, authenticated; GRANT SELECT ON public.probe_members_v TO anon, authenticated;'
negative "n11b the same view with security_invoker (must apply)" 0 '' \
    'CREATE VIEW public.probe_members_v WITH (security_invoker = true) AS SELECT org_id, user_id FROM public.memberships; ALTER VIEW public.probe_members_v OWNER TO postgres; REVOKE ALL ON public.probe_members_v FROM anon, authenticated; GRANT SELECT ON public.probe_members_v TO anon, authenticated;'
negative "n12 a client-readable table with RLS disabled" nonzero \
    'client roles can read rows that RLS does not filter: reports \(anon\), reports \(authenticated\)' \
    'ALTER TABLE public.reports DISABLE ROW LEVEL SECURITY;'
negative "n13 program_shares owned by another role keeps a client SELECT" nonzero \
    'unexpected client privileges on organization tables: program_shares \(anon\)' \
    'ALTER TABLE public.program_shares OWNER TO supabase_admin; GRANT SELECT ON public.program_shares TO anon;'
negative "n14 a default privilege of postgres for all schemas grants INSERT" nonzero \
    'default privileges of postgres grant clients: all schemas INSERT to authenticated' \
    'ALTER DEFAULT PRIVILEGES FOR ROLE postgres GRANT INSERT ON TABLES TO authenticated;'
negative "n15 a listed table is missing" nonzero \
    'tables missing from schema public: what_if_scenarios' \
    'DROP TABLE public.what_if_scenarios CASCADE;'
negative "n16 schema private owned by another role" nonzero \
    'schema private is owned by supabase_admin, expected postgres' \
    'DROP FUNCTION private.is_org_member(uuid, text[]) CASCADE; DROP SCHEMA private; CREATE SCHEMA private AUTHORIZATION supabase_admin;'

fp3=$(psql_as supabase_admin < "$here/fingerprint.sql")
if [[ $fp3 == "$fp2" ]]; then pass "catalog unchanged by the negative controls"; else fail "negative controls changed the catalog"; fi

stage "summary ($image)"
echo "failures=$failures"
[[ $failures -eq 0 ]]
