# pg-partman
<!--
SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
SPDX-License-Identifier: Apache-2.0
-->

[pg_partman](https://github.com/pgpartman/pg_partman) creates and maintains
time-based and ID-based PostgreSQL partition sets. Its optional background
worker can run partition maintenance automatically.

## Usage

Add the image to a Cluster and preload the background worker:

~~~yaml
postgresql:
  shared_preload_libraries:
  - pg_partman_bgw
  extensions:
  - name: pg-partman
    image:
      # renovate: suite=trixie-pgdg depName=postgresql-18-partman
      reference: ghcr.io/cnpg-extensions/pg-partman:5.5.0-18-trixie
~~~

Enable the SQL extension in a Database, conventionally in the partman schema:

~~~yaml
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
    # renovate: suite=trixie-pgdg depName=postgresql-18-partman extractVersion=^(?<version>\d+\.\d+\.\d+)
    version: '5.5.0'
~~~

See the [pg_partman documentation](https://github.com/pgpartman/pg_partman/tree/development/doc)
for partition-set configuration examples.

## Contributors

This extension is maintained by:

- Jeremy Schneider (@ardentperf)

## Licenses and Copyright

The package copyright and license notice are included in the image under
/licenses/postgresql-18-partman/.
