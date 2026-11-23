"""Every read-only query the tool sends.

Values go in through `%(name)s` placeholders, never formatting, and every
computed column has an alias, so callers read rows by field name.
"""

from psycopg import sql

# === Session and server ===

TRY_ADVISORY_LOCK = "SELECT pg_try_advisory_lock(%(key)s) AS acquired"

SSL_VERSION = "SELECT version FROM pg_stat_ssl WHERE pid = pg_backend_pid()"

ADMIN_FACTS = (
    "SELECT r.rolname, r.rolsuper, r.rolcreatedb, r.rolcreaterole, "
    "EXISTS (SELECT 1 FROM pg_roles m WHERE m.rolname = ANY(%(managed_superusers)s) "
    "AND pg_has_role(r.oid, m.oid, 'USAGE')) AS managed_superuser, "
    "pg_has_role(r.oid, 'pg_signal_backend', 'USAGE') AS signal_backend, "
    "current_setting('server_version') AS server_version, "
    "current_setting('createrole_self_grant') AS createrole_self_grant "
    "FROM pg_roles r WHERE r.rolname = current_user"
)

VALIDATE_SETTING = "SELECT set_config(%(setting)s, %(value)s, true) AS value"

SESSION_SETTINGS = (
    "SELECT current_user AS role, "
    "current_setting('search_path') AS search_path, "
    "current_setting('default_transaction_read_only') AS read_only"
)

QUOTE_IDENT = "SELECT quote_ident(%(name)s) AS quoted"

# === Roles and the database ===

ROLES = (
    "SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, "
    "rolreplication, rolbypassrls, shobj_description(oid, 'pg_authid') AS marker "
    "FROM pg_roles WHERE rolname = ANY(%(roles)s)"
)

MEMBERSHIPS = (
    "SELECT r.rolname AS role, m.rolname AS member, am.admin_option, "
    "am.inherit_option, am.set_option FROM pg_auth_members am "
    "JOIN pg_roles r ON r.oid = am.roleid JOIN pg_roles m ON m.oid = am.member "
    "WHERE r.rolname = ANY(%(roles)s) OR m.rolname = ANY(%(roles)s)"
)

DATABASE = (
    "SELECT d.oid, pg_get_userbyid(d.datdba) AS owner, d.datallowconn, "
    "EXISTS (SELECT 1 FROM aclexplode(COALESCE(d.datacl, acldefault('d', d.datdba))) a "
    "WHERE a.grantee = 0 AND a.privilege_type = 'CONNECT') AS public_connect "
    "FROM pg_database d WHERE d.datname = %(database)s"
)

TEMPLATE0_ENCODING = (
    "SELECT pg_encoding_to_char(encoding) AS encoding FROM pg_database "
    "WHERE datname = 'template0'"
)

ROLE_SETTINGS = (
    "SELECT r.rolname, s.setconfig FROM pg_db_role_setting s "
    "JOIN pg_roles r ON r.oid = s.setrole "
    "JOIN pg_database d ON d.oid = s.setdatabase "
    "WHERE d.datname = %(database)s AND r.rolname = ANY(%(roles)s)"
)

ROLE_DEPENDENCIES = (
    "SELECT r.rolname, s.dbid, s.classid::regclass::text AS class_name, s.objid "
    "FROM pg_shdepend s JOIN pg_roles r ON r.oid = s.refobjid "
    "WHERE s.refclassid = 'pg_authid'::regclass AND s.deptype <> 'p' "
    "AND r.rolname = ANY(%(roles)s)"
)

# === Extensions ===

EXTENSION_TRUSTED = (
    "SELECT v.trusted FROM pg_available_extension_versions v "
    "JOIN pg_available_extensions e ON e.name = v.name "
    "AND e.default_version = v.version WHERE v.name = %(name)s"
)

INSTALLED_EXTENSIONS = "SELECT extname FROM pg_extension WHERE extname = ANY(%(names)s)"

# === Schemas and privileges ===

PUBLIC_HOLDS_CREATE_ON_PUBLIC = (
    "SELECT EXISTS (SELECT 1 FROM pg_namespace n, "
    "aclexplode(COALESCE(n.nspacl, acldefault('n', n.nspowner))) a "
    "WHERE n.nspname = 'public' AND a.grantee = 0 "
    "AND a.privilege_type = 'CREATE') AS holds_create"
)

SCHEMA_OWNER = (
    "SELECT pg_get_userbyid(nspowner) AS owner FROM pg_namespace "
    "WHERE nspname = %(schema)s"
)

EXISTING_SCHEMAS = "SELECT nspname FROM pg_namespace WHERE nspname = ANY(%(schemas)s)"

SCHEMA_PRIVILEGE = (
    "SELECT has_schema_privilege(%(role)s, %(schema)s, %(privilege)s) AS held"
)

DEFAULT_PRIVILEGES = (
    "SELECT COALESCE(n.nspname, '') AS schema_name, d.defaclobjtype AS object_type, "
    "CASE WHEN a.grantee = 0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END "
    "AS grantee, a.privilege_type FROM pg_default_acl d "
    "LEFT JOIN pg_namespace n ON n.oid = d.defaclnamespace "
    "CROSS JOIN LATERAL aclexplode(d.defaclacl) a "
    "WHERE d.defaclrole = (SELECT oid FROM pg_roles WHERE rolname = %(role)s)"
)

TABLE_PRIVILEGES = (
    "SELECT c.oid::regclass::text AS relation, "
    "has_table_privilege(%(reader)s, c.oid, 'INSERT, UPDATE, DELETE, TRUNCATE') "
    "AS reader_writes, "
    "has_table_privilege(%(app)s, c.oid, 'TRUNCATE') AS app_truncates "
    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
    "WHERE n.nspname = %(schema)s AND c.relkind = ANY(%(relkinds)s)"
)

PUBLIC_EXECUTABLE_FUNCTIONS = (
    "SELECT p.oid::regprocedure::text AS signature FROM pg_proc p "
    "JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = %(schema)s "
    "AND EXISTS (SELECT 1 FROM aclexplode(COALESCE(p.proacl, "
    "acldefault('f', p.proowner))) a WHERE a.grantee = 0 "
    "AND a.privilege_type = 'EXECUTE')"
)

DEFINER_FUNCTIONS_EXECUTABLE_BY = (
    "SELECT p.oid::regprocedure::text AS signature FROM pg_proc p "
    "JOIN pg_namespace n ON n.oid = p.pronamespace "
    "WHERE p.prosecdef AND n.nspname <> ALL(%(system_schemas)s) "
    "AND has_function_privilege(%(role)s, p.oid, 'EXECUTE')"
)

# === Teardown ===

SAMPLE_RELATIONS = (
    "SELECT n.nspname || '.' || c.relname AS relation FROM pg_class c "
    "JOIN pg_namespace n ON n.oid = c.relnamespace "
    "WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast') "
    "AND n.nspname !~ '^pg_temp_' AND n.nspname !~ '^pg_toast_temp_' "
    "AND c.relkind NOT IN ('i', 'I') "
    "AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_class'::regclass "
    "AND d.objid = c.oid AND d.deptype = 'e') "
    "ORDER BY relation LIMIT %(limit)s"
)

EXTENSION_CONFIG_TABLES = (
    "SELECT n.nspname AS schema_name, c.relname AS table_name, "
    "COALESCE(u.condition, '') AS condition FROM pg_extension e "
    "CROSS JOIN LATERAL unnest(e.extconfig, e.extcondition) AS u(relid, condition) "
    "JOIN pg_class c ON c.oid = u.relid "
    "JOIN pg_namespace n ON n.oid = c.relnamespace "
    "WHERE c.relkind IN ('r', 'p') ORDER BY schema_name, table_name"
)


def config_table_has_rows(schema: str, table: str, condition: str) -> sql.Composed:
    """Whether a configuration table holds a row its extension tells `pg_dump` to dump.

    Args:
        schema: The table's schema.
        table: The table's name.
        condition: The table's `extcondition`, such as `WHERE NOT builtin`.
            Only an extension's install script can set it, through
            `pg_extension_config_dump`.
    """
    return sql.SQL("SELECT EXISTS (SELECT 1 FROM {} {}) AS found").format(
        sql.Identifier(schema, table), sql.SQL(condition)
    )


HAS_LARGE_OBJECTS = "SELECT EXISTS (SELECT 1 FROM pg_largeobject_metadata) AS found"

OTHER_SESSIONS = (
    "SELECT pid FROM pg_stat_activity "
    "WHERE datname = %(database)s AND pid <> %(exclude_pid)s"
)

TERMINATE_BACKEND = "SELECT pg_terminate_backend(%(pid)s, %(timeout_ms)s) AS terminated"
