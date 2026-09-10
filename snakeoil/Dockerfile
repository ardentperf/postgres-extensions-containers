# syntax=docker/dockerfile:1
# SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
# SPDX-License-Identifier: Apache-2.0

ARG BASE=ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
FROM $BASE AS builder

ARG PG_MAJOR
ARG EXT_VERSION

USER 0

RUN apt-get update && \
	apt-get install -y --no-install-recommends "postgresql-${PG_MAJOR}-snakeoil=${EXT_VERSION}"

RUN mkdir -p /clamav && \
	printf '44d88612fea8a8f36de82e1278abb02f:68:Eicar-Test-Signature\n' > /clamav/stub.hdb

FROM scratch
ARG PG_MAJOR

# Licenses
COPY --parents --from=builder /usr/share/doc/./libclamav12/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libjson-c5/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libmspack0*/copyright /licenses/
COPY --from=builder /usr/share/doc/postgresql-${PG_MAJOR}-snakeoil/copyright /licenses/postgresql-${PG_MAJOR}-snakeoil/

# Libraries
COPY --from=builder /usr/lib/postgresql/${PG_MAJOR}/lib/pg_snakeoil.so /lib/
COPY --from=builder /usr/lib/postgresql/${PG_MAJOR}/lib/bitcode/ /lib/bitcode/

# System libs
COPY --from=builder /lib/*-linux-gnu/libclamav.so.12 /system/
COPY --from=builder /lib/*-linux-gnu/libjson-c.so.5 /system/
COPY --from=builder /lib/*-linux-gnu/libmspack.so.0 /system/

# ClamAV stub database (minimal signatures to satisfy libclamav at init)
COPY --from=builder /clamav/ /share/clamav/

# Share
COPY --from=builder /usr/share/postgresql/${PG_MAJOR}/extension/pg_snakeoil* /share/extension/

USER 65532:65532
