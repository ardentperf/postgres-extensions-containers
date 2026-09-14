# SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
# SPDX-License-Identifier: Apache-2.0

ARG BASE=ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
FROM ${BASE} AS builder

ARG PG_MAJOR
ARG EXT_VERSION

USER 0

WORKDIR /build
ADD https://github.com/paradedb/paradedb/archive/${EXT_VERSION}.tar.gz /tmp/source.tar.gz
RUN tar -xzf /tmp/source.tar.gz --strip-components=1 -C /build

# ParadeDB's release workflow installs OpenBLAS before packaging pg_search:
# https://github.com/paradedb/paradedb/blob/v0.25.6/.github/workflows/publish-pg_search-debian.yml#L256-L260
RUN apt-get update && \
    apt-get install -y --no-install-recommends libopenblas-dev

COPY pgrx/ /pgrx/
# cargo-cyclonedx writes the workspace report beside the pg_search manifest;
# the shared installer reads the report from the workspace root.
RUN ln -s pg_search/pgrx.json /build/pgrx.json
RUN /pgrx/install-pgrx-build-environment.sh "${PG_MAJOR}" /build/Cargo.lock

# ParadeDB packages from the pg_search workspace directory:
# https://github.com/paradedb/paradedb/blob/v0.25.6/.github/workflows/publish-pg_search-debian.yml#L289-L294
RUN cd pg_search && cargo pgrx package

FROM scratch AS pgrx-sbom
# Do not remove this line; the installer generates the SBOM material automatically.
COPY --from=builder /build/pgrx-sbom/ /pgrx-sbom/

FROM scratch
ARG PG_MAJOR

# Licenses
COPY --from=builder /build/pgrx-licenses/rust/ /licenses/rust/
COPY --from=builder /usr/share/doc/libopenblas0-pthread/copyright /licenses/system/libopenblas0-pthread/
COPY --from=builder /usr/share/doc/libgfortran5/copyright /licenses/system/libgfortran5/

# Libraries
COPY --from=builder /build/target/release/pg_search-pg${PG_MAJOR}/usr/lib/postgresql/${PG_MAJOR}/lib/pg_search.so /lib/
COPY --from=builder /usr/lib/*/libopenblas.so.0 /system/
COPY --from=builder /usr/lib/*/libgfortran.so.5 /system/

# Share
COPY --from=builder /build/target/release/pg_search-pg${PG_MAJOR}/usr/share/postgresql/${PG_MAJOR}/extension/pg_search* /share/extension/

USER 65532:65532
