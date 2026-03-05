# HypoPG

[HypoPG](https://github.com/HypoPG/hypopg) is an open-source extension
that provides hypothetical indexes for PostgreSQL, allowing you to check
whether an index would improve query performance without actually creating it.

## Usage

### 1. Add the hypopg extension image to your Cluster

Define the `hypopg` extension under the `postgresql.extensions` section of
your `Cluster` resource:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: cluster-hypopg
spec:
  imageName: ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
  instances: 1

  storage:
    size: 1Gi

  postgresql:
    extensions:
    - name: hypopg
      image:
        # renovate: suite=trixie-pgdg depName=postgresql-18-hypopg
        reference: ghcr.io/cloudnative-pg/hypopg:1.4.2-18-trixie
```

### 2. Enable the extension in a database

You can install `hypopg` in a specific database by creating or updating a
`Database` resource. For example, to enable it in the `app` database:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Database
metadata:
  name: cluster-hypopg-app
spec:
  name: app
  owner: app
  cluster:
    name: cluster-hypopg
  extensions:
  - name: hypopg
    # renovate: suite=trixie-pgdg depName=postgresql-18-hypopg
    version: '1.4.2'
```

### 3. Verify installation

Once the database is ready, connect to it with `psql` and run:

```sql
\dx
```

You should see `hypopg` listed among the installed extensions.
