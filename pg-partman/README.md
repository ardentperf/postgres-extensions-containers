# pg_partman

[pg_partman](https://github.com/pgpartman/pg_partman) is an open-source
extension that provides partition management for PostgreSQL, supporting both
time-based and serial-based table partitioning.

## Usage

### 1. Add the pg-partman extension image to your Cluster

Define the `pg-partman` extension under the `postgresql.extensions` section of
your `Cluster` resource:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: cluster-pg-partman
spec:
  imageName: ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
  instances: 1

  storage:
    size: 1Gi

  postgresql:
    shared_preload_libraries:
      - pg_partman_bgw
    extensions:
    - name: pg-partman
      image:
        # renovate: suite=trixie-pgdg depName=postgresql-18-partman
        reference: ghcr.io/cloudnative-pg/pg-partman:5.4.2-18-trixie
```

### 2. Enable the extension in a database

You can install `pg_partman` in a specific database by creating or updating a
`Database` resource. For example, to enable it in the `app` database:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Database
metadata:
  name: cluster-pg-partman-app
spec:
  name: app
  owner: app
  cluster:
    name: cluster-pg-partman
  extensions:
  - name: pg_partman
    # renovate: suite=trixie-pgdg depName=postgresql-18-partman
    version: '5.4.1'
```

### 3. Verify installation

Once the database is ready, connect to it with `psql` and run:

```sql
\dx
```

You should see `pg_partman` listed among the installed extensions.
