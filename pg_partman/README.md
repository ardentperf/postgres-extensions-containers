# pg_partman
<!--
SPDX-FileCopyrightText: Copyright © contributors to CloudNativePG, established as CloudNativePG a Series of LF Projects, LLC.
SPDX-License-Identifier: Apache-2.0
-->

[pg_partman](https://github.com/pgpartman/pg_partman) is a PostgreSQL extension to create and
manage both time-based and number-based table partition sets, with optional automatic maintenance
via the included background worker (`pg_partman_bgw`).

## Usage

### 1. Add the pg_partman extension image to your Cluster

Define the `pg_partman` extension under the `postgresql.extensions` section of
your `Cluster` resource. For example:

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
      - "pg_partman_bgw"

    extensions:
    - name: pg_partman
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
    schema: partman
    # renovate: suite=trixie-pgdg depName=postgresql-18-partman
    version: '5.4.2'
```

### 3. Verify installation

Once the database is ready, connect to it with `psql` and run:

```sql
\dx
SELECT partman.show_partitions('your_table');
```

You should see `pg_partman` listed among the installed extensions.

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

All relevant license and copyright information for the `pg_partman` extension
and its dependencies are bundled within the image at:

```text
/licenses/
```

By using this image, you agree to comply with the terms of the licenses
contained therein.
