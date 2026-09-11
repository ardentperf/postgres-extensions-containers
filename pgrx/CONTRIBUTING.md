# Contributing a pgrx extension

The pgrx path is for PostgreSQL extensions whose upstream release is built
and packaged with pgrx. It is not a generic Rust application, PGXS extension,
or Rust library distribution framework.

## Required target

Each target owns these files:

```text
pg-example/
  Dockerfile
  metadata.hcl
  README.md
```

Run `task create-extension NAME=myextension BUILD_SYSTEM=pgrx` to scaffold the
target, then edit the Dockerfile directly. Keep the source archive,
Cargo package/manifest selection, native packages, matching cargo-pgrx version,
and output normalization visible in that Dockerfile. The checked-in helper in
`pgrx/` may own shared Rust/reporting setup when a Dockerfile downloads the
source before deriving its build-tool versions; the Dockerfile must invoke
that helper explicitly.

`metadata.hcl` is the CNPG/catalog source and must set:

```hcl
metadata = {
  build_system = "pgrx"
}
```

The source URL, Rust/pgrx versions, Cargo feature selection, and SBOM tool
versions belong in the Dockerfile. The `versions.*.*.package` and `sql` values
remain the catalog/image source version and must be updated with the Dockerfile
release tag.

## Dockerfile contract

The target Dockerfile must visibly perform the following sequence:

- install PostgreSQL development headers and target-specific native build deps;
- install a pinned Rust toolchain and matching cargo-pgrx, directly or through
  an explicitly invoked helper in `pgrx/`;
- download a Renovate-managed GitHub source archive, either commit-pinned or
  selected through a tag/version input;
- verify `Cargo.lock` with `cargo metadata --locked` before packaging;
- generate CycloneDX and cargo-about reports from the same manifest/features,
  directly or through that helper;
- run `cargo pgrx package` and normalize `.so`, control, SQL, runtime library,
  and license files into `/payload`;
- expose `/pgrx-sbom/cyclonedx.json` and `/pgrx-sbom/cargo-about.json` through
  `FROM scratch AS pgrx-sbom`; and
- copy only `/payload` into the final scratch image.

The build naturally fails when a release has no usable Cargo.lock. The cargo-
pgrx version must match the pgrx crate version; adjacent versions can reject
one another before compilation.

The final payload uses `/lib`, `/share/extension`, `/system`,
`/licenses/rust`, and `/licenses/system`. Complete license text from
cargo-about is redistribution evidence and remains in the runtime image. Raw
reports remain in the named stage.

## Licensing and dependencies

The policy is DFSG-first and package-specific. The cargo-about configuration
helps enforce complete evidence for the initial target set; it is not a
project-wide license-name allowlist. Discuss a package Debian would consider
non-free in the issue or pull request. Do not add a source-controlled
license-review artifact.

Catalog dependencies are expressed by name in `required_extensions`. Do not
create a local metadata/Dockerfile/image stub for an upstream catalog extension.

## Validation

From the repository root:

```bash
python3 -m unittest discover -s pgrx -p 'test_*.py'
go test ./dagger/maintenance/...
docker buildx bake -f docker-bake.hcl -f pg-rrule/metadata.hcl --check \
  --set '*.output=type=cacheonly'
docker buildx bake -f docker-bake-pgrx.hcl -f pg-parquet/metadata.hcl --check
```

Use the local caller workflow for the full build, composition, Trivy, image
copy, and E2E path. Only GitHub identity-dependent attestation and production
reattachment are intentionally deferred to repository administrators.
