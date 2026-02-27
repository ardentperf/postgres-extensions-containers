# SPDX-FileCopyrightText: Copyright © contributors to CloudNativePG, established as CloudNativePG a Series of LF Projects, LLC.
# SPDX-License-Identifier: Apache-2.0

ARG BASE=ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
FROM $BASE AS builder

ARG PG_MAJOR
ARG EXT_VERSION

USER 0

# Install extension via `apt-get`
RUN apt-get update && apt-get install -y --no-install-recommends \
      "postgresql-${PG_MAJOR}-hll=${EXT_VERSION}"

FROM scratch
ARG PG_MAJOR

# Licenses
COPY --from=builder /usr/share/doc/postgresql-${PG_MAJOR}-hll/copyright /licenses/postgresql-${PG_MAJOR}-hll/

# Libraries
COPY --from=builder /usr/lib/postgresql/${PG_MAJOR}/lib/hll* /lib/
COPY --from=builder /usr/lib/postgresql/${PG_MAJOR}/lib/bitcode/ /lib/bitcode/

# Share
COPY --from=builder /usr/share/postgresql/${PG_MAJOR}/extension/hll* /share/extension/

USER 65532:65532
