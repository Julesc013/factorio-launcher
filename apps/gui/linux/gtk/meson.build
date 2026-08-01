project('facman_gtk_preview', 'c', version: '0.1.0', default_options: ['c_std=c11', 'warning_level=2'])

gtk = dependency('gtk+-3.0', version: '>=3.22', required: true)

executable('facman-gui-gtk',
  'main.c',
  'command_client.c',
  'generated_rpc_request.c',
  'preview_model.c',
  dependencies: gtk,
  install: true,
  install_dir: get_option('bindir'),
)

install_data(
  'io.github.julesc013.facman.preview.desktop',
  install_dir: join_paths(get_option('datadir'), 'applications'),
)
