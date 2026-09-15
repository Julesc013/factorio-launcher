// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_self_setup.h"
#include "windows_integration.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_user_paths.h"
#include "version.h"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cctype>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <initializer_list>
#include <iostream>
#include <optional>
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
  bool package_explicit = false;
  bool install_root_explicit = false;
  bool state_root_explicit = false;
  bool acceptance_root_explicit = false;
  unsigned package_count = 0;
  unsigned install_root_count = 0;
  unsigned state_root_count = 0;
  unsigned acceptance_root_count = 0;
  unsigned yes_count = 0;
  unsigned json_count = 0;
  unsigned noninteractive_count = 0;
  unsigned shell_integration_count = 0;
  unsigned no_shell_integration_count = 0;
  std::optional<facman::self_setup::DurableBoundary>
      qualification_interrupt_after;
  fs::path qualification_interrupt_permit;
  bool qualification_interrupt_permit_explicit = false;
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

class SetupPackageMaterializer final
    : public facman::self_setup::PackageMaterializer {
public:
  facman::core::Result<fs::path> materialize(
      const fs::path &source) override;

private:
  MaterializedPackage materialized_;
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

facman::core::Result<fs::path> SetupPackageMaterializer::materialize(
    const fs::path &source) {
  std::error_code status;
  if (!fs::is_regular_file(source, status) || status)
    return facman::core::Result<fs::path>::failure({
        "self_setup_package_missing",
        "The setup payload is not a regular file",
        facman::platform::path_to_utf8(source)});
  std::string problem;
  if (!materialize_zip_overlay(source, materialized_, problem))
    return facman::core::Result<fs::path>::failure({
        "self_setup_payload_invalid",
        "FacMan Setup could not read its embedded payload", problem});
  return facman::core::Result<fs::path>::success(materialized_.path);
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

std::optional<fs::path> current_executable_path(std::string &problem) {
  std::vector<wchar_t> buffer(32768U, L'\0');
  const DWORD length = GetModuleFileNameW(
      nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
  if (length == 0U || length >= buffer.size()) {
    problem = "Windows could not identify the running maintenance launcher";
    return std::nullopt;
  }
  std::error_code status;
  const fs::path result = fs::absolute(
      fs::path(std::wstring(buffer.data(), length)), status).lexically_normal();
  if (status || result.empty()) {
    problem = "The running maintenance launcher path is invalid";
    return std::nullopt;
  }
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
      << "Qualification interruption requires both "
         "--qualification-interrupt-after provider_plan_reviewed|files_applied|shortcut_applied and "
         "--qualification-interrupt-permit PATH, with explicit noninteractive "
         "installed-operation inputs.\n\n"
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
    if (argument == L"--yes") {
      ++options.yes_count;
      options.apply = true;
    } else if (argument == L"--json") {
      ++options.json_count;
      options.json = true;
    } else if (argument == L"--noninteractive") {
      ++options.noninteractive_count;
      options.interactive = false;
    } else if (argument == L"--shell-integration") {
      ++options.shell_integration_count;
      options.shell_integration = true;
    } else if (argument == L"--no-shell-integration") {
      ++options.no_shell_integration_count;
      options.shell_integration = false;
    } else if (argument == L"--help" || argument == L"-h")
      options.help = true;
    else if (argument == L"--package" || argument == L"--root" ||
             argument == L"--state-root" || argument == L"--acceptance-root") {
      if (++index >= argc) {
        problem = "missing value after " + utf8(argument);
        return false;
      }
      if (argument == L"--package") {
        options.package = fs::path(argv[index]);
        options.package_explicit = true;
        ++options.package_count;
      } else if (argument == L"--root") {
        options.install_root = fs::path(argv[index]);
        options.install_root_explicit = true;
        ++options.install_root_count;
      } else if (argument == L"--state-root") {
        options.state_root = fs::path(argv[index]);
        options.state_root_explicit = true;
        ++options.state_root_count;
      } else {
        options.acceptance_root = fs::path(argv[index]);
        options.acceptance_root_explicit = true;
        ++options.acceptance_root_count;
      }
    } else if (argument == L"--qualification-interrupt-after" ||
               argument == L"--qualification-interrupt-permit") {
      if (++index >= argc) {
        problem = "missing value after " + utf8(argument);
        return false;
      }
      if (argument == L"--qualification-interrupt-after") {
        if (options.qualification_interrupt_after.has_value()) {
          problem = "duplicate option: --qualification-interrupt-after";
          return false;
        }
        const std::wstring value(argv[index]);
        if (value == L"provider_plan_reviewed")
          options.qualification_interrupt_after = facman::self_setup::DurableBoundary::provider_plan_reviewed;
        else if (value == L"files_applied")
          options.qualification_interrupt_after = facman::self_setup::DurableBoundary::files_applied;
        else if (value == L"shortcut_applied")
          options.qualification_interrupt_after = facman::self_setup::DurableBoundary::shortcut_applied;
        else {
          problem = "invalid qualification interruption boundary: " + utf8(value);
          return false;
        }
      } else {
        if (options.qualification_interrupt_permit_explicit) {
          problem = "duplicate option: --qualification-interrupt-permit";
          return false;
        }
        options.qualification_interrupt_permit = fs::path(argv[index]);
        options.qualification_interrupt_permit_explicit = true;
      }
    } else {
      problem = "unknown option: " + utf8(argument);
      return false;
    }
  }
  return true;
}

constexpr std::uint64_t kQualificationPermitMaximumBytes = 4096U;
constexpr std::uint64_t kQualificationPermitMaximumLifetimeSeconds = 120U;
constexpr std::uint64_t kQualificationPermitMaximumFutureSkewSeconds = 5U;

std::string operation_text(facman::self_setup::Operation operation) {
  switch (operation) {
  case facman::self_setup::Operation::install: return "install";
  case facman::self_setup::Operation::repair: return "repair";
  case facman::self_setup::Operation::uninstall: return "uninstall";
  case facman::self_setup::Operation::verify: return "verify";
  }
  return "verify";
}

std::string boundary_text(facman::self_setup::DurableBoundary boundary) {
  switch (boundary) {
  case facman::self_setup::DurableBoundary::provider_plan_reviewed:
    return "provider_plan_reviewed";
  case facman::self_setup::DurableBoundary::files_applied:
    return "files_applied";
  case facman::self_setup::DurableBoundary::shortcut_applied:
    return "shortcut_applied";
  }
  return "files_applied";
}

bool exact_keys(const facman::core::json::Value &object,
                std::initializer_list<const char *> expected) {
  if (!object.is_object() || object.object_keys().size() != expected.size())
    return false;
  for (const char *key : expected) {
    if (object.find(key) == nullptr)
      return false;
  }
  return true;
}

bool string_member(const facman::core::json::Value &object, const char *key,
                   std::string &value) {
  const auto *member = object.find(key);
  if (member == nullptr)
    return false;
  auto decoded = member->string_value();
  if (!decoded)
    return false;
  value = decoded.take_value();
  return true;
}

bool unsigned_member(const facman::core::json::Value &object, const char *key,
                     std::uint64_t &value) {
  const auto *member = object.find(key);
  if (member == nullptr)
    return false;
  auto decoded = member->unsigned_integer_value();
  if (!decoded)
    return false;
  value = decoded.take_value();
  return true;
}

bool lowercase_hex_64(const std::string &value) {
  return value.size() == 64U && std::all_of(value.begin(), value.end(),
      [](unsigned char byte) { return (byte >= '0' && byte <= '9') ||
          (byte >= 'a' && byte <= 'f'); });
}

bool normalized_absolute_path(const fs::path &input, fs::path &normalized,
                              std::string &problem, const char *field) {
  if (input.empty() || !input.is_absolute()) {
    problem = std::string(field) + " must be an explicit absolute path";
    return false;
  }
  normalized = input.lexically_normal();
  if (normalized.empty() || !normalized.is_absolute()) {
    problem = std::string(field) + " could not be normalized as an absolute path";
    return false;
  }
  return true;
}

bool validate_qualification_descendant(
    const facman::platform::StableDirectoryObject &acceptance,
    const fs::path &candidate, bool allow_absent_leaf,
    std::string &problem, const char *field) {
  std::string detail;
  if (facman::base::path_crosses_link_or_reparse_point(candidate, detail)) {
    problem = std::string(field) + " crosses a link or reparse point: " + detail;
    return false;
  }
  const auto validated = acceptance.validate_descendant(candidate, allow_absent_leaf);
  if (!validated.ok()) {
    problem = std::string(field) + " is not a safe descendant of acceptance root: " +
        validated.detail;
    return false;
  }
  return true;
}

bool validate_qualification_direct_child(const fs::path &root,
                                         const fs::path &candidate,
                                         std::string &problem,
                                         const char *field) {
  if (candidate.filename().empty() || candidate.filename() == "." ||
      candidate.filename() == ".." || candidate.parent_path() != root) {
    problem = std::string(field) + " must be a direct child of acceptance root";
    return false;
  }
  return true;
}

std::uint64_t unix_seconds() {
  const auto seconds = std::chrono::duration_cast<std::chrono::seconds>(
      std::chrono::system_clock::now().time_since_epoch()).count();
  return seconds < 0 ? 0U : static_cast<std::uint64_t>(seconds);
}

struct QualificationInterrupt {
  facman::self_setup::DurableBoundary boundary;
  fs::path consumed_permit;
  facman::self_setup::QualificationClaims claims;
};

bool consume_qualification_interrupt(Options &options,
                                      std::optional<QualificationInterrupt> &interrupt,
                                      std::string &problem) {
  const bool after_supplied = options.qualification_interrupt_after.has_value();
  const bool permit_supplied = options.qualification_interrupt_permit_explicit;
  if (!after_supplied && !permit_supplied)
    return true;
  if (!after_supplied || !permit_supplied) {
    problem = "qualification interruption requires both --qualification-interrupt-after and --qualification-interrupt-permit";
    return false;
  }
  if (options.operation == facman::self_setup::Operation::verify ||
      !options.install_root_explicit || !options.state_root_explicit ||
      !options.acceptance_root_explicit || options.install_root_count != 1U ||
      options.state_root_count != 1U || options.acceptance_root_count != 1U ||
      options.package_count > 1U ||
      options.yes_count != 1U ||
      options.json_count != 1U || options.noninteractive_count != 1U ||
      options.shell_integration_count != 1U || !options.shell_integration ||
      options.no_shell_integration_count != 0U ||
      options.interactive ||
      ((options.operation == facman::self_setup::Operation::install ||
        options.operation == facman::self_setup::Operation::repair) &&
       (!options.package_explicit || options.package_count != 1U)) ||
      (options.operation == facman::self_setup::Operation::uninstall &&
       options.package_count != 0U)) {
    problem = "qualification interruption requires one explicit noninteractive installed operation with --root, --state-root, --acceptance-root, --yes, --json, and --shell-integration";
    return false;
  }

  fs::path install_root;
  fs::path state_root;
  fs::path acceptance_root;
  fs::path permit_path;
  if (!normalized_absolute_path(options.install_root, install_root, problem, "install root") ||
      !normalized_absolute_path(options.state_root, state_root, problem, "state root") ||
      !normalized_absolute_path(options.acceptance_root, acceptance_root, problem, "acceptance root") ||
      !normalized_absolute_path(options.qualification_interrupt_permit, permit_path,
                                problem, "qualification interrupt permit"))
    return false;

  std::string link_detail;
  if (facman::base::path_crosses_link_or_reparse_point(acceptance_root, link_detail)) {
    problem = "acceptance root crosses a link or reparse point: " + link_detail;
    return false;
  }
  facman::platform::StableDirectoryObject acceptance;
  const auto acceptance_opened = acceptance.open_no_follow(acceptance_root);
  if (!acceptance_opened.ok()) {
    problem = "acceptance root must be an existing plain no-follow directory: " +
        acceptance_opened.detail;
    return false;
  }
  if (!validate_qualification_descendant(acceptance, install_root, true, problem,
                                          "install root") ||
      !validate_qualification_descendant(acceptance, state_root, true, problem,
                                         "state root") ||
      !validate_qualification_descendant(acceptance, permit_path, false, problem,
                                         "qualification interrupt permit") ||
      !validate_qualification_direct_child(acceptance_root, permit_path, problem,
                                           "qualification interrupt permit"))
    return false;

  facman::platform::StableInputFile permit;
  const auto permit_opened = permit.open_no_follow(permit_path);
  if (!permit_opened.ok() || permit.size() > kQualificationPermitMaximumBytes) {
    problem = "qualification interrupt permit must be a bounded regular no-follow file";
    return false;
  }
  std::string permit_bytes(static_cast<std::size_t>(permit.size()), '\0');
  if ((permit.size() != 0U &&
       permit.read_at(0, permit_bytes.data(), permit_bytes.size()) != permit_bytes.size()) ||
      !permit.revalidate().ok()) {
    problem = "qualification interrupt permit changed while being read";
    return false;
  }
  facman::core::json::Limits permit_limits;
  permit_limits.maximum_bytes = kQualificationPermitMaximumBytes;
  permit_limits.maximum_depth = 8U;
  permit_limits.maximum_nodes = 32U;
  permit_limits.maximum_string_bytes = kQualificationPermitMaximumBytes;
  auto document = facman::core::json::parse(permit_bytes, permit_limits);
  if (!document || !exact_keys(document.value(),
      {"schema", "nonce", "operation", "boundary", "product_version",
       "install_root", "state_root", "acceptance_root", "issued_at_unix_seconds",
       "expires_at_unix_seconds"})) {
    problem = "qualification interrupt permit has an invalid exact JSON schema";
    return false;
  }
  std::string schema;
  std::string nonce;
  std::string operation;
  std::string boundary;
  std::string product_version;
  std::string permit_install_root;
  std::string permit_state_root;
  std::string permit_acceptance_root;
  std::uint64_t issued_at = 0U;
  std::uint64_t expires_at = 0U;
  if (!string_member(document.value(), "schema", schema) ||
      !string_member(document.value(), "nonce", nonce) ||
      !string_member(document.value(), "operation", operation) ||
      !string_member(document.value(), "boundary", boundary) ||
      !string_member(document.value(), "product_version", product_version) ||
      !string_member(document.value(), "install_root", permit_install_root) ||
      !string_member(document.value(), "state_root", permit_state_root) ||
      !string_member(document.value(), "acceptance_root", permit_acceptance_root) ||
      !unsigned_member(document.value(), "issued_at_unix_seconds", issued_at) ||
      !unsigned_member(document.value(), "expires_at_unix_seconds", expires_at) ||
      schema != "facman.self_setup_qualification_interrupt_permit.v1" ||
      !lowercase_hex_64(nonce)) {
    problem = "qualification interrupt permit has invalid claims";
    return false;
  }
  const std::uint64_t now = unix_seconds();
  if (expires_at <= issued_at ||
      expires_at - issued_at > kQualificationPermitMaximumLifetimeSeconds ||
      (issued_at > now && issued_at - now > kQualificationPermitMaximumFutureSkewSeconds) ||
      now >= expires_at) {
    problem = "qualification interrupt permit is outside its bounded time window";
    return false;
  }
  if (operation != operation_text(options.operation) ||
      boundary != boundary_text(*options.qualification_interrupt_after) ||
      product_version != FACMAN_VERSION_SEMVER ||
      permit_install_root != facman::platform::path_to_utf8(install_root) ||
      permit_state_root != facman::platform::path_to_utf8(state_root) ||
      permit_acceptance_root != facman::platform::path_to_utf8(acceptance_root)) {
    problem = "qualification interrupt permit does not bind this exact operation";
    return false;
  }

  const fs::path consumed_path = permit_path.parent_path() /
      facman::platform::path_from_utf8(nonce + ".consumed.v1.json");
  if (!validate_qualification_descendant(acceptance, consumed_path, true, problem,
                                         "qualification consumed permit") ||
      !validate_qualification_direct_child(acceptance_root, consumed_path, problem,
                                           "qualification consumed permit") ||
      !permit.revalidate().ok()) {
    if (problem.empty())
      problem = "qualification interrupt permit changed before consumption";
    return false;
  }
  facman::platform::PathIdentity consumed_before;
  const auto inspected = facman::platform::inspect_path_no_follow(consumed_path,
                                                                    consumed_before);
  if (!inspected.ok() || consumed_before.exists) {
    problem = "qualification consumed permit already exists or cannot be inspected";
    return false;
  }
  const auto committed = facman::platform::commit_no_replace(permit_path, consumed_path);
  if (!committed.ok()) {
    problem = "qualification interrupt permit could not be consumed without replacement: " +
        committed.detail;
    return false;
  }
  facman::platform::StableInputFile consumed;
  const auto consumed_opened = consumed.open_no_follow(consumed_path);
  if (!consumed_opened.ok() || !consumed.identity().same_object(permit.identity()) ||
      !consumed.revalidate().ok()) {
    problem = "qualification consumed permit identity could not be proven";
    return false;
  }
  options.install_root = install_root;
  options.state_root = state_root;
  options.acceptance_root = acceptance_root;
  facman::self_setup::QualificationClaims claims;
  claims.operation = options.operation;
  claims.install_root = install_root;
  claims.state_root = state_root;
  claims.acceptance_root = acceptance_root;
  claims.product_version = FACMAN_VERSION_SEMVER;
  claims.installed_mode = true;
  claims.boundary = *options.qualification_interrupt_after;
  interrupt = QualificationInterrupt{*options.qualification_interrupt_after,
                                       consumed_path, std::move(claims)};
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

constexpr std::uint64_t kMaximumRepairSourceBytes =
    16ULL * 1024ULL * 1024ULL * 1024ULL;
constexpr std::uint64_t kMaximumRepairLauncherBytes =
    256ULL * 1024ULL * 1024ULL;
constexpr char kRepairSourceMarker[] = "facman-repair-sources-v1\n";

std::optional<std::string> digest_stable_input(
    facman::platform::StableInputFile &file) {
  facman::base::Sha256Hasher hash;
  std::vector<unsigned char> buffer(1024U * 1024U);
  for (std::uint64_t offset = 0; offset < file.size();) {
    const std::size_t requested = static_cast<std::size_t>((std::min)(
        static_cast<std::uint64_t>(buffer.size()), file.size() - offset));
    if (file.read_at(offset, buffer.data(), requested) != requested)
      return std::nullopt;
    hash.update(buffer.data(), requested);
    offset += requested;
  }
  if (!file.revalidate().ok()) return std::nullopt;
  return hash.finish();
}

std::optional<std::string> digest_stable_file(
    const fs::path &path, std::uint64_t maximum_bytes) {
  facman::platform::StableInputFile file;
  const auto opened = file.open_no_follow(path);
  if (!opened.ok() || !file.identity().regular_file ||
      file.identity().link_count != 1U || file.size() == 0U ||
      file.size() > maximum_bytes)
    return std::nullopt;
  return digest_stable_input(file);
}

std::optional<std::string> read_stable_text(
    const fs::path &path, std::uint64_t maximum_bytes) {
  facman::platform::StableInputFile file;
  const auto opened = file.open_no_follow(path);
  if (!opened.ok() || !file.identity().regular_file ||
      file.identity().link_count != 1U || file.size() == 0U ||
      file.size() > maximum_bytes)
    return std::nullopt;
  std::string result(static_cast<std::size_t>(file.size()), '\0');
  if (file.read_at(0, result.data(), result.size()) != result.size() ||
      !file.revalidate().ok()) return std::nullopt;
  return result;
}

std::optional<std::string> read_stable_input(
    facman::platform::StableInputFile &file, std::uint64_t maximum_bytes) {
  if (!file.open() || !file.identity().regular_file ||
      file.identity().link_count != 1U || file.size() == 0U ||
      file.size() > maximum_bytes)
    return std::nullopt;
  std::string result(static_cast<std::size_t>(file.size()), '\0');
  if (file.read_at(0, result.data(), result.size()) != result.size() ||
      !file.revalidate().ok()) return std::nullopt;
  return result;
}

fs::path repair_launcher_path(const fs::path &repair_source) {
  return repair_source.parent_path() /
      fs::path(repair_source.stem().wstring() + L".FacManSetup.exe");
}

fs::path repair_receipt_path(const fs::path &repair_source) {
  return repair_source.parent_path() /
      fs::path(repair_source.stem().wstring() + L".maintenance.v1");
}

std::string repair_receipt_bytes(const std::string &source_sha256,
                                 const std::string &launcher_sha256) {
  return "facman-repair-source-receipt-v1\nsource_sha256=" + source_sha256 +
      "\nlauncher_sha256=" + launcher_sha256 + "\n";
}

struct PinnedRepairSource {
  facman::platform::StableDirectoryObject state;
  facman::platform::StableDirectoryObject cache;
  facman::platform::StableInputFile marker;
  facman::platform::StableInputFile receipt;
  facman::platform::StableInputFile source;
  facman::platform::StableInputFile launcher;
  bool source_pinned = false;

  bool revalidate(std::string &detail) const {
    const std::pair<const char *, const facman::platform::StableInputFile *>
        files[] = {{"cache marker", &marker}, {"maintenance receipt", &receipt},
                   {"maintenance launcher", &launcher}};
    for (const auto &[label, file] : files) {
      const auto status = file->revalidate_path();
      if (!status.ok()) {
        detail = std::string(label) + " pathname no longer binds its pinned object: " +
            status.detail;
        return false;
      }
    }
    if (source_pinned) {
      const auto status = source.revalidate_path();
      if (!status.ok()) {
        detail = "repair source pathname no longer binds its pinned object: " +
            status.detail;
        return false;
      }
    }
    const auto cache_status = cache.revalidate();
    const auto state_status = state.revalidate();
    if (!cache_status.ok() || !state_status.ok()) {
      detail = "repair source cache directory identity changed while pinned";
      return false;
    }
    detail.clear();
    return true;
  }
};

bool write_text_new_pinned(const fs::path &path, const std::string &text,
                           std::string &detail) {
  const fs::path temporary = path.parent_path() /
      facman::platform::path_from_utf8("." +
          facman::platform::path_to_utf8(path.filename()) + ".pending." +
          std::to_string(GetCurrentProcessId()) + "." +
          std::to_string(GetTickCount64()) + ".tmp");
  facman::platform::DurableOutputFile output;
  const auto created = output.create_exclusive(temporary, text.size());
  if (!created.ok()) {
    detail = "temporary could not be created: " + created.detail;
    return false;
  }
  if (output.write_at(0, text.data(), text.size()) != text.size()) {
    detail = "temporary could not be written";
    const auto discarded = output.discard_open();
    if (!discarded.ok()) detail += "; cleanup: " + discarded.detail;
    return false;
  }
  const auto published = output.publish_no_replace(path);
  if (!published.ok()) {
    detail = "temporary could not be published: " + published.detail;
    const auto discarded = output.discard_open();
    if (!discarded.ok()) detail += "; cleanup: " + discarded.detail;
    return false;
  }
  detail.clear();
  return true;
}

facman::self_setup::RetainedSourceResult validate_maintenance_identity(
    const facman::self_setup::NativeContext &context,
    const std::string &expected_sha256,
    bool require_source,
    PinnedRepairSource *retained_pins = nullptr) {
  const fs::path source = context.repair_source;
  if (!lowercase_hex_64(expected_sha256) ||
      source.filename() !=
          facman::platform::path_from_utf8(expected_sha256 + ".zip"))
    return {false, {}, "repair source path does not bind the installed source", true};
  const fs::path directory = source.parent_path();
  const fs::path state_root = directory.parent_path();
  const fs::path launcher = repair_launcher_path(source);
  const fs::path receipt = repair_receipt_path(source);
  const fs::path marker = directory / ".facman-repair-sources.v1";
  if (state_root.lexically_normal() != context.state_root.lexically_normal())
    return {false, {}, "repair source cache does not bind the setup-state root", true};
  PinnedRepairSource local;
  PinnedRepairSource &pins = retained_pins == nullptr ? local : *retained_pins;
  if (!pins.state.open_no_follow(state_root).ok() ||
      !pins.cache.open_no_follow(directory).ok() ||
      !pins.state.validate_descendant(source, !require_source).ok() ||
      !pins.state.validate_descendant(launcher, false).ok() ||
      !pins.state.validate_descendant(receipt, false).ok() ||
      !pins.state.validate_descendant(marker, false).ok())
    return {false, {}, "repair source cache identity is unsafe or incomplete", true};
  if (!pins.marker.open_no_follow_pinned(marker).ok() ||
      !pins.receipt.open_no_follow_pinned(receipt).ok() ||
      (require_source && !pins.source.open_no_follow_pinned(source).ok()) ||
      !pins.launcher.open_no_follow_pinned(launcher).ok())
    return {false, {}, "repair source cache files could not be pinned", true};
  pins.source_pinned = require_source;
  if ((require_source && (!pins.source.identity().regular_file ||
       pins.source.identity().link_count != 1U || pins.source.size() == 0U ||
       pins.source.size() > kMaximumRepairSourceBytes)) ||
      !pins.launcher.identity().regular_file ||
      pins.launcher.identity().link_count != 1U || pins.launcher.size() == 0U ||
      pins.launcher.size() > kMaximumRepairLauncherBytes)
    return {false, {}, "repair source or launcher has unsafe file identity", true};
  const auto marker_bytes = read_stable_input(pins.marker, 128U);
  const auto receipt_content = read_stable_input(pins.receipt, 512U);
  const std::string prefix =
      "facman-repair-source-receipt-v1\nsource_sha256=" + expected_sha256 +
      "\nlauncher_sha256=";
  if (!marker_bytes.has_value() || *marker_bytes != kRepairSourceMarker ||
      !receipt_content.has_value() ||
      receipt_content->size() != prefix.size() + 65U ||
      receipt_content->compare(0, prefix.size(), prefix) != 0 ||
      receipt_content->back() != '\n')
    return {false, {}, "repair source receipt is absent, changed, or incompatible", true};
  const std::string launcher_sha256 = receipt_content->substr(prefix.size(), 64U);
  if (!lowercase_hex_64(launcher_sha256) ||
      *receipt_content != repair_receipt_bytes(expected_sha256, launcher_sha256))
    return {false, {}, "repair source receipt has an invalid launcher identity", true};
  const auto source_digest = require_source
      ? digest_stable_input(pins.source) : std::optional<std::string>{};
  const auto launcher_digest = digest_stable_input(pins.launcher);
  std::string pin_detail;
  if ((require_source && (!source_digest.has_value() ||
                          *source_digest != expected_sha256)) ||
      !launcher_digest.has_value() || *launcher_digest != launcher_sha256 ||
      !pins.revalidate(pin_detail))
    return {false, {}, "repair source or maintenance launcher changed after retention", true};
  return {true, require_source ? source : launcher,
          require_source
              ? "retained repair source and launcher identity verified"
              : "retained maintenance launcher identity verified"};
}

facman::self_setup::RetainedSourceResult validate_repair_source(
    const facman::self_setup::NativeContext &context,
    const std::string &expected_sha256,
    PinnedRepairSource *retained_pins = nullptr) {
  return validate_maintenance_identity(
      context, expected_sha256, true, retained_pins);
}

facman::self_setup::RetainedSourceResult validate_maintenance_launcher(
    const facman::self_setup::NativeContext &context,
    const std::string &expected_sha256,
    PinnedRepairSource *retained_pins = nullptr) {
  return validate_maintenance_identity(
      context, expected_sha256, false, retained_pins);
}

facman::self_setup::RetainedSourceResult retain_repair_source(
    const facman::self_setup::NativeContext &context,
    const fs::path &package, const fs::path &maintenance_launcher,
    const std::string &expected_sha256) {
  const fs::path destination = context.repair_source;
  if (expected_sha256.size() != 64U || destination.filename() !=
          facman::platform::path_from_utf8(expected_sha256 + ".zip"))
    return {false, {}, "repair source destination is not digest-bound", true};

  const fs::path directory = destination.parent_path();
  const fs::path state_root = directory.parent_path();
  std::error_code status;
  if (!fs::exists(state_root, status)) {
    if (status || !fs::create_directory(state_root, status) || status)
      return {false, {}, "setup-state root for repair retention could not be created"};
  } else if (status) {
    return {false, {}, "setup-state root for repair retention could not be inspected", true};
  }
  facman::platform::StableDirectoryObject state;
  const auto state_opened = state.open_no_follow(state_root);
  if (!state_opened.ok() ||
      !state.validate_descendant(directory, true).ok() ||
      !state.validate_descendant(destination, true).ok())
    return {false, {}, "repair source cache is outside the stable setup-state root", true};

  if (!fs::exists(directory, status)) {
    if (status || !fs::create_directory(directory, status) || status)
      return {false, {}, "repair source cache directory could not be created"};
  } else if (status) {
    return {false, {}, "repair source cache directory could not be inspected", true};
  }
  facman::platform::StableDirectoryObject cache;
  if (!cache.open_no_follow(directory).ok() ||
      !state.revalidate().ok() ||
      !state.validate_descendant(destination, true).ok())
    return {false, {}, "repair source cache directory is linked or changed", true};

  const fs::path marker = directory / ".facman-repair-sources.v1";
  facman::platform::PathIdentity marker_identity;
  auto marker_status = facman::platform::inspect_path_no_follow(marker, marker_identity);
  if (!marker_status.ok())
    return {false, {}, "repair source cache marker could not be inspected", true};
  if (!marker_identity.exists) {
    if (!fs::is_empty(directory, status) || status)
      return {false, {}, "unmarked repair source cache contains foreign content", true};
    std::string detail;
    if (!write_text_new_pinned(marker, kRepairSourceMarker, detail))
      return {false, {}, "repair source cache marker could not be committed: " + detail};
  }
  facman::platform::StableInputFile marker_file;
  if (!marker_file.open_no_follow(marker).ok() ||
      !marker_file.identity().regular_file ||
      marker_file.identity().link_count != 1U ||
      marker_file.size() != sizeof(kRepairSourceMarker) - 1U)
    return {false, {}, "repair source cache marker is unreadable or substituted", true};
  std::string marker_bytes(sizeof(kRepairSourceMarker) - 1U, '\0');
  if (marker_file.read_at(0, marker_bytes.data(), marker_bytes.size()) !=
          marker_bytes.size() ||
      marker_bytes != kRepairSourceMarker || !marker_file.revalidate().ok() ||
      !cache.revalidate().ok())
    return {false, {}, "repair source cache marker changed or is incompatible", true};

  auto retain_file = [&](const fs::path &source, const fs::path &target,
                         std::uint64_t maximum_bytes,
                         const std::string &bound_digest,
                         const char *label)
      -> facman::self_setup::RetainedSourceResult {
    facman::platform::StableInputFile input;
    const auto opened = input.open_no_follow(source);
    if (!opened.ok() || !input.identity().regular_file ||
        input.identity().link_count != 1U || input.size() == 0U ||
        input.size() > maximum_bytes)
      return {false, {}, std::string(label) +
          " input is absent, unsafe, or exceeds its byte limit"};
    const auto source_digest = digest_stable_input(input);
    if (!source_digest.has_value() ||
        (!bound_digest.empty() && *source_digest != bound_digest))
      return {false, {}, std::string(label) +
          " digest differs from its durable identity"};

    facman::platform::PathIdentity existing_identity;
    const auto inspected = facman::platform::inspect_path_no_follow(
        target, existing_identity);
    if (!inspected.ok())
      return {false, {}, std::string(label) +
          " destination could not be inspected", true};
    if (existing_identity.exists) {
      facman::platform::StableInputFile existing;
      const auto existing_opened = existing.open_no_follow(target);
      const auto existing_digest = existing_opened.ok() &&
              existing.identity().regular_file && existing.identity().link_count == 1U
          ? digest_stable_input(existing) : std::optional<std::string>{};
      return existing_digest.has_value() && *existing_digest == *source_digest
          ? facman::self_setup::RetainedSourceResult{
                true, target, std::string("exact ") + label + " already retained"}
          : facman::self_setup::RetainedSourceResult{
                false, {}, std::string(label) +
                    " destination is foreign or changed", true};
    }

    const fs::path temporary = directory /
        facman::platform::path_from_utf8("." +
            facman::platform::path_to_utf8(target.filename()) + ".pending." +
            std::to_string(GetCurrentProcessId()) + "." +
            std::to_string(GetTickCount64()) + ".tmp");
    facman::platform::DurableOutputFile output;
    const auto created = output.create_exclusive(temporary, input.size());
    if (!created.ok())
      return {false, {}, std::string(label) +
          " temporary could not be created: " + created.detail};
    facman::base::Sha256Hasher copied_hash;
    std::vector<unsigned char> buffer(1024U * 1024U);
    for (std::uint64_t offset = 0; offset < input.size();) {
      const std::size_t requested = static_cast<std::size_t>((std::min)(
          static_cast<std::uint64_t>(buffer.size()), input.size() - offset));
      if (input.read_at(offset, buffer.data(), requested) != requested ||
          output.write_at(offset, buffer.data(), requested) != requested) {
        std::string detail = std::string(label) + " changed or could not be copied";
        const auto discarded = output.discard_open();
        if (!discarded.ok()) detail += "; cleanup: " + discarded.detail;
        return {false, {}, detail};
      }
      copied_hash.update(buffer.data(), requested);
      offset += requested;
    }
    if (!input.revalidate().ok() || copied_hash.finish() != *source_digest) {
      std::string detail = std::string(label) + " changed while it was retained";
      const auto discarded = output.discard_open();
      if (!discarded.ok()) detail += "; cleanup: " + discarded.detail;
      return {false, {}, detail, true};
    }
    const auto committed = output.publish_no_replace(target);
    if (!committed.ok()) {
      std::string detail = std::string(label) +
          " could not be published without replacement: " + committed.detail;
      const auto discarded = output.discard_open();
      if (!discarded.ok()) detail += "; cleanup: " + discarded.detail;
      return {false, {}, detail, true};
    }
    facman::platform::StableInputFile retained;
    const auto retained_opened = retained.open_no_follow(target);
    const auto retained_digest = retained_opened.ok() &&
            retained.identity().regular_file && retained.identity().link_count == 1U
        ? digest_stable_input(retained) : std::optional<std::string>{};
    if (!retained_digest.has_value() || *retained_digest != *source_digest ||
        !cache.revalidate().ok() || !state.revalidate().ok())
      return {false, {}, std::string("published ") + label +
          " identity could not be revalidated", true};
    return {true, target, std::string("exact ") + label + " retained"};
  };

  const auto retained_source = retain_file(
      package, destination, kMaximumRepairSourceBytes, expected_sha256,
      "offline repair source");
  if (!retained_source.ok) return retained_source;
  const fs::path launcher = repair_launcher_path(destination);
  if (!state.validate_descendant(launcher, true).ok())
    return {false, {}, "offline maintenance launcher is outside the stable setup-state root", true};
  const auto retained_launcher = retain_file(
      maintenance_launcher, launcher,
      kMaximumRepairLauncherBytes, {}, "offline maintenance launcher");
  if (!retained_launcher.ok) return retained_launcher;
  const auto launcher_digest = digest_stable_file(
      launcher, kMaximumRepairLauncherBytes);
  if (!launcher_digest.has_value())
    return {false, {}, "retained maintenance launcher could not be identified", true};
  const fs::path receipt = repair_receipt_path(destination);
  if (!state.validate_descendant(receipt, true).ok())
    return {false, {}, "repair source receipt is outside the stable setup-state root", true};
  const std::string receipt_content = repair_receipt_bytes(
      expected_sha256, *launcher_digest);
  const auto existing_receipt = read_stable_text(receipt, 512U);
  if (existing_receipt.has_value()) {
    if (*existing_receipt != receipt_content)
      return {false, {}, "repair source receipt is foreign or changed", true};
  } else {
    facman::platform::PathIdentity receipt_identity;
    if (!facman::platform::inspect_path_no_follow(receipt, receipt_identity).ok() ||
        receipt_identity.exists)
      return {false, {}, "repair source receipt is unreadable or substituted", true};
    std::string detail;
    if (!write_text_new_pinned(receipt, receipt_content, detail))
      return {false, {}, "repair source receipt could not be committed: " + detail};
  }
  return validate_repair_source(context, expected_sha256);
}

class SetupNativeEffects final : public facman::self_setup::NativeEffects {
public:
  facman::self_setup::RetainedSourceResult retain_repair_source(
      const facman::self_setup::NativeContext &context,
      const fs::path &package,
      const fs::path &maintenance_launcher,
      const std::string &expected_sha256) override {
    return ::retain_repair_source(
        context, package, maintenance_launcher, expected_sha256);
  }

  facman::self_setup::RetainedSourceResult validate_repair_source(
      const facman::self_setup::NativeContext &context,
      const std::string &expected_sha256) override {
    return ::validate_repair_source(context, expected_sha256);
  }

  facman::self_setup::RetainedSourceResult validate_maintenance_launcher(
      const facman::self_setup::NativeContext &context,
      const std::string &expected_sha256) override {
    return ::validate_maintenance_launcher(context, expected_sha256);
  }

  facman::self_setup::NativeOwnership inspect(
      const facman::self_setup::NativeContext &context,
      facman::self_setup::NativeEffect effect) override {
    PinnedRepairSource pins;
    const auto retained = context.operation == facman::self_setup::Operation::uninstall
        ? ::validate_maintenance_launcher(
              context, context.repair_source.stem().string(), &pins)
        : ::validate_repair_source(
              context, context.repair_source.stem().string(), &pins);
    if (!retained.ok) return facman::self_setup::NativeOwnership::unreadable;
    const auto observed = facman::setup::integration::inspect_windows_effect(
        effect == facman::self_setup::NativeEffect::shortcut
            ? facman::setup::integration::Effect::shortcut
            : facman::setup::integration::Effect::registration,
        {context.install_root, context.state_root, context.acceptance_root,
         context.repair_source},
        context.product_version,
        context.operation == facman::self_setup::Operation::uninstall);
    std::string pin_detail;
    if (!pins.revalidate(pin_detail))
      return facman::self_setup::NativeOwnership::unreadable;
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
      const facman::self_setup::NativeContext &context,
      facman::self_setup::NativeEffect effect) override {
    PinnedRepairSource pins;
    const auto retained = context.operation == facman::self_setup::Operation::uninstall
        ? ::validate_maintenance_launcher(
              context, context.repair_source.stem().string(), &pins)
        : ::validate_repair_source(
              context, context.repair_source.stem().string(), &pins);
    if (!retained.ok) return {false, retained.detail, true};
    const auto result = facman::setup::integration::apply_windows_effect(
        effect == facman::self_setup::NativeEffect::shortcut
            ? facman::setup::integration::Effect::shortcut
            : facman::setup::integration::Effect::registration,
        {context.install_root, context.state_root, context.acceptance_root,
         context.repair_source},
        context.product_version,
        context.operation == facman::self_setup::Operation::uninstall);
    std::string pin_detail;
    if (!pins.revalidate(pin_detail)) {
      const std::string detail = result.detail.empty()
          ? pin_detail : result.detail + "; cache revalidation: " + pin_detail;
      return {false, detail, true};
    }
    return {result.ok, result.detail, result.recovery_required};
  }
};

class QualificationInterruptHook final
    : public facman::self_setup::DurableBoundaryHook {
public:
  explicit QualificationInterruptHook(facman::self_setup::DurableBoundary boundary)
      : boundary_(boundary) {}

  bool reached(facman::self_setup::DurableBoundary boundary) override {
    return boundary != boundary_;
  }

private:
  facman::self_setup::DurableBoundary boundary_;
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

  std::optional<QualificationInterrupt> qualification_interrupt;
  if (!consume_qualification_interrupt(options, qualification_interrupt, problem)) {
    print_error({"self_setup_qualification_interrupt_invalid", problem, ""},
                options.json);
    return 4;
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
  fs::path maintenance_launcher;
  if (options.operation != facman::self_setup::Operation::verify) {
    auto executable = current_executable_path(problem);
    if (!executable.has_value()) {
      print_error({"self_setup_launcher_invalid", problem, ""}, options.json);
      return 4;
    }
    maintenance_launcher = std::move(*executable);
  }
  if (options.package.empty() &&
      (options.operation == facman::self_setup::Operation::install ||
       options.operation == facman::self_setup::Operation::repair)) {
    options.package = maintenance_launcher;
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

  facman::self_setup::Request request;
  request.operation = options.operation;
  request.package = options.package;
  request.maintenance_launcher = maintenance_launcher;
  request.install_root = options.install_root;
  request.state_root = options.state_root;
  request.acceptance_root = options.acceptance_root;
  request.product_version = FACMAN_VERSION_SEMVER;
  request.apply = options.apply;
  SetupNativeEffects native_effects;
  SetupPackageMaterializer package_materializer;
  if (options.shell_integration)
    request.native_effects = &native_effects;
  if (options.operation == facman::self_setup::Operation::install ||
      options.operation == facman::self_setup::Operation::repair)
    request.package_materializer = &package_materializer;
  std::optional<QualificationInterruptHook> qualification_hook;
  if (qualification_interrupt.has_value()) {
    qualification_hook.emplace(qualification_interrupt->boundary);
    request.durable_boundary_hook = &*qualification_hook;
    request.qualification_claims = qualification_interrupt->claims;
  }
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
