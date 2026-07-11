#include "fl_archive.h"

#include <filesystem>
#include <iostream>
#include <string>

namespace {

void print_status(const facman::archive::Status& status)
{
    std::cout << (status.ok() ? "ok" : status.code) << "\n";
    if (!status.detail.empty()) std::cerr << status.detail << "\n";
}

} // namespace

int main(int argc, char** argv)
{
    if (argc < 3) return 64;
    facman::archive::Limits limits;
    for (int index = 3; index + 1 < argc; index += 2) {
        const std::string option = argv[index];
        const std::uint64_t value = std::stoull(argv[index + 1]);
        if (option == "--archive") limits.maximum_archive_bytes = value;
        else if (option == "--entries") limits.maximum_entry_count = value;
        else if (option == "--entry-compressed") limits.maximum_entry_compressed_bytes = value;
        else if (option == "--expanded") limits.maximum_total_expanded_bytes = value;
        else if (option == "--entry-expanded") limits.maximum_entry_expanded_bytes = value;
        else if (option == "--ratio") limits.maximum_compression_ratio = value;
        else if (option == "--path") limits.maximum_path_bytes = static_cast<std::size_t>(value);
        else if (option == "--depth") limits.maximum_directory_depth = static_cast<std::size_t>(value);
        else if (option == "--milliseconds") limits.maximum_read_milliseconds = value;
        else return 64;
    }
    facman::archive::Plan plan;
    facman::archive::Status status = facman::archive::inspect_archive(argv[2], limits, plan);
    if (std::string(argv[1]) == "inspect") {
        print_status(status);
        return status.ok() ? 0 : 2;
    }
    if (std::string(argv[1]) == "extract" && argc >= 4) {
        if (!status.ok()) {
            print_status(status);
            return 2;
        }
        status = facman::archive::extract_to_new_owned_staging(plan, argv[3], limits);
        print_status(status);
        return status.ok() ? 0 : 2;
    }
    return 64;
}
