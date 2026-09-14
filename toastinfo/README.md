# toastinfo
<!--
SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
SPDX-License-Identifier: Apache-2.0
-->

[toastinfo](https://github.com/df7cb/toastinfo) describes how PostgreSQL
stores variable-length values, including inline, compressed, and out-of-line
TOAST values. It does not need to be preloaded.

## Usage

Add the image to a Cluster:

~~~yaml
postgresql:
  extensions:
  - name: toastinfo
    image:
      # renovate: suite=trixie-pgdg depName=postgresql-18-toastinfo
      reference: ghcr.io/cnpg-extensions/toastinfo:1.7-18-trixie
~~~

Enable the SQL extension in a Database:

~~~yaml
apiVersion: postgresql.cnpg.io/v1
kind: Database
metadata:
  name: cluster-toastinfo-app
spec:
  name: app
  owner: app
  cluster:
    name: cluster-toastinfo
  extensions:
  - name: toastinfo
    # toastinfo's SQL extension version is independent of its package version.
    # renovate: suite=trixie-pgdg depName=postgresql-18-toastinfo extractVersion=^(?<version>\d+)
    version: '1'
~~~

Use pg_toastinfo and pg_toastpointer to inspect a value:

~~~sql
CREATE EXTENSION toastinfo;
SELECT pg_toastinfo(value), pg_toastpointer(value) FROM my_table;
~~~

## Contributors

This extension is maintained by:

- Jeremy Schneider (@ardentperf)

## Licenses and Copyright

The package copyright and license notice are included in the image under
/licenses/postgresql-18-toastinfo/.
