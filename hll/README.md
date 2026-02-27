# hll
<!--
SPDX-FileCopyrightText: Copyright © contributors to CloudNativePG, established as CloudNativePG a Series of LF Projects, LLC.
SPDX-License-Identifier: Apache-2.0
-->

[hll](https://github.com/citusdata/postgresql-hll) is a PostgreSQL extension adding the
HyperLogLog data type for fast, space-efficient approximate distinct value counting, enabling
efficient cardinality estimation over large datasets.

## Usage

### 1. Add the hll extension image to your Cluster

Define the `hll` extension under the `postgresql.extensions` section of
your `Cluster` resource. For example:

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
SELECT hll_empty();
```

You should see `hll` listed among the installed extensions.

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

All relevant license and copyright information for the `hll` extension
and its dependencies are bundled within the image at:

```text
/licenses/
```

By using this image, you agree to comply with the terms of the licenses
contained therein.
