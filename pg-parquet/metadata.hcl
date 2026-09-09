# SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
# SPDX-License-Identifier: Apache-2.0
metadata = {
  build_system             = "pgrx"
  name                     = "pg-parquet"
  sql_name                 = "pg_parquet"
  image_name               = "pg-parquet"
  licenses                 = ["PostgreSQL"]
  shared_preload_libraries = ["pg_parquet"]
  postgresql_parameters    = {}
  extension_control_path   = []
  dynamic_library_path     = []
  ld_library_path          = ["system"]
  bin_path                 = []
  env                      = {}
  auto_update_os_libs      = false
  required_extensions      = []
  create_extension         = true

  // The source release is declared in pg-parquet/Dockerfile. Keep the
  // catalog/image version synchronized with its Renovate tag comment.
  versions = {
    bookworm = {
      "18" = {
        package = "0.5.1"
        sql     = "0.5.1"
      }
    }
    trixie = {
      "18" = {
        package = "0.5.1"
        sql     = "0.5.1"
      }
    }
  }
}
