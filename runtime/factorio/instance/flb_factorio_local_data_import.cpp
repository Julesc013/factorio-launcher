// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_local_data_import.h"

#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <sstream>
#include <system_error>

namespace facman::factorio::instance {
namespace fs = std::filesystem;

namespace {
constexpr std::uint64_t kMaximumFiles = 100000;
constexpr std::uint64_t kMaximumBytes = 16ULL * 1024ULL * 1024ULL * 1024ULL;
constexpr std::size_t kMaximumDepth = 32;

facman::core::Result<LocalDataImportReport> failure(
    const std::string& code,
    const std::string& message,
    const fs::path& path)
{
    return facman::core::Result<LocalDataImportReport>::failure(
        {code, message, facman::platform::path_to_utf8(path)});
}

bool add_domain(std::vector<std::string>& domains, const std::string& domain)
{
    if (std::find(domains.begin(), domains.end(), domain) != domains.end()) return false;
    domains.push_back(domain);
    return true;
}

facman::core::Result<LocalDataImportReport> copy_stable_file(
    const fs::path& source,
    const fs::path& destination,
    LocalDataImportReport report)
{
    if (report.file_count >= kMaximumFiles) {
        return failure("local_data_import_budget_exceeded", "Local player-data file budget exceeded", source);
    }
    std::string link_detail;
    if (facman::base::path_crosses_link_or_reparse_point(source, link_detail)) {
        return failure("local_data_import_link_refused", "Local player-data import encountered a link or reparse point", source);
    }
    facman::platform::StableInputFile input;
    facman::platform::IoStatus opened = input.open_no_follow(source);
    if (!opened.ok() || !input.identity().regular_file) {
        return failure("local_data_import_read_refused", "Local player-data source is not a stable regular file", source);
    }
    if (input.size() > kMaximumBytes - report.byte_count) {
        return failure("local_data_import_budget_exceeded", "Local player-data byte budget exceeded", source);
    }
    std::error_code error;
    fs::create_directories(destination.parent_path(), error);
    if (error) return failure("local_data_import_write_refused", "Import destination could not be created", destination.parent_path());
    facman::platform::DurableOutputFile output;
    facman::platform::IoStatus created = output.create_exclusive(destination, input.size());
    if (!created.ok()) return failure("local_data_import_write_refused", "Import destination could not be created exclusively", destination);
    std::array<unsigned char, 64U * 1024U> buffer {};
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t requested = static_cast<std::size_t>(
            std::min<std::uint64_t>(buffer.size(), input.size() - offset));
        const std::size_t read = input.read_at(offset, buffer.data(), requested);
        if (read != requested || output.write_at(offset, buffer.data(), read) != read) {
            return failure("local_data_import_copy_failed", "Local player-data could not be copied completely", source);
        }
        offset += read;
    }
    const facman::platform::IoStatus unchanged = input.revalidate();
    if (!unchanged.ok()) return failure("local_data_import_source_changed", "Local player-data changed during import", source);
    const facman::platform::IoStatus flushed = output.flush_file_and_parent();
    if (!flushed.ok()) return failure("local_data_import_flush_failed", "Imported player-data could not be durably flushed", destination);
    ++report.file_count;
    report.byte_count += input.size();
    return facman::core::Result<LocalDataImportReport>::success(std::move(report));
}

facman::core::Result<LocalDataImportReport> copy_directory(
    const fs::path& source,
    const fs::path& destination,
    LocalDataImportReport report)
{
    std::error_code error;
    const fs::file_status source_status = fs::symlink_status(source, error);
    if ((!error && source_status.type() == fs::file_type::not_found) ||
        error == std::errc::no_such_file_or_directory) {
        return facman::core::Result<LocalDataImportReport>::success(std::move(report));
    }
    if (error) return failure("local_data_import_read_refused", "Local player-data directory could not be inspected", source);
    std::string link_detail;
    if (!fs::is_directory(source_status) ||
        facman::base::path_crosses_link_or_reparse_point(source, link_detail)) {
        return failure("local_data_import_link_refused", "Local player-data directory is unsafe", source);
    }
    fs::create_directories(destination, error);
    if (error) return failure("local_data_import_write_refused", "Import destination could not be created", destination);
    fs::recursive_directory_iterator iterator(source, fs::directory_options::none, error), end;
    for (; !error && iterator != end; iterator.increment(error)) {
        if (static_cast<std::size_t>(iterator.depth()) > kMaximumDepth) {
            return failure("local_data_import_budget_exceeded", "Local player-data nesting budget exceeded", iterator->path());
        }
        const fs::path relative = iterator->path().lexically_relative(source);
        if (relative.empty() || relative.is_absolute()) {
            return failure("local_data_import_path_refused", "Local player-data relative path is invalid", iterator->path());
        }
        const fs::file_status status = iterator->symlink_status(error);
        if (error) break;
        if (facman::base::path_crosses_link_or_reparse_point(iterator->path(), link_detail)) {
            return failure("local_data_import_link_refused", "Local player-data import encountered a link or reparse point", iterator->path());
        }
        const fs::path target = destination / relative;
        if (fs::is_directory(status)) {
            fs::create_directories(target, error);
            if (error) break;
        } else if (fs::is_regular_file(status)) {
            auto copied = copy_stable_file(iterator->path(), target, std::move(report));
            if (!copied) return copied;
            report = copied.take_value();
        } else {
            return failure("local_data_import_file_type_refused", "Local player-data contains an unsupported file type", iterator->path());
        }
    }
    if (error) return failure("local_data_import_read_refused", "Local player-data traversal failed", source);
    return facman::core::Result<LocalDataImportReport>::success(std::move(report));
}

facman::core::Result<LocalDataImportReport> copy_named_file(
    const fs::path& source,
    const fs::path& destination,
    LocalDataImportReport report,
    const char* domain)
{
    std::error_code error;
    const fs::file_status status = fs::symlink_status(source, error);
    if ((!error && status.type() == fs::file_type::not_found) ||
        error == std::errc::no_such_file_or_directory) {
        return facman::core::Result<LocalDataImportReport>::success(std::move(report));
    }
    if (error || !fs::is_regular_file(status)) {
        return failure("local_data_import_read_refused", "Local player-data file could not be inspected", source);
    }
    auto copied = copy_stable_file(source, destination, std::move(report));
    if (copied) add_domain(copied.value().imported_domains, domain);
    return copied;
}
}

facman::core::Result<LocalDataImportReport> import_local_player_data(
    const fs::path& source_install_root,
    const fs::path& staging_instance_root)
{
    std::string link_detail;
    if (facman::base::path_crosses_link_or_reparse_point(source_install_root, link_detail)) {
        return failure("local_data_import_link_refused", "Selected installation root is linked or substituted", source_install_root);
    }
    LocalDataImportReport report;
    const struct { const char* source; const char* destination; const char* domain; } directories[] = {
        {"mods", "mods", "mods"}, {"saves", "saves", "saves"},
        {"scenarios", "scenarios", "scenarios"}, {"script-output", "script-output", "script_output"},
        {"config", "imports/source-config", "source_config"},
    };
    for (const auto& domain : directories) {
        const std::uint64_t before = report.file_count;
        auto copied = copy_directory(
            source_install_root / domain.source,
            staging_instance_root / domain.destination,
            std::move(report));
        if (!copied) return copied;
        report = copied.take_value();
        if (report.file_count != before) {
            if (std::string(domain.domain) == "source_config") {
                add_domain(report.preserved_but_inactive_domains, domain.domain);
            } else {
                add_domain(report.imported_domains, domain.domain);
            }
        }
    }
    const struct { const char* source; const char* destination; const char* domain; } files[] = {
        {"player-data.json", "player-data.json", "player_data"},
        {"achievements.dat", "achievements.dat", "achievements"},
        {"crop-cache.dat", "cache/imported-crop-cache.dat", "cache"},
        {"factorio-current.log", "logs/imported-factorio-current.log", "logs"},
        {"factorio-previous.log", "logs/imported-factorio-previous.log", "logs"},
    };
    for (const auto& domain : files) {
        auto copied = copy_named_file(
            source_install_root / domain.source,
            staging_instance_root / domain.destination,
            std::move(report),
            domain.domain);
        if (!copied) return copied;
        report = copied.take_value();
    }
    std::error_code error;
    if (fs::exists(source_install_root / "temp", error) && !error) {
        report.skipped_volatile_domains.push_back("temp");
    }
    facman::core::json::ArrayBuilder imported;
    for (const std::string& domain : report.imported_domains) imported.add_string(domain);
    facman::core::json::ArrayBuilder inactive;
    for (const std::string& domain : report.preserved_but_inactive_domains) inactive.add_string(domain);
    facman::core::json::ArrayBuilder skipped;
    for (const std::string& domain : report.skipped_volatile_domains) skipped.add_string(domain);
    facman::core::json::ObjectBuilder manifest;
    manifest.add_string("schema", "factorio.local_data_import.v1");
    manifest.add_string("source_install_root", facman::platform::path_to_utf8(source_install_root.lexically_normal()));
    manifest.add_unsigned_integer("file_count", report.file_count);
    manifest.add_unsigned_integer("byte_count", report.byte_count);
    manifest.add_array("imported_domains", imported);
    manifest.add_array("preserved_but_inactive_domains", inactive);
    manifest.add_array("skipped_volatile_domains", skipped);
    std::string detail;
    if (!facman::base::write_text_new_atomic(
            staging_instance_root / "imports" / "local-data-import.v1.json",
            manifest.serialize() + "\n",
            detail)) {
        return failure("local_data_import_manifest_failed", detail, staging_instance_root / "imports");
    }
    return facman::core::Result<LocalDataImportReport>::success(std::move(report));
}

facman::core::Result<std::string> merge_imported_config_settings(
    const fs::path& source_config,
    const std::string& required_effective_config)
{
    std::error_code error;
    const fs::file_status status = fs::symlink_status(source_config, error);
    if (!error && status.type() == fs::file_type::not_found) {
        return facman::core::Result<std::string>::success(required_effective_config);
    }
    if (error || !fs::is_regular_file(status)) {
        return facman::core::Result<std::string>::failure({
            "local_data_import_config_refused",
            "Imported Factorio configuration is not a regular file",
            facman::platform::path_to_utf8(source_config)});
    }
    facman::platform::StableInputFile input;
    facman::platform::IoStatus opened = input.open_no_follow(source_config);
    constexpr std::uint64_t kMaximumConfigBytes = 4U * 1024U * 1024U;
    if (!opened.ok() || input.size() > kMaximumConfigBytes) {
        return facman::core::Result<std::string>::failure({
            "local_data_import_config_refused",
            "Imported Factorio configuration is unavailable or exceeds 4 MiB",
            facman::platform::path_to_utf8(source_config)});
    }
    std::string source(static_cast<std::size_t>(input.size()), '\0');
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(
            offset,
            source.data() + static_cast<std::size_t>(offset),
            static_cast<std::size_t>(input.size() - offset));
        if (count == 0) {
            return facman::core::Result<std::string>::failure({
                "local_data_import_config_refused",
                "Imported Factorio configuration could not be read completely",
                facman::platform::path_to_utf8(source_config)});
        }
        offset += count;
    }
    if (!input.revalidate().ok()) {
        return facman::core::Result<std::string>::failure({
            "local_data_import_source_changed",
            "Imported Factorio configuration changed during migration",
            facman::platform::path_to_utf8(source_config)});
    }
    const std::size_t other = required_effective_config.find("\n[other]\n");
    const std::string required_paths = other == std::string::npos
        ? required_effective_config
        : required_effective_config.substr(0, other + 1);
    std::ostringstream output;
    output << required_paths;
    std::istringstream lines(source);
    std::string line;
    std::string section;
    bool saw_other = false;
    while (std::getline(lines, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        std::string trimmed = line;
        while (!trimmed.empty() && std::isspace(static_cast<unsigned char>(trimmed.front()))) trimmed.erase(trimmed.begin());
        while (!trimmed.empty() && std::isspace(static_cast<unsigned char>(trimmed.back()))) trimmed.pop_back();
        if (trimmed.size() >= 2 && trimmed.front() == '[' && trimmed.back() == ']') {
            section = trimmed.substr(1, trimmed.size() - 2);
            std::transform(section.begin(), section.end(), section.begin(), [](unsigned char ch) {
                return static_cast<char>(std::tolower(ch));
            });
            if (section == "path") continue;
            output << line << '\n';
            if (section == "other") {
                output << "check_updates=false\n";
                saw_other = true;
            }
            continue;
        }
        if (section == "path") continue;
        std::string lower = trimmed;
        std::transform(lower.begin(), lower.end(), lower.begin(), [](unsigned char ch) {
            return static_cast<char>(std::tolower(ch));
        });
        if (section == "other" && lower.rfind("check_updates", 0) == 0) continue;
        output << line << '\n';
    }
    if (!saw_other) output << "\n[other]\ncheck_updates=false\n";
    return facman::core::Result<std::string>::success(output.str());
}

} // namespace facman::factorio::instance
