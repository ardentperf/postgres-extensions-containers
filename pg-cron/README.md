# pg_cron

[pg_cron](https://github.com/citusdata/pg_cron) is an open-source extension
that provides a cron-based job scheduler for PostgreSQL, allowing you to run
scheduled database maintenance tasks directly from the database.

> **Note:** pg_cron can only be installed in the `postgres` database, as it
> uses the PostgreSQL background worker infrastructure tied to that database.

## Usage

### 1. Add the pg-cron extension image to your Cluster

Define the `pg-cron` extension under the `postgresql.extensions` section of
your `Cluster` resource:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: cluster-pg-cron
spec:
  imageName: ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
  instances: 1

  storage:
    size: 1Gi

  postgresql:
    shared_preload_libraries:
      - pg_cron
    extensions:
    - name: pg-cron
      image:
        # renovate: suite=trixie-pgdg depName=postgresql-18-cron
        reference: ghcr.io/cloudnative-pg/pg-cron:1.6.7-18-trixie
```

### 2. Enable the extension in the postgres database

pg_cron must be installed in the `postgres` database. Create a `Database`
resource targeting the `postgres` database:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Database
metadata:
  name: cluster-pg-cron-postgres
spec:
  name: postgres
  owner: postgres
  cluster:
    name: cluster-pg-cron
  extensions:
  - name: pg_cron
    # renovate: suite=trixie-pgdg depName=postgresql-18-cron
    version: '1.6'
```

### 3. Verify installation

Once the database is ready, connect to the `postgres` database with `psql` and run:

```sql
\dx
```

You should see `pg_cron` listed among the installed extensions.
