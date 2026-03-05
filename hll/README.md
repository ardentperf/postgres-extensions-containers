# HLL Extension

[HLL (HyperLogLog)](https://github.com/citusdata/postgresql-hll) is an open-source
extension that adds the HyperLogLog data structure to PostgreSQL, enabling fast
and space-efficient approximate distinct count operations on large datasets.

## Usage

### 1. Add the hll extension image to your Cluster

Define the `hll` extension under the `postgresql.extensions` section of
your `Cluster` resource:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: cluster-hll
spec:
  imageName: ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
  instances: 1

  storage:
    size: 1Gi

  postgresql:
    extensions:
    - name: hll
      image:
        # renovate: suite=trixie-pgdg depName=postgresql-18-hll
        reference: ghcr.io/cloudnative-pg/hll:2.19-18-trixie
```

### 2. Enable the extension in a database

You can install `hll` in a specific database by creating or updating a
`Database` resource. For example, to enable it in the `app` database:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Database
metadata:
  name: cluster-hll-app
spec:
  name: app
  owner: app
  cluster:
    name: cluster-hll
  extensions:
  - name: hll
    # renovate: suite=trixie-pgdg depName=postgresql-18-hll
    version: '2.19'
```

### 3. Verify installation

Once the database is ready, connect to it with `psql` and run:

```sql
\dx
```

You should see `hll` listed among the installed extensions.
