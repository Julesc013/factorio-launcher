// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_discovery.h"
#include "fl_file_io.h"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>

namespace fs = std::filesystem;

namespace {
void set_environment(const char* name, const std::string& value)
{
#ifdef _WIN32
    _putenv_s(name, value.c_str());
#else
    setenv(name, value.c_str(), 1);
#endif
}

void make_fixture(const fs::path& root, const char* id)
{
    fs::create_directories(root / "data" / "base");
    fs::create_directories(root / "bin" / "x64");
    std::ofstream(root / "data" / "base" / "info.json", std::ios::binary) << "{\"version\":\"2.0.77\"}";
    std::ofstream(root / "fixture.manifest.v1.json", std::ios::binary)
        << "{\"fixture_id\":\"" << id << "\",\"source\":\"fixture\",\"ownership\":\"fixture_owned\"}";
    std::ofstream(root / "bin" / "x64" / "factorio.stub", std::ios::binary) << "fixture";
}
}

int main()
{
    const fs::path base = fs::temp_directory_path() / "facman-discovery-delimiter-smoke";
    std::error_code cleanup_error;
    fs::remove_all(base, cleanup_error);
    const fs::path first = base / "first";
    const fs::path second = base / facman::platform::path_from_utf8("unicode-\xE2\x98\x83");
    make_fixture(first, "first");
    make_fixture(second, "second");
#ifdef _WIN32
    _wputenv_s(L"FACMAN_DISCOVERY_ROOTS", (first.wstring() + L";" + second.wstring()).c_str());
#else
    set_environment(
        "FACMAN_DISCOVERY_ROOTS",
        facman::platform::path_to_utf8(first) + ":" + facman::platform::path_to_utf8(second));
#endif
    set_environment("FACMAN_DISCOVERY_DISABLE_DEFAULTS", "1");
    const auto installs = facman::factorio::discovery::scan_install_candidates({});
    fs::remove_all(base, cleanup_error);
    if (installs.size() != 2) {
        std::cerr << "expected two delimiter-separated roots, got " << installs.size() << '\n';
        return 1;
    }
    if (installs[0].verification_status != "structural" || installs[1].verification_status != "structural") return 2;
    return 0;
}
