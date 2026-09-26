-- Catalog state that 034 touches, hashed. Two applies must give the same hash.
\pset footer off
\pset tuples_only on
\pset format unaligned
SELECT 'fingerprint ' || md5(
    coalesce((SELECT string_agg(concat_ws('|', tablename, policyname, permissive, roles::text, cmd, qual, with_check), E'\n'
                                ORDER BY tablename, policyname)
              FROM pg_policies WHERE schemaname = 'public'), '')
    || coalesce((SELECT string_agg(concat_ws('|', relname, relacl::text, relrowsecurity, relforcerowsecurity), E'\n'
                                   ORDER BY relname)
                 FROM pg_class WHERE relnamespace = 'public'::regnamespace AND relkind = 'r'), '')
    || coalesce((SELECT string_agg(concat_ws('|', p.oid::regprocedure::text, p.prosrc, p.proconfig::text, p.proacl::text,
                                             pg_get_userbyid(p.proowner), p.prosecdef, p.provolatile::text,
                                             obj_description(p.oid, 'pg_proc')), E'\n'
                                   ORDER BY p.oid::regprocedure::text)
                 FROM pg_proc AS p WHERE p.pronamespace = 'public'::regnamespace), ''))
    || '  policies=' || (SELECT count(*) FROM pg_policies WHERE schemaname = 'public')
    || '  functions=' || (SELECT count(*) FROM pg_proc WHERE pronamespace = 'public'::regnamespace);
