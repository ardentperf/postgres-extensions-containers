# pg-squash
<!--
SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
SPDX-License-Identifier: Apache-2.0
-->

The requested pg-squash image contains the upstream
[pg_squeeze](https://github.com/cybertec-postgresql/pg_squeeze) extension. It
removes unused table space and can sort tuples according to an index while
allowing normal reads and writes for most of the operation.

## Usage

Add the image to a Cluster. PostgreSQL 18 requires logical decoding for this
extension:

~~~yaml
postgresql:
  parameters:
    max_replication_slots: '1'
    output_plugin_libraries: pg_squeeze
    wal_level: logical
  shared_preload_libraries:
  - pg_squeeze
  extensions:
  - name: pg-squash
    image:
      # renovate: suite=trixie-pgdg depName=postgresql-18-squeeze
      reference: ghcr.io/cnpg-extensions/pg-squash:1.9.4-18-trixie
~~~

Enable the SQL extension in a Database:

~~~yaml
apiVersion: postgresql.cnpg.io/v1
kind: Database
metadata:
  name: cluster-pg-squash-app
spec:
  name: app
  owner: app
  cluster:
    name: cluster-pg-squash
  extensions:
  - name: pg_squeeze
    # renovate: suite=trixie-pgdg depName=postgresql-18-squeeze extractVersion=^(?<version>\d+\.\d+)
    version: '1.9'
~~~

The extension stores its configuration and logs in the squeeze schema. A
table can be registered for maintenance after it has an identity index:

~~~sql
CREATE EXTENSION pg_squeeze;
INSERT INTO squeeze.tables (tabschema, tabname, schedule)
VALUES ('public', 'my_table', ('{30}', '{22}', NULL, NULL, '{3, 5}'));
~~~

## Contributors

This extension is maintained by:

- Jeremy Schneider (@ardentperf)

## Licenses and Copyright

The package copyright and license notice are included in the image under
/licenses/postgresql-18-squeeze/.
