# pgrx feasibility spike findings

This document records the local feasibility run for the five initial pgrx
targets. It is an implementation input, not an implementation change. The
run used disposable source checkouts and a disposable Docker container; the
pgrx implementation plan and existing Debian build infrastructure were not
modified.

The run was performed on 2026-09-07 UTC against the release tags and commits
below. Each source checkout contained a root `Cargo.lock`.

| Target | Upstream repository | Release tag | Commit | Cargo package | pgrx version |
| --- | --- | --- | --- | --- | --- |
| `pg-search` | `paradedb/paradedb` | `v0.25.6` | `d06d83ab8233c08e4a0104b0281391d81fba713` | workspace package `pg_search` under `pg_search/` | `0.19.0` |
| `pg-parquet` | `CrunchyData/pg_parquet` | `v0.5.1` | `253bfa2228a0d5323180455cdc9ae9301db38be5` | root package `pg_parquet` | `0.16.0` |
| `pg-graphql` | `supabase/pg_graphql` | `v1.6.2` | `f46687dae404b6e65149f74c6d5a76e8a2f7aef5` | root package `pg_graphql` | `0.19.2` |
| `pg-jsonschema` | `supabase/pg_jsonschema` | `v0.3.4` | `cbe74b570d38aa0c4d42914e7a118bcb3adaee7a` | root package `pg_jsonschema` | `0.16.1` |
| `pg-session-jwt` | `neondatabase/pg_session_jwt` | `v0.5.0` | `937a79a65e596d916295d078b3a82ab421291665` | root package `pg_session_jwt` | `0.16.1` |

## Results

All five extensions successfully ran `cargo pgrx package` for PostgreSQL
18, after a successful `cargo metadata --locked` preflight, using the `pg18`
feature and the matching `cargo-pgrx` version. The tested cargo-pgrx package
subcommands do not expose a `--locked` option themselves, so the locked
preflight is important when enforcing the source lockfile.

| Target | Build result | Shared object | SQL entities discovered | CycloneDX components / dependencies | cargo-about crates / license records |
| --- | --- | ---: | ---: | ---: | ---: |
| `pg_search` | Pass | 159,138,160 bytes | 751 | 504 / 505 | 591 / 141 |
| `pg_parquet` | Pass | 30,251,808 bytes | 11 | 342 / 343 | 448 / 144 |
| `pg_graphql` | Pass | 2,283,712 bytes | 5 | 139 / 140 | 269 / 55 |
| `pg_jsonschema` | Pass | 5,095,768 bytes | 4 | 146 / 147 | 268 / 61 |
| `pg_session_jwt` | Pass | 1,250,520 bytes | 9 | 138 / 139 | 284 / 59 |

The pgrx package outputs contained the expected control file, shared library,
generated versioned SQL file, and, where applicable, upgrade SQL files.

The `pg_search` release build was much more expensive than the others: the
optimized Rust compilation took 34m38s in the four-CPU feasibility container.
The other optimized builds took approximately 1m50s–8m13s. Some pgrx package
commands also rebuild the embed helper in debug mode to generate SQL.

## Reproduction environment

The successful run used:

- Docker image `rust:1.97-slim-trixie`
- Rust/Cargo `1.97.1`
- PostgreSQL `18.6` from the PostgreSQL apt repository
- `cargo-pgrx` versions `0.16.0`, `0.16.1`, `0.19.0`, and `0.19.2`
- `cargo-about` `0.9.2`
- `cargo-cyclonedx` `0.5.9`
- a disk-backed internal container target directory, not a target directory
  on the host bind mount

The container had PostgreSQL development and native build dependencies
installed, including `build-essential`, `clang`, `libclang-dev`, `pkg-config`,
`libssl-dev`, `cmake`, `libopenblas-dev`, `git`, `curl`, and `gnupg`, as well
as `postgresql-client-18`, `postgresql-server-dev-18`, and `libpq-dev`.

The following is a representative setup from a clean host. The exact apt
mirror metadata can change, but the important properties are the Rust 1.97.1
toolchain, PostgreSQL 18 `pg_config`, and the listed tool versions.

```bash
FEAS_ROOT="$(mktemp -d /tmp/pgrx-feasibility.XXXXXX)"

git clone --depth 1 --branch v0.25.6 \
  https://github.com/paradedb/paradedb.git "$FEAS_ROOT/pg-search"
git clone --depth 1 --branch v0.5.1 \
  https://github.com/CrunchyData/pg_parquet.git "$FEAS_ROOT/pg-parquet"
git clone --depth 1 --branch v1.6.2 \
  https://github.com/supabase/pg_graphql.git "$FEAS_ROOT/pg-graphql"
git clone --depth 1 --branch v0.3.4 \
  https://github.com/supabase/pg_jsonschema.git "$FEAS_ROOT/pg-jsonschema"
git clone --depth 1 --branch v0.5.0 \
  https://github.com/neondatabase/pg_session_jwt.git "$FEAS_ROOT/pg-session-jwt"

# Pin the checkout to the exact commits recorded in this document, even if a
# release tag is later moved upstream.
git -C "$FEAS_ROOT/pg-search" checkout --detach d06d83ab8233c08e4a0104b0281391d81fba713
git -C "$FEAS_ROOT/pg-parquet" checkout --detach 253bfa2228a0d5323180455cdc9ae9301db38be5
git -C "$FEAS_ROOT/pg-graphql" checkout --detach f46687dae404b6e65149f74c6d5a76e8a2f7aef5
git -C "$FEAS_ROOT/pg-jsonschema" checkout --detach cbe74b570d38aa0c4d42914e7a118bcb3adaee7a
git -C "$FEAS_ROOT/pg-session-jwt" checkout --detach 937a79a65e596d916295d078b3a82ab421291665

for target in pg-search pg-parquet pg-graphql pg-jsonschema pg-session-jwt; do
  test -f "$FEAS_ROOT/$target/Cargo.lock"
done

docker run --detach --name pgrx-feasibility \
  --volume "$FEAS_ROOT:/workspace" \
  rust:1.97-slim-trixie sleep infinity

docker exec pgrx-feasibility bash -lc '
  apt-get update
  apt-get install --yes ca-certificates curl gnupg
  install -d /usr/share/postgresql-common/pgdg
  curl --fail --location \
    --output /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    https://www.postgresql.org/media/keys/ACCC4CF8.asc
  echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt trixie-pgdg main" \
    > /etc/apt/sources.list.d/pgdg.list
  apt-get update
  apt-get install --yes \
    build-essential clang libclang-dev pkg-config libssl-dev cmake \
    libopenblas-dev git curl gnupg \
    postgresql-client-18 postgresql-server-dev-18 libpq-dev
  mkdir --parents /build-target /workspace/results
'
```

Install the exact Cargo tools into separate roots so multiple pgrx versions
can coexist:

```bash
docker exec pgrx-feasibility bash -lc '
  export PATH=/usr/local/cargo/bin:/usr/local/rustup/toolchains/1.97.1-x86_64-unknown-linux-gnu/bin:$PATH

  cargo install --locked --version 0.16.0 cargo-pgrx \
    --root /home/builder/tools/pgrx-0.16.0
  cargo install --locked --version 0.16.1 cargo-pgrx \
    --root /home/builder/tools/pgrx-0.16.1
  cargo install --locked --version 0.19.0 cargo-pgrx \
    --root /home/builder/tools/pgrx-0.19.0
  cargo install --locked --version 0.19.2 cargo-pgrx \
    --root /home/builder/tools/pgrx-0.19.2

  cargo install --locked --version 0.9.2 cargo-about \
    --features cli --root /home/builder/tools/cargo-about-0.9.2
  cargo install --locked --version 0.5.9 cargo-cyclonedx \
    --root /home/builder/tools/cargo-cyclonedx-0.5.9
'

docker exec pgrx-feasibility bash -lc '
  export PATH=/usr/local/cargo/bin:/usr/local/rustup/toolchains/1.97.1-x86_64-unknown-linux-gnu/bin:/home/builder/tools/pgrx-0.16.1/bin:$PATH
  export PGRX_HOME=/home/builder/.pgrx
  cargo pgrx init --pg18 /usr/lib/postgresql/18/bin/pg_config --no-run
'
```

If the source checkout is bind-mounted with a host path that has limited
space, set `CARGO_TARGET_DIR` to a container-internal path for every build.
The first feasibility attempt placed a large Rust target directory on the
host temporary filesystem and ran out of space; moving it to
`/build-target/<target>` resolved that problem.

## Reproducing the five builds

Each command must use the `cargo-pgrx` version shown in the target table. The
commands below use the same PG18 configuration and write package contents to
`/workspace/results/<target>`.

### pg_search

```bash
docker exec pgrx-feasibility bash -lc '
  export PATH=/usr/local/cargo/bin:/usr/local/rustup/toolchains/1.97.1-x86_64-unknown-linux-gnu/bin:/home/builder/tools/pgrx-0.19.0/bin:$PATH
  export PGRX_HOME=/home/builder/.pgrx
  export CARGO_TARGET_DIR=/build-target/pg-search
  cd /workspace/pg-search
  mkdir --parents /workspace/results/pg-search
  cargo metadata --locked --format-version 1 \
    --features pg18 --no-default-features \
    --manifest-path pg_search/Cargo.toml >/dev/null
  cargo pgrx package -p pg_search \
    --profile release \
    --features pg18 --no-default-features \
    --pg-config /usr/lib/postgresql/18/bin/pg_config \
    --out-dir /workspace/results/pg-search
'
```

### pg_parquet

```bash
docker exec pgrx-feasibility bash -lc '
  export PATH=/usr/local/cargo/bin:/usr/local/rustup/toolchains/1.97.1-x86_64-unknown-linux-gnu/bin:/home/builder/tools/pgrx-0.16.0/bin:$PATH
  export PGRX_HOME=/home/builder/.pgrx
  export CARGO_TARGET_DIR=/build-target/pg-parquet
  cd /workspace/pg-parquet
  mkdir --parents /workspace/results/pg-parquet
  cargo metadata --locked --format-version 1 \
    --features pg18 --no-default-features \
    --manifest-path Cargo.toml >/dev/null
  cargo pgrx package \
    --profile release \
    --features pg18 --no-default-features \
    --pg-config /usr/lib/postgresql/18/bin/pg_config \
    --out-dir /workspace/results/pg-parquet
'
```

### pg_graphql

```bash
docker exec pgrx-feasibility bash -lc '
  export PATH=/usr/local/cargo/bin:/usr/local/rustup/toolchains/1.97.1-x86_64-unknown-linux-gnu/bin:/home/builder/tools/pgrx-0.19.2/bin:$PATH
  export PGRX_HOME=/home/builder/.pgrx
  export CARGO_TARGET_DIR=/build-target/pg-graphql
  cd /workspace/pg-graphql
  mkdir --parents /workspace/results/pg-graphql
  cargo metadata --locked --format-version 1 \
    --features pg18 --no-default-features \
    --manifest-path Cargo.toml >/dev/null
  cargo pgrx package \
    --profile release \
    --features pg18 --no-default-features \
    --pg-config /usr/lib/postgresql/18/bin/pg_config \
    --out-dir /workspace/results/pg-graphql
'
```

### pg_jsonschema

```bash
docker exec pgrx-feasibility bash -lc '
  export PATH=/usr/local/cargo/bin:/usr/local/rustup/toolchains/1.97.1-x86_64-unknown-linux-gnu/bin:/home/builder/tools/pgrx-0.16.1/bin:$PATH
  export PGRX_HOME=/home/builder/.pgrx
  export CARGO_TARGET_DIR=/build-target/pg-jsonschema
  cd /workspace/pg-jsonschema
  mkdir --parents /workspace/results/pg-jsonschema
  cargo metadata --locked --format-version 1 \
    --features pg18 --no-default-features \
    --manifest-path Cargo.toml >/dev/null
  cargo pgrx package \
    --profile release \
    --features pg18 --no-default-features \
    --pg-config /usr/lib/postgresql/18/bin/pg_config \
    --out-dir /workspace/results/pg-jsonschema
'
```

### pg_session_jwt

```bash
docker exec pgrx-feasibility bash -lc '
  export PATH=/usr/local/cargo/bin:/usr/local/rustup/toolchains/1.97.1-x86_64-unknown-linux-gnu/bin:/home/builder/tools/pgrx-0.16.1/bin:$PATH
  export PGRX_HOME=/home/builder/.pgrx
  export CARGO_TARGET_DIR=/build-target/pg-session-jwt
  cd /workspace/pg-session-jwt
  mkdir --parents /workspace/results/pg-session-jwt
  cargo metadata --locked --format-version 1 \
    --features pg18 --no-default-features \
    --manifest-path Cargo.toml >/dev/null
  cargo pgrx package \
    --profile release \
    --features pg18 --no-default-features \
    --pg-config /usr/lib/postgresql/18/bin/pg_config \
    --out-dir /workspace/results/pg-session-jwt
'
```

Because the package subcommand itself cannot receive `--locked`, verify that
the build did not alter any source lockfile afterward:

```bash
for target in pg-search pg-parquet pg-graphql pg-jsonschema pg-session-jwt; do
  git -C "$FEAS_ROOT/$target" \
    diff --exit-code -- Cargo.lock
done
```

This assumes the `FEAS_ROOT` shell variable from the setup section is still
set. For a fully offline package invocation, run
`cargo fetch --locked` after the metadata preflight and set
`CARGO_NET_OFFLINE=true` before invoking cargo-pgrx; the feasibility run used
the network-enabled default after confirming the locked metadata.

Verify the package outputs with:

```bash
docker exec pgrx-feasibility bash -lc '
  find /workspace/results -path "*/usr/lib/postgresql/18/lib/*.so" \
    -o -path "*/usr/share/postgresql/18/extension/*.control" \
    -o -path "*/usr/share/postgresql/18/extension/*.sql" \
    | sort
'
```

## CycloneDX reproduction

The command-line tool is `cargo cyclonedx`, installed from
`cargo-cyclonedx` version 0.5.9. It was run against the exact locked source
tree and feature selection used by the build.

For the four root-package repositories:

```bash
docker exec pgrx-feasibility bash -lc '
  export PATH=/usr/local/cargo/bin:/usr/local/rustup/toolchains/1.97.1-x86_64-unknown-linux-gnu/bin:/home/builder/tools/cargo-cyclonedx-0.5.9/bin:$PATH
  for target in pg-parquet pg-graphql pg-jsonschema pg-session-jwt; do
    cd /workspace/$target
    cargo cyclonedx \
      --manifest-path Cargo.toml \
      --features pg18 --no-default-features \
      --format json --spec-version 1.5 \
      --override-filename "$target"
  done
'
```

For the `pg_search` workspace package:

```bash
docker exec pgrx-feasibility bash -lc '
  export PATH=/usr/local/cargo/bin:/usr/local/rustup/toolchains/1.97.1-x86_64-unknown-linux-gnu/bin:/home/builder/tools/cargo-cyclonedx-0.5.9/bin:$PATH
  cd /workspace/pg-search
  cargo cyclonedx \
    --manifest-path pg_search/Cargo.toml \
    --features pg18 --no-default-features \
    --format json --spec-version 1.5 \
    --override-filename pg_search
'
```

The generated files are:

```text
/workspace/pg-search/pg_search/pg_search.json
/workspace/pg-parquet/pg-parquet.json
/workspace/pg-graphql/pg-graphql.json
/workspace/pg-jsonschema/pg-jsonschema.json
/workspace/pg-session-jwt/pg-session-jwt.json
```

`--override-filename` is a filename prefix, not a destination path. Passing
an absolute path to that option produced `Invalid filename: Illegal
characters in custom prefix string: /`; using a basename produced the
successful outputs above.

The raw outputs all declared CycloneDX 1.5, had no component missing a
version, and had no component missing a license entry. The `pg_search` report
also retained versioned VCS PURLs for its Git dependencies. For example,
`datafusion-distributed` was represented as version `3.0.0` with a GitHub
commit in its `vcs_url` PURL.

## cargo-about reproduction

`cargo-about` needs two kinds of configuration for this source set:

1. An explicit accepted-license policy. The generated default config only
   accepted Apache-2.0 and MIT, which was not enough for the dependency
   graphs.
2. Per-package clarifications for source repositories that do not expose a
   Cargo `license` field. The clarifications below are temporary feasibility
   configuration and do not constitute the project's eventual licensing
   policy.

Create `/workspace/about-feasibility.toml` with this content:

```toml
accepted = [
    "Apache-2.0",
    "MIT",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "CC0-1.0",
    "ISC",
    "MIT-0",
    "OpenSSL",
    "Unlicense",
    "Unicode-3.0",
    "Zlib",
    "BSL-1.0",
    "AGPL-3.0",
    "CDLA-Permissive-2.0",
    "0BSD",
    "MPL-2.0",
    "zlib-acknowledgement",
    "PostgreSQL",
]

[pg_parquet.clarify]
license = "PostgreSQL"

[[pg_parquet.clarify.files]]
path = "LICENSE"
license = "PostgreSQL"
checksum = "5af2fa8f8bab50d2222a62543b450775187fc095dce36cb44f3a1af4663ab68e"

[pg_graphql.clarify]
license = "Apache-2.0"

[[pg_graphql.clarify.files]]
path = "LICENSE"
license = "Apache-2.0"
checksum = "9b78bbb5a12f0e1928691f09604c788f8b8b4db59cdb82f9924679cf9beae5d2"

[pg_jsonschema.clarify]
license = "Apache-2.0"

[[pg_jsonschema.clarify.files]]
path = "LICENSE"
license = "Apache-2.0"
checksum = "31088ca1e26bfe86295635d34e82c82cf4ce180646441ddc8f947bc70b94495b"

[pg_session_jwt.clarify]
license = "Apache-2.0"

[[pg_session_jwt.clarify.files]]
path = "LICENSE"
license = "Apache-2.0"
checksum = "58d1e17ffe5109a7ae296caafcadfdbe6a7d176f0bc4ab01e12a689b0499d8bd"
```

Run the strict report for each target. The first online run may take several
minutes because cargo-about retrieves and materializes license evidence for
many crates. Once the Cargo cache is populated, `--offline` was sufficient
for the strict validation run.

```bash
docker exec pgrx-feasibility bash -lc '
  export PATH=/usr/local/cargo/bin:/usr/local/rustup/toolchains/1.97.1-x86_64-unknown-linux-gnu/bin:/home/builder/tools/cargo-about-0.9.2/bin:$PATH

  cd /workspace/pg-search
  cargo about generate \
    --config /workspace/about-feasibility.toml \
    --format json --locked --fail \
    --features pg18 --no-default-features \
    --manifest-path pg_search/Cargo.toml \
    > /workspace/results/pg-search/pg-search-about-strict.json

  cd /workspace/pg-parquet
  cargo about generate \
    --config /workspace/about-feasibility.toml \
    --format json --locked --fail \
    --features pg18 --no-default-features \
    --manifest-path Cargo.toml \
    > /workspace/results/pg-parquet/pg-parquet-about-strict.json

  cd /workspace/pg-graphql
  cargo about generate \
    --config /workspace/about-feasibility.toml \
    --format json --locked --fail \
    --features pg18 --no-default-features \
    --manifest-path Cargo.toml \
    > /workspace/results/pg-graphql/pg-graphql-about-strict.json

  cd /workspace/pg-jsonschema
  cargo about generate \
    --config /workspace/about-feasibility.toml \
    --format json --locked --fail \
    --features pg18 --no-default-features \
    --manifest-path Cargo.toml \
    > /workspace/results/pg-jsonschema/pg-jsonschema-about-strict.json

  cd /workspace/pg-session-jwt
  cargo about generate \
    --config /workspace/about-feasibility.toml \
    --format json --locked --fail \
    --features pg18 --no-default-features \
    --manifest-path Cargo.toml \
    > /workspace/results/pg-session-jwt/pg-session-jwt-about-strict.json
'
```

The strict reports contained no unknown-license crates and every deduplicated
license record contained non-empty license text. The report counts were:

| Target | cargo-about crates | License records with text | Root license after clarification |
| --- | ---: | ---: | --- |
| `pg_search` | 591 | 141 | `AGPL-3.0` |
| `pg_parquet` | 448 | 144 | `PostgreSQL` |
| `pg_graphql` | 269 | 55 | `Apache-2.0` |
| `pg_jsonschema` | 268 | 61 | `Apache-2.0` |
| `pg_session_jwt` | 284 | 59 | `Apache-2.0` |

The `--fail` option matters. Without it, cargo-about can exit successfully
while leaving an unresolved crate as `Unknown`. In the unclarified reports,
`pg_parquet`, `pg_graphql`, `pg_jsonschema`, and `pg_session_jwt` each had an
unknown root package license. `pg_parquet` declares `license-file =
"LICENSE"`, but cargo-about 0.9.2 did not automatically synthesize that
license. The checked-in license file clarifications resolved the issue and
made strict mode pass.

The broad accepted list above is only a tool-feasibility list. It must not be
copied as the project's final licensing policy. The final policy should apply
the project's package-specific DFSG review and maintainer decisions.

## Report validation

The following Python snippet validates the key structural properties and
reproduces the counts from the run:

```bash
docker exec pgrx-feasibility bash -lc 'python3 - <<"PY"
import json
import os

targets = [
    ("pg_search", "/workspace/pg-search/pg_search/pg_search.json", "/workspace/results/pg-search/pg-search-about-strict.json"),
    ("pg_parquet", "/workspace/pg-parquet/pg-parquet.json", "/workspace/results/pg-parquet/pg-parquet-about-strict.json"),
    ("pg_graphql", "/workspace/pg-graphql/pg-graphql.json", "/workspace/results/pg-graphql/pg-graphql-about-strict.json"),
    ("pg_jsonschema", "/workspace/pg-jsonschema/pg-jsonschema.json", "/workspace/results/pg-jsonschema/pg-jsonschema-about-strict.json"),
    ("pg_session_jwt", "/workspace/pg-session-jwt/pg-session-jwt.json", "/workspace/results/pg-session-jwt/pg-session-jwt-about-strict.json"),
]

for name, cyclonedx_path, about_path in targets:
    cyclonedx = json.load(open(cyclonedx_path))
    about = json.load(open(about_path))
    components = cyclonedx["components"]
    crates = about["crates"]
    license_records = about["licenses"]
    assert cyclonedx["bomFormat"] == "CycloneDX"
    assert cyclonedx["specVersion"] == "1.5"
    assert all(component.get("version") for component in components)
    assert all(component.get("licenses") for component in components)
    assert all(crate.get("license") not in (None, "Unknown", "") for crate in crates)
    assert all(record.get("text") for record in license_records)
    print(
        name,
        "CycloneDX components=", len(components),
        "dependencies=", len(cyclonedx["dependencies"]),
        "cargo-about crates=", len(crates),
        "license-records=", len(license_records),
        "shared-object-bytes=", os.path.getsize(
            next(
                path for path in (
                    f"/workspace/results/{name}/usr/lib/postgresql/18/lib/{name}.so",
                    f"/workspace/results/{name.replace('_', '-')}/usr/lib/postgresql/18/lib/{name}.so",
                )
                if os.path.exists(path)
            )
        ) if name != "pg_search" else os.path.getsize("/workspace/results/pg-search/usr/lib/postgresql/18/lib/pg_search.so"),
    )
PY'
```

For a simpler artifact-only check, inspect the expected shared objects directly:

```bash
docker exec pgrx-feasibility bash -lc '
  for artifact in \
    /workspace/results/pg-search/usr/lib/postgresql/18/lib/pg_search.so \
    /workspace/results/pg-parquet/usr/lib/postgresql/18/lib/pg_parquet.so \
    /workspace/results/pg-graphql/usr/lib/postgresql/18/lib/pg_graphql.so \
    /workspace/results/pg-jsonschema/usr/lib/postgresql/18/lib/pg_jsonschema.so \
    /workspace/results/pg-session-jwt/usr/lib/postgresql/18/lib/pg_session_jwt.so; do
    test -s "$artifact"
    echo "$artifact"
  done
'
```

## Additional findings

### Exact pgrx version mapping is required

The first `pg_parquet` package attempt used cargo-pgrx 0.16.1 while the
source required pgrx 0.16.0. It failed before compilation with the explicit
diagnostic that cargo-pgrx and the pgrx library versions must be identical.
Installing and selecting cargo-pgrx 0.16.0 made the same build pass. The
target manifest therefore needs a per-extension pgrx CLI version rather than
one global CLI version.

### Cargo graph scope differs between the two raw reports

CycloneDX reported the resolved component graph for the selected manifest and
features. cargo-about reported more crates because its default scope includes
additional build and development dependency information. This difference is
expected and should be preserved when the eventual composition code records
the scope of each source report.

### CycloneDX does not provide the full license text

The raw CycloneDX files retained component license expressions and versions,
including Git source metadata where available. They did not serve as the
full-text license notice. cargo-about's `licenses` records supplied the
deduplicated full license text and the crate-to-expression mapping in this
run.

### Runtime native dependency

`ldd` on the packaged shared objects showed that `pg_search.so` requires:

```text
libopenblas.so.0
libgfortran.so.5
```

The other four packaged extension libraries only showed standard runtime
dependencies such as libc, libm, and libgcc. The eventual pgrx runtime image
must therefore account for the OpenBLAS and Fortran runtime packages needed by
pg_search.

### What this spike did not test

This was a source-build and report-generation feasibility run. It did not
modify or run the future pgrx workflow, did not run the full multi-platform
Buildx image pipeline, did not run `act`, and did not test GitHub attestation.
Those remain implementation and local-pipeline acceptance work.
