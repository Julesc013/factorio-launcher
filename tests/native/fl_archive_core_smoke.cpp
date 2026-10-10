// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_archive.h"
#include "fl_archive_platform.h"
#include "fl_archive_policy.h"
#include "fl_file_io.h"
#include "fl_sha256.h"

#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <vector>

namespace fs = std::filesystem;
using facman::archive::CompressionMethod;
using facman::archive::Limits;
using facman::archive::PathKeys;
using facman::archive::Plan;
using facman::archive::Status;
using facman::archive::WriteEntry;
using facman::archive::WriteOptions;
using facman::archive::WriteResult;

namespace {

bool write_file(const fs::path& path, const std::string& text)
{
    std::ofstream output(path, std::ios::binary);
    output << text;
    return static_cast<bool>(output);
}

std::vector<unsigned char> read_file(const fs::path& path)
{
    std::ifstream input(path, std::ios::binary);
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}

int prove_path_policy()
{
    const Limits limits;
    PathKeys keys;
    const std::vector<std::string> refused = {
        "/absolute.txt",
        "C:/drive.txt",
        "../escape.txt",
        "a/./dot.txt",
        "a//empty.txt",
        "a\\backslash.txt",
        "a/stream:name",
        "CON.txt",
        "trailing. ",
    };
    for (const std::string& path : refused) {
        if (facman::archive::validate_archive_path(path, false, limits, keys).ok()) {
            return 10;
        }
    }
    facman::archive::CollisionTracker collisions;
    if (!facman::archive::validate_archive_path("caf\xC3\xA9.txt", false, limits, keys).ok() ||
        !collisions.add(keys, false).ok()) {
        return 11;
    }
    if (!facman::archive::validate_archive_path("cafe\xCC\x81.txt", false, limits, keys).ok() ||
        collisions.add(keys, false).code != "archive_path_unicode_normalization_collision") {
        return 12;
    }
    const Limits mods = facman::archive::ModArchivePolicy::limits();
    const Limits saves = facman::archive::SaveArchivePolicy::limits();
    const Limits transfers = facman::archive::InstanceTransferPolicy::limits();
    const Limits diagnostics = facman::archive::DiagnosticBundlePolicy::limits();
    const Limits packages = facman::archive::PackageArchivePolicy::limits();
    if (mods.maximum_entry_count != 4096 || saves.maximum_entry_count != 2048 ||
        transfers.maximum_total_expanded_bytes != 12ULL * 1024ULL * 1024ULL * 1024ULL ||
        diagnostics.maximum_archive_bytes != 32ULL * 1024ULL * 1024ULL ||
        packages.maximum_entry_count != 100000) {
        return 13;
    }
    return 0;
}

int prove_writer_and_reader(const fs::path& root, CompressionMethod method, bool force_zip64)
{
    const fs::path source = root / (force_zip64 ? "source zip64" : "source");
    fs::create_directories(source);
    if (!write_file(source / fs::u8path("payload-\xE2\x98\x83.txt"), "streamed payload\n") ||
        !write_file(source / "empty.txt", "")) {
        return 20;
    }
    std::vector<WriteEntry> entries = {
        {"nested/", {}, true},
        {"nested/payload-\xE2\x98\x83.txt", source / fs::u8path("payload-\xE2\x98\x83.txt"), false},
        {"spaces and unicode/", {}, true},
        {"spaces and unicode/empty.txt", source / "empty.txt", false},
    };
    WriteOptions options;
    options.method = method;
    options.force_zip64 = force_zip64;
    options.reproducible = true;
    const fs::path original_source = source / fs::u8path("payload-\xE2\x98\x83.txt");
    const fs::path retained_source = source / "payload-retained-original.txt";
    bool source_replaced = false;
    options.checkpoint = [&](const char* checkpoint) {
        if (std::string(checkpoint) != "after_sources_opened") return true;
        std::error_code source_error;
        fs::rename(original_source, retained_source, source_error);
        if (source_error || !write_file(original_source, "substituted source bytes\n")) return false;
        source_replaced = true;
        return true;
    };
    const fs::path staging = root / (force_zip64 ? "writer zip64 staging" :
        method == CompressionMethod::stored ? "writer stored staging" : "writer deflate staging");
    WriteResult result;
    Status status = facman::archive::write_to_new_owned_staging(
        staging,
        "bundle.zip",
        entries,
        options,
        result);
    std::error_code source_restore_error;
    if (source_replaced) {
        fs::remove(original_source, source_restore_error);
        source_restore_error.clear();
        fs::rename(retained_source, original_source, source_restore_error);
    }
    options.checkpoint = {};
    if (source_restore_error) return 32;
    if (!status.ok()) return 21;
    if (result.verified_plan.entries.size() != entries.size() ||
        result.verified_plan.zip64 != force_zip64) {
        std::cerr << "entry-count=" << result.verified_plan.entries.size()
                  << " expected=" << entries.size()
                  << " zip64=" << result.verified_plan.zip64
                  << " expected-zip64=" << force_zip64 << "\n";
        return 22;
    }
    for (const auto& entry : result.verified_plan.entries) {
        if (!entry.directory && entry.expanded_size != 0 && entry.method != method) return 23;
    }
    const auto payload = std::find_if(
        result.verified_plan.entries.begin(),
        result.verified_plan.entries.end(),
        [](const facman::archive::Entry& entry) { return !entry.directory && entry.expanded_size != 0; });
    if (payload == result.verified_plan.entries.end()) return 27;

    // The verified plan owns the original object. Replacing the pathname after
    // inspection must not redirect a later stream or extraction to new bytes.
    const fs::path retained_archive = result.archive_path.string() + ".retained-original";
    std::error_code replacement_error;
    fs::rename(result.archive_path, retained_archive, replacement_error);
    if (replacement_error || !write_file(result.archive_path, "substituted archive path\n")) return 29;
    std::string retained_payload;
    status = facman::archive::stream_entry(
        result.verified_plan,
        payload->index,
        options.limits,
        [&](const unsigned char* bytes, std::size_t size) {
            retained_payload.append(reinterpret_cast<const char*>(bytes), size);
            return true;
        });
    fs::remove(result.archive_path, replacement_error);
    replacement_error.clear();
    fs::rename(retained_archive, result.archive_path, replacement_error);
    if (!status.ok() || replacement_error || retained_payload != "streamed payload\n") return 30;

    const fs::path extraction = root / (force_zip64 ? "extract zip64" :
        method == CompressionMethod::stored ? "extract stored" : "extract deflate");
    status = facman::archive::extract_to_new_owned_staging(
        result.verified_plan,
        extraction,
        options.limits);
    if (!status.ok()) return 24;
    if (read_file(extraction / fs::u8path("nested/payload-\xE2\x98\x83.txt")) !=
        read_file(source / fs::u8path("payload-\xE2\x98\x83.txt"))) {
        return 25;
    }

    if (!force_zip64 && method == CompressionMethod::deflate) {
        WriteResult repeat;
        status = facman::archive::write_to_new_owned_staging(
            root / "writer repeat staging",
            "bundle.zip",
            entries,
            options,
            repeat);
        if (!status.ok() || read_file(repeat.archive_path) != read_file(result.archive_path)) {
            return 26;
        }
        const std::uint64_t corrupt_offset = payload->data_offset + payload->compressed_size / 2;
        result.verified_plan.reader.reset();
        std::fstream corrupt(result.archive_path, std::ios::binary | std::ios::in | std::ios::out);
        corrupt.seekg(static_cast<std::streamoff>(corrupt_offset));
        char byte = 0;
        corrupt.read(&byte, 1);
        byte ^= 0x40;
        corrupt.seekp(static_cast<std::streamoff>(corrupt_offset));
        corrupt.write(&byte, 1);
        corrupt.close();
        Plan corrupted_plan;
        status = facman::archive::inspect_archive(result.archive_path, options.limits, corrupted_plan);
        const fs::path failed_staging = root / "failed extraction staging";
        if (status.ok()) {
            status = facman::archive::extract_to_new_owned_staging(
                corrupted_plan,
                failed_staging,
                options.limits);
        }
        if (status.ok() || fs::exists(failed_staging)) {
            std::cerr << "failed-extract-status=" << status.code
                      << " detail=" << status.detail
                      << " staging-exists=" << fs::exists(failed_staging) << "\n";
            return 28;
        }
    }
    return 0;
}

int prove_failed_writer_retention(const fs::path& root)
{
    const fs::path source = root / "failed-writer-source.txt";
    if (!write_file(source, "source remains intact\n")) return 40;
    const auto original = read_file(source);
    for (const bool retain : {false, true}) {
        WriteOptions options;
        options.preserve_staging_on_failure = retain;
        options.limits.maximum_archive_bytes = 1U;
        const fs::path staging = root / (retain ? "retained-writer-failure" : "default-writer-failure");
        WriteResult written;
        const Status status = facman::archive::write_to_new_owned_staging(
            staging, "partial.zip", {{"source.txt", source, false}}, options, written);
        if (status.ok() || read_file(source) != original || fs::exists(staging) != retain) {
            std::cerr << "failed-writer-retention=" << retain << " status=" << status.code << "\n";
            return 41;
        }
        if (retain && !fs::is_regular_file(staging / facman::archive::owned_staging_marker_name())) return 42;
    }
    return 0;
}


int prove_retained_handle_extraction(const fs::path& root)
{
    const std::string payload = "retained exact payload\n";
    const fs::path source = root / "retained-input.bin";
    if (!write_file(source, payload)) return 50;
    WriteOptions options;
    WriteResult written;
    auto status = facman::archive::write_to_new_owned_staging(
        root / "retained-writer", "payload.zip", {{"nested/consumed.txt", source, false}},
        options, written);
    if (!status.ok()) return 51;
    const std::vector<facman::archive::VerifiedEntry> expected = {{
        "nested/consumed.txt", payload.size(),
        facman::base::sha256_hex_bytes(
            reinterpret_cast<const unsigned char*>(payload.data()), payload.size())}};
    const auto exact = [](const fs::path& path, const std::string& value) {
        const auto actual = read_file(path);
        return actual == std::vector<unsigned char>(value.begin(), value.end());
    };
    const fs::path foreign = root / "retained-foreign";
    std::error_code error;
    if (!fs::create_directory(foreign, error) || error ||
        !write_file(foreign / "sentinel", "foreign exact bytes\n")) return 52;
    facman::platform::PathIdentity foreign_before, foreign_after;
    if (!facman::platform::inspect_path_no_follow(foreign, foreign_before).ok()) return 52;
    const auto foreign_unchanged = [&]() {
        std::error_code inventory_error;
        fs::directory_iterator entries(foreign, inventory_error);
        if (inventory_error) return false;
        unsigned count = 0;
        for (const auto& entry : entries) {
            ++count;
            if (entry.path().filename() != "sentinel" ||
                !entry.is_regular_file(inventory_error) || inventory_error) return false;
        }
        return count == 1U && exact(foreign / "sentinel", "foreign exact bytes\n");
    };
    const fs::path staging = root / "retained-extracted";
    unsigned attempts = 0;
    facman::archive::ExtractionObservation observation;
    status = facman::archive::extract_verified_to_new_retained_staging(
        written.verified_plan, staging, options.limits, expected,
        [&](std::uint32_t, const char* phase) {
#ifdef _WIN32
            const std::string name = phase;
            fs::path target;
            if (name == "root_created") target = staging;
            else if (name == "directory_created") target = staging / "nested";
            else if (name == "output_created") target = staging / "nested" / "consumed.txt";
            else return true;
            std::error_code inspection_error;
            const bool correct_type = name == "output_created" ?
                fs::is_regular_file(target, inspection_error) :
                fs::is_directory(target, inspection_error);
            if (inspection_error || !correct_type) return false;
            ++attempts;
            std::error_code rename_error;
            const fs::path displaced = root / ("displaced-" + name);
            fs::rename(target, displaced, rename_error);
            return (rename_error.value() == 32 || rename_error.value() == 5) &&
                fs::exists(target) && !fs::exists(displaced) && foreign_unchanged();
#else
            (void)phase;
            return true;
#endif
        }, &observation);
    if (!status.ok() || !observation.effects_possible() ||
        !exact(staging / "nested" / "consumed.txt", payload) ||
        !exact(staging / facman::archive::owned_staging_marker_name(),
            "schema=facman.archive_staging.v1\n") ||
        !facman::platform::inspect_path_no_follow(foreign, foreign_after).ok() ||
        !foreign_before.same_object(foreign_after) || !foreign_unchanged()) return 53;
#ifdef _WIN32
    if (attempts != 3U) return 53;
#else
    (void)attempts;
#endif
    for (const char* phase : {"root_created", "directory_created", "output_created"}) {
        const fs::path partial = root / (std::string("partial-") + phase);
        facman::archive::ExtractionObservation interrupted;
        status = facman::archive::extract_verified_to_new_retained_staging(
            written.verified_plan, partial, options.limits, expected,
            [&](std::uint32_t, const char* current) { return std::string(current) != phase; },
            &interrupted);
        if (status.code != "archive_extract_fault_injected" ||
            !interrupted.effects_possible() || !fs::is_directory(partial)) return 54;
        if (std::string(phase) == "output_created" &&
            (!fs::is_regular_file(partial / "nested" / "consumed.txt") ||
                fs::file_size(partial / "nested" / "consumed.txt") != 0U)) return 54;
    }
    auto wrong = expected;
    wrong[0].sha256 = std::string(64, '0');
    const fs::path corrupt = root / "retained-wrong-digest";
    status = facman::archive::extract_verified_to_new_retained_staging(
        written.verified_plan, corrupt, options.limits, wrong);
    if (status.code != "archive_consumed_digest_mismatch" ||
        !exact(corrupt / "nested" / "consumed.txt", payload)) return 55;
    status = facman::archive::extract_verified_to_new_retained_staging(
        written.verified_plan, foreign, options.limits, expected);
    if (status.code != "archive_staging_root_exists" ||
        !exact(foreign / "sentinel", "foreign exact bytes\n")) return 55;

    std::vector<std::string> names = {
        "with spaces.txt", "caf\xC3\xA9.txt", "cafe\xCC\x81.txt", "emoji-\xF0\x9F\x98\x80.txt"};
#ifdef _WIN32
    std::string multibyte;
    for (unsigned i = 0; i < 100U; ++i) multibyte += "\xE4\xB8\xAD";
    if (multibyte.size() <= 255U) return 56;
    names.push_back(multibyte);
#endif
    std::vector<WriteEntry> entries;
    for (std::size_t i = 0; i < names.size(); ++i)
        entries.push_back({"caf\xC3\xA9 folder/" + std::to_string(i) + "/" + names[i], source, false});
    WriteResult unicode;
    status = facman::archive::write_to_new_owned_staging(
        root / "retained-unicode-writer", "unicode.zip", entries, options, unicode);
    if (!status.ok()) return 56;
    std::vector<facman::archive::VerifiedEntry> unicode_expected;
    for (const auto& entry : unicode.verified_plan.entries)
        unicode_expected.push_back({entry.path, payload.size(), expected[0].sha256});
    const fs::path unicode_root = root / "retained-unicode-extracted";
    status = facman::archive::extract_verified_to_new_retained_staging(
        unicode.verified_plan, unicode_root, options.limits, unicode_expected);
    if (!status.ok()) return 57;
    for (const auto& entry : unicode.verified_plan.entries)
        if (!exact(unicode_root / fs::u8path(entry.path), payload)) return 57;
    const fs::path api_root = root / "retained-utf8-api";
    if (!fs::create_directory(api_root, error) || error) return 58;
    facman::platform::StableDirectoryObject api;
    if (!api.open_no_follow_for_relative_writes(api_root).ok()) return 58;
    const std::vector<std::string> invalid = {"", ".", "..", "a/b", "a\\b", "a:b",
        std::string("a\0b", 3), "\xC0\xAF", "\xED\xA0\x80", "\xF4\x90\x80\x80", "\xE2\x82", "\x80"};
    for (const auto& name : invalid) {
        facman::platform::DurableOutputFile file;
        facman::platform::StableDirectoryObject directory;
        if (api.create_child_file_exclusive_utf8(name, 10U, file).code != "relative_leaf_invalid" ||
            api.create_child_directory_exclusive_utf8(name, directory).code != "relative_leaf_invalid") return 58;
    }
    if (!fs::is_empty(api_root)) return 58;
    for (const auto& name : names) {
        facman::platform::DurableOutputFile file;
        facman::platform::StableDirectoryObject directory;
        if (api.create_child_file_exclusive(fs::u8path(name), 10U, file).code != "relative_leaf_invalid" ||
            api.create_child_directory_exclusive(fs::u8path(name), directory).code != "relative_leaf_invalid") return 59;
    }
    if (!fs::is_empty(api_root)) return 59;
    return 0;
}

} // namespace

int main()
{
    const int policy = prove_path_policy();
    if (policy != 0) return policy;
    std::error_code error;
    fs::path temporary_root = fs::temp_directory_path(error);
    if (error) return 1;
    temporary_root = fs::canonical(temporary_root, error);
    if (error) return 1;
    fs::path root = temporary_root / fs::u8path("facman archive unicode-\xE2\x98\x83") /
        std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
    while (root.u8string().size() < 320) {
        root /= "long-path-component-0123456789abcdef";
    }
    fs::create_directories(root, error);
    if (error) return 1;
    int result = prove_writer_and_reader(root, CompressionMethod::stored, false);
    if (result == 0) result = prove_writer_and_reader(root, CompressionMethod::deflate, false);
    if (result == 0) result = prove_writer_and_reader(root, CompressionMethod::deflate, true);
    if (result == 0) result = prove_failed_writer_retention(root);
    if (result == 0) result = prove_retained_handle_extraction(root);
    if (result != 0) std::cerr << "archive-core-smoke-stage-code=" << result << "\n";
    fs::remove_all(root, error);
    return result;
}
