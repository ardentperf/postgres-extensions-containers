metadata = {
  name                     = "pgnodemx"
  sql_name                 = "pgnodemx"
  image_name               = "pgnodemx"
  licenses                 = ["PostgreSQL", "Apache-2.0"]
  shared_preload_libraries = []
  extension_control_path   = []
  dynamic_library_path     = []
  ld_library_path          = []
  auto_update_os_libs      = false
  required_extensions      = []
  # package version (2.0.1) differs from extension default_version (2.0) with no upgrade path
  create_extension         = false

  versions = {
    bookworm = {
      // renovate: suite=bookworm-pgdg depName=postgresql-18-pgnodemx
      "18" = "2.0.1-1.pgdg12+1"
    }
    trixie = {
      // renovate: suite=trixie-pgdg depName=postgresql-18-pgnodemx
      "18" = "2.0.1-1.pgdg13+1"
    }
  }
}
