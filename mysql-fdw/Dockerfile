# syntax=docker/dockerfile:1
# SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
# SPDX-License-Identifier: Apache-2.0

ARG BASE=ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
FROM $BASE AS builder

ARG PG_MAJOR
ARG EXT_VERSION

USER 0

RUN apt-get update && \
	apt-get install -y --no-install-recommends "postgresql-${PG_MAJOR}-mysql-fdw=${EXT_VERSION}"

FROM scratch
ARG PG_MAJOR

# Licenses
COPY --parents --from=builder /usr/share/doc/./libmariadb3/copyright /licenses/
COPY --from=builder /usr/share/doc/postgresql-${PG_MAJOR}-mysql-fdw/copyright /licenses/postgresql-${PG_MAJOR}-mysql-fdw/

# Libraries
COPY --from=builder /usr/lib/postgresql/${PG_MAJOR}/lib/mysql_fdw.so /lib/
COPY --from=builder /usr/lib/postgresql/${PG_MAJOR}/lib/bitcode/ /lib/bitcode/

# System libs (includes the dlopen-loaded MariaDB client and MySQL alias)
COPY --from=builder /lib/*-linux-gnu/libmariadb.so.3 /system/
COPY --from=builder /lib/*-linux-gnu/libmysqlclient.so /system/

# Share
COPY --from=builder /usr/share/postgresql/${PG_MAJOR}/extension/mysql_fdw* /share/extension/

USER 65532:65532
