# SPDX-FileCopyrightText: Copyright © contributors to CloudNativePG, established as CloudNativePG a Series of LF Projects, LLC.
# SPDX-License-Identifier: Apache-2.0
metadata = {
  name                     = "pg_hint_plan"
  sql_name                 = "pg_hint_plan"
  image_name               = "pg-hint-plan"
  shared_preload_libraries = ["pg_hint_plan"]
  extension_control_path   = []
  dynamic_library_path     = []
  ld_library_path          = []
  auto_update_os_libs      = false

  versions = {
    trixie = {
        // renovate: suite=trixie-pgdg depName=postgresql-18-pg-hint-plan
        "18" = "1.8.0-3.pgdg13+1"
    }
    bookworm = {
        // renovate: suite=bookworm-pgdg depName=postgresql-18-pg-hint-plan
        "18" = "1.8.0-3.pgdg12+1"
    }
  }
}
