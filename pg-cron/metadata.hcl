metadata = {
  name                     = "pg-cron"
  sql_name                 = "pg_cron"
  image_name               = "pg-cron"
  licenses                 = ["PostgreSQL"]
  shared_preload_libraries = ["pg_cron"]
  extension_control_path   = []
  dynamic_library_path     = []
  ld_library_path          = []
  auto_update_os_libs      = false
  required_extensions      = []
  # pg_cron can only be installed in the postgres database
  create_extension         = false

  versions = {
    bookworm = {
      // renovate: suite=bookworm-pgdg depName=postgresql-18-cron
      "18" = "1.6.7-2.pgdg12+1"
    }
    trixie = {
      // renovate: suite=trixie-pgdg depName=postgresql-18-cron
      "18" = "1.6.7-2.pgdg13+1"
    }
  }
}
