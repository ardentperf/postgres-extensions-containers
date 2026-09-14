# SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
# SPDX-License-Identifier: Apache-2.0
metadata = {
  build_system             = "pgrx"
  name                     = "pg-graphql"
  sql_name                 = "pg_graphql"
  image_name               = "pg-graphql"
  licenses                 = ["Apache-2.0"]
  shared_preload_libraries = []
  postgresql_parameters    = {}
  extension_control_path   = []
  dynamic_library_path     = []
  ld_library_path          = ["system"]
  bin_path                 = []
  env                      = {}
  auto_update_os_libs      = false
  required_extensions      = []
  create_extension         = true

  // The source release is declared in pg-graphql/Dockerfile. Keep the
  // catalog/image version synchronized with its Renovate tag comment.
  versions = {
    bookworm = {
      "18" = {
        package = "1.6.2"
        sql     = "1.6.2"
      }
    }
    trixie = {
      "18" = {
        package = "1.6.2"
        sql     = "1.6.2"
      }
    }
  }
}
