// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_self_setup.h"
#include "windows_integration.h"
#include "fl_json.h"
#include "fl_user_paths.h"
#include "version.h"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include <algorithm>
#include <array>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace {

struct Options {
  facman::self_setup::Operation operation =
      facman::self_setup::Operation::verify;
  fs::path package;
  fs::path install_root;
  fs::path state_root;
  fs::path acceptance_root;
  bool apply = false;
  bool json = false;
  bool help = false;
  bool interactive = false;
  bool shell_integration = true;
};

struct MaterializedPackage {
  fs::path path;
  fs::path temporary;

  ~MaterializedPackage() {
    if (!temporary.empty()) {
      std::error_code ignored;
      fs::remove(temporary, ignored);
    }
  }
};

std::uint16_t little_u16(const std::vector<unsigned char> &value,
                         std::size_t offset) {
  return static_cast<std::uint16_t>(value[offset]) |
         (static_cast<std::uint16_t>(value[offset + 1]) << 8);
}

std::uint32_t little_u32(const std::vector<unsigned char> &value,
                         std::size_t offset) {
  return static_cast<std::uint32_t>(value[offset]) |
         (static_cast<std::uint32_t>(value[offset + 1]) << 8) |
         (static_cast<std::uint32_t>(value[offset + 2]) << 16) |
         (static_cast<std::uint32_t>(value[offset + 3]) << 24);
}

bool has_signature(std::ifstream &input, std::uint64_t offset,
                   const std::array<unsigned char, 4> &expected) {
  std::array<unsigned char, 4> observed{};
  input.clear();
  input.seekg(static_cast<std::streamoff>(offset), std::ios::beg);
  input.read(reinterpret_cast<char *>(observed.data()),
             static_cast<std::streamsize>(observed.size()));
  return input && observed == expected;
}

bool materialize_zip_overlay(const fs::path &source,
                             MaterializedPackage &materialized,
                             std::string &problem) {
  std::error_code status;
  const std::uint64_t file_size = fs::file_size(source, status);
  if (status || file_size < 22) {
    problem = "The setup package is missing or too small to contain a ZIP payload";
    return false;
  }
  constexpr std::uint64_t max_tail = 22 + 65535;
  const std::uint64_t tail_size = (std::min)(file_size, max_tail);
  const std::uint64_t tail_start = file_size - tail_size;
  std::ifstream input(source, std::ios::binary);
  if (!input) {
    problem = "The setup package could not be opened";
    return false;
  }
  std::vector<unsigned char> tail(static_cast<std::size_t>(tail_size));
  input.seekg(static_cast<std::streamoff>(tail_start), std::ios::beg);
  input.read(reinterpret_cast<char *>(tail.data()),
             static_cast<std::streamsize>(tail.size()));
  if (!input) {
    problem = "The setup package ZIP footer could not be read";
    return false;
  }
  std::size_t eocd = tail.size();
  for (std::size_t position = tail.size() - 22;; --position) {
    if (tail[position] == 0x50 && tail[position + 1] == 0x4b &&
        tail[position + 2] == 0x05 && tail[position + 3] == 0x06 &&
        position + 22 + little_u16(tail, position + 20) == tail.size()) {
      eocd = position;
      break;
    }
    if (position == 0)
      break;
  }
  if (eocd == tail.size()) {
    problem = "The setup package has no bounded ZIP end record";
    return false;
  }
  const std::uint16_t disk = little_u16(tail, eocd + 4);
  const std::uint16_t central_disk = little_u16(tail, eocd + 6);
  const std::uint16_t disk_entries = little_u16(tail, eocd + 8);
  const std::uint16_t total_entries = little_u16(tail, eocd + 10);
  const std::uint32_t central_size = little_u32(tail, eocd + 12);
  const std::uint32_t central_offset = little_u32(tail, eocd + 16);
  if (disk != 0 || central_disk != 0 || disk_entries != total_entries ||
      total_entries == 0 || total_entries == 0xffff ||
      central_size == 0xffffffff || central_offset == 0xffffffff) {
    problem = "The setup package uses an unsupported split or ZIP64 overlay";
    return false;
  }
  const std::uint64_t absolute_eocd = tail_start + eocd;
  const std::uint64_t relative_span =
      static_cast<std::uint64_t>(central_size) + central_offset;
  if (relative_span > absolute_eocd) {
    problem = "The setup package ZIP offsets are inconsistent";
    return false;
  }
  const std::uint64_t archive_start = absolute_eocd - relative_span;
  if (!has_signature(input, archive_start, {0x50, 0x4b, 0x03, 0x04}) ||
      !has_signature(input, archive_start + central_offset,
                     {0x50, 0x4b, 0x01, 0x02})) {
    problem = "The setup package ZIP overlay signatures are invalid";
    return false;
  }
  if (archive_start == 0) {
    materialized.path = source;
    return true;
  }

  wchar_t temporary_root[MAX_PATH + 1]{};
  wchar_t temporary_file[MAX_PATH + 1]{};
  if (GetTempPathW(MAX_PATH, temporary_root) == 0 ||
      GetTempFileNameW(temporary_root, L"fms", 0, temporary_file) == 0) {
    problem = "Windows could not allocate the temporary setup payload";
    return false;
  }
  materialized.temporary = fs::path(temporary_file);
  std::ofstream output(materialized.temporary,
                       std::ios::binary | std::ios::trunc);
  if (!output) {
    problem = "The temporary setup payload could not be opened";
    return false;
  }
  input.clear();
  input.seekg(static_cast<std::streamoff>(archive_start), std::ios::beg);
  std::vector<char> buffer(1024 * 1024);
  std::uint64_t remaining = file_size - archive_start;
  while (remaining != 0) {
    const std::streamsize count = static_cast<std::streamsize>(
        (std::min)(remaining, static_cast<std::uint64_t>(buffer.size())));
    input.read(buffer.data(), count);
    if (input.gcount() != count) {
      problem = "The setup package ZIP overlay could not be extracted";
      return false;
    }
    output.write(buffer.data(), count);
    if (!output) {
      problem = "The temporary setup payload could not be written";
      return false;
    }
    remaining -= static_cast<std::uint64_t>(count);
  }
  output.close();
  if (!output) {
    problem = "The temporary setup payload could not be committed";
    return false;
  }
  materialized.path = materialized.temporary;
  return true;
}

std::string utf8(const std::wstring &value) {
  if (value.empty())
    return {};
  const int needed = WideCharToMultiByte(
      CP_UTF8, WC_ERR_INVALID_CHARS, value.data(),
      static_cast<int>(value.size()), nullptr, 0, nullptr, nullptr);
  if (needed <= 0)
    return {};
  std::string result(static_cast<std::size_t>(needed), '\0');
  WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value.data(),
                      static_cast<int>(value.size()), result.data(), needed,
                      nullptr, nullptr);
  return result;
}

void usage() {
  std::cout
      << "FacManSetup " FACMAN_VERSION_SEMVER "\n\n"
      << "Usage:\n"
      << "  FacManSetup install   [--package PATH] [--root PATH] [--state-root "
         "PATH] [--acceptance-root PATH] [--yes] [--json]\n"
      << "  FacManSetup verify    [--root PATH] [--state-root PATH] "
         "[--acceptance-root PATH] [--json]\n"
      << "  FacManSetup repair    [--package PATH] [--root PATH] [--state-root "
         "PATH] [--acceptance-root PATH] [--yes] [--json]\n"
      << "  FacManSetup uninstall [--root PATH] [--state-root PATH] "
         "[--acceptance-root PATH] [--yes] [--json]\n\n"
      << "Double-clicking starts the guided per-user install flow. Without "
         "--yes, explicit install, repair, and uninstall commands return a "
         "read-only plan.\n"
      << "The default is a per-user install and never requests elevation. "
         "Use --no-shell-integration only for isolated qualification fixtures.\n";
}

bool parse(int argc, wchar_t **argv, Options &options, std::string &problem) {
  if (argc < 2) {
    options.operation = facman::self_setup::Operation::install;
    options.interactive = true;
    return true;
  }
  const std::wstring operation(argv[1]);
  if (operation == L"install")
    options.operation = facman::self_setup::Operation::install;
  else if (operation == L"verify")
    options.operation = facman::self_setup::Operation::verify;
  else if (operation == L"repair")
    options.operation = facman::self_setup::Operation::repair;
  else if (operation == L"uninstall")
    options.operation = facman::self_setup::Operation::uninstall;
  else if (operation == L"--help" || operation == L"-h" ||
           operation == L"help") {
    options.help = true;
    return true;
  } else if (operation == L"--version") {
    std::cout << FACMAN_VERSION_SEMVER << '\n';
    options.help = true;
    return true;
  } else {
    problem = "unknown operation: " + utf8(operation);
    return false;
  }
  for (int index = 2; index < argc; ++index) {
    const std::wstring argument(argv[index]);
    if (argument == L"--yes")
      options.apply = true;
    else if (argument == L"--json")
      options.json = true;
    else if (argument == L"--no-shell-integration")
      options.shell_integration = false;
    else if (argument == L"--help" || argument == L"-h")
      options.help = true;
    else if (argument == L"--package" || argument == L"--root" ||
             argument == L"--state-root" || argument == L"--acceptance-root") {
      if (++index >= argc) {
        problem = "missing value after " + utf8(argument);
        return false;
      }
      if (argument == L"--package")
        options.package = fs::path(argv[index]);
      else if (argument == L"--root")
        options.install_root = fs::path(argv[index]);
      else if (argument == L"--state-root")
        options.state_root = fs::path(argv[index]);
      else
        options.acceptance_root = fs::path(argv[index]);
    } else {
      problem = "unknown option: " + utf8(argument);
      return false;
    }
  }
  return true;
}

void print_error(const facman::core::Error &value, bool json_mode) {
  if (!json_mode) {
    std::cerr << "FacManSetup: " << value.message << '\n';
    if (!value.detail.empty())
      std::cerr << value.detail << '\n';
    return;
  }
  facman::core::json::ObjectBuilder output;
  output.add_string("schema", "facman.self_setup_cli.v1");
  output.add_string("status", "error");
  facman::core::json::ObjectBuilder error;
  error.add_string("code", value.code);
  error.add_string("message", value.message);
  error.add_string("detail", value.detail);
  output.add_object("error", error);
  std::cout << output.serialize() << '\n';
}

class SetupNativeEffects final : public facman::self_setup::NativeEffects {
public:
  SetupNativeEffects(fs::path install_root, std::string product_version)
      : install_root_(std::move(install_root)) { (void)product_version; }

  facman::self_setup::NativeOwnership inspect(
      facman::self_setup::NativeEffect effect,
      const std::string &product_version) override {
    const auto observed = facman::setup::integration::inspect_windows_effect(
        effect == facman::self_setup::NativeEffect::shortcut
            ? facman::setup::integration::Effect::shortcut
            : facman::setup::integration::Effect::registration,
        install_root_, product_version);
    switch (observed) {
    case facman::setup::integration::Ownership::absent:
      return facman::self_setup::NativeOwnership::absent;
    case facman::setup::integration::Ownership::owned:
      return facman::self_setup::NativeOwnership::owned;
    case facman::setup::integration::Ownership::owned_stale:
      return facman::self_setup::NativeOwnership::owned_stale;
    case facman::setup::integration::Ownership::foreign:
      return facman::self_setup::NativeOwnership::foreign;
    case facman::setup::integration::Ownership::unreadable:
      return facman::self_setup::NativeOwnership::unreadable;
    }
    return facman::self_setup::NativeOwnership::unreadable;
  }

  facman::self_setup::NativeResult apply(
      facman::self_setup::NativeEffect effect,
      facman::self_setup::Operation operation,
      const std::string &product_version) override {
    const auto result = facman::setup::integration::apply_windows_effect(
        effect == facman::self_setup::NativeEffect::shortcut
            ? facman::setup::integration::Effect::shortcut
            : facman::setup::integration::Effect::registration,
        install_root_, product_version, operation == facman::self_setup::Operation::uninstall);
    return {result.ok, result.detail, result.recovery_required};
  }

private:
  fs::path install_root_;
};

} // namespace

int wmain(int argc, wchar_t **argv) {
  SetConsoleOutputCP(CP_UTF8);
  Options options;
  std::string problem;
  if (!parse(argc, argv, options, problem)) {
    std::cerr << "FacManSetup: " << problem << "\n\n";
    usage();
    return 2;
  }
  if (options.help) {
    if (argc < 2 || std::wstring(argv[1]) != L"--version")
      usage();
    return 0;
  }

  auto paths = facman::platform::user_paths();
  if (!paths) {
    print_error(paths.error(), options.json);
    return 3;
  }
  const fs::path local = paths.value().state;
  if (options.install_root.empty()) {
    options.install_root = local / "Programs" / "FacMan";
  }
  if (options.state_root.empty()) {
    options.state_root = local / "FacMan" / "setup";
  }
  if (options.acceptance_root.empty()) {
    options.acceptance_root = local;
  }
  if (options.package.empty() &&
      (options.operation == facman::self_setup::Operation::install ||
       options.operation == facman::self_setup::Operation::repair)) {
    const fs::path executable =
        fs::absolute(fs::path(argv[0])).lexically_normal();
    options.package = executable;
  }

  if (options.interactive) {
    const int answer = MessageBoxW(
        nullptr,
        L"Install FacMan for the current user?\n\nThe installer works offline, "
        L"does not modify Factorio installations, and preserves FacMan workspaces.",
        L"FacMan Setup",
        MB_OKCANCEL | MB_ICONINFORMATION | MB_SETFOREGROUND);
    if (answer != IDOK)
      return 0;
    options.apply = true;
  }

  MaterializedPackage materialized;
  if (options.operation == facman::self_setup::Operation::install ||
      options.operation == facman::self_setup::Operation::repair) {
    if (!materialize_zip_overlay(options.package, materialized, problem)) {
      facman::core::Error package_error{
          "self_setup_payload_invalid",
          "FacMan Setup could not read its embedded payload", problem};
      print_error(package_error, options.json);
      return 4;
    }
    options.package = materialized.path;
  }

  facman::self_setup::Request request;
  request.operation = options.operation;
  request.package = options.package;
  request.install_root = options.install_root;
  request.state_root = options.state_root;
  request.acceptance_root = options.acceptance_root;
  request.product_version = FACMAN_VERSION_SEMVER;
  request.apply = options.apply;
  SetupNativeEffects native_effects(options.install_root, FACMAN_VERSION_SEMVER);
  if (options.shell_integration)
    request.native_effects = &native_effects;
  auto response = facman::self_setup::execute(request);
  if (!response) {
    print_error(response.error(), options.json);
    return 4;
  }
  const std::string integration = options.shell_integration
      ? "coordinated current-user integration"
      : "not_applicable (portable mode)";
  if (options.json) {
    facman::core::json::ObjectBuilder output;
    output.add_string("schema", "facman.self_setup_cli.v1");
    output.add_string("status", "ok");
    output.add_string("operation", response.value().operation);
    output.add_string("phase", response.value().phase);
    auto provider = facman::core::json::parse(response.value().provider_json);
    if (provider)
      output.add_value("provider", provider.value());
    else
      output.add_string("provider_json", response.value().provider_json);
    output.add_string("windows_integration", integration);
    output.add_string("setup_operation_id", response.value().setup_operation_id);
    std::cout << output.serialize() << '\n';
  } else {
    std::cout << "FacManSetup " << response.value().operation << ' '
              << response.value().phase << ":\n"
              << response.value().provider_json << '\n';
    if (!options.apply &&
        options.operation != facman::self_setup::Operation::verify) {
      std::cout << "Review the plan, then repeat with --yes to apply it.\n";
    }
  }
  if (options.interactive) {
    MessageBoxW(nullptr,
                L"FacMan was installed for the current user. Open FacMan from "
                L"the Start Menu, or use facman from the installed generation.",
                L"FacMan Setup", MB_OK | MB_ICONINFORMATION | MB_SETFOREGROUND);
  }
  return 0;
}
