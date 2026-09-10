# syntax=docker/dockerfile:1
# SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
# SPDX-License-Identifier: Apache-2.0

ARG BASE=ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
FROM $BASE AS builder

ARG PG_MAJOR
ARG EXT_VERSION

USER 0

RUN apt-get update && \
	apt-get install -y --no-install-recommends "postgresql-${PG_MAJOR}-plr=${EXT_VERSION}"

FROM scratch
ARG PG_MAJOR

# Licenses
COPY --parents --from=builder /usr/share/doc/./r-base-core/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libblas3/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libdeflate0/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libgomp1/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libtirpc3*/copyright /licenses/
COPY --from=builder /usr/share/doc/postgresql-${PG_MAJOR}-plr/copyright /licenses/postgresql-${PG_MAJOR}-plr/

# Libraries
COPY --from=builder /usr/lib/postgresql/${PG_MAJOR}/lib/plr.so /lib/
COPY --from=builder /usr/lib/postgresql/${PG_MAJOR}/lib/bitcode/ /lib/bitcode/

# System libs
COPY --from=builder /lib/libR.so /system/
COPY --from=builder /lib/*-linux-gnu/libblas.so.3 /system/
COPY --from=builder /lib/*-linux-gnu/libdeflate.so.0 /system/
COPY --from=builder /lib/*-linux-gnu/libgomp.so.1 /system/
COPY --from=builder /lib/*-linux-gnu/libtirpc.so.3 /system/

# Share
COPY --from=builder /usr/share/postgresql/${PG_MAJOR}/extension/plr* /share/extension/

USER 65532:65532
