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

void unset_environment(const char* name)
{
#ifdef _WIN32
    _putenv_s(name, "");
#else
    unsetenv(name);
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

#if defined(__APPLE__)
void make_app_fixture(const fs::path& root, const char* id)
{
    fs::create_directories(root / "Contents" / "Resources" / "data" / "base");
    fs::create_directories(root / "Contents" / "MacOS");
    std::ofstream(root / "Contents" / "Resources" / "data" / "base" / "info.json", std::ios::binary) << "{\"version\":\"2.0.77\"}";
    std::ofstream(root / "fixture.manifest.v1.json", std::ios::binary)
        << "{\"fixture_id\":\"" << id << "\",\"source\":\"app_bundle\",\"ownership\":\"foreign_owned\"}";
    std::ofstream(root / "Contents" / "MacOS" / "factorio.stub", std::ios::binary) << "fixture";
}
#endif
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
    for (const auto& install : installs) {
        if (install.provider_id != "explicit.environment" || install.evidence.empty()) return 3;
    }

#if defined(__linux__)
    const fs::path native_base = fs::temp_directory_path() / "facman-linux-provider-smoke";
    fs::remove_all(native_base, cleanup_error);
    const fs::path home = native_base / "home";
    const fs::path steam = home / ".local" / "share" / "Steam";
    const fs::path library = native_base / "steam-library";
    make_fixture(home / "factorio", "linux-home");
    make_fixture(library / "steamapps" / "common" / "Factorio", "linux-steam");
    fs::create_directories(steam / "steamapps");
    std::ofstream(steam / "steamapps" / "libraryfolders.vdf", std::ios::binary)
        << "\"libraryfolders\" { \"1\" { \"path\" \""
        << facman::platform::path_to_utf8(library) << "\" } }";
    unset_environment("FACMAN_DISCOVERY_ROOTS");
    unset_environment("FACMAN_DISCOVERY_DISABLE_DEFAULTS");
    unset_environment("FACMAN_STANDALONE_ROOTS");
    set_environment("HOME", facman::platform::path_to_utf8(home));
    const auto native_installs = facman::factorio::discovery::scan_install_candidates({});
    fs::remove_all(native_base, cleanup_error);
    if (native_installs.size() != 2) return 4;
    if (native_installs[0].provider_id.rfind("linux.", 0) != 0 ||
        native_installs[1].provider_id.rfind("linux.", 0) != 0) return 5;
#elif defined(__APPLE__)
    const fs::path native_base = fs::temp_directory_path() / "facman-macos-provider-smoke";
    fs::remove_all(native_base, cleanup_error);
    const fs::path home = native_base / "home";
    const fs::path steam = home / "Library" / "Application Support" / "Steam";
    const fs::path library = native_base / "steam-library";
    make_app_fixture(home / "Applications" / "Factorio.app", "macos-home");
    make_app_fixture(library / "steamapps" / "common" / "Factorio" / "Factorio.app", "macos-steam");
    fs::create_directories(steam / "steamapps");
    std::ofstream(steam / "steamapps" / "libraryfolders.vdf", std::ios::binary)
        << "\"libraryfolders\" { \"1\" { \"path\" \""
        << facman::platform::path_to_utf8(library) << "\" } }";
    unset_environment("FACMAN_DISCOVERY_ROOTS");
    unset_environment("FACMAN_DISCOVERY_DISABLE_DEFAULTS");
    unset_environment("FACMAN_STANDALONE_ROOTS");
    set_environment("HOME", facman::platform::path_to_utf8(home));
    const auto native_installs = facman::factorio::discovery::scan_install_candidates({});
    fs::remove_all(native_base, cleanup_error);
    if (native_installs.size() != 2) return 6;
    if (native_installs[0].provider_id.rfind("macos.", 0) != 0 ||
        native_installs[1].provider_id.rfind("macos.", 0) != 0) return 7;
#endif
    return 0;
}
