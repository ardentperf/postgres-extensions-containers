metadata = {
  name                     = "pg-hint-plan"
  sql_name                 = "pg_hint_plan"
  image_name               = "pg-hint-plan"
  licenses                 = ["PostgreSQL"]
  shared_preload_libraries = ["pg_hint_plan"]
  extension_control_path   = []
  dynamic_library_path     = []
  ld_library_path          = []
  auto_update_os_libs      = false
  required_extensions      = []
  create_extension         = true

  versions = {
    bookworm = {
      // renovate: suite=bookworm-pgdg depName=postgresql-18-pg-hint-plan
      "18" = "1.8.0-3.pgdg12+1"
    }
    trixie = {
      // renovate: suite=trixie-pgdg depName=postgresql-18-pg-hint-plan
      "18" = "1.8.0-3.pgdg13+1"
    }
  }
}
