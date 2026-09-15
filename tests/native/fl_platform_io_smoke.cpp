// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_file_io.h"
#include "fl_system_services.h"
#include "fl_user_paths.h"

#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>

int main()
{
    namespace fs = std::filesystem;
    const fs::path root = fs::temp_directory_path() / "facman-platform-io-smoke";
    std::error_code error;
    fs::remove_all(root, error);
    fs::create_directory(root, error);
    if (error) return 1;
    const fs::path staging = root / fs::u8path("stable-ß.tmp");
    const fs::path destination = root / fs::u8path("stable-ß.txt");
    facman::platform::DurableOutputFile output;
    auto status = output.create_exclusive(staging, 1024);
    const std::string payload = "durable payload";
    if (!status.ok() || output.write_at(0, payload.data(), payload.size()) != payload.size()) return 2;
    status = output.flush_file_and_parent();
    if (!status.ok() || status.durability == facman::platform::DurabilityLevel::none) return 3;
    status = facman::platform::commit_no_replace(staging, destination);
    if (!status.ok() || status.durability == facman::platform::DurabilityLevel::none) return 4;
    facman::platform::StableInputFile input;
    if (!input.open_no_follow(destination).ok() || input.size() != payload.size()) return 5;
    std::string read(payload.size(), '\0');
    if (input.read_at(0, read.data(), read.size()) != read.size() || read != payload) return 6;
    if (!input.revalidate().ok()) return 7;
    if (!facman::platform::remove_exact_object(destination, input.identity()).ok()) return 8;
    const fs::path pinned_staging = root / "pinned.tmp";
    const fs::path pinned_destination = root / "pinned.txt";
    facman::platform::DurableOutputFile pinned_output;
    status = pinned_output.create_exclusive(pinned_staging, 1024);
    if (!status.ok() ||
        pinned_output.write_at(0, payload.data(), payload.size()) != payload.size() ||
        !pinned_output.publish_no_replace(pinned_destination).ok()) return 18;
    {
        facman::platform::StableInputFile pinned;
        const auto opened_pinned = pinned.open_no_follow_pinned(pinned_destination);
        const auto validated_pinned = opened_pinned.ok()
            ? pinned.revalidate_path()
            : opened_pinned;
        if (!opened_pinned.ok() || !validated_pinned.ok()) {
            std::cerr << "pinned input validation failed: " << opened_pinned.code
                      << ':' << opened_pinned.detail << ' ' << validated_pinned.code
                      << ':' << validated_pinned.detail << '\n';
            return 19;
        }
        const fs::path moved = root / "pinned-moved.txt";
        error.clear();
        fs::rename(pinned_destination, moved, error);
#ifdef _WIN32
        if (!error || !pinned.revalidate_path().ok() || !fs::exists(pinned_destination)) return 20;
#else
        if (error) return 20;
        std::ofstream(pinned_destination, std::ios::binary) << "replacement";
        if (pinned.revalidate_path().ok()) return 21;
        fs::remove(pinned_destination, error);
        error.clear();
        fs::rename(moved, pinned_destination, error);
        if (error) return 22;
#endif
    }
    fs::remove(pinned_destination, error);
    if (error) return 23;
    const fs::path refused_staging = root / "refused.tmp";
    const fs::path foreign_destination = root / "foreign.txt";
    const std::string foreign = "foreign bytes";
    std::ofstream(foreign_destination, std::ios::binary) << foreign;
    facman::platform::DurableOutputFile refused_output;
    status = refused_output.create_exclusive(refused_staging, 1024);
    if (!status.ok() ||
        refused_output.write_at(0, payload.data(), payload.size()) != payload.size() ||
        refused_output.publish_no_replace(foreign_destination).ok()) return 24;
    const auto discarded = refused_output.discard_open();
#ifdef _WIN32
    if (!discarded.ok() || fs::exists(refused_staging)) return 25;
#else
    if (discarded.ok() || !fs::exists(refused_staging)) return 25;
    fs::remove(refused_staging, error);
    if (error) return 26;
#endif
    std::ifstream foreign_input(foreign_destination, std::ios::binary);
    const std::string foreign_after{std::istreambuf_iterator<char>(foreign_input), {}};
    if (foreign_after != foreign) return 27;
#ifdef _WIN32
    const fs::path linked_source = root / "linked-source.zip";
    const fs::path linked_source_alias = root / "linked-source-alias.zip";
    const fs::path linked_launcher = root / "linked-launcher.exe";
    const fs::path linked_launcher_alias = root / "linked-launcher-alias.exe";
    std::ofstream(linked_source, std::ios::binary) << payload;
    std::ofstream(linked_launcher, std::ios::binary) << payload;
    error.clear();
    fs::create_hard_link(linked_source, linked_source_alias, error);
    if (error) return 28;
    fs::create_hard_link(linked_launcher, linked_launcher_alias, error);
    if (error) return 29;
    facman::platform::StableInputFile linked_source_input;
    facman::platform::StableInputFile linked_launcher_input;
    if (linked_source_input.open_no_follow_pinned(linked_source).ok() ||
        linked_launcher_input.open_no_follow_pinned(linked_launcher).ok()) return 30;
#endif
#ifdef _WIN32
    const std::size_t root_length = fs::absolute(root).native().size();
    const std::size_t padding = root_length < 235 ? 235 - root_length : 80;
    const fs::path long_parent = root / std::string(padding, 'p');
    fs::create_directory(long_parent, error);
    if (error) return 12;
    const fs::path long_staging = long_parent / (std::string(70, 's') + ".tmp");
    const fs::path long_destination = long_parent / (std::string(70, 'd') + ".txt");
    if (fs::absolute(long_staging).native().size() <= 260) return 13;
    facman::platform::DurableOutputFile long_output;
    status = long_output.create_exclusive(long_staging, 1024);
    if (!status.ok() || long_output.write_at(0, payload.data(), payload.size()) != payload.size() ||
        !long_output.flush_file_and_parent().ok()) return 14;
    if (!facman::platform::commit_no_replace(long_staging, long_destination).ok()) return 15;
    facman::platform::StableInputFile long_input;
    if (!long_input.open_no_follow(long_destination).ok() ||
        !facman::platform::remove_exact_object(long_destination, long_input.identity()).ok()) return 16;
    fs::remove(long_parent, error);
    if (error) return 17;
#endif
    facman::platform::RandomIdGenerator ids;
    const std::string first = ids.next("tx");
    const std::string second = ids.next("tx");
    if (first == second || first.rfind("tx-", 0) != 0 || first.size() != 35) return 9;
    facman::core::FixedClock fixed("2000-01-01T00:00:00Z");
    if (fixed.now_utc() != "2000-01-01T00:00:00Z") return 10;
    auto paths = facman::platform::user_paths();
    if (!paths || !paths.value().home.is_absolute() || !paths.value().data.is_absolute() ||
        !paths.value().config.is_absolute() || !paths.value().cache.is_absolute() ||
        !paths.value().state.is_absolute()) return 11;
    fs::remove(root, error);
    std::cout << "fl-platform-io-smoke: ok\n";
    return 0;
}
