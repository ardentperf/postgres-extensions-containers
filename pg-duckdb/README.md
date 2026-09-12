# pg_duckdb

[`pg_duckdb`](https://github.com/duckdb/pg_duckdb) adds DuckDB execution and
analytical storage features to PostgreSQL. This image builds the upstream
`v1.1.1` release from source for PostgreSQL 18 on Debian trixie and bookworm.
The image embeds DuckDB `v1.4.3` and bundles the JSON, ICU, and HTTPFS DuckDB
extensions.

## Usage

### 1. Add the pg_duckdb extension image to your Cluster

Define `pg-duckdb` under `postgresql.extensions` in your `Cluster` resource:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: cluster-pg-duckdb
spec:
  imageName: ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
  instances: 1

  storage:
    size: 1Gi

  postgresql:
    extensions:
    - name: pg-duckdb
      image:
        # The v-prefixed source tag is intentional and manually synchronized.
        reference: ghcr.io/cnpg-extensions/pg-duckdb:v1.1.1-18-trixie
```

### 2. Enable the extension in a database

The extension requires `pg_duckdb` in `shared_preload_libraries`, which the
image metadata configures. Create a `Database` resource to install it:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Database
metadata:
  name: cluster-pg-duckdb-app
spec:
  name: app
  owner: app
  cluster:
    name: cluster-pg-duckdb
  extensions:
  - name: pg-duckdb
    # SQL version cannot be updated by Renovate; if it changes, manually update
    # pg-duckdb/README.md, pg-duckdb/metadata.hcl, and renovate.json.
    version: '1.1.0'
```

Alternatively, connect as a superuser and run:

```sql
CREATE EXTENSION pg_duckdb;
```

### 3. Verify installation and execution

Check the installed SQL version and the embedded DuckDB version:

```sql
SELECT extversion FROM pg_extension WHERE extname = 'pg_duckdb';
-- 1.1.0

SELECT * FROM duckdb.query('SELECT version() AS version');
-- v1.4.3
```

DuckDB can execute an analytical query over a PostgreSQL table. The setting is
per connection, so this example enables it for the current session:

```sql
CREATE TABLE sales(day date, amount integer);
INSERT INTO sales VALUES ('2026-01-01', 10), ('2026-01-02', 20);

SET duckdb.force_execution = true;
EXPLAIN SELECT day, sum(amount) FROM sales GROUP BY day ORDER BY day;
SELECT day, sum(amount) FROM sales GROUP BY day ORDER BY day;
```

The release's EXPLAIN behavior shows the DuckDB execution path for the
PostgreSQL scan. The bundled JSON, ICU, and HTTPFS functionality is available
without installing a DuckDB extension from the Internet.

## Caveats and configuration

By default, DuckDB execution and secret management are restricted to
superusers. Set `duckdb.postgres_role` if a dedicated role should be allowed;
review the role's access to secrets and data before doing so. The upstream
[settings documentation](https://github.com/duckdb/pg_duckdb/blob/v1.1.1/docs/settings.md)
describes the full configuration surface.

Known DuckDB extensions can be downloaded at runtime when
`duckdb.autoinstall_known_extensions` and `duckdb.autoload_known_extensions`
allow it. Those downloads are stored below the PostgreSQL data directory by
default and are not part of this immutable image. Community extensions remain
disabled unless explicitly enabled.

DuckDB uses the data directory for temporary files by default, under
`DataDir/pg_duckdb/temp`, and stores downloaded extensions under
`DataDir/pg_duckdb/extensions`. Set `duckdb.temporary_directory` and
`duckdb.extension_directory` to writable paths when those defaults do not fit
the cluster's storage layout. `duckdb.enable_external_access` controls access
to HTTP and S3 resources.

Each PostgreSQL connection has its own DuckDB instance. Set
`duckdb.max_memory` (or `duckdb.memory_limit`) and `duckdb.threads` (or
`duckdb.worker_threads`) conservatively when many connections can execute
DuckDB queries at once.

## Contributors

This extension is maintained by:

- @ardentperf

Maintainers review upstream release changes, source pins, vendored dependency
inventory, runtime library closure, and the generated SBOM before updating the
image.

## Licenses and Copyright

The image contains software under several open-source licenses. Complete
license and copyright information for pg_duckdb, DuckDB, bundled dependencies,
and copied system libraries is included in the image under:

```text
/licenses/
```

Optional extensions downloaded at runtime have their own license obligations
and are outside the immutable image inventory.
