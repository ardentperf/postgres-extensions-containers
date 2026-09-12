#!/usr/bin/env bash
set -Eeuo pipefail

# Prepare the exact source tree expected by the upstream Makefile. GitHub
# source archives contain the release files but omit the DuckDB submodule and
# the .git/modules metadata that Make uses as a dependency.
source_root="${1:-/build}"
pg_major="${PG_MAJOR:?PG_MAJOR is required}"
ext_version="${EXT_VERSION:?EXT_VERSION is required}"

cd "${source_root}"
tar -xzf /tmp/source.tar.gz --strip-components=1 -C "${source_root}"
test -f .gitmodules

# Capture the pristine image's dynamic library view before development
# packages are installed. The runtime closure helper uses this to separate
# base-provided libraries from files that must be copied into the scratch
# extension image.
ldconfig -p | awk '$NF ~ /^\// {print $NF}' | while IFS= read -r library; do
  readlink -f "${library}"
done | sort -u > /build/pg-duckdb-base-libs.txt

apt-get update

install_if_available() {
  local package
  for package in "$@"; do
    if apt-cache policy "${package}" | awk '
      $1 == "Candidate:" && $2 != "(none)" { found = 1 }
      END { exit found ? 0 : 1 }
    '; then
      printf '%s\n' "${package}"
      return 0
    fi
  done
  echo "none of the candidate packages are available: $*" >&2
  return 1
}

declare -a packages=(
  build-essential
  ca-certificates
  cmake
  curl
  git
  ninja-build
  pkg-config
  python3
  bison
  flex
  libreadline-dev
  zlib1g-dev
  libxml2-dev
  libxslt1-dev
  libssl-dev
  libicu-dev
  libxml2-utils
  xsltproc
  libc++-dev
  libc++abi-dev
  libglib2.0-dev
  liblz4-dev
  libcurl4-openssl-dev
  "postgresql-server-dev-${pg_major}"
)
packages+=("$(install_if_available libtinfo6 libtinfo5 libtinfo-dev)")
packages+=("$(install_if_available libstdc++-dev libstdc++-12-dev libstdc++-13-dev libstdc++-14-dev)")

apt-get install -y --no-install-recommends "${packages[@]}"
rm -rf /var/lib/apt/lists/*

export PATH="/usr/lib/postgresql/${pg_major}/bin:${PATH}"
pg_config_path="$(command -v pg_config || true)"
test -n "${pg_config_path}"
pg_config_version="$(pg_config --version)"
case "${pg_config_version}" in
  "PostgreSQL ${pg_major}".*) ;;
  *)
    echo "pg_config is for the wrong PostgreSQL major: ${pg_config_version}" >&2
    exit 2
    ;;
esac
printf 'PG_CONFIG=%s\nPATH=%s\n' "${pg_config_path}" "${PATH}" > /build/pg-duckdb-build-environment.txt

# Keep the resolved build inputs as evidence.  These packages are inputs to
# compilation; the collector uses the runtime closure separately for shipped
# Debian package claims.
python3 - "${packages[@]}" > /build/pg-duckdb-build-inputs.json <<'PY'
import json
import subprocess
import sys


def command_version(command, *args):
    try:
        output = subprocess.check_output(
            [command, *args], stderr=subprocess.STDOUT, text=True
        )
    except (OSError, subprocess.CalledProcessError) as error:
        return f"unavailable: {error}"
    return output.splitlines()[0] if output.splitlines() else ""


packages = []
for package_name in sys.argv[1:]:
    def field(format_string):
        return subprocess.check_output(
            ["dpkg-query", "-W", f"-f={format_string}", package_name],
            text=True,
        ).strip()

    binary_name = field("${binary:Package}")
    version = field("${Version}")
    architecture = field("${Architecture}")
    packages.append({
        "name": binary_name,
        "version": version,
        "architecture": architecture,
    })

tools = {
    "pg_config": command_version("pg_config", "--version"),
    "cmake": command_version("cmake", "--version"),
    "gcc": command_version("gcc", "--version"),
    "g++": command_version("g++", "--version"),
    "git": command_version("git", "--version"),
    "make": command_version("make", "--version"),
    "ninja": command_version("ninja", "--version"),
    "python3": command_version("python3", "--version"),
}
json.dump(
    {"packages": packages, "tools": tools},
    sys.stdout,
    indent=2,
    sort_keys=True,
)
sys.stdout.write("\n")
PY

# Recreate a real repository and verify every archived tracked file against
# the exact release commit. The gitlink is intentionally excluded from the
# archive comparison because GitHub omits submodule contents.
git init -q
git config user.email pg-duckdb-build@localhost
git config user.name pg-duckdb-build
git remote add origin https://github.com/duckdb/pg_duckdb.git
git fetch --no-tags --depth=1 origin "refs/tags/${ext_version}"
release_commit="$(git rev-parse FETCH_HEAD^{commit})"
# Force-add files that the release's .gitignore excludes from a fresh clone
# (the archive still contains them), then leave our build evidence outside the
# source comparison.
git add -A -f
git reset -- \
  pg-duckdb-base-libs.txt \
  pg-duckdb-build-environment.txt \
  pg-duckdb-build-inputs.json >/dev/null
git diff --cached --exit-code "${release_commit}" -- . \
  ':(exclude)third_party/duckdb' ':(exclude)third_party/duckdb/**'
git update-ref refs/heads/pg-duckdb-release "${release_commit}"
git symbolic-ref HEAD refs/heads/pg-duckdb-release
git reset --mixed "${release_commit}" >/dev/null

git submodule sync --recursive
git submodule update --init --recursive
expected_duckdb="$(git ls-tree "${release_commit}" third_party/duckdb | awk '{print $3}')"
test -n "${expected_duckdb}"
actual_duckdb="$(git -C third_party/duckdb rev-parse HEAD)"
test "${actual_duckdb}" = "${expected_duckdb}"

printf '%s\n' "${release_commit}" > /build/pg-duckdb-release-commit.txt
printf '%s\n' "${expected_duckdb}" > /build/pg-duckdb-duckdb-commit.txt
printf '%s\n' "${ext_version}" > /build/pg-duckdb-source-tag.txt
sha256sum /tmp/source.tar.gz | awk '{print $1}' > /build/pg-duckdb-source-archive-sha256.txt
