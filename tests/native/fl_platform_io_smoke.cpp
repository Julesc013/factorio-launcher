// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_file_io.h"
#include "fl_system_services.h"

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
    facman::platform::RandomIdGenerator ids;
    const std::string first = ids.next("tx");
    const std::string second = ids.next("tx");
    if (first == second || first.rfind("tx-", 0) != 0 || first.size() != 35) return 9;
    facman::core::FixedClock fixed("2000-01-01T00:00:00Z");
    if (fixed.now_utc() != "2000-01-01T00:00:00Z") return 10;
    fs::remove(root, error);
    std::cout << "fl-platform-io-smoke: ok\n";
    return 0;
}
