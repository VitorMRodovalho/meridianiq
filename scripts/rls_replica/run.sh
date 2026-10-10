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
# must make 034 abort; then 035 and 036 stages, and, with the Supabase
# image only (it ships pg_cron), 040: two applies, its postcheck, the purge
# horizon scenarios, a real pg_cron run with a control row, negative
# controls and the recovery after re-applying 036. Each check prints PASS,
# FAIL or INFO (the census also REVIEW). Exit status is 0 only when every
# stage ran and no check failed.

set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd "$here/../.." && pwd)
migrations="$repo/supabase/migrations"
m034="$migrations/034_org_rls_rewrite.sql"
m035="$migrations/035_ai_access_ledger.sql"
m036="$migrations/036_ai_access_requests.sql"
m040="$migrations/040_ai_request_retention.sql"
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

stage "apply 035 as postgres (1st)"
rc=0
psql_as postgres -v ON_ERROR_STOP=1 < "$m035" > "$work/apply035_1.log" 2>&1 || rc=$?
grep -E 'ERROR|WARNING' "$work/apply035_1.log" || true
if [[ $rc -eq 0 ]]; then pass "035 apply #1 rc=0"; else fail "035 apply #1 rc=$rc"; cat "$work/apply035_1.log"; exit 1; fi
fp4=$(psql_as supabase_admin < "$here/fingerprint.sql")

stage "apply 035 as postgres (2nd, must be a no-op)"
rc=0
psql_as postgres -v ON_ERROR_STOP=1 < "$m035" > "$work/apply035_2.log" 2>&1 || rc=$?
if [[ $rc -eq 0 ]]; then pass "035 apply #2 rc=0"; else fail "035 apply #2 rc=$rc"; cat "$work/apply035_2.log"; fi
fp5=$(psql_as supabase_admin < "$here/fingerprint.sql")
if [[ -n $fp4 && $fp4 == "$fp5" ]]; then pass "catalog fingerprint unchanged by the 2nd 035 apply"; else fail "catalog fingerprint changed by the 2nd 035 apply"; fi

stage "postcheck after 035 (read-only)"
psql_as supabase_admin -At < "$here/034/postcheck.sql" > "$work/postcheck035.log" 2>&1
tally "$work/postcheck035.log"

stage "035 ledger scenarios as service_role (mirror tests/test_ai_gate.py)"
cat "$here/probe_lib.sql" "$here/035/scenarios.sql" | psql_as supabase_admin > "$work/scenarios035.log" 2>&1
tally "$work/scenarios035.log"

# Concurrency: N sessions reserve at once against a daily limit of 5. The
# real function must grant exactly 5. Two copies of it with a pause between
# reading the quota and inserting show that the advisory lock is what holds
# the limit: with the lock exactly 5, without it more than 5. If the no-lock
# copy does not overrun, the instrument cannot say no, and that is a failure.
concurrent_reserve() {  # <function> <sessions>
    local fn=$1 n=$2 i
    psql_as supabase_admin -q -c "DELETE FROM public.ai_usage; DELETE FROM public.ai_entitlements;
        INSERT INTO public.ai_entitlements (user_id, daily_questions) VALUES ('a0000000-0000-4000-8000-000000000001', 5);"
    for i in $(seq 1 "$n"); do
        psql_as supabase_admin -q -c "SET ROLE service_role; SELECT reservation_id FROM $fn('a0000000-0000-4000-8000-000000000001', NULL, 0.01, 20, 5, 50, 'm', 3, 15);" > /dev/null 2>&1 &
    done
    wait
    psql_as supabase_admin -At -c "SELECT count(*) FROM public.ai_usage"
}
stage "035 concurrency: the advisory lock holds a limit (with a no-lock control)"
psql_as supabase_admin -v ON_ERROR_STOP=1 -q > "$work/probe035.log" 2>&1 <<'SQL'
CREATE SCHEMA probe035;
GRANT USAGE ON SCHEMA probe035 TO service_role;
DO $$
DECLARE
    v_def text := pg_get_functiondef('public.ai_reserve(uuid, uuid, numeric, integer, numeric, numeric, text, numeric, numeric)'::regprocedure);
    -- The first statement after the quota read: the pause goes before it,
    -- between reading the quota and inserting the reservation.
    v_after_read text := 'IF NOT v_q.entitled THEN';
BEGIN
    IF position(v_after_read IN v_def) = 0 OR position('PERFORM pg_advisory_xact_lock' IN v_def) = 0 THEN
        RAISE EXCEPTION 'ai_reserve body changed: update the concurrency probe';
    END IF;
    v_def := replace(v_def, 'public.ai_reserve(', 'probe035.reserve_lock(');
    v_def := replace(v_def, v_after_read, 'PERFORM pg_sleep(1.0); ' || v_after_read);
    EXECUTE v_def;
    v_def := replace(v_def, 'probe035.reserve_lock(', 'probe035.reserve_nolock(');
    v_def := regexp_replace(v_def, 'PERFORM pg_advisory_xact_lock\([^;]*;', '');
    EXECUTE v_def;
END
$$;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA probe035 TO service_role;
SQL
if grep -q 'ERROR' "$work/probe035.log"; then fail "concurrency probe setup"; cat "$work/probe035.log"; fi
n_real=$(concurrent_reserve public.ai_reserve 12)
n_lock=$(concurrent_reserve probe035.reserve_lock 12)
n_nolock=$(concurrent_reserve probe035.reserve_nolock 12)
echo "reservations granted of 12 concurrent, daily limit 5: real=$n_real lock+pause=$n_lock nolock+pause=$n_nolock"
if [[ $n_real == 5 ]]; then pass "real ai_reserve granted exactly 5"; else fail "real ai_reserve granted $n_real"; fi
if [[ $n_lock == 5 ]]; then pass "locked copy with a pause granted exactly 5"; else fail "locked copy granted $n_lock"; fi
if [[ $n_nolock =~ ^[0-9]+$ && $n_nolock -gt 5 ]]; then pass "no-lock control overran ($n_nolock): the probe can say no"; else fail "no-lock control granted $n_nolock: the probe cannot tell"; fi
psql_as supabase_admin -q -c "DROP SCHEMA probe035 CASCADE; DELETE FROM public.ai_usage; DELETE FROM public.ai_entitlements;" > /dev/null 2>&1

stage "preflight before 036 (read-only, as postgres)"
psql_as postgres -At < "$here/036/preflight.sql" > "$work/preflight036.log" 2>&1
tally "$work/preflight036.log"

# Every 036 preflight check must be able to say FAIL: plant each drift in a
# rolled-back transaction (run as supabase_admin, so pf06 fails too).
stage "036 preflight must report drift (planted in a rolled-back transaction)"
rc=0
{
    cat <<'SQL'
\set ON_ERROR_STOP on
BEGIN;
ALTER FUNCTION public.ai_quota OWNER TO supabase_admin;
CREATE TABLE public.ai_access_requests (user_id uuid PRIMARY KEY, status text);
DO $$
BEGIN
    EXECUTE replace(pg_get_functiondef('public.ai_grant(uuid,text,uuid,integer,numeric,text,text,text)'::regprocedure),
                    'BEGIN', 'BEGIN' || chr(10) || '    -- local hot-fix');
END
$$;
DROP SCHEMA private CASCADE;
SQL
    cat "$here/036/preflight.sql"
    printf 'ROLLBACK;\n'
} | psql_as supabase_admin -At > "$work/preflight036_planted.log" 2>&1 || rc=$?
cat "$work/preflight036_planted.log"
if [[ $rc -ne 0 ]]; then fail "planted 036 preflight run rc=$rc"; fi
expect_lines "$work/preflight036_planted.log" "036 preflight reports" \
    '^FAIL +pf01 .*ai_quota:supabase_admin' \
    '^FAIL +pf02 .*=>  user_id,status$' \
    '^FAIL +pf03 .*=>  md5 [0-9a-f]{32}$' \
    '^FAIL +pf05 .*schema private absent' \
    '^FAIL +pf06 .*supabase_admin'
n_rows=$(grep -cE '^(PASS|FAIL) +pf0[1-6] ' "$work/preflight036_planted.log" || true)
if [[ $n_rows == 6 ]]; then pass "036 preflight printed 6 rows with drift planted"; else fail "036 preflight printed $n_rows rows with drift planted, expected 6"; fi
if grep -q 'ERROR:' "$work/preflight036_planted.log"; then fail "planted 036 preflight had a statement error"; fi

stage "apply 036 as postgres (1st)"
rc=0
psql_as postgres -v ON_ERROR_STOP=1 < "$m036" > "$work/apply036_1.log" 2>&1 || rc=$?
grep -E 'ERROR|WARNING' "$work/apply036_1.log" || true
if [[ $rc -eq 0 ]]; then pass "036 apply #1 rc=0"; else fail "036 apply #1 rc=$rc"; cat "$work/apply036_1.log"; exit 1; fi
fp6=$(psql_as supabase_admin < "$here/fingerprint.sql")

stage "apply 036 as postgres (2nd, must be a no-op)"
rc=0
psql_as postgres -v ON_ERROR_STOP=1 < "$m036" > "$work/apply036_2.log" 2>&1 || rc=$?
if [[ $rc -eq 0 ]]; then pass "036 apply #2 rc=0"; else fail "036 apply #2 rc=$rc"; cat "$work/apply036_2.log"; fi
fp7=$(psql_as supabase_admin < "$here/fingerprint.sql")
if [[ -n $fp6 && $fp6 == "$fp7" ]]; then pass "catalog fingerprint unchanged by the 2nd 036 apply"; else fail "catalog fingerprint changed by the 2nd 036 apply"; fi

stage "postcheck after 036 (read-only)"
psql_as supabase_admin -At < "$here/034/postcheck.sql" > "$work/postcheck036.log" 2>&1
tally "$work/postcheck036.log"

stage "036 postcheck (read-only)"
psql_as postgres -At < "$here/036/postcheck.sql" > "$work/postcheck036b.log" 2>&1
tally "$work/postcheck036b.log"

stage "036 access request scenarios as service_role (mirror tests/test_ai_requests.py)"
cat "$here/probe_lib.sql" "$here/036/scenarios.sql" | psql_as supabase_admin > "$work/scenarios036.log" 2>&1
tally "$work/scenarios036.log"

stage "negative controls: 036 must abort (each in a rolled-back transaction)"
[[ $(grep -c '^BEGIN;$' "$m036") -eq 1 && $(grep -c '^COMMIT;$' "$m036") -eq 1 ]] \
    || { fail "036 does not have exactly one BEGIN; and one COMMIT; line"; exit 1; }
sed -e '/^BEGIN;$/d' -e '/^COMMIT;$/d' "$m036" > "$work/036_body.sql"
fp036a=$(psql_as supabase_admin < "$here/fingerprint.sql")

# negative036 <label> <expected rc: 0|nonzero> <regex expected in the output> <setup SQL>
negative036() {
    local label=$1 want=$2 regex=$3 setup=$4 rc=0 hit
    {
        printf '\\set ON_ERROR_STOP on\nBEGIN;\n%s\nSET ROLE postgres;\n' "$setup"
        cat "$work/036_body.sql"
        printf 'ROLLBACK;\n'
    } | psql_as supabase_admin > "$work/neg036.log" 2>&1 || rc=$?
    hit=$(grep -Eo "$regex" "$work/neg036.log" | head -1 || true)
    if [[ $want == 0 && $rc -eq 0 ]] || [[ $want == nonzero && $rc -ne 0 && -n $hit ]]; then
        pass "$label  =>  rc=$rc ${hit:+| $hit}"
    else
        fail "$label  =>  rc=$rc, expected rc $want and /$regex/"
        tail -5 "$work/neg036.log"
    fi
}

negative036 "m0 unmodified body inside BEGIN/ROLLBACK applies (harness control)" 0 '' ''
negative036 "m1 a 035 function callable by authenticated" nonzero \
    'unsafe ai_\* functions in public: ai_revoke\(' \
    "DO \$\$ BEGIN EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO authenticated', 'public.ai_revoke'::regproc::regprocedure); END \$\$;"
negative036 "m2 another ai_* definer in public" nonzero \
    'unsafe ai_\* functions in public: ai_probe\(\)' \
    "CREATE FUNCTION public.ai_probe() RETURNS int LANGUAGE sql SECURITY DEFINER AS 'SELECT 1'; ALTER FUNCTION public.ai_probe() OWNER TO postgres; REVOKE ALL ON FUNCTION public.ai_probe() FROM PUBLIC;"
negative036 "m3 an ai_* function owned by another role" nonzero \
    'unsafe ai_\* functions in public: ai_quota\(' \
    'ALTER FUNCTION public.ai_quota OWNER TO supabase_admin;'
negative036 "m4 client USAGE on schema private" nonzero \
    'private\.ai_pending_requests is not safely owned and confined' \
    'GRANT USAGE ON SCHEMA private TO authenticated;'
fp036b=$(psql_as supabase_admin < "$here/fingerprint.sql")
if [[ $fp036a == "$fp036b" ]]; then pass "catalog unchanged by the 036 negative controls"; else fail "036 negative controls changed the catalog"; fi

stage "035 ledger scenarios again, after 036 replaced ai_grant"
cat "$here/probe_lib.sql" "$here/035/scenarios.sql" | psql_as supabase_admin > "$work/scenarios035b.log" 2>&1
tally "$work/scenarios035b.log"

# Concurrency: N sessions of the same account ask at once. The real function
# must answer 'created' exactly once (one request, one operator email). A
# naive copy that reads, pauses and then writes answers 'created' more than
# once: if it does not, the probe cannot tell.
concurrent_ask() {  # <function> <sessions>
    local fn=$1 n=$2 i
    psql_as supabase_admin -q -c "DELETE FROM public.ai_access_requests; DELETE FROM public.ai_entitlements;"
    for i in $(seq 1 "$n"); do
        psql_as supabase_admin -At -c "SET ROLE service_role; SELECT outcome FROM $fn('b0000000-0000-4000-8000-000000000002', NULL);" > "$work/ask_$i.out" 2>&1 &
    done
    wait
    cat "$work"/ask_*.out | grep -c '^created$' || true
    rm -f "$work"/ask_*.out
}
stage "036 concurrency: one request and one email per account (with a naive control)"
psql_as supabase_admin -v ON_ERROR_STOP=1 -q > "$work/probe036.log" 2>&1 <<'SQL'
CREATE SCHEMA probe036;
GRANT USAGE ON SCHEMA probe036 TO service_role;
CREATE FUNCTION probe036.request_naive(p_user_id uuid, p_note text)
RETURNS TABLE (outcome text)
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.ai_access_requests AS r
                WHERE r.user_id = p_user_id AND r.status = 'pending') THEN
        RETURN QUERY SELECT 'pending'::text;
        RETURN;
    END IF;
    PERFORM pg_sleep(1.0);
    INSERT INTO public.ai_access_requests (user_id, status, note, requested_at)
    VALUES (p_user_id, 'pending', p_note, now())
    ON CONFLICT (user_id) DO UPDATE SET requested_at = now();
    RETURN QUERY SELECT 'created'::text;
END
$$;
GRANT EXECUTE ON FUNCTION probe036.request_naive(uuid, text) TO service_role;
SQL
if grep -q 'ERROR' "$work/probe036.log"; then fail "036 concurrency probe setup"; cat "$work/probe036.log"; fi
c_real=$(concurrent_ask public.ai_request_access 12)
c_naive=$(concurrent_ask probe036.request_naive 12)
echo "'created' answers of 12 concurrent requests from one account: real=$c_real naive=$c_naive"
if [[ $c_real == 1 ]]; then pass "real ai_request_access created exactly once"; else fail "real ai_request_access created $c_real times"; fi
if [[ $c_naive =~ ^[0-9]+$ && $c_naive -gt 1 ]]; then pass "naive control created $c_naive times: the probe can say no"; else fail "naive control created $c_naive times: the probe cannot tell"; fi
psql_as supabase_admin -q -c "DROP SCHEMA probe036 CASCADE; DELETE FROM public.ai_access_requests;" > /dev/null 2>&1

# Race: the operator dismisses a pending request while the same account asks
# again. The dismissal must hold ('dismissed', not 'created'). Control: the
# same function without the locked-row condition on decided_at re-opens it.
race_dismiss() {  # <function>
    local fn=$1
    psql_as supabase_admin -q -c "DELETE FROM public.ai_access_requests; DELETE FROM public.ai_entitlements;
        SET ROLE service_role; SELECT * FROM public.ai_request_access('b0000000-0000-4000-8000-000000000002', NULL);" > /dev/null
    psql_as supabase_admin -q -c "BEGIN; SET LOCAL ROLE service_role;
        SELECT public.ai_dismiss_request('b0000000-0000-4000-8000-000000000002', 'a0000000-0000-4000-8000-000000000001', NULL, NULL);
        SELECT pg_sleep(1.5); COMMIT;" > /dev/null 2>&1 &
    sleep 0.5
    psql_as supabase_admin -At -c "SET ROLE service_role; SELECT outcome FROM $fn('b0000000-0000-4000-8000-000000000002', NULL);" 2>&1 | tail -1
    wait
}
stage "036 race: a dismissal committed while the account asks again holds"
psql_as supabase_admin -v ON_ERROR_STOP=1 -q > "$work/race036.log" 2>&1 <<'SQL'
CREATE SCHEMA probe036r;
GRANT USAGE ON SCHEMA probe036r TO service_role;
DO $$
DECLARE
    v_def text := pg_get_functiondef('public.ai_request_access(uuid, text)'::regprocedure);
    -- plpgsql bodies are stored as written, so this is the source text.
    v_clause text := 'AND r.decided_at <= now() - interval ''30 days''';
BEGIN
    IF position(v_clause IN v_def) = 0 THEN
        RAISE EXCEPTION 'ai_request_access body changed: update the race probe (clause not found)';
    END IF;
    v_def := replace(v_def, 'public.ai_request_access(', 'probe036r.request_unguarded(');
    EXECUTE replace(v_def, v_clause, '');
END
$$;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA probe036r TO service_role;
SQL
if grep -q 'ERROR' "$work/race036.log"; then fail "036 race probe setup"; cat "$work/race036.log"; fi
race_real=$(race_dismiss public.ai_request_access)
race_ctrl=$(race_dismiss probe036r.request_unguarded)
echo "ask during a dismissal: real=$race_real unguarded=$race_ctrl"
if [[ $race_real == dismissed ]]; then pass "the dismissal held"; else fail "real function answered '$race_real' during a dismissal"; fi
if [[ $race_ctrl == created ]]; then pass "unguarded control re-opened the request: the probe can say no"; else fail "unguarded control answered '$race_ctrl': the probe cannot tell"; fi
psql_as supabase_admin -q -c "DROP SCHEMA probe036r CASCADE; DELETE FROM public.ai_access_requests;" > /dev/null 2>&1

# Recovery path documented in 036 and postcheck qc05: 035 re-applied after
# 036 drops ai_grant's closing statement; qc05 must FAIL, the preflight must
# still pass (table present with 036's columns, ai_grant at 035's md5), and
# applying 036 again must restore qc05.
stage "036 recovery: 035 re-applied after 036, then 036 again"
rc=0
psql_as postgres -v ON_ERROR_STOP=1 < "$m035" > "$work/apply035_again.log" 2>&1 || rc=$?
if [[ $rc -eq 0 ]]; then pass "035 re-applied after 036 rc=0"; else fail "035 re-apply rc=$rc"; cat "$work/apply035_again.log"; fi
psql_as postgres -At < "$here/036/postcheck.sql" > "$work/postcheck036_after035.log" 2>&1
cat "$work/postcheck036_after035.log"
expect_lines "$work/postcheck036_after035.log" "postcheck reports the re-applied 035" '^FAIL +qc05 .*md5 [0-9a-f]{32}$'
psql_as postgres -At < "$here/036/preflight.sql" > "$work/preflight036_recovery.log" 2>&1
tally "$work/preflight036_recovery.log"
rc=0
psql_as postgres -v ON_ERROR_STOP=1 < "$m036" > "$work/apply036_3.log" 2>&1 || rc=$?
if [[ $rc -eq 0 ]]; then pass "036 re-applied rc=0"; else fail "036 re-apply rc=$rc"; cat "$work/apply036_3.log"; fi
psql_as postgres -At < "$here/036/postcheck.sql" > "$work/postcheck036_recovered.log" 2>&1
tally "$work/postcheck036_recovered.log"
fp036c=$(psql_as supabase_admin < "$here/fingerprint.sql")
if [[ -n $fp7 && $fp036c == "$fp7" ]]; then pass "catalog after recovery equals the catalog after the first 036 apply"; else fail "catalog after recovery differs from the first 036 apply"; fi

# Migration 040 (retention of AI access requests) needs pg_cron, which only
# the Supabase image ships.
cron_available=$(psql_as supabase_admin -At -c "SELECT count(*) FROM pg_available_extensions WHERE name = 'pg_cron'")
if [[ $cron_available != 1 ]]; then
    stage "040 skipped"
    echo "INFO  pg_cron is not available in $image; run with the Supabase image to exercise 040"
else
    cron_jobs="SELECT string_agg(concat_ws('|', jobid, jobname, schedule, command, username, database, active), E'\n' ORDER BY jobname) FROM cron.job"

    stage "040 preflight (read-only, as postgres)"
    psql_as postgres -At < "$here/040/preflight.sql" > "$work/preflight040.log" 2>&1
    tally "$work/preflight040.log"

    stage "040 refuses a changed ai_forget_user (planted in a rolled-back transaction)"
    rc=0
    {
        printf '\\set ON_ERROR_STOP on\nBEGIN;\n'
        printf '%s\n' "DO \$\$ BEGIN EXECUTE replace(pg_get_functiondef('public.ai_forget_user(uuid)'::regprocedure), 'BEGIN', 'BEGIN' || chr(10) || '    -- local hot-fix'); END \$\$;"
        cat "$here/040/preflight.sql"
        printf 'SET ROLE postgres;\n'
        sed -e '/^BEGIN;$/d' -e '/^COMMIT;$/d' "$m040"
        printf 'ROLLBACK;\n'
    } | psql_as supabase_admin -At > "$work/n5_040.log" 2>&1 || rc=$?
    cat "$work/n5_040.log"
    expect_lines "$work/n5_040.log" "040 preflight and body refuse a changed ai_forget_user" \
        '^FAIL +pf05 .*md5 [0-9a-f]{32}$' \
        "ai_forget_user is not 036's or 040's"
    if [[ $rc -ne 0 ]]; then pass "n5 the body aborted (rc=$rc)"; else fail "n5 the body applied over a changed ai_forget_user"; fi

    stage "apply 040 as postgres (1st)"
    rc=0
    psql_as postgres -v ON_ERROR_STOP=1 < "$m040" > "$work/apply040_1.log" 2>&1 || rc=$?
    grep -E 'ERROR|WARNING' "$work/apply040_1.log" || true
    if [[ $rc -eq 0 ]]; then pass "040 apply #1 rc=0"; else fail "040 apply #1 rc=$rc"; cat "$work/apply040_1.log"; exit 1; fi
    fp8=$(psql_as supabase_admin < "$here/fingerprint.sql")
    jobs8=$(psql_as supabase_admin -At -c "$cron_jobs")

    stage "apply 040 as postgres (2nd, must be a no-op)"
    rc=0
    psql_as postgres -v ON_ERROR_STOP=1 < "$m040" > "$work/apply040_2.log" 2>&1 || rc=$?
    if [[ $rc -eq 0 ]]; then pass "040 apply #2 rc=0"; else fail "040 apply #2 rc=$rc"; cat "$work/apply040_2.log"; fi
    fp9=$(psql_as supabase_admin < "$here/fingerprint.sql")
    jobs9=$(psql_as supabase_admin -At -c "$cron_jobs")
    if [[ -n $fp8 && $fp8 == "$fp9" ]]; then pass "catalog fingerprint unchanged by the 2nd 040 apply"; else fail "catalog fingerprint changed by the 2nd 040 apply"; fi
    if [[ -n $jobs8 && $jobs8 == "$jobs9" ]]; then pass "cron jobs unchanged by the 2nd 040 apply (same ids)"; else fail "cron jobs changed by the 2nd 040 apply"; printf '%s\n---\n%s\n' "$jobs8" "$jobs9"; fi

    stage "036 and 040 postchecks after 040 (read-only)"
    psql_as postgres -At < "$here/036/postcheck.sql" > "$work/postcheck036_after040.log" 2>&1
    tally "$work/postcheck036_after040.log"
    psql_as postgres -At < "$here/040/postcheck.sql" > "$work/postcheck040.log" 2>&1
    tally "$work/postcheck040.log"

    stage "040 postcheck must report a stale decided request (planted in a rolled-back transaction)"
    {
        printf 'BEGIN;\nSET session_replication_role = replica;\n'
        printf "INSERT INTO auth.users (id, email) VALUES ('40000000-0000-4000-8000-0000000004c1', 'c1@example.test');\n"
        printf "INSERT INTO public.ai_access_requests (user_id, status, requested_at, decided_at) VALUES ('40000000-0000-4000-8000-0000000004c1', 'dismissed', now() - interval '60 days', now() - interval '40 days');\n"
        printf 'SET session_replication_role = origin;\nSET ROLE postgres;\n'
        cat "$here/040/postcheck.sql"
        printf 'ROLLBACK;\n'
    } | psql_as supabase_admin -At > "$work/postcheck040_planted.log" 2>&1
    cat "$work/postcheck040_planted.log"
    expect_lines "$work/postcheck040_planted.log" "040 postcheck reports" '^FAIL +rc06 .*=>  1 left$'

    stage "040 scenarios (purge horizon, erasure, who can reach what)"
    cat "$here/probe_lib.sql" "$here/040/scenarios.sql" | psql_as supabase_admin > "$work/scenarios040.log" 2>&1
    tally "$work/scenarios040.log"

    # The job itself, not only its command: a copy scheduled every 2 seconds
    # must delete the 31-day row and keep the 29-day one (the control).
    stage "040 the purge runs from pg_cron"
    psql_as supabase_admin -v ON_ERROR_STOP=1 -q > "$work/cron040.log" 2>&1 <<'SQL'
SET session_replication_role = replica;
INSERT INTO auth.users (id, email) VALUES
    ('40000000-0000-4000-8000-0000000004b1', 'b1@example.test'),
    ('40000000-0000-4000-8000-0000000004b2', 'b2@example.test');
SET session_replication_role = origin;
INSERT INTO public.ai_access_requests (user_id, status, requested_at, decided_at) VALUES
    ('40000000-0000-4000-8000-0000000004b1', 'dismissed', now() - interval '40 days', now() - interval '31 days'),
    ('40000000-0000-4000-8000-0000000004b2', 'dismissed', now() - interval '40 days', now() - interval '29 days');
SET ROLE postgres;
SELECT cron.schedule('meridianiq-replica-probe', '2 seconds', 'SELECT public.ai_purge_decided_requests()');
SQL
    if grep -q 'ERROR' "$work/cron040.log"; then fail "040 cron probe setup"; cat "$work/cron040.log"; fi
    left=""
    for _ in $(seq 1 15); do
        left=$(psql_as supabase_admin -At -c "SELECT string_agg(right(user_id::text, 2), ',' ORDER BY user_id) FROM public.ai_access_requests WHERE user_id::text LIKE '40000000-%-0000000004b_'")
        [[ $left == b2 ]] && break
        sleep 1
    done
    runs=$(psql_as supabase_admin -At -c "SELECT count(*) FILTER (WHERE status = 'succeeded') || ' succeeded, ' || count(*) FILTER (WHERE status = 'failed') || ' failed' FROM cron.job_run_details WHERE jobid = (SELECT jobid FROM cron.job WHERE jobname = 'meridianiq-replica-probe')")
    echo "rows left: ${left:-none}; runs: $runs"
    if [[ $left == b2 ]]; then pass "pg_cron deleted the 31-day row and kept the 29-day control"; else fail "after the cron runs the rows left are '${left:-none}', expected b2"; fi
    if [[ $runs =~ ^[1-9][0-9]*\ succeeded,\ 0\ failed$ ]]; then pass "cron runs: $runs"; else fail "cron runs: $runs"; fi
    psql_as supabase_admin -q -c "SET ROLE postgres; SELECT cron.unschedule('meridianiq-replica-probe'); RESET ROLE;
        DELETE FROM cron.job_run_details WHERE jobid NOT IN (SELECT jobid FROM cron.job);
        DELETE FROM public.ai_access_requests WHERE user_id::text LIKE '40000000-%';
        DELETE FROM auth.users WHERE id::text LIKE '40000000-%';" > /dev/null 2>&1

    stage "negative controls: 040 must abort (each in a rolled-back transaction)"
    [[ $(grep -c '^BEGIN;$' "$m040") -eq 1 && $(grep -c '^COMMIT;$' "$m040") -eq 1 ]] \
        || { fail "040 does not have exactly one BEGIN; and one COMMIT; line"; exit 1; }
    sed -e '/^BEGIN;$/d' -e '/^COMMIT;$/d' "$m040" > "$work/040_body.sql"
    fp040a=$(psql_as supabase_admin < "$here/fingerprint.sql")
    negative040() {  # <label> <expected rc: 0|nonzero> <regex> <setup SQL run after the body's REVOKEs would undo it>
        local label=$1 want=$2 regex=$3 setup=$4 rc=0 hit
        {
            printf '\\set ON_ERROR_STOP on\nBEGIN;\nSET ROLE postgres;\n'
            # The setup goes right before the guard, so the body's own
            # REVOKEs cannot undo it.
            sed -n '1,/^-- 4\. Guard/p' "$work/040_body.sql" | sed '$d'
            printf 'RESET ROLE;\n%s\nSET ROLE postgres;\n' "$setup"
            sed -n '/^-- 4\. Guard/,$p' "$work/040_body.sql"
            printf 'ROLLBACK;\n'
        } | psql_as supabase_admin > "$work/neg040.log" 2>&1 || rc=$?
        hit=$(grep -Eo "$regex" "$work/neg040.log" | head -1 || true)
        if [[ $want == 0 && $rc -eq 0 ]] || [[ $want == nonzero && $rc -ne 0 && -n $hit ]]; then
            pass "$label  =>  rc=$rc ${hit:+| $hit}"
        else
            fail "$label  =>  rc=$rc, expected rc $want and /$regex/"
            tail -5 "$work/neg040.log"
        fi
    }
    negative040 "n0 unmodified body inside BEGIN/ROLLBACK applies (harness control)" 0 '' ''
    negative040 "n1 service_role can call the purge" nonzero \
        'service_role can call ai_purge_decided_requests' \
        'GRANT EXECUTE ON FUNCTION public.ai_purge_decided_requests() TO service_role;'
    negative040 "n2 a client role can use schema cron" nonzero \
        'authenticated has USAGE on schema cron' \
        'GRANT USAGE ON SCHEMA cron TO authenticated;'
    negative040 "n3 the purge job is not scheduled" nonzero \
        'the two meridianiq cron jobs are not scheduled as expected' \
        "SET ROLE postgres; SELECT cron.unschedule('meridianiq-ai-requests-purge'); RESET ROLE;"
    negative040 "n4 ai_forget_user callable by authenticated" nonzero \
        'ai_forget_user is not service_role only' \
        'GRANT EXECUTE ON FUNCTION public.ai_forget_user(uuid) TO authenticated;'
    fp040b=$(psql_as supabase_admin < "$here/fingerprint.sql")
    if [[ $fp040a == "$fp040b" ]]; then pass "catalog unchanged by the 040 negative controls"; else fail "040 negative controls changed the catalog"; fi

    # Recovery path documented in 040 and its postcheck rc02: 036 re-applied
    # after 040 restores ai_forget_user without the note; rc02 must FAIL, and
    # applying 040 again must restore it.
    stage "040 recovery: 036 re-applied after 040, then 040 again"
    rc=0
    psql_as postgres -v ON_ERROR_STOP=1 < "$m036" > "$work/apply036_after040.log" 2>&1 || rc=$?
    if [[ $rc -eq 0 ]]; then pass "036 re-applied after 040 rc=0"; else fail "036 re-apply after 040 rc=$rc"; cat "$work/apply036_after040.log"; fi
    psql_as postgres -At < "$here/040/postcheck.sql" > "$work/postcheck040_after036.log" 2>&1
    cat "$work/postcheck040_after036.log"
    expect_lines "$work/postcheck040_after036.log" "040 postcheck reports the re-applied 036" '^FAIL +rc02 .*md5 [0-9a-f]{32}$'
    rc=0
    psql_as postgres -v ON_ERROR_STOP=1 < "$m040" > "$work/apply040_3.log" 2>&1 || rc=$?
    if [[ $rc -eq 0 ]]; then pass "040 re-applied rc=0"; else fail "040 re-apply rc=$rc"; cat "$work/apply040_3.log"; fi
    psql_as postgres -At < "$here/040/postcheck.sql" > "$work/postcheck040_recovered.log" 2>&1
    tally "$work/postcheck040_recovered.log"
    fp040c=$(psql_as supabase_admin < "$here/fingerprint.sql")
    if [[ -n $fp8 && $fp040c == "$fp8" ]]; then pass "catalog after recovery equals the catalog after the first 040 apply"; else fail "catalog after recovery differs from the first 040 apply"; fi
fi

stage "summary ($image)"
echo "failures=$failures"
[[ $failures -eq 0 ]]
