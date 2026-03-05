# pg_hint_plan

[pg_hint_plan](https://github.com/ossc-db/pg_hint_plan) is an open-source
extension that allows you to control query execution plans in PostgreSQL using
hint phrases in SQL comments.

## Usage

### 1. Add the pg-hint-plan extension image to your Cluster

Define the `pg-hint-plan` extension under the `postgresql.extensions` section of
your `Cluster` resource:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: cluster-pg-hint-plan
spec:
  imageName: ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
  instances: 1

  storage:
    size: 1Gi

  postgresql:
    shared_preload_libraries:
      - pg_hint_plan
    extensions:
    - name: pg-hint-plan
      image:
        # renovate: suite=trixie-pgdg depName=postgresql-18-pg-hint-plan
        reference: ghcr.io/cloudnative-pg/pg-hint-plan:1.8.0-18-trixie
```

### 2. Enable the extension in a database

You can install `pg_hint_plan` in a specific database by creating or updating a
`Database` resource. For example, to enable it in the `app` database:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Database
metadata:
  name: cluster-pg-hint-plan-app
spec:
  name: app
  owner: app
  cluster:
    name: cluster-pg-hint-plan
  extensions:
  - name: pg_hint_plan
    # renovate: suite=trixie-pgdg depName=postgresql-18-pg-hint-plan
    version: '1.8.0'
```

### 3. Verify installation

Once the database is ready, connect to it with `psql` and run:

```sql
\dx
```

You should see `pg_hint_plan` listed among the installed extensions.
