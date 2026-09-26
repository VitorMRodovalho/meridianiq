-- Probe helpers, created in pg_temp for the current session only.
--
-- run_as(role, uid, sql [, setup [, after]]) runs `setup` as the session user,
-- then `sql` as `role` with request.jwt.claims set the way PostgREST sets
-- them (sub = uid, role = role), then `after` as the session user, and
-- returns 'OK <first column of sql>[ | after: <first column of after>]' or
-- 'ERR <sqlstate> <message>'. Everything it does is rolled back: the block
-- always ends in an exception, so probes never change the fixtures.
--
-- expect(label, pattern, actual) prints PASS or FAIL; `pattern` is a LIKE
-- pattern matched against the whole result.

\set QUIET on
\pset footer off
\pset tuples_only on
\pset format unaligned

CREATE FUNCTION pg_temp.run_as(
    p_role  text,
    p_uid   uuid,
    p_sql   text,
    p_setup text DEFAULT NULL,
    p_after text DEFAULT NULL
) RETURNS text
LANGUAGE plpgsql AS $fn$
DECLARE
    v_out   text;
    v_after text;
    v_rows  bigint;
BEGIN
    BEGIN
        IF p_setup IS NOT NULL THEN
            EXECUTE p_setup;
        END IF;
        PERFORM set_config(
            'request.jwt.claims',
            CASE WHEN p_uid IS NULL
                 THEN json_build_object('role', p_role)::text
                 ELSE json_build_object('sub', p_uid, 'role', p_role)::text
            END,
            true);
        -- The older per-claim setting, read by older auth.uid() definitions.
        PERFORM set_config('request.jwt.claim.sub', coalesce(p_uid::text, ''), true);
        EXECUTE format('SET LOCAL ROLE %I', p_role);
        IF p_sql ~* '^\s*(insert|update|delete|truncate)\M' AND p_sql !~* '\mreturning\M' THEN
            -- A write without RETURNING: report the affected row count.
            EXECUTE p_sql;
            GET DIAGNOSTICS v_rows = ROW_COUNT;
            v_out := 'rows=' || v_rows;
        ELSE
            EXECUTE p_sql INTO v_out;
        END IF;
        EXECUTE 'SET LOCAL ROLE NONE';
        PERFORM set_config('request.jwt.claims', '', true);
        PERFORM set_config('request.jwt.claim.sub', '', true);
        IF p_after IS NOT NULL THEN
            EXECUTE p_after INTO v_after;
            v_out := coalesce(v_out, '<null>') || ' | after: ' || coalesce(v_after, '<null>');
        END IF;
        RAISE EXCEPTION USING ERRCODE = 'ZZ999', MESSAGE = coalesce(v_out, '<null>');
    EXCEPTION
        WHEN SQLSTATE 'ZZ999' THEN
            RETURN 'OK ' || SQLERRM;
        WHEN OTHERS THEN
            RETURN 'ERR ' || SQLSTATE || ' ' || SQLERRM;
    END;
END
$fn$;

CREATE FUNCTION pg_temp.expect(p_label text, p_pattern text, p_actual text)
RETURNS text
LANGUAGE sql AS $fn$
    SELECT CASE WHEN p_actual LIKE p_pattern
                THEN 'PASS  ' || p_label || '  =>  ' || p_actual
                ELSE 'FAIL  ' || p_label || '  =>  ' || coalesce(p_actual, '<null>')
                     || '   [expected ' || p_pattern || ']'
           END
$fn$;

-- info(label, actual) records a measurement that has no pass/fail
-- expectation (a baseline).
CREATE FUNCTION pg_temp.info(p_label text, p_actual text)
RETURNS text
LANGUAGE sql AS $fn$
    SELECT 'INFO  ' || p_label || '  =>  ' || coalesce(p_actual, '<null>')
$fn$;

-- Fixture identities (fixed, synthetic).
\set A '''a0000000-0000-4000-8000-000000000001'''
\set B '''b0000000-0000-4000-8000-000000000002'''
\set C '''c0000000-0000-4000-8000-000000000003'''
\set D '''d0000000-0000-4000-8000-000000000004'''
\set E '''e0000000-0000-4000-8000-000000000005'''
\set F '''f0000000-0000-4000-8000-000000000006'''
\set X '''10000000-0000-4000-8000-0000000000a1'''
\set Y '''20000000-0000-4000-8000-0000000000a2'''
\set PA '''30000000-0000-4000-8000-0000000000b1'''
\set PD '''30000000-0000-4000-8000-0000000000b4'''
\set UA '''40000000-0000-4000-8000-0000000000c1'''
\set UD '''40000000-0000-4000-8000-0000000000c4'''
