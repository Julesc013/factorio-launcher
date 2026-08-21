// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "ulk/ulk_api.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <set>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

namespace fs = std::filesystem;

namespace {

struct Options {
  fs::path root;
  fs::path output;
  std::uint64_t admissions = 100000U;
  std::uint64_t reopen_cycles = 1000U;
  unsigned int writers = 2U;
  unsigned int readers = 8U;
  unsigned int maximum_records = 64U;
  unsigned int minimum_seconds = 5400U;
};

ulk_string_view view(const std::string &value) {
  return {value.data(), static_cast<ulk_size>(value.size())};
}

std::string json_escape(const std::string &value) {
  std::ostringstream output;
  for (const unsigned char byte : value) {
    switch (byte) {
    case '\\':
      output << "\\\\";
      break;
    case '"':
      output << "\\\"";
      break;
    case '\n':
      output << "\\n";
      break;
    case '\r':
      output << "\\r";
      break;
    case '\t':
      output << "\\t";
      break;
    default:
      if (byte < 0x20U) {
        output << "\\u" << std::hex << std::setw(4) << std::setfill('0')
               << static_cast<unsigned int>(byte) << std::dec;
      } else {
        output << static_cast<char>(byte);
      }
    }
  }
  return output.str();
}

bool parse_unsigned(const char *value, std::uint64_t &output) {
  try {
    std::size_t consumed = 0U;
    const std::string text(value);
    output = std::stoull(text, &consumed, 10);
    return consumed == text.size();
  } catch (...) {
    return false;
  }
}

bool parse_arguments(int argc, char **argv, Options &options) {
  for (int index = 1; index < argc; ++index) {
    const std::string argument(argv[index]);
    if (index + 1 >= argc)
      return false;
    const char *value = argv[++index];
    std::uint64_t number = 0U;
    if (argument == "--root")
      options.root = fs::u8path(value);
    else if (argument == "--output")
      options.output = fs::u8path(value);
    else if (!parse_unsigned(value, number))
      return false;
    else if (argument == "--admissions")
      options.admissions = number;
    else if (argument == "--reopen-cycles")
      options.reopen_cycles = number;
    else if (argument == "--writers")
      options.writers = static_cast<unsigned int>(number);
    else if (argument == "--readers")
      options.readers = static_cast<unsigned int>(number);
    else if (argument == "--maximum-records")
      options.maximum_records = static_cast<unsigned int>(number);
    else if (argument == "--minimum-seconds")
      options.minimum_seconds = static_cast<unsigned int>(number);
    else
      return false;
  }
  return !options.root.empty() && !options.output.empty() &&
         options.admissions != 0U && options.writers >= 2U &&
         options.readers >= 8U && options.maximum_records != 0U;
}

std::string identity(const char *prefix, std::uint64_t index) {
  std::ostringstream value;
  value << prefix << '-' << std::setw(12) << std::setfill('0') << index;
  return value.str();
}

void initialize_error(ulk_error_v1 &error) {
  error = {};
  error.struct_size = sizeof(error);
}

bool write_session(const std::string &root, unsigned int maximum_records,
                   std::uint64_t index,
                   std::atomic<std::uint64_t> &successful_admissions,
                   std::atomic<std::uint64_t> &successful_terminal_writes,
                   std::atomic<std::uint64_t> &contention_retries,
                   std::atomic<std::uint64_t> &failures) {
  const std::string session_id = identity("session", index);
  const std::string operation_id = identity("operation", index);
  const std::string attempt_id = identity("attempt", index);
  const std::string runnable = "facman.instance:endurance";
  const std::string process = "endurance-writer";
  const std::string timestamp = "2026-08-16T06:45:00Z";
  const std::string relaunch = "relaunch:facman.instance:endurance";

  ulk_session_journal_v1 journal{};
  journal.struct_size = sizeof(journal);
  journal.root = view(root);
  journal.maximum_records = maximum_records;

  ulk_session_record_v1 record{};
  record.struct_size = sizeof(record);
  record.session_id = view(session_id);
  record.identity.struct_size = sizeof(record.identity);
  record.identity.operation_id = view(operation_id);
  record.identity.attempt_id = view(attempt_id);
  record.runnable_reference = view(runnable);
  record.process_identity = view(process);
  record.state = ULK_SESSION_RUNNING;
  record.started_at = view(timestamp);

  ulk_error_v1 error;
  initialize_error(error);
  for (;;) {
    if (ulk_session_journal_write_v1(&journal, &record, &error) ==
        ULK_STATUS_OK)
      break;
    const std::string detail(error.detail.data, error.detail.size);
    if (detail != "session_lock_unavailable") {
      ++failures;
      return false;
    }
    ++contention_retries;
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
    initialize_error(error);
  }
  ++successful_admissions;

  ulk_operation_result_v1 result{};
  result.struct_size = sizeof(result);
  result.identity = record.identity;
  result.outcome = ULK_OPERATION_COMPLETED;
  result.effects_may_have_occurred = 1;
  result.recovery.struct_size = sizeof(result.recovery);
  record.state = ULK_SESSION_TERMINAL;
  record.ended_at = view(timestamp);
  record.exit_code_known = 1;
  record.exit_code = 0;
  record.terminal_result = &result;
  record.relaunch_reference = view(relaunch);
  initialize_error(error);
  for (;;) {
    if (ulk_session_journal_write_v1(&journal, &record, &error) ==
        ULK_STATUS_OK)
      break;
    const std::string detail(error.detail.data, error.detail.size);
    if (detail != "session_lock_unavailable") {
      ++failures;
      return false;
    }
    ++contention_retries;
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
    initialize_error(error);
  }
  ++successful_terminal_writes;
  return true;
}

std::vector<std::string> split(const std::string &value, char separator) {
  std::vector<std::string> fields;
  std::string field;
  std::istringstream stream(value);
  while (std::getline(stream, field, separator))
    fields.push_back(field);
  return fields;
}

struct DiskAudit {
  std::size_t records = 0U;
  std::size_t terminal_records = 0U;
  std::size_t v2_records = 0U;
  std::size_t duplicate_commit_orders = 0U;
  std::int64_t maximum_commit_order = 0;
  std::string newest_session;
};

DiskAudit audit_records(const fs::path &root) {
  DiskAudit audit;
  std::set<std::int64_t> commit_orders;
  std::error_code error;
  const fs::path sessions = root / "sessions";
  for (const fs::directory_entry &entry :
       fs::directory_iterator(sessions, error)) {
    if (error || !entry.is_regular_file() ||
        entry.path().extension() != ".session")
      continue;
    std::ifstream input(entry.path(), std::ios::binary);
    const std::string text((std::istreambuf_iterator<char>(input)),
                           std::istreambuf_iterator<char>());
    const std::vector<std::string> fields = split(text, '|');
    ++audit.records;
    if (fields.size() != 20U || fields[0] != "ULK_SESSION_RECORD_V2")
      continue;
    ++audit.v2_records;
    if (fields[6] == "2")
      ++audit.terminal_records;
    std::int64_t order = 0;
    try {
      order = std::stoll(fields[18]);
    } catch (...) {
      continue;
    }
    if (!commit_orders.insert(order).second)
      ++audit.duplicate_commit_orders;
    if (order > audit.maximum_commit_order) {
      audit.maximum_commit_order = order;
      audit.newest_session = entry.path().stem().u8string();
    }
  }
  return audit;
}

} // namespace

int main(int argc, char **argv) {
  Options options;
  if (!parse_arguments(argc, argv, options)) {
    std::cerr
        << "usage: facman_ulk_session_journal_endurance --root PATH --output "
           "PATH "
           "[--admissions N] [--reopen-cycles N] [--writers N] [--readers N] "
           "[--maximum-records N] [--minimum-seconds N]\n";
    return 2;
  }

  std::error_code error;
  fs::remove_all(options.root, error);
  error.clear();
  fs::create_directories(options.root, error);
  if (error)
    return 3;
  fs::create_directories(options.output.parent_path(), error);
  if (error)
    return 4;

  const std::string root = options.root.u8string();
  const auto started = std::chrono::steady_clock::now();
  const auto deadline = started + std::chrono::seconds(options.minimum_seconds);
  std::atomic<std::uint64_t> next_index{0U};
  std::atomic<std::uint64_t> admissions{0U};
  std::atomic<std::uint64_t> terminal_writes{0U};
  std::atomic<std::uint64_t> write_failures{0U};
  std::atomic<std::uint64_t> contention_retries{0U};
  std::atomic<std::uint64_t> reader_calls{0U};
  std::atomic<std::uint64_t> reader_failures{0U};
  std::atomic<std::uint64_t> reopen_cycles{0U};
  std::atomic<bool> writers_complete{false};

  std::vector<std::thread> readers;
  for (unsigned int reader = 0U; reader < options.readers; ++reader) {
    readers.emplace_back([&] {
      const std::string runnable = "facman.instance:endurance";
      std::vector<char> buffer(8192U);
      while (!writers_complete.load(std::memory_order_acquire) ||
             reopen_cycles.load(std::memory_order_relaxed) <
                 options.reopen_cycles) {
        ulk_session_journal_v1 journal{};
        journal.struct_size = sizeof(journal);
        journal.root = view(root);
        journal.maximum_records = options.maximum_records;
        ulk_session_lookup_status_v1 lookup = ULK_SESSION_LOOKUP_NOT_FOUND;
        ulk_size required = 0U;
        ulk_error_v1 journal_error;
        initialize_error(journal_error);
        const int status = ulk_session_journal_last_run_v1(
            &journal, view(runnable), &lookup, buffer.data(),
            static_cast<ulk_size>(buffer.size()), &required, &journal_error);
        ++reader_calls;
        ++reopen_cycles;
        if (status != ULK_STATUS_OK) {
          const std::string detail(journal_error.detail.data,
                                   journal_error.detail.size);
          if (detail == "session_lock_unavailable")
            ++contention_retries;
          else
            ++reader_failures;
        } else if (lookup != ULK_SESSION_LOOKUP_FOUND &&
                   lookup != ULK_SESSION_LOOKUP_NOT_FOUND) {
          ++reader_failures;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
      }
    });
  }

  std::vector<std::thread> writers;
  for (unsigned int writer = 0U; writer < options.writers; ++writer) {
    writers.emplace_back([&] {
      for (;;) {
        const std::uint64_t index =
            next_index.fetch_add(1U, std::memory_order_relaxed);
        if (index >= options.admissions &&
            std::chrono::steady_clock::now() >= deadline)
          break;
        (void)write_session(root, options.maximum_records, index, admissions,
                            terminal_writes, contention_retries,
                            write_failures);
      }
    });
  }
  for (std::thread &writer : writers)
    writer.join();
  writers_complete.store(true, std::memory_order_release);
  for (std::thread &reader : readers)
    reader.join();

  const auto ended = std::chrono::steady_clock::now();
  const double elapsed = std::chrono::duration<double>(ended - started).count();
  const DiskAudit audit = audit_records(options.root);

  ulk_session_journal_v1 journal{};
  journal.struct_size = sizeof(journal);
  journal.root = view(root);
  journal.maximum_records = options.maximum_records;
  const std::string runnable = "facman.instance:endurance";
  std::vector<char> last_run(8192U);
  ulk_session_lookup_status_v1 lookup = ULK_SESSION_LOOKUP_NOT_FOUND;
  ulk_size required = 0U;
  ulk_error_v1 journal_error;
  initialize_error(journal_error);
  const int last_status = ulk_session_journal_last_run_v1(
      &journal, view(runnable), &lookup, last_run.data(),
      static_cast<ulk_size>(last_run.size()), &required, &journal_error);
  const bool latest_matches =
      last_status == ULK_STATUS_OK && lookup == ULK_SESSION_LOOKUP_FOUND &&
      !audit.newest_session.empty() &&
      std::string(last_run.data()).find(audit.newest_session) !=
          std::string::npos;
  const bool lock_reacquired = last_status == ULK_STATUS_OK;
  const bool passed =
      elapsed >= static_cast<double>(options.minimum_seconds) &&
      admissions >= options.admissions && terminal_writes == admissions &&
      write_failures == 0U && reader_failures == 0U &&
      reopen_cycles >= options.reopen_cycles &&
      audit.records == options.maximum_records &&
      audit.v2_records == audit.records &&
      audit.terminal_records == audit.records &&
      audit.duplicate_commit_orders == 0U && latest_matches && lock_reacquired;

  std::ofstream output(options.output, std::ios::binary | std::ios::trunc);
  output << "{\n"
         << "  \"schema\": \"facman.ulk_session_journal_endurance.v1\",\n"
         << "  \"status\": \"" << (passed ? "pass" : "fail") << "\",\n"
         << "  \"elapsed_seconds\": " << std::fixed << std::setprecision(3)
         << elapsed << ",\n"
         << "  \"root\": \"" << json_escape(root) << "\",\n"
         << "  \"writers\": " << options.writers << ",\n"
         << "  \"readers\": " << options.readers << ",\n"
         << "  \"admissions\": " << admissions.load() << ",\n"
         << "  \"same_second_admissions\": " << admissions.load() << ",\n"
         << "  \"terminal_writes\": " << terminal_writes.load() << ",\n"
         << "  \"write_failures\": " << write_failures.load() << ",\n"
         << "  \"contention_retries\": " << contention_retries.load() << ",\n"
         << "  \"reader_calls\": " << reader_calls.load() << ",\n"
         << "  \"reader_failures\": " << reader_failures.load() << ",\n"
         << "  \"reopen_cycles\": " << reopen_cycles.load() << ",\n"
         << "  \"retained_records\": " << audit.records << ",\n"
         << "  \"terminal_retained_records\": " << audit.terminal_records
         << ",\n"
         << "  \"v2_retained_records\": " << audit.v2_records << ",\n"
         << "  \"duplicate_commit_orders\": " << audit.duplicate_commit_orders
         << ",\n"
         << "  \"maximum_commit_order\": " << audit.maximum_commit_order
         << ",\n"
         << "  \"latest_matches_maximum_commit_order\": "
         << (latest_matches ? "true" : "false") << ",\n"
         << "  \"lock_reacquired_after_campaign\": "
         << (lock_reacquired ? "true" : "false") << "\n"
         << "}\n";
  output.close();
  fs::remove_all(options.root, error);
  return passed ? 0 : 1;
}
