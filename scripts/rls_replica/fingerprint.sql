-- Catalog state that 034 touches (policies, table and column ACLs, RLS
-- flags, functions in public and private, default privileges, schema
-- private), hashed. Two applies must give the same hash.
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
                 FROM pg_proc AS p WHERE p.pronamespace IN ('public'::regnamespace, to_regnamespace('private'))), '')
    || coalesce((SELECT string_agg(concat_ws('|', c.relname, a.attname, a.attacl::text), E'\n'
                                   ORDER BY c.relname, a.attname)
                 FROM pg_attribute AS a JOIN pg_class AS c ON c.oid = a.attrelid
                 WHERE c.relnamespace = 'public'::regnamespace AND a.attacl IS NOT NULL), '')
    || coalesce((SELECT string_agg(concat_ws('|', pg_get_userbyid(defaclrole), defaclnamespace::regnamespace::text,
                                             defaclobjtype::text, defaclacl::text), E'\n'
                                   ORDER BY 1)
                 FROM pg_default_acl), '')
    || coalesce((SELECT concat_ws('|', nspname, pg_get_userbyid(nspowner), nspacl::text)
                 FROM pg_namespace WHERE nspname = 'private'), ''))
    || '  policies=' || (SELECT count(*) FROM pg_policies WHERE schemaname = 'public')
    || '  functions=' || (SELECT count(*) FROM pg_proc WHERE pronamespace IN ('public'::regnamespace, to_regnamespace('private')))
    || '  default_acls=' || (SELECT count(*) FROM pg_default_acl);
