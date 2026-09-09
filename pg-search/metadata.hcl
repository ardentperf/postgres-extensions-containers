# SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
# SPDX-License-Identifier: Apache-2.0
metadata = {
  build_system             = "pgrx"
  name                     = "pg-search"
  sql_name                 = "pg_search"
  image_name               = "pg-search"
  licenses                 = ["AGPL-3.0"]
  shared_preload_libraries = ["pg_search"]
  postgresql_parameters    = {}
  extension_control_path   = []
  dynamic_library_path     = []
  ld_library_path          = ["system"]
  bin_path                 = []
  env                      = {}
  auto_update_os_libs      = false
  // pgvector is provided by the selected CNPG extension catalog. It is not a
  // local target and must not acquire a stub directory in this repository.
  required_extensions      = ["pgvector"]
  create_extension         = true

  // The source release is declared in pg-search/Dockerfile. Keep the
  // catalog/image version synchronized with its Renovate tag comment.
  versions = {
    bookworm = {
      "18" = {
        package = "0.25.6"
        sql     = "0.25.6"
      }
    }
    trixie = {
      "18" = {
        package = "0.25.6"
        sql     = "0.25.6"
      }
    }
  }
}
