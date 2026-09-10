# syntax=docker/dockerfile:1
# SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
# SPDX-License-Identifier: Apache-2.0

ARG BASE=ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
FROM $BASE AS builder

ARG PG_MAJOR
ARG EXT_VERSION

USER 0

RUN apt-get update && \
	apt-get install -y --no-install-recommends "postgresql-${PG_MAJOR}-h3=${EXT_VERSION}"

FROM scratch
ARG PG_MAJOR

# Licenses
COPY --parents --from=builder /usr/share/doc/./libh3-1/copyright /licenses/
COPY --from=builder /usr/share/doc/postgresql-${PG_MAJOR}-h3/copyright /licenses/postgresql-${PG_MAJOR}-h3/

# Libraries
COPY --from=builder /usr/lib/postgresql/${PG_MAJOR}/lib/h3.so /lib/
COPY --from=builder /usr/lib/postgresql/${PG_MAJOR}/lib/h3_postgis.so /lib/

# System libs
COPY --from=builder /lib/*-linux-gnu/libh3.so.1 /system/

# Share
COPY --from=builder /usr/share/postgresql/${PG_MAJOR}/extension/h3* /share/extension/

USER 65532:65532
