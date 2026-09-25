// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_self_setup.h"
#include "facman_self_maintenance.h"
#include "facman_self_maintenance_provider.h"

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
#include <set>
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
  // v1 journals predate install-scoped self setup. They remain readable as
  // the historical facman.self identity and retain their original digest.
  bool legacy_v1 = false;
  std::string operation_id;
  std::string intent_digest;
  std::string operation;
  std::string install_id = "facman.self";
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

std::string provider_transaction_identity(const std::string &operation_id,
                                          const std::string &install_id) {
  const std::string direct = "tx." + operation_id;
  // Universal Setup derives `ownership.<install-id>.<transaction-id>` and
  // admits identifiers only through 128 bytes. Generation install IDs already
  // carry their full content identity, so compact only the transaction suffix
  // when that derived identifier would exceed the provider contract.
  if (("ownership." + install_id + "." + direct).size() <= 128U)
    return direct;
  return "tx." + digest_text(
      "facman.setup.provider-transaction.v1\n" + operation_id + "\n" +
      install_id + "\n").substr(0, 24);
}

bool classic_generation_install_identity(const std::string &install_id) {
  static const std::string prefix = "facman.self.generation.";
  return install_id.size() == prefix.size() + 64U &&
      install_id.compare(0, prefix.size(), prefix) == 0 &&
      digest_or_empty(install_id.substr(prefix.size()));
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
                      const std::string &intent_digest, bool legacy_v1 = false) {
  return state_root / "setup-operations" /
      ("facman." + operation + "." + root_identity.substr(0, 32) +
       "." + intent_digest.substr(0, 32) +
       ".setup-operation.v" + (legacy_v1 ? "1" : "2") + ".json");
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
  // Start Menu and HKCU registration are per-user product objects. Every
  // FacMan root therefore shares one coordinator lock: allowing the caller's
  // selected root to choose the lock would let two individually valid roots
  // race those singleton effects during an update or rollback.
  (void)root_identity;
  const fs::path path = directory / "facman.self.lock";
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
  document.add_string("schema", journal.legacy_v1
      ? "facman.setup_operation_journal.v1"
      : "facman.setup_operation_journal.v2");
  document.add_string("operation_id", journal.operation_id);
  document.add_string("intent_digest", journal.intent_digest);
  document.add_string("operation", journal.operation);
  if (!journal.legacy_v1)
    document.add_string("install_id", journal.install_id);
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
  if (journal.legacy_v1)
    return digest_text(journal.operation + "\n" + journal.install_root_identity + "\n" +
        journal.product_version + "\n" + journal.mode + "\n" +
        journal.provider_source_digest + "\n" + journal.provider_state_root + "\n" +
        journal.provider_acceptance_root);
  return digest_text("facman.setup.intent.v2\n" + journal.install_id + "\n" +
      journal.operation + "\n" + journal.install_root_identity + "\n" +
      journal.product_version + "\n" + journal.mode + "\n" +
      journal.provider_source_digest + "\n" + journal.provider_state_root + "\n" +
      journal.provider_acceptance_root);
}

facman::core::Result<SetupJournal> load_journal(const fs::path &path);

std::string history_filename(const SetupJournal &journal) {
  const std::string identity = "facman.setup.history.v1\n" + journal.operation_id + "\n" +
      journal.intent_digest + "\n" + journal.install_root_identity + "\n" + journal.operation;
  return "facman." + digest_text(identity) + ".setup-history.v" +
      (journal.legacy_v1 ? "1" : "2") + ".json";
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
  const bool v1 = document && document.value().is_object() &&
      string_field(document.value(), "schema") == "facman.setup_operation_journal.v1";
  const bool v2 = document && document.value().is_object() &&
      string_field(document.value(), "schema") == "facman.setup_operation_journal.v2";
  if (!document ||
      !(v1
            ? exact_keys(document.value(),
                {"schema", "operation_id", "intent_digest", "operation",
                 "install_root", "install_root_identity", "product",
                 "product_version", "mode", "provider", "recovery", "effects", "state",
                 "recovery_boundary", "last_error"})
            : v2 && exact_keys(document.value(),
                {"schema", "operation_id", "intent_digest", "operation", "install_id",
                 "install_root", "install_root_identity", "product",
                 "product_version", "mode", "provider", "recovery", "effects", "state",
                 "recovery_boundary", "last_error"})) ||
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
  journal.legacy_v1 = v1;
  journal.operation_id = string_field(document.value(), "operation_id");
  journal.intent_digest = string_field(document.value(), "intent_digest");
  journal.operation = string_field(document.value(), "operation");
  journal.install_id = v1 ? "facman.self" : string_field(document.value(), "install_id");
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
  if (!bounded_identifier(journal.operation_id) || !bounded_identifier(journal.install_id) ||
      !digest_or_empty(journal.intent_digest) ||
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
  const std::string expected_transaction = provider_transaction_identity(
      journal.operation_id, journal.install_id);
  const std::string legacy_direct_transaction = "tx." + journal.operation_id;
  // Pre-compaction builds already emitted generation-specific uninstall
  // journals. Preserve their recorded transaction through restart recovery;
  // substituting the compact identity would describe a different provider
  // transaction. New journals always use the bounded identity above.
  const bool legacy_generation_uninstall_transaction =
      !journal.legacy_v1 && journal.operation == "uninstall" &&
      classic_generation_install_identity(journal.install_id) &&
      expected_transaction != legacy_direct_transaction &&
      journal.provider_transaction_id == legacy_direct_transaction;
  if (journal.provider_request_id != "request." + journal.operation_id ||
      (journal.provider_transaction_id != expected_transaction &&
       !legacy_generation_uninstall_transaction) ||
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
    const bool v1_name = name.size() >= std::string(".setup-operation.v1.json").size() &&
        name.compare(name.size() - std::string(".setup-operation.v1.json").size(),
                     std::string(".setup-operation.v1.json").size(),
                     ".setup-operation.v1.json") == 0;
    const bool v2_name = name.size() >= std::string(".setup-operation.v2.json").size() &&
        name.compare(name.size() - std::string(".setup-operation.v2.json").size(),
                     std::string(".setup-operation.v2.json").size(),
                     ".setup-operation.v2.json") == 0;
    if (name.find("facman.") != 0 || name.find(marker) == std::string::npos ||
        (!v1_name && !v2_name))
      continue;
    if (++entries > maximum_entries)
      return facman::core::Result<std::optional<DiscoveredJournal>>::failure(error(
          "self_setup_recovery_required", "setup coordinator active journal set exceeds its entry limit"));
    auto journal = load_journal(candidate);
    if (!journal) return facman::core::Result<std::optional<DiscoveredJournal>>::failure(journal.error());
    if (journal.value().install_root_identity != root_identity)
      continue;
    const fs::path expected = journal_path(coordinator_root, journal.value().operation,
                                           root_identity, journal.value().intent_digest,
                                           journal.value().legacy_v1);
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


facman::core::Result<std::string> command_with(
    ProviderEffects *provider, const std::string &name,
    const std::string &payload, const fs::path &state_root,
    const fs::path &acceptance_root, bool dry_run) {
  if (provider != nullptr)
    return provider->command(name, payload, state_root, acceptance_root,
                             dry_run);
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

facman::core::Result<std::string> command(const std::string &name,
                                          const std::string &payload,
                                          const fs::path &state_root,
                                          const fs::path &acceptance_root,
                                          bool dry_run) {
  return command_with(injected_provider, name, payload, state_root,
                      acceptance_root, dry_run);
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

facman::core::Result<ProviderPlanIdentity> plan_identity(
    const std::string &response, const std::string *expected_install_id = nullptr) {
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
  bool install_identity_matches = expected_install_id == nullptr;
  if (expected_install_id != nullptr && payload != nullptr && payload->is_object()) {
    if (string_field(*payload, "schema") == "usk.install_plan.v1") {
      const json::Value *source = payload->find("source");
      install_identity_matches = source != nullptr && source->is_object() &&
          string_field(*source, "source_id") == "source." + *expected_install_id;
    } else {
      install_identity_matches =
          string_field(*payload, "install_id") == *expected_install_id;
    }
  }
  if (digest.size() != 64 || !digest_or_empty(digest) || !bounded_identifier(plan_id) ||
      !install_identity_matches) {
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
  plan.add_string("install_id", request.install_id);
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
    plan.add_string("install_id", request.install_id);
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
  auto reviewed = plan_identity(planned.value(), &request.install_id);
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

facman::core::Result<Response> verify(const Request &request,
                                      const fs::path &state_root,
                                      const fs::path &acceptance_root) {
  json::ObjectBuilder payload;
  payload.add_string("schema", "usk.installed_verify_request.v1");
  payload.add_string("request_id", identifier("request.facman.verify"));
  payload.add_string("install_id", request.install_id);
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
  inspection.add_string("install_id", request.install_id);
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
      string_field(*payload, "install_id") != request.install_id ||
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
  plan.add_string("install_id", request.install_id);
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
  auto reviewed = plan_identity(planned.value(), &request.install_id);
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
        string_field(*payload, "install_id") != request.install_id ||
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
  inspection.add_string("install_id", journal.install_id);
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
  inspection.add_string("install_id", journal.install_id);
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
  if (!bounded_identifier(request.install_id))
    return facman::core::Result<Response>::failure(error(
        "self_setup_install_id_invalid", "The setup install identity is invalid"));
  if (request.operation == Operation::verify) {
    auto state = absolute_path(request.state_root, "state root");
    auto acceptance = absolute_path(request.acceptance_root, "acceptance root");
    if (!state || !acceptance)
      return facman::core::Result<Response>::failure(!state ? state.error() : acceptance.error());
    return verify(request, state.value(), acceptance.value());
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
  std::optional<ScopedSetupLock> held_lock;
  if (request.coordinator_lock != nullptr &&
      request.coordinator_lock->operation_id().empty())
    return facman::core::Result<Response>::failure(error(
        "self_setup_lock_unsafe", "retirement coordinator lock proof is invalid"));
  const bool coordinator_lock_already_held =
      request.coordinator_lock != nullptr &&
      request.coordinator_lock->coordinator_root().lexically_normal() ==
          coordinator.value().lexically_normal();
  if (!coordinator_lock_already_held) {
    auto acquired = acquire_setup_lock(coordinator.value(), root_identity,
                                       provisional_operation_id);
    if (!acquired)
      return facman::core::Result<Response>::failure(acquired.error());
    held_lock.emplace(acquired.take_value());
  }

  if (request.apply && !request.reserved_successor_epoch_id.empty()) {
    if (request.operation != Operation::install ||
        request.reserved_successor_epoch_id.size() != 64U ||
        !digest_or_empty(request.reserved_successor_epoch_id))
      return facman::core::Result<Response>::failure(error(
          "self_maintenance_epoch_recovery_required",
          "setup successor reservation identity is invalid"));
    // Public Setup keeps lifecycle history beside the selected provider state
    // root. The user-wide Setup lock above serializes the singleton effects;
    // the reservation itself must be checked against that exact history.
    const fs::path lifecycle_coordinator =
        (state.value().parent_path() / "setup-coordinator.v1")
            .lexically_normal();
    auto epochs = self_maintenance::discover_lifecycle_epoch_chain(
        lifecycle_coordinator);
    if (!epochs || epochs.value().epochs.size() < 2U ||
        epochs.value().epochs.back().compatibility_epoch ||
        epochs.value().epochs.back().epoch_id !=
            request.reserved_successor_epoch_id ||
        !epochs.value().epochs.back().retirement_sha256.empty() ||
        epochs.value().epochs[epochs.value().epochs.size() - 2U]
            .retirement_sha256.empty())
      return facman::core::Result<Response>::failure(!epochs
          ? epochs.error()
          : error("self_maintenance_epoch_recovery_required",
              "the reserved successor no longer follows a retired epoch"));
  }

  // A direct compatibility install must observe epoch ownership while the
  // shared setup lock is held. The public Setup preflight alone cannot close
  // a race with bootstrap or a real epoch created by another process.
  if (request.operation == Operation::install &&
      request.install_id == "facman.self") {
    facman::platform::StableDirectoryObject coordinator_directory;
    if (!coordinator_directory.open_no_follow(coordinator.value()).ok())
      return facman::core::Result<Response>::failure(error(
          "self_maintenance_epoch_recovery_required",
          "setup coordinator cannot be safely inspected before install"));
    for (const char *name : {"epochs", "authority-bootstrap.v1",
                             "authority-handoff.v1.json"}) {
      const fs::path path = coordinator.value() / name;
      facman::platform::PathIdentity identity;
      if (!coordinator_directory.validate_descendant(path, true).ok() ||
          !facman::platform::inspect_path_no_follow(path, identity).ok() ||
          identity.exists)
        return facman::core::Result<Response>::failure(error(
            "self_maintenance_epoch_recovery_required",
            "lifecycle epoch authority blocks direct compatibility install",
            name));
    }
    if (!coordinator_directory.revalidate().ok())
      return facman::core::Result<Response>::failure(error(
          "self_maintenance_epoch_recovery_required",
          "setup coordinator changed during epoch exclusion"));
  }

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
    active.install_id = journal.install_id;
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
    intended.operation = operation; intended.install_id = active.install_id;
    intended.install_root_identity = root_identity;
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
    journal.install_id = active.install_id;
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
    journal.provider_transaction_id = provider_transaction_identity(
        journal.operation_id, journal.install_id);
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

facman::core::Result<bool> has_pending_operation(
    const fs::path &install_root, const fs::path &coordinator_root) {
  auto install = canonical_install_root(install_root);
  auto coordinator = absolute_path(coordinator_root, "setup coordinator root");
  if (!install || !coordinator)
    return facman::core::Result<bool>::failure(
        !install ? install.error() : coordinator.error());
  const std::string root_identity = digest_text(
      "facman.setup.root.v1\n" + install.value());
  auto discovered = discover_root_journal(coordinator.value(), root_identity);
  if (!discovered)
    return facman::core::Result<bool>::failure(discovered.error());
  return facman::core::Result<bool>::success(discovered.value().has_value());
}

std::string provider_revision() { return FACMAN_SELF_SETUP_PROVIDER_REVISION; }

} // namespace facman::self_setup

namespace facman::self_maintenance {
namespace {

std::string provider_hash(const std::string &value) {
  return facman::base::sha256_hex_bytes(
      reinterpret_cast<const unsigned char *>(value.data()), value.size());
}

std::string provider_string(const json::Value &value, const char *key) {
  const json::Value *field = value.find(key);
  return field != nullptr && field->string_value()
      ? field->string_value().value() : std::string();
}

bool provider_exact_keys(const json::Value &value,
                         std::initializer_list<const char *> keys) {
  if (!value.is_object() || value.size() != keys.size()) return false;
  return std::all_of(keys.begin(), keys.end(),
      [&](const char *key) { return value.find(key) != nullptr; });
}

bool provider_digest(const std::string &value) {
  return value.size() == 64U &&
      std::all_of(value.begin(), value.end(), [](unsigned char character) {
        return (character >= '0' && character <= '9') ||
            (character >= 'a' && character <= 'f');
      });
}

bool provider_same_path(const fs::path &left, const fs::path &right) {
#ifdef _WIN32
  return _wcsicmp(left.lexically_normal().native().c_str(),
                  right.lexically_normal().native().c_str()) == 0;
#else
  return left.lexically_normal() == right.lexically_normal();
#endif
}

bool provider_bool(const json::Value &object, const char *key, bool expected) {
  const json::Value *field = object.find(key);
  if (field == nullptr) return false;
  auto value = field->bool_value();
  return value && value.value() == expected;
}

bool provider_uint(const json::Value &object, const char *key,
                   std::uint64_t *output = nullptr) {
  const json::Value *field = object.find(key);
  if (field == nullptr) return false;
  auto value = field->unsigned_integer_value();
  if (!value) return false;
  if (output != nullptr) *output = value.value();
  return true;
}

bool provider_exact_string_array(const json::Value &value,
                                 std::initializer_list<const char *> expected) {
  if (!value.is_array() || value.size() != expected.size()) return false;
  std::size_t index = 0;
  for (const char *item : expected) {
    const json::Value *entry = value.at(index++);
    if (entry == nullptr || !entry->string_value() ||
        entry->string_value().value() != item) return false;
  }
  return true;
}

bool provider_safe_relative(const std::string &value) {
  if (value.empty() || value.size() > 4096U) return false;
  const fs::path path = facman::platform::path_from_utf8(value);
  if (path.is_absolute()) return false;
  for (const auto &component : path)
    if (component == "." || component == "..") return false;
  return true;
}

facman::core::Error provider_error(std::string code, std::string message,
                                   std::string detail = {}) {
  facman::core::Error result{std::move(code), std::move(message), ""};
  result.detail = std::move(detail);
  return result;
}

std::string provider_installed_state_digest(const json::Value &payload) {
  json::ObjectBuilder projection;
  for (const char *key : {
           "audit_chain_id", "component_selection", "created_at",
           "entrypoints", "install_id", "lifecycle_status",
           "ownership_manifest_digest", "ownership_manifest_ref",
           "product_id", "product_version", "recipe_digest", "setup_abi",
           "source_archive_digest", "target_root", "target_scope",
           "transaction_id"}) {
    const json::Value *field = payload.find(key);
    if (field == nullptr || !projection.add_value(key, *field)) return {};
  }
  auto parsed = json::parse(projection.serialize());
  auto canonical = parsed
      ? json::canonical_integer_json(parsed.value())
      : facman::core::Result<std::string>::failure(provider_error(
            "self_maintenance_provider_response_invalid",
            "installed-state digest projection could not be parsed"));
  return canonical ? provider_hash(canonical.value()) : std::string();
}

facman::core::Result<InstalledIdentity> decode_installed_identity(
    const std::string &response) {
  auto envelope = json::parse(response);
  const json::Value *response_error = envelope && envelope.value().is_object()
      ? envelope.value().find("error") : nullptr;
  const json::Value *payload = envelope && envelope.value().is_object()
      ? envelope.value().find("payload") : nullptr;
  const json::Value *setup_abi = payload != nullptr && payload->is_object()
      ? payload->find("setup_abi") : nullptr;
  const json::Value *entrypoints = payload != nullptr && payload->is_object()
      ? payload->find("entrypoints") : nullptr;
  const json::Value *components = payload != nullptr && payload->is_object()
      ? payload->find("component_selection") : nullptr;
  const json::Value *last_verification = payload != nullptr && payload->is_object()
      ? payload->find("last_verification") : nullptr;
  if (!envelope ||
      !provider_exact_keys(envelope.value(),
          {"error", "payload", "schema", "status"}) ||
      provider_string(envelope.value(), "schema") !=
          "usk.command_response.v1" ||
      provider_string(envelope.value(), "status") != "ok" ||
      response_error == nullptr || !response_error->is_null() ||
      payload == nullptr || !payload->is_object() ||
      !provider_exact_keys(*payload,
          {"audit_chain_id", "component_selection", "created_at",
           "entrypoints", "install_id", "last_verification",
           "lifecycle_status", "ownership_manifest_digest",
           "ownership_manifest_ref", "product_id", "product_version",
           "recipe_digest", "schema", "setup_abi",
           "source_archive_digest", "target_root", "target_scope",
           "transaction_id"}) ||
      setup_abi == nullptr ||
      !provider_exact_keys(*setup_abi,
          {"major", "minor", "provider_revision"}) ||
      !provider_uint(*setup_abi, "major") ||
      !provider_uint(*setup_abi, "minor") ||
      components == nullptr ||
      !provider_exact_string_array(*components,
          {"facman.product", "facman.maintenance"}) ||
      entrypoints == nullptr || !entrypoints->is_array() ||
      entrypoints->size() != 3U ||
      last_verification == nullptr ||
      !provider_exact_keys(*last_verification,
          {"report_digest", "report_id", "status", "verified_at"}) ||
      !provider_digest(provider_string(*last_verification, "report_digest")) ||
      provider_string(*last_verification, "report_id").empty() ||
      (provider_string(*last_verification, "status") != "pass" &&
       provider_string(*last_verification, "status") != "warn" &&
       provider_string(*last_verification, "status") != "fail") ||
      !self_setup::valid_timestamp(
          provider_string(*last_verification, "verified_at")) ||
      provider_string(*payload, "schema") != "usk.installed_state.v1" ||
      provider_string(*payload, "product_id") != "facman" ||
      provider_string(*payload, "target_scope") != "portable" ||
      (provider_string(*payload, "lifecycle_status") != "installed" &&
       provider_string(*payload, "lifecycle_status") != "verified") ||
      !provider_digest(provider_string(*payload, "recipe_digest")) ||
      !provider_digest(provider_string(*payload, "source_archive_digest")) ||
      !provider_digest(provider_string(*payload,
                                       "ownership_manifest_digest")) ||
      provider_string(*payload, "ownership_manifest_ref").empty() ||
      provider_string(*payload, "audit_chain_id").empty() ||
      provider_string(*payload, "transaction_id").empty() ||
      !self_setup::valid_timestamp(provider_string(*payload, "created_at")) ||
      provider_string(*setup_abi, "provider_revision") !=
          self_setup::provider_revision())
    return facman::core::Result<InstalledIdentity>::failure(provider_error(
        "self_maintenance_provider_response_invalid",
        "Universal Setup installed-state response is incompatible",
        response));
  InstalledIdentity result;
  result.install_id = provider_string(*payload, "install_id");
  result.product_version = provider_string(*payload, "product_version");
  result.source_archive_sha256 =
      provider_string(*payload, "source_archive_digest");
  result.recipe_digest = provider_string(*payload, "recipe_digest");
  result.provider_revision = provider_string(*setup_abi, "provider_revision");
  result.transaction_id = provider_string(*payload, "transaction_id");
  result.ownership_manifest_digest =
      provider_string(*payload, "ownership_manifest_digest");
  result.installed_state_digest = provider_installed_state_digest(*payload);
  result.last_verification_report_digest = provider_string(*last_verification, "report_digest");
  result.last_verification_status = provider_string(*last_verification, "status");
  if (!provider_digest(result.installed_state_digest))
    return facman::core::Result<InstalledIdentity>::failure(provider_error(
        "self_maintenance_provider_response_invalid",
        "Universal Setup installed-state digest projection is incompatible"));
  result.install_root = facman::platform::path_from_utf8(
      provider_string(*payload, "target_root"));
  for (std::size_t index = 0; index < entrypoints->size(); ++index) {
    const json::Value *entrypoint = entrypoints->at(index);
    if (entrypoint == nullptr ||
        !provider_exact_keys(*entrypoint,
            {"entrypoint_id", "kind", "relative_path"}))
      return facman::core::Result<InstalledIdentity>::failure(provider_error(
          "self_maintenance_provider_response_invalid",
          "Universal Setup installed entrypoints are incompatible", response));
    const std::string id = provider_string(*entrypoint, "entrypoint_id");
    const std::string kind = provider_string(*entrypoint, "kind");
    const std::string path = provider_string(*entrypoint, "relative_path");
    if (id == "facman.gui" && kind == "application" &&
        result.gui_relative_path.empty())
      result.gui_relative_path = path;
    else if (id == "facman.cli" && kind == "tool" &&
             result.cli_relative_path.empty())
      result.cli_relative_path = path;
    else if (id == "facman.setup" && kind == "tool" &&
             result.maintenance_relative_path.empty())
      result.maintenance_relative_path = path;
    else
      return facman::core::Result<InstalledIdentity>::failure(provider_error(
          "self_maintenance_provider_response_invalid",
          "Universal Setup installed entrypoints are duplicated or unknown",
          response));
  }
  const std::string generation =
      "generations/" + result.product_version + "/";
  if (result.install_id.empty() || result.product_version.empty() ||
      !result.install_root.is_absolute() ||
      result.gui_relative_path != generation + "FacMan.exe" ||
      result.cli_relative_path != generation + "bin/facman.exe" ||
      result.maintenance_relative_path != "maintenance/FacManSetup.exe")
    return facman::core::Result<InstalledIdentity>::failure(provider_error(
        "self_maintenance_provider_response_invalid",
        "Universal Setup installed-state identity is incomplete", response));
  return facman::core::Result<InstalledIdentity>::success(std::move(result));
}

std::string bridge_key(const Plan &plan) {
  return provider_hash(plan.operation + "\n" + plan.operation_id + "\n" +
      generation_record_bytes(plan.target) + plan.package_sha256 + "\n" +
      facman::platform::path_to_utf8(plan.package.lexically_normal()) + "\n");
}

std::string maintenance_recipe_digest(const Plan &transition) {
  json::ObjectBuilder recipe_identity;
  recipe_identity.add_string("schema", "facman.self_setup_recipe.v1");
  recipe_identity.add_string("product_id", "facman");
  recipe_identity.add_string("product_version",
                             transition.target.product_version);
  recipe_identity.add_string("provider_revision",
                             self_setup::provider_revision());
  recipe_identity.add_string("source_sha256", transition.target.package_sha256);
  recipe_identity.add_string("target_layout",
                             "versioned_generation_with_maintenance_v1");
  return provider_hash(recipe_identity.serialize());
}

std::string maintenance_review_receipt(const Plan &transition,
                                       const std::string &semantic_digest) {
  return provider_hash("facman.self_maintenance.provider_review.v1\n" +
      bridge_key(transition) + "\n" + maintenance_recipe_digest(transition) +
      "\n" + self_setup::provider_revision() + "\n" + semantic_digest + "\n");
}

json::ObjectBuilder maintenance_install_plan(
    const Plan &transition, const std::string &created_at,
    const std::string &request_id) {
  json::ArrayBuilder components;
  components.add_string("facman.product");
  components.add_string("facman.maintenance");
  const std::string generation =
      "generations/" + transition.target.product_version + "/";
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
  recipe.add_string("product_version", transition.target.product_version);
  recipe.add_string("recipe_digest", maintenance_recipe_digest(transition));
  recipe.add_string("provider_revision", self_setup::provider_revision());
  recipe.add_array("components", components);
  recipe.add_array("entrypoints", entrypoints);
  json::ObjectBuilder target;
  target.add_string("root",
      facman::platform::path_to_utf8(transition.target.install_root));
  target.add_string("class", "operator_acceptance");
  json::ObjectBuilder plan;
  plan.add_string("schema", "usk.install_local_plan_request.v1");
  plan.add_string("request_id", request_id);
  plan.add_string("created_at", created_at);
  plan.add_string("install_id", transition.target.install_id);
  plan.add_object("archive", self_setup::archive(
      transition.package, transition.package_sha256, true));
  plan.add_object("target", target);
  plan.add_object("recipe", recipe);
  return plan;
}

struct MaintenancePlanReview {
  std::string plan_id;
  std::string digest;
  std::string semantic_digest;
};

facman::core::Result<std::string> maintenance_plan_semantic_digest(
    const json::Value &payload, bool authority) {
  // plan_digest is deliberately excluded: providers commonly derive it from
  // the complete response, including created_at and plan_id.  The projection
  // below binds every independently validated, apply-relevant plan field while
  // allowing a fresh bridge to retry the same plan with new request metadata.
  json::ObjectBuilder projection;
  for (const char *key : {"schema", "status", "operation",
                          "component_selection", "effects", "input_identity",
                          "planned_entries", "refusal_policy", "revalidation",
                          "source", "target", "totals"}) {
    const json::Value *field = payload.find(key);
    if (field == nullptr || !projection.add_value(key, *field))
      return facman::core::Result<std::string>::failure(provider_error(
          "self_maintenance_provider_response_invalid",
          "Universal Setup plan semantic projection is incomplete"));
  }
  if (authority) {
    for (const char *key : {"required_commit_authority",
                            "commit_authority_available"}) {
      const json::Value *field = payload.find(key);
      if (field == nullptr || !projection.add_value(key, *field))
        return facman::core::Result<std::string>::failure(provider_error(
            "self_maintenance_provider_response_invalid",
            "Universal Setup plan authority projection is incomplete"));
    }
  }
  auto parsed = json::parse(projection.serialize());
  auto canonical = parsed
      ? json::canonical_integer_json(parsed.value())
      : facman::core::Result<std::string>::failure(provider_error(
            "self_maintenance_provider_response_invalid",
            "Universal Setup plan semantic projection could not be parsed"));
  if (!canonical)
    return facman::core::Result<std::string>::failure(provider_error(
        "self_maintenance_provider_response_invalid",
        "Universal Setup plan semantic projection could not be canonicalized"));
  return facman::core::Result<std::string>::success(provider_hash(canonical.value()));
}

facman::core::Result<MaintenancePlanReview> decode_maintenance_plan(
    const std::string &response, const Plan &transition,
    const std::string &created_at, const std::string &request_id,
    const std::string &recipe_digest) {
  auto envelope = json::parse(response);
  const json::Value *error_value = envelope && envelope.value().is_object()
      ? envelope.value().find("error") : nullptr;
  const json::Value *payload = envelope && envelope.value().is_object()
      ? envelope.value().find("payload") : nullptr;
  if (!envelope ||
      !provider_exact_keys(envelope.value(),
          {"error", "payload", "schema", "status"}) ||
      provider_string(envelope.value(), "schema") !=
          "usk.command_response.v1" ||
      provider_string(envelope.value(), "status") != "ok" ||
      error_value == nullptr || !error_value->is_null() ||
      payload == nullptr || !payload->is_object())
    return facman::core::Result<MaintenancePlanReview>::failure(provider_error(
        "self_maintenance_provider_response_invalid",
        "Universal Setup plan response envelope is incompatible"));
  const bool authority = payload->find("required_commit_authority") != nullptr ||
      payload->find("commit_authority_available") != nullptr;
  const bool exact = authority
      ? provider_exact_keys(*payload,
          {"commit_authority_available", "component_selection", "created_at",
           "effects", "input_identity", "operation", "plan_digest",
           "plan_id", "planned_entries", "refusal_policy",
           "required_commit_authority", "revalidation", "schema", "source",
           "status", "target", "totals"})
      : provider_exact_keys(*payload,
          {"component_selection", "created_at", "effects", "input_identity",
           "operation", "plan_digest", "plan_id", "planned_entries",
           "refusal_policy", "revalidation", "schema", "source", "status",
           "target", "totals"});
  const json::Value *input = payload->find("input_identity");
  const json::Value *source = payload->find("source");
  const json::Value *target = payload->find("target");
  const json::Value *filesystem = target != nullptr ? target->find("filesystem") : nullptr;
  const json::Value *capabilities = filesystem != nullptr
      ? filesystem->find("capabilities") : nullptr;
  const json::Value *components = payload->find("component_selection");
  const json::Value *entries = payload->find("planned_entries");
  const json::Value *effects = payload->find("effects");
  const json::Value *totals = payload->find("totals");
  const json::Value *revalidation = payload->find("revalidation");
  const json::Value *invalidations = revalidation != nullptr
      ? revalidation->find("invalidate_on") : nullptr;
  const json::Value *refusal = payload->find("refusal_policy");
  if (!exact || provider_string(*payload, "schema") != "usk.install_plan.v1" ||
      provider_string(*payload, "plan_id") != request_id ||
      !provider_digest(provider_string(*payload, "plan_digest")) ||
      provider_string(*payload, "operation") != "install_local" ||
      provider_string(*payload, "status") != "planned" ||
      provider_string(*payload, "created_at") != created_at ||
      (authority &&
       (provider_string(*payload, "required_commit_authority") !=
            "staged_child_bound_v1" ||
        !provider_bool(*payload, "commit_authority_available", false))) ||
      input == nullptr || !provider_exact_keys(*input,
          {"policy_digest", "provider_revision", "recipe_digest",
           "source_digest"}) ||
      !provider_digest(provider_string(*input, "policy_digest")) ||
      provider_string(*input, "provider_revision") !=
          self_setup::provider_revision() ||
      provider_string(*input, "recipe_digest") != recipe_digest ||
      provider_string(*input, "source_digest") != transition.package_sha256 ||
      source == nullptr || !provider_exact_keys(*source,
          {"filesystem_identity_digest", "path", "path_identity_digest",
           "sha256", "size_bytes", "source_id"}) ||
      provider_string(*source, "source_id") !=
          "source." + transition.target.install_id ||
      !provider_same_path(facman::platform::path_from_utf8(
                              provider_string(*source, "path")),
                          transition.package) ||
      provider_string(*source, "sha256") != transition.package_sha256 ||
      !provider_uint(*source, "size_bytes") ||
      !provider_digest(provider_string(*source, "filesystem_identity_digest")) ||
      !provider_digest(provider_string(*source, "path_identity_digest")) ||
      target == nullptr || !provider_exact_keys(*target,
          {"classification", "filesystem", "identity_digest",
           "must_not_exist", "path_identity_digest", "pre_snapshot_digest",
           "root", "scope", "volume_id"}) ||
      !provider_same_path(facman::platform::path_from_utf8(
                              provider_string(*target, "root")),
                          transition.target.install_root) ||
      provider_string(*target, "scope") != "portable" ||
      provider_string(*target, "classification") !=
          "operator_selected_owned_target" ||
      !provider_bool(*target, "must_not_exist", true) ||
      provider_string(*target, "volume_id").empty() ||
      !provider_digest(provider_string(*target, "identity_digest")) ||
      !provider_digest(provider_string(*target, "path_identity_digest")) ||
      !provider_digest(provider_string(*target, "pre_snapshot_digest")) ||
      filesystem == nullptr || !provider_exact_keys(*filesystem,
          {"capabilities", "identity_digest", "kind"}) ||
      !provider_digest(provider_string(*filesystem, "identity_digest")) ||
      provider_string(*filesystem, "kind").empty() ||
      capabilities == nullptr || !provider_exact_keys(*capabilities,
          {"local", "no_mount_redirection", "no_replace_commit",
           "stable_ancestors"}) ||
      !provider_bool(*capabilities, "local", true) ||
      !provider_bool(*capabilities, "no_mount_redirection", true) ||
      !provider_bool(*capabilities, "no_replace_commit", true) ||
      !provider_bool(*capabilities, "stable_ancestors", true) ||
      components == nullptr || !provider_exact_string_array(*components,
          {"facman.product", "facman.maintenance"}) ||
      entries == nullptr || !entries->is_array() ||
      effects == nullptr || !effects->is_array() || effects->size() == 0U ||
      totals == nullptr || !provider_exact_keys(*totals,
          {"directory_count", "file_count", "uncompressed_bytes"}) ||
      !provider_uint(*totals, "directory_count") ||
      !provider_uint(*totals, "file_count") ||
      !provider_uint(*totals, "uncompressed_bytes") ||
      revalidation == nullptr || !provider_exact_keys(*revalidation,
          {"immediately_before_apply", "invalidate_on"}) ||
      !provider_bool(*revalidation, "immediately_before_apply", true) ||
      invalidations == nullptr || !provider_exact_string_array(*invalidations,
          {"source", "recipe", "target", "policy", "provider_revision"}) ||
      refusal == nullptr || !provider_exact_keys(*refusal,
          {"refuse_elevation", "refuse_existing_target",
           "refuse_installer_execution", "refuse_network",
           "refuse_package_manager", "refuse_registry"}) ||
      !provider_bool(*refusal, "refuse_elevation", true) ||
      !provider_bool(*refusal, "refuse_existing_target", true) ||
      !provider_bool(*refusal, "refuse_installer_execution", true) ||
      !provider_bool(*refusal, "refuse_network", true) ||
      !provider_bool(*refusal, "refuse_package_manager", true) ||
      !provider_bool(*refusal, "refuse_registry", true))
    return facman::core::Result<MaintenancePlanReview>::failure(provider_error(
        "self_maintenance_provider_response_invalid",
        "Universal Setup plan response does not bind the reviewed input"));
  std::uint64_t observed_files = 0;
  std::uint64_t observed_directories = 0;
  for (std::size_t index = 0; index < entries->size(); ++index) {
    const json::Value *entry = entries->at(index);
    const std::string type = entry != nullptr
        ? provider_string(*entry, "entry_type") : std::string();
    if (entry == nullptr ||
        !(type == "directory"
              ? provider_exact_keys(*entry,
                    {"entry_type", "relative_path", "size_bytes"})
              : type == "file" && provider_exact_keys(*entry,
                    {"entry_type", "relative_path", "sha256", "size_bytes"})) ||
        !provider_safe_relative(provider_string(*entry, "relative_path")) ||
        !provider_uint(*entry, "size_bytes") ||
        (type == "file" && !provider_digest(provider_string(*entry, "sha256"))))
      return facman::core::Result<MaintenancePlanReview>::failure(provider_error(
          "self_maintenance_provider_response_invalid",
          "Universal Setup plan entries are incompatible"));
    if (type == "file") ++observed_files;
    else ++observed_directories;
  }
  std::uint64_t declared_files = 0;
  std::uint64_t declared_directories = 0;
  if (!provider_uint(*totals, "file_count", &declared_files) ||
      !provider_uint(*totals, "directory_count", &declared_directories) ||
      declared_files != observed_files ||
      declared_directories != observed_directories)
    return facman::core::Result<MaintenancePlanReview>::failure(provider_error(
        "self_maintenance_provider_response_invalid",
        "Universal Setup plan totals do not bind its entries"));
  for (std::size_t index = 0; index < effects->size(); ++index) {
    const json::Value *effect = effects->at(index);
    const std::string kind = effect != nullptr
        ? provider_string(*effect, "kind") : std::string();
    const std::string root_class = effect != nullptr
        ? provider_string(*effect, "root_class") : std::string();
    if (effect == nullptr || !provider_exact_keys(*effect,
            {"effect_id", "kind", "relative_path", "root_class"}) ||
        provider_string(*effect, "effect_id").empty() ||
        (kind != "create_directory" && kind != "write_file" &&
         kind != "write_installed_state" && kind != "write_journal" &&
         kind != "write_audit") ||
        (root_class != "owned_target" && root_class != "setup_state" &&
         root_class != "staging" && root_class != "audit") ||
        !provider_safe_relative(provider_string(*effect, "relative_path")))
      return facman::core::Result<MaintenancePlanReview>::failure(provider_error(
          "self_maintenance_provider_response_invalid",
          "Universal Setup plan effects are incompatible"));
  }
  auto semantic_digest = maintenance_plan_semantic_digest(*payload, authority);
  if (!semantic_digest)
    return facman::core::Result<MaintenancePlanReview>::failure(semantic_digest.error());
  return facman::core::Result<MaintenancePlanReview>::success(
      {request_id, provider_string(*payload, "plan_digest"),
       semantic_digest.take_value()});
}

} // namespace

struct ProviderBridge::Impl {
  fs::path state_root;
  fs::path acceptance_root;
  self_setup::ProviderEffects *effects = nullptr;
  self_setup::Clock *clock = nullptr;
  std::string reviewed_key;
  std::string reviewed_transaction_id;
  std::string reviewed_recipe_digest;
  std::string reviewed_receipt;
  std::string reviewed_semantic_digest;
  std::string reviewed_plan_id;
  std::string reviewed_plan_digest;
  std::string reviewed_plan_created_at;
  std::string reviewed_request_id;
  ProviderApplyBinding reviewed_binding;
  std::string apply_payload;
  std::string inspected_key;
  std::string inspected_state_digest;
  std::string inspected_ownership_digest;
  std::string inspected_recipe_digest;
  facman::platform::StableDirectoryObject acceptance_pin;
  facman::platform::StableDirectoryObject state_pin;
};

ProviderBridge::ProviderBridge(fs::path state_root, fs::path acceptance_root,
                               self_setup::ProviderEffects *effects,
                               self_setup::Clock *clock)
    : impl_(std::make_unique<Impl>()) {
  impl_->state_root = std::move(state_root).lexically_normal();
  impl_->acceptance_root = std::move(acceptance_root).lexically_normal();
  impl_->effects = effects;
  impl_->clock = clock;
}

ProviderBridge::~ProviderBridge() = default;
ProviderBridge::ProviderBridge(ProviderBridge &&) noexcept = default;
ProviderBridge &ProviderBridge::operator=(ProviderBridge &&) noexcept = default;

facman::core::Result<InstalledIdentity> ProviderBridge::inspect_identity(
    const std::string &install_id) {
  facman::platform::StableDirectoryObject acceptance;
  auto opened = acceptance.open_no_follow(impl_->acceptance_root);
  if (!opened.ok() ||
      !acceptance.validate_descendant(impl_->state_root, false).ok())
    return facman::core::Result<InstalledIdentity>::failure(provider_error(
        "self_maintenance_provider_root_unsafe",
        "provider state root is outside stable acceptance authority"));
  facman::platform::StableDirectoryObject state;
  opened = state.open_no_follow(impl_->state_root);
  if (!opened.ok() || !acceptance.revalidate().ok() ||
      !state.revalidate().ok())
    return facman::core::Result<InstalledIdentity>::failure(provider_error(
        "self_maintenance_provider_root_unsafe",
        "provider roots are not stable existing directories"));
  json::ObjectBuilder request;
  request.add_string("schema", "usk.installed_inspect_request.v1");
  request.add_string("request_id",
      "request.maintenance.inspect." + provider_hash(install_id).substr(0, 32));
  request.add_string("install_id", install_id);
  auto response = self_setup::command_with(
      impl_->effects, "installed.inspect", request.serialize(),
      impl_->state_root, impl_->acceptance_root, true);
  if (!response)
    return facman::core::Result<InstalledIdentity>::failure(provider_error(
        "self_maintenance_inspect_failed",
        "Universal Setup could not inspect the installation",
        response.error().detail.empty() ? response.error().message
                                        : response.error().detail));
  auto decoded = decode_installed_identity(response.value());
  if (!decoded || decoded.value().install_id != install_id)
    return facman::core::Result<InstalledIdentity>::failure(
        decoded ? provider_error(
            "self_maintenance_provider_response_invalid",
            "Universal Setup inspected a different installation")
                : decoded.error());
  return decoded;
}

CandidateState ProviderBridge::inspect_candidate(const Plan &transition) {
  facman::platform::PathIdentity identity;
  const auto inspected = facman::platform::inspect_path_no_follow(
      transition.target.install_root, identity);
  if (!inspected.ok()) return CandidateState::unreadable;
  if (!identity.exists) return CandidateState::absent;
  if (identity.reparse_or_link ||
      identity.kind != facman::platform::PathObjectKind::directory)
    return CandidateState::foreign;
  auto installed = inspect_identity(transition.target.install_id);
  return installed &&
      installed.value().product_version == transition.target.product_version &&
      installed.value().source_archive_sha256 == transition.package_sha256 &&
      installed.value().recipe_digest == maintenance_recipe_digest(transition) &&
      provider_same_path(installed.value().install_root,
                         transition.target.install_root)
      ? CandidateState::exact : CandidateState::foreign;
}

EffectResult ProviderBridge::review_install_local(const Plan &transition) {
  if (transition.provider_operation != "install_local")
    return {false, false, {}, "provider operation is not install_local"};
  if (transition.target.universal_setup_revision !=
      self_setup::provider_revision())
    return {false, false, {},
            "package Universal Setup revision differs from the pinned provider"};
  if (!provider_same_path(transition.target.state_root, impl_->state_root) ||
      !provider_same_path(transition.target.acceptance_root,
                          impl_->acceptance_root))
    return {false, false, {},
            "generation provider roots differ from the configured authority"};
  facman::platform::StableDirectoryObject acceptance;
  auto admitted = acceptance.open_no_follow(impl_->acceptance_root);
  if (!admitted.ok())
    return {false, false, {},
            "acceptance root is not a stable plain directory: " +
                admitted.code + ": " + admitted.detail};
  admitted = acceptance.validate_descendant(impl_->state_root, false);
  if (!admitted.ok())
    return {false, false, {},
            "provider state root is outside stable acceptance authority: " +
                admitted.code + ": " + admitted.detail};
  facman::platform::StableDirectoryObject state;
  admitted = state.open_no_follow(impl_->state_root);
  if (!admitted.ok() || !acceptance.revalidate().ok() ||
      !state.revalidate().ok())
    return {false, false, {},
            "provider roots are not stable existing directories"};
  impl_->acceptance_pin = std::move(acceptance);
  impl_->state_pin = std::move(state);
  const std::string key = bridge_key(transition);
  if (impl_->reviewed_key == key && !impl_->apply_payload.empty())
    return impl_->reviewed_recipe_digest == maintenance_recipe_digest(transition)
        ? EffectResult{true, false, impl_->reviewed_receipt, {}}
        : EffectResult{false, false, {},
              "cached provider plan has a different recipe identity"};
  impl_->reviewed_key.clear();
  impl_->reviewed_transaction_id.clear();
  impl_->reviewed_recipe_digest.clear();
  impl_->reviewed_receipt.clear();
  impl_->reviewed_semantic_digest.clear();
  impl_->reviewed_plan_id.clear();
  impl_->reviewed_plan_digest.clear();
  impl_->reviewed_plan_created_at.clear();
  impl_->reviewed_request_id.clear();
  impl_->apply_payload.clear();
  std::string created_at = self_setup::timestamp();
  if (impl_->clock != nullptr) {
    // Tests and embedders that supply the bridge clock get a deterministic
    // request timestamp; ordinary provider operation remains wall-clock based.
    auto controlled_time = self_setup::timestamp_after(
        "1970-01-01T00:00:00Z", impl_->clock);
    if (!controlled_time)
      return {false, false, {}, controlled_time.error().message + ": " +
          controlled_time.error().detail};
    created_at = controlled_time.take_value();
  }
  const std::string request_id =
      "request.maintenance." + key.substr(0, 32);
  const auto plan = maintenance_install_plan(
      transition, created_at, request_id);
  auto planned = self_setup::command_with(
      impl_->effects, "install_local.plan", plan.serialize(),
      impl_->state_root, impl_->acceptance_root, true);
  if (!planned)
    return {false, false, {}, planned.error().message + ": " +
        planned.error().detail};
  auto plan_document = json::parse(plan.serialize());
  const json::Value *recipe = plan_document
      ? plan_document.value().find("recipe") : nullptr;
  const std::string recipe_digest = recipe != nullptr
      ? provider_string(*recipe, "recipe_digest") : std::string();
  auto reviewed = decode_maintenance_plan(
      planned.value(), transition, created_at, request_id, recipe_digest);
  if (!reviewed)
    return {false, false, {}, reviewed.error().message + ": " +
        reviewed.error().detail};
  // Universal Setup derives its ownership-record identifier from both the
  // install and transaction identities.  Keep the install identifier's full
  // 256-bit generation suffix and bound only this opaque transaction label to
  // the provider's 128-character durable-record limit.
  const std::string transaction_id = "tx.m." + key.substr(0, 24);
  auto apply = self_setup::apply_request(
      "usk.install_local_apply_request.v1", plan,
      reviewed.value().plan_id, reviewed.value().digest, created_at,
      transaction_id, impl_->clock);
  if (!apply)
    return {false, false, {}, apply.error().message + ": " +
        apply.error().detail};
  impl_->reviewed_key = key;
  impl_->reviewed_transaction_id = transaction_id;
  impl_->reviewed_recipe_digest = recipe_digest;
  impl_->reviewed_receipt = maintenance_review_receipt(
      transition, reviewed.value().semantic_digest);
  impl_->reviewed_semantic_digest = reviewed.value().semantic_digest;
  impl_->reviewed_plan_id = reviewed.value().plan_id;
  impl_->reviewed_plan_digest = reviewed.value().digest;
  impl_->reviewed_plan_created_at = created_at;
  impl_->reviewed_request_id = request_id;
  impl_->apply_payload = apply.value().serialize();
  return {true, false, impl_->reviewed_receipt, {}};
}

facman::core::Result<ProviderApplyBinding> ProviderBridge::bind_install_local(
    const Plan &transition, const std::string &expected_provider_plan_sha256) {
  const EffectResult reviewed = review_install_local(transition);
  if (!reviewed.ok || reviewed.outcome_unknown ||
      reviewed.receipt_sha256 != expected_provider_plan_sha256 ||
      impl_->reviewed_transaction_id.empty())
    return facman::core::Result<ProviderApplyBinding>::failure({
        "self_maintenance_provider_binding_invalid",
        "provider review does not bind the admitted epoch handoff", reviewed.detail});
  const std::string apply_digest = provider_hash(impl_->apply_payload);
  if (!provider_digest(apply_digest) || impl_->apply_payload.empty())
    return facman::core::Result<ProviderApplyBinding>::failure({
        "self_maintenance_provider_binding_invalid",
        "provider apply request is unavailable after review", {}});
  impl_->reviewed_binding = {reviewed.receipt_sha256, impl_->reviewed_transaction_id, apply_digest,
       impl_->apply_payload, impl_->reviewed_semantic_digest, impl_->reviewed_key,
       impl_->reviewed_plan_id, impl_->reviewed_plan_digest,
       impl_->reviewed_plan_created_at, impl_->reviewed_request_id};
  return facman::core::Result<ProviderApplyBinding>::success(impl_->reviewed_binding);
}

facman::core::Result<void> ProviderBridge::rehydrate_install_local(
    const Plan &transition, const ProviderApplyBinding &binding) {
  std::string detail;
  auto payload = json::parse(binding.apply_payload);
  const json::Value *plan_request = payload && payload.value().is_object()
      ? payload.value().find("plan_request") : nullptr;
  const json::Value *archive = plan_request != nullptr && plan_request->is_object()
      ? plan_request->find("archive") : nullptr;
  const json::Value *target = plan_request != nullptr && plan_request->is_object()
      ? plan_request->find("target") : nullptr;
  const json::Value *recipe = plan_request != nullptr && plan_request->is_object()
      ? plan_request->find("recipe") : nullptr;
  const std::string key = bridge_key(transition);
  const std::string expected_request_id = "request.maintenance." + key.substr(0, 32);
  const std::string expected_transaction_id = "tx.m." + key.substr(0, 24);
  const auto expected_plan = maintenance_install_plan(
      transition, binding.plan_created_at, expected_request_id).serialize();
  const auto expected_plan_document = json::parse(expected_plan);
  const auto canonical_expected_plan = expected_plan_document
      ? json::canonical_integer_json(expected_plan_document.value())
      : json::canonical_integer_json(json::Value{});
  const auto canonical_plan = plan_request != nullptr
      ? json::canonical_integer_json(*plan_request) : json::canonical_integer_json(json::Value{});
  if (plan_request == nullptr || !canonical_plan || !canonical_expected_plan ||
      canonical_plan.value() != canonical_expected_plan.value())
    return facman::core::Result<void>::failure(provider_error(
        "self_maintenance_provider_binding_invalid", "stored provider plan request differs from binding"));
  if (binding.bridge_key != key || binding.request_id != expected_request_id ||
      binding.transaction_id != expected_transaction_id)
    return facman::core::Result<void>::failure(provider_error(
        "self_maintenance_provider_binding_invalid", "stored provider key identities differ from binding"));
  if (binding.provider_plan_sha256 != maintenance_review_receipt(transition, binding.semantic_digest))
    return facman::core::Result<void>::failure(provider_error(
        "self_maintenance_provider_binding_invalid", "stored provider receipt differs from semantic binding"));
  if (binding.provider_plan_sha256.empty() ||
      binding.transaction_id.empty() || binding.transaction_id.size() > 128U ||
      binding.apply_payload.empty() || provider_hash(binding.apply_payload) != binding.apply_sha256 ||
      !payload || !payload.value().is_object() ||
      !provider_exact_keys(payload.value(), {"schema", "transaction_id", "applied_at",
          "confirmation", "reviewed_plan_id", "reviewed_plan_digest", "plan_request"}) ||
      provider_string(payload.value(), "transaction_id") != binding.transaction_id ||
      provider_string(payload.value(), "schema") != "usk.install_local_apply_request.v1" ||
      provider_string(payload.value(), "confirmation") != "APPLY" ||
      provider_string(payload.value(), "reviewed_plan_id").empty() ||
      !provider_digest(provider_string(payload.value(), "reviewed_plan_digest")) ||
      !self_setup::valid_timestamp(provider_string(payload.value(), "applied_at")) ||
      binding.bridge_key != key || binding.request_id != expected_request_id ||
      binding.transaction_id != expected_transaction_id ||
      !self_setup::valid_timestamp(binding.plan_created_at) ||
      plan_request == nullptr || !canonical_plan || !canonical_expected_plan ||
      canonical_plan.value() != canonical_expected_plan.value() ||
      provider_string(payload.value(), "reviewed_plan_id") != binding.reviewed_plan_id ||
      provider_string(payload.value(), "reviewed_plan_digest") != binding.reviewed_plan_digest ||
      binding.provider_plan_sha256 != maintenance_review_receipt(
          transition, binding.semantic_digest) ||
      plan_request == nullptr || !plan_request->is_object() ||
      provider_string(*plan_request, "schema") != "usk.install_local_plan_request.v1" ||
      provider_string(*plan_request, "install_id") != transition.target.install_id ||
      archive == nullptr || !archive->is_object() ||
      provider_string(*archive, "expected_sha256") != transition.package_sha256 ||
      target == nullptr || !target->is_object() ||
      provider_string(*target, "root") != facman::platform::path_to_utf8(transition.target.install_root) ||
      recipe == nullptr || !recipe->is_object() ||
      provider_string(*recipe, "recipe_digest") != maintenance_recipe_digest(transition) ||
      provider_string(*recipe, "provider_revision") != self_setup::provider_revision() ||
      transition.target.universal_setup_revision != self_setup::provider_revision() ||
      !provider_same_path(transition.target.state_root, impl_->state_root) ||
      !provider_same_path(transition.target.acceptance_root, impl_->acceptance_root))
    return facman::core::Result<void>::failure(provider_error(
        "self_maintenance_provider_binding_invalid",
        "stored provider apply payload is not an exact usable binding"));
  facman::platform::StableDirectoryObject acceptance, state;
  if (!acceptance.open_no_follow(impl_->acceptance_root).ok() ||
      !acceptance.validate_descendant(impl_->state_root, false).ok() ||
      !state.open_no_follow(impl_->state_root).ok())
    return facman::core::Result<void>::failure(provider_error(
        "self_maintenance_provider_root_unsafe", "provider authority changed before rehydration"));
  impl_->acceptance_pin = std::move(acceptance);
  impl_->state_pin = std::move(state);
  // The durable receipt is a projection of provider-reviewed semantics, not
  // merely of the caller-supplied digest. Re-run the exact read-only request
  // with its persisted timestamp/request identity before accepting an apply
  // payload, so an alternate permitted-effect plan cannot borrow another
  // plan's semantic digest and receipt.
  const auto persisted_plan = maintenance_install_plan(
      transition, binding.plan_created_at, binding.request_id);
  auto reviewed_response = self_setup::command_with(
      impl_->effects, "install_local.plan", persisted_plan.serialize(),
      impl_->state_root, impl_->acceptance_root, true);
  const auto persisted_document = json::parse(persisted_plan.serialize());
  const json::Value *persisted_recipe = persisted_document
      ? persisted_document.value().find("recipe") : nullptr;
  const std::string persisted_recipe_digest = persisted_recipe != nullptr
      ? provider_string(*persisted_recipe, "recipe_digest") : std::string();
  auto reviewed_persisted = reviewed_response
      ? decode_maintenance_plan(reviewed_response.value(), transition,
          binding.plan_created_at, binding.request_id, persisted_recipe_digest)
      : facman::core::Result<MaintenancePlanReview>::failure(reviewed_response.error());
  if (!reviewed_persisted ||
      reviewed_persisted.value().semantic_digest != binding.semantic_digest ||
      reviewed_persisted.value().plan_id != binding.reviewed_plan_id ||
      reviewed_persisted.value().digest != binding.reviewed_plan_digest)
    return facman::core::Result<void>::failure(provider_error(
        "self_maintenance_provider_binding_invalid",
        "stored provider semantic identity differs from the exact reviewed plan"));
  impl_->reviewed_key = binding.bridge_key;
  impl_->reviewed_transaction_id = binding.transaction_id;
  impl_->reviewed_recipe_digest = maintenance_recipe_digest(transition);
  impl_->reviewed_receipt = binding.provider_plan_sha256;
  impl_->reviewed_semantic_digest = binding.semantic_digest;
  impl_->reviewed_plan_id = binding.reviewed_plan_id;
  impl_->reviewed_plan_digest = binding.reviewed_plan_digest;
  impl_->reviewed_plan_created_at = binding.plan_created_at;
  impl_->reviewed_request_id = binding.request_id;
  impl_->reviewed_binding = binding;
  impl_->apply_payload = binding.apply_payload;
  return facman::core::Result<void>::success();
}

EffectResult ProviderBridge::apply_bound_install_local(
    const Plan &transition, const ProviderApplyBinding &binding) {
  const ProviderApplyBinding &cached = impl_->reviewed_binding;
  if (binding.provider_plan_sha256 != cached.provider_plan_sha256 ||
      binding.transaction_id != cached.transaction_id ||
      binding.apply_sha256 != cached.apply_sha256 ||
      binding.apply_payload != cached.apply_payload ||
      binding.semantic_digest != cached.semantic_digest || binding.bridge_key != cached.bridge_key ||
      binding.reviewed_plan_id != cached.reviewed_plan_id ||
      binding.reviewed_plan_digest != cached.reviewed_plan_digest ||
      binding.plan_created_at != cached.plan_created_at || binding.request_id != cached.request_id ||
      binding.apply_sha256 != provider_hash(impl_->apply_payload))
    return {false, false, {}, "provider apply binding differs from the reviewed request"};
  return install_local(transition);
}

EffectResult ProviderBridge::install_local(const Plan &transition) {
  if (impl_->reviewed_key != bridge_key(transition) ||
      impl_->apply_payload.empty() || impl_->reviewed_transaction_id.empty() ||
      impl_->reviewed_recipe_digest != maintenance_recipe_digest(transition))
    return {false, false, {}, "no exact reviewed install_local plan is cached"};
  const auto acceptance_stable = impl_->acceptance_pin.revalidate();
  const auto state_stable = impl_->state_pin.revalidate();
  const auto admitted = impl_->acceptance_pin.validate_descendant(
      impl_->state_root, false);
  if (!acceptance_stable.ok() || !state_stable.ok() || !admitted.ok())
    return {false, false, {},
            "provider root authority changed after plan admission"};
  auto response = self_setup::command_with(
      impl_->effects, "install_local.apply", impl_->apply_payload,
      impl_->state_root, impl_->acceptance_root, false);
  if (!response)
    return {false, true, {}, response.error().message + ": " +
        response.error().detail};
  auto installed = decode_installed_identity(response.value());
  if (!installed ||
      installed.value().install_id != transition.target.install_id ||
      installed.value().product_version != transition.target.product_version ||
      installed.value().source_archive_sha256 != transition.package_sha256 ||
      installed.value().recipe_digest != impl_->reviewed_recipe_digest ||
      installed.value().provider_revision !=
          transition.target.universal_setup_revision ||
      installed.value().transaction_id != impl_->reviewed_transaction_id ||
      !provider_same_path(installed.value().install_root,
                          transition.target.install_root))
    return {false, true, {}, installed
        ? "provider apply receipt does not bind the reviewed generation"
        : installed.error().message + ": " + installed.error().detail};
  impl_->apply_payload.clear();
  return {true, false, provider_hash(response.value()), {}};
}

EffectResult ProviderBridge::prepare_install_local(const Plan &) {
  return {false, false, {},
          "offline repair input retention requires the application storage edge"};
}

namespace {
bool installed_binds_transition(const InstalledIdentity &installed, const Plan &transition,
                               const std::string *transaction = nullptr) {
  return installed.install_id == transition.target.install_id &&
      installed.product_version == transition.target.product_version &&
      installed.source_archive_sha256 == transition.target.package_sha256 &&
      installed.recipe_digest == maintenance_recipe_digest(transition) &&
      installed.provider_revision == transition.target.universal_setup_revision &&
      provider_same_path(installed.install_root, transition.target.install_root) &&
      (transaction == nullptr || installed.transaction_id == *transaction);
}

} // namespace

EffectResult ProviderBridge::inspect_installed(const Plan &transition) {
  auto installed = inspect_identity(transition.target.install_id);
  if (!installed) return {false, false, {}, installed.error().message + ": " + installed.error().detail};
  if (!installed_binds_transition(installed.value(), transition))
    return {false, false, {}, "installed state does not bind the retained generation"};
  const std::string identity = installed.value().install_id + "\n" +
      installed.value().product_version + "\n" + installed.value().source_archive_sha256 + "\n" +
      facman::platform::path_to_utf8(installed.value().install_root) + "\n";
  impl_->inspected_key = bridge_key(transition);
  impl_->inspected_state_digest = installed.value().installed_state_digest;
  impl_->inspected_ownership_digest = installed.value().ownership_manifest_digest;
  impl_->inspected_recipe_digest = installed.value().recipe_digest;
  return {true, false, provider_hash(identity), {}};
}

EffectResult ProviderBridge::inspect_retained_installed(const Plan &transition) {
  return inspect_installed(transition);
}

EffectResult ProviderBridge::inspect_installed(const Plan &transition,
                                               const ProviderApplyBinding &binding) {
  if (binding.transaction_id.empty() || binding.transaction_id.size() > 128U)
    return {false, false, {}, "stored provider transaction identity is invalid"};
  auto installed = inspect_identity(transition.target.install_id);
  if (!installed) return {false, false, {}, installed.error().message + ": " + installed.error().detail};
  if (!installed_binds_transition(installed.value(), transition, &binding.transaction_id))
    return {false, false, {}, "installed state does not bind the durable apply transaction"};
  const std::string identity = installed.value().install_id + "\n" +
      installed.value().product_version + "\n" + installed.value().source_archive_sha256 + "\n" +
      facman::platform::path_to_utf8(installed.value().install_root) + "\n";
  impl_->inspected_key = bridge_key(transition);
  impl_->inspected_state_digest = installed.value().installed_state_digest;
  impl_->inspected_ownership_digest = installed.value().ownership_manifest_digest;
  impl_->inspected_recipe_digest = installed.value().recipe_digest;
  return {true, false, provider_hash(identity), {}};
}

EffectResult ProviderBridge::validate_terminal_verification(
    const Plan &transition, const ProviderApplyBinding &binding,
    const std::string &receipt_sha256) {
  if (!provider_digest(receipt_sha256) ||
      !self_setup::valid_timestamp(binding.plan_created_at))
    return {false, false, {}, "durable provider verification receipt is invalid"};
  auto installed = inspect_identity(transition.target.install_id);
  if (!installed || !installed_binds_transition(installed.value(), transition,
                                                 &binding.transaction_id))
    return {false, false, {}, installed ?
        "installed state does not reproduce the durable apply identity" :
        installed.error().message + ": " + installed.error().detail};
  // installed.verify is read-only: its report is not written back into the
  // installed-state record.  Reproduce the exact deterministic request from
  // the durable provider binding and compare the freshly observed filesystem
  // report with the receipt stored in phase 40.
  impl_->inspected_key = bridge_key(transition);
  impl_->inspected_state_digest = installed.value().installed_state_digest;
  impl_->inspected_ownership_digest = installed.value().ownership_manifest_digest;
  impl_->inspected_recipe_digest = installed.value().recipe_digest;
  impl_->reviewed_plan_created_at = binding.plan_created_at;
  const EffectResult reproduced = verify_installed(transition);
  if (!reproduced.ok || reproduced.outcome_unknown ||
      reproduced.receipt_sha256 != receipt_sha256)
    return {false, reproduced.outcome_unknown, {}, reproduced.ok
        ? "installed state does not reproduce the durable verification report"
        : reproduced.detail};
  return reproduced;
}

EffectResult ProviderBridge::verify_installed(const Plan &transition) {
  const std::string identity = bridge_key(transition);
  if (impl_->inspected_key != identity ||
      !provider_digest(impl_->inspected_state_digest) ||
      !provider_digest(impl_->inspected_ownership_digest) ||
      impl_->inspected_recipe_digest != maintenance_recipe_digest(transition))
    return {false, false, {},
            "verification requires the exact inspected installed state"};
  json::ObjectBuilder request;
  const std::string report_id =
      "report.maintenance." + identity.substr(0, 32);
  const std::string verified_at =
      self_setup::valid_timestamp(impl_->reviewed_plan_created_at)
          ? impl_->reviewed_plan_created_at
          : self_setup::timestamp();
  request.add_string("schema", "usk.installed_verify_request.v1");
  request.add_string("request_id",
      "request.maintenance.verify." + identity.substr(0, 24));
  request.add_string("install_id", transition.target.install_id);
  request.add_string("report_id", report_id);
  request.add_string("verified_at", verified_at);
  auto response = self_setup::command_with(
      impl_->effects, "installed.verify", request.serialize(),
      impl_->state_root, impl_->acceptance_root, true);
  if (!response)
    return {false, false, {}, response.error().message + ": " +
        response.error().detail};
  auto envelope = json::parse(response.value());
  const json::Value *response_error = envelope && envelope.value().is_object()
      ? envelope.value().find("error") : nullptr;
  const json::Value *payload = envelope && envelope.value().is_object()
      ? envelope.value().find("payload") : nullptr;
  if (!envelope ||
      !provider_exact_keys(envelope.value(),
          {"error", "payload", "schema", "status"}) ||
      provider_string(envelope.value(), "schema") !=
          "usk.command_response.v1" ||
      provider_string(envelope.value(), "status") != "ok" ||
      response_error == nullptr || !response_error->is_null() ||
      payload == nullptr || !payload->is_object() ||
      !provider_exact_keys(*payload,
          {"directories", "files", "install_id", "installed_state_digest",
           "ownership_manifest_digest", "report_digest", "report_id",
           "schema", "status", "summary", "unknown_paths", "verified_at"}) ||
      provider_string(*payload, "schema") != "usk.verification_report.v1" ||
      provider_string(*payload, "install_id") != transition.target.install_id ||
      provider_string(*payload, "report_id") != report_id ||
      provider_string(*payload, "verified_at") != verified_at ||
      provider_string(*payload, "status") != "pass" ||
      !provider_digest(provider_string(*payload, "report_digest")) ||
      provider_string(*payload, "installed_state_digest") !=
          impl_->inspected_state_digest ||
      provider_string(*payload, "ownership_manifest_digest") !=
          impl_->inspected_ownership_digest)
    return {false, false, {},
            "Universal Setup verification response did not bind the requested "
            "installed state, ownership, report, timestamp, and evidence"};
  const json::Value *files = payload->find("files");
  const json::Value *directories = payload->find("directories");
  const json::Value *unknown = payload->find("unknown_paths");
  const json::Value *summary = payload->find("summary");
  std::uint64_t owned_files = 0;
  std::uint64_t missing_files = 0;
  std::uint64_t modified_files = 0;
  std::uint64_t unknown_count = 0;
  if (files == nullptr || !files->is_array() ||
      directories == nullptr || !directories->is_array() ||
      unknown == nullptr || !unknown->is_array() || unknown->size() != 0U ||
      summary == nullptr || !provider_exact_keys(*summary,
          {"missing_files", "modified_files", "owned_files",
           "unknown_paths"}) ||
      !provider_uint(*summary, "owned_files", &owned_files) ||
      !provider_uint(*summary, "missing_files", &missing_files) ||
      !provider_uint(*summary, "modified_files", &modified_files) ||
      !provider_uint(*summary, "unknown_paths", &unknown_count) ||
      owned_files != files->size() || missing_files != 0U ||
      modified_files != 0U || unknown_count != 0U)
    return {false, false, {},
            "Universal Setup verification evidence summary is incompatible"};
  std::set<std::string> observed_paths;
  for (std::size_t index = 0; index < files->size(); ++index) {
    const json::Value *file = files->at(index);
    const bool has_actual = file != nullptr &&
        file->find("actual_sha256") != nullptr;
    const std::string path = file != nullptr
        ? provider_string(*file, "relative_path") : std::string();
    const std::string expected = file != nullptr
        ? provider_string(*file, "expected_sha256") : std::string();
    if (file == nullptr ||
        !(has_actual
              ? provider_exact_keys(*file,
                    {"actual_sha256", "expected_sha256", "relative_path",
                     "status"})
              : provider_exact_keys(*file,
                    {"expected_sha256", "relative_path", "status"})) ||
        !provider_safe_relative(path) ||
        !observed_paths.insert(path).second ||
        provider_string(*file, "status") != "present" ||
        !provider_digest(expected) ||
        (has_actual && provider_string(*file, "actual_sha256") != expected))
      return {false, false, {},
              "Universal Setup verification file evidence is incompatible"};
  }
  for (std::size_t index = 0; index < directories->size(); ++index) {
    const json::Value *directory = directories->at(index);
    const std::string path = directory != nullptr
        ? provider_string(*directory, "relative_path") : std::string();
    if (directory == nullptr || !provider_exact_keys(*directory,
            {"relative_path", "status"}) ||
        !provider_safe_relative(path) ||
        !observed_paths.insert(path).second ||
        provider_string(*directory, "status") != "present")
      return {false, false, {},
              "Universal Setup verification directory evidence is incompatible"};
  }
  json::ObjectBuilder report_projection;
  for (const char *key : {
           "directories", "files", "install_id", "installed_state_digest",
           "ownership_manifest_digest", "report_id", "status", "summary",
           "unknown_paths", "verified_at"}) {
    const json::Value *field = payload->find(key);
    if (field == nullptr || !report_projection.add_value(key, *field))
      return {false, false, {},
              "Universal Setup verification digest projection is incompatible"};
  }
  auto projected = json::parse(report_projection.serialize());
  auto canonical = projected
      ? json::canonical_integer_json(projected.value())
      : facman::core::Result<std::string>::failure(provider_error(
            "self_maintenance_provider_response_invalid",
            "verification digest projection could not be parsed"));
  if (!canonical || provider_hash(canonical.value()) !=
          provider_string(*payload, "report_digest"))
    return {false, false, {},
            "Universal Setup verification report digest is incompatible"};
  return {true, false, provider_string(*payload, "report_digest"), {}};
}

} // namespace facman::self_maintenance
