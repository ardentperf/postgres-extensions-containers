# pgsentinel

[pgsentinel](https://github.com/pgsentinel/pgsentinel) is an open-source
extension that provides active session history sampling for PostgreSQL,
enabling detailed analysis of database activity over time.

## Usage

### 1. Add the pgsentinel extension image to your Cluster

Define the `pgsentinel` extension under the `postgresql.extensions` section of
your `Cluster` resource:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: cluster-pgsentinel
spec:
  imageName: ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
  instances: 1

  storage:
    size: 1Gi

  postgresql:
    shared_preload_libraries:
      - pg_stat_statements
      - pgsentinel
    extensions:
    - name: pgsentinel
      image:
        # renovate: suite=trixie-pgdg depName=postgresql-18-pgsentinel
        reference: ghcr.io/cloudnative-pg/pgsentinel:1.4.0-18-trixie
```

### 2. Enable the extension in a database

You can install `pgsentinel` in a specific database by creating or updating a
`Database` resource. For example, to enable it in the `app` database:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Database
metadata:
  name: cluster-pgsentinel-app
spec:
  name: app
  owner: app
  cluster:
    name: cluster-pgsentinel
  extensions:
  - name: pgsentinel
    # renovate: suite=trixie-pgdg depName=postgresql-18-pgsentinel
    version: '1.4.0'
```

### 3. Verify installation

Once the database is ready, connect to it with `psql` and run:

```sql
\dx
```

You should see `pgsentinel` listed among the installed extensions.
