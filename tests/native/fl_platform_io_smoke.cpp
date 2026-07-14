// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_file_io.h"
#include "fl_system_services.h"
#include "fl_user_paths.h"

#include <filesystem>
#include <iostream>
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
