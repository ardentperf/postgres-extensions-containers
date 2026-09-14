# Upstream Sync Commit Review

Reviewed locally on 2026-09-14 for the upstream merge branch.

- Mirror ref: `origin/main` at `b0fff504974d3dd8d5b179e5a1c9e8efd10c603f` (`cnpg-extensions/postgres-extensions-containers`)
- Downstream merge base: `x-ai/ardentperf/revert-7d0e470` at `e6df6e44849dbee60d3e9eb372c9b08c7ead7677`
- Upstream ref: `upstream/main` at `c1c47c21fb6ffa7ff46d19f019e8d6502dc8ffec` (`cloudnative-pg/postgres-extensions-containers`)
- Last upstream commit already merged: `011b3fc72455574a6b87043f14c220f6b4cca160`
- Downstream merge commit: `de085321536e94a602b62d32f99ca21e47fcc614`
- Upstream commits reviewed in `011b3fc72455574a6b87043f14c220f6b4cca160..c1c47c21fb6ffa7ff46d19f019e8d6502dc8ffec`: 7
- Detailed non-dependency commits: 1
- Pure dependency chore commits consolidated below: 6

## Review rules

`Touches mirror files?` is `Yes` when at least one exact changed path exists in
the downstream mirror at `origin/main`. Extension-specific paths absent from
the mirror are documented as intentional exclusions. Pure `chore(deps):`
commits are not replayed individually; their final cumulative values are
reviewed once below.

## Consolidated dependency-only updates

| Dependency area | Reviewed commits | Final upstream value / relevant paths | Decision |
| --- | --- | --- | --- |
| Kind node image | `71af50fb7ddd1c08b2984165db900ee2c39d6b21` (2026-09-07, `chore(deps): update kindest/node docker tag to v1.37.0 (#327)`) | `Taskfile.yml`: `KIND_NODE_VERSION` `v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5` | Adopt with the shared E2E maintenance change. |
| kubectl image | `88472303288cc00b6b148f71ee99374efebcd719` (2026-09-07, `chore(deps): update alpine/kubectl docker tag to v1.37.0 (#330)`) | `Taskfile.yml`: `KUBECTL_VERSION` `1.37.0@sha256:f4ec5b2f9c92ba565a544e48fbcfe5353e3c6b96507f00dc898ccfb4b87889c5` | Adopt the shared tool pin. |
| psql test image | `32115022ca8c2442fc9f69fbc5a92eabf17be29f` (2026-09-07, `chore(deps): update alpine/psql:18.6 docker digest to 466b9fb (#329)`) | Upstream reviewed `test/check-extension.yaml` value: `alpine/psql:18.6@sha256:466b9fb940b45d317099c89d26ee8f1078dced59ef9304f9f4eab2d5fc616d46`; downstream `origin/main` already had newer `alpine/psql:18.6@sha256:2042ec7a9a4200b70f387287cb0307f09fe565f1eab6840a1d5a87df68bfe544`. Other changed paths are upstream-only extension tests. | Retain the newer downstream pin; do not regress to the older upstream digest. Exclude extension-only paths. |
| QEMU action | `140f9f92a1cc52fc25dfc5f60a0874a70affb91d` (2026-09-08, `chore(deps): update docker/setup-qemu-action digest to 1f40c72 (#332)`) | `.github/workflows/bake_targets.yml`: `docker/setup-qemu-action@1f40c72289eff860ee54a304f1438e3cff362e0a` | Adopt the shared workflow pin. |
| pg_ivm package | `7d5a1e30c64d6bbc2e5d7e7bc98904429d091023` (2026-09-11, `chore(deps): update dependency postgresql-18-pg-ivm (#334)`) | Upstream-only `pg-ivm/README.md` and `pg-ivm/metadata.hcl` | Exclude; the downstream mirror does not publish pg_ivm. |
| TimescaleDB package | `c1c47c21fb6ffa7ff46d19f019e8d6502dc8ffec` (2026-09-11, `chore(deps): update dependency postgresql-18-timescaledb (#335)`) | Upstream-only `timescaledb-oss/README.md` and `timescaledb-oss/metadata.hcl` | Exclude; the downstream mirror does not publish TimescaleDB. |

## Detailed review: commits planned for adoption

| Audit order | Date | Upstream commit | Subject | Touches mirror files? | Mirror paths / paths absent from mirror | Adoption note |
| ---: | --- | --- | --- | :---: | --- | --- |
| 1 | 2026-09-04 | [82ac57153b5448e17cfc5f7bf55b1d2172647d99](https://github.com/cloudnative-pg/postgres-extensions-containers/commit/82ac57153b5448e17cfc5f7bf55b1d2172647d99) | ci(e2e): replace aweris/daggerverse kind module with an in-house built container (#328) | Yes | `Taskfile.yml` | Adopt — replace the unmaintained Kind module with the pinned in-house toolbox and retain the downstream E2E task structure. |

## Detailed review: commits not relevant to this mirror

There are no additional substantive non-dependency commits in this review
range. The extension-specific dependency paths are listed in the consolidated
dependency table above and remain excluded.

| Audit order | Date | Upstream commit | Subject | Touches mirror files? | Mirror paths / paths absent from mirror | Exclusion note |
| ---: | --- | --- | --- | :---: | --- | --- |
| — | — | — | None | — | — | All six dependency-only commits were handled in the consolidated table; no other substantive commit is in this range. |

## Merge resolution

- Preserve the downstream extension set, downstream extension metadata, and
  downstream branding; do not add upstream-only extension files or package
  updates.
- Adopted the shared `Taskfile.yml`, `.github/workflows/bake_targets.yml`, and
  `test/check-extension.yaml` changes, including the in-house Kind toolbox and
  relevant final dependency pins.
- Retained the newer downstream `alpine/psql:18.6` digest in
  `test/check-extension.yaml` instead of adopting the older upstream digest.
- Preserved the downstream catalog update command in `e2e:install-cnpg` while
  adapting its kubeconfig acquisition to the upstream Kind toolbox.
- Keep downstream `CODEOWNERS`, security metadata, image locations, and policy
  links if touched by merge ancestry; do not copy upstream ownership changes.
- Check repository and image identity values for accidental
  `cloudnative-pg` references before finalizing the merge.

## Conflict decisions

The merge produced conflicts in `Taskfile.yml`, shared
`test/check-extension.yaml`, and extension-specific paths that are absent from
the downstream mirror. `Taskfile.yml` was resolved in favor of the newer
upstream in-house Kind implementation, while retaining the downstream catalog
update command. The newer downstream psql test pin was retained instead of
adopting the older upstream cumulative value. Downstream `pg-uuidv7/metadata.hcl` was preserved, and the upstream-only
`pg-ivm`, `pgrouting`, `postgis`, `timescaledb-oss`, and `wal2json` conflict
paths were removed.

## Validation

- `git diff --cached --check` passed with no whitespace errors or conflict
  markers.
- `task --summary` parsed the merged `Taskfile.yml` successfully.
- `PATH=<isolated-Dagger-v0.21.7>:$PATH task checks:all` passed for all
  downstream extension targets with no warnings.
- The staged merge delta contains only `Taskfile.yml`,
  `test/check-extension.yaml`, and this merge record; no upstream-only
  extension directories or extension-specific version updates were added.
- Repository and image identity references were reviewed; downstream
  `cnpg-extensions` branding, catalog, image, and policy references remain in
  place.

## Bottom line

Adopt the shared in-house Kind E2E maintenance change and relevant cumulative
tool, workflow, and shared-test dependency pins. Keep upstream-only extension
content and extension-specific package updates out of the downstream mirror.
