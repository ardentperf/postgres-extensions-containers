# SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
# SPDX-License-Identifier: Apache-2.0
metadata = {
  build_system             = "pgrx"
  name                     = "pg-session-jwt"
  sql_name                 = "pg_session_jwt"
  image_name               = "pg-session-jwt"
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

  // The source release is declared in pg-session-jwt/Dockerfile. Keep the
  // catalog/image version synchronized with its Renovate tag comment.
  versions = {
    bookworm = {
      "18" = {
        package = "0.5.0"
        sql     = "0.5.0"
      }
    }
    trixie = {
      "18" = {
        package = "0.5.0"
        sql     = "0.5.0"
      }
    }
  }
}
