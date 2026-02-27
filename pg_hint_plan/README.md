# pg_hint_plan
<!--
SPDX-FileCopyrightText: Copyright © contributors to CloudNativePG, established as CloudNativePG a Series of LF Projects, LLC.
SPDX-License-Identifier: Apache-2.0
-->

[pg_hint_plan](https://github.com/ossc-db/pg_hint_plan) makes it possible to tweak PostgreSQL
execution plans using so-called "hints" in SQL comments, providing fine-grained control over
the query planner without modifying application code.

## Usage

### 1. Add the pg_hint_plan extension image to your Cluster

Define the `pg_hint_plan` extension under the `postgresql.extensions` section of
your `Cluster` resource. For example:

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
      - "pg_hint_plan"

    extensions:
    - name: pg_hint_plan
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
/*+ SeqScan(t) */ EXPLAIN SELECT * FROM t WHERE id = 1;
```

You should see `pg_hint_plan` listed among the installed extensions.

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

All relevant license and copyright information for the `pg_hint_plan` extension
and its dependencies are bundled within the image at:

```text
/licenses/
```

By using this image, you agree to comply with the terms of the licenses
contained therein.
