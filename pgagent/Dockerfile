# syntax=docker/dockerfile:1
# SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
# SPDX-License-Identifier: Apache-2.0

ARG BASE=ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
FROM $BASE AS builder

ARG PG_MAJOR
ARG EXT_VERSION

USER 0

RUN apt-get update && \
	apt-get install -y --no-install-recommends "pgagent=${EXT_VERSION}"

FROM scratch
ARG PG_MAJOR

# Licenses
COPY --parents --from=builder /usr/share/doc/./libboost-filesystem1.*/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libboost-thread1.*/copyright /licenses/
COPY --from=builder /usr/share/doc/pgagent/copyright /licenses/pgagent/

# Binary
COPY --from=builder /usr/bin/pgagent /bin/

# System libs
COPY --from=builder /lib/*-linux-gnu/libboost_filesystem.so.* /system/
COPY --from=builder /lib/*-linux-gnu/libboost_thread.so.* /system/

# Share
COPY --from=builder /usr/share/postgresql/${PG_MAJOR}/extension/pgagent* /share/extension/

USER 65532:65532
