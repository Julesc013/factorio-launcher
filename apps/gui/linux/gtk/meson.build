project('facman_gtk_preview', 'c', version: '0.1.0', default_options: ['c_std=c11', 'warning_level=2'])

gtk = dependency('gtk+-3.0', version: '>=3.22', required: true)
glib = dependency('glib-2.0', required: true)

executable('FacMan',
  'main.c',
  'command_client.c',
  'generated_rpc_request.c',
  'generated_live_presentation.c',
  'preview_model.c',
  dependencies: gtk,
  install: true,
  install_dir: get_option('bindir'),
)

live_presentation_test = executable(
  'facman-live-presentation-test',
  'live_presentation_test.c',
  'generated_live_presentation.c',
  dependencies: glib,
)

test(
  'facman-live-presentation-payload-scope',
  live_presentation_test,
  args: [
    join_paths(
      meson.project_source_root(),
      '../../../../tests/fixtures/presentation/live/completed-launch.transport_response.v2.json',
    ),
    join_paths(
      meson.project_source_root(),
      '../../../../tests/fixtures/presentation/live/recovery-history.transport_response.v2.json',
    ),
  ],
)

install_data(
  'io.github.julesc013.facman.preview.desktop',
  install_dir: join_paths(get_option('datadir'), 'applications'),
)

branding_icon_sizes = ['16x16', '24x24', '32x32', '48x48', '64x64', '96x96', '128x128', '192x192', '256x256', '512x512']
foreach branding_icon_size : branding_icon_sizes
  install_data(
    join_paths('icons', 'hicolor', branding_icon_size, 'apps', 'io.github.julesc013.facman.preview.png'),
    install_dir: join_paths(get_option('datadir'), 'icons', 'hicolor', branding_icon_size, 'apps'),
  )
endforeach
