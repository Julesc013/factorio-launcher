// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_self_setup.h"
#include "windows_integration.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
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
      << "Qualification interruption requires both "
         "--qualification-interrupt-after files_applied|shortcut_applied and "
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
        if (value == L"files_applied")
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
  return boundary == facman::self_setup::DurableBoundary::files_applied
      ? "files_applied" : "shortcut_applied";
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

class SetupNativeEffects final : public facman::self_setup::NativeEffects {
public:
  facman::self_setup::NativeOwnership inspect(
      const fs::path &install_root,
      facman::self_setup::NativeEffect effect,
      const std::string &product_version) override {
    const auto observed = facman::setup::integration::inspect_windows_effect(
        effect == facman::self_setup::NativeEffect::shortcut
            ? facman::setup::integration::Effect::shortcut
            : facman::setup::integration::Effect::registration,
        install_root, product_version);
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
      const fs::path &install_root,
      facman::self_setup::NativeEffect effect,
      facman::self_setup::Operation operation,
      const std::string &product_version) override {
    const auto result = facman::setup::integration::apply_windows_effect(
        effect == facman::self_setup::NativeEffect::shortcut
            ? facman::setup::integration::Effect::shortcut
            : facman::setup::integration::Effect::registration,
        install_root, product_version, operation == facman::self_setup::Operation::uninstall);
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
  SetupNativeEffects native_effects;
  if (options.shell_integration)
    request.native_effects = &native_effects;
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
