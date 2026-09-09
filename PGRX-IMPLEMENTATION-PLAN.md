# Additive pgrx extension images: implementation plan

## Current baseline and design direction

Implement this on top of PR 61 at verified head 7828a03863dd0b3750dd75f2915765b07638f9e7
(2026-09-07). PR 61 provides the filesystem-SBOM, ScanCode,
composition-manifest, local-act, and attestation primitives for the Debian
extension images. The pgrx implementation is a sibling build path;
existing Debian Dockerfiles, Bake definitions, workflows, and packaging
behavior should remain unchanged.

The design is intentionally close to the existing Debian contribution model.
Each pgrx target owns a Dockerfile copied from a documented template. The
Dockerfile contains the source archive URL and the Rust commands that build the
extension and produce its Cargo reports. The project-owned pgrx composition
wrapper checks for the required artifacts and combines them with PR 61's
filesystem SBOM. It does not attempt to reconstruct or validate every Cargo
choice from a separate manifest.

This is an implementation plan for PostgreSQL extensions built with pgrx only.
It is not a generic Rust application/container framework, and it does not
cover PGXS extensions, generic Rust binaries, or Rust libraries distributed on
their own.

Cross-platform image support remains part of the implementation: the pgrx Bake
definition, workflows, SBOM layout, and promotion logic must support both
linux/amd64 and linux/arm64. The local implementation gate intentionally
builds and tests one selected platform only. This checkout uses linux/amd64
for local acceptance, but the platform must be parameterized so an ARM laptop
can select linux/arm64. Production builds leave the local override unset and
use the full multi-arch matrix. Cross-platform builds and their validation are
a separate follow-up run after the implementation has passed all local
acceptance criteria; they are not local acceptance criteria.

PR 61 already contains the one small neutral extension point needed here:
scripts/compose_sboms.sh accepts an alternate Bake file while retaining
docker-bake.hcl as the default. The wrapper remains unaware of pgrx. The pgrx
wrapper can call this shared filesystem phase and chain its own Cargo
enrichment after it.

## Initial targets

The first implementation contains these five targets, using the existing
PG18+ project scope and the existing bookworm/trixie and amd64/arm64 build
matrix. The matrix is required for the implementation, while local acceptance
uses only the selected local platform (linux/amd64 in this checkout):

| Image target | Upstream source | Initial release | Cargo package | pgrx |
| --- | --- | --- | --- | --- |
| pg-search / pg_search | paradedb/paradedb | v0.25.6 | pg_search workspace package | 0.19.0 |
| pg-parquet / pg_parquet | CrunchyData/pg_parquet | v0.5.1 | root package | 0.16.0 |
| pg-graphql / pg_graphql | supabase/pg_graphql | v1.6.2 | root package | 0.19.2 |
| pg-jsonschema / pg_jsonschema | supabase/pg_jsonschema | v0.3.4 | root package | 0.16.1 |
| pg-session-jwt / pg_session_jwt | neondatabase/pg_session_jwt | v0.5.0 tag | root package | 0.16.1 |

The feasibility spike established that all five have a root Cargo.lock, can
be built for PostgreSQL 18 with the standard pgrx feature pattern, and produce
usable CycloneDX and cargo-about reports. Its detailed commands and observed
native-library differences are in
PGRX-FEASIBILITY-FINDINGS.md.

Implementation sequencing is deliberately staged. Start with pg_parquet,
pg_graphql, pg_jsonschema, and pg_session_jwt. Defer pg_search until those
four targets build, compose their SBOMs, pass local image checks, and pass the
local E2E path. pg_search is substantially more compute-intensive than the
other targets and has additional native dependencies, including OpenBLAS and
libgfortran. It should be the final implementation phase rather than slowing
down the first end-to-end iteration.

## Target layout and ownership

Each target is a normal top-level extension directory:

    pg-example/
      Dockerfile
      metadata.hcl
      README.md

The reusable template and implementation documentation live under pgrx:

    pgrx/
      templates/Dockerfile.tmpl
      templates/README.md.tmpl
      compose_sboms.sh
      compose_pgrx_sbom.py
      license-about.toml
      Taskfile.yml
      CONTRIBUTING.md
      examples/trivy-sbom-examples.txt
      GITHUB-ADMIN-NEXT-STEPS.md

The target Dockerfile is intentionally editable. Contributors may add native
packages, adjust workspace/package arguments, and adapt the source-specific
packaging commands, provided that the documented output contract remains true.
The project does not require a separate targets.json, generated build-plan
document, source fetcher, or per-target shell build script.

The top-level target HCL remains the source of CNPG/catalog metadata. It should
contain the existing fields such as name, sql_name, image_name,
shared_preload_libraries, ld_library_path, required_extensions,
create_extension, and versions, plus the required build-system discriminator:

    metadata = {
      build_system = "pgrx"
      # existing CNPG metadata follows
    }

Existing targets omit build_system and continue to mean Debian. No source
URL, Cargo package, Rust version, pgrx version, or CycloneDX version is added
to HCL merely to support pgrx. Those are Dockerfile build inputs. The existing
versions.*.*.package value continues to supply the image/catalog source
version, so the version in the Dockerfile's Renovate comment and the HCL
version are updated together by the release PR. This is acceptable duplication
and follows the existing Debian pattern.

For pg_search, required_extensions = ["pgvector"] remains a catalog
dependency. There must be no local pgvector metadata, Dockerfile, or image
stub. The E2E values generator represents this as a catalog-only extension
mount (omitting an empty image reference) and uses its SQL name, vector, in
the Database resource. The selected CNPG extension catalog resolves and pulls
the pgvector image from upstream.

## Dockerfile contract

pgrx/templates/Dockerfile.tmpl should contain the complete ordinary build
sequence, with comments explaining which lines may be customized and which
outputs are required. It should not hide the Rust build behind an elaborate
repository-specific abstraction.

The source declaration is in the target Dockerfile, not HCL. It uses a GitHub
archive URL selected by an immutable commit SHA, with the human-readable tag
as a Renovate comment. The URL is the build input; the downloaded archive's
SHA-256 is calculated as evidence and is not hand-maintained in source:

    # renovate: datasource=github-tags depName=paradedb/paradedb versioning=semver
    RUN curl --fail --location --silent --show-error "https://github.com/paradedb/paradedb/archive/d06d83ab8233c08e4a0104b0281391d81fba713.tar.gz" -o /tmp/source.tar.gz # v0.25.6

The exact Renovate regex convention must be documented and tested against all
five targets. It must update the commit selector and tag comment together and
must never replace the commit-pinned archive with a branch or mutable-tag
URL. A release tag may be tag-only upstream, as with pg_session_jwt; the
archive URL still uses the resolved commit.

The template should show commands equivalent to:

    # Install the target-specific Rust toolchain and matching cargo-pgrx.
    #
    # Extract the source archive, preserving its Cargo.lock.

    cargo pgrx init --pg<PG_MAJOR>=<PG_CONFIG>

    # This is the simple lockfile guard. It must run before packaging.
    cargo metadata --locked --format-version=1

    # Generate the Cargo dependency report from the same source/package/features.
    cargo cyclonedx ... --format json

    # Generate complete license and notice evidence.
    cargo about generate ...

    # Build the PostgreSQL extension.
    cargo pgrx package ...

The exact command arguments remain visible in each target Dockerfile. The
template should use the common initial convention:

    --no-default-features
    --features pg<PG_MAJOR>
    --release

The five initial extensions follow this convention. A target may add a
source-specific feature or workspace/package argument in its Dockerfile when
necessary. The build system does not generate a second command and does not
try to prove that every Cargo graph choice matches a separate HCL schema.

The Dockerfile owns build-time and runtime Debian packages, Rust and
cargo-pgrx installation, workspace/package selection, native-library handling,
pgrx package-output copying, and license-file copying. The matching
cargo-pgrx version is still important: the feasibility run showed that
cargo-pgrx 0.16.1 rejects source using pgrx 0.16.0. The template comments
should call out that the versions must match, while the build naturally fails
if they do not.

The final scratch image must contain the normalized payload:

    /lib/<extension>.so
    /share/extension/<extension>.control
    /share/extension/<extension>*.sql
    /licenses/rust/...
    /licenses/system/...
    /system/...

The target Dockerfile may use any convenient intermediate pgrx package path,
but it must copy the expected files into these final locations. The pgrx
composition wrapper only needs to fail when required final files or reports
are absent; it does not need a generic content-based pgrx package discovery
algorithm.

### Required named SBOM stage

The named SBOM stage is retained. It keeps raw build reports out of the
runtime image while allowing the pgrx wrapper to export them independently:

    FROM scratch AS pgrx-sbom
    COPY --from=builder /tmp/pgrx-sbom/ /pgrx-sbom/

    FROM scratch
    # Copy only the extension payload, runtime libraries, and required licenses.

The stage must expose at least:

    /pgrx-sbom/cyclonedx.json
    /pgrx-sbom/cargo-about.json

Any materialized Rust license/notice files needed in the final image belong
under /licenses/rust/ in the runtime stage as well. Exporting directly from
builder is not the contract: it would export the builder root, including
source and build tooling, rather than only the reports. Raw reports should not
be copied into the final image by default because they duplicate the attached
SPDX and may contain builder-only information. Required license text is
different and must remain in the final image.

## Release monitoring and source acquisition

Renovate is the release monitor and PR creator. A custom regex manager should
match the structured source RUN curl line in each pgrx Dockerfile, use the
GitHub-tags datasource, and capture both the current tag comment and the
40-character commit selector. It should cover all five repositories,
including the tag-only pg_session_jwt release.

The update path is:

    Renovate discovers a new GitHub release/tag
            ↓
    Renovate updates the Dockerfile archive commit and tag comment
            ↓
    Renovate updates the corresponding HCL image/catalog version
            ↓
    the pgrx build downloads that exact archive
            ↓
    cargo metadata --locked fails if Cargo.lock is absent or unusable

There is no second committed release manifest. The build records the exact
archive URL, commit selector, downloaded archive SHA-256, source tag comment,
and Cargo.lock hash in the composition manifest. The archive digest is
per-run evidence because GitHub can change compressed archive bytes without
changing the selected commit.

The initial implementation does not need a separate scheduled release
watcher. A small manual diagnostic can be added later if Renovate needs a
backstop, but it must not become a second release-update mechanism or require
another source of truth.

## Minimal Debian separation and changed-file routing

The current Dagger discovery treats directories containing metadata.hcl as
targets. Add only the classification needed to distinguish:

    missing build_system → debian
    build_system = "debian" → debian
    build_system = "pgrx" → pgrx

The change belongs at the target-list boundary in
dagger/maintenance/parse.go and any corresponding target-list/update entry
point. It should classify and filter targets; it must not contain pgrx build
logic. Add parser/filter tests and regenerate the Dagger client if required.

The existing Debian caller, Bake file, Dockerfiles, and workflow remain
Debian-only. Add a pgrx caller and reusable workflow with its own Bake file.
The pgrx implementation machinery, templates, scripts, tests, and Taskfile
remain under pgrx wherever possible.

The order is mandatory:

    discover metadata
      ↓
    apply build_system filter
      ↓
    construct dorny/paths-filter rules
      ↓
    compute changed-target matrix
      ↓
    dispatch the appropriate workflow

Do not pass all metadata directories to dorny/paths-filter and discard pgrx
targets later with a job-level condition. That would still create Debian
matrix jobs for pgrx extensions.

The Debian shared filter must not be expanded to include pgrx directories.
The pgrx filter should include pgrx target directories, pgrx/**, the pgrx
Bake/workflow files, the target-classification boundary, and
scripts/compose_sbom.py because it is an intentional shared dependency. The
pgrx wrapper may call scripts/compose_sboms.sh through its neutral alternate-
Bake-file input, but that shared wrapper must not contain pgrx-specific logic.

Changes to a target Dockerfile, HCL, or README should schedule only that pgrx
target. Changes to pgrx machinery, docker-bake-pgrx.hcl, the shared SPDX
composer, target classification, or pgrx workflow logic should schedule all
five. A Renovate release PR should validate all five because the release
manager and shared assumptions are common.

Add a mixed Debian/pgrx fixture proving that the Debian matrix contains no
pgrx target and the pgrx matrix contains only pgrx targets. The fixture must
exercise discovery before dorny/paths-filter, not merely a later condition.

## Build and package pipeline

docker-bake-pgrx.hcl is parallel to docker-bake.hcl. It owns pgrx matrix,
tag, OCI annotation, provenance, and testing/production naming definitions,
but has no Debian target definitions. Each target's Dockerfile is used
directly by the pgrx Bake target.

The initial pgrx image tag shape is:

    <image>:<source-version>-<timestamp>-<pg-major>-<distro>

The pgrx Dockerfile should:

1. Start from the exact CNPG PostgreSQL base image for the PG major and distro.
2. Install the build packages required by that extension and PostgreSQL.
3. Install the Rust toolchain and matching cargo-pgrx version shown in the
   Dockerfile comments/commands.
4. Download and extract the commit-pinned GitHub archive.
5. Run cargo pgrx init against the selected pg_config.
6. Run cargo metadata --locked before the package command.
7. Run cargo-cyclonedx and cargo-about, writing their reports under
   /tmp/pgrx-sbom/.
8. Run cargo pgrx package and copy the extension's library, control file,
   SQL files, runtime libraries, and required license texts into /payload.
9. Materialize complete Rust license/notice files under
   /payload/licenses/rust/. The project's policy is DFSG-first and package-
   specific, following Debian's licensing guidance. DFSG-free packages need
   no separate discussion; a package Debian would consider non-free requires
   discussion in the relevant GitHub issue or PR. No license-review artifact
   is checked into source control.
10. Expose the two raw Cargo reports through the named pgrx-sbom stage.
11. Copy only /payload into the final scratch image and run the basic local
    output checks.

The Dockerfile is the flexible part of the contract. The composition wrapper
is responsible for the stable artifact paths, not for making every upstream
project conform to one generated Cargo command.

## SBOM composition and provenance

PR 61's filesystem composition remains the first stage. Its existing Python
composer matches final-image file subjects to builder SBOM files, retains
packages owning shipped files, applies ScanCode license findings, and creates
one multi-platform SPDX document. The pgrx path must reuse that behavior as a
black box.

The current PR 61 shell wrapper is invoked as
scripts/compose_sboms.sh --bake-file PATH. In a cross-platform run, it
combines that Bake file with the selected target's metadata.hcl, injects the
BuildKit SBOM scan-stage argument into the target Dockerfile, exports one
builder SPDX attestation and one ScanCode report for each of linux/amd64 and
linux/arm64, and writes its artifacts under RUNNER_TEMP/extension-sbom. It
emits the attestation-manifest JSON through GITHUB_OUTPUT for the reusable
workflow's attestation matrix. The local gate constrains the selected Bake
target to one parameterized local platform and therefore exports only that
platform's artifacts; this must not remove or weaken the cross-platform path.
The ordinary Docker Bake definition no longer requests a direct SBOM
attestation; the composition wrapper requests the local SBOM export during
composition.

The preferred integration is:

    pgrx/compose_sboms.sh
      ↓
    scripts/compose_sboms.sh --bake-file docker-bake-pgrx.hcl
      ↓
    PR 61 filesystem SPDX + ScanCode + composition manifest
      ↓
    export each platform's pgrx-sbom stage
      ↓
    check required Cargo report files exist
      ↓
    pgrx/compose_pgrx_sbom.py enriches the SPDX predicate
      ↓
    extend the existing composition annotation
      ↓
    upload the same artifact layout for attestation

The existing Debian workflow explicitly calls
scripts/compose_sboms.sh --bake-file docker-bake.hcl. The pgrx wrapper calls
the same script with docker-bake-pgrx.hcl. This extension point already exists
in PR 61 and must remain generic: it must not contain a pgrx branch. This
avoids duplicating the filesystem matching and ScanCode orchestration while
keeping all pgrx-specific code in the pgrx wrapper.

The pgrx wrapper may update each predicate and its composition manifest after
the shared phase. It must retain PR 61's existing annotation and extend its
same document-level OTHER annotation with the Cargo enrichment record. The
final result has one SPDX predicate and one SBOM attestation, not separate
CycloneDX, cargo-about, and filesystem SBOM publications.

The enrichment record should include, at minimum:

- source archive URL and commit selector;
- downloaded archive SHA-256 and Cargo.lock SHA-256;
- Cargo CycloneDX and cargo-about report hashes;
- pgrx Dockerfile/build selection and tool versions;
- the pgrx wrapper and merger revisions; and
- the relationship between the filesystem composition stage and Cargo/license
  enrichment stage.

The final SPDX document should represent Cargo components as SPDX packages,
with versions, source coordinates, dependency relationships, and license
evidence. Convert the raw CycloneDX graph into SPDX; do not paste CycloneDX
JSON into an SPDX comment. Preserve Git dependencies using their Cargo
version plus repository and commit location when available. Do not claim that
every Cargo component is statically linked merely because Cargo resolved it.

The final SPDX must remain interpretable without the raw reports. The raw
CycloneDX and cargo-about files are useful CI/export diagnostics; the complete
license and notice text under /licenses/rust/ is part of the runtime image
when redistribution requires it.

The final SPDX is a point-in-time inventory, not a live vulnerability report.
It must retain enough package name, version, PURL/source, and commit
information for a future scanner to match a later CVE or RustSec advisory.
Known vulnerabilities at generation time are not embedded as a requirement.
No CodeQL, gosec equivalent, or generic Rust code-scanning workflow is part of
the initial implementation. cargo-audit is also out of scope for the first
build gate.

### License evidence

The Dockerfile should invoke the pinned project cargo-about configuration and
materialize complete license/notice text for the selected Cargo graph. This
includes transitive packages and the source extension license where evidence
is available. The pgrx merger maps each Cargo package to its license
expression, extracted license text, copyright/attribution evidence, and final
license-file path where possible.

The policy is not a CNCF or abstract license-name allowlist. Evaluate the
actual package and its dependencies using Debian's licensing guidance and a
DFSG-first project position. Package-specific non-free questions can be
discussed in a GitHub issue or PR; no source-controlled review record is
required.

### Trivy example

Keep the pgrx transcript in its own file,
pgrx/examples/trivy-sbom-examples.txt; do not alter PR 61's Debian example.
Use the same plaintext style, extracting the GitHub-attested SPDX predicate
and then running:

    trivy sbom --scanners vuln,license --no-progress --skip-version-check <pgrx-sbom.spdx.json>

If a pgrx extension or dependency has an active advisory when the example is
generated, use that result. Otherwise choose the pgrx SBOM with the more
interesting license inventory. Record the selected image/index digest, target,
scan date, and Trivy version while preserving the unedited plaintext output.
This GitHub-attested transcript is a deferred admin-runner task; local act
must still run Trivy against the local aggregate predicate.

## Promotion, attestations, and copying

Use PR 61's current split:

- BuildKit/SLSA provenance describes image build identity and materials per
  platform.
- The composed SPDX predicate contains the filesystem/Cargo/license evidence
  and its compact composition manifest.
- actions/attest signs and attaches the one aggregate SPDX predicate to the
  immutable multi-platform index.

The SLSA predicate does not by itself prove how a later SBOM merger ran. The
embedded composition manifest records those post-build inputs and commands.
Do not add a second SBOM-composition attestation by default.

The SBOM and provenance are OCI referrers to the image index. A normal image
copy is not sufficient to guarantee that they move with the image. The
GitHub-only promotion and private-registry documentation must use a
referrer-aware recursive copy operation, such as ORAS recursive copy, and
verify the destination index, SBOM attestation, SLSA provenance, and
signatures. The local workflow should exercise the image/index copy and digest
checks, but cannot prove GitHub OIDC or production-registry behavior.

## Workflows and local validation

Add pgrx caller and reusable workflows parallel to the existing Debian
workflows. The reusable pgrx path should preserve the PR 61 job sequence:

    changed-target routing
      ↓
    multi-platform pgrx Buildx Bake
      ↓
    filesystem SBOM + ScanCode + pgrx-sbom export
      ↓
    combined SPDX composition
      ↓
    artifact upload
      ↓
    GitHub-only SBOM attestation
      ↓
    security scans, image signing, E2E, promotion, reattestation

The local act path is the primary implementation gate. It must execute the
caller workflow, target filtering, selected-platform pgrx builds, SBOM
composition, scanner, local registry copy, digest verification, and
CNPG/Chainsaw E2E. The reusable workflow must provide a deterministic
local-only platform override, accepting linux/amd64 or linux/arm64, so this
gate does not require QEMU or a second architecture's workers. The Bake
definition and reusable workflow must still retain their multi-arch support
for production and the separate post-implementation validation run. The local
gate may skip only the GitHub-identity-dependent SBOM attestation and
production reattachment.

Use the local registry and host-network behavior established by PR 61. A full
local run should be equivalent to:

    artifact_dir="$(mktemp -d)"
    act workflow_dispatch -W .github/workflows/pgrx.yml \
      -e .act/pgrx-local.json \
      --input extension_name=pg-search \
      --input local=true \
      --input platform=linux/amd64 \
      -P ubuntu-24.04=catthehacker/ubuntu:act-latest \
      --container-daemon-socket /var/run/docker.sock \
      --artifact-server-path "$artifact_dir" \
      --artifact-server-port 34568 \
      --container-options '--privileged'

The local registry must be available at 127.0.0.1:5000. The `platform` input
is the local architecture parameter; use linux/amd64 for this checkout or
linux/arm64 on an ARM laptop. Verify the selected-platform image or index and
its platform manifest, copy testing images to local-production references,
compare source/destination digests, run Trivy against each aggregate SPDX,
and run the existing E2E tests. Repeat for all five targets and the supported
local distro matrix before local completion is claimed. Do not run the
cross-platform matrix as part of this gate.

After local completion is claimed, run the separate cross-platform
validation against linux/amd64 and linux/arm64. That follow-up must build the
full platform matrix, export and compose the per-platform SBOM evidence,
verify the multi-platform index and platform digests after registry copying,
and exercise the arm64 image checks and E2E path where the runner supports
them. Its results are required before release readiness, but are outside this
implementation's local acceptance criteria.

## GitHub-admin handoff

Create pgrx/GITHUB-ADMIN-NEXT-STEPS.md as part of the local implementation.
It is a handoff checklist, not a license-review artifact and not a substitute
for local tests. It must list every step that cannot be completed in this
checkout:

- GitHub Actions permissions for contents, packages, attestations, and OIDC;
- GHCR package/repository access, environments, approvals, secrets, variables,
  allowed actions, hosted-runner/QEMU availability, and branch/ruleset needs;
- Renovate enablement and permissions for the five source monitors;
- repository configuration needed by image signing, actions/attest, catalog
  dispatch, production copying, and referrer-aware mirroring; and
- the order for committing locally validated changes to the real repository,
  running pgrx and unchanged Debian workflows on hosted runners, checking
  changed-file routing, verifying BuildKit provenance and signed SBOM
  attestations, exercising production copy/reattestation, and generating the
  GitHub-attested Trivy transcript.

For each deferred item, record the responsible administrator, workflow or
setting, expected evidence, and completion condition. Local act success is the
prerequisite for this handoff. GitHub execution is required before claiming
signed provenance, signed SBOMs, production promotion, or release readiness.

## Implementation files

Expected new files and narrowly scoped changes are:

    pg-search/{Dockerfile,metadata.hcl,README.md}
    pg-parquet/{Dockerfile,metadata.hcl,README.md}
    pg-graphql/{Dockerfile,metadata.hcl,README.md}
    pg-jsonschema/{Dockerfile,metadata.hcl,README.md}
    pg-session-jwt/{Dockerfile,metadata.hcl,README.md}

    pgrx/templates/Dockerfile.tmpl
    pgrx/templates/README.md.tmpl
    pgrx/compose_sboms.sh
    pgrx/compose_pgrx_sbom.py
    pgrx/license-about.toml
    pgrx/Taskfile.yml
    pgrx/CONTRIBUTING.md
    pgrx/examples/trivy-sbom-examples.txt
    pgrx/GITHUB-ADMIN-NEXT-STEPS.md

    docker-bake-pgrx.hcl
    CONTRIBUTING_NEW_PGRX_EXTENSION.md
    .github/workflows/pgrx.yml
    .github/workflows/pgrx_targets.yml
    .github/PULL_REQUEST_TEMPLATE/new_pgrx_extension.md

There should be no pgrx/targets.json, no pgrx/fetch_release_source.py, and
no generic pgrx/Dockerfile replacing target-owned Dockerfiles. The template
is copied into each target and may be modified with the source-specific
commands required by that extension.

The root contributor entrypoint should link to pgrx/CONTRIBUTING.md; the
existing Debian guide and templates remain unchanged. A pgrx scaffold helper
may copy the pgrx templates, but it must not alter the existing Debian
create-extension helper.

## Implementation order and local acceptance criteria

### Phase 0: completed feasibility evidence

The feasibility spike is recorded in
PGRX-FEASIBILITY-FINDINGS.md. It documents reproduction commands for all five
builds, CycloneDX, cargo-about, license counts, the exact pgrx-version mismatch
found, and pg_search's additional runtime libraries.

### Phase 1: target Dockerfiles and routing

Add the five target directories and Dockerfiles from the template, HCL
metadata, pgrx Bake definition, contributor documentation, and the minimal
build_system target filtering. Use PR 61's existing alternate-Bake-file
option; do not add a second composition interface.

Run locally on the selected platform (linux/amd64 for this checkout) for
pg_parquet, pg_graphql, pg_jsonschema, and pg_session_jwt:

- Dockerfile syntax and docker buildx bake --check for the pgrx and existing
  Debian definitions;
- parser/filter tests with mixed Debian and pgrx fixtures;
- Renovate configuration/regex fixtures for all five archive lines; and
- focused pgrx build jobs for fast iteration.

### Phase 2: local SBOM composition

Implement the named pgrx-sbom stage, pgrx wrapper, Cargo-to-SPDX enrichment,
license-file handling, and Trivy transcript selection logic. Run the shared
PR 61 composer tests plus pgrx fixtures. Build the selected local platform
locally for the first four targets and confirm that the final aggregate SPDX contains
final files, retained system packages, the extension artifact package, Cargo
package/version/source data, dependency edges, and license evidence without
requiring raw reports to interpret it. Preserve the linux/arm64 build and
composition path for the separate post-implementation cross-platform run.

Run Trivy locally with both vulnerability and license scanners. Current
findings are diagnostic only; the signed SBOM must remain a durable inventory
for future advisory matching.

### Phase 3: full local act and handoff

Run the full pgrx caller through act for the first four targets and the
configured local distro matrix, constrained to the selected local platform.
Confirm changed-file routing, selected-platform image build, named-stage export, combined SPDX
artifact upload, local scans, local image copy/digest equality, and E2E. The
cross-platform Bake/workflow definitions must remain present, but their
execution is deferred to the separate post-implementation validation. Only
the GitHub-identity-dependent attestation steps may be skipped.

### Phase 4: pg_search final phase

After the first four targets pass the full local gate, add and validate
pg_search. Run its compute-heavy selected-platform build separately first,
then run its named-stage export, combined SPDX composition, Trivy scan, local
image copy/digest verification, and catalog-resolved pgvector E2E. Confirm the
additional OpenBLAS/libgfortran runtime closure and license files before
claiming the complete five-target implementation. Defer its arm64 and full
cross-platform validation to the separate post-implementation run.

Complete pgrx/GITHUB-ADMIN-NEXT-STEPS.md with actions that cannot be proven
locally: repository/workflow permissions, OIDC and attestations, GHCR access,
Renovate enablement, hosted-runner execution, production copy/reattestation,
referrer-aware mirroring, and generation of the GitHub-attested Trivy example.

### Local acceptance criteria

- Existing Debian builds and routing remain unchanged; Debian matrices never
  contain pgrx targets.
- pg_parquet, pg_graphql, pg_jsonschema, and pg_session_jwt build the expected
  extension files for the local PG18 bookworm/trixie matrix on the selected
  local platform before pg_search is attempted.
- pg_search is validated as the final target on the selected local platform and builds
  the expected files, including its additional native runtime closure.
- Every Dockerfile uses a commit-pinned GitHub source archive and the build
  fails naturally when its required Cargo.lock is absent or unusable.
- Each target emits CycloneDX and cargo-about reports through the named
  pgrx-sbom stage.
- Required Rust and system license/notice files are present in the final
  image and represented in the combined SPDX document.
- The final SPDX contains the PR 61 filesystem composition plus Cargo package,
  version, source, dependency, and license data in one valid document.
- The composition annotation records both the PR 61 filesystem stage and the
  pgrx Cargo/license enrichment stage.
- The full pgrx caller runs under act on the selected local platform with local
  registry behavior for the first four targets, and then for pg_search in the
  final phase; only GitHub-identity-dependent attestation is omitted.
- Local image copy preserves the selected-platform image/index and platform digest, and
  Trivy can query every local aggregate predicate with
  --scanners vuln,license.
- CNPG/Chainsaw E2E passes on the selected local platform for all five targets, with
  pgvector resolved from the extension catalog and no local pgvector stub.
- The Bake definitions, target Dockerfiles, SBOM composition, workflows, and
  copy/promotion logic retain support for linux/amd64 and linux/arm64; the
  local architecture is parameterized, and the cross-platform build and
  validation are explicitly deferred until after this local implementation
  gate completes.
- No generic Rust code-scanning workflow, live vulnerability report, or
  source-controlled license-review artifact is required.
- The admin handoff explicitly separates proven local behavior from deferred
  GitHub-only claims.

The following are deliberately not local acceptance criteria: linux/arm64 or
other cross-platform build execution and validation, GitHub OIDC identity,
actions/attest signatures, production SBOM reattestation, GHCR permissions,
hosted-runner behavior, production referrer copying, and the GitHub-attested
Trivy transcript. Cross-platform validation is a separate post-implementation
release-readiness task, not a prerequisite for completing this local
implementation gate.

## References inspected

- Gist proposal: https://gist.github.com/ardentperf/8696974e930b049abce1e54ce7ac48d5
- Stacking point, PR 61: https://github.com/cnpg-extensions/postgres-extensions-containers/pull/61
- SLSA provenance: https://slsa.dev/spec/v1.2/provenance
- Docker Build attestations: https://docs.docker.com/build/metadata/attestations/
- OCI Distribution referrers: https://github.com/opencontainers/distribution-spec/blob/main/spec.md
- SPDX 2.3 annotations: https://spdx.github.io/spdx-spec/v2.3/annotations/
- ORAS recursive copy: https://oras.land/docs/1.1/commands/oras_cp/
- GitHub Actions attest: https://github.com/actions/attest
- Renovate regex manager: https://docs.renovatebot.com/modules/manager/regex/
- Debian licensing guidance: https://www.debian.org/legal/licenses/
- CloudNativePG security documentation: https://cloudnative-pg.io/docs/devel/security/#code
- pgrx: https://github.com/pgcentralfoundation/pgrx
- cargo-cyclonedx: https://github.com/trueforge-org/cargo-cyclonedx
- cargo-about: https://github.com/EmbarkStudios/cargo-about
