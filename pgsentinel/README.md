# pgsentinel
<!--
SPDX-FileCopyrightText: Copyright © contributors to CloudNativePG, established as CloudNativePG a Series of LF Projects, LLC.
SPDX-License-Identifier: Apache-2.0
-->

[pgsentinel](https://github.com/pgsentinel/pgsentinel) provides Active Session History
for PostgreSQL, sampling session activity into an in-memory ring buffer.

## Usage

<!--
Usage: add instructions on how to use the extension with CloudNativePG.
Include code snippets for Cluster and Database resources as needed.
-->

### 1. Add the pgsentinel extension image to your Cluster

Define the `pgsentinel` extension under the `postgresql.extensions` section of
your `Cluster` resource. For example:

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
      - "pgsentinel"

    extensions:
    - name: pgsentinel
      image:
        # renovate: suite=trixie-pgdg depName=postgresql-18-pgsentinel
        reference: ghcr.io/cloudnative-pg/pgsentinel:1.3.1-18-trixie
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
    version: '1.3.1'
```

### 3. Verify installation

Once the database is ready, connect to it with `psql` and run:

```sql
\dx
SELECT sleep(2);
SELECT * FROM pg_active_session_history LIMIT 5;
```

You should see `pgsentinel` listed among the installed extensions.

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

All relevant license and copyright information for the `pgsentinel` extension
and its dependencies are bundled within the image at:

```text
/licenses/
```

By using this image, you agree to comply with the terms of the licenses
contained therein.
