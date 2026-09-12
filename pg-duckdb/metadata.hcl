# SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
# SPDX-License-Identifier: Apache-2.0
metadata = {
  build_system             = "pg-duckdb"
  name                     = "pg-duckdb"
  sql_name                 = "pg_duckdb"
  image_name               = "pg-duckdb"
  licenses                 = ["MIT"]
  shared_preload_libraries = ["pg_duckdb"]
  postgresql_parameters    = {}
  extension_control_path   = []
  dynamic_library_path     = []
  ld_library_path          = ["system"]
  bin_path                 = []
  env                      = {}
  auto_update_os_libs      = false
  required_extensions      = []
  create_extension         = true

  versions = {
    trixie = {
      "18" = {
        # renovate: datasource=github-tags depName=duckdb/pg_duckdb versioning=semver
        package = "v1.1.1"
        // SQL version cannot be updated by Renovate; if it changes, manually
        // update pg-duckdb/README.md, pg-duckdb/metadata.hcl, and renovate.json.
        sql = "1.1.0"
      }
    }
    bookworm = {
      "18" = {
        # renovate: datasource=github-tags depName=duckdb/pg_duckdb versioning=semver
        package = "v1.1.1"
        // SQL version cannot be updated by Renovate; if it changes, manually
        // update pg-duckdb/README.md, pg-duckdb/metadata.hcl, and renovate.json.
        sql = "1.1.0"
      }
    }
  }
}
