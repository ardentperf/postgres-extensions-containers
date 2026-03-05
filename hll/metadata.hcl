metadata = {
  name                     = "hll"
  sql_name                 = "hll"
  image_name               = "hll"
  licenses                 = ["Apache-2.0"]
  shared_preload_libraries = []
  extension_control_path   = []
  dynamic_library_path     = []
  ld_library_path          = []
  auto_update_os_libs      = false
  required_extensions      = []
  create_extension         = true

  versions = {
    bookworm = {
      // renovate: suite=bookworm-pgdg depName=postgresql-18-hll
      "18" = "2.19-2.pgdg12+2"
    }
    trixie = {
      // renovate: suite=trixie-pgdg depName=postgresql-18-hll
      "18" = "2.19-2.pgdg13+2"
    }
  }
}
