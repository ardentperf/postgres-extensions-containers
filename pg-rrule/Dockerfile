# SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
# SPDX-License-Identifier: Apache-2.0

ARG BASE=ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
FROM $BASE AS builder

ARG PG_MAJOR
ARG EXT_VERSION

USER 0

COPY scripts/stage_system_libs.sh /usr/local/bin/stage_system_libs.sh

RUN set -eux && \
	ldconfig -p | awk '{print $NF}' | grep '^/' | sort | uniq > /tmp/base-image-libs.out && \
	apt-get update && \
	apt-get install -y --no-install-recommends "postgresql-${PG_MAJOR}-pg-rrule=${EXT_VERSION}"

RUN /usr/local/bin/stage_system_libs.sh /usr/lib/postgresql/${PG_MAJOR}/lib/pg_rrule.so

FROM scratch
ARG PG_MAJOR

# Licenses
COPY --from=builder /licenses /licenses/
COPY --from=builder /usr/share/doc/postgresql-${PG_MAJOR}-pg-rrule/copyright /licenses/postgresql-${PG_MAJOR}-pg-rrule/

# Libraries
COPY --from=builder /usr/lib/postgresql/${PG_MAJOR}/lib/pg_rrule.so /lib/
COPY --from=builder /usr/lib/postgresql/${PG_MAJOR}/lib/bitcode/ /lib/bitcode/

# System libs
COPY --from=builder /system /system/

# Share
COPY --from=builder /usr/share/postgresql/${PG_MAJOR}/extension/pg_rrule* /share/extension/

USER 65532:65532
