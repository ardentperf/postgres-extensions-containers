# pgnodemx

[pgnodemx](https://github.com/pgnodemx/pgnodemx) is an open-source extension
that provides SQL functions for capturing node OS metrics directly from
PostgreSQL, including CPU, memory, disk, and cgroup statistics.

## Usage

### 1. Add the pgnodemx extension image to your Cluster

Define the `pgnodemx` extension under the `postgresql.extensions` section of
your `Cluster` resource:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: cluster-pgnodemx
spec:
  imageName: ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
  instances: 1

  storage:
    size: 1Gi

  postgresql:
    extensions:
    - name: pgnodemx
      image:
        # renovate: suite=trixie-pgdg depName=postgresql-18-pgnodemx
        reference: ghcr.io/cloudnative-pg/pgnodemx:2.0.1-18-trixie
```

### 2. Enable the extension in a database

You can install `pgnodemx` in a specific database by creating or updating a
`Database` resource. For example, to enable it in the `app` database:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Database
metadata:
  name: cluster-pgnodemx-app
spec:
  name: app
  owner: app
  cluster:
    name: cluster-pgnodemx
  extensions:
  - name: pgnodemx
    # renovate: suite=trixie-pgdg depName=postgresql-18-pgnodemx
    version: '2.0'
```

### 3. Verify installation

Once the database is ready, connect to it with `psql` and run:

```sql
\dx
```

You should see `pgnodemx` listed among the installed extensions.
