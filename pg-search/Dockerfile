# SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
# SPDX-License-Identifier: Apache-2.0

# pg_search is intentionally the final, compute-heavy pgrx target. It has
# additional OpenBLAS/libgfortran runtime closure beyond the other targets.
ARG BASE=ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
FROM ${BASE} AS builder
ARG PG_MAJOR
ARG EXTENSION=pg_search
ARG RUST_VERSION=1.97.1
ARG PGRX_VERSION=0.19.0
ARG CARGO_CYCLONEDX_VERSION=0.5.9
ARG CARGO_ABOUT_VERSION=0.9.2
ENV CARGO_HOME=/root/.cargo CARGO_TARGET_DIR=/build-target PGRX_HOME=/root/.pgrx PATH=/root/.cargo/bin:${PATH}
USER 0
RUN set -eux; \
    ldconfig -p | awk '{print $NF}' | grep '^/' | sort -u > /tmp/base-image-libs.out; \
    apt-get update; apt-get install -y --no-install-recommends \
      build-essential ca-certificates clang cmake curl git libclang-dev \
      libgfortran5 libopenblas-dev libssl-dev pkg-config python3 \
      postgresql-server-dev-${PG_MAJOR}; rm -rf /var/lib/apt/lists/*
RUN set -eux; curl --proto '=https' --tlsv1.2 --fail --silent --show-error https://sh.rustup.rs | \
      sh -s -- -y --profile minimal --default-toolchain "${RUST_VERSION}"; \
    rustup component add rustfmt; cargo install --locked --version "${PGRX_VERSION}" cargo-pgrx; \
    cargo install --locked --version "${CARGO_CYCLONEDX_VERSION}" cargo-cyclonedx; \
    cargo install --locked --version "${CARGO_ABOUT_VERSION}" cargo-about --features cli
COPY pgrx/license-about.toml /tmp/license-about.toml
WORKDIR /workspace/source
# renovate: datasource=github-tags depName=paradedb/paradedb versioning=semver
RUN curl --fail --location --silent --show-error "https://github.com/paradedb/paradedb/archive/d06d83ab82383c08e4a0104b0281391d81fba713.tar.gz" -o /tmp/source.tar.gz # v0.25.6
RUN set -eux; \
    printf '%s\n' 'https://github.com/paradedb/paradedb/archive/d06d83ab82383c08e4a0104b0281391d81fba713.tar.gz' > /tmp/source-url; \
    printf '%s\n' 'd06d83ab82383c08e4a0104b0281391d81fba713' > /tmp/source-commit; printf '%s\n' 'v0.25.6' > /tmp/source-tag; \
    sha256sum /tmp/source.tar.gz | awk '{print $1}' > /tmp/source-archive-sha256; \
    tar -xzf /tmp/source.tar.gz --strip-components=1 -C /workspace/source; test -s /workspace/source/Cargo.lock; \
    sha256sum /workspace/source/Cargo.lock | awk '{print $1}' > /tmp/cargo-lock-sha256
RUN set -eux; \
    cargo pgrx init --pg${PG_MAJOR} "/usr/lib/postgresql/${PG_MAJOR}/bin/pg_config" --no-run; \
    cargo metadata --locked --format-version=1 --manifest-path pg_search/Cargo.toml --features pg${PG_MAJOR} --no-default-features
RUN set -eux; \
    mkdir -p /tmp/pgrx-sbom; cargo cyclonedx --manifest-path pg_search/Cargo.toml --features pg${PG_MAJOR} \
      --no-default-features --format json --spec-version 1.5 --override-filename pgrx; \
    cyclonedx_file="pg_search/pgrx.json"; test -s "${cyclonedx_file}"; \
    cp "${cyclonedx_file}" /tmp/pgrx-sbom/cyclonedx.json; \
    cargo about generate --config /tmp/license-about.toml --format json --locked --fail --features pg${PG_MAJOR} \
      --no-default-features --manifest-path pg_search/Cargo.toml > /tmp/pgrx-sbom/cargo-about.json
RUN set -eux; \
    cargo pgrx package -p pg_search --profile release --features pg${PG_MAJOR} --no-default-features \
      --pg-config "/usr/lib/postgresql/${PG_MAJOR}/bin/pg_config" --out-dir /tmp/pgrx-package; \
    mkdir -p /payload/lib /payload/share/extension /payload/system /payload/licenses/rust /payload/licenses/system; \
    extension_library="$(find /tmp/pgrx-package -name "${EXTENSION}.so" -print -quit)"; test -s "${extension_library}"; cp -a "${extension_library}" /payload/lib/; \
    find /tmp/pgrx-package -type f \( -name "${EXTENSION}.control" -o -name "${EXTENSION}*.sql" \) -exec cp -a {} /payload/share/extension/ \;; \
    test -s "/payload/share/extension/${EXTENSION}.control"; \
    find /workspace/source -maxdepth 3 -type f \( -iname 'LICENSE*' -o -iname 'COPYING*' \) -exec cp -a {} /payload/licenses/rust/ \; || true
RUN set -eux; python3 -c 'import json,re; from pathlib import Path; r=json.loads(Path("/tmp/pgrx-sbom/cargo-about.json").read_text()); o=Path("/payload/licenses/rust"); [(o/("cargo-about-"+re.sub(r"[^A-Za-z0-9_.-]+","_",x.get("id") or x.get("name") or "unknown")+".txt")).write_text(x["text"].rstrip()+"\n") for x in r.get("licenses",[]) if x.get("text")]'
RUN set -eux; \
    : > /tmp/all-deps.out; \
    printf '%s\n' "/payload/lib/${EXTENSION}.so" > /tmp/dependency-queue.out; \
    while [ -s /tmp/dependency-queue.out ]; do \
      : > /tmp/dependency-next.out; \
      while read -r object; do \
        ldd "${object}" 2>/dev/null | awk '$1 ~ /^\// {print $1} $3 ~ /^\// {print $3}' > /tmp/object-deps.out; \
        while read -r lib; do \
          [ -n "${lib}" ] || continue; \
          if ! grep -Fqx "${lib}" /tmp/all-deps.out; then \
            printf '%s\n' "${lib}" >> /tmp/all-deps.out; \
            printf '%s\n' "${lib}" >> /tmp/dependency-next.out; \
          fi; \
        done < /tmp/object-deps.out; \
      done < /tmp/dependency-queue.out; \
      mv /tmp/dependency-next.out /tmp/dependency-queue.out; \
    done; \
    sort -u /tmp/all-deps.out -o /tmp/all-deps.out; \
    comm -13 /tmp/base-image-libs.out /tmp/all-deps.out > /tmp/libraries.out; \
    while read -r lib; do \
      [ -n "${lib}" ] || continue; \
      resolved="$(readlink -f "${lib}")"; \
      [ -f "${resolved}" ] || continue; \
      cp -a "${resolved}" /payload/system/; \
      dir="$(dirname "${lib}")"; base="$(basename "${lib}")"; \
      for alias in "${dir}"/"${base%.so*}.so"*; do \
        [ -L "${alias}" ] || continue; \
        [ "$(readlink -f "${alias}")" = "${resolved}" ] || continue; \
        ln -sf "$(basename "${resolved}")" "/payload/system/$(basename "${alias}")"; \
      done; \
    done < /tmp/libraries.out; \
    for lib in /payload/system/*.so*; do \
      [ -e "${lib}" ] || continue; \
      pkg="$(dpkg -S "$(basename "${lib}")" 2>/dev/null | awk -F: '!/diversion by/{print $1; exit}' || true)"; \
      [ -n "${pkg}" ] || continue; \
      if [ -f "/usr/share/doc/${pkg}/copyright" ]; then \
        mkdir -p "/payload/licenses/system/${pkg}"; \
        cp -a "/usr/share/doc/${pkg}/copyright" "/payload/licenses/system/${pkg}/"; \
      fi; \
    done
RUN set -eux; \
    archive_sha="$(cat /tmp/source-archive-sha256)"; lock_sha="$(cat /tmp/cargo-lock-sha256)"; report_sha="$(sha256sum /tmp/pgrx-sbom/cyclonedx.json | awk '{print $1}')"; about_sha="$(sha256sum /tmp/pgrx-sbom/cargo-about.json | awk '{print $1}')"; \
    cat > /tmp/pgrx-sbom/pgrx-build.json <<EOF
{"schemaVersion":"https://github.com/cnpg-extensions/postgres-extensions-containers/pgrx-build/v1","extension":"${EXTENSION}","source":{"archiveUrl":"$(cat /tmp/source-url)","commit":"$(cat /tmp/source-commit)","tag":"$(cat /tmp/source-tag)","archiveSha256":"${archive_sha}","cargoLockSha256":"${lock_sha}"},"cargo":{"package":"pg_search","manifestPath":"pg_search/Cargo.toml","features":["pg${PG_MAJOR}"],"noDefaultFeatures":true,"rustVersion":"${RUST_VERSION}","cargoPgrxVersion":"${PGRX_VERSION}","cargoCyclonedxVersion":"${CARGO_CYCLONEDX_VERSION}","cargoAboutVersion":"${CARGO_ABOUT_VERSION}"},"runtimeNotes":["libopenblas.so.0","libgfortran.so.5"],"reports":{"cyclonedxSha256":"${report_sha}","cargoAboutSha256":"${about_sha}"}}
EOF
FROM scratch AS pgrx-sbom
COPY --from=builder /tmp/pgrx-sbom/ /pgrx-sbom/
FROM scratch
COPY --from=builder /payload/ /
USER 65532:65532
