# GitHub administrator handoff

This checklist separates local evidence from claims that require GitHub or
production state. The local pgrx implementation must pass its act gate before
these items are closed.

| Responsible administrator | Workflow/setting | Evidence | Completion condition |
| --- | --- | --- | --- |
| Repository administrator | Actions permissions: contents, packages, attestations, and OIDC `id-token: write` | Repository settings and successful run permissions | Each workflow receives only the permissions it uses |
| Registry administrator | GHCR package visibility, write access, package linkage, and production approvals | Successful push and package access | Testing and production references are writable |
| Repository administrator | Environments, required reviewers, secrets, variables, allowed actions, and fork policy | Settings capture or approved run | pgrx build, scan, sign, and promotion steps are allowed |
| Runner administrator | Hosted 16-core runner availability and QEMU/binfmt for amd64/arm64 | Successful matrix run | Both architectures complete without manual intervention |
| Renovate administrator | Enable five `github-tags` regex monitors and update permissions | Renovate dry run/PR | Commit and tag update together; no mutable archive URL |
| Security administrator | Image signing/cosign identity and policy | Verified testing image signatures | Signed promotion is accepted by policy |
| Supply-chain administrator | `actions/attest` permissions and OIDC trust | Verified aggregate SPDX attestation | Signed SPDX subject digest equals the image index |
| Catalog administrator | Repository dispatch/token access to CNPG catalogs | Catalog update run | All five images resolve and pgvector remains upstream-provided |
| Promotion administrator | Referrer-aware recursive copy (ORAS or equivalent) | Destination index, provenance, SBOM, and signatures | Index/platform digests and referrers are preserved |
| Release administrator | Production image copy and production SBOM reattestation | Production digest and attestation verification | Production subject is the copied immutable index |
| Security administrator | Generate the GitHub-attested Trivy transcript | Updated `examples/trivy-sbom-examples.txt` | Target, digest, date, version, and raw output are recorded |

## Required execution order

1. Commit the locally validated pgrx changes to the protected agent branch and
   run the unchanged Debian workflows as a control.
2. Run the pgrx workflow for each target and supported distro/architecture;
   inspect changed-file routing so Debian matrices never contain pgrx targets.
3. Verify BuildKit provenance and the single signed aggregate SPDX attestation.
4. Exercise production copy with OCI referrers and verify index/platform
   digests, SBOM, provenance, and signatures at the destination.
5. Run catalog dispatch/E2E, then generate the GitHub-attested Trivy example.

Local act can prove Dockerfile/build, target filtering, filesystem/Cargo SPDX
composition, local scans, local registry copy, digest equality, and E2E. It
cannot prove GitHub OIDC, hosted-runner behavior, GHCR permissions, Renovate
execution, production referrer copying, or signed production reattestation.
