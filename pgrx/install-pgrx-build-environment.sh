#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
# SPDX-License-Identifier: Apache-2.0

set -Eeuo pipefail

pg_major=${1:?PostgreSQL major version is required}
lock_file=${2:?full path to Cargo.lock is required}
source_dir="$(dirname "${lock_file}")"
pg_config_dir="/usr/lib/postgresql/${pg_major}/bin"
pg_config="${pg_config_dir}/pg_config"
about_config=/pgrx/license-about.toml
sbom_dir="${source_dir}/pgrx-sbom"
license_dir="${source_dir}/pgrx-licenses/rust"
metadata_file=/tmp/cargo-metadata.json
cargo_bin_dir="${HOME}/.cargo/bin"

# These are the shared build/reporting inputs. The cargo-pgrx version is
# derived from Cargo.lock below.
# renovate: datasource=github-releases depName=rust-lang/rust versioning=semver
RUST_VERSION=1.97.1
# renovate: datasource=crate depName=cargo-cyclonedx versioning=semver
CARGO_CYCLONEDX_VERSION=0.5.9
# renovate: datasource=crate depName=cargo-about versioning=semver
CARGO_ABOUT_VERSION=0.9.2

manifest_file=${source_dir}/Cargo.toml

apt-get update
apt-get install -y --no-install-recommends \
    build-essential ca-certificates clang cmake curl git jq libclang-dev \
    libssl-dev pkg-config python3 postgresql-server-dev-${pg_major}
rm -rf /var/lib/apt/lists/*

test -x "${pg_config}"
ln -sf "${pg_config}" /usr/local/bin/pg_config
export PATH="${pg_config_dir}:${PATH}"

test -s "${lock_file}"
test -s "${manifest_file}"
test -s "${about_config}"
mkdir -p "${sbom_dir}" "${license_dir}"
find "${source_dir}" -maxdepth 2 -type f \( -iname 'LICENSE*' -o -iname 'COPYING*' \) \
    -exec cp -a {} "${license_dir}/" \; || true

curl --proto '=https' --tlsv1.2 --fail --silent --show-error https://sh.rustup.rs | \
    sh -s -- -y --profile minimal --default-toolchain "${RUST_VERSION}"
export PATH="${cargo_bin_dir}:${PATH}"
rustup component add rustfmt --toolchain "${RUST_VERSION}"
for rust_command in cargo rustc rustdoc rustfmt; do
    ln -sf "${cargo_bin_dir}/${rust_command}" "/usr/local/bin/${rust_command}"
done

cargo metadata --locked --format-version=1 --manifest-path "${manifest_file}" \
    --features "pg${pg_major}" --no-default-features \
    > "${metadata_file}"
pgrx_version="$(
    jq -er '
        [.packages[] | select(.name == "pgrx") | .version] | unique |
        if length == 1 then .[0] else error("expected exactly one pgrx version") end
    ' "${metadata_file}"
)"

cargo install --root /usr/local --locked --version "${pgrx_version}" cargo-pgrx
cargo install --root /usr/local --locked --version "${CARGO_CYCLONEDX_VERSION}" cargo-cyclonedx
cargo install --root /usr/local --locked --version "${CARGO_ABOUT_VERSION}" cargo-about --features cli

cargo pgrx init --pg${pg_major} "${pg_config}" --no-run
cargo metadata --locked --format-version=1 --manifest-path "${manifest_file}" \
    --features "pg${pg_major}" --no-default-features >/dev/null

pushd "${source_dir}" >/dev/null
cargo cyclonedx --manifest-path "${manifest_file}" --features "pg${pg_major}" \
    --no-default-features --format json --spec-version 1.5 --override-filename pgrx
cyclonedx_file="pgrx.json"
test -s "${cyclonedx_file}"
cp "${cyclonedx_file}" "${sbom_dir}/cyclonedx.json"
cargo about generate --config "${about_config}" --format json --locked --fail \
    --features "pg${pg_major}" --no-default-features --manifest-path "${manifest_file}" \
    > "${sbom_dir}/cargo-about.json"
python3 -c 'import json,re,sys; from pathlib import Path; r=json.loads(Path(sys.argv[1]).read_text()); o=Path(sys.argv[2]); [(o/("cargo-about-"+re.sub(r"[^A-Za-z0-9_.-]+","_",x.get("id") or x.get("name") or "unknown")+".txt")).write_text(x["text"].rstrip()+"\n") for x in r.get("licenses",[]) if x.get("text")]' \
    "${sbom_dir}/cargo-about.json" "${license_dir}"
popd >/dev/null
