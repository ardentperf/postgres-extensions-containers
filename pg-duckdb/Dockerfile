# SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
# SPDX-License-Identifier: Apache-2.0

# pg_duckdb is a C++ extension. The release archive is the package input;
# prepare-build.sh recreates the release repository metadata and checks the
# DuckDB gitlink before the upstream Makefile is invoked.
ARG BASE=ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
FROM ${BASE} AS builder

ARG PG_MAJOR
ARG EXT_VERSION
ARG TARGETPLATFORM

USER 0
WORKDIR /build
ENV PATH=/usr/lib/postgresql/${PG_MAJOR}/bin:${PATH}

# renovate: datasource=github-tags depName=duckdb/pg_duckdb versioning=semver
ADD https://github.com/duckdb/pg_duckdb/archive/${EXT_VERSION}.tar.gz /tmp/source.tar.gz

COPY pg-duckdb/build/prepare-build.sh /pg-duckdb/build/

RUN /pg-duckdb/build/prepare-build.sh /build

# https://github.com/duckdb/pg_duckdb/blob/v1.1.1/docs/compilation.md#build-options
RUN DUCKDB_BUILD=ReleaseStatic make install

COPY pg-duckdb/build/collect_runtime_closure.sh pg-duckdb/build/collect_dependencies.py pg-duckdb/build/dependencies.json /pg-duckdb/build/

# Preserve build-system evidence for the target-local collector. The source
# roots are intentionally explicit so an unexpected root added by a release
# fails the collector rather than disappearing from the SBOM.
RUN python3 -c 'import json; json.dump({"schemaVersion": "https://github.com/cnpg-extensions/postgres-extensions-containers/pg-duckdb-build/v1", "dependencyRoots": ["src", "include", "third_party", "third_party/duckdb", "third_party/pg_duckdb_extensions.cmake"], "downloads": []}, open("/build/pg-duckdb-build-evidence.json", "w"), indent=2, sort_keys=True); open("/build/pg-duckdb-build-evidence.json", "a").write("\n")'

RUN /pg-duckdb/build/collect_runtime_closure.sh \
      "/usr/lib/postgresql/${PG_MAJOR}/lib/pg_duckdb.so" \
      /build/pg-duckdb-base-libs.txt \
      /build/pg-duckdb-runtime

RUN python3 /pg-duckdb/build/collect_dependencies.py \
      --source-root /build \
      --build-root /build \
      --recipe /pg-duckdb/build/dependencies.json \
      --output-dir /build/pg-duckdb-sbom \
      --platform "${TARGETPLATFORM:-linux/amd64}" \
      --pg-major "${PG_MAJOR}" \
      --source-tag "${EXT_VERSION}" \
      --runtime-evidence /build/pg-duckdb-runtime/runtime-libraries.json \
      --build-evidence /build/pg-duckdb-build-evidence.json \
      --build-inputs /build/pg-duckdb-build-inputs.json \
      --require-build-evidence

FROM scratch AS pg-duckdb-sbom
COPY --from=builder /build/pg-duckdb-sbom/ /pg-duckdb-sbom/

FROM scratch
ARG PG_MAJOR

# Complete source and runtime license evidence is intentionally kept beside
# the target-local manifest; compiler and source files remain in the builder.
COPY --from=builder /build/pg-duckdb-sbom/licenses/ /licenses/

# The static DuckDB bundle still uses OS shared libraries such as curl,
# libstdc++, libgcc, and their transitive closure. Only libraries absent from
# the pristine CNPG base are copied into this image.
COPY --from=builder /build/pg-duckdb-runtime/system/ /system/

COPY --from=builder /usr/lib/postgresql/${PG_MAJOR}/lib/pg_duckdb.so /lib/
COPY --from=builder /usr/share/postgresql/${PG_MAJOR}/extension/pg_duckdb* /share/extension/

USER 65532:65532
