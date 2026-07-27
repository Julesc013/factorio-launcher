// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_evidence_io.h"

#include "fl_file_io.h"

#include <chrono>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

namespace {

std::uint64_t positive_integer(const char* value, const char* name)
{
    try {
        const std::string text(value);
        std::size_t consumed = 0;
        const unsigned long long parsed =
            std::stoull(text, &consumed, 10);
        if (consumed != text.size() || parsed == 0) {
            throw std::runtime_error("not positive");
        }
        return static_cast<std::uint64_t>(parsed);
    } catch (const std::exception&) {
        throw std::runtime_error(
            std::string(name) + " is not a positive integer");
    }
}

std::string read_standard_input(std::uint64_t maximum_bytes)
{
    std::string value;
    value.reserve(static_cast<std::size_t>(
        std::min<std::uint64_t>(maximum_bytes, 1024U * 1024U)));
    char buffer[64U * 1024U];
    while (std::cin.good()) {
        std::cin.read(buffer, sizeof(buffer));
        const std::streamsize count = std::cin.gcount();
        if (count <= 0) {
            break;
        }
        const std::uint64_t observed =
            static_cast<std::uint64_t>(value.size());
        const std::uint64_t incoming =
            static_cast<std::uint64_t>(count);
        if (observed > maximum_bytes ||
            incoming > maximum_bytes - observed) {
            throw std::runtime_error(
                "standard input exceeds the native evidence byte budget");
        }
        value.append(buffer, static_cast<std::size_t>(count));
    }
    return value;
}

int self_test(const std::filesystem::path& parent)
{
    namespace fs = std::filesystem;
    const auto nonce =
        std::chrono::steady_clock::now().time_since_epoch().count();
    const fs::path root =
        fs::absolute(parent) /
        ("facman-evidence-probe-" + std::to_string(nonce));
    std::error_code error;
    fs::create_directories(root, error);
    if (error) {
        throw std::runtime_error(
            "self-test root could not be created: " + error.message());
    }
    const std::string first =
        "{\"schema\":\"facman.evidence_probe_test.v1\",\"value\":1}\n";
    const std::string second =
        "{\"schema\":\"facman.evidence_probe_test.v1\",\"value\":2}\n";
    facman::play_evidence::ProbeRequest request;
    request.operation = "write_new_durable";
    request.destination = root / "record.json";
    request.maximum_bytes = 4096;
    auto result =
        facman::play_evidence::execute_probe_request(request, first);
    if (!result) return 10;
    const auto substituted_output =
        facman::play_evidence::execute_probe_request(request, first);
    if (substituted_output) return 11;

    request = {};
    request.operation = "read_bounded_json";
    request.source = root / "record.json";
    request.maximum_bytes = 4096;
    result = facman::play_evidence::execute_probe_request(request, "");
    if (!result) return 12;

    request.operation = "read_bounded_text";
    result = facman::play_evidence::execute_probe_request(request, "");
    if (!result) return 13;

    request = {};
    request.operation = "capture_directory_manifest";
    request.source = root;
    request.maximum_entries = 32;
    request.maximum_total_bytes = 1024U * 1024U;
    request.maximum_entry_bytes = 1024U * 1024U;
    request.maximum_depth = 8;
    result = facman::play_evidence::execute_probe_request(request, "");
    if (!result) return 14;

    request = {};
    request.operation = "replace_durable";
    request.destination = root / "record.json";
    request.maximum_bytes = 4096;
    result =
        facman::play_evidence::execute_probe_request(request, second);
    if (!result) return 15;

    fs::create_directory(root / "copied", error);
    if (error) return 16;
    request = {};
    request.operation = "copy_file_durable";
    request.source = root / "record.json";
    request.destination = root / "copied" / "record.json";
    request.maximum_bytes = 4096;
    result = facman::play_evidence::execute_probe_request(request, "");
    if (!result) return 17;

    request = {};
    request.operation = "inspect_zip";
    request.source =
        facman::platform::path_from_utf8(FACMAN_TEST_SOURCE_ROOT) /
        "tests" / "fixtures" / "factorio_mods" / "valid_simple" /
        "simple_mod_1.0.0.zip";
    request.maximum_bytes = 1024U * 1024U;
    request.maximum_entries = 8;
    request.maximum_total_bytes = 1024U * 1024U;
    request.maximum_entry_bytes = 1024U * 1024U;
    request.maximum_depth = 8;
    request.maximum_ratio = 100;
    request.maximum_elapsed_ms = 30000;
    result = facman::play_evidence::execute_probe_request(request, "");
    if (!result) return 18;

    request.operation = "inspect_exact_member";
    request.member = "simple_mod_1.0.0/info.json";
    result = facman::play_evidence::execute_probe_request(request, "");
    if (!result) return 19;

    fs::create_directory(root / "extracted", error);
    if (error) return 20;
    request.operation = "extract_exact_member";
    request.destination = root / "extracted" / "record.json";
    result = facman::play_evidence::execute_probe_request(request, "");
    if (!result) return 21;

    request = {};
    request.operation = "hash_file";
    request.source = root / "extracted" / "record.json";
    request.maximum_bytes = 4096;
    result = facman::play_evidence::execute_probe_request(request, "");
    if (!result) return 22;

    const auto resources =
        facman::play_evidence::resource_revalidation_self_test(root);
    if (!resources) return 23;

    std::cout << "facman-evidence-probe-self-test: pass\n";
    return 0;
}

void usage()
{
    std::cerr
        << "Usage:\n"
        << "  facman_evidence_probe inspect-file <path> <max-bytes>\n"
        << "  facman_evidence_probe read-bounded-json <path> <max-bytes>\n"
        << "  facman_evidence_probe read-bounded-text <path> <max-bytes>\n"
        << "  facman_evidence_probe hash-file <path> <max-bytes>\n"
        << "  facman_evidence_probe inspect-directory <path>\n"
        << "  facman_evidence_probe capture-directory-manifest <path> "
           "<max-entries> <max-total-bytes> <max-entry-bytes> <max-depth>\n"
        << "  facman_evidence_probe write-new-durable <path> <max-bytes>\n"
        << "  facman_evidence_probe replace-durable <path> <max-bytes>\n"
        << "  facman_evidence_probe copy-file-durable <source> "
           "<destination> <max-bytes>\n"
        << "  facman_evidence_probe revalidate-resource-specification "
           "<preflight> <preflight-digest> <resource-set-digest>\n"
        << "  facman_evidence_probe inspect-zip <path> <max-archive-bytes> "
           "<max-entries> <max-total-bytes> <max-entry-bytes> <max-depth> "
           "<max-ratio> <max-elapsed-ms>\n"
        << "  facman_evidence_probe inspect-exact-member <archive> <member> "
           "<max-archive-bytes> <max-entries> <max-total-bytes> "
           "<max-entry-bytes> <max-depth> <max-ratio> <max-elapsed-ms>\n"
        << "  facman_evidence_probe extract-exact-member <archive> <member> "
           "<destination> <max-archive-bytes> <max-entries> "
           "<max-total-bytes> <max-entry-bytes> <max-depth> <max-ratio> "
           "<max-elapsed-ms>\n";
    std::cerr
        << "  facman_evidence_probe --self-test <temporary-parent>\n";
}

} // namespace

int main(int argc, char** argv)
{
    try {
        if (argc < 2) {
            usage();
            return 2;
        }
        facman::play_evidence::ProbeRequest request;
        const std::string command(argv[1]);
        if (command == "--self-test" && argc == 3) {
            return self_test(
                facman::platform::path_from_utf8(argv[2]));
        }
        std::string standard_input;
        if ((command == "inspect-file" ||
             command == "read-bounded-json" ||
             command == "read-bounded-text" ||
             command == "hash-file") &&
            argc == 4) {
            request.operation =
                command == "inspect-file"
                ? "inspect_file"
                : command == "read-bounded-json"
                    ? "read_bounded_json"
                    : command == "read-bounded-text"
                        ? "read_bounded_text"
                    : "hash_file";
            request.source =
                facman::platform::path_from_utf8(argv[2]);
            request.maximum_bytes =
                positive_integer(argv[3], "max-bytes");
        } else if (
            command == "inspect-directory" && argc == 3) {
            request.operation = "inspect_directory";
            request.source =
                facman::platform::path_from_utf8(argv[2]);
        } else if (
            command == "capture-directory-manifest" && argc == 7) {
            request.operation = "capture_directory_manifest";
            request.source =
                facman::platform::path_from_utf8(argv[2]);
            request.maximum_entries =
                positive_integer(argv[3], "max-entries");
            request.maximum_total_bytes =
                positive_integer(argv[4], "max-total-bytes");
            request.maximum_entry_bytes =
                positive_integer(argv[5], "max-entry-bytes");
            request.maximum_depth =
                positive_integer(argv[6], "max-depth");
        } else if (
            (command == "write-new-durable" ||
             command == "replace-durable") &&
            argc == 4) {
            request.operation =
                command == "write-new-durable"
                ? "write_new_durable"
                : "replace_durable";
            request.destination =
                facman::platform::path_from_utf8(argv[2]);
            request.maximum_bytes =
                positive_integer(argv[3], "max-bytes");
            standard_input = read_standard_input(request.maximum_bytes);
        } else if (
            command == "copy-file-durable" && argc == 5) {
            request.operation = "copy_file_durable";
            request.source =
                facman::platform::path_from_utf8(argv[2]);
            request.destination =
                facman::platform::path_from_utf8(argv[3]);
            request.maximum_bytes =
                positive_integer(argv[4], "max-bytes");
        } else if (
            command == "revalidate-resource-specification" &&
            argc == 5) {
            request.operation =
                "revalidate_resource_specification";
            request.source =
                facman::platform::path_from_utf8(argv[2]);
            request.member = argv[3];
            standard_input = argv[4];
        } else if (command == "inspect-zip" && argc == 10) {
            request.operation = "inspect_zip";
            request.source =
                facman::platform::path_from_utf8(argv[2]);
            request.maximum_bytes =
                positive_integer(argv[3], "max-archive-bytes");
            request.maximum_entries =
                positive_integer(argv[4], "max-entries");
            request.maximum_total_bytes =
                positive_integer(argv[5], "max-total-bytes");
            request.maximum_entry_bytes =
                positive_integer(argv[6], "max-entry-bytes");
            request.maximum_depth =
                positive_integer(argv[7], "max-depth");
            request.maximum_ratio =
                positive_integer(argv[8], "max-ratio");
            request.maximum_elapsed_ms =
                positive_integer(argv[9], "max-elapsed-ms");
        } else if (
            command == "inspect-exact-member" && argc == 11) {
            request.operation = "inspect_exact_member";
            request.source =
                facman::platform::path_from_utf8(argv[2]);
            request.member = argv[3];
            request.maximum_bytes =
                positive_integer(argv[4], "max-archive-bytes");
            request.maximum_entries =
                positive_integer(argv[5], "max-entries");
            request.maximum_total_bytes =
                positive_integer(argv[6], "max-total-bytes");
            request.maximum_entry_bytes =
                positive_integer(argv[7], "max-entry-bytes");
            request.maximum_depth =
                positive_integer(argv[8], "max-depth");
            request.maximum_ratio =
                positive_integer(argv[9], "max-ratio");
            request.maximum_elapsed_ms =
                positive_integer(argv[10], "max-elapsed-ms");
        } else if (
            command == "extract-exact-member" && argc == 12) {
            request.operation = "extract_exact_member";
            request.source =
                facman::platform::path_from_utf8(argv[2]);
            request.member = argv[3];
            request.destination =
                facman::platform::path_from_utf8(argv[4]);
            request.maximum_bytes =
                positive_integer(argv[5], "max-archive-bytes");
            request.maximum_entries =
                positive_integer(argv[6], "max-entries");
            request.maximum_total_bytes =
                positive_integer(argv[7], "max-total-bytes");
            request.maximum_entry_bytes =
                positive_integer(argv[8], "max-entry-bytes");
            request.maximum_depth =
                positive_integer(argv[9], "max-depth");
            request.maximum_ratio =
                positive_integer(argv[10], "max-ratio");
            request.maximum_elapsed_ms =
                positive_integer(argv[11], "max-elapsed-ms");
        } else {
            usage();
            return 2;
        }
        auto result = facman::play_evidence::execute_probe_request(
            request, standard_input);
        if (!result) {
            std::cout << facman::play_evidence::error_record_json(
                request.operation, result.error()) << '\n';
            return 3;
        }
        std::cout << result.value() << '\n';
        return 0;
    } catch (const std::exception& exception) {
        facman::core::Error error(
            "evidence_io_invalid_request",
            exception.what(),
            argc > 1 ? argv[1] : "",
            facman::core::OutcomeKind::invalid_argument);
        std::cout << facman::play_evidence::error_record_json(
            argc > 1 ? argv[1] : "", error) << '\n';
        return 2;
    }
}
