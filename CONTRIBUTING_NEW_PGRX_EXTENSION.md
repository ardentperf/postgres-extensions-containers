# Adding a pgrx extension

This repository supports pgrx PostgreSQL extensions through a separate build
path. The contributor contract is documented in
[`pgrx/CONTRIBUTING.md`](pgrx/CONTRIBUTING.md).

1. Copy `pgrx/templates/Dockerfile.tmpl` and `pgrx/templates/README.md.tmpl`
   into a new top-level target directory.
2. Add `metadata.hcl` with `build_system = "pgrx"`, CNPG metadata, and the
   source release version for both bookworm and trixie.
3. Use an immutable 40-character GitHub commit archive URL and keep the
   Renovate tag comment beside it.
4. Run locked metadata, CycloneDX, cargo-about, and pgrx package commands;
   normalize the final payload and expose the named `pgrx-sbom` stage.
5. Run the focused pgrx checks and the local pgrx caller before submitting.

Do not add `pgrx/targets.json`, a generic pgrx Dockerfile, a release manifest,
or a local stub for a catalog dependency such as pgvector.
