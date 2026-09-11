# pgrx Extension Contributor Contract

This document defines the proposed contract for adding a PostgreSQL extension
built with pgrx. It is intentionally modeled on the existing Debian
extension workflow: a contributor provides a Dockerfile based on a documented
template, and the repository composes the resulting image and SBOM.

The scope is pgrx PostgreSQL extensions only. This is not a contract for
generic Rust applications, Rust libraries, PGXS extensions, or pgmq.

## Contributor-provided structure

A target contains:

    pg-example/
      Dockerfile
      metadata.hcl
      README.md

The contributor copies pgrx/templates/Dockerfile.tmpl, adapts it for the
upstream extension, and keeps the required output contract. The Dockerfile is
the source of truth for source acquisition and Cargo commands. There is no
pgrx/targets.json and no separate target build manifest.

metadata.hcl remains the source of CNPG/catalog metadata. It contains the
existing target fields and the required build-system marker:

    metadata = {
      build_system = "pgrx"
      # name, sql_name, image_name, versions, and other CNPG fields
    }

The HCL does not duplicate the source archive URL, Cargo package, Rust
toolchain, pgrx version, or SBOM tool versions. The image/source version in
versions is still updated with the Dockerfile's Renovate tag comment, as is
already done for repeated Debian version values.

## Dockerfile responsibilities

The contributor's Dockerfile should visibly contain the following:

1. The CNPG PostgreSQL base image and PG-major arguments.
2. Build-time packages, including PostgreSQL development headers and any
   source-specific native dependencies.
3. The Rust toolchain and matching cargo-pgrx installation.
4. A commit-pinned GitHub source archive URL.
5. Cargo commands for pgrx initialization, the locked metadata check,
   CycloneDX, cargo-about, and packaging.
6. Copy commands that normalize the pgrx package into the required payload.
7. Runtime-library and license/notice-file handling.
8. A named pgrx-sbom stage exposing the raw Cargo reports.
9. A final scratch image containing only the extension payload, runtime
   libraries, and required license/notice files.

The template should contain extensive comments explaining these requirements,
the reason for the named stage, and the paths expected by the composition
workflow. It should show the ordinary commands rather than require a hidden
generic Rust build helper.

## Source declaration and Renovate

The source URL belongs in the Dockerfile. It must select an immutable commit
through GitHub's archive endpoint:

    # renovate: datasource=github-tags depName=paradedb/paradedb versioning=semver
    RUN curl --fail --location --silent --show-error "https://github.com/paradedb/paradedb/archive/<40-character-commit>.tar.gz" -o /tmp/source.tar.gz # v0.25.6

The exact source-line regex must be parser-safe for Dockerfile and Renovate.
Renovate updates the commit selector and tag comment together. The build must
never use a branch or mutable release tag as its source input.

The downloaded archive SHA-256 and Cargo.lock SHA-256 are calculated during
the build and recorded in the composition manifest. They are evidence, not
additional contributor-maintained fields.

Renovate should also update the corresponding image/catalog version in
metadata.hcl. The two version declarations are deliberately duplicated because
the existing Debian infrastructure already uses that model. A consistency
fixture should ensure the tag comment and catalog version do not silently
diverge.

## Standard Rust commands

The template should use commands equivalent to:

    cargo pgrx init --pg<PG_MAJOR>=<PG_CONFIG>
    cargo metadata --locked --format-version=1
    cargo cyclonedx ... --format json
    cargo about generate ...
    cargo pgrx package ...

The initial convention is:

    --no-default-features
    --features pg<PG_MAJOR>
    --release

A contributor may customize workspace/package selection, additional Cargo
features, the source directory, and target-specific command arguments directly
in the Dockerfile. For example, pg_search selects its workspace package while
the other initial targets use their root package.

The contributor does not provide a command through HCL. They also do not need
to conform to a generated command abstraction. The template and comments define
the normal path, while the editable Dockerfile provides the flexibility needed
by pgrx source releases.

cargo-pgrx must match the pgrx crate version used by the source release. The
feasibility work showed that cargo-pgrx 0.16.1 rejects source using pgrx 0.16.0.
A mismatch should fail through the ordinary build command; no separate graph
resolver is required.

The cargo metadata locked command is the simple lockfile guard. A release
without Cargo.lock, or one whose dependencies cannot be resolved without
changing Cargo.lock, fails before packaging. The repository does not need a
separate pre-dispatch source validator.

## Output contract

The Dockerfile must normalize the final runtime image to:

    /lib/<extension>.so
    /share/extension/<extension>.control
    /share/extension/<extension>*.sql
    /licenses/rust/...
    /licenses/system/...
    /system/...

All upgrade SQL files required by the extension must be copied. The final
image must not contain the compiler, Cargo registry, source tree, PostgreSQL
headers, pgrx embed helper binaries, or build cache.

The composition workflow performs only the necessary output checks. It fails
when required extension files, reports, or license directories are absent. It
does not implement a general pgrx package-output discovery algorithm and does
not validate every Dockerfile command semantically.

## Named SBOM stage

The Dockerfile must expose raw Cargo reports through a separate named stage:

    FROM scratch AS pgrx-sbom
    COPY --from=builder /tmp/pgrx-sbom/ /pgrx-sbom/

    FROM scratch
    # Copy only runtime payload and required license files.

The stage must contain at least:

    /pgrx-sbom/cyclonedx.json
    /pgrx-sbom/cargo-about.json

The pgrx composition wrapper exports this stage locally for each platform and
checks that the reports are non-empty. Exporting the builder stage directly is
not the contract because that would expose the entire builder filesystem.
Raw reports are not copied into the runtime image by default. Complete license
and notice text is copied into the runtime image separately under
licenses/rust because that is redistribution evidence rather than a build
diagnostic.

## License evidence

The Dockerfile invokes the pinned project cargo-about configuration and
materializes complete license and notice text for the selected Cargo graph,
including transitive packages and the extension's own source license where
available.

The final SPDX enrichment maps Cargo packages to their license expressions,
source evidence, copyright/attribution data, extracted license text, and final
license-file paths. The raw cargo-about report is not required to interpret the
published SPDX.

The policy is DFSG-first and follows Debian's licensing guidance. It is not a
CNCF list, OSI list, or abstract license-name allowlist. A package that Debian
would consider non-free can be discussed in the GitHub issue or PR for that
package. No license-review record is added to source control. The project
decides on actual packages and dependencies, not license names in isolation.

## System libraries and packaging

The Dockerfile is responsible for target-specific native build packages and
runtime libraries. It should use the selected CNPG PostgreSQL image as its
base, copy the extension's runtime library closure into system, preserve
required symlink aliases, and copy the relevant system copyright/license
files.

The initial feasibility run found that pg_search requires additional native
runtime libraries including libopenblas.so.0 and libgfortran.so.5. The other
four initial targets used only the standard runtime closure observed in the
spike. Each Dockerfile should document its own requirements rather than
forcing every pgrx target through pg_search's layout.

## Cargo and SPDX expectations

cargo-cyclonedx supplies Cargo package names, versions, source identities,
license declarations, and dependency edges for the selected graph.
cargo-about supplies license text and attribution evidence. The pgrx merger
converts the raw CycloneDX graph into SPDX packages and relationships, then
adds the license evidence.

The merger must not claim that every resolved Cargo component is statically
linked into the final extension. Cargo dependency resolution is useful
supply-chain evidence but is not a complete linker map.

The result is one aggregate SPDX document combining:

    final image files and OS package ownership
    + Cargo package/version/source/dependency data
    + Cargo license and notice evidence

The raw reports remain optional CI diagnostics after the final SPDX is
generated. The final SPDX must be useful without them.

## SBOM composition integration

The pgrx workflow invokes the shared PR 61 filesystem composer first, then
chains pgrx-specific enrichment. PR 61's current wrapper already accepts the
alternate Bake-file argument needed for this:

    pgrx/compose_sboms.sh
      -> scripts/compose_sboms.sh --bake-file docker-bake-pgrx.hcl
      -> export the pgrx-sbom stage
      -> check required report paths
      -> pgrx/compose_pgrx_sbom.py
      -> extend PR 61's composition annotation

The existing Debian workflow explicitly calls the shared wrapper with
docker-bake.hcl. The pgrx wrapper passes docker-bake-pgrx.hcl. The shared
wrapper must remain pgrx-agnostic and must not gain pgrx conditionals.

The pgrx wrapper preserves PR 61's final-file matching, ScanCode findings,
SPDX relationships, composition manifest, and artifact layout. It updates the
same document-level composition annotation with Cargo report hashes, source
archive/commit, Cargo.lock hash, pgrx command/tool details, and enrichment
revision. There is one final SPDX predicate and one SBOM attestation.

## Workflow and local testing

The pgrx caller and reusable workflow are parallel to the Debian workflows.
Target classification must happen before dorny/paths-filter creates target
filters or matrices. A Debian change must never create pgrx jobs, and a pgrx
change must not cause Debian target jobs merely because shared pgrx-owned files
changed.

The full local act path must test:

- target discovery and changed-file routing;
- the five Dockerfiles and multi-platform Buildx Bake;
- pgrx-sbom stage export;
- filesystem and Cargo SPDX composition;
- Trivy vulnerability/license scanning;
- local registry push and testing-to-production-like copy;
- index and platform digest equality; and
- CNPG/Chainsaw E2E, with pgvector resolved from the extension catalog for
  pg_search.

Only GitHub-identity-dependent SBOM attestation and production reattestation
are omitted locally. Those actions, hosted runners, GHCR permissions,
Renovate execution, production referrer copying, and the GitHub-attested
Trivy example belong in pgrx/GITHUB-ADMIN-NEXT-STEPS.md.

## Initial targets

The first five contributors/target definitions are:

| Target | Repository | Release | Cargo package | Special case |
| --- | --- | --- | --- | --- |
| pg-search | paradedb/paradedb | v0.25.6 | pg_search | workspace package; requires catalog pgvector |
| pg-parquet | CrunchyData/pg_parquet | v0.5.1 | pg_parquet | root package |
| pg-graphql | supabase/pg_graphql | v1.6.2 | pg_graphql | root package |
| pg-jsonschema | supabase/pg_jsonschema | v0.3.4 | pg_jsonschema | root package |
| pg-session-jwt | neondatabase/pg_session_jwt | v0.5.0 tag | pg_session_jwt | tag without a GitHub Release object |

All are initially tested for PostgreSQL 18, bookworm/trixie, and amd64/arm64.
The exact seed commits and reproduction commands are documented in
PGRX-FEASIBILITY-FINDINGS.md.

## Contributor checklist

Before submitting a new pgrx target, the contributor should:

- copy and customize the pgrx Dockerfile template;
- use a commit-pinned GitHub archive URL and Renovate tag comment;
- preserve a versioned Cargo.lock in the source archive;
- run the standard pgrx initialization, locked metadata, CycloneDX,
  cargo-about, and package commands;
- copy the extension library, control/SQL files, runtime libraries, and
  required license text into the prescribed locations;
- expose cyclonedx.json and cargo-about.json through pgrx-sbom;
- add CNPG metadata and a README;
- run the focused local build and full act workflow; and
- explain any non-free package concern in the GitHub issue or PR rather than
  adding a review artifact.
