#!/usr/bin/env bash
set -Eeuo pipefail

# The shared composer performs final-file checksums, Debian ownership,
# ScanCode enrichment, and multi-platform document composition. This target
# then exports its own evidence stage and adds native source/runtime records.
./scripts/compose_sboms.sh --bake-file pg-duckdb/build/docker-bake.hcl

working_directory="${RUNNER_TEMP}/extension-sbom"
bake_definition="${working_directory}/bake.json"
mapfile -t bake_targets < <(jq -r '.target | keys[]' "${bake_definition}")
test "${#bake_targets[@]}" -gt 0

platform_spec="${BUILD_PLATFORMS:-linux/amd64 linux/arm64}"
read -r -a platforms <<< "${platform_spec}"
test "${#platforms[@]}" -gt 0
for platform in "${platforms[@]}"; do
  case "${platform}" in
    linux/amd64|linux/arm64) ;;
    *)
      echo "unsupported build platform: ${platform}" >&2
      exit 2
      ;;
  esac
done

for bake_target in "${bake_targets[@]}"; do
  manifest_paths=()
  evidence_roots=()
  for platform in "${platforms[@]}"; do
    output_directory="${working_directory}/pg-duckdb-${bake_target}-${platform//\//-}"
    mkdir -p "${output_directory}"

    docker buildx bake -f pg-duckdb/build/docker-bake.hcl -f "${EXTENSION_NAME}/metadata.hcl" "${bake_target}" \
      --set "${bake_target}.platform=${platform}" \
      --set "${bake_target}.dockerfile=${EXTENSION_NAME}/.sbom.Dockerfile" \
      --set "${bake_target}.target=pg-duckdb-sbom" \
      --set "${bake_target}.output=type=local,dest=${output_directory}" \
      --progress plain

    evidence_root="${output_directory}/pg-duckdb-sbom"
    manifest="${evidence_root}/resolved-manifest.json"
    test -s "${manifest}"
    test -s "${evidence_root}/coverage.json"
    test -s "${evidence_root}/license-index.json"
    test -s "${evidence_root}/build-source-evidence.json"
    test -d "${evidence_root}/licenses"
    manifest_paths+=("${manifest}")
    evidence_roots+=("${evidence_root}")
  done

  predicate="${working_directory}/predicates/${bake_target}/extension-sbom.spdx.json"
  test -s "${predicate}"
  compose_args=(
    ./pg-duckdb/build/compose_pg_duckdb_sbom.py
    --spdx "${predicate}"
    --output "${predicate}"
    --extension-name "${EXTENSION_NAME}"
  )
  for index in "${!platforms[@]}"; do
    compose_args+=(
      --manifest "${manifest_paths[$index]}"
      --platform "${platforms[$index]}"
      --evidence-root "${evidence_roots[$index]}"
    )
  done
  "${compose_args[@]}"
  jq -e --arg namespace "${COMPOSITION_NAMESPACE:-https://github.com/cnpg-extensions/postgres-extensions-containers/sbom-composition/v1}" '
    .spdxVersion == "SPDX-2.3" and
    any((.annotations // [])[]; .spdxElementId == "SPDXRef-DOCUMENT" and
      .annotationType == "OTHER" and (.comment | startswith($namespace + " ")) and
      (.comment | contains("pgDuckdb"))) and
    ([.packages[]? | select(.name == "pg_duckdb" or .name == "duckdb")] | length >= 2)
  ' "${predicate}" >/dev/null
done
