# SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
# SPDX-License-Identifier: Apache-2.0

ARG BASE=ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
FROM $BASE AS builder

ARG PG_MAJOR
ARG EXT_VERSION

USER 0

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      "postgresql-${PG_MAJOR}-pgsentinel=${EXT_VERSION}"

FROM scratch
ARG PG_MAJOR

# Licenses
COPY --from=builder /usr/share/doc/postgresql-${PG_MAJOR}-pgsentinel/copyright /licenses/postgresql-${PG_MAJOR}-pgsentinel/
COPY --from=builder /usr/share/doc/postgresql-${PG_MAJOR}/copyright /licenses/postgresql-${PG_MAJOR}/

# Libraries
COPY --from=builder /usr/lib/postgresql/${PG_MAJOR}/lib/pgsentinel* /lib/
COPY --from=builder /usr/lib/postgresql/${PG_MAJOR}/lib/pg_stat_statements* /lib/
COPY --from=builder /usr/lib/postgresql/${PG_MAJOR}/lib/bitcode/ /lib/bitcode/

# Share
COPY --from=builder /usr/share/postgresql/${PG_MAJOR}/extension/pgsentinel* /share/extension/
COPY --from=builder /usr/share/postgresql/${PG_MAJOR}/extension/pg_stat_statements* /share/extension/

USER 65532:65532
