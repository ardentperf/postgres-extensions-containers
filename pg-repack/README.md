# pg_repack

[pg_repack](https://github.com/reorg/pg_repack) is an open-source extension
that lets you reclaim storage occupied by dead tuples in tables and indexes
without locking, making it a useful alternative to `VACUUM FULL`.

## Usage

### 1. Add the pg-repack extension image to your Cluster

Define the `pg-repack` extension under the `postgresql.extensions` section of
your `Cluster` resource:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: cluster-pg-repack
spec:
  imageName: ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
  instances: 1

  storage:
    size: 1Gi

  postgresql:
    extensions:
    - name: pg-repack
      image:
        # renovate: suite=trixie-pgdg depName=postgresql-18-repack
        reference: ghcr.io/cloudnative-pg/pg-repack:1.5.3-18-trixie
```

### 2. Enable the extension in a database

You can install `pg_repack` in a specific database by creating or updating a
`Database` resource. For example, to enable it in the `app` database:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Database
metadata:
  name: cluster-pg-repack-app
spec:
  name: app
  owner: app
  cluster:
    name: cluster-pg-repack
  extensions:
  - name: pg_repack
    # renovate: suite=trixie-pgdg depName=postgresql-18-repack
    version: '1.5.3'
```

### 3. Verify installation

Once the database is ready, connect to it with `psql` and run:

```sql
\dx
```

You should see `pg_repack` listed among the installed extensions.
