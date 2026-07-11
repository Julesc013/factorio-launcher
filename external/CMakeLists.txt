add_library(miniz_static STATIC miniz/miniz.c)
target_include_directories(miniz_static PUBLIC miniz)

add_library(picojson_headers INTERFACE)
target_include_directories(picojson_headers SYSTEM INTERFACE picojson)
