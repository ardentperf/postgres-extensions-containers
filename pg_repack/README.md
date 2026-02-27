# pg_repack
<!--
SPDX-FileCopyrightText: Copyright © contributors to CloudNativePG, established as CloudNativePG a Series of LF Projects, LLC.
SPDX-License-Identifier: Apache-2.0
-->

[pg_repack](https://github.com/reorg/pg_repack) is a PostgreSQL extension that lets you remove
bloat from tables and indexes, and optionally restore the physical order of clustered indexes,
all with minimal locks.

## Usage

### 1. Add the pg_repack extension image to your Cluster

Define the `pg_repack` extension under the `postgresql.extensions` section of
your `Cluster` resource. For example:

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
    - name: pg_repack
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
SELECT repack.version();
```

You should see `pg_repack` listed among the installed extensions.

## Contributors

This extension is maintained by:

- Jeremy Schneider (@ardentperf)

The maintainers are responsible for:

- Monitoring upstream releases and security vulnerabilities.
- Ensuring compatibility with supported PostgreSQL versions.
- Reviewing and merging contributions specific to this extension's container
  image and lifecycle.

---

## Licenses and Copyright

This container image contains software that may be licensed under various
open-source licenses.

All relevant license and copyright information for the `pg_repack` extension
and its dependencies are bundled within the image at:

```text
/licenses/
```

By using this image, you agree to comply with the terms of the licenses
contained therein.
