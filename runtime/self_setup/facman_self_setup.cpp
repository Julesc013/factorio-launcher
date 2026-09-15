// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_self_setup.h"

#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_local_operation_lock.h"
#include "fl_sha256.h"
#include "fl_user_paths.h"
#include "usk/usk_api.h"

#include <atomic>
#include <algorithm>
#include <chrono>
#include <cctype>
#include <ctime>
#include <filesystem>
#include <iomanip>
#include <optional>
#include <sstream>
#include <system_error>
#include <thread>
#include <vector>

#ifdef _WIN32
#include <windows.h>
#endif

#ifndef FACMAN_SELF_SETUP_PROVIDER_REVISION
#define FACMAN_SELF_SETUP_PROVIDER_REVISION "unknown"
#endif

namespace fs = std::filesystem;
namespace json = facman::core::json;

namespace facman::self_setup {
namespace {

std::atomic<unsigned long long> sequence{0};
thread_local ProviderEffects *injected_provider = nullptr;

struct ScopedProviderEffects {
  ProviderEffects *previous = nullptr;
  explicit ScopedProviderEffects(ProviderEffects *value)
      : previous(injected_provider) { injected_provider = value; }
  ~ScopedProviderEffects() { injected_provider = previous; }
};

facman::core::Error error(std::string code, std::string message,
                          std::string detail = {}) {
  facman::core::Error result{std::move(code), std::move(message), ""};
  result.detail = std::move(detail);
  return result;
}

facman::core::Error journal_write_failure(
    std::string message,
    const facman::core::Error &original,
    const facman::core::Error &journal_error) {
  return error(
      "self_setup_journal_write_failed", std::move(message),
      "original=" + original.code + ": " + original.message +
          (original.detail.empty() ? std::string() : ": " + original.detail) +
          "; journal=" + journal_error.code + ": " + journal_error.message +
          (journal_error.detail.empty() ? std::string()
                                        : ": " + journal_error.detail));
}

facman::core::Result<fs::path> absolute_path(const fs::path &value,
                                             const char *field) {
  if (value.empty()) {
    return facman::core::Result<fs::path>::failure(
        error("self_setup_input_missing", std::string(field) + " is required"));
  }
  std::error_code status;
  const fs::path absolute = fs::absolute(value, status);
  if (status || !absolute.is_absolute()) {
    return facman::core::Result<fs::path>::failure(
        error("self_setup_path_invalid",
              std::string(field) + " is not an absolute usable path"));
  }
  return facman::core::Result<fs::path>::success(absolute.lexically_normal());
}

facman::core::Result<fs::path> coordinator_state_root(const Request &request) {
  if (request.provider_effects != nullptr) {
    const fs::path override = request.provider_effects->test_coordinator_root();
    if (!override.empty()) return absolute_path(override, "test coordinator root");
  }
  auto paths = facman::platform::user_paths();
  if (!paths || paths.value().state.empty())
    return facman::core::Result<fs::path>::failure(error(
        "self_setup_path_invalid", "platform setup coordinator state is unavailable"));
  // This is an app-owned authority, deliberately independent of every USK
  // state/acceptance option. It makes root locking and recovery admission
  // global even when callers select distinct provider roots.
  return facman::core::Result<fs::path>::success(
      (paths.value().state / "FacMan" / "setup-coordinator.v1").lexically_normal());
}

facman::core::Result<std::string> canonical_install_root(const fs::path &value) {
  auto absolute = absolute_path(value, "install root");
  if (!absolute) return facman::core::Result<std::string>::failure(absolute.error());
#ifdef _WIN32
  fs::path ancestor = absolute.value();
  std::vector<fs::path> suffix;
  std::error_code status;
  while (!fs::exists(ancestor, status) || status) {
    if (status || ancestor == ancestor.root_path())
      return facman::core::Result<std::string>::failure(error(
          "self_setup_path_invalid", "install root has no usable existing ancestor"));
    suffix.push_back(ancestor.filename());
    ancestor = ancestor.parent_path();
  }
  HANDLE handle = CreateFileW(ancestor.c_str(), FILE_READ_ATTRIBUTES,
      FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr, OPEN_EXISTING,
      FILE_FLAG_BACKUP_SEMANTICS, nullptr);
  if (handle == INVALID_HANDLE_VALUE)
    return facman::core::Result<std::string>::failure(error(
        "self_setup_path_invalid", "install root ancestor could not be opened by handle"));
  const DWORD required = GetFinalPathNameByHandleW(handle, nullptr, 0,
      FILE_NAME_NORMALIZED | VOLUME_NAME_GUID);
  if (required == 0) { CloseHandle(handle); return facman::core::Result<std::string>::failure(error(
      "self_setup_path_invalid", "install root ancestor identity could not be resolved")); }
  std::wstring resolved(required, L'\0');
  const DWORD copied = GetFinalPathNameByHandleW(handle, resolved.data(), required,
      FILE_NAME_NORMALIZED | VOLUME_NAME_GUID);
  CloseHandle(handle);
  if (copied == 0 || copied >= required)
    return facman::core::Result<std::string>::failure(error(
        "self_setup_path_invalid", "install root ancestor identity could not be read"));
  resolved.resize(copied);
  fs::path result(resolved);
  for (auto it = suffix.rbegin(); it != suffix.rend(); ++it) result /= *it;
  const std::wstring raw = result.native();
  const int length = LCMapStringEx(LOCALE_NAME_INVARIANT, LCMAP_LOWERCASE,
      raw.c_str(), static_cast<int>(raw.size()), nullptr, 0, nullptr, nullptr, 0);
  if (length <= 0) return facman::core::Result<std::string>::failure(error(
      "self_setup_path_invalid", "install root identity could not be invariant-folded"));
  std::wstring folded(static_cast<std::size_t>(length), L'\0');
  if (LCMapStringEx(LOCALE_NAME_INVARIANT, LCMAP_LOWERCASE, raw.c_str(),
      static_cast<int>(raw.size()), folded.data(), length, nullptr, nullptr, 0) != length)
    return facman::core::Result<std::string>::failure(error(
        "self_setup_path_invalid", "install root identity could not be invariant-folded"));
  return facman::core::Result<std::string>::success(facman::platform::path_to_utf8(fs::path(folded).lexically_normal()));
#else
  std::error_code status;
  const fs::path canonical = fs::weakly_canonical(absolute.value(), status);
  if (!status && canonical.is_absolute())
    return facman::core::Result<std::string>::success(facman::platform::path_to_utf8(canonical.lexically_normal()));
  return facman::core::Result<std::string>::failure(error(
      "self_setup_path_invalid", "install root could not be canonicalized"));
#endif
}

std::string timestamp() {
  const std::time_t now = std::time(nullptr);
  std::tm utc{};
#ifdef _WIN32
  gmtime_s(&utc, &now);
#else
  gmtime_r(&now, &utc);
#endif
  std::ostringstream output;
  output << std::put_time(&utc, "%Y-%m-%dT%H:%M:%SZ");
  return output.str();
}

bool valid_timestamp(const std::string &value) {
  if (value.size() != 20U || value[4] != '-' || value[7] != '-' ||
      value[10] != 'T' || value[13] != ':' || value[16] != ':' ||
      value[19] != 'Z')
    return false;
  for (const std::size_t index : {0U, 1U, 2U, 3U, 5U, 6U, 8U, 9U,
                                  11U, 12U, 14U, 15U, 17U, 18U}) {
    if (value[index] < '0' || value[index] > '9') return false;
  }
  const auto number = [&](std::size_t offset, std::size_t length) {
    int result = 0;
    for (std::size_t index = 0; index < length; ++index)
      result = result * 10 + (value[offset + index] - '0');
    return result;
  };
  const int year = number(0, 4);
  const int month = number(5, 2);
  const int day = number(8, 2);
  const int hour = number(11, 2);
  const int minute = number(14, 2);
  const int second = number(17, 2);
  if (year == 0 || month < 1 || month > 12 || hour > 23 ||
      minute > 59 || second > 59)
    return false;
  const bool leap = (year % 4 == 0 && year % 100 != 0) || year % 400 == 0;
  constexpr int month_days[] = {0, 31, 28, 31, 30, 31, 30,
                                31, 31, 30, 31, 30, 31};
  const int maximum_day = month_days[month] + (month == 2 && leap ? 1 : 0);
  return day >= 1 && day <= maximum_day;
}

facman::core::Result<std::string> timestamp_after(
    const std::string &lower_bound, Clock *clock) {
  if (!valid_timestamp(lower_bound))
    return facman::core::Result<std::string>::failure(error(
        "self_setup_clock_unusable", "setup lifecycle lower timestamp is malformed"));
  if (clock != nullptr) {
    const std::string current = clock->after(lower_bound);
    if (valid_timestamp(current) && current > lower_bound)
      return facman::core::Result<std::string>::success(current);
    return facman::core::Result<std::string>::failure(error(
        "self_setup_clock_unusable",
        "setup lifecycle injected timestamp did not advance"));
  }
  constexpr int attempts = 80;
  for (int attempt = 0; attempt < attempts; ++attempt) {
    const std::string current = timestamp();
    if (current > lower_bound)
      return facman::core::Result<std::string>::success(current);
    std::this_thread::sleep_for(std::chrono::milliseconds(25));
  }
  return facman::core::Result<std::string>::failure(error(
      "self_setup_clock_unusable",
      "setup lifecycle timestamp did not advance within its bounded wait"));
}

std::string identifier(const char *prefix) {
  const auto ticks =
      std::chrono::steady_clock::now().time_since_epoch().count();
  const auto index = sequence.fetch_add(1, std::memory_order_relaxed);
  std::ostringstream output;
  output << prefix << '.' << ticks << '.' << index;
  return output.str();
}

std::string string_field(const json::Value &object, const char *key) {
  const json::Value *value = object.find(key);
  if (value == nullptr)
    return {};
  auto decoded = value->string_value();
  return decoded ? decoded.take_value() : std::string();
}

bool exact_keys(const json::Value &object,
                std::initializer_list<const char *> expected) {
  if (!object.is_object() || object.object_keys().size() != expected.size())
    return false;
  for (const char *key : expected) {
    if (object.find(key) == nullptr)
      return false;
  }
  return true;
}

bool bounded_identifier(const std::string &value) {
  if (value.empty() || value.size() > 160U)
    return false;
  return std::all_of(value.begin(), value.end(), [](unsigned char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
           (c >= '0' && c <= '9') || c == '.' || c == '-' || c == '_';
  });
}

bool one_of(const std::string &value,
            std::initializer_list<const char *> allowed) {
  return std::any_of(allowed.begin(), allowed.end(), [&](const char *candidate) {
    return value == candidate;
  });
}

bool digest_or_empty(const std::string &value) {
  return value.empty() || (value.size() == 64U &&
      std::all_of(value.begin(), value.end(), [](unsigned char c) {
        return (c >= 'a' && c <= 'f') || (c >= '0' && c <= '9');
      }));
}

struct SetupJournal {
  std::string operation_id;
  std::string intent_digest;
  std::string operation;
  std::string install_root;
  std::string install_root_identity;
  std::string product_version;
  std::string mode;
  std::string provider_revision;
  std::string provider_state_root;
  std::string provider_acceptance_root;
  std::string provider_source_digest;
  std::string installed_source_digest;
  std::string provider_request_id;
  std::string provider_plan_id;
  std::string provider_transaction_id;
  std::string provider_created_at;
  std::string provider_plan_digest;
  std::string provider_phase = "before_plan";
  std::string provider_receipt_identity;
  std::string recovery_plan_id;
  std::string recovery_plan_digest;
  std::string recovery_plan_created_at;
  std::string recovery_action;
  std::string files = "pending";
  std::string repair_source = "pending";
  std::string shortcut = "pending";
  std::string registration = "pending";
  std::string state = "intent";
  std::string recovery_boundary = "intent_recorded";
  std::string last_error;
};

std::string operation_name(Operation operation) {
  switch (operation) {
  case Operation::install: return "install";
  case Operation::repair: return "repair";
  case Operation::uninstall: return "uninstall";
  case Operation::verify: return "verify";
  }
  return "verify";
}

std::string digest_text(const std::string &value) {
  return facman::base::sha256_hex_bytes(
      reinterpret_cast<const unsigned char *>(value.data()), value.size());
}

facman::core::Result<std::string> stable_file_digest(const fs::path &path) {
  facman::platform::StableInputFile input;
  const auto opened = input.open_no_follow(path);
  if (!opened.ok() || input.size() == 0)
    return facman::core::Result<std::string>::failure(error(
        "self_setup_package_hash_failed", "setup payload could not be safely opened", opened.detail));
  facman::base::Sha256Hasher hash;
  std::vector<unsigned char> buffer(1024U * 1024U);
  for (std::uint64_t offset = 0; offset < input.size();) {
    const std::size_t requested = static_cast<std::size_t>((std::min)(
        static_cast<std::uint64_t>(buffer.size()), input.size() - offset));
    if (input.read_at(offset, buffer.data(), requested) != requested)
      return facman::core::Result<std::string>::failure(error(
          "self_setup_package_hash_failed", "setup payload changed while being hashed"));
    hash.update(buffer.data(), requested);
    offset += requested;
  }
  const auto revalidated = input.revalidate();
  if (!revalidated.ok())
    return facman::core::Result<std::string>::failure(error(
        "self_setup_package_hash_failed", "setup payload changed while being hashed", revalidated.detail));
  return facman::core::Result<std::string>::success(hash.finish());
}

fs::path journal_path(const fs::path &state_root, const std::string &operation,
                      const std::string &root_identity,
                      const std::string &intent_digest) {
  return state_root / "setup-operations" /
      ("facman." + operation + "." + root_identity.substr(0, 32) +
       "." + intent_digest.substr(0, 32) +
       ".setup-operation.v1.json");
}

struct ScopedSetupLock {
  facman::base::StableLocalLock value;
  ScopedSetupLock() = default;
  ScopedSetupLock(const ScopedSetupLock &) = delete;
  ScopedSetupLock &operator=(const ScopedSetupLock &) = delete;
  ScopedSetupLock(ScopedSetupLock &&) noexcept = default;
  ScopedSetupLock &operator=(ScopedSetupLock &&) noexcept = default;
  ~ScopedSetupLock() {
    std::string ignored;
    if (value.open()) (void)value.remove_exact(ignored);
  }
};

facman::core::Result<ScopedSetupLock> acquire_setup_lock(
    const fs::path &state_root, const std::string &root_identity,
    const std::string &operation_id) {
  std::error_code status;
  const fs::path directory = state_root / "setup-operations";
  fs::create_directories(directory, status);
  if (status) return facman::core::Result<ScopedSetupLock>::failure(error(
      "self_setup_lock_unsafe", "setup operation lock directory could not be created", status.message()));
  // Setup changes one owned root across all mutating modes.  An uninstall
  // cannot race an install or repair merely because their journal names differ.
  const fs::path path = directory / ("facman.root." +
      root_identity + ".lock");
  ScopedSetupLock result;
  auto acquired = result.value.create(path);
  if (acquired.code == facman::base::StableLockCode::exists) {
    std::string previous;
    acquired = result.value.open_existing(path, 256U, previous);
    if (acquired.code == facman::base::StableLockCode::contended)
      return facman::core::Result<ScopedSetupLock>::failure(error(
          "self_setup_lock_contended", "another setup operation is active", acquired.detail));
    if (!acquired.acquired())
      return facman::core::Result<ScopedSetupLock>::failure(error(
          "self_setup_lock_unsafe", "existing setup operation lock is unsafe", acquired.detail));
    if (!bounded_identifier(previous))
      return facman::core::Result<ScopedSetupLock>::failure(error(
          "self_setup_lock_unsafe", "stale setup operation lock has invalid content", previous));
    std::string removed;
    if (!result.value.remove_exact(removed))
      return facman::core::Result<ScopedSetupLock>::failure(error(
          "self_setup_lock_unsafe", "stale setup operation lock could not be retired", removed));
    acquired = result.value.create(path);
  }
  if (!acquired.acquired())
    return facman::core::Result<ScopedSetupLock>::failure(error(
        "self_setup_lock_unsafe", "setup operation lock could not be acquired", acquired.detail));
  std::string written;
  if (!result.value.write_text(operation_id, written))
    return facman::core::Result<ScopedSetupLock>::failure(error(
        "self_setup_lock_unsafe", "setup operation lock could not be written", written));
  return facman::core::Result<ScopedSetupLock>::success(std::move(result));
}

std::string journal_json(const SetupJournal &journal) {
  json::ObjectBuilder provider;
  provider.add_string("revision", journal.provider_revision);
  provider.add_string("state_root", journal.provider_state_root);
  provider.add_string("acceptance_root", journal.provider_acceptance_root);
  provider.add_string("source_digest", journal.provider_source_digest);
  provider.add_string("installed_source_digest", journal.installed_source_digest);
  provider.add_string("request_id", journal.provider_request_id);
  provider.add_string("plan_id", journal.provider_plan_id);
  provider.add_string("transaction_id", journal.provider_transaction_id);
  provider.add_string("created_at", journal.provider_created_at);
  provider.add_string("plan_digest", journal.provider_plan_digest);
  provider.add_string("phase", journal.provider_phase);
  provider.add_string("receipt_identity", journal.provider_receipt_identity);
  json::ObjectBuilder recovery;
  recovery.add_string("plan_id", journal.recovery_plan_id);
  recovery.add_string("plan_digest", journal.recovery_plan_digest);
  recovery.add_string("created_at", journal.recovery_plan_created_at);
  recovery.add_string("action", journal.recovery_action);
  json::ObjectBuilder effects;
  effects.add_string("files", journal.files);
  effects.add_string("repair_source", journal.repair_source);
  effects.add_string("shortcut", journal.shortcut);
  effects.add_string("registration", journal.registration);
  json::ObjectBuilder document;
  document.add_string("schema", "facman.setup_operation_journal.v1");
  document.add_string("operation_id", journal.operation_id);
  document.add_string("intent_digest", journal.intent_digest);
  document.add_string("operation", journal.operation);
  document.add_string("install_root", journal.install_root);
  document.add_string("install_root_identity", journal.install_root_identity);
  document.add_string("product", "facman");
  document.add_string("product_version", journal.product_version);
  document.add_string("mode", journal.mode);
  document.add_object("provider", provider);
  document.add_object("recovery", recovery);
  document.add_object("effects", effects);
  document.add_string("state", journal.state);
  document.add_string("recovery_boundary", journal.recovery_boundary);
  document.add_string("last_error", journal.last_error);
  return document.serialize() + "\n";
}

facman::core::Result<void> persist_journal(const fs::path &path,
                                            const SetupJournal &journal) {
  const std::string bytes = journal_json(journal);
  if (bytes.size() > 32U * 1024U)
    return facman::core::Result<void>::failure(
        error("self_setup_journal_invalid", "setup operation journal exceeds its byte limit"));
  std::error_code status;
  fs::create_directories(path.parent_path(), status);
  if (status)
    return facman::core::Result<void>::failure(
        error("self_setup_journal_write_failed", "setup operation journal directory could not be created"));
  const fs::path temporary = path.parent_path() /
      (path.filename().string() + ".pending." + identifier("journal"));
  facman::platform::DurableOutputFile output;
  auto opened = output.create_exclusive(temporary, 32U * 1024U);
  if (!opened.ok() || output.write_at(0, bytes.data(), bytes.size()) != bytes.size())
    return facman::core::Result<void>::failure(
        error("self_setup_journal_write_failed", "setup operation journal could not be written", opened.detail));
  auto flushed = output.flush_file_and_parent();
  if (!flushed.ok())
    return facman::core::Result<void>::failure(
        error("self_setup_journal_write_failed", "setup operation journal could not be flushed", flushed.detail));
  auto replaced = fs::exists(path, status)
      ? facman::platform::replace_existing_durable(temporary, path)
      : facman::platform::commit_no_replace(temporary, path);
  if (!replaced.ok())
    return facman::core::Result<void>::failure(
        error("self_setup_journal_write_failed", "setup operation journal could not be published", replaced.detail));
  return facman::core::Result<void>::success();
}

std::string journal_intent_digest(const SetupJournal &journal) {
  return digest_text(journal.operation + "\n" + journal.install_root_identity + "\n" +
      journal.product_version + "\n" + journal.mode + "\n" +
      journal.provider_source_digest + "\n" + journal.provider_state_root + "\n" +
      journal.provider_acceptance_root);
}

facman::core::Result<SetupJournal> load_journal(const fs::path &path);

std::string history_filename(const SetupJournal &journal) {
  const std::string identity = "facman.setup.history.v1\n" + journal.operation_id + "\n" +
      journal.intent_digest + "\n" + journal.install_root_identity + "\n" + journal.operation;
  return "facman." + digest_text(identity) + ".setup-history.v1.json";
}

facman::core::Result<void> archive_journal(const fs::path &active_path,
                                           const SetupJournal &journal) {
  const fs::path history = active_path.parent_path() / "history" /
      history_filename(journal);
  std::error_code status;
  if (fs::exists(history, status)) {
    if (status) return facman::core::Result<void>::failure(error(
        "self_setup_journal_write_failed", "setup operation history could not be observed", history.string()));
    auto prior = load_journal(history);
    if (!prior || journal_json(prior.value()) != journal_json(journal))
      return facman::core::Result<void>::failure(error(
          "self_setup_journal_write_failed", "setup operation history is substituted", history.string()));
    return facman::core::Result<void>::success();
  }
  if (status) return facman::core::Result<void>::failure(error(
      "self_setup_journal_write_failed", "setup operation history could not be observed", history.string()));
  return persist_journal(history, journal);
}

facman::core::Result<SetupJournal> load_journal(const fs::path &path) {
  std::error_code status;
  if (!fs::exists(path, status) || status)
    return facman::core::Result<SetupJournal>::failure(
        error("self_setup_journal_absent", "setup operation journal is absent"));
  const auto size = fs::file_size(path, status);
  if (status || size == 0 || size > 32U * 1024U)
    return facman::core::Result<SetupJournal>::failure(
        error("self_setup_recovery_required", "setup operation journal is malformed", facman::platform::path_to_utf8(path)));
  facman::platform::StableInputFile input;
  auto opened = input.open_no_follow(path);
  if (!opened.ok())
    return facman::core::Result<SetupJournal>::failure(
        error("self_setup_recovery_required", "setup operation journal is unreadable", opened.detail));
  std::string bytes(static_cast<std::size_t>(size), '\0');
  if (input.read_at(0, bytes.data(), bytes.size()) != bytes.size() || !input.revalidate().ok())
    return facman::core::Result<SetupJournal>::failure(
        error("self_setup_recovery_required", "setup operation journal changed while being read"));
  auto document = json::parse(bytes);
  if (!document ||
      !exact_keys(document.value(),
                  {"schema", "operation_id", "intent_digest", "operation",
                   "install_root", "install_root_identity", "product",
                   "product_version", "mode", "provider", "recovery", "effects", "state",
                   "recovery_boundary", "last_error"}) ||
      string_field(document.value(), "schema") != "facman.setup_operation_journal.v1" ||
      string_field(document.value(), "product") != "facman")
    return facman::core::Result<SetupJournal>::failure(
        error("self_setup_recovery_required", "setup operation journal has an invalid schema", facman::platform::path_to_utf8(path)));
  const auto *provider = document.value().find("provider");
  const auto *recovery = document.value().find("recovery");
  const auto *effects = document.value().find("effects");
  const bool provider_fields_valid = provider != nullptr &&
      (exact_keys(*provider, {"revision", "state_root", "acceptance_root", "source_digest", "installed_source_digest", "request_id", "plan_id", "transaction_id", "created_at", "plan_digest", "phase", "receipt_identity"}) ||
       exact_keys(*provider, {"revision", "state_root", "acceptance_root", "source_digest", "installed_source_digest", "request_id", "plan_id", "transaction_id", "created_at", "plan_digest", "receipt_identity"}));
  if (!provider_fields_valid || recovery == nullptr || effects == nullptr ||
      !exact_keys(*recovery, {"plan_id", "plan_digest", "created_at", "action"}) ||
      !exact_keys(*effects, {"files", "repair_source", "shortcut", "registration"}))
    return facman::core::Result<SetupJournal>::failure(
        error("self_setup_recovery_required", "setup operation journal has invalid nested fields", facman::platform::path_to_utf8(path)));
  SetupJournal journal;
  journal.operation_id = string_field(document.value(), "operation_id");
  journal.intent_digest = string_field(document.value(), "intent_digest");
  journal.operation = string_field(document.value(), "operation");
  journal.install_root = string_field(document.value(), "install_root");
  journal.install_root_identity = string_field(document.value(), "install_root_identity");
  journal.product_version = string_field(document.value(), "product_version");
  journal.mode = string_field(document.value(), "mode");
  journal.provider_revision = string_field(*provider, "revision");
  journal.provider_state_root = string_field(*provider, "state_root");
  journal.provider_acceptance_root = string_field(*provider, "acceptance_root");
  journal.provider_source_digest = string_field(*provider, "source_digest");
  journal.installed_source_digest = string_field(*provider, "installed_source_digest");
  journal.provider_request_id = string_field(*provider, "request_id");
  journal.provider_plan_id = string_field(*provider, "plan_id");
  journal.provider_transaction_id = string_field(*provider, "transaction_id");
  journal.provider_created_at = string_field(*provider, "created_at");
  journal.provider_plan_digest = string_field(*provider, "plan_digest");
  journal.provider_phase = provider->find("phase") == nullptr
      ? (journal.provider_plan_digest.empty() ? "before_plan" : "apply_entered")
      : string_field(*provider, "phase");
  journal.provider_receipt_identity = string_field(*provider, "receipt_identity");
  journal.recovery_plan_id = string_field(*recovery, "plan_id");
  journal.recovery_plan_digest = string_field(*recovery, "plan_digest");
  journal.recovery_plan_created_at = string_field(*recovery, "created_at");
  journal.recovery_action = string_field(*recovery, "action");
  journal.files = string_field(*effects, "files");
  journal.repair_source = string_field(*effects, "repair_source");
  journal.shortcut = string_field(*effects, "shortcut");
  journal.registration = string_field(*effects, "registration");
  journal.state = string_field(document.value(), "state");
  journal.recovery_boundary = string_field(document.value(), "recovery_boundary");
  journal.last_error = string_field(document.value(), "last_error");
  if (!bounded_identifier(journal.operation_id) || !digest_or_empty(journal.intent_digest) ||
      journal.intent_digest.empty() || !bounded_identifier(journal.provider_request_id) ||
      !bounded_identifier(journal.provider_plan_id) || !bounded_identifier(journal.provider_transaction_id) ||
      journal.install_root_identity.size() != 64U ||
      !digest_or_empty(journal.install_root_identity) || journal.operation.empty() ||
      journal.product_version.empty() || !valid_timestamp(journal.provider_created_at) ||
      journal.provider_revision.empty() || journal.provider_state_root.empty() ||
      journal.provider_acceptance_root.empty() ||
      !digest_or_empty(journal.provider_source_digest) || journal.provider_source_digest.empty() ||
      !digest_or_empty(journal.installed_source_digest) ||
      (journal.operation != "uninstall" && journal.installed_source_digest.empty()) ||
      (journal.operation != "uninstall" &&
       journal.installed_source_digest != journal.provider_source_digest) ||
      (journal.operation == "uninstall" &&
       !journal.provider_plan_digest.empty() && journal.installed_source_digest.empty()) ||
      !digest_or_empty(journal.provider_plan_digest) ||
      !one_of(journal.provider_phase, {"before_plan", "plan_reviewed", "apply_entered"}) ||
      !digest_or_empty(journal.provider_receipt_identity) ||
      !digest_or_empty(journal.recovery_plan_digest) ||
      (!journal.recovery_plan_id.empty() && !bounded_identifier(journal.recovery_plan_id)) ||
      (!journal.recovery_plan_created_at.empty() && !valid_timestamp(journal.recovery_plan_created_at)) ||
      !one_of(journal.recovery_action, {"", "rollback"}) ||
      !one_of(journal.operation, {"install", "repair", "uninstall"}) ||
      !one_of(journal.mode, {"installed", "portable"}) ||
      !one_of(journal.files, {"pending", "applied"}) ||
      !one_of(journal.repair_source, {"pending", "applying", "applied", "not_applicable"}) ||
      !one_of(journal.shortcut, {"pending", "applying", "applied", "not_applicable"}) ||
      !one_of(journal.registration, {"pending", "applying", "applied", "not_applicable"}) ||
      !one_of(journal.state, {"intent", "files_applying", "files_applied", "native_applying", "completed", "rolled_back", "abandoned", "recovery_required"}) ||
      journal.recovery_boundary.empty() || journal.recovery_boundary.size() > 160U ||
      journal.last_error.size() > 1024U)
    return facman::core::Result<SetupJournal>::failure(
        error("self_setup_recovery_required", "setup operation journal contains invalid identities", facman::platform::path_to_utf8(path)));
  if (journal.provider_request_id != "request." + journal.operation_id ||
      journal.provider_transaction_id != "tx." + journal.operation_id ||
      (journal.operation == "install" && journal.provider_plan_id != journal.provider_request_id) ||
      (journal.operation != "install" && journal.provider_plan_id != "plan." + journal.operation_id)) {
    return facman::core::Result<SetupJournal>::failure(error(
        "self_setup_recovery_required", "setup operation journal provider identities do not match its operation", facman::platform::path_to_utf8(path)));
  }
  auto journal_root = absolute_path(fs::path(journal.install_root), "journal install root");
  auto journal_identity = journal_root ? canonical_install_root(journal_root.value())
      : facman::core::Result<std::string>::failure(journal_root.error());
  if (!journal_root || !journal_identity ||
      digest_text("facman.setup.root.v1\n" + journal_identity.value()) != journal.install_root_identity ||
      journal_intent_digest(journal) != journal.intent_digest)
    return facman::core::Result<SetupJournal>::failure(error(
        "self_setup_recovery_required", "setup operation journal intent does not recompute", facman::platform::path_to_utf8(path)));
  const bool recovery_empty = journal.recovery_plan_id.empty() &&
      journal.recovery_plan_digest.empty() && journal.recovery_plan_created_at.empty() &&
      journal.recovery_action.empty();
  const bool recovery_complete = journal.recovery_plan_id == "recovery.plan." + journal.operation_id &&
      !journal.recovery_plan_digest.empty() && !journal.recovery_plan_created_at.empty() &&
      journal.recovery_action == "rollback";
  if (!recovery_empty && !recovery_complete)
    return facman::core::Result<SetupJournal>::failure(error(
        "self_setup_recovery_required", "setup operation recovery review tuple is incomplete or foreign", facman::platform::path_to_utf8(path)));
  const bool portable = journal.mode == "portable";
  const bool source_required = !portable && journal.operation != "uninstall";
  const bool native_complete = journal.shortcut == "applied" &&
      journal.registration == "applied";
  if ((portable && (journal.repair_source != "not_applicable" ||
                    journal.shortcut != "not_applicable" ||
                    journal.registration != "not_applicable")) ||
      (!source_required && !portable && journal.repair_source != "not_applicable") ||
      (journal.state == "completed" &&
       (journal.files != "applied" ||
        (source_required && journal.repair_source != "applied") ||
        (!portable && !native_complete))) ||
      (journal.files == "pending" &&
       (journal.shortcut == "applied" || journal.registration == "applied")) ||
      (journal.provider_phase == "before_plan" &&
       !journal.provider_plan_digest.empty()) ||
      (journal.provider_phase != "before_plan" &&
       journal.provider_plan_digest.empty()) ||
      (journal.files == "applied" && journal.provider_phase != "apply_entered")) {
    return facman::core::Result<SetupJournal>::failure(error(
        "self_setup_recovery_required",
        "setup operation journal has incompatible phase and effect states",
        facman::platform::path_to_utf8(path)));
  }
  if (journal.state == "rolled_back" &&
      (journal.files != "pending" || journal.shortcut == "applied" ||
       journal.registration == "applied" || journal.provider_plan_digest.empty() || !recovery_complete)) {
    return facman::core::Result<SetupJournal>::failure(error(
        "self_setup_recovery_required", "rolled-back setup journal has incompatible terminal effects", facman::platform::path_to_utf8(path)));
  }
  if (journal.state == "abandoned" &&
      (!journal.provider_plan_digest.empty() || !journal.provider_receipt_identity.empty() ||
       journal.files != "pending" ||
       (journal.mode == "installed" && (journal.shortcut != "pending" ||
                                         journal.registration != "pending")) ||
       (journal.mode == "portable" && (journal.shortcut != "not_applicable" ||
                                         journal.registration != "not_applicable")) ||
       journal.provider_phase != "before_plan" ||
       journal.recovery_boundary != "abandoned_before_provider_apply" || !recovery_empty)) {
    return facman::core::Result<SetupJournal>::failure(error(
        "self_setup_recovery_required", "abandoned setup journal has incompatible effects", facman::platform::path_to_utf8(path)));
  }
  return facman::core::Result<SetupJournal>::success(std::move(journal));
}

struct DiscoveredJournal {
  SetupJournal journal;
  fs::path path;
};

facman::core::Result<std::optional<DiscoveredJournal>> discover_root_journal(
    const fs::path &coordinator_root, const std::string &root_identity) {
  const fs::path directory = coordinator_root / "setup-operations";
  std::error_code status;
  if (!fs::exists(directory, status)) {
    if (status) return facman::core::Result<std::optional<DiscoveredJournal>>::failure(error(
        "self_setup_recovery_required", "setup coordinator journal directory could not be observed", status.message()));
    return facman::core::Result<std::optional<DiscoveredJournal>>::success({});
  }
  const std::string marker = "." + root_identity.substr(0, 32) + ".";
  constexpr std::size_t maximum_entries = 256;
  std::size_t entries = 0;
  std::optional<DiscoveredJournal> found;
  for (fs::directory_iterator iterator(directory, status), end; !status && iterator != end;
       iterator.increment(status)) {
    const fs::path candidate = iterator->path();
    const std::string name = candidate.filename().string();
    if (name.find("facman.") != 0 ||
        name.find(marker) == std::string::npos ||
        name.size() < std::string(".setup-operation.v1.json").size() ||
        name.compare(name.size() - std::string(".setup-operation.v1.json").size(),
                     std::string(".setup-operation.v1.json").size(),
                      ".setup-operation.v1.json") != 0)
      continue;
    if (++entries > maximum_entries)
      return facman::core::Result<std::optional<DiscoveredJournal>>::failure(error(
          "self_setup_recovery_required", "setup coordinator active journal set exceeds its entry limit"));
    auto journal = load_journal(candidate);
    if (!journal) return facman::core::Result<std::optional<DiscoveredJournal>>::failure(journal.error());
    if (journal.value().install_root_identity != root_identity)
      continue;
    const fs::path expected = journal_path(coordinator_root, journal.value().operation,
                                           root_identity, journal.value().intent_digest);
    if (candidate.filename() != expected.filename())
      return facman::core::Result<std::optional<DiscoveredJournal>>::failure(error(
          "self_setup_recovery_required", "setup coordinator journal filename does not bind its intent",
          facman::platform::path_to_utf8(candidate)));
    if (journal.value().state != "completed" &&
        journal.value().state != "rolled_back" &&
        journal.value().state != "abandoned") {
      if (journal.value().state != "abandoned") {
        if (found.has_value()) return facman::core::Result<std::optional<DiscoveredJournal>>::failure(error(
            "self_setup_recovery_required", "more than one setup operation for this install root remains unresolved",
            facman::platform::path_to_utf8(candidate)));
        found = DiscoveredJournal{journal.take_value(), candidate};
      }
    }
  }
  if (status) return facman::core::Result<std::optional<DiscoveredJournal>>::failure(error(
      "self_setup_recovery_required", "setup coordinator journal directory changed while being scanned", status.message()));
  return facman::core::Result<std::optional<DiscoveredJournal>>::success(std::move(found));
}


facman::core::Result<std::string> command(const std::string &name,
                                          const std::string &payload,
                                          const fs::path &state_root,
                                          const fs::path &acceptance_root,
                                          bool dry_run) {
  if (injected_provider != nullptr)
    return injected_provider->command(name, payload, state_root, acceptance_root, dry_run);
  // FacMan owns the outer setup-state root, including retained offline repair
  // inputs. Universal Setup receives a dedicated child so its ownership marker
  // and transaction records never compete with those FacMan-owned files.
  const fs::path provider_state_root = (state_root / "usk").lexically_normal();
  const std::string state = facman::platform::path_to_utf8(provider_state_root);
  const std::string acceptance =
      facman::platform::path_to_utf8(acceptance_root);
  usk_config_v1 config{};
  config.struct_size = sizeof(config);
  config.state_root = state.c_str();
  config.authorized_acceptance_root = acceptance.c_str();
  config.target_policy_activation = "operator_acceptance_candidate";

  usk_context *context = nullptr;
  if (usk_context_create_v1(&config, &context) != USK_STATUS_OK ||
      context == nullptr) {
    return facman::core::Result<std::string>::failure(
        error("self_setup_context_failed",
              "Universal Setup context creation failed"));
  }

  usk_command_request_v1 request{};
  usk_command_response_v1 response{};
  request.struct_size = sizeof(request);
  request.command_name = {name.data(), static_cast<usk_size>(name.size())};
  request.json_payload = {payload.data(),
                          static_cast<usk_size>(payload.size())};
  request.dry_run = dry_run ? 1 : 0;
  response.struct_size = sizeof(response);
  const int status = usk_command_execute_v1(context, &request, &response);
  std::string output;
  if (response.json_payload.data != nullptr) {
    output.assign(response.json_payload.data, response.json_payload.size);
  }
  usk_context_destroy_v1(context);
  if (status != USK_STATUS_OK) {
    return facman::core::Result<std::string>::failure(
        error("self_setup_provider_refused",
              "Universal Setup refused the operation", output));
  }
  return facman::core::Result<std::string>::success(std::move(output));
}

facman::core::Result<void> prepare_provider_parent(
    const fs::path &state_root, const fs::path &acceptance_root) {
  facman::platform::StableDirectoryObject acceptance;
  auto opened = acceptance.open_no_follow(acceptance_root);
  if (!opened.ok())
    return facman::core::Result<void>::failure(error(
        "self_setup_state_root_unsafe",
        "setup acceptance root is not a stable plain directory",
        opened.code + ": " + opened.detail));
  auto admitted = acceptance.validate_descendant(state_root, true);
  if (!admitted.ok())
    return facman::core::Result<void>::failure(error(
        "self_setup_state_root_unsafe",
        "FacMan setup-state root is outside its stable acceptance authority",
        admitted.code + ": " + admitted.detail));

  facman::platform::PathIdentity observed;
  auto inspected = facman::platform::inspect_path_no_follow(state_root, observed);
  if (!inspected.ok())
    return facman::core::Result<void>::failure(error(
        "self_setup_state_root_unsafe",
        "FacMan setup-state root could not be inspected",
        inspected.code + ": " + inspected.detail));
  if (!observed.exists) {
    std::error_code status;
    const bool created = fs::create_directory(state_root, status);
    if (status || !created)
      return facman::core::Result<void>::failure(error(
          "self_setup_state_root_unsafe",
          "FacMan setup-state root could not be created exclusively",
          status ? status.message() : "the admitted absent path changed before creation"));
  }

  facman::platform::StableDirectoryObject state;
  opened = state.open_no_follow(state_root);
  if (!opened.ok())
    return facman::core::Result<void>::failure(error(
        "self_setup_state_root_unsafe",
        "FacMan setup-state root is not a stable plain directory",
        opened.code + ": " + opened.detail));
  admitted = acceptance.validate_descendant(state_root);
  if (!admitted.ok())
    return facman::core::Result<void>::failure(error(
        "self_setup_state_root_unsafe",
        "FacMan setup-state root changed after creation",
        admitted.code + ": " + admitted.detail));
  auto stable = state.revalidate();
  if (!stable.ok())
    return facman::core::Result<void>::failure(error(
        "self_setup_state_root_unsafe",
        "FacMan setup-state root changed after it was opened",
        stable.code + ": " + stable.detail));
  return facman::core::Result<void>::success();
}

struct ProviderPlanIdentity {
  std::string plan_id;
  std::string digest;
};

facman::core::Result<ProviderPlanIdentity> plan_identity(const std::string &response) {
  auto document = json::parse(response);
  if (!document || !document.value().is_object() ||
      string_field(document.value(), "status") != "ok") {
    return facman::core::Result<ProviderPlanIdentity>::failure(
        error("self_setup_response_invalid",
              "Universal Setup returned an invalid plan envelope", response));
  }
  const json::Value *payload = document.value().find("payload");
  const std::string digest = payload != nullptr && payload->is_object()
      ? string_field(*payload, "plan_digest") : std::string();
  const std::string plan_id = payload != nullptr && payload->is_object()
      ? string_field(*payload, "plan_id") : std::string();
  if (digest.size() != 64 || !digest_or_empty(digest) || !bounded_identifier(plan_id)) {
    return facman::core::Result<ProviderPlanIdentity>::failure(
        error("self_setup_response_invalid",
              "Universal Setup plan has no valid identity", response));
  }
  return facman::core::Result<ProviderPlanIdentity>::success({plan_id, digest});
}

json::ObjectBuilder archive(const fs::path &package, const std::string &digest,
                            bool budgets) {
  json::ObjectBuilder result;
  result.add_string("path", facman::platform::path_to_utf8(package));
  result.add_string("format", "zip");
  result.add_string("expected_sha256", digest);
  result.add_string("strip_prefix", "facman");
  if (budgets) {
    json::ObjectBuilder limits;
    limits.add_unsigned_integer("max_entries", 100000);
    limits.add_unsigned_integer("max_uncompressed_bytes",
                                16ULL * 1024ULL * 1024ULL * 1024ULL);
    limits.add_unsigned_integer("max_entry_bytes",
                                8ULL * 1024ULL * 1024ULL * 1024ULL);
    limits.add_unsigned_integer("max_depth", 64);
    limits.add_unsigned_integer("max_ratio", 1000);
    limits.add_unsigned_integer("max_elapsed_ms", 600000);
    result.add_object("budgets", limits);
  }
  return result;
}

std::string recipe_digest(const Request &request,
                          const std::string &source_digest) {
  json::ObjectBuilder recipe;
  recipe.add_string("schema", "facman.self_setup_recipe.v1");
  recipe.add_string("product_id", "facman");
  recipe.add_string("product_version", request.product_version);
  recipe.add_string("provider_revision", provider_revision());
  recipe.add_string("source_sha256", source_digest);
  recipe.add_string("target_layout",
                    "versioned_generation_with_maintenance_v1");
  const std::string serialized = recipe.serialize();
  return facman::base::sha256_hex_bytes(
      reinterpret_cast<const unsigned char *>(serialized.data()),
      serialized.size());
}

json::ObjectBuilder
install_plan(const Request &request, const fs::path &package,
             const fs::path &install_root, const std::string &source_digest,
             const std::string &created_at, const std::string &request_id,
             const std::string &plan_id) {
  json::ArrayBuilder components;
  components.add_string("facman.product");
  components.add_string("facman.maintenance");

  const std::string generation = "generations/" + request.product_version + "/";
  json::ObjectBuilder gui;
  gui.add_string("entrypoint_id", "facman.gui");
  gui.add_string("kind", "application");
  gui.add_string("relative_path", generation + "FacMan.exe");
  json::ObjectBuilder cli;
  cli.add_string("entrypoint_id", "facman.cli");
  cli.add_string("kind", "tool");
  cli.add_string("relative_path", generation + "bin/facman.exe");
  json::ObjectBuilder maintenance;
  maintenance.add_string("entrypoint_id", "facman.setup");
  maintenance.add_string("kind", "tool");
  maintenance.add_string("relative_path", "maintenance/FacManSetup.exe");
  json::ArrayBuilder entrypoints;
  entrypoints.add_object(gui);
  entrypoints.add_object(cli);
  entrypoints.add_object(maintenance);

  json::ObjectBuilder recipe;
  recipe.add_string("product_id", "facman");
  recipe.add_string("product_version", request.product_version);
  recipe.add_string("recipe_digest", recipe_digest(request, source_digest));
  recipe.add_string("provider_revision", provider_revision());
  recipe.add_array("components", components);
  recipe.add_array("entrypoints", entrypoints);

  json::ObjectBuilder target;
  target.add_string("root", facman::platform::path_to_utf8(install_root));
  target.add_string("class", "operator_acceptance");

  json::ObjectBuilder plan;
  plan.add_string("schema", "usk.install_local_plan_request.v1");
  plan.add_string("request_id", request_id);
  plan.add_string("created_at", created_at);
  plan.add_string("install_id", "facman.self");
  plan.add_object("archive", archive(package, source_digest, true));
  plan.add_object("target", target);
  plan.add_object("recipe", recipe);
  (void)plan_id;
  return plan;
}

enum class ProviderProgress {
  before_plan,
  plan_reviewed,
  apply_entered,
};

facman::core::Result<json::ObjectBuilder> apply_request(const char *schema,
                                  const json::ObjectBuilder &plan,
                                  const std::string &plan_id,
                                  const std::string &digest,
                                  const std::string &plan_created_at,
                                  const std::string &transaction_id,
                                  Clock *clock) {
  auto parsed_plan = json::parse(plan.serialize());
  auto applied_at = timestamp_after(plan_created_at, clock);
  if (!applied_at)
    return facman::core::Result<json::ObjectBuilder>::failure(applied_at.error());
  json::ObjectBuilder apply;
  apply.add_string("schema", schema);
  apply.add_string("transaction_id", transaction_id);
  // USK preserves second-resolution immutable lifecycle timestamps and
  // requires every mutating result to advance them.  Waiting here keeps the
  // receipt truthful even when plan and apply occur within the same second.
  apply.add_string("applied_at", applied_at.take_value());
  apply.add_string("confirmation", "APPLY");
  apply.add_string("reviewed_plan_id", plan_id);
  apply.add_string("reviewed_plan_digest", digest);
  if (parsed_plan)
    apply.add_value("plan_request", parsed_plan.value());
  return facman::core::Result<json::ObjectBuilder>::success(std::move(apply));
}

facman::core::Result<Response>
install_or_repair(const Request &request, const fs::path &package,
                  const fs::path &install_root, const fs::path &state_root,
                  const fs::path &acceptance_root, SetupJournal *identity = nullptr,
                   const fs::path *identity_path = nullptr,
                   const std::string *bound_source_digest = nullptr,
                   ProviderProgress *provider_progress = nullptr) {
  if (provider_progress != nullptr)
    *provider_progress = ProviderProgress::before_plan;
  std::error_code status;
  if (!fs::is_regular_file(package, status) || status) {
    return facman::core::Result<Response>::failure(error(
        "self_setup_package_missing", "The setup payload is not a regular file",
        facman::platform::path_to_utf8(package)));
  }
  auto stable_digest = bound_source_digest == nullptr
      ? stable_file_digest(package)
      : facman::core::Result<std::string>::success(*bound_source_digest);
  if (!stable_digest || stable_digest.value().size() != 64) {
    return facman::core::Result<Response>::failure(
        error("self_setup_package_hash_failed",
              "The setup payload could not be hashed"));
  }
  const std::string source_digest = stable_digest.take_value();
  const std::string created_at = identity == nullptr
      ? timestamp() : identity->provider_created_at;
  const std::string request_id = identity == nullptr ? identifier(
      request.operation == Operation::install ? "request.facman.install"
                                              : "request.facman.repair") : identity->provider_request_id;
  const std::string plan_id = identity != nullptr ? identity->provider_plan_id : request.operation == Operation::install
                                  ? request_id
                                  : identifier("plan.facman.repair");
  json::ObjectBuilder plan;
  std::string plan_command;
  std::string apply_command;
  const char *apply_schema = nullptr;
  if (request.operation == Operation::install) {
    plan = install_plan(request, package, install_root, source_digest,
                        created_at, request_id, plan_id);
    plan_command = "install_local.plan";
    apply_command = "install_local.apply";
    apply_schema = "usk.install_local_apply_request.v1";
  } else {
    plan.add_string("schema", "usk.repair_plan_request.v1");
    plan.add_string("request_id", request_id);
    plan.add_string("plan_id", plan_id);
    plan.add_string("install_id", "facman.self");
    plan.add_string("created_at", created_at);
    plan.add_object("archive", archive(package, source_digest, false));
    plan_command = "repair.plan";
    apply_command = "repair.apply";
    apply_schema = "usk.repair_apply_request.v1";
  }

  // Preview remains effect-free. During an applied first install FacMan
  // creates only its outer state directory, after durable intent exists and
  // before planning. Universal Setup still exclusively creates and marks its
  // dedicated `usk` child, and both plan and apply observe the same parent.
  if (identity != nullptr && injected_provider == nullptr &&
      request.operation == Operation::install) {
    auto prepared = prepare_provider_parent(state_root, acceptance_root);
    if (!prepared)
      return facman::core::Result<Response>::failure(prepared.error());
  }

  auto planned = command(plan_command, plan.serialize(), state_root,
                         acceptance_root, true);
  if (!planned)
    return facman::core::Result<Response>::failure(planned.error());
  if (!request.apply) {
    return facman::core::Result<Response>::success(
        {request.operation == Operation::install ? "install" : "repair", "plan",
         planned.take_value(), {}});
  }
  auto reviewed = plan_identity(planned.value());
  if (!reviewed)
    return facman::core::Result<Response>::failure(reviewed.error());
  if (identity != nullptr) {
    // install_local plan_id is request_id by USK contract; never substitute
    // a locally invented plan namespace for that authoritative identity.
    if (reviewed.value().plan_id != identity->provider_plan_id ||
        (request.operation == Operation::install &&
         reviewed.value().plan_id != identity->provider_request_id))
      return facman::core::Result<Response>::failure(error(
          "self_setup_recovery_required", "provider plan identity differs from durable intent"));
    if (!identity->provider_plan_digest.empty() &&
        identity->provider_plan_digest != reviewed.value().digest)
      return facman::core::Result<Response>::failure(error(
          "self_setup_recovery_required",
          "provider plan changed after its durable review boundary"));
    identity->provider_plan_digest = reviewed.value().digest;
    identity->provider_phase = "plan_reviewed";
    if (identity_path == nullptr)
      return facman::core::Result<Response>::failure(error(
          "self_setup_journal_write_failed", "provider plan has no durable journal path"));
    auto persisted = persist_journal(*identity_path, *identity);
    if (!persisted)
      return facman::core::Result<Response>::failure(persisted.error());
    if (request.durable_boundary_hook != nullptr &&
        !request.durable_boundary_hook->reached(
            DurableBoundary::provider_plan_reviewed))
      return facman::core::Result<Response>::failure(error(
          "self_setup_interrupted",
          "setup operation interrupted after its provider plan-review boundary",
          facman::platform::path_to_utf8(*identity_path)));
  }
  if (provider_progress != nullptr)
    *provider_progress = ProviderProgress::plan_reviewed;
  auto apply =
      apply_request(apply_schema, plan, reviewed.value().plan_id, reviewed.value().digest, created_at,
                    identity == nullptr ? identifier("tx.facman.self") : identity->provider_transaction_id,
                    request.clock);
  if (!apply) return facman::core::Result<Response>::failure(apply.error());
  if (identity != nullptr) {
    identity->provider_phase = "apply_entered";
    auto persisted = persist_journal(*identity_path, *identity);
    if (!persisted)
      return facman::core::Result<Response>::failure(persisted.error());
  }
  if (provider_progress != nullptr)
    *provider_progress = ProviderProgress::apply_entered;
  auto applied = command(apply_command, apply.value().serialize(), state_root,
                         acceptance_root, false);
  if (!applied)
    return facman::core::Result<Response>::failure(applied.error());
  return facman::core::Result<Response>::success(
      {request.operation == Operation::install ? "install" : "repair",
       "receipt", applied.take_value(), {}});
}

facman::core::Result<Response> verify(const fs::path &state_root,
                                      const fs::path &acceptance_root) {
  json::ObjectBuilder payload;
  payload.add_string("schema", "usk.installed_verify_request.v1");
  payload.add_string("request_id", identifier("request.facman.verify"));
  payload.add_string("install_id", "facman.self");
  payload.add_string("report_id", identifier("report.facman.verify"));
  payload.add_string("verified_at", timestamp());
  auto response = command("installed.verify", payload.serialize(), state_root,
                          acceptance_root, true);
  if (!response)
    return facman::core::Result<Response>::failure(response.error());
  return facman::core::Result<Response>::success(
      {"verify", "receipt", response.take_value(), {}});
}

facman::core::Result<std::string> inspect_installed_source(
    const Request &request, const fs::path &state_root,
    const fs::path &acceptance_root, const std::string &request_id) {
  json::ObjectBuilder inspection;
  inspection.add_string("schema", "usk.installed_inspect_request.v1");
  inspection.add_string("request_id", request_id + ".installed");
  inspection.add_string("install_id", "facman.self");
  auto response = command("installed.inspect", inspection.serialize(),
                          state_root, acceptance_root, true);
  if (!response) return facman::core::Result<std::string>::failure(response.error());
  auto envelope = json::parse(response.value());
  const json::Value *response_error = envelope && envelope.value().is_object()
      ? envelope.value().find("error") : nullptr;
  const json::Value *payload = envelope && envelope.value().is_object()
      ? envelope.value().find("payload") : nullptr;
  const json::Value *setup_abi = payload != nullptr && payload->is_object()
      ? payload->find("setup_abi") : nullptr;
  if (!envelope ||
      !exact_keys(envelope.value(), {"error", "payload", "schema", "status"}) ||
      string_field(envelope.value(), "schema") != "usk.command_response.v1" ||
      string_field(envelope.value(), "status") != "ok" ||
      response_error == nullptr || !response_error->is_null() ||
      payload == nullptr || !payload->is_object() ||
      !exact_keys(*payload, {"audit_chain_id", "component_selection", "created_at",
          "entrypoints", "install_id", "last_verification", "lifecycle_status",
          "ownership_manifest_digest", "ownership_manifest_ref", "product_id",
          "product_version", "recipe_digest", "schema", "setup_abi",
          "source_archive_digest", "target_root", "target_scope", "transaction_id"}) ||
      setup_abi == nullptr || !setup_abi->is_object() ||
      !exact_keys(*setup_abi, {"major", "minor", "provider_revision"}) ||
      string_field(*payload, "schema") != "usk.installed_state.v1" ||
      string_field(*payload, "install_id") != "facman.self" ||
      string_field(*payload, "product_id") != "facman" ||
      string_field(*payload, "product_version") != request.product_version ||
      !one_of(string_field(*payload, "lifecycle_status"), {"installed", "verified"}) ||
      string_field(*setup_abi, "provider_revision") != provider_revision())
    return facman::core::Result<std::string>::failure(error(
        "self_setup_response_invalid",
        "Universal Setup installed-state inspection is incompatible",
        response.value()));
  auto observed_root = absolute_path(
      facman::platform::path_from_utf8(string_field(*payload, "target_root")),
      "installed-state target root");
  auto expected_root = canonical_install_root(request.install_root);
  auto actual_root = observed_root
      ? canonical_install_root(observed_root.value())
      : facman::core::Result<std::string>::failure(observed_root.error());
  const std::string source_digest = string_field(*payload, "source_archive_digest");
  if (!observed_root || !expected_root || !actual_root ||
      actual_root.value() != expected_root.value() ||
      source_digest.size() != 64U || !digest_or_empty(source_digest))
    return facman::core::Result<std::string>::failure(error(
        "self_setup_response_invalid",
        "Universal Setup installed-state identity does not bind this install",
        response.value()));
  return facman::core::Result<std::string>::success(source_digest);
}

facman::core::Result<Response> uninstall(const Request &request,
                                         const fs::path &state_root,
                                         const fs::path &acceptance_root,
                                         SetupJournal *identity = nullptr,
                                         const fs::path *identity_path = nullptr,
                                         ProviderProgress *provider_progress = nullptr) {
  if (provider_progress != nullptr)
    *provider_progress = ProviderProgress::before_plan;
  const std::string plan_id = identity == nullptr ? identifier("plan.facman.uninstall") : identity->provider_plan_id;
  const std::string created_at = identity == nullptr
      ? timestamp() : identity->provider_created_at;
  json::ObjectBuilder plan;
  plan.add_string("schema", "usk.uninstall_plan_request.v1");
  plan.add_string("request_id", identity == nullptr ? identifier("request.facman.uninstall") : identity->provider_request_id);
  plan.add_string("plan_id", plan_id);
  plan.add_string("install_id", "facman.self");
  plan.add_string("created_at", created_at);
  auto inspected_source = inspect_installed_source(
      request, state_root, acceptance_root,
      identity == nullptr ? identifier("request.facman.uninstall")
                          : identity->provider_request_id);
  if (!inspected_source)
    return facman::core::Result<Response>::failure(inspected_source.error());
  if (identity != nullptr) {
    identity->installed_source_digest = inspected_source.value();
    if (identity_path == nullptr)
      return facman::core::Result<Response>::failure(error(
          "self_setup_journal_write_failed",
          "installed source inspection has no durable journal path"));
    auto persisted = persist_journal(*identity_path, *identity);
    if (!persisted)
      return facman::core::Result<Response>::failure(persisted.error());
  }
  auto planned = command("uninstall.plan", plan.serialize(), state_root,
                         acceptance_root, true);
  if (!planned)
    return facman::core::Result<Response>::failure(planned.error());
  if (!request.apply) {
    return facman::core::Result<Response>::success(
        {"uninstall", "plan", planned.take_value(), {}});
  }
  auto reviewed = plan_identity(planned.value());
  if (!reviewed)
    return facman::core::Result<Response>::failure(reviewed.error());
  if (identity != nullptr) {
    auto envelope = json::parse(planned.value());
    const json::Value *payload = envelope && envelope.value().is_object()
        ? envelope.value().find("payload") : nullptr;
    const json::Value *input_identity = payload != nullptr && payload->is_object()
        ? payload->find("input_identity") : nullptr;
    const std::string installed_source = input_identity != nullptr && input_identity->is_object()
        ? string_field(*input_identity, "source_digest") : std::string();
    if (payload == nullptr || !payload->is_object() ||
        string_field(*payload, "schema") != "usk.operation_plan.v1" ||
        string_field(*payload, "operation") != "uninstall" ||
        string_field(*payload, "status") != "planned" ||
        string_field(*payload, "install_id") != "facman.self" ||
        input_identity == nullptr || !input_identity->is_object() ||
        string_field(*input_identity, "provider_revision") != provider_revision() ||
        installed_source.size() != 64U || !digest_or_empty(installed_source) ||
        installed_source != inspected_source.value())
      return facman::core::Result<Response>::failure(error(
          "self_setup_response_invalid",
          "Universal Setup uninstall plan has no exact installed source identity",
           planned.value()));
    if (reviewed.value().plan_id != identity->provider_plan_id)
      return facman::core::Result<Response>::failure(error(
          "self_setup_recovery_required", "provider plan identity differs from durable intent"));
    if (provider_progress != nullptr)
      *provider_progress = ProviderProgress::plan_reviewed;
    if (!identity->provider_plan_digest.empty() &&
        identity->provider_plan_digest != reviewed.value().digest)
      return facman::core::Result<Response>::failure(error(
          "self_setup_recovery_required",
          "provider plan changed after its durable review boundary"));
    identity->provider_plan_digest = reviewed.value().digest;
    identity->provider_phase = "plan_reviewed";
    if (identity_path == nullptr)
      return facman::core::Result<Response>::failure(error(
          "self_setup_journal_write_failed", "provider plan has no durable journal path"));
    auto persisted = persist_journal(*identity_path, *identity);
    if (!persisted)
      return facman::core::Result<Response>::failure(persisted.error());
    if (request.durable_boundary_hook != nullptr &&
        !request.durable_boundary_hook->reached(
            DurableBoundary::provider_plan_reviewed))
      return facman::core::Result<Response>::failure(error(
          "self_setup_interrupted",
          "setup operation interrupted after its provider plan-review boundary",
          facman::platform::path_to_utf8(*identity_path)));
    if (request.native_effects != nullptr) {
      const fs::path repair_source = state_root / "repair-sources" /
          facman::platform::path_from_utf8(installed_source + ".zip");
      const NativeContext native_context{Operation::uninstall,
          request.install_root, state_root, acceptance_root, repair_source,
          request.product_version};
      const auto retained = request.native_effects->validate_maintenance_launcher(
          native_context, installed_source);
      if (!retained.ok || retained.path !=
              repair_source.parent_path() /
                  facman::platform::path_from_utf8(
                      installed_source + ".FacManSetup.exe"))
        return facman::core::Result<Response>::failure(error(
            "self_setup_recovery_required",
            "offline maintenance identity is invalid before uninstall",
            retained.detail));
    }
  }
  auto apply =
      apply_request("usk.uninstall_apply_request.v1", plan, plan_id,
                    reviewed.value().digest, created_at,
                    identity == nullptr ? identifier("tx.facman.self") : identity->provider_transaction_id,
                    request.clock);
  if (!apply) return facman::core::Result<Response>::failure(apply.error());
  if (identity != nullptr) {
    identity->provider_phase = "apply_entered";
    auto persisted = persist_journal(*identity_path, *identity);
    if (!persisted)
      return facman::core::Result<Response>::failure(persisted.error());
  }
  if (provider_progress != nullptr)
    *provider_progress = ProviderProgress::apply_entered;
  auto applied = command("uninstall.apply", apply.value().serialize(), state_root,
                         acceptance_root, false);
  if (!applied)
    return facman::core::Result<Response>::failure(applied.error());
  return facman::core::Result<Response>::success(
      {"uninstall", "receipt", applied.take_value(), {}});
}

bool definitive_pre_effect_uninstall_refusal(const facman::core::Error &provider_error) {
  if (provider_error.code != "self_setup_provider_refused") return false;
  auto envelope = json::parse(provider_error.detail);
  const json::Value *refusal = envelope && envelope.value().is_object()
      ? envelope.value().find("error") : nullptr;
  return envelope && envelope.value().is_object() &&
      string_field(envelope.value(), "schema") == "usk.command_response.v1" &&
      string_field(envelope.value(), "status") == "refused" &&
      refusal != nullptr && refusal->is_object() &&
      string_field(*refusal, "code") == "foreign_content_review_required";
}

bool has_action(const json::Value &envelope, const char *action) {
  const json::Value *payload = envelope.find("payload");
  const json::Value *actions = payload == nullptr ? nullptr : payload->find("available_actions");
  if (actions == nullptr || !actions->is_array()) return false;
  for (std::size_t index = 0; index < actions->size(); ++index) {
    const json::Value *value = actions->at(index);
    if (value != nullptr && value->string_value() &&
        value->string_value().value() == action) return true;
  }
  return false;
}

facman::core::Result<Response> review_provider_rollback(
    SetupJournal &journal, const fs::path &target_root,
    const fs::path &state_root, const fs::path &acceptance_root) {
  json::ObjectBuilder inspection;
  inspection.add_string("schema", "usk.recovery_inspect_request.v1");
  inspection.add_string("request_id", "recovery.inspect." + journal.operation_id);
  inspection.add_string("install_id", "facman.self");
  inspection.add_string("transaction_id", journal.provider_transaction_id);
  inspection.add_string("plan_id", journal.provider_plan_id);
  inspection.add_string("plan_digest", journal.provider_plan_digest);
  inspection.add_string("operation", journal.operation == "install" ? "install_local" : journal.operation);
  inspection.add_string("target_root", facman::platform::path_to_utf8(target_root));
  const std::string inspection_bytes = inspection.serialize();
  auto inspected = command("recovery.inspect", inspection_bytes, state_root, acceptance_root, true);
  if (!inspected) return facman::core::Result<Response>::failure(inspected.error());
  auto inspection_document = json::parse(inspected.value());
  const json::Value *inspection_payload = inspection_document && inspection_document.value().is_object()
      ? inspection_document.value().find("payload") : nullptr;
  if (!inspection_document || string_field(inspection_document.value(), "status") != "ok" ||
      inspection_payload == nullptr || !inspection_payload->is_object() ||
      string_field(*inspection_payload, "schema") != "usk.recovery_report.v1" ||
      string_field(*inspection_payload, "status") != "inspection_only" ||
      string_field(*inspection_payload, "transaction_id") != journal.provider_transaction_id ||
      string_field(*inspection_payload, "report_digest").empty() || string_field(*inspection_payload, "journal_digest").empty() ||
      !digest_or_empty(string_field(*inspection_payload, "report_digest")) ||
      !digest_or_empty(string_field(*inspection_payload, "journal_digest")) ||
      !has_action(inspection_document.value(), "rollback"))
    return facman::core::Result<Response>::failure(error(
        "self_setup_recovery_required", "provider recovery does not offer a safe rollback", inspected.value()));
  auto inspection_value = json::parse(inspection_bytes);
  if (!inspection_value) return facman::core::Result<Response>::failure(error(
      "self_setup_recovery_required", "provider recovery inspection could not be reconstructed"));
  journal.recovery_plan_id = "recovery.plan." + journal.operation_id;
  journal.recovery_plan_created_at = timestamp();
  journal.recovery_action = "rollback";
  json::ObjectBuilder plan;
  plan.add_string("schema", "usk.recovery_plan_request.v1");
  plan.add_value("inspection", inspection_value.value());
  plan.add_string("recovery_plan_id", journal.recovery_plan_id);
  plan.add_string("created_at", journal.recovery_plan_created_at);
  auto planned = command("recovery.plan", plan.serialize(), state_root, acceptance_root, true);
  if (!planned) return facman::core::Result<Response>::failure(planned.error());
  auto identity = plan_identity(planned.value());
  if (!identity || identity.value().plan_id != journal.recovery_plan_id)
    return facman::core::Result<Response>::failure(error(
        "self_setup_recovery_required", "provider recovery plan identity is invalid", planned.value()));
  journal.recovery_plan_digest = identity.value().digest;
  return facman::core::Result<Response>::success(
      {journal.operation, "recovery_plan", planned.take_value(), journal.operation_id});
}

facman::core::Result<void> apply_reviewed_provider_rollback(
    const SetupJournal &journal, const fs::path &target_root,
    const fs::path &state_root, const fs::path &acceptance_root,
    Clock *clock) {
  if (journal.recovery_action != "rollback" || journal.recovery_plan_id.empty() ||
      journal.recovery_plan_digest.empty() || journal.recovery_plan_created_at.empty())
    return facman::core::Result<void>::failure(error(
        "self_setup_recovery_preview_required",
        "review the provider recovery plan, then repeat with --yes"));
  json::ObjectBuilder inspection;
  inspection.add_string("schema", "usk.recovery_inspect_request.v1");
  inspection.add_string("request_id", "recovery.inspect." + journal.operation_id);
  inspection.add_string("install_id", "facman.self");
  inspection.add_string("transaction_id", journal.provider_transaction_id);
  inspection.add_string("plan_id", journal.provider_plan_id);
  inspection.add_string("plan_digest", journal.provider_plan_digest);
  inspection.add_string("operation", journal.operation == "install" ? "install_local" : journal.operation);
  inspection.add_string("target_root", facman::platform::path_to_utf8(target_root));
  auto inspection_value = json::parse(inspection.serialize());
  if (!inspection_value) return facman::core::Result<void>::failure(error("self_setup_recovery_required", "recovery inspection could not be reconstructed"));
  json::ObjectBuilder plan;
  plan.add_string("schema", "usk.recovery_plan_request.v1");
  plan.add_value("inspection", inspection_value.value());
  plan.add_string("recovery_plan_id", journal.recovery_plan_id);
  plan.add_string("created_at", journal.recovery_plan_created_at);
  const std::string plan_bytes = plan.serialize();
  auto planned = command("recovery.plan", plan_bytes, state_root, acceptance_root, true);
  if (!planned) return facman::core::Result<void>::failure(planned.error());
  auto identity = plan_identity(planned.value());
  if (!identity || identity.value().plan_id != journal.recovery_plan_id ||
      identity.value().digest != journal.recovery_plan_digest)
    return facman::core::Result<void>::failure(error(
        "self_setup_recovery_preview_required", "provider recovery plan changed; review a new plan before applying", planned.value()));
  auto plan_value = json::parse(plan_bytes);
  auto applied_at = timestamp_after(journal.recovery_plan_created_at, clock);
  if (!plan_value || !applied_at) return facman::core::Result<void>::failure(
      applied_at ? error("self_setup_recovery_required", "recovery plan could not be reconstructed") : applied_at.error());
  json::ObjectBuilder apply;
  apply.add_string("schema", "usk.recovery_apply_request.v1");
  apply.add_value("plan_request", plan_value.value());
  apply.add_string("reviewed_plan_id", journal.recovery_plan_id);
  apply.add_string("reviewed_plan_digest", journal.recovery_plan_digest);
  apply.add_string("selected_action", "rollback");
  apply.add_string("applied_at", applied_at.take_value());
  apply.add_string("confirmation", "APPLY");
  auto applied = command("recovery.apply", apply.serialize(), state_root, acceptance_root, false);
  if (!applied) return facman::core::Result<void>::failure(applied.error());
  auto receipt = json::parse(applied.value());
  const json::Value *payload = receipt && receipt.value().is_object() ? receipt.value().find("payload") : nullptr;
  if (!receipt || string_field(receipt.value(), "status") != "ok" || payload == nullptr || !payload->is_object() ||
      string_field(*payload, "schema") != "usk.recovery_report.v1" ||
      string_field(*payload, "status") != "rolled_back" ||
      string_field(*payload, "selected_action") != "rollback" ||
      string_field(*payload, "transaction_id") != journal.provider_transaction_id ||
      string_field(*payload, "report_digest").empty() || string_field(*payload, "journal_digest").empty() ||
      !digest_or_empty(string_field(*payload, "report_digest")) || !digest_or_empty(string_field(*payload, "journal_digest")))
    return facman::core::Result<void>::failure(error(
        "self_setup_recovery_required", "provider rollback receipt is invalid", applied.value()));
  return facman::core::Result<void>::success();
}

} // namespace

facman::core::Result<Response> execute(const Request &request) {
  ScopedProviderEffects provider_scope(request.provider_effects);
  if (request.operation == Operation::verify) {
    auto state = absolute_path(request.state_root, "state root");
    auto acceptance = absolute_path(request.acceptance_root, "acceptance root");
    if (!state || !acceptance)
      return facman::core::Result<Response>::failure(!state ? state.error() : acceptance.error());
    return verify(state.value(), acceptance.value());
  }
  auto install = canonical_install_root(request.install_root);
  auto install_target = absolute_path(request.install_root, "install root");
  auto state = absolute_path(request.state_root, "state root");
  auto acceptance = absolute_path(request.acceptance_root, "acceptance root");
  if (!install || !install_target || !state || !acceptance)
    return facman::core::Result<Response>::failure(!install ? install.error() : !install_target ? install_target.error() : !state ? state.error() : acceptance.error());
  std::optional<QualificationClaims> qualification;
  if (request.qualification_claims.has_value()) {
    qualification = request.qualification_claims;
    auto claimed_install = absolute_path(qualification->install_root,
                                         "qualification install root");
    auto claimed_state = absolute_path(qualification->state_root,
                                       "qualification state root");
    auto claimed_acceptance = absolute_path(qualification->acceptance_root,
                                            "qualification acceptance root");
    if (!claimed_install || !claimed_state || !claimed_acceptance ||
        qualification->operation != request.operation ||
        qualification->product_version != request.product_version ||
        qualification->installed_mode != (request.native_effects != nullptr) ||
        facman::platform::path_to_utf8(claimed_install.value()) !=
            facman::platform::path_to_utf8(install_target.value()) ||
        facman::platform::path_to_utf8(claimed_state.value()) !=
            facman::platform::path_to_utf8(state.value()) ||
        facman::platform::path_to_utf8(claimed_acceptance.value()) !=
            facman::platform::path_to_utf8(acceptance.value()))
      return facman::core::Result<Response>::failure(error(
          "self_setup_qualification_interrupt_invalid",
          "qualification claims do not bind this exact setup request"));
    qualification->install_root = claimed_install.take_value();
    qualification->state_root = claimed_state.take_value();
    qualification->acceptance_root = claimed_acceptance.take_value();
  }
  auto coordinator = coordinator_state_root(request);
  if (!coordinator) return facman::core::Result<Response>::failure(coordinator.error());
  const std::string root_text = facman::platform::path_to_utf8(install_target.value());
  const std::string root_identity = digest_text("facman.setup.root.v1\n" + install.value());
  const std::string provisional_operation_id = "setup.admission." + identifier("attempt");
  auto held_lock = acquire_setup_lock(coordinator.value(), root_identity, provisional_operation_id);
  if (!held_lock) return facman::core::Result<Response>::failure(held_lock.error());

  // Admission runs before reading or hashing a new payload. A caller changing
  // source/version/mode/provider roots therefore cannot bypass an unfinished
  // durable operation for this canonical install root.
  auto discovered = discover_root_journal(coordinator.value(), root_identity);
  if (!discovered) return facman::core::Result<Response>::failure(discovered.error());
  Request active = request;
  SetupJournal journal;
  fs::path record_path;
  bool record_exists = false;
  std::string operation;
  std::string source_digest;
  std::string intent_digest;
  std::string operation_id;
  std::string mode;
  if (discovered.value().has_value()) {
    journal = discovered.value()->journal;
    record_path = discovered.value()->path;
    record_exists = true;
    auto old_root = absolute_path(fs::path(journal.install_root), "journal install root");
    auto old_identity = old_root ? canonical_install_root(old_root.value())
        : facman::core::Result<std::string>::failure(old_root.error());
    auto old_state = absolute_path(fs::path(journal.provider_state_root), "journal provider state root");
    auto old_acceptance = absolute_path(fs::path(journal.provider_acceptance_root), "journal provider acceptance root");
    if (!old_root || !old_identity || !old_state || !old_acceptance ||
        digest_text("facman.setup.root.v1\n" + old_identity.value()) != journal.install_root_identity)
      return facman::core::Result<Response>::failure(error(
          "self_setup_recovery_required", "setup journal provider authority paths are invalid", record_path.string()));
    if (qualification.has_value()) {
      const bool claim_mismatch =
          journal.operation != operation_name(qualification->operation) ||
          journal.product_version != qualification->product_version ||
          journal.mode != (qualification->installed_mode ? "installed" : "portable") ||
          facman::platform::path_to_utf8(old_root.value()) !=
              facman::platform::path_to_utf8(qualification->install_root) ||
          facman::platform::path_to_utf8(old_state.value()) !=
              facman::platform::path_to_utf8(qualification->state_root) ||
          facman::platform::path_to_utf8(old_acceptance.value()) !=
              facman::platform::path_to_utf8(qualification->acceptance_root);
      const bool boundary_crossed =
          qualification->boundary == DurableBoundary::provider_plan_reviewed
              ? journal.provider_phase != "before_plan"
              : qualification->boundary == DurableBoundary::files_applied
                    ? journal.files == "applied"
                    : journal.shortcut == "applied";
      if (claim_mismatch || boundary_crossed)
        return facman::core::Result<Response>::failure(error(
            "self_setup_qualification_interrupt_invalid",
            claim_mismatch
                ? "qualification claims do not bind the unfinished setup journal"
                : "qualification boundary was already crossed by the unfinished setup journal",
            facman::platform::path_to_utf8(record_path)));
    }
    active.install_root = old_root.take_value();
    active.state_root = old_state.take_value();
    active.acceptance_root = old_acceptance.take_value();
    active.product_version = journal.product_version;
    active.operation = journal.operation == "install" ? Operation::install :
                       journal.operation == "repair" ? Operation::repair : Operation::uninstall;
    // Native authority is part of the durable intent. A later caller cannot
    // turn a portable operation into an installed one by supplying an adapter.
    active.native_effects = journal.mode == "installed" ? request.native_effects : nullptr;
    operation = journal.operation;
    source_digest = journal.provider_source_digest;
    intent_digest = journal.intent_digest;
    operation_id = journal.operation_id;

    if (journal.state == "recovery_required")
      return facman::core::Result<Response>::failure(error(
          "self_setup_recovery_required", "a prior setup operation requires manual recovery", record_path.string()));
    if (journal.files != "applied" &&
        journal.provider_phase == "apply_entered") {
      if (!active.apply) {
        auto reviewed = review_provider_rollback(
            journal, active.install_root, active.state_root,
            active.acceptance_root);
        if (!reviewed) return facman::core::Result<Response>::failure(reviewed.error());
        auto persisted = persist_journal(record_path, journal);
        if (!persisted) return facman::core::Result<Response>::failure(persisted.error());
        return reviewed;
      } else {
        auto recovered = apply_reviewed_provider_rollback(
            journal, active.install_root, active.state_root,
            active.acceptance_root, active.clock);
        if (!recovered) return facman::core::Result<Response>::failure(recovered.error());
        journal.state = "rolled_back";
        journal.recovery_boundary = "provider_rollback_completed";
        journal.last_error = "provider_rolled_back_new_attempt_required";
        auto persisted = persist_journal(record_path, journal);
        if (!persisted) return facman::core::Result<Response>::failure(persisted.error());
        return facman::core::Result<Response>::failure(error(
            "self_setup_recovery_required",
            "provider rollback completed; submit a new setup operation instead of replaying its transaction",
            record_path.string()));
      }
    }
    if (record_exists && active.native_effects == nullptr && journal.mode == "installed")
      return facman::core::Result<Response>::failure(error(
          "self_setup_recovery_required", "an installed setup journal needs a native integration adapter", record_path.string()));
  }
  if (!record_exists) {
    active = request;
    if (active.product_version.empty()) return facman::core::Result<Response>::failure(error(
        "self_setup_version_missing", "The FacMan product version is required"));
    active.install_root = install_target.value(); active.state_root = state.value(); active.acceptance_root = acceptance.value();
    if (active.operation != Operation::uninstall) {
      if (active.package_materializer != nullptr) {
        auto materialized = active.package_materializer->materialize(active.package);
        if (!materialized)
          return facman::core::Result<Response>::failure(materialized.error());
        active.package = materialized.take_value();
      }
      auto checked = absolute_path(active.package, "setup payload");
      if (!checked)
        return facman::core::Result<Response>::failure(checked.error());
      active.package = checked.take_value();
      std::error_code package_status;
      if (!fs::is_regular_file(active.package, package_status) || package_status)
        return facman::core::Result<Response>::failure(error(
            "self_setup_package_missing",
            "The setup payload is not a regular file",
            facman::platform::path_to_utf8(active.package)));
      auto digest = stable_file_digest(active.package);
      if (!digest)
        return facman::core::Result<Response>::failure(digest.error());
      source_digest = digest.take_value();
    } else {
      source_digest = digest_text("facman.setup.uninstall.v1\n" + root_text);
    }
    operation = operation_name(active.operation);
    mode = active.native_effects == nullptr ? "portable" : "installed";
    SetupJournal intended;
    intended.operation = operation; intended.install_root_identity = root_identity;
    intended.product_version = active.product_version; intended.mode = mode;
    intended.provider_source_digest = source_digest;
    intended.provider_state_root = facman::platform::path_to_utf8(active.state_root);
    intended.provider_acceptance_root = facman::platform::path_to_utf8(active.acceptance_root);
    intent_digest = journal_intent_digest(intended);
    const std::string attempt_id = identifier("attempt");
    operation_id = "setup." + digest_text(
        "facman.setup.operation.v2\n" + operation + "\n" + attempt_id + "\n" +
        intent_digest).substr(0, 24);
    record_path = journal_path(coordinator.value(), operation, root_identity, intent_digest);
    std::error_code exists_error;
    if (fs::exists(record_path, exists_error) && !exists_error) {
      auto restored = load_journal(record_path);
      if (!restored) return facman::core::Result<Response>::failure(restored.error());
      journal = restored.take_value();
      auto archived = archive_journal(record_path, journal);
      if (!archived) return facman::core::Result<Response>::failure(archived.error());
    } else if (exists_error) return facman::core::Result<Response>::failure(error(
        "self_setup_recovery_required", "setup operation journal could not be observed", record_path.string()));
  }

  if (record_exists && active.operation != Operation::uninstall &&
      journal.files != "applied") {
    const bool use_retained_source =
        journal.mode == "installed" && journal.repair_source == "applied";
    if (use_retained_source) {
      active.package = active.state_root / "repair-sources" /
          facman::platform::path_from_utf8(
              journal.provider_source_digest + ".zip");
    } else if (active.package_materializer != nullptr) {
      auto materialized = active.package_materializer->materialize(active.package);
      if (!materialized)
        return facman::core::Result<Response>::failure(materialized.error());
      active.package = materialized.take_value();
    }
    auto checked = absolute_path(active.package, "setup payload");
    if (!checked)
      return facman::core::Result<Response>::failure(checked.error());
    active.package = checked.take_value();
    std::error_code package_status;
    if (!fs::is_regular_file(active.package, package_status) || package_status) {
      const auto missing = error(
          use_retained_source ? "self_setup_recovery_required"
                              : "self_setup_package_missing",
          use_retained_source
              ? "The retained setup payload required by the unfinished operation is absent"
              : "The setup payload is not a regular file",
          facman::platform::path_to_utf8(active.package));
      if (record_exists && use_retained_source) {
        journal.state = "recovery_required";
        journal.recovery_boundary = "retained_repair_source_missing";
        journal.last_error = missing.code;
        auto recorded = persist_journal(record_path, journal);
        if (!recorded)
          return facman::core::Result<Response>::failure(recorded.error());
      }
      return facman::core::Result<Response>::failure(missing);
    }
    auto digest = stable_file_digest(active.package);
    if (!digest)
      return facman::core::Result<Response>::failure(digest.error());
    if (record_exists && digest.value() != journal.provider_source_digest)
      return facman::core::Result<Response>::failure(error(
          "self_setup_recovery_required",
          "The setup payload does not match the unfinished operation",
          facman::platform::path_to_utf8(active.package)));
    source_digest = digest.take_value();
  }
  // A preview is admitted under the root lock.  If it discovers its own
  // incomplete provider transaction, return the exact provider inspection
  // result rather than presenting a normal-operation plan that could imply a
  // replay or implicit rollback.
  if (!active.apply) {
    if (record_exists)
      return facman::core::Result<Response>::failure(error(
          "self_setup_recovery_required", "review cannot mutate pending native integration", record_path.string()));
    return active.operation == Operation::uninstall
        ? uninstall(active, active.state_root, active.acceptance_root)
        : install_or_repair(active, active.package, active.install_root, active.state_root,
                            active.acceptance_root, nullptr, nullptr, &source_digest);
  }
  if (!record_exists) {
    journal = SetupJournal{};
    journal.operation_id = operation_id;
    journal.intent_digest = intent_digest;
    journal.operation = operation;
    journal.install_root = root_text;
    journal.install_root_identity = root_identity;
    journal.product_version = active.product_version;
    journal.mode = mode;
    journal.provider_revision = provider_revision();
    journal.provider_state_root = facman::platform::path_to_utf8(active.state_root);
    journal.provider_acceptance_root = facman::platform::path_to_utf8(active.acceptance_root);
    journal.provider_source_digest = source_digest;
    journal.installed_source_digest = active.operation == Operation::uninstall
        ? std::string() : source_digest;
    journal.provider_request_id = "request." + journal.operation_id;
    // USK install plans are explicitly identified by request_id. Repair and
    // uninstall own their plan_id field but retain the same durable identity.
    journal.provider_plan_id = active.operation == Operation::install
        ? journal.provider_request_id : "plan." + journal.operation_id;
    journal.provider_transaction_id = "tx." + journal.operation_id;
    journal.provider_created_at = timestamp();
    if (mode == "portable") {
      journal.repair_source = "not_applicable";
      journal.shortcut = "not_applicable";
      journal.registration = "not_applicable";
    } else if (active.operation == Operation::uninstall) {
      journal.repair_source = "not_applicable";
    }
    auto persisted = persist_journal(record_path, journal);
    if (!persisted)
      return facman::core::Result<Response>::failure(persisted.error());
  }

  fs::path repair_source;
  if (active.native_effects != nullptr &&
      !journal.installed_source_digest.empty()) {
    repair_source = active.state_root / "repair-sources" /
        facman::platform::path_from_utf8(
            journal.installed_source_digest + ".zip");
  }
  if (active.native_effects != nullptr &&
      active.operation != Operation::uninstall) {
    const NativeContext retention_context{
        active.operation, active.install_root, active.state_root,
        active.acceptance_root, repair_source, journal.product_version};
    if (journal.repair_source == "applied") {
      const auto retained = active.native_effects->validate_repair_source(
          retention_context, journal.installed_source_digest);
      if (!retained.ok || retained.path != repair_source) {
        journal.state = "recovery_required";
        journal.recovery_boundary = "repair_source_ownership_unproven";
        journal.last_error = retained.detail.empty()
            ? "repair source path differs from durable intent"
            : retained.detail;
        auto recorded = persist_journal(record_path, journal);
        if (!recorded)
          return facman::core::Result<Response>::failure(recorded.error());
        return facman::core::Result<Response>::failure(error(
            "self_setup_recovery_required",
            "The retained repair source for the unfinished operation is invalid",
            journal.last_error));
      }
      active.package = retained.path;
    } else {
      journal.repair_source = "applying";
      journal.state = journal.files == "applied" ? "native_applying" : "intent";
      journal.recovery_boundary = journal.files == "applied"
          ? "repair_source_pending" : "repair_source_pending_before_provider";
      auto pending = persist_journal(record_path, journal);
      if (!pending)
        return facman::core::Result<Response>::failure(pending.error());
      const auto retained = active.native_effects->retain_repair_source(
          retention_context, active.package, active.maintenance_launcher,
          journal.installed_source_digest);
      if (!retained.ok || retained.path != repair_source) {
        journal.last_error = retained.detail.empty()
            ? "repair source path differs from durable intent" : retained.detail;
        if (retained.recovery_required) {
          journal.state = "recovery_required";
          journal.recovery_boundary = "repair_source_ownership_unproven";
        } else {
          journal.repair_source = "pending";
          journal.state = journal.files == "applied" ? "files_applied" : "intent";
          journal.recovery_boundary = journal.files == "applied"
              ? "repair_source_pending" : "repair_source_pending_before_provider";
        }
        const auto retained_error = error(
            retained.recovery_required ? "self_setup_recovery_required"
                                       : "self_setup_windows_integration_failed",
            journal.files == "applied"
                ? "FacMan files changed, but the offline repair source was not retained"
                : "The offline repair source was not retained before provider mutation",
            journal.last_error);
        auto recorded = persist_journal(record_path, journal);
        if (!recorded)
          return facman::core::Result<Response>::failure(journal_write_failure(
              "offline repair source failure could not be recorded",
              retained_error, recorded.error()));
        return facman::core::Result<Response>::failure(retained_error);
      }
      journal.repair_source = "applied";
      journal.state = journal.files == "applied" ? "native_applying" : "intent";
      journal.recovery_boundary = journal.files == "applied"
          ? "repair_source_applied" : "repair_source_applied_before_provider";
      journal.last_error.clear();
      auto retained_record = persist_journal(record_path, journal);
      if (!retained_record)
        return facman::core::Result<Response>::failure(retained_record.error());
      active.package = retained.path;
    }
  }

  Response provider_response;
  if (journal.files != "applied") {
    if (journal.provider_phase == "apply_entered") {
      auto recovered = apply_reviewed_provider_rollback(
          journal, active.install_root, active.state_root,
          active.acceptance_root, active.clock);
      if (recovered) {
        journal.state = "rolled_back";
        journal.recovery_boundary = "provider_rollback_completed";
        journal.last_error = "provider_rolled_back_new_attempt_required";
        auto recorded = persist_journal(record_path, journal);
        if (!recorded)
          return facman::core::Result<Response>::failure(recorded.error());
        return facman::core::Result<Response>::failure(error(
            "self_setup_recovery_required",
            "provider rollback completed; submit a new setup operation instead of replaying its transaction",
            facman::platform::path_to_utf8(record_path)));
      }
      if (recovered.error().code == "self_setup_recovery_preview_required")
        return facman::core::Result<Response>::failure(recovered.error());
      journal.state = "recovery_required";
      journal.recovery_boundary = recovered.error().code == "self_setup_recovery_preview_required"
          ? "provider_recovery_review_required" : "provider_recovery_requires_operator";
      journal.last_error = recovered.error().code;
      auto recorded = persist_journal(record_path, journal);
      if (!recorded)
        return facman::core::Result<Response>::failure(recorded.error());
      return facman::core::Result<Response>::failure(recovered.error());
    }
    journal.state = "files_applying";
    journal.recovery_boundary = "file_effects_pending";
    auto persisted = persist_journal(record_path, journal);
    if (!persisted)
      return facman::core::Result<Response>::failure(persisted.error());
    ProviderProgress provider_progress = ProviderProgress::before_plan;
    auto applied = active.operation == Operation::uninstall
        ? uninstall(active, active.state_root, active.acceptance_root, &journal,
                    &record_path, &provider_progress)
        : install_or_repair(active, active.package, active.install_root, active.state_root,
                            active.acceptance_root, &journal, &record_path,
                            &source_digest, &provider_progress);
    if (!applied) {
      if (active.operation == Operation::uninstall &&
          definitive_pre_effect_uninstall_refusal(applied.error())) {
        // Pinned USK rejects this exact uninstall condition before reading a
        // transaction identity or entering apply_uninstall. It is therefore a
        // reviewed pre-effect refusal, unlike every generic provider error.
        journal.provider_plan_digest.clear();
        journal.provider_phase = "before_plan";
        journal.provider_receipt_identity.clear();
        journal.recovery_plan_id.clear();
        journal.recovery_plan_digest.clear();
        journal.recovery_plan_created_at.clear();
        journal.recovery_action.clear();
        journal.files = "pending";
        journal.state = "abandoned";
        journal.recovery_boundary = "abandoned_before_provider_apply";
        journal.last_error = "foreign_content_review_required";
        auto retired = persist_journal(record_path, journal);
        if (!retired) return facman::core::Result<Response>::failure(
            journal_write_failure(
                "uninstall refusal could not be durably retired",
                applied.error(), retired.error()));
        return facman::core::Result<Response>::failure(applied.error());
      }
      if (applied.error().code == "self_setup_interrupted" &&
          journal.provider_phase == "plan_reviewed") {
        journal.state = "files_applying";
        journal.recovery_boundary = "provider_plan_reviewed_before_apply";
        journal.last_error = applied.error().code;
        auto recorded = persist_journal(record_path, journal);
        if (!recorded)
          return facman::core::Result<Response>::failure(journal_write_failure(
              "provider plan-review interruption could not be recorded",
              applied.error(), recorded.error()));
        return facman::core::Result<Response>::failure(applied.error());
      }
      if (provider_progress != ProviderProgress::apply_entered) {
        journal.files = "pending";
        if (applied.error().code == "self_setup_recovery_required") {
          journal.state = "recovery_required";
          journal.recovery_boundary =
              provider_progress == ProviderProgress::plan_reviewed &&
                      active.operation == Operation::uninstall
                  ? "maintenance_launcher_ownership_unproven"
              : provider_progress == ProviderProgress::plan_reviewed
                  ? "provider_plan_identity_unproven"
                  : "pre_provider_identity_ownership_unproven";
        } else {
          journal.provider_plan_digest.clear();
          journal.provider_phase = "before_plan";
          journal.provider_receipt_identity.clear();
          journal.recovery_plan_id.clear();
          journal.recovery_plan_digest.clear();
          journal.recovery_plan_created_at.clear();
          journal.recovery_action.clear();
          journal.state = "abandoned";
          journal.recovery_boundary = "abandoned_before_provider_apply";
        }
      } else {
        journal.state = "files_applying";
        journal.recovery_boundary = "provider_receipt_unconfirmed";
      }
      journal.last_error = applied.error().code;
      auto recorded = persist_journal(record_path, journal);
      if (!recorded)
        return facman::core::Result<Response>::failure(journal_write_failure(
            "provider operation failed and its recovery boundary could not be recorded",
            applied.error(), recorded.error()));
      return facman::core::Result<Response>::failure(applied.error());
    }
    provider_response = applied.take_value();
    journal.provider_receipt_identity = digest_text(provider_response.provider_json);
    journal.files = "applied";
    journal.state = "files_applied";
    journal.recovery_boundary = "files_applied_before_native";
    journal.last_error.clear();
    auto persisted_after_files = persist_journal(record_path, journal);
    if (!persisted_after_files)
      return facman::core::Result<Response>::failure(persisted_after_files.error());
    if (active.durable_boundary_hook != nullptr &&
        !active.durable_boundary_hook->reached(DurableBoundary::files_applied))
      return facman::core::Result<Response>::failure(error(
          "self_setup_interrupted",
          "setup operation interrupted after its files-applied durable boundary",
          facman::platform::path_to_utf8(record_path)));
  }

  if (active.native_effects != nullptr && !journal.installed_source_digest.empty()) {
    repair_source = active.state_root / "repair-sources" /
        facman::platform::path_from_utf8(journal.installed_source_digest + ".zip");
  }
  const NativeContext native_context{active.operation, active.install_root,
      active.state_root, active.acceptance_root, repair_source,
      journal.product_version};

  if (active.native_effects != nullptr) {
    for (const NativeEffect effect : {NativeEffect::shortcut, NativeEffect::registration}) {
      std::string &effect_state = effect == NativeEffect::shortcut ? journal.shortcut : journal.registration;
      const NativeOwnership observed = active.native_effects->inspect(
          native_context, effect);
      const NativeOwnership desired = active.operation == Operation::uninstall
          ? NativeOwnership::absent : NativeOwnership::owned;
      if (effect_state == "applied") {
        if (observed == desired)
          continue;
        journal.state = "recovery_required";
        journal.recovery_boundary = "native_applied_effect_changed";
        journal.last_error = "native_applied_effect_changed";
        auto recorded = persist_journal(record_path, journal);
        if (!recorded)
          return facman::core::Result<Response>::failure(recorded.error());
        return facman::core::Result<Response>::failure(error(
            "self_setup_recovery_required",
            "a previously applied Windows integration effect no longer matches durable intent",
            facman::platform::path_to_utf8(record_path)));
      }
      if (observed == NativeOwnership::foreign || observed == NativeOwnership::unreadable) {
        journal.state = "recovery_required";
        journal.recovery_boundary = "native_ownership_unproven";
        journal.last_error = observed == NativeOwnership::foreign ? "foreign_native_effect" : "unreadable_native_effect";
        auto recorded = persist_journal(record_path, journal);
        if (!recorded)
          return facman::core::Result<Response>::failure(recorded.error());
        return facman::core::Result<Response>::failure(error(
            "self_setup_recovery_required", "Windows integration ownership could not be proven; existing object was preserved",
            facman::platform::path_to_utf8(record_path)));
      }
      // A lost receipt after an effect is reconciled by a fresh observation.
      if (effect_state == "applying" &&
          ((active.operation == Operation::uninstall && observed == NativeOwnership::absent) ||
           (active.operation != Operation::uninstall && observed == NativeOwnership::owned))) {
        effect_state = "applied";
      } else if ((active.operation == Operation::uninstall && observed == NativeOwnership::absent) ||
                 (active.operation != Operation::uninstall && observed == NativeOwnership::owned)) {
        // Existing owned integration is already the desired effect.  Do not
        // overwrite it after a separate observation, which would reopen a
        // shortcut/registry substitution race.
        effect_state = "applied";
      } else {
        effect_state = "applying";
        journal.state = "native_applying";
        journal.recovery_boundary = effect == NativeEffect::shortcut
            ? "shortcut_pending" : "registration_pending";
        auto persisted = persist_journal(record_path, journal);
        if (!persisted)
          return facman::core::Result<Response>::failure(persisted.error());
        const auto native = active.native_effects->apply(native_context, effect);
        if (!native.ok) {
          journal.last_error = native.detail;
          if (native.recovery_required) {
            journal.state = "recovery_required";
            journal.recovery_boundary = "native_mutation_edge_changed";
          }
          auto recorded = persist_journal(record_path, journal);
          if (!recorded)
            return facman::core::Result<Response>::failure(error(
                "self_setup_journal_write_failed",
                "native integration failed and its recovery boundary could not be recorded",
                native.detail + ": " + recorded.error().detail));
          return facman::core::Result<Response>::failure(error(
              native.recovery_required ? "self_setup_recovery_required" : "self_setup_windows_integration_failed",
              "FacMan files changed, but Windows integration did not complete", native.detail));
        }
        effect_state = "applied";
      }
      journal.state = "native_applying";
      journal.recovery_boundary = effect == NativeEffect::shortcut
          ? "shortcut_applied" : "registration_applied";
      journal.last_error.clear();
      auto persisted = persist_journal(record_path, journal);
      if (!persisted)
        return facman::core::Result<Response>::failure(persisted.error());
      if (effect == NativeEffect::shortcut &&
          active.durable_boundary_hook != nullptr &&
          !active.durable_boundary_hook->reached(DurableBoundary::shortcut_applied))
        return facman::core::Result<Response>::failure(error(
            "self_setup_interrupted",
            "setup operation interrupted after its shortcut-applied durable boundary",
            facman::platform::path_to_utf8(record_path)));
    }
  }
  journal.state = "completed";
  journal.recovery_boundary = "fully_committed";
  journal.last_error.clear();
  auto completed = persist_journal(record_path, journal);
  if (!completed)
    return facman::core::Result<Response>::failure(completed.error());
  if (provider_response.provider_json.empty())
    provider_response = {operation, "receipt", "", journal.operation_id};
  provider_response.setup_operation_id = journal.operation_id;
  return facman::core::Result<Response>::success(std::move(provider_response));
}

std::string provider_revision() { return FACMAN_SELF_SETUP_PROVIDER_REVISION; }

} // namespace facman::self_setup
