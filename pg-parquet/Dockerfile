# SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
# SPDX-License-Identifier: Apache-2.0

# This Dockerfile is deliberately target-owned. Keep the source URL, package
# selection, and cargo commands visible when adapting it for another release.
# The cargo-pgrx version must match the pgrx crate version in the source tree.
ARG BASE=ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
FROM ${BASE} AS builder

ARG PG_MAJOR
ARG EXTENSION=pg_parquet
ARG RUST_VERSION=1.97.1
ARG PGRX_VERSION=0.16.0
ARG CARGO_CYCLONEDX_VERSION=0.5.9
ARG CARGO_ABOUT_VERSION=0.9.2

ENV CARGO_HOME=/root/.cargo \
    CARGO_TARGET_DIR=/build-target \
    PGRX_HOME=/root/.pgrx \
    PATH=/root/.cargo/bin:${PATH}

USER 0

# Customize this package list when the upstream extension adds native build
# dependencies. Only the runtime closure is copied into the scratch image.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      build-essential ca-certificates clang cmake curl git libclang-dev \
      libssl-dev pkg-config python3 postgresql-server-dev-${PG_MAJOR}; \
    rm -rf /var/lib/apt/lists/*

# Install Rust and the tools used by the exact Cargo graph. These versions are
# inputs to the build and are recorded in /pgrx-sbom/pgrx-build.json.
RUN set -eux; \
    curl --proto '=https' --tlsv1.2 --fail --silent --show-error https://sh.rustup.rs | \
      sh -s -- -y --profile minimal --default-toolchain "${RUST_VERSION}"; \
    rustup component add rustfmt; \
    cargo install --locked --version "${PGRX_VERSION}" cargo-pgrx; \
    cargo install --locked --version "${CARGO_CYCLONEDX_VERSION}" cargo-cyclonedx; \
    cargo install --locked --version "${CARGO_ABOUT_VERSION}" cargo-about --features cli

COPY pgrx/license-about.toml /tmp/license-about.toml
WORKDIR /workspace/source

# renovate: datasource=github-tags depName=CrunchyData/pg_parquet versioning=semver
RUN curl --fail --location --silent --show-error "https://github.com/CrunchyData/pg_parquet/archive/253bfa2228a0d5323180455cdc9ae9301db38be5.tar.gz" -o /tmp/source.tar.gz # v0.5.1

RUN set -eux; \
    printf '%s\n' 'https://github.com/CrunchyData/pg_parquet/archive/253bfa2228a0d5323180455cdc9ae9301db38be5.tar.gz' > /tmp/source-url; \
    printf '%s\n' '253bfa2228a0d5323180455cdc9ae9301db38be5' > /tmp/source-commit; \
    printf '%s\n' 'v0.5.1' > /tmp/source-tag; \
    sha256sum /tmp/source.tar.gz | awk '{print $1}' > /tmp/source-archive-sha256; \
    mkdir -p /workspace/source; \
    tar -xzf /tmp/source.tar.gz --strip-components=1 -C /workspace/source; \
    test -s Cargo.lock; \
    sha256sum Cargo.lock | awk '{print $1}' > /tmp/cargo-lock-sha256

# The locked metadata preflight is intentionally before packaging. The package
# subcommand does not expose --locked, so this is the lockfile guard.
RUN set -eux; \
    cargo pgrx init --pg${PG_MAJOR} "/usr/lib/postgresql/${PG_MAJOR}/bin/pg_config" --no-run; \
    cargo metadata --locked --format-version=1 --manifest-path Cargo.toml \
      --features pg${PG_MAJOR} --no-default-features

# Generate both raw Cargo reports from the same manifest and feature set used
# by cargo pgrx package. The report files are exported only by pgrx-sbom.
RUN set -eux; \
    mkdir -p /tmp/pgrx-sbom; \
    cargo cyclonedx --manifest-path Cargo.toml --features pg${PG_MAJOR} \
      --no-default-features --format json --spec-version 1.5 --override-filename pgrx; \
    cyclonedx_file="pgrx.json"; \
    test -s "${cyclonedx_file}"; \
    cp "${cyclonedx_file}" /tmp/pgrx-sbom/cyclonedx.json; \
    cargo about generate --config /tmp/license-about.toml --format json --locked --fail \
      --features pg${PG_MAJOR} --no-default-features --manifest-path Cargo.toml \
      > /tmp/pgrx-sbom/cargo-about.json

# Build and normalize the pgrx package into the stable runtime payload.
RUN set -eux; \
    cargo pgrx package --profile release --features pg${PG_MAJOR} \
      --no-default-features --pg-config "/usr/lib/postgresql/${PG_MAJOR}/bin/pg_config" \
      --out-dir /tmp/pgrx-package; \
    mkdir -p /payload/lib /payload/share/extension /payload/system \
      /payload/licenses/rust /payload/licenses/system; \
    extension_library="$(find /tmp/pgrx-package -name "${EXTENSION}.so" -print -quit)"; \
    test -s "${extension_library}"; \
    cp -a "${extension_library}" /payload/lib/; \
    find /tmp/pgrx-package -type f \( -name "${EXTENSION}.control" -o -name "${EXTENSION}*.sql" \) \
      -exec cp -a {} /payload/share/extension/ \;; \
    test -s "/payload/share/extension/${EXTENSION}.control"; \
    find /workspace/source -maxdepth 2 -type f \( -iname 'LICENSE*' -o -iname 'COPYING*' \) \
      -exec cp -a {} "/payload/licenses/rust/" \; || true

# Materialize complete license text from cargo-about. The SPDX merger uses the
# same records for package license evidence; raw reports stay out of runtime.
RUN set -eux; \
    python3 - <<'PY'
import json
import re
from pathlib import Path

report = json.loads(Path('/tmp/pgrx-sbom/cargo-about.json').read_text())
out = Path('/payload/licenses/rust')
for record in report.get('licenses', []):
    text = record.get('text')
    if not text:
        continue
    license_id = record.get('id') or record.get('name') or 'unknown'
    safe = re.sub(r'[^A-Za-z0-9_.-]+', '_', license_id)
    (out / f'cargo-about-{safe}.txt').write_text(text.rstrip() + '\n')
PY

# Capture the runtime linker closure not supplied by the PostgreSQL base image,
# preserving symlink aliases and the Debian copyright text for each library.
RUN set -eux; \
    ldconfig -p | awk '{print $NF}' | grep '^/' | sort -u > /tmp/base-image-libs.out; \
    ldd "/payload/lib/${EXTENSION}.so" | awk '$3 ~ /^\// {print $3}' | sort -u > /tmp/all-deps.out; \
    comm -13 /tmp/base-image-libs.out /tmp/all-deps.out > /tmp/libraries.out; \
    while read -r lib; do \
      [ -n "$lib" ] || continue; \
      resolved="$(readlink -f "$lib")"; \
      [ -f "$resolved" ] || continue; \
      cp -a "$resolved" /payload/system/; \
      dir="$(dirname "$lib")"; base="$(basename "$lib")"; \
      for alias in "$dir"/"${base%.so*}.so"*; do \
        [ -L "$alias" ] || continue; \
        [ "$(readlink -f "$alias")" = "$resolved" ] || continue; \
        ln -sf "$(basename "$resolved")" "/payload/system/$(basename "$alias")"; \
      done; \
    done < /tmp/libraries.out; \
    for lib in /payload/system/*.so*; do \
      [ -e "$lib" ] || continue; \
      pkg="$(dpkg -S "$(basename "$lib")" 2>/dev/null | awk -F: '!/diversion by/{print $1; exit}' || true)"; \
      [ -n "$pkg" ] || continue; \
      if [ -f "/usr/share/doc/${pkg}/copyright" ]; then \
        mkdir -p "/payload/licenses/system/${pkg}"; \
        cp -a "/usr/share/doc/${pkg}/copyright" "/payload/licenses/system/${pkg}/"; \
      fi; \
    done

# This compact manifest is consumed by pgrx/compose_pgrx_sbom.py and records
# build evidence without becoming a second source-of-truth release manifest.
RUN set -eux; \
    archive_sha="$(cat /tmp/source-archive-sha256)"; \
    lock_sha="$(cat /tmp/cargo-lock-sha256)"; \
    report_sha="$(sha256sum /tmp/pgrx-sbom/cyclonedx.json | awk '{print $1}')"; \
    about_sha="$(sha256sum /tmp/pgrx-sbom/cargo-about.json | awk '{print $1}')"; \
    cat > /tmp/pgrx-sbom/pgrx-build.json <<EOF
{
  "schemaVersion": "https://github.com/cnpg-extensions/postgres-extensions-containers/pgrx-build/v1",
  "extension": "${EXTENSION}",
  "source": {
    "archiveUrl": "$(cat /tmp/source-url)",
    "commit": "$(cat /tmp/source-commit)",
    "tag": "$(cat /tmp/source-tag)",
    "archiveSha256": "${archive_sha}",
    "cargoLockSha256": "${lock_sha}"
  },
  "cargo": {
    "package": "pg_parquet",
    "manifestPath": "Cargo.toml",
    "features": ["pg${PG_MAJOR}"],
    "noDefaultFeatures": true,
    "rustVersion": "${RUST_VERSION}",
    "cargoPgrxVersion": "${PGRX_VERSION}",
    "cargoCyclonedxVersion": "${CARGO_CYCLONEDX_VERSION}",
    "cargoAboutVersion": "${CARGO_ABOUT_VERSION}"
  },
  "reports": {
    "cyclonedxSha256": "${report_sha}",
    "cargoAboutSha256": "${about_sha}"
  }
}
EOF

FROM scratch AS pgrx-sbom
COPY --from=builder /tmp/pgrx-sbom/ /pgrx-sbom/

FROM scratch
# Only the normalized extension payload, runtime closure, and license evidence
# enter the runtime image. Compiler, source, Cargo registry, and reports stay
# in intermediate stages (reports are exported through pgrx-sbom instead).
COPY --from=builder /payload/ /
USER 65532:65532
