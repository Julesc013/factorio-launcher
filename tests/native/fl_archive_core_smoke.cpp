#include "fl_archive.h"
#include "fl_archive_platform.h"
#include "fl_archive_policy.h"

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
    const fs::path staging = root / (force_zip64 ? "writer zip64 staging" :
        method == CompressionMethod::stored ? "writer stored staging" : "writer deflate staging");
    WriteResult result;
    Status status = facman::archive::write_to_new_owned_staging(
        staging,
        "bundle.zip",
        entries,
        options,
        result);
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
        const auto payload = std::find_if(
            result.verified_plan.entries.begin(),
            result.verified_plan.entries.end(),
            [](const facman::archive::Entry& entry) { return !entry.directory && entry.expanded_size != 0; });
        if (payload == result.verified_plan.entries.end()) return 27;
        std::fstream corrupt(result.archive_path, std::ios::binary | std::ios::in | std::ios::out);
        const std::uint64_t corrupt_offset = payload->data_offset + payload->compressed_size / 2;
        corrupt.seekg(static_cast<std::streamoff>(corrupt_offset));
        char byte = 0;
        corrupt.read(&byte, 1);
        byte ^= 0x40;
        corrupt.seekp(static_cast<std::streamoff>(corrupt_offset));
        corrupt.write(&byte, 1);
        corrupt.close();
        const fs::path failed_staging = root / "failed extraction staging";
        status = facman::archive::extract_to_new_owned_staging(
            result.verified_plan,
            failed_staging,
            options.limits);
        if (status.ok() || fs::exists(failed_staging)) {
            std::cerr << "failed-extract-status=" << status.code
                      << " detail=" << status.detail
                      << " staging-exists=" << fs::exists(failed_staging) << "\n";
            return 28;
        }
    }
    return 0;
}

} // namespace

int main()
{
    const int policy = prove_path_policy();
    if (policy != 0) return policy;
    fs::path root = fs::temp_directory_path() / fs::u8path("facman archive unicode-\xE2\x98\x83") /
        std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
    while (root.u8string().size() < 320) {
        root /= "long-path-component-0123456789abcdef";
    }
    std::error_code error;
    fs::create_directories(root, error);
    if (error) return 1;
    int result = prove_writer_and_reader(root, CompressionMethod::stored, false);
    if (result == 0) result = prove_writer_and_reader(root, CompressionMethod::deflate, false);
    if (result == 0) result = prove_writer_and_reader(root, CompressionMethod::deflate, true);
    fs::remove_all(root, error);
    return result;
}
