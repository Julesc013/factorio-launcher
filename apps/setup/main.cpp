// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_self_setup.h"
#include "facman_self_maintenance.h"
#include "facman_self_maintenance_provider.h"
#include "windows_maintenance_handoff.h"
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
#include <limits>
#include <optional>
#include <sstream>
#include <string>
#include <tuple>
#include <vector>

namespace fs = std::filesystem;

namespace {

std::string utf8(const std::wstring &value);
bool lowercase_hex_64(const std::string &value);

struct Options {
  facman::self_setup::Operation operation =
      facman::self_setup::Operation::verify;
  std::optional<facman::self_maintenance::Operation> maintenance_operation;
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
  fs::path qualification_fixture_permit;
  bool qualification_fixture_permit_explicit = false;
};

struct ContinuationOptions {
  std::string operation_id;
  std::string nonce;
  fs::path journal;
  std::string journal_sha256;
  std::uintptr_t parent_handle = 0;
  DWORD parent_pid = 0;
  std::uint64_t parent_created = 0;
  std::uint64_t deadline_tick_ms = 0;
};

bool parse_unsigned(const std::wstring &text, std::uint64_t &value) {
  if (text.empty()) return false;
  std::uint64_t result = 0;
  for (const wchar_t character : text) {
    if (character < L'0' || character > L'9') return false;
    const std::uint64_t digit = static_cast<std::uint64_t>(character - L'0');
    if (result > ((std::numeric_limits<std::uint64_t>::max)() - digit) / 10U)
      return false;
    result = result * 10U + digit;
  }
  value = result;
  return true;
}

bool parse_continuation(int argc, wchar_t **argv, ContinuationOptions &options,
                        std::string &problem) {
  if (argc != 18 || std::wstring(argv[1]) != L"continue-maintenance") {
    problem = "private continuation requires exactly eight named inputs";
    return false;
  }
  unsigned operation_count = 0, nonce_count = 0, journal_count = 0,
           journal_sha_count = 0, handle_count = 0, pid_count = 0,
           created_count = 0, deadline_count = 0;
  std::uint64_t handle = 0, pid = 0;
  for (int index = 2; index < argc; index += 2) {
    const std::wstring name(argv[index]);
    const std::wstring value(argv[index + 1]);
    if (value.empty()) {
      problem = "private continuation input is empty";
      return false;
    }
    if (name == L"--operation-id") {
      ++operation_count;
      options.operation_id = utf8(value);
    } else if (name == L"--handoff-nonce") {
      ++nonce_count;
      options.nonce = utf8(value);
    } else if (name == L"--handoff-journal") {
      ++journal_count;
      options.journal = fs::path(value);
    } else if (name == L"--handoff-journal-sha256") {
      ++journal_sha_count;
      options.journal_sha256 = utf8(value);
    } else if (name == L"--parent-handle") {
      ++handle_count;
      if (!parse_unsigned(value, handle)) {
        problem = "private continuation parent handle is invalid";
        return false;
      }
    } else if (name == L"--parent-pid") {
      ++pid_count;
      if (!parse_unsigned(value, pid)) {
        problem = "private continuation parent PID is invalid";
        return false;
      }
    } else if (name == L"--parent-created") {
      ++created_count;
      if (!parse_unsigned(value, options.parent_created)) {
        problem = "private continuation parent creation time is invalid";
        return false;
      }
    } else if (name == L"--deadline-tick-ms") {
      ++deadline_count;
      if (!parse_unsigned(value, options.deadline_tick_ms)) {
        problem = "private continuation deadline is invalid";
        return false;
      }
    } else {
      problem = "private continuation contains an unknown input";
      return false;
    }
  }
  std::string identifier_detail;
  if (operation_count != 1U || nonce_count != 1U || journal_count != 1U ||
      journal_sha_count != 1U || handle_count != 1U || pid_count != 1U ||
      created_count != 1U || deadline_count != 1U ||
      !facman::base::validate_identifier(options.operation_id, identifier_detail) ||
      !facman::base::validate_identifier(options.nonce, identifier_detail) ||
      handle == 0 ||
      handle > static_cast<std::uint64_t>((std::numeric_limits<std::intptr_t>::max)()) ||
      pid == 0 || pid > (std::numeric_limits<DWORD>::max)() ||
      options.parent_created == 0 || options.deadline_tick_ms == 0 ||
      !options.journal.is_absolute() ||
      options.journal != options.journal.lexically_normal() ||
      !lowercase_hex_64(options.journal_sha256)) {
    problem = "private continuation inputs are incomplete or out of range";
    return false;
  }
  options.parent_handle = static_cast<std::uintptr_t>(handle);
  options.parent_pid = static_cast<DWORD>(pid);
  return true;
}

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
  const fs::path &materialized_path() const { return materialized_.path; }

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
      << "  FacManSetup update    --package PATH [--root PATH] [--state-root "
         "PATH] [--acceptance-root PATH] [--yes] [--json]\n"
      << "  FacManSetup downgrade --package PATH [--root PATH] [--state-root "
         "PATH] [--acceptance-root PATH] [--yes] [--json]\n"
      << "  FacManSetup rollback  [--root PATH] [--state-root PATH] "
         "[--acceptance-root PATH] [--yes] [--json]\n\n"
      << "Qualification interruption requires both "
         "--qualification-interrupt-after provider_plan_reviewed|files_applied|shortcut_applied and "
         "--qualification-interrupt-permit PATH, with explicit noninteractive "
         "installed-operation inputs.\n\n"
      << "Self-maintenance --no-shell-integration requires an exact "
         "--qualification-fixture-permit under a marked disposable "
         "acceptance root.\n\n"
      << "Double-clicking starts the guided per-user install flow. Without "
         "--yes, explicit mutating commands return a "
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
  else if (operation == L"update")
    options.maintenance_operation =
        facman::self_maintenance::Operation::update;
  else if (operation == L"downgrade")
    options.maintenance_operation =
        facman::self_maintenance::Operation::downgrade;
  else if (operation == L"rollback")
    options.maintenance_operation =
        facman::self_maintenance::Operation::rollback;
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
               argument == L"--qualification-interrupt-permit" ||
               argument == L"--qualification-fixture-permit") {
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
      } else if (argument == L"--qualification-interrupt-permit") {
        if (options.qualification_interrupt_permit_explicit) {
          problem = "duplicate option: --qualification-interrupt-permit";
          return false;
        }
        options.qualification_interrupt_permit = fs::path(argv[index]);
        options.qualification_interrupt_permit_explicit = true;
      } else {
        if (options.qualification_fixture_permit_explicit) {
          problem = "duplicate option: --qualification-fixture-permit";
          return false;
        }
        options.qualification_fixture_permit = fs::path(argv[index]);
        options.qualification_fixture_permit_explicit = true;
      }
    } else {
      problem = "unknown option: " + utf8(argument);
      return false;
    }
  }
  if (options.maintenance_operation.has_value()) {
    const bool rollback = *options.maintenance_operation ==
        facman::self_maintenance::Operation::rollback;
    if ((!rollback && (!options.package_explicit ||
                       options.package_count != 1U)) ||
        (rollback && options.package_count != 0U)) {
      problem = rollback
          ? "rollback does not accept --package"
          : "update and downgrade require exactly one --package";
      return false;
    }
    const bool isolated_no_shell = !options.shell_integration &&
        options.no_shell_integration_count == 1U &&
        options.install_root_explicit && options.state_root_explicit &&
        options.acceptance_root_explicit && !options.interactive;
    if ((!options.shell_integration && !isolated_no_shell) ||
        (options.shell_integration && options.no_shell_integration_count != 0U)) {
      problem = "self-maintenance requires Windows shell integration or an "
          "explicit isolated --no-shell-integration fixture";
      return false;
    }
  }
  if (!options.maintenance_operation.has_value() &&
      options.qualification_fixture_permit_explicit) {
    problem = "--qualification-fixture-permit is limited to self-maintenance";
    return false;
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
  if (options.maintenance_operation.has_value()) {
    problem = "qualification interruption is not supported for self-maintenance verbs";
    return false;
  }
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

facman::core::Error setup_error_with_detail(std::string code,
                                            std::string message,
                                            std::string detail) {
  facman::core::Error error(std::move(code), std::move(message), "");
  error.detail = std::move(detail);
  return error;
}

void print_maintenance_error(const facman::core::Error &value,
                             bool json_mode) {
  if (!json_mode) {
    std::cerr << "FacManSetup: " << value.message << '\n';
    if (!value.detail.empty()) std::cerr << value.detail << '\n';
    return;
  }
  facman::core::json::ObjectBuilder output;
  output.add_string("schema", "facman.self_maintenance_cli.v1");
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
  facman::platform::StableDirectoryObject acceptance;
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
    const auto acceptance_status = acceptance.revalidate();
    const auto cache_status = cache.revalidate();
    const auto state_status = state.revalidate();
    if (!acceptance_status.ok() || !cache_status.ok() || !state_status.ok() ||
        !acceptance.validate_descendant(state.path(), false).ok()) {
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
  auto admitted = pins.acceptance.open_no_follow(context.acceptance_root);
  if (!admitted.ok())
    return {false, {}, "acceptance root is unsafe: " + admitted.detail, true};
  admitted = pins.acceptance.validate_descendant(state_root, false);
  if (!admitted.ok())
    return {false, {}, "state root is outside acceptance: " + admitted.detail, true};
  admitted = pins.state.open_no_follow(state_root);
  if (!admitted.ok())
    return {false, {}, "state root is unsafe: " + admitted.detail, true};
  admitted = pins.cache.open_no_follow(directory);
  if (!admitted.ok())
    return {false, {}, "repair source cache is unsafe: " + admitted.detail, true};
  for (const auto &[path, allow_absent, label] :
       std::vector<std::tuple<fs::path, bool, const char *>>{
           {source, !require_source, "source"}, {launcher, false, "launcher"},
           {receipt, false, "receipt"}, {marker, false, "marker"}}) {
    admitted = pins.state.validate_descendant(path, allow_absent);
    if (!admitted.ok())
      return {false, {}, std::string("repair cache ") + label +
          " is outside stable state authority: " + admitted.detail, true};
  }
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

facman::core::Result<void> retire_repair_source(
    const facman::self_setup::NativeContext &context,
    PinnedRepairSource &pins) {
  std::string detail;
  if (!pins.revalidate(detail))
    return facman::core::Result<void>::failure(
        {"self_maintenance_repair_source_retirement_failed",
         "retained repair source changed before retirement", detail});

  const fs::path source = context.repair_source;
  const std::pair<fs::path, facman::platform::FileIdentity> files[] = {
      {source, pins.source.identity()},
      {repair_launcher_path(source), pins.launcher.identity()},
      {repair_receipt_path(source), pins.receipt.identity()},
  };
  // Pinned reads deliberately deny namespace replacement.  Retain their exact
  // identities, close only the three generation-owned handles, then reopen and
  // remove each pathname through remove_exact_object's identity check.  The
  // acceptance, state, cache, and marker objects stay pinned throughout.
  pins.source = facman::platform::StableInputFile{};
  pins.launcher = facman::platform::StableInputFile{};
  pins.receipt = facman::platform::StableInputFile{};
  for (const auto &[path, identity] : files) {
    const auto removed = facman::platform::remove_exact_object(path, identity);
    if (!removed.ok())
      return facman::core::Result<void>::failure(
          {"self_maintenance_repair_source_retirement_failed",
           "exact retained repair source file could not be retired",
           facman::platform::path_to_utf8(path) + ": " + removed.detail});
  }

  const auto acceptance_status = pins.acceptance.revalidate();
  const auto state_status = pins.state.revalidate();
  const auto cache_status = pins.cache.revalidate();
  const auto marker_status = pins.marker.revalidate_path();
  if (!acceptance_status.ok() || !state_status.ok() || !cache_status.ok() ||
      !marker_status.ok()) {
    const auto &failed = !acceptance_status.ok() ? acceptance_status
        : (!state_status.ok() ? state_status
        : (!cache_status.ok() ? cache_status : marker_status));
    return facman::core::Result<void>::failure(
        {"self_maintenance_repair_source_retirement_failed",
         "repair source cache identity changed during retirement",
         failed.detail});
  }
  return facman::core::Result<void>::success();
}

facman::self_setup::RetainedSourceResult retain_repair_source(
    const facman::self_setup::NativeContext &context,
    const fs::path &package, const fs::path &maintenance_launcher,
    const std::string &expected_sha256,
    const std::string &expected_launcher_sha256 = {}) {
  const fs::path destination = context.repair_source;
  if (expected_sha256.size() != 64U || destination.filename() !=
          facman::platform::path_from_utf8(expected_sha256 + ".zip"))
    return {false, {}, "repair source destination is not digest-bound", true};

  const fs::path directory = destination.parent_path();
  const fs::path state_root = directory.parent_path();
  if (state_root.lexically_normal() != context.state_root.lexically_normal())
    return {false, {}, "repair source does not bind the configured state root", true};
  facman::platform::StableDirectoryObject acceptance;
  const auto acceptance_opened = acceptance.open_no_follow(
      context.acceptance_root);
  if (!acceptance_opened.ok() ||
      !acceptance.validate_descendant(state_root, true).ok())
    return {false, {},
            "repair source state root is outside stable acceptance authority",
            true};
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
      !acceptance.validate_descendant(state_root, false).ok() ||
      !state.validate_descendant(directory, true).ok())
    return {false, {}, "repair source cache is outside the stable setup-state root", true};

  if (!fs::exists(directory, status)) {
    if (status || !fs::create_directory(directory, status) || status)
      return {false, {}, "repair source cache directory could not be created"};
  } else if (status) {
    return {false, {}, "repair source cache directory could not be inspected", true};
  }
  facman::platform::StableDirectoryObject cache;
  if (!cache.open_no_follow(directory).ok() ||
      !acceptance.revalidate().ok() ||
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
      kMaximumRepairLauncherBytes, expected_launcher_sha256,
      "offline maintenance launcher");
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

std::string digest_text(const std::string &value) {
  return facman::base::sha256_hex_bytes(
      reinterpret_cast<const unsigned char *>(value.data()), value.size());
}

bool same_path(const fs::path &left, const fs::path &right);

class MaintenanceEffects final : public facman::self_maintenance::Effects,
                                 public facman::self_maintenance::EpochPreparationEffects,
                                 public facman::self_maintenance::EpochContinuationEffects,
                                 public facman::self_maintenance::EpochShellCutoverEffects {
public:
  MaintenanceEffects(facman::self_maintenance::ProviderBridge &provider,
                     fs::path state_root, fs::path acceptance_root,
                     fs::path maintenance_launcher,
                     std::string maintenance_launcher_sha256,
                     bool shell_integration)
      : provider_(provider), state_root_(std::move(state_root)),
        acceptance_root_(std::move(acceptance_root)),
        maintenance_launcher_(std::move(maintenance_launcher)),
        maintenance_launcher_sha256_(std::move(maintenance_launcher_sha256)),
        shell_integration_(shell_integration) {}

  facman::self_maintenance::CandidateState inspect_candidate(
      const facman::self_maintenance::Plan &plan) override {
    const auto state = provider_.inspect_candidate(plan);
    if (state != facman::self_maintenance::CandidateState::exact)
      return state;
    if (!target_pins_ready_) {
      const auto retained = ::validate_repair_source(
          native_context(plan.target), plan.target.package_sha256,
          &target_pins_);
      target_pins_ready_ = retained.ok;
      if (!retained.ok)
        return facman::self_maintenance::CandidateState::unreadable;
    } else {
      std::string detail;
      if (!target_pins_.revalidate(detail))
        return facman::self_maintenance::CandidateState::unreadable;
    }
    return bind_target_files(plan) ? state
        : facman::self_maintenance::CandidateState::unreadable;
  }

  facman::self_maintenance::EffectResult review_install_local(
      const facman::self_maintenance::Plan &plan) override {
    return provider_.review_install_local(plan);
  }

  facman::core::Result<facman::self_maintenance::RetainedMaintenanceInputs>
  retain_handoff_inputs(const facman::self_maintenance::Plan &plan,
      const fs::path &continuation_helper,
      const std::string &continuation_helper_sha256) override {
    return retain_epoch_handoff_inputs(
        plan, continuation_helper, continuation_helper_sha256);
  }

  facman::core::Result<facman::self_maintenance::ProviderApplyBinding>
  bind_install_local(const facman::self_maintenance::Plan &plan,
                     const std::string &receipt) override {
    return provider_.bind_install_local(plan, receipt);
  }

  facman::core::Result<void> rehydrate_install_local(
      const facman::self_maintenance::Plan &plan,
      const facman::self_maintenance::ProviderApplyBinding &binding) override {
    return provider_.rehydrate_install_local(plan, binding);
  }

  facman::self_maintenance::EffectResult apply_bound_install_local(
      const facman::self_maintenance::Plan &plan,
      const facman::self_maintenance::ProviderApplyBinding &binding) override {
    return provider_.apply_bound_install_local(plan, binding);
  }

  facman::self_maintenance::EffectResult prepare_install_local(
      const facman::self_maintenance::Plan &plan) override {
    const auto retained = ::retain_repair_source(
        native_context(plan.target), plan.package, maintenance_launcher_,
        plan.package_sha256, maintenance_launcher_sha256_);
    if (!retained.ok)
      return {false, retained.recovery_required, {}, retained.detail};
    const auto pinned = ::validate_repair_source(
        native_context(plan.target), plan.package_sha256, &target_pins_);
    target_pins_ready_ = pinned.ok;
    return {pinned.ok, pinned.recovery_required, {}, pinned.detail};
  }

  facman::self_maintenance::EffectResult install_local(
      const facman::self_maintenance::Plan &plan) override {
    return provider_.install_local(plan);
  }

  facman::self_maintenance::EffectResult inspect_installed(
      const facman::self_maintenance::Plan &plan) override {
    auto result = provider_.inspect_installed(plan);
    if (result.ok && !ensure_target_pins(plan))
      return {false, false, {}, target_pin_detail_};
    return result;
  }

  facman::self_maintenance::EffectResult inspect_installed(
      const facman::self_maintenance::Plan &plan,
      const facman::self_maintenance::ProviderApplyBinding &binding) override {
    auto result = provider_.inspect_installed(plan, binding);
    if (result.ok && !ensure_target_pins(plan))
      return {false, false, {}, target_pin_detail_};
    return result;
  }

  facman::self_maintenance::EffectResult verify_installed(
      const facman::self_maintenance::Plan &plan) override {
    return provider_.verify_installed(plan);
  }

  facman::self_maintenance::EffectResult validate_terminal_verification(
      const facman::self_maintenance::Plan &plan,
      const facman::self_maintenance::ProviderApplyBinding &binding,
      const std::string &receipt) override {
    return provider_.validate_terminal_verification(plan, binding, receipt);
  }

  facman::self_maintenance::ShellState inspect_shortcut(
      const facman::self_maintenance::Plan &plan) override {
    return inspect_shell(facman::setup::integration::Effect::shortcut, plan);
  }

  facman::self_maintenance::ShellState inspect_registration(
      const facman::self_maintenance::Plan &plan) override {
    return inspect_shell(facman::setup::integration::Effect::registration,
                         plan);
  }

  facman::self_maintenance::EffectResult cutover_shortcut(
      const facman::self_maintenance::Plan &plan) override {
    return cutover(facman::setup::integration::Effect::shortcut, plan);
  }

  facman::self_maintenance::EffectResult cutover_registration(
      const facman::self_maintenance::Plan &plan) override {
    return cutover(facman::setup::integration::Effect::registration, plan);
  }

  facman::self_maintenance::EffectResult retire_shortcut_backup(
      const facman::self_maintenance::Plan &plan) override {
    if (!ensure_target_pins(plan))
      return {false, false, {}, target_pin_detail_};
    const std::string receipt = digest_text(
        plan.operation_id + "\nshortcut-backup-retired\n");
    if (!shell_integration_)
      return {true, false, receipt,
              "shortcut integration is disabled; no backup exists"};
    const auto result =
        facman::setup::integration::retire_windows_shortcut_cutover_backup(
            windows_context(plan));
    if (!revalidate_target_pins()) {
      const std::string detail = result.detail.empty()
          ? target_pin_detail_
          : result.detail + "; target pin revalidation: " +
                target_pin_detail_;
      return {false, true, {}, detail};
    }
    if (!result.ok)
      return {false, result.recovery_required, {}, result.detail};
    return {true, false, receipt, result.detail};
  }

private:
  facman::core::Result<facman::self_maintenance::RetainedMaintenanceInputs>
  retain_epoch_handoff_inputs(const facman::self_maintenance::Plan &plan,
      const fs::path &continuation_helper,
      const std::string &continuation_helper_sha256) {
    using Inputs = facman::self_maintenance::RetainedMaintenanceInputs;
    const fs::path handoff_root = plan.target.state_root / "epoch-handoff";
    const fs::path operation_root = handoff_root / plan.operation_id;
    facman::platform::StableDirectoryObject acceptance, state, handoffs, operation;
    if (!acceptance.open_no_follow(plan.target.acceptance_root).ok() ||
        !acceptance.validate_descendant(plan.target.state_root, false).ok() ||
        !state.open_no_follow_for_relative_writes(plan.target.state_root).ok() ||
        !state.validate_descendant(handoff_root, true).ok())
      return facman::core::Result<Inputs>::failure({"self_maintenance_epoch_recovery_required",
          "epoch handoff root is outside the held state root", {}});
    auto opened = state.open_child_directory_no_follow_for_relative_writes(
        "epoch-handoff", handoffs);
    if (!opened.ok())
      opened = state.create_child_directory_exclusive("epoch-handoff", handoffs);
    if (!opened.ok()) return facman::core::Result<Inputs>::failure(
        {"self_maintenance_epoch_recovery_required", "epoch handoff root could not be opened", opened.detail});
    opened = handoffs.open_child_directory_no_follow_for_relative_writes(
        plan.operation_id, operation);
    if (!opened.ok())
      opened = handoffs.create_child_directory_exclusive(plan.operation_id, operation);
    if (!opened.ok()) return facman::core::Result<Inputs>::failure(
        {"self_maintenance_epoch_recovery_required", "epoch handoff operation could not be opened", opened.detail});

    std::vector<fs::path> initial_names;
    const auto is_initial_prefix = [&](const std::vector<fs::path> &names) {
      return names.empty() || names == std::vector<fs::path>{"package.zip"} ||
          names == std::vector<fs::path>{"package.staging"} ||
          names == std::vector<fs::path>{"FacManContinuation.staging", "package.zip"} ||
          names == std::vector<fs::path>{"FacManContinuation.exe", "package.zip"};
    };
    if (!operation.list_child_names_bounded(3U, initial_names).ok() ||
        !is_initial_prefix(initial_names))
      return facman::core::Result<Inputs>::failure(
          {"self_maintenance_epoch_recovery_required",
           "epoch handoff operation contains a partial or foreign input set", {}});

    const auto retain = [&](const fs::path &source, const char *final_name,
                            const char *staging_name, std::uint64_t maximum,
                            const std::string &expected)
        -> facman::core::Result<std::string> {
      facman::platform::StableInputFile input;
      if (!input.open_no_follow_pinned(source).ok() || !input.identity().regular_file ||
          input.identity().link_count != 1U || input.size() == 0U || input.size() > maximum)
        return facman::core::Result<std::string>::failure({"self_maintenance_epoch_recovery_required",
            "epoch handoff input is unsafe", facman::platform::path_to_utf8(source)});
      const auto source_digest = digest_stable_input(input);
      if (!source_digest || (!expected.empty() && *source_digest != expected))
        return facman::core::Result<std::string>::failure({"self_maintenance_epoch_recovery_required",
            "epoch handoff input digest changed", facman::platform::path_to_utf8(source)});
      facman::platform::StableInputFile existing;
      if (operation.open_child_file_no_follow_pinned(final_name, existing).ok()) {
        const auto existing_digest = existing.identity().regular_file &&
                existing.identity().link_count == 1U
            ? digest_stable_input(existing) : std::optional<std::string>{};
        if (!existing_digest || *existing_digest != *source_digest ||
            !existing.revalidate_path().ok() || !input.revalidate_path().ok())
          return facman::core::Result<std::string>::failure({"self_maintenance_epoch_recovery_required",
              "epoch handoff destination is foreign or changed", final_name});
        return facman::core::Result<std::string>::success(*source_digest);
      }
      facman::platform::StableInputFile staging;
      if (operation.open_child_file_no_follow_pinned(staging_name, staging).ok()) {
        // Windows keeps this pinned input read-shared only.  Capture its exact
        // no-follow identity, close it, then reopen that identity for the
        // durable rename; retaining the handle here would share-violate.
        facman::platform::FileIdentity staging_identity;
        if (!staging.identity().regular_file || staging.identity().link_count != 1U ||
            staging.size() == 0U || staging.size() > maximum ||
            digest_stable_input(staging) != source_digest || !staging.revalidate().ok() ||
            !staging.revalidate_path().ok() || !input.revalidate_path().ok())
          return facman::core::Result<std::string>::failure(
              {"self_maintenance_epoch_recovery_required",
               "epoch handoff staging input is foreign or changed", staging_name});
        staging_identity = staging.identity();
        staging = {};
        facman::platform::DurableOutputFile recovered;
        if (!operation.reopen_child_file_no_follow_for_relative_publish(
                staging_name, staging_identity, maximum, recovered).ok() ||
            !recovered.publish_sibling_no_replace(final_name).ok())
          return facman::core::Result<std::string>::failure(
              {"self_maintenance_epoch_recovery_required",
               "epoch handoff staging input could not be promoted", staging_name});
        facman::platform::StableInputFile promoted;
        if (!operation.open_child_file_no_follow_pinned(final_name, promoted).ok() ||
            digest_stable_input(promoted) != source_digest || !promoted.revalidate_path().ok())
          return facman::core::Result<std::string>::failure(
              {"self_maintenance_epoch_recovery_required",
               "promoted epoch handoff input is foreign or changed", final_name});
        return facman::core::Result<std::string>::success(*source_digest);
      }
      facman::platform::DurableOutputFile output;
      if (!operation.create_child_file_exclusive(staging_name, maximum, output).ok())
        return facman::core::Result<std::string>::failure({"self_maintenance_epoch_recovery_required",
            "epoch handoff staging already exists or cannot be created", staging_name});
      std::vector<unsigned char> buffer(1024U * 1024U);
      facman::base::Sha256Hasher copied;
      for (std::uint64_t offset = 0; offset < input.size();) {
        const std::size_t length = static_cast<std::size_t>((std::min)(
            static_cast<std::uint64_t>(buffer.size()), input.size() - offset));
        if (input.read_at(offset, buffer.data(), length) != length ||
            output.write_at(offset, buffer.data(), length) != length) {
          output.discard_open();
          return facman::core::Result<std::string>::failure({"self_maintenance_epoch_recovery_required",
              "epoch handoff input could not be copied", final_name});
        }
        copied.update(buffer.data(), length);
        offset += length;
      }
      if (!input.revalidate().ok() || !input.revalidate_path().ok() ||
          copied.finish() != *source_digest ||
          !output.publish_sibling_no_replace(final_name).ok()) {
        output.discard_open();
        return facman::core::Result<std::string>::failure({"self_maintenance_epoch_recovery_required",
            "epoch handoff input changed or could not be published", final_name});
      }
      facman::platform::StableInputFile retained;
      if (!operation.open_child_file_no_follow_pinned(final_name, retained).ok() ||
          !retained.identity().regular_file || retained.identity().link_count != 1U ||
          digest_stable_input(retained) != source_digest || !retained.revalidate_path().ok())
        return facman::core::Result<std::string>::failure({"self_maintenance_epoch_recovery_required",
            "published epoch handoff input could not be revalidated", final_name});
      return facman::core::Result<std::string>::success(*source_digest);
    };
    auto package = retain(plan.package, "package.zip", "package.staging",
                          kMaximumRepairSourceBytes, plan.package_sha256);
    auto helper = package ? retain(continuation_helper, "FacManContinuation.exe",
                                   "FacManContinuation.staging",
                                   kMaximumRepairLauncherBytes,
                                   continuation_helper_sha256)
                          : facman::core::Result<std::string>::failure(package.error());
    std::vector<fs::path> names;
    if (!package || !helper || !operation.list_child_names_bounded(3U, names).ok() ||
        names != std::vector<fs::path>{"FacManContinuation.exe", "package.zip"} ||
        !acceptance.revalidate().ok() || !acceptance.validate_descendant(plan.target.state_root, false).ok() ||
        !state.revalidate().ok() || !handoffs.revalidate().ok() || !operation.revalidate().ok() ||
        !operation.flush_metadata().ok() || !handoffs.flush_metadata().ok() ||
        !state.flush_metadata().ok())
      return facman::core::Result<Inputs>::failure(!package ? package.error() : !helper ? helper.error() :
          facman::core::Error{"self_maintenance_epoch_recovery_required",
              "epoch handoff custody set is incomplete or changed", {}});
    return facman::core::Result<Inputs>::success(
        {operation_root / "package.zip", package.value(),
         operation_root / "FacManContinuation.exe", helper.value()});
  }

  facman::self_setup::NativeContext native_context(
      const facman::self_maintenance::Generation &generation) const {
    return {facman::self_setup::Operation::repair, generation.install_root,
            generation.state_root, generation.acceptance_root,
            generation.state_root / "repair-sources" /
                facman::platform::path_from_utf8(
                    generation.package_sha256 + ".zip"),
            generation.product_version};
  }

  facman::setup::integration::CutoverContext windows_context(
      const facman::self_maintenance::Plan &plan) const {
    const auto source = native_context(plan.source);
    const auto target = native_context(plan.target);
    return {{source.install_root, source.state_root, source.acceptance_root,
             source.repair_source},
            {target.install_root, target.state_root, target.acceptance_root,
             target.repair_source},
            plan.source.product_version, plan.target.product_version,
            plan.operation_id};
  }

  facman::self_maintenance::ShellState inspect_shell(
      facman::setup::integration::Effect effect,
      const facman::self_maintenance::Plan &plan) {
    if (!ensure_target_pins(plan))
      return facman::self_maintenance::ShellState::unreadable;
    if (!shell_integration_)
      return facman::self_maintenance::ShellState::new_exact;
    const auto observed =
        facman::setup::integration::inspect_windows_cutover_effect(
            effect, windows_context(plan));
    if (!revalidate_target_pins())
      return facman::self_maintenance::ShellState::unreadable;
    switch (observed) {
    case facman::setup::integration::CutoverOwnership::absent:
      return facman::self_maintenance::ShellState::absent;
    case facman::setup::integration::CutoverOwnership::old_exact:
      return facman::self_maintenance::ShellState::old_exact;
    case facman::setup::integration::CutoverOwnership::new_exact:
      return facman::self_maintenance::ShellState::new_exact;
    case facman::setup::integration::CutoverOwnership::facman_owned_other:
    case facman::setup::integration::CutoverOwnership::foreign:
      return facman::self_maintenance::ShellState::foreign;
    case facman::setup::integration::CutoverOwnership::unreadable:
      return facman::self_maintenance::ShellState::unreadable;
    }
    return facman::self_maintenance::ShellState::unreadable;
  }

  facman::self_maintenance::EffectResult cutover(
      facman::setup::integration::Effect effect,
      const facman::self_maintenance::Plan &plan) {
    if (!ensure_target_pins(plan))
      return {false, false, {}, target_pin_detail_};
    const auto result = facman::setup::integration::apply_windows_cutover_effect(
        effect, windows_context(plan));
    if (!revalidate_target_pins()) {
      const std::string detail = result.detail.empty()
          ? target_pin_detail_
          : result.detail + "; target pin revalidation: " + target_pin_detail_;
      return {false, true, {}, detail};
    }
    if (!result.ok)
      return {false, result.recovery_required, {}, result.detail};
    return {true, false,
            digest_text(plan.operation_id + "\n" +
                        (effect == facman::setup::integration::Effect::shortcut
                             ? "shortcut\n" : "registration\n") +
                        result.detail),
            result.detail};
  }

  bool bind_target_files(const facman::self_maintenance::Plan &plan) {
    if (!target_pins_ready_) {
      target_pin_detail_ = "retained maintenance inputs are not pinned";
      return false;
    }
    facman::platform::StableInputFile gui;
    facman::platform::StableInputFile maintenance;
    const auto gui_opened = gui.open_no_follow_pinned(plan.target.gui);
    const auto maintenance_opened = maintenance.open_no_follow_pinned(
        plan.target.maintenance_launcher);
    if (!gui_opened.ok() || !maintenance_opened.ok() ||
        !gui.identity().regular_file || gui.identity().link_count != 1U ||
        gui.size() == 0U || gui.size() > kMaximumRepairSourceBytes ||
        !maintenance.identity().regular_file ||
        maintenance.identity().link_count != 1U || maintenance.size() == 0U ||
        maintenance.size() > kMaximumRepairLauncherBytes) {
      target_pin_detail_ =
          "target GUI or installed maintenance launcher is unsafe";
      return false;
    }
    const auto retained_digest = digest_stable_input(target_pins_.launcher);
    const auto installed_digest = digest_stable_input(maintenance);
    const bool legacy_retained_generation =
        (plan.operation == "downgrade" || plan.operation == "rollback") &&
        plan.target.install_id == "facman.self" &&
        same_path(plan.target.install_root, plan.target.logical_root);
    const bool bootstrap_installed_launcher =
        plan.operation == "bootstrap" &&
        installed_digest.has_value() &&
        *installed_digest == maintenance_launcher_sha256_;
    if (!retained_digest.has_value() || !installed_digest.has_value() ||
        (*retained_digest != *installed_digest &&
         !legacy_retained_generation && !bootstrap_installed_launcher)) {
      target_pin_detail_ =
          "installed maintenance launcher differs from the retained helper";
      return false;
    }
    // Legacy installs retained the downloaded self-extracting Setup file as
    // their repair helper, while Universal Setup owned the smaller embedded
    // maintenance entry point under the logical installation root.  The
    // migrated generation record and provider installed-state verification
    // bind both identities independently.  Keep both files pinned here; only
    // skip their byte-equality requirement for that exact retained legacy
    // generation.
    target_gui_ = std::move(gui);
    target_maintenance_ = std::move(maintenance);
    target_files_ready_ = true;
    return revalidate_target_pins();
  }

  bool revalidate_target_pins() {
    std::string detail;
    if (!target_pins_ready_ || !target_pins_.revalidate(detail)) {
      target_pin_detail_ = detail.empty()
          ? "retained maintenance inputs are not pinned" : detail;
      return false;
    }
    if (!target_files_ready_) {
      target_pin_detail_ = "target executable identities are not pinned";
      return false;
    }
    const auto gui = target_gui_.revalidate_path();
    const auto maintenance = target_maintenance_.revalidate_path();
    if (!gui.ok() || !maintenance.ok()) {
      target_pin_detail_ =
          "target GUI or installed maintenance launcher was substituted";
      return false;
    }
    target_pin_detail_.clear();
    return true;
  }

  bool ensure_target_pins(const facman::self_maintenance::Plan &plan) {
    if (target_pins_ready_ && target_files_ready_)
      return revalidate_target_pins();
    const auto retained = ::validate_repair_source(
        native_context(plan.target), plan.target.package_sha256, &target_pins_);
    target_pins_ready_ = retained.ok;
    if (!retained.ok) {
      target_pin_detail_ = retained.detail;
      return false;
    }
    return bind_target_files(plan);
  }

  facman::self_maintenance::ProviderBridge &provider_;
  fs::path state_root_;
  fs::path acceptance_root_;
  fs::path maintenance_launcher_;
  std::string maintenance_launcher_sha256_;
  PinnedRepairSource target_pins_;
  facman::platform::StableInputFile target_gui_;
  facman::platform::StableInputFile target_maintenance_;
  bool target_pins_ready_ = false;
  bool target_files_ready_ = false;
  std::string target_pin_detail_;
  bool shell_integration_ = true;
};

class SetupBootstrapEffects final
    : public facman::self_maintenance::CompatibilityAuthorityBootstrapEffects {
public:
  SetupBootstrapEffects(facman::self_maintenance::ProviderBridge &provider,
      const facman::self_maintenance::PackageInspection &package,
      fs::path state_root, fs::path acceptance_root, bool shell_integration)
      : provider_(provider), package_(package),
        native_(provider, std::move(state_root), std::move(acceptance_root),
            package.package,
            package.maintenance_launcher_sha256, shell_integration) {}

  facman::self_maintenance::EffectResult inspect_epoch_clone(
      const facman::self_maintenance::Generation &source,
      const facman::self_maintenance::Generation &target) override {
    const auto plan = transition(source, target);
    const auto inspected = provider_.inspect_installed(plan);
    if (!inspected.ok || inspected.outcome_unknown)
      return inspected;
    const auto verified = provider_.verify_installed(plan);
    return verified.ok && !verified.outcome_unknown
        ? inspected
        : facman::self_maintenance::EffectResult{
            false, verified.outcome_unknown, {}, verified.detail};
  }

  facman::self_maintenance::EffectResult clone_epoch(
      const facman::self_maintenance::Generation &source,
      const facman::self_maintenance::Generation &target) override {
    const auto plan = transition(source, target);
    const auto candidate = provider_.inspect_candidate(plan);
    if (candidate != facman::self_maintenance::CandidateState::absent)
      return {false, candidate == facman::self_maintenance::CandidateState::unreadable,
              {}, "epoch clone target is already present or unsafe"};
    const facman::self_setup::NativeContext context{
        facman::self_setup::Operation::repair, target.install_root,
        target.state_root, target.acceptance_root, package_.package,
        target.product_version};
    PinnedRepairSource pinned;
    const auto retained = validate_repair_source(
        context, target.package_sha256, &pinned);
    if (!retained.ok)
      return {false, retained.recovery_required, {}, retained.detail};
    const auto reviewed = provider_.review_install_local(plan);
    if (!reviewed.ok || reviewed.outcome_unknown)
      return reviewed;
    std::string detail;
    if (!pinned.revalidate(detail))
      return {false, true, {}, detail};
    const auto applied = provider_.install_local(plan);
    if (!applied.ok || applied.outcome_unknown)
      return applied;
    if (!pinned.revalidate(detail))
      return {false, true, {}, detail};
    return inspect_epoch_clone(source, target);
  }

  facman::self_maintenance::ShellState inspect_epoch_shortcut(
      const facman::self_maintenance::Generation &source,
      const facman::self_maintenance::Generation &target) override {
    return native_.inspect_shortcut(transition(source, target));
  }
  facman::self_maintenance::ShellState inspect_epoch_registration(
      const facman::self_maintenance::Generation &source,
      const facman::self_maintenance::Generation &target) override {
    return native_.inspect_registration(transition(source, target));
  }
  facman::self_maintenance::EffectResult cutover_epoch_shortcut(
      const facman::self_maintenance::Generation &source,
      const facman::self_maintenance::Generation &target) override {
    return native_.cutover_shortcut(transition(source, target));
  }
  facman::self_maintenance::EffectResult cutover_epoch_registration(
      const facman::self_maintenance::Generation &source,
      const facman::self_maintenance::Generation &target) override {
    return native_.cutover_registration(transition(source, target));
  }

private:
  facman::self_maintenance::Plan transition(
      const facman::self_maintenance::Generation &source,
      const facman::self_maintenance::Generation &target) const {
    facman::self_maintenance::Plan plan;
    plan.operation = "bootstrap";
    plan.operation_id = "bootstrap." +
        digest_text(target.install_id + "\n").substr(0, 32);
    plan.source = source;
    plan.target = target;
    plan.package = package_.package;
    plan.package_sha256 = package_.package_sha256;
    plan.provider_operation = "install_local";
    return plan;
  }

  facman::self_maintenance::ProviderBridge &provider_;
  facman::self_maintenance::PackageInspection package_;
  MaintenanceEffects native_;
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

bool same_path(const fs::path &left, const fs::path &right) {
  return _wcsicmp(left.lexically_normal().native().c_str(),
                  right.lexically_normal().native().c_str()) == 0;
}

std::string maintenance_operation_text(
    facman::self_maintenance::Operation operation) {
  switch (operation) {
  case facman::self_maintenance::Operation::update: return "update";
  case facman::self_maintenance::Operation::downgrade: return "downgrade";
  case facman::self_maintenance::Operation::rollback: return "rollback";
  }
  return "update";
}

constexpr char kMaintenanceQualificationMarker[] =
    "facman-self-maintenance-qualification-root-v1\n";

struct MaintenanceQualification {
  facman::platform::StableDirectoryObject acceptance;
  facman::platform::StableInputFile marker;
  facman::platform::StableInputFile permit;
  fs::path install_root;
  fs::path state_root;
  fs::path coordinator_root;

  bool revalidate(std::string &detail) const {
    const auto accepted = acceptance.revalidate();
    const auto marker_status = marker.revalidate_path();
    const auto permit_status = permit.revalidate_path();
    if (!accepted.ok() || !marker_status.ok() || !permit_status.ok()) {
      detail = !accepted.ok() ? accepted.detail
          : !marker_status.ok() ? marker_status.detail : permit_status.detail;
      return false;
    }
    for (const auto &[path, allow_absent] :
         std::vector<std::pair<fs::path, bool>>{
             {install_root, true}, {state_root, false},
             {coordinator_root, true}}) {
      const auto admitted = acceptance.validate_descendant(path, allow_absent);
      if (!admitted.ok() ||
          facman::base::path_crosses_link_or_reparse_point(path, detail)) {
        if (!admitted.ok()) detail = admitted.detail;
        return false;
      }
    }
    detail.clear();
    return true;
  }
};

bool admit_maintenance_qualification(
    Options &options, std::optional<MaintenanceQualification> &qualification,
    std::string &problem) {
  if (!options.maintenance_operation.has_value())
    return !options.qualification_fixture_permit_explicit;
  if (options.shell_integration) {
    if (options.qualification_fixture_permit_explicit) {
      problem = "shell-integrated maintenance does not accept a fixture permit";
      return false;
    }
    return true;
  }
  if (!options.qualification_fixture_permit_explicit) {
    problem = "--no-shell-integration requires an exact qualification fixture permit";
    return false;
  }
  fs::path install_root;
  fs::path state_root;
  fs::path acceptance_root;
  fs::path permit_path;
  if (!normalized_absolute_path(options.install_root, install_root, problem,
                                "install root") ||
      !normalized_absolute_path(options.state_root, state_root, problem,
                                "state root") ||
      !normalized_absolute_path(options.acceptance_root, acceptance_root,
                                problem, "acceptance root") ||
      !normalized_absolute_path(options.qualification_fixture_permit,
                                permit_path, problem,
                                "qualification fixture permit"))
    return false;
  MaintenanceQualification admitted;
  const auto opened = admitted.acceptance.open_no_follow(acceptance_root);
  if (!opened.ok()) {
    problem = "qualification acceptance root is not a stable plain directory";
    return false;
  }
  const fs::path coordinator_root =
      (state_root.parent_path() / "setup-coordinator.v1").lexically_normal();
  const fs::path marker_path =
      acceptance_root / ".facman-self-maintenance-qualification-root.v1";
  if (!validate_qualification_descendant(admitted.acceptance, install_root,
                                          true, problem, "install root") ||
      !validate_qualification_descendant(admitted.acceptance, state_root,
                                          false, problem, "state root") ||
      !validate_qualification_descendant(admitted.acceptance, coordinator_root,
                                          true, problem, "coordinator root") ||
      !validate_qualification_descendant(admitted.acceptance, marker_path,
                                          false, problem, "fixture marker") ||
      !validate_qualification_descendant(admitted.acceptance, permit_path,
                                          false, problem, "fixture permit") ||
      !validate_qualification_direct_child(acceptance_root, marker_path,
                                            problem, "fixture marker") ||
      !validate_qualification_direct_child(acceptance_root, permit_path,
                                            problem, "fixture permit"))
    return false;
  const auto marker_opened = admitted.marker.open_no_follow_pinned(marker_path);
  const auto permit_opened = admitted.permit.open_no_follow_pinned(permit_path);
  const auto marker_bytes = read_stable_input(admitted.marker, 128U);
  const auto permit_bytes = read_stable_input(
      admitted.permit, kQualificationPermitMaximumBytes);
  if (!marker_opened.ok() || !permit_opened.ok() || !marker_bytes ||
      *marker_bytes != kMaintenanceQualificationMarker || !permit_bytes) {
    problem = "qualification fixture marker or permit is absent, unsafe, or changed";
    return false;
  }
  facman::core::json::Limits limits;
  limits.maximum_bytes = kQualificationPermitMaximumBytes;
  limits.maximum_depth = 8U;
  limits.maximum_nodes = 32U;
  limits.maximum_string_bytes = kQualificationPermitMaximumBytes;
  auto document = facman::core::json::parse(*permit_bytes, limits);
  if (!document || !exact_keys(document.value(),
      {"acceptance_root", "apply", "expires_at_unix_seconds",
       "fixture_marker_sha256", "install_root", "issued_at_unix_seconds",
       "nonce", "operation", "product_version", "schema", "state_root"})) {
    problem = "qualification fixture permit has an invalid exact JSON schema";
    return false;
  }
  std::string schema;
  std::string nonce;
  std::string operation;
  std::string product_version;
  std::string permit_install_root;
  std::string permit_state_root;
  std::string permit_acceptance_root;
  std::string marker_digest;
  std::uint64_t issued_at = 0U;
  std::uint64_t expires_at = 0U;
  const auto *apply_value = document.value().find("apply");
  const auto apply = apply_value == nullptr
      ? facman::core::Result<bool>::failure(
            {"qualification", "missing apply claim", ""})
      : apply_value->bool_value();
  const std::string marker_sha256 = facman::base::sha256_hex_bytes(
      reinterpret_cast<const unsigned char *>(marker_bytes->data()),
      marker_bytes->size());
  if (!string_member(document.value(), "schema", schema) ||
      !string_member(document.value(), "nonce", nonce) ||
      !string_member(document.value(), "operation", operation) ||
      !string_member(document.value(), "product_version", product_version) ||
      !string_member(document.value(), "install_root", permit_install_root) ||
      !string_member(document.value(), "state_root", permit_state_root) ||
      !string_member(document.value(), "acceptance_root",
                     permit_acceptance_root) ||
      !string_member(document.value(), "fixture_marker_sha256",
                     marker_digest) ||
      !unsigned_member(document.value(), "issued_at_unix_seconds", issued_at) ||
      !unsigned_member(document.value(), "expires_at_unix_seconds",
                       expires_at) ||
      !apply || schema != "facman.self_maintenance_qualification_fixture.v1" ||
      !lowercase_hex_64(nonce) || marker_digest != marker_sha256) {
    problem = "qualification fixture permit has invalid claims";
    return false;
  }
  const std::uint64_t now = unix_seconds();
  if (expires_at <= issued_at ||
      expires_at - issued_at > kQualificationPermitMaximumLifetimeSeconds ||
      (issued_at > now &&
       issued_at - now > kQualificationPermitMaximumFutureSkewSeconds) ||
      now >= expires_at || apply.value() != options.apply ||
      operation != maintenance_operation_text(*options.maintenance_operation) ||
      product_version != FACMAN_VERSION_SEMVER ||
      permit_install_root != facman::platform::path_to_utf8(install_root) ||
      permit_state_root != facman::platform::path_to_utf8(state_root) ||
      permit_acceptance_root !=
          facman::platform::path_to_utf8(acceptance_root)) {
    problem = "qualification fixture permit does not bind this exact operation";
    return false;
  }
  admitted.install_root = install_root;
  admitted.state_root = state_root;
  admitted.coordinator_root = coordinator_root;
  if (!admitted.revalidate(problem)) {
    problem = "qualification fixture authority changed: " + problem;
    return false;
  }
  options.install_root = install_root;
  options.state_root = state_root;
  options.acceptance_root = acceptance_root;
  qualification.emplace(std::move(admitted));
  return true;
}

constexpr std::uint64_t kMaintenanceHandoffBudgetMs = 600000U;

std::uint64_t maintenance_utc_ms() {
  const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
      std::chrono::system_clock::now().time_since_epoch()).count();
  return elapsed > 0 ? static_cast<std::uint64_t>(elapsed) : 0;
}

bool extract_target_maintenance_launcher(
    const facman::self_maintenance::PackageInspection &package,
    MaterializedPackage &target_launcher, std::string &problem) {
  wchar_t temporary_root[MAX_PATH + 1]{};
  wchar_t temporary_file[MAX_PATH + 1]{};
  if (GetTempPathW(MAX_PATH, temporary_root) == 0 ||
      GetTempFileNameW(temporary_root, L"fmm", 0, temporary_file) == 0) {
    problem = "Windows could not allocate target launcher staging";
    return false;
  }
  target_launcher.temporary = fs::path(temporary_file);
  std::error_code removed;
  fs::remove(target_launcher.temporary, removed);
  if (removed) {
    problem = "target launcher staging could not be prepared: " +
        removed.message();
    return false;
  }
  auto extracted = facman::self_maintenance::extract_maintenance_launcher(
      package, target_launcher.temporary);
  if (!extracted) {
    problem = extracted.error().message;
    if (!extracted.error().detail.empty())
      problem += ": " + extracted.error().detail;
    return false;
  }
  target_launcher.path = target_launcher.temporary;
  return true;
}

std::optional<std::string> exact_regular_file_digest(
    const fs::path &path, std::string &problem) {
  facman::platform::StableInputFile input;
  const auto opened = input.open_no_follow_pinned(path);
  if (!opened.ok() || !input.identity().regular_file ||
      input.identity().link_count != 1U || input.size() == 0U ||
      input.size() > kMaximumRepairLauncherBytes) {
    problem = opened.ok() ? "file identity is not an admitted regular file"
                          : opened.detail;
    return std::nullopt;
  }
  auto digest = digest_stable_input(input);
  if (!digest || !input.revalidate().ok() || !input.revalidate_path().ok()) {
    problem = "file identity changed while it was hashed";
    return std::nullopt;
  }
  return digest;
}

bool derive_continuation_coordinator(const ContinuationOptions &options,
                                     fs::path &coordinator,
                                     std::string &problem) {
  const fs::path operation = options.journal.parent_path();
  const fs::path maintenance = operation.parent_path();
  const fs::path epoch = maintenance.parent_path();
  const fs::path epochs = epoch.parent_path();
  coordinator = epochs.parent_path();
  std::string identifier_detail;
  if (options.journal.filename() != "00-handoff-ready.v3.json" ||
      operation.filename() != fs::path(options.operation_id) ||
      maintenance.filename() != "maintenance" || epochs.filename() != "epochs" ||
      coordinator.empty() || !coordinator.is_absolute() ||
      !facman::base::validate_identifier(options.operation_id,
                                         identifier_detail) ||
      !facman::base::validate_identifier(options.nonce, identifier_detail) ||
      !lowercase_hex_64(epoch.filename().string())) {
    problem = "private continuation journal does not have the canonical epoch path";
    return false;
  }
  const fs::path expected = coordinator / "epochs" / epoch.filename() /
      "maintenance" / options.operation_id / "00-handoff-ready.v3.json";
  if (expected.lexically_normal() != options.journal) {
    problem = "private continuation journal path is not canonical";
    return false;
  }
  return true;
}

facman::setup::handoff::Result launch_continuation_helper(
    const facman::self_maintenance::EpochTransitionPreparation &prepared) {
  const std::uint64_t now = GetTickCount64();
  std::uint64_t remaining = kMaintenanceHandoffBudgetMs;
  if (prepared.deadline_utc_ms != 0) {
    const std::uint64_t utc_now = maintenance_utc_ms();
    if (utc_now == 0 || utc_now >= prepared.deadline_utc_ms)
      return {false, "maintenance handoff operation deadline has expired"};
    remaining = (std::min)(remaining, prepared.deadline_utc_ms - utc_now);
  }
  if (now > (std::numeric_limits<std::uint64_t>::max)() - remaining)
    return {false, "maintenance handoff deadline overflow"};
  return facman::setup::handoff::launch({prepared.inputs.helper,
      prepared.inputs.helper_sha256, prepared.journal, prepared.journal_sha256,
      prepared.transition.operation_id, prepared.nonce,
      now + remaining});
}

int run_private_continuation(const ContinuationOptions &options) {
  const auto waited = facman::setup::handoff::wait_for_initiator(
      {options.parent_handle, options.parent_pid, options.parent_created,
       options.deadline_tick_ms});
  if (!waited.ok) return 4;

  fs::path coordinator_root;
  std::string problem;
  if (!derive_continuation_coordinator(options, coordinator_root, problem) ||
      GetTickCount64() >= options.deadline_tick_ms)
    return 4;
  auto pending =
      facman::self_maintenance::discover_lifecycle_epoch_pending_transition(
          coordinator_root);
  if (!pending || !pending.value().has_value()) return 4;
  const auto &transition = *pending.value();
  if (transition.pre_handoff || transition.completed ||
      transition.operation_id != options.operation_id ||
      transition.nonce != options.nonce ||
      transition.journal_sha256 != options.journal_sha256 ||
      (transition.deadline_utc_ms != 0 &&
       maintenance_utc_ms() >= transition.deadline_utc_ms))
    return 4;

  auto executable = current_executable_path(problem);
  auto executable_digest = executable
      ? exact_regular_file_digest(*executable, problem)
      : std::optional<std::string>{};
  if (!executable || !executable_digest ||
      !same_path(*executable, transition.retained_inputs.helper) ||
      *executable_digest != transition.retained_inputs.helper_sha256)
    return 4;

  MaterializedPackage target_launcher;
  if (!extract_target_maintenance_launcher(
          transition.retained_package, target_launcher, problem) ||
      GetTickCount64() >= options.deadline_tick_ms ||
      (transition.deadline_utc_ms != 0 &&
       maintenance_utc_ms() >= transition.deadline_utc_ms))
    return 4;
  facman::self_maintenance::ProviderBridge provider(
      transition.target.state_root, transition.target.acceptance_root);
  MaintenanceEffects effects(provider, transition.target.state_root,
      transition.target.acceptance_root, target_launcher.path,
      transition.retained_package.maintenance_launcher_sha256,
      transition.shell_integration);

  std::string phase = transition.phase;
  if (phase == "continuation_pending") {
    auto continued = facman::self_maintenance::execute_lifecycle_epoch_continuation(
        {coordinator_root, options.operation_id, options.nonce,
         options.journal_sha256, true}, effects);
    if (!continued) return 4;
    phase = "publication_pending";
  }
  if (GetTickCount64() >= options.deadline_tick_ms ||
      (transition.deadline_utc_ms != 0 &&
       maintenance_utc_ms() >= transition.deadline_utc_ms)) return 4;
  if (phase == "publication_pending") {
    auto published = facman::self_maintenance::execute_lifecycle_epoch_publication(
        {coordinator_root, options.operation_id, options.nonce,
         options.journal_sha256, true},
        static_cast<facman::self_maintenance::EpochContinuationEffects &>(effects));
    if (!published) return 4;
    phase = "shell_cutover_pending";
  }
  if (GetTickCount64() >= options.deadline_tick_ms ||
      (transition.deadline_utc_ms != 0 &&
       maintenance_utc_ms() >= transition.deadline_utc_ms)) return 4;
  if (phase == "shell_cutover_pending") {
    auto shell = facman::self_maintenance::execute_lifecycle_epoch_shell_cutover(
        {coordinator_root, options.operation_id, options.nonce,
         options.journal_sha256, true}, effects);
    if (!shell || shell.value().phase != "shell_cutover_complete") return 4;
    phase = shell.value().phase;
  }
  return phase == "shell_cutover_complete" ? 0 : 4;
}

int run_maintenance(Options &options, const fs::path &,
                    MaintenanceQualification *qualification) {
  const auto operation = *options.maintenance_operation;
  const fs::path coordinator_root =
      (options.state_root.parent_path() / "setup-coordinator.v1")
          .lexically_normal();
  if (!options.shell_integration) {
    std::string detail;
    if (qualification == nullptr || !qualification->revalidate(detail)) {
      print_maintenance_error(
          {"self_maintenance_qualification_invalid",
           "no-shell maintenance qualification changed", detail},
          options.json);
      return 4;
    }
  }
  // This read-side preflight is deliberately before package materialization:
  // an epoch makes rollback invalid and must not fall through to any legacy
  // preparation work.  The epoch is discovered again under normal authority
  // below before it is used.
  auto pending_preflight =
      facman::self_maintenance::discover_lifecycle_epoch_pending_transition(
          coordinator_root);
  if (!pending_preflight) {
    print_maintenance_error(pending_preflight.error(), options.json);
    return 4;
  }
  bool epoch_present_preflight = pending_preflight.value().has_value();
  if (!epoch_present_preflight) {
    auto epoch_preflight = facman::self_maintenance::discover_lifecycle_epoch_chain(
        coordinator_root);
    if (!epoch_preflight) {
      print_maintenance_error(epoch_preflight.error(), options.json);
      return 4;
    }
    epoch_present_preflight = !epoch_preflight.value().epochs.empty() &&
        !epoch_preflight.value().epochs.back().compatibility_epoch;
  }
  if (epoch_present_preflight &&
      operation == facman::self_maintenance::Operation::rollback) {
    print_maintenance_error({"self_maintenance_rollback_invalid",
                 "rollback is not defined across an authoritative lifecycle epoch", ""},
                options.json);
    return 4;
  }
  if (epoch_present_preflight && !pending_preflight.value().has_value()) {
    auto selected = facman::self_maintenance::resolve_authoritative_active_state(
        coordinator_root);
    if (!selected || !selected.value().has_value() ||
        !selected.value()->epoch.has_value()) {
      print_maintenance_error(!selected ? selected.error() :
          facman::core::Error{"self_maintenance_epoch_recovery_required",
              "real epoch is not yet authoritative for maintenance", {}},
          options.json);
      return 4;
    }
  }
  std::optional<facman::self_maintenance::PackageInspection> package;
  SetupPackageMaterializer materializer;
  MaterializedPackage target_launcher;
  fs::path launcher;
  if (operation != facman::self_maintenance::Operation::rollback &&
      (!pending_preflight.value().has_value() || options.package_explicit)) {
    std::error_code status;
    const fs::path source = fs::absolute(options.package, status).lexically_normal();
    if (status) {
      print_maintenance_error({"self_maintenance_package_incompatible",
                   "maintenance package path is invalid", status.message()},
                  options.json);
      return 4;
    }
    auto materialized = materializer.materialize(source);
    if (!materialized) {
      print_maintenance_error(materialized.error(), options.json);
      return 4;
    }
    auto inspected = facman::self_maintenance::inspect_package(
        materialized.value());
    if (!inspected) {
      print_maintenance_error(inspected.error(), options.json);
      return 4;
    }
    package = inspected.take_value();
    // Preview reaches only the provider review in the epoch path.  It needs
    // the package inspection but must not create a launcher staging file.
    if (options.apply || !epoch_present_preflight) {
      wchar_t temporary_root[MAX_PATH + 1]{};
      wchar_t temporary_file[MAX_PATH + 1]{};
      if (GetTempPathW(MAX_PATH, temporary_root) == 0 ||
          GetTempFileNameW(temporary_root, L"fmm", 0, temporary_file) == 0) {
        print_maintenance_error({"self_maintenance_launcher_invalid",
                     "Windows could not allocate target launcher staging", ""},
                    options.json);
        return 4;
      }
      target_launcher.temporary = fs::path(temporary_file);
      std::error_code removed;
      fs::remove(target_launcher.temporary, removed);
      if (removed) {
        print_maintenance_error({"self_maintenance_launcher_invalid",
                     "target launcher staging could not be prepared",
                     removed.message()}, options.json);
        return 4;
      }
      auto extracted = facman::self_maintenance::extract_maintenance_launcher(
          *package, target_launcher.temporary);
      if (!extracted) {
        print_maintenance_error(extracted.error(), options.json);
        return 4;
      }
      target_launcher.path = target_launcher.temporary;
      launcher = target_launcher.path;
    }
  }

  facman::platform::StableDirectoryObject maintenance_acceptance;
  const auto acceptance_opened = maintenance_acceptance.open_no_follow(
      options.acceptance_root);
  if (!acceptance_opened.ok() ||
      !maintenance_acceptance.validate_descendant(
          options.state_root, false).ok() ||
      !maintenance_acceptance.validate_descendant(
          coordinator_root, true).ok()) {
    print_maintenance_error(
        {"self_maintenance_provider_root_unsafe",
         "maintenance state and coordinator roots are outside stable acceptance authority",
         acceptance_opened.detail}, options.json);
    return 4;
  }
  const auto authority_stable = [&](std::string &detail) {
    const auto accepted = maintenance_acceptance.revalidate();
    const auto state = maintenance_acceptance.validate_descendant(
        options.state_root, false);
    const auto coordinator = maintenance_acceptance.validate_descendant(
        coordinator_root, true);
    if (!accepted.ok() || !state.ok() || !coordinator.ok()) {
      detail = !accepted.ok() ? accepted.detail
          : !state.ok() ? state.detail : coordinator.detail;
      return false;
    }
    if (facman::base::path_crosses_link_or_reparse_point(
            coordinator_root, detail))
      return false;
    if (qualification != nullptr && !qualification->revalidate(detail))
      return false;
    detail.clear();
    return true;
  };

  facman::self_maintenance::ProviderBridge provider(
      options.state_root, options.acceptance_root);
  const auto same_epoch_package = [](const facman::self_maintenance::PackageInspection &left,
                                     const facman::self_maintenance::PackageInspection &right) {
    const auto &a = left.descriptor;
    const auto &b = right.descriptor;
    return left.package_sha256 == right.package_sha256 &&
        left.maintenance_launcher_sha256 == right.maintenance_launcher_sha256 &&
        a.product_id == b.product_id && a.product_version == b.product_version &&
        a.generation_relative_path == b.generation_relative_path &&
        a.facman_source_revision == b.facman_source_revision &&
        a.universal_setup_revision == b.universal_setup_revision &&
        a.setup_protocol == b.setup_protocol && a.package_layout == b.package_layout &&
        a.gui_relative_path == b.gui_relative_path && a.cli_relative_path == b.cli_relative_path &&
        a.maintenance_relative_path == b.maintenance_relative_path &&
        a.automatic_update == b.automatic_update;
  };
  auto pending_epoch =
      facman::self_maintenance::discover_lifecycle_epoch_pending_transition(
          coordinator_root);
  if (!pending_epoch) {
    print_maintenance_error(pending_epoch.error(), options.json);
    return 4;
  }
  if (!pending_epoch.value().has_value()) {
    auto terminal_epoch =
        facman::self_maintenance::discover_lifecycle_epoch_terminal_transition(
            coordinator_root);
    if (!terminal_epoch) {
      print_maintenance_error(terminal_epoch.error(), options.json);
      return 4;
    }
    pending_epoch = std::move(terminal_epoch);
  }
  const bool pending_is_new_request = pending_epoch.value().has_value() &&
      pending_epoch.value()->completed && package.has_value() &&
      (operation != pending_epoch.value()->operation ||
       !same_epoch_package(*package, pending_epoch.value()->retained_package));
  if (pending_epoch.value().has_value() && !pending_epoch.value()->pre_handoff &&
      !pending_is_new_request) {
    const auto &pending = *pending_epoch.value();
    if (operation != pending.operation) {
      print_maintenance_error({"self_maintenance_epoch_recovery_required",
                   "requested maintenance operation does not match the pending epoch handoff",
                   pending.operation_id}, options.json);
      return 4;
    }
    if (package.has_value() && !same_epoch_package(*package, pending.retained_package)) {
      print_maintenance_error({"self_maintenance_epoch_recovery_required",
          "requested package does not match the immutable pending epoch handoff",
          pending.operation_id}, options.json);
      return 4;
    }
    if (!same_path(pending.target.logical_root, options.install_root) ||
        !same_path(pending.target.state_root, options.state_root) ||
        !same_path(pending.target.acceptance_root, options.acceptance_root)) {
      print_maintenance_error({"self_maintenance_lineage_mismatch",
          "pending epoch target does not belong to the configured maintenance lineage",
          facman::platform::path_to_utf8(pending.target.logical_root)}, options.json);
      return 4;
    }
    if (options.shell_integration != pending.shell_integration) {
      print_maintenance_error({"self_maintenance_epoch_recovery_required",
          "requested shell integration does not match the immutable pending handoff",
          pending.operation_id}, options.json);
      return 4;
    }
    MaintenanceEffects effects(provider, options.state_root,
                               options.acceptance_root, {},
                               pending.retained_package.maintenance_launcher_sha256,
                               pending.shell_integration);
    std::string authority_detail;
    if (!authority_stable(authority_detail)) {
      print_maintenance_error({"self_maintenance_provider_root_unsafe",
          "maintenance authority changed before pending epoch recovery", authority_detail},
          options.json);
      return 4;
    }
    std::string phase = pending.phase;
    std::string nonce = pending.nonce;
    std::string journal_sha256 = pending.journal_sha256;
    facman::self_maintenance::Generation reported = pending.target;
    if (pending.completed && options.apply) {
      if (!authority_stable(authority_detail)) {
        print_maintenance_error({"self_maintenance_provider_root_unsafe",
            "maintenance authority changed before terminal epoch shell retry", authority_detail},
            options.json);
        return 4;
      }
      auto shell = facman::self_maintenance::execute_lifecycle_epoch_shell_cutover(
          {coordinator_root, pending.operation_id, nonce, journal_sha256, true}, effects);
      if (!shell) {
        print_maintenance_error(shell.error(), options.json);
        return 4;
      }
      reported = shell.value().generation;
      phase = shell.value().phase;
    }
    if (options.apply && phase == "handoff_staging") {
      facman::self_maintenance::EpochTransitionRequest request{
          coordinator_root, pending.epoch_id, pending.operation,
          pending.operation_id,
          pending.retained_package, true, {}, {}, true};
      request.continuation_helper = pending.retained_inputs.helper;
      request.continuation_helper_sha256 =
          pending.retained_inputs.helper_sha256;
      request.shell_integration = pending.shell_integration;
      request.deadline_utc_ms = pending.deadline_utc_ms;
      auto prepared = facman::self_maintenance::prepare_lifecycle_epoch_transition(
          request, effects);
      if (!prepared) {
        print_maintenance_error(prepared.error(), options.json);
        return 4;
      }
      nonce = prepared.value().nonce;
      journal_sha256 = prepared.value().journal_sha256;
      reported = prepared.value().transition.target;
      phase = "continuation_pending";
    }
    if (options.apply && !pending.completed && phase != "handoff_staging") {
      if (phase != "continuation_pending" && phase != "publication_pending" &&
          phase != "shell_cutover_pending") {
        print_maintenance_error({"self_maintenance_epoch_recovery_required",
            "pending epoch is not at an externally continuable phase", phase},
            options.json);
        return 4;
      }
      if (!authority_stable(authority_detail)) {
        print_maintenance_error({"self_maintenance_provider_root_unsafe",
            "maintenance authority changed before external helper launch", authority_detail},
            options.json);
        return 4;
      }
      facman::self_maintenance::EpochTransitionPreparation prepared;
      prepared.phase = "handoff_ready";
      prepared.transition.operation_id = pending.operation_id;
      prepared.transition.target = pending.target;
      prepared.journal = coordinator_root / "epochs" / pending.epoch_id /
          "maintenance" / pending.operation_id / "00-handoff-ready.v3.json";
      prepared.journal_sha256 = journal_sha256;
      prepared.inputs = pending.retained_inputs;
      prepared.nonce = nonce;
      prepared.deadline_utc_ms = pending.deadline_utc_ms;
      const auto launched = launch_continuation_helper(prepared);
      if (!launched.ok) {
        print_maintenance_error({"self_maintenance_epoch_recovery_required",
            "external maintenance helper could not be launched", launched.detail},
            options.json);
        return 4;
      }
      phase = "handoff_launched";
    }
    const fs::path epoch_root = coordinator_root / "epochs" / pending.epoch_id;
    const fs::path generation_record = reported.generation_id.empty() ? fs::path() :
        epoch_root / "generations" / ("generation." + reported.generation_id + ".v2.json");
    const fs::path activation_record = reported.generation_id.empty() ? fs::path() :
        epoch_root / "activations" / ("activation." + pending.operation_id + ".v2.json");
    if (options.json) {
      facman::core::json::ObjectBuilder output;
      output.add_string("schema", "facman.self_maintenance_cli.v1");
      output.add_string("status", "ok");
      output.add_string("operation", maintenance_operation_text(operation));
      output.add_string("phase", phase);
      output.add_string("operation_id", pending.operation_id);
      output.add_string("generation_id", reported.generation_id);
      output.add_string("product_version", reported.product_version);
      output.add_string("install_id", reported.install_id);
      output.add_string("install_root", facman::platform::path_to_utf8(reported.install_root));
      output.add_string("generation_record", facman::platform::path_to_utf8(generation_record));
      output.add_string("activation_record", facman::platform::path_to_utf8(activation_record));
      std::cout << output.serialize() << '\n';
    } else {
      std::cout << "FacManSetup " << maintenance_operation_text(operation) << ' ' << phase << '\n';
    }
    return 0;
  }
  // Epoch state is authoritative once it exists.  Do not let an incomplete
  // or malformed epoch fall through to the flat v1 coordinator path.
  auto epoch_chain = facman::self_maintenance::discover_lifecycle_epoch_chain(
      coordinator_root);
  if (!epoch_chain) {
    print_maintenance_error(epoch_chain.error(), options.json);
    return 4;
  }
  const bool has_real_epoch = !epoch_chain.value().epochs.empty() &&
      !epoch_chain.value().epochs.back().compatibility_epoch;
  if (has_real_epoch) {
    auto epoch_active = facman::self_maintenance::discover_lifecycle_epoch_active(
        coordinator_root);
    if (!epoch_active) {
      print_maintenance_error(epoch_active.error(), options.json);
      return 4;
    }
    if (pending_epoch.value().has_value() && pending_epoch.value()->pre_handoff &&
        (pending_epoch.value()->epoch_id != epoch_active.value().epoch.epoch_id ||
         pending_epoch.value()->target.generation_id !=
             epoch_active.value().active.active.generation_id ||
         pending_epoch.value()->source_activation_name !=
             epoch_active.value().active.activation_name ||
         pending_epoch.value()->source_activation_sha256 !=
             epoch_active.value().active.activation_sha256)) {
      print_maintenance_error({"self_maintenance_epoch_recovery_required",
          "pre-handoff epoch source changed before deterministic request admission", ""}, options.json);
      return 4;
    }
    if (!same_path(epoch_active.value().active.active.logical_root, options.install_root) ||
        !same_path(epoch_active.value().active.active.state_root, options.state_root) ||
        !same_path(epoch_active.value().active.active.acceptance_root,
                   options.acceptance_root)) {
      print_maintenance_error({"self_maintenance_lineage_mismatch",
                   "configured roots do not identify the active epoch lineage",
                   facman::platform::path_to_utf8(
                       epoch_active.value().active.active.logical_root)}, options.json);
      return 4;
    }
    if (operation == facman::self_maintenance::Operation::rollback) {
      print_maintenance_error({"self_maintenance_rollback_invalid",
                   "rollback is not defined across an authoritative lifecycle epoch", ""},
                  options.json);
      return 4;
    }
    if (!package.has_value()) {
      print_maintenance_error({"self_maintenance_input_invalid",
                   "epoch maintenance requires an exact package inspection", ""}, options.json);
      return 4;
    }

    const std::string operation_id = "maint." + maintenance_operation_text(operation) + "." +
        epoch_active.value().active.active.generation_id.substr(0, 8) + "." +
        package->package_sha256.substr(0, 20);
    if (pending_epoch.value().has_value() && pending_epoch.value()->pre_handoff &&
        !pending_epoch.value()->operation_id.empty() &&
        pending_epoch.value()->operation_id != operation_id) {
      print_maintenance_error({"self_maintenance_epoch_recovery_required",
          "empty epoch operation does not match this deterministic maintenance request",
          pending_epoch.value()->operation_id}, options.json);
      return 4;
    }
    facman::self_maintenance::EpochTransitionRequest epoch_request;
    epoch_request.coordinator_root = coordinator_root;
    epoch_request.epoch_id = epoch_active.value().epoch.epoch_id;
    epoch_request.operation = operation;
    epoch_request.operation_id = operation_id;
    epoch_request.package = *package;
    epoch_request.apply = options.apply;
    epoch_request.shell_integration = options.shell_integration;
    if (options.apply) {
      const std::uint64_t now = maintenance_utc_ms();
      if (now == 0 || now > (std::numeric_limits<std::uint64_t>::max)() -
                              kMaintenanceHandoffBudgetMs) {
        print_maintenance_error({"self_maintenance_epoch_recovery_required",
            "maintenance operation deadline could not be established", ""},
            options.json);
        return 4;
      }
      epoch_request.deadline_utc_ms = now + kMaintenanceHandoffBudgetMs;
      std::string helper_problem;
      auto current_helper = current_executable_path(helper_problem);
      auto current_helper_sha256 = current_helper
          ? exact_regular_file_digest(*current_helper, helper_problem)
          : std::optional<std::string>{};
      if (!current_helper || !current_helper_sha256) {
        print_maintenance_error({"self_maintenance_launcher_invalid",
            "current setup binary cannot be retained for continuation",
            helper_problem}, options.json);
        return 4;
      }
      epoch_request.continuation_helper = *current_helper;
      epoch_request.continuation_helper_sha256 = *current_helper_sha256;
    }
    MaintenanceEffects effects(provider, options.state_root,
                               options.acceptance_root, launcher,
                               package->maintenance_launcher_sha256,
                               options.shell_integration);
    std::string authority_detail;
    if (!authority_stable(authority_detail)) {
      print_maintenance_error(
          {"self_maintenance_provider_root_unsafe",
           "maintenance authority changed before epoch preparation", authority_detail},
          options.json);
      return 4;
    }
    auto prepared = facman::self_maintenance::prepare_lifecycle_epoch_transition(
        epoch_request, effects);
    if (!prepared) {
      print_maintenance_error(prepared.error(), options.json);
      return 4;
    }

    facman::self_maintenance::Generation reported = prepared.value().transition.target;
    std::string phase = prepared.value().phase;
    fs::path generation_record;
    fs::path activation_record;
    if (options.apply) {
      if (!authority_stable(authority_detail)) {
        print_maintenance_error(
            {"self_maintenance_provider_root_unsafe",
             "maintenance authority changed before external helper launch", authority_detail},
            options.json);
        return 4;
      }
      const auto launched = launch_continuation_helper(prepared.value());
      if (!launched.ok) {
        print_maintenance_error({"self_maintenance_epoch_recovery_required",
            "external maintenance helper could not be launched", launched.detail},
            options.json);
        return 4;
      }
      phase = "handoff_launched";
    }
    if (options.json) {
      facman::core::json::ObjectBuilder output;
      output.add_string("schema", "facman.self_maintenance_cli.v1");
      output.add_string("status", "ok");
      output.add_string("operation", maintenance_operation_text(operation));
      output.add_string("phase", phase);
      output.add_string("operation_id", operation_id);
      output.add_string("generation_id", reported.generation_id);
      output.add_string("product_version", reported.product_version);
      output.add_string("install_id", reported.install_id);
      output.add_string("install_root", facman::platform::path_to_utf8(reported.install_root));
      output.add_string("generation_record", facman::platform::path_to_utf8(generation_record));
      output.add_string("activation_record", facman::platform::path_to_utf8(activation_record));
      std::cout << output.serialize() << '\n';
    } else {
      std::cout << "FacManSetup " << maintenance_operation_text(operation) << ' ' << phase
                << ":\n  generation " << reported.generation_id << "\n  root "
                << facman::platform::path_to_utf8(reported.install_root) << '\n';
      if (!options.apply)
        std::cout << "Review the plan, then repeat with --yes to apply it.\n";
    }
    return 0;
  }
  auto selected = facman::self_maintenance::resolve_authoritative_active_state(
      coordinator_root);
  if (!selected) {
    print_maintenance_error(selected.error(), options.json);
    return 4;
  }

  facman::self_maintenance::ActiveState state;
  bool migrate_legacy = false;
  if (selected.value().has_value()) {
    if (selected.value()->epoch.has_value()) {
      print_maintenance_error({"self_maintenance_epoch_recovery_required",
          "real epoch appeared before flat maintenance selection", ""}, options.json);
      return 4;
    }
    state = selected.value()->active;
    if (!same_path(state.active.logical_root, options.install_root) ||
        !same_path(state.active.state_root, options.state_root) ||
        !same_path(state.active.acceptance_root, options.acceptance_root)) {
      print_maintenance_error({"self_maintenance_lineage_mismatch",
                   "configured roots do not identify the active FacMan lineage",
                   facman::platform::path_to_utf8(state.active.logical_root)},
                  options.json);
      return 4;
    }
  } else {
    auto descriptor = facman::self_maintenance::inspect_legacy_descriptor(
        options.install_root);
    auto identity = provider.inspect_identity("facman.self");
    if (!descriptor || !identity) {
      print_maintenance_error(!descriptor ? descriptor.error() : identity.error(),
                  options.json);
      return 4;
    }
    if (!same_path(identity.value().install_root, options.install_root) ||
        identity.value().product_version != descriptor.value().product_version ||
        identity.value().provider_revision !=
            descriptor.value().universal_setup_revision ||
        identity.value().provider_revision !=
            facman::self_setup::provider_revision()) {
      print_maintenance_error({"self_maintenance_legacy_invalid",
                   "legacy package and provider identities do not agree", ""},
                  options.json);
      return 4;
    }
    auto generation = facman::self_maintenance::make_generation(
        descriptor.value(), identity.value().source_archive_sha256,
        "facman.self", options.install_root, options.install_root,
        options.state_root, options.acceptance_root);
    if (!generation) {
      print_maintenance_error(generation.error(), options.json);
      return 4;
    }
    facman::self_maintenance::Plan legacy_plan;
    legacy_plan.operation = "migration";
    legacy_plan.operation_id =
        "migration." + generation.value().generation_id.substr(0, 32);
    legacy_plan.source = generation.value();
    legacy_plan.target = generation.value();
    const auto inspected_legacy = provider.inspect_installed(legacy_plan);
    const auto verified_legacy = provider.verify_installed(legacy_plan);
    if (!inspected_legacy.ok || !verified_legacy.ok) {
      facman::core::Error error{
          "self_maintenance_legacy_invalid",
          "legacy installation could not be inspected and verified", ""};
      error.detail = "inspect=" + inspected_legacy.detail +
          "; verify=" + verified_legacy.detail;
      print_maintenance_error(error, options.json);
      return 4;
    }
    auto predicted = facman::self_maintenance::adopt_legacy(
        coordinator_root, generation.value(), false);
    if (!predicted) {
      print_maintenance_error(predicted.error(), options.json);
      return 4;
    }
    state = predicted.take_value();
    migrate_legacy = true;
  }

  if (operation == facman::self_maintenance::Operation::rollback &&
      !state.previous.has_value()) {
    print_maintenance_error({"self_maintenance_rollback_invalid",
                 "the active generation has no retained predecessor", ""},
                options.json);
    return 4;
  }

  facman::self_maintenance::Request request;
  request.operation = operation;
  request.coordinator_root = coordinator_root;
  request.logical_root = state.active.logical_root;
  request.state_root = state.active.state_root;
  request.acceptance_root = state.active.acceptance_root;
  request.active = state.active;
  request.previous_activation_name = state.activation_name;
  request.previous_activation_sha256 = state.activation_sha256;
  if (state.previous.has_value())
    request.rollback_target = *state.previous;
  const std::string target_identity = operation ==
          facman::self_maintenance::Operation::rollback
      ? state.previous->generation_id
      : package->package_sha256;
  request.operation_id = "maint." +
      maintenance_operation_text(operation) + "." +
      state.active.generation_id.substr(0, 8) + "." +
      target_identity.substr(0, 20);
  if (operation != facman::self_maintenance::Operation::rollback) {
    request.package = package->package;
    request.package_sha256 = package->package_sha256;
    request.package_descriptor = package->descriptor;
  }
  request.apply = options.apply;

  auto reviewed = facman::self_maintenance::plan(request);
  if (!reviewed) {
    print_maintenance_error(reviewed.error(), options.json);
    return 4;
  }
  MaintenanceEffects effects(provider, options.state_root,
                             options.acceptance_root, launcher,
                             package.has_value()
                                 ? package->maintenance_launcher_sha256
                                 : std::string(),
                             options.shell_integration);
  if (options.apply && migrate_legacy) {
    const auto admitted = effects.review_install_local(reviewed.value());
    if (!admitted.ok) {
      facman::core::Error error{
          "self_maintenance_plan_failed",
          "candidate installation plan was refused before legacy adoption", ""};
      error.detail = admitted.detail;
      print_maintenance_error(error, options.json);
      return 4;
    }
    std::string authority_detail;
    if (!authority_stable(authority_detail)) {
      print_maintenance_error(
          {"self_maintenance_provider_root_unsafe",
           "maintenance authority changed before legacy adoption",
           authority_detail}, options.json);
      return 4;
    }
    auto adopted = facman::self_maintenance::adopt_legacy(
        coordinator_root, state.active, true);
    if (!adopted) {
      print_maintenance_error(adopted.error(), options.json);
      return 4;
    }
    state = adopted.take_value();
    request.active = state.active;
    request.previous_activation_name = state.activation_name;
    request.previous_activation_sha256 = state.activation_sha256;
  }

  std::string authority_detail;
  if (!authority_stable(authority_detail)) {
    print_maintenance_error(
        {"self_maintenance_provider_root_unsafe",
         "maintenance authority changed before execution", authority_detail},
        options.json);
    return 4;
  }
  auto response = facman::self_maintenance::execute(request, effects);
  if (!response) {
    print_maintenance_error(response.error(), options.json);
    return 4;
  }
  const auto &reported_generation = response.value().phase == "plan"
      ? reviewed.value().target : response.value().active;
  if (options.json) {
    facman::core::json::ObjectBuilder output;
    output.add_string("schema", "facman.self_maintenance_cli.v1");
    output.add_string("status", "ok");
    output.add_string("operation", response.value().operation);
    output.add_string("phase", response.value().phase);
    output.add_string("operation_id", response.value().operation_id);
    output.add_string("generation_id", reported_generation.generation_id);
    output.add_string("product_version", reported_generation.product_version);
    output.add_string("install_id", reported_generation.install_id);
    output.add_string("install_root", facman::platform::path_to_utf8(
        reported_generation.install_root));
    output.add_string("generation_record", facman::platform::path_to_utf8(
        response.value().generation_record));
    output.add_string("activation_record", facman::platform::path_to_utf8(
        response.value().activation_record));
    std::cout << output.serialize() << '\n';
  } else {
    std::cout << "FacManSetup " << response.value().operation << ' '
              << response.value().phase << ":\n  generation "
              << reported_generation.generation_id << "\n  root "
              << facman::platform::path_to_utf8(
                     reported_generation.install_root)
              << '\n';
    if (!options.apply)
      std::cout << "Review the plan, then repeat with --yes to apply it.\n";
  }
  return 0;
}

class SetupRetirementEffects final
    : public facman::self_maintenance::RetirementEffects {
public:
  SetupRetirementEffects(const Options &options, fs::path coordinator_root,
                         SetupNativeEffects &native_effects,
                         bool preserve_repair_sources = false)
      : options_(options), coordinator_root_(std::move(coordinator_root)),
        native_effects_(native_effects),
        preserve_repair_sources_(preserve_repair_sources) {}

  facman::core::Result<void> inspect_retirement_generation(
      const facman::self_maintenance::Generation &generation,
      bool active,
      const facman::self_maintenance::CoordinatorLockToken
          &coordinator_lock) override {
    auto pending = facman::self_setup::has_pending_operation(
        generation.install_root, coordinator_root_);
    if (!pending)
      return facman::core::Result<void>::failure(pending.error());
    if (pending.value())
      return facman::core::Result<void>::failure(
          {"self_setup_recovery_required",
           "generation has an unresolved nested setup journal", generation.install_id});
    facman::self_maintenance::ProviderBridge provider(
        generation.state_root, generation.acceptance_root);
    auto inspected = provider.inspect_identity(generation.install_id);
    if (!inspected ||
        !same_path(inspected.value().install_root, generation.install_root) ||
        inspected.value().product_version != generation.product_version ||
        inspected.value().source_archive_sha256 != generation.package_sha256 ||
        inspected.value().provider_revision != generation.universal_setup_revision)
      return facman::core::Result<void>::failure(
          {"self_maintenance_provider_identity_ambiguous",
           "provider installed identity does not exactly bind the generation",
           inspected ? generation.install_id : inspected.error().detail});
    facman::self_setup::Request preview;
    preview.operation = facman::self_setup::Operation::uninstall;
    preview.install_id = generation.install_id;
    preview.maintenance_launcher = generation.maintenance_launcher;
    preview.install_root = generation.install_root;
    preview.state_root = generation.state_root;
    preview.acceptance_root = generation.acceptance_root;
    preview.product_version = generation.product_version;
    preview.apply = false;
    preview.coordinator_lock = &coordinator_lock;
    if (active && options_.shell_integration)
      preview.native_effects = &native_effects_;
    auto planned = facman::self_setup::execute(preview);
    if (!planned || planned.value().phase != "plan")
      return facman::core::Result<void>::failure(
          !planned ? planned.error() : facman::core::Error{
              "self_maintenance_provider_identity_ambiguous",
              "provider uninstall preview did not return a plan",
              generation.install_id});
    return facman::core::Result<void>::success();
  }

  facman::core::Result<void> uninstall_generation(
      const facman::self_maintenance::Generation &generation,
      bool active,
      const facman::self_maintenance::CoordinatorLockToken
          &coordinator_lock) override {
    const facman::self_setup::NativeContext retirement_context{
        facman::self_setup::Operation::uninstall,
        generation.install_root,
        generation.state_root,
        generation.acceptance_root,
        generation.state_root / "repair-sources" /
            facman::platform::path_from_utf8(generation.package_sha256 + ".zip"),
        generation.product_version};
    PinnedRepairSource retirement_pins;
    if (!active && !preserve_repair_sources_) {
      const auto retained = validate_repair_source(
          retirement_context, generation.package_sha256, &retirement_pins);
      if (!retained.ok)
        return facman::core::Result<void>::failure(
            {"self_maintenance_repair_source_retirement_failed",
             "retained generation repair source is not exactly owned",
             retained.detail});
    }
    facman::self_setup::Request request;
    request.operation = facman::self_setup::Operation::uninstall;
    request.install_id = generation.install_id;
    request.maintenance_launcher = generation.maintenance_launcher;
    request.install_root = generation.install_root;
    request.state_root = generation.state_root;
    request.acceptance_root = generation.acceptance_root;
    request.product_version = generation.product_version;
    request.apply = true;
    request.coordinator_lock = &coordinator_lock;
    if (active && options_.shell_integration)
      request.native_effects = &native_effects_;
    auto removed = facman::self_setup::execute(request);
    if (!removed)
      return facman::core::Result<void>::failure(removed.error());
    if (!active && !preserve_repair_sources_) {
      auto retired = retire_repair_source(
          retirement_context, retirement_pins);
      if (!retired)
        return facman::core::Result<void>::failure(retired.error());
    }
    return facman::core::Result<void>::success();
  }

private:
  const Options &options_;
  fs::path coordinator_root_;
  SetupNativeEffects &native_effects_;
  bool preserve_repair_sources_ = false;
};

facman::core::Result<facman::self_maintenance::CompatibilityAuthorityBootstrapResponse>
bootstrap_installed_facman(const Options &options, const fs::path &coordinator_root,
                           bool apply, const fs::path &materialized_package = {}) {
  using Bootstrap = facman::self_maintenance::CompatibilityAuthorityBootstrapResponse;
  auto flat = facman::self_maintenance::discover_activation_chain(coordinator_root);
  if (!flat) return facman::core::Result<Bootstrap>::failure(flat.error());
  facman::self_maintenance::ProviderBridge provider(
      options.state_root, options.acceptance_root);
  if (!flat.value().has_value()) {
    if (!apply)
      return facman::core::Result<Bootstrap>::failure(
          {"self_maintenance_legacy_invalid",
           "bootstrap preview requires an existing flat activation history", {}});
    auto descriptor = facman::self_maintenance::inspect_legacy_descriptor(
        options.install_root);
    auto installed = provider.inspect_identity("facman.self");
    if (!descriptor || !installed ||
        !same_path(installed.value().install_root, options.install_root) ||
        installed.value().product_version != descriptor.value().product_version ||
        installed.value().provider_revision !=
            descriptor.value().universal_setup_revision ||
        installed.value().provider_revision !=
            facman::self_setup::provider_revision())
      return facman::core::Result<Bootstrap>::failure(
          !descriptor ? descriptor.error() : !installed ? installed.error() :
          facman::core::Error{"self_maintenance_legacy_invalid",
              "installed Setup identity does not match its package descriptor", {}});
    auto generation = facman::self_maintenance::make_generation(
        descriptor.value(), installed.value().source_archive_sha256,
        "facman.self", options.install_root, options.install_root,
        options.state_root, options.acceptance_root);
    if (!generation) return facman::core::Result<Bootstrap>::failure(
        generation.error());
    facman::self_maintenance::Plan source_plan;
    source_plan.operation = "migration";
    source_plan.operation_id = "bootstrap.source." +
        generation.value().generation_id.substr(0, 32);
    source_plan.source = generation.value();
    source_plan.target = generation.value();
    const auto exact = provider.inspect_installed(source_plan);
    const auto verified = exact.ok ? provider.verify_installed(source_plan)
        : facman::self_maintenance::EffectResult{};
    if (!exact.ok || !verified.ok)
      return facman::core::Result<Bootstrap>::failure(
          {"self_maintenance_legacy_invalid",
           "installed Setup source cannot be verified before bootstrap",
           exact.ok ? verified.detail : exact.detail});
    auto adopted = facman::self_maintenance::adopt_legacy(
        coordinator_root, generation.value(), true);
    if (!adopted) return facman::core::Result<Bootstrap>::failure(adopted.error());
    flat = facman::self_maintenance::discover_activation_chain(coordinator_root);
    if (!flat || !flat.value().has_value())
      return facman::core::Result<Bootstrap>::failure(!flat ? flat.error() :
          facman::core::Error{"self_maintenance_epoch_recovery_required",
              "legacy adoption did not establish a flat activation history", {}});
  }
  const auto &source = flat.value()->generations.back();
  const fs::path repair_source = source.state_root / "repair-sources" /
      facman::platform::path_from_utf8(source.package_sha256 + ".zip");
  const facman::self_setup::NativeContext repair_context{
      facman::self_setup::Operation::repair, source.install_root,
      source.state_root, source.acceptance_root, repair_source,
      source.product_version};
  PinnedRepairSource pins;
  auto retained = validate_repair_source(
      repair_context, source.package_sha256, &pins);
  if (apply && !retained.ok && !options.package.empty()) {
    SetupPackageMaterializer materializer;
    auto materialized = materialized_package.empty()
        ? materializer.materialize(options.package)
        : facman::core::Result<fs::path>::success(materialized_package);
    auto supplied = materialized
        ? facman::self_maintenance::inspect_package(materialized.value())
        : facman::core::Result<facman::self_maintenance::PackageInspection>::failure(
            materialized.error());
    std::string launcher_problem;
    auto launcher = current_executable_path(launcher_problem);
    if (supplied && launcher.has_value() &&
        supplied.value().package_sha256 == source.package_sha256) {
      const auto copied = retain_repair_source(repair_context,
          supplied.value().package, *launcher, source.package_sha256);
      if (copied.ok)
        retained = validate_repair_source(
            repair_context, source.package_sha256, &pins);
    }
  }
  if (!retained.ok)
    return facman::core::Result<Bootstrap>::failure(
        {"self_maintenance_repair_source_missing",
         "active Setup package must be retained before epoch bootstrap",
         retained.detail});
  auto package = facman::self_maintenance::inspect_package(repair_source);
  std::string detail;
  if (!package || package.value().package_sha256 != source.package_sha256 ||
      !pins.revalidate(detail))
    return facman::core::Result<Bootstrap>::failure(!package ? package.error() :
        facman::core::Error{"self_maintenance_package_incompatible",
            "retained active package changed before epoch bootstrap", detail});
  SetupBootstrapEffects effects(provider, package.value(), source.state_root,
                                source.acceptance_root, options.shell_integration);
  return facman::self_maintenance::bootstrap_compatibility_authority(
      {coordinator_root, package.value().descriptor,
       package.value().package_sha256, options.shell_integration, apply},
      effects);
}

} // namespace

int wmain(int argc, wchar_t **argv) {
  SetConsoleOutputCP(CP_UTF8);
  if (argc > 1 && std::wstring(argv[1]) == L"continue-maintenance") {
    ContinuationOptions continuation;
    std::string continuation_problem;
    if (!parse_continuation(argc, argv, continuation, continuation_problem))
      return 2;
    return run_private_continuation(continuation);
  }
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
  std::optional<MaintenanceQualification> maintenance_qualification;
  if (!admit_maintenance_qualification(
          options, maintenance_qualification, problem)) {
    print_maintenance_error(
        {"self_maintenance_qualification_invalid",
         "self-maintenance qualification was refused", problem},
        options.json);
    return 4;
  }
  if (options.maintenance_operation.has_value())
    return run_maintenance(options, local,
        maintenance_qualification ? &*maintenance_qualification : nullptr);

  std::optional<facman::self_maintenance::Generation>
      active_repair_generation;
  if (options.operation == facman::self_setup::Operation::verify ||
      options.operation == facman::self_setup::Operation::repair ||
      options.operation == facman::self_setup::Operation::uninstall) {
    const fs::path coordinator_root =
        (options.state_root.parent_path() / "setup-coordinator.v1")
            .lexically_normal();
    if (options.operation == facman::self_setup::Operation::uninstall) {
      auto epochs = facman::self_maintenance::discover_lifecycle_epoch_chain(
          coordinator_root);
      if (!epochs) {
        print_error(epochs.error(), options.json);
        return 4;
      }
      if (!epochs.value().epochs.empty() &&
          !epochs.value().epochs.back().compatibility_epoch) {
        SetupNativeEffects retirement_native_effects;
        SetupRetirementEffects retirement_effects(
            options, coordinator_root, retirement_native_effects, true);
        facman::self_maintenance::RetirementRequest retirement;
        retirement.coordinator_root = coordinator_root;
        retirement.apply = options.apply;
        retirement.epoch_mode = true;
        retirement.logical_root = options.install_root;
        retirement.state_root = options.state_root;
        retirement.acceptance_root = options.acceptance_root;
        auto retired = facman::self_maintenance::retire_active(
            retirement, retirement_effects);
        if (!retired) {
          print_error(retired.error(), options.json);
          return 4;
        }
        if (options.apply) {
          const std::size_t maximum_steps = retired.value().steps.size();
          for (std::size_t step = 1U;
               retired.value().phase == "step_completed" &&
                   step < maximum_steps; ++step) {
            auto resumed = facman::self_maintenance::retire_active(
                retirement, retirement_effects);
            if (!resumed) {
              print_error(resumed.error(), options.json);
              return 4;
            }
            retired = std::move(resumed);
          }
          if (retired.value().phase != "completed") {
            print_error({"self_maintenance_retirement_recovery_required",
                         "epoch retirement did not reach its durable completion",
                         retired.value().phase}, options.json);
            return 4;
          }
        }
        if (options.json) {
          facman::core::json::ObjectBuilder output;
          output.add_string("schema", "facman.self_setup_cli.v1");
          output.add_string("status", "ok");
          output.add_string("operation", "uninstall");
          output.add_string("phase", retired.value().phase);
          output.add_string("retirement_journal",
              facman::platform::path_to_utf8(
                  retired.value().journal_directory));
          std::cout << output.serialize() << '\n';
        } else if (retired.value().phase == "planned") {
          std::cout << "FacMan epoch retirement is planned. Repeat with --yes to apply it.\n";
        } else {
          std::cout << "FacMan epoch retirement " << retired.value().phase << ".\n";
        }
        return 0;
      }
    }
    auto selected = facman::self_maintenance::resolve_authoritative_active_state(
        coordinator_root);
    const bool resumable_flat_retirement =
        !selected &&
        options.operation == facman::self_setup::Operation::uninstall &&
        selected.error().code ==
            "self_maintenance_retirement_recovery_required";
    if (!selected && !resumable_flat_retirement) {
      print_error(selected.error(), options.json);
      return 4;
    }
    if (options.operation == facman::self_setup::Operation::uninstall) {
      auto chain = facman::self_maintenance::discover_activation_chain(
          coordinator_root);
      if (!chain) {
        print_error(chain.error(), options.json);
        return 4;
      }
      if (chain.value().has_value()) {
        const auto &generation = chain.value()->generations.back();
        if ((!same_path(generation.logical_root, options.install_root) &&
             !same_path(generation.install_root, options.install_root)) ||
            !same_path(generation.state_root, options.state_root) ||
            !same_path(generation.acceptance_root, options.acceptance_root)) {
          print_error({"self_maintenance_lineage_mismatch",
                       "uninstall roots do not bind the active activation chain",
                       generation.install_id}, options.json);
          return 4;
        }
        SetupNativeEffects retirement_native_effects;
        SetupRetirementEffects retirement_effects(
            options, coordinator_root, retirement_native_effects);
        facman::self_maintenance::RetirementRequest retirement;
        retirement.coordinator_root = coordinator_root;
        retirement.apply = options.apply;
        auto retired = facman::self_maintenance::retire_active(
            retirement, retirement_effects);
        if (!retired) {
          print_error(retired.error(), options.json);
          return 4;
        }
        if (options.json) {
          facman::core::json::ObjectBuilder output;
          output.add_string("schema", "facman.self_setup_cli.v1");
          output.add_string("status", "ok");
          output.add_string("operation", "uninstall");
          output.add_string("phase", retired.value().phase);
          output.add_string("retirement_journal",
                            facman::platform::path_to_utf8(
                                retired.value().journal_directory));
          std::cout << output.serialize() << '\n';
        } else if (retired.value().phase == "planned") {
          std::cout << "FacMan activation-chain retirement is planned. Repeat with --yes to apply it.\n";
        } else {
          std::cout << "FacMan activation-chain retirement "
                    << retired.value().phase << ".\n";
        }
        return 0;
      }
      if (!selected) {
        print_error(selected.error(), options.json);
        return 4;
      }
    }
    if (selected.value().has_value() &&
        (options.operation == facman::self_setup::Operation::repair ||
         options.operation == facman::self_setup::Operation::verify)) {
      const auto &generation = selected.value()->active.active;
      if ((!same_path(generation.logical_root, options.install_root) &&
           !same_path(generation.install_root, options.install_root)) ||
          !same_path(generation.state_root, options.state_root) ||
          !same_path(generation.acceptance_root, options.acceptance_root)) {
        print_error(setup_error_with_detail(
            "self_maintenance_lineage_mismatch",
            "setup roots do not bind the active activation-chain generation",
            generation.install_id), options.json);
        return 4;
      }
      facman::self_maintenance::ProviderBridge provider(
          options.state_root, options.acceptance_root);
      facman::self_maintenance::Plan active_plan;
      active_plan.operation = "migration";
      active_plan.operation_id = "repair.preflight." +
          generation.generation_id.substr(0, 32);
      active_plan.source = generation;
      active_plan.target = generation;
      const auto inspected = provider.inspect_installed(active_plan);
      if (!inspected.ok) {
        std::string detail = generation.install_id;
        if (!inspected.detail.empty()) detail += ": " + inspected.detail;
        print_error(setup_error_with_detail(
            "self_maintenance_active_generation_unavailable",
            "setup requires an exact provider-inspected active generation",
            std::move(detail)), options.json);
        return 4;
      }
      active_repair_generation = generation;
    }
  }
  bool resume_bootstrap = false;
  if (options.operation == facman::self_setup::Operation::install) {
    const fs::path coordinator_root =
        (options.state_root.parent_path() / "setup-coordinator.v1")
            .lexically_normal();
    auto flat = facman::self_maintenance::discover_activation_chain(
        coordinator_root);
    if (!flat) {
      print_error(flat.error(), options.json);
      return 4;
    }
    resume_bootstrap = flat.value().has_value();
    if (!resume_bootstrap) {
      auto legacy = facman::self_maintenance::inspect_legacy_descriptor(
          options.install_root);
      resume_bootstrap = legacy.ok();
    }
    auto selected = facman::self_maintenance::resolve_authoritative_active_state(
        coordinator_root);
    if (!selected && !resume_bootstrap) {
      print_error(selected.error(), options.json);
      return 4;
    }
    if (selected && selected.value().has_value() &&
        selected.value()->epoch.has_value()) {
      print_error(setup_error_with_detail(
          "self_maintenance_epoch_operation_unsupported",
          "install over an authoritative lifecycle epoch requires its "
          "maintenance route", selected.value()->epoch->epoch_id), options.json);
      return 4;
    }
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

  if (resume_bootstrap) {
    SetupPackageMaterializer materializer;
    auto supplied = materializer.materialize(options.package);
    auto metadata = supplied
        ? facman::self_maintenance::has_self_maintenance_metadata(
            supplied.value())
        : facman::core::Result<bool>::failure(supplied.error());
    if (!metadata) {
      print_error(metadata.error(), options.json);
      return 4;
    }
    if (!metadata.value()) {
      const fs::path coordinator_root =
          (options.state_root.parent_path() / "setup-coordinator.v1")
              .lexically_normal();
      auto flat = facman::self_maintenance::discover_activation_chain(
          coordinator_root);
      std::string package_problem;
      auto supplied_sha256 = exact_regular_file_digest(
          supplied.value(), package_problem);
      facman::self_maintenance::ProviderBridge provider(
          options.state_root, options.acceptance_root);
      auto installed = provider.inspect_identity("facman.self");
      const bool same_flat = flat && flat.value().has_value() &&
          supplied_sha256 &&
          flat.value()->generations.back().package_sha256 == *supplied_sha256;
      const bool same_legacy = flat && !flat.value().has_value() &&
          supplied_sha256 && installed &&
          installed.value().source_archive_sha256 == *supplied_sha256 &&
          same_path(installed.value().install_root, options.install_root);
      if (!flat || (!same_flat && !same_legacy)) {
        print_error(!flat ? flat.error() : setup_error_with_detail(
            "self_maintenance_package_incompatible",
            "generic Setup retry must match the exact installed flat package",
            package_problem), options.json);
        return 4;
      }
      // Generic legacy payloads have no maintenance identity to clone.
      // Their exact repeat install remains on the flat Setup route, whose
      // coordinator-locked epoch guard still rejects an entered bootstrap.
      resume_bootstrap = false;
    }
  }

  if (resume_bootstrap) {
    const fs::path coordinator_root =
        (options.state_root.parent_path() / "setup-coordinator.v1")
            .lexically_normal();
    auto bootstrap = bootstrap_installed_facman(
        options, coordinator_root, options.apply);
    if (!bootstrap) {
      print_error(bootstrap.error(), options.json);
      return 4;
    }
    if (options.json) {
      facman::core::json::ObjectBuilder output;
      output.add_string("schema", "facman.self_setup_cli.v1");
      output.add_string("status", "ok");
      output.add_string("operation", "install");
      output.add_string("phase", bootstrap.value().phase);
      output.add_string("epoch_id", bootstrap.value().epoch.epoch_id);
      std::cout << output.serialize() << '\n';
    } else {
      std::cout << "FacManSetup install " << bootstrap.value().phase
                << ": epoch " << bootstrap.value().epoch.epoch_id << '\n';
    }
    return 0;
  }

  facman::self_setup::Request request;
  request.operation = options.operation;
  request.package = options.package;
  request.maintenance_launcher = maintenance_launcher;
  request.install_root = options.install_root;
  request.state_root = options.state_root;
  request.acceptance_root = options.acceptance_root;
  request.product_version = FACMAN_VERSION_SEMVER;
  if (active_repair_generation.has_value()) {
    request.install_id = active_repair_generation->install_id;
    request.install_root = active_repair_generation->install_root;
    request.state_root = active_repair_generation->state_root;
    request.acceptance_root = active_repair_generation->acceptance_root;
    request.product_version = active_repair_generation->product_version;
  }
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
  std::optional<facman::self_maintenance::CompatibilityAuthorityBootstrapResponse>
      installed_bootstrap;
  if (options.operation == facman::self_setup::Operation::install &&
      options.apply) {
    const fs::path coordinator_root =
        (options.state_root.parent_path() / "setup-coordinator.v1")
            .lexically_normal();
    fs::path supplied = package_materializer.materialized_path();
    if (supplied.empty()) {
      auto materialized = package_materializer.materialize(options.package);
      if (!materialized) {
        print_error(materialized.error(), options.json);
        return 4;
      }
      supplied = materialized.take_value();
    }
    auto metadata = facman::self_maintenance::has_self_maintenance_metadata(
        supplied);
    if (!metadata) {
      print_error(metadata.error(), options.json);
      return 4;
    }
    if (metadata.value()) {
      auto bootstrap = bootstrap_installed_facman(
          options, coordinator_root, true, supplied);
      if (!bootstrap) {
        print_error(bootstrap.error(), options.json);
        return 4;
      }
      installed_bootstrap = bootstrap.take_value();
    }
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
    if (installed_bootstrap.has_value()) {
      output.add_string("bootstrap_phase", installed_bootstrap->phase);
      output.add_string("epoch_id", installed_bootstrap->epoch.epoch_id);
    }
    std::cout << output.serialize() << '\n';
  } else {
    std::cout << "FacManSetup " << response.value().operation << ' '
              << response.value().phase << ":\n"
              << response.value().provider_json << '\n';
    if (installed_bootstrap.has_value())
      std::cout << "Lifecycle epoch " << installed_bootstrap->epoch.epoch_id
                << " " << installed_bootstrap->phase << '\n';
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
