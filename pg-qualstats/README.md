# pg-qualstats
<!--
SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
SPDX-License-Identifier: Apache-2.0
-->

[pg_qualstats](https://github.com/powa-team/pg_qualstats) gathers statistics
about predicates found in WHERE and JOIN clauses. The statistics help
identify frequently used predicates and potentially missing indexes.

## Usage

Add the image to a Cluster and preload pg_qualstats:

~~~yaml
postgresql:
  shared_preload_libraries:
  - pg_qualstats
  extensions:
  - name: pg-qualstats
    image:
      # renovate: suite=trixie-pgdg depName=postgresql-18-pg-qualstats
      reference: ghcr.io/cnpg-extensions/pg-qualstats:2.1.4-18-trixie
~~~

Enable the SQL extension in a Database:

~~~yaml
apiVersion: postgresql.cnpg.io/v1
kind: Database
metadata:
  name: cluster-pg-qualstats-app
spec:
  name: app
  owner: app
  cluster:
    name: cluster-pg-qualstats
  extensions:
  - name: pg_qualstats
    # renovate: suite=trixie-pgdg depName=postgresql-18-pg-qualstats extractVersion=^(?<version>\d+\.\d+\.\d+)
    version: '2.1.4'
~~~

Inspect the gathered predicate statistics with:

~~~sql
CREATE EXTENSION pg_qualstats;
SELECT * FROM pg_qualstats;
~~~

## Contributors

This extension is maintained by:

- Jeremy Schneider (@ardentperf)

## Licenses and Copyright

The package copyright and license notice are included in the image under
/licenses/postgresql-18-pg-qualstats/.
