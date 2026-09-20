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
#include <utility>

int main()
{
    namespace fs = std::filesystem;
    const fs::path root = fs::temp_directory_path() / "facman-platform-io-smoke";
    std::error_code error;
    fs::remove_all(root, error);
    if (error) return 1;
    fs::create_directory(root, error);
    if (error) return 1;
    const fs::path relative_root = root / "relative";
    fs::create_directory(relative_root, error);
    if (error) return 31;
    {
        facman::platform::StableDirectoryObject root_authority;
        if (!root_authority.open_no_follow_for_relative_writes(relative_root).ok()) return 31;
        facman::platform::StableDirectoryObject bounded;
        facman::platform::StableDirectoryObject duplicate_bounded;
        if (!root_authority.create_child_directory_exclusive("bounded", bounded).ok() ||
            root_authority.create_child_directory_exclusive("bounded", duplicate_bounded).ok()) return 32;
        facman::platform::StableDirectoryObject reopened_bounded;
        facman::platform::DurableOutputFile reopened_output;
        if (!root_authority.open_child_directory_no_follow_for_relative_writes(
                "bounded", reopened_bounded).ok() ||
            !reopened_bounded.create_child_file_exclusive("existing-child.tmp", 1024, reopened_output).ok()) return 56;
        const auto reopened_discarded = reopened_output.discard_open();
#ifdef _WIN32
        if (!reopened_discarded.ok() || fs::exists(bounded.path() / "existing-child.tmp")) return 56;
#else
        if (reopened_discarded.ok() || !fs::exists(bounded.path() / "existing-child.tmp")) return 56;
        fs::remove(bounded.path() / "existing-child.tmp", error);
        if (error) return 56;
#endif
        facman::platform::DurableOutputFile bounded_output;
        const std::string bounded_payload = "handle-relative payload";
        auto bounded_status = bounded.create_child_file_exclusive("staging.tmp", 1024, bounded_output);
        if (!bounded_status.ok() ||
            bounded_output.write_at(0, bounded_payload.data(), bounded_payload.size()) != bounded_payload.size()) return 33;
#ifdef _WIN32
        error.clear();
        fs::rename(bounded.path() / "staging.tmp", bounded.path() / "staging-moved.tmp", error);
        if (!error) return 45;
#endif
        const fs::path decoy_cwd = relative_root / "decoy-cwd";
        fs::create_directory(decoy_cwd, error);
        if (error) return 46;
        const std::string decoy_bytes = "decoy CWD bytes";
        std::ofstream(decoy_cwd / "published.txt", std::ios::binary) << decoy_bytes;
        const fs::path original_cwd = fs::current_path(error);
        if (error) return 47;
        fs::current_path(decoy_cwd, error);
        if (error) return 48;
        bounded_status = bounded_output.publish_sibling_no_replace("published.txt");
        fs::current_path(original_cwd, error);
        if (error) return 49;
        if (!bounded_status.ok()) return 33;
        bounded_status = bounded.flush_metadata();
        if (!bounded_status.ok()) return 33;
        std::ifstream decoy_input(decoy_cwd / "published.txt", std::ios::binary);
        const std::string decoy_after{std::istreambuf_iterator<char>(decoy_input), {}};
        if (decoy_after != decoy_bytes || !fs::exists(bounded.path() / "published.txt")) return 50;
        facman::platform::StableInputFile bounded_input;
        if (!bounded.open_child_file_no_follow_pinned("published.txt", bounded_input).ok() ||
            bounded_input.size() != bounded_payload.size()) return 34;
        std::string bounded_read(bounded_payload.size(), '\0');
        if (bounded_input.read_at(0, bounded_read.data(), bounded_read.size()) != bounded_read.size() ||
            bounded_read != bounded_payload) return 35;
        for (const fs::path& invalid : {fs::path{}, fs::path("."), fs::path(".."), fs::path("a/b"),
             fs::path("a\\b"), fs::path("a:b"), fs::path("name."), fs::path("name "),
             fs::path("CON"), fs::path("NUL.txt"), fs::path("bad<name"), fs::path("bad?name"),
             fs::path(std::string(256, 'x')), fs::path("non-ascii-\xC3\x9F")}) {
            facman::platform::StableInputFile rejected;
            if (bounded.open_child_file_no_follow_pinned(invalid, rejected).ok()) return 36;
        }
        std::ofstream(bounded.path() / "foreign.txt", std::ios::binary) << "foreign relative bytes";
        facman::platform::DurableOutputFile collision;
        if (!bounded.create_child_file_exclusive("collision.tmp", 1024, collision).ok() ||
            collision.write_at(0, bounded_payload.data(), bounded_payload.size()) != bounded_payload.size() ||
            collision.publish_sibling_no_replace("foreign.txt").ok()) return 37;
        const fs::path collision_path = bounded.path() / "collision.tmp";
        if (!fs::exists(collision_path)) return 38;
        const auto collision_discarded = collision.discard_open();
#ifdef _WIN32
        if (!collision_discarded.ok() || fs::exists(collision_path)) return 39;
#else
        if (collision_discarded.ok() || !fs::exists(collision_path)) return 39;
        fs::remove(collision_path, error);
        if (error) return 39;
#endif
        std::ifstream relative_foreign_input(bounded.path() / "foreign.txt", std::ios::binary);
        const std::string relative_foreign{std::istreambuf_iterator<char>(relative_foreign_input), {}};
        if (relative_foreign != "foreign relative bytes") return 40;
        facman::platform::DurableOutputFile faulted_output;
        const fs::path faulted_destination = bounded.path() / "faulted-published.txt";
        if (!bounded.create_child_file_exclusive("faulted-staging.tmp", 1024, faulted_output).ok() ||
            faulted_output.write_at(0, bounded_payload.data(), bounded_payload.size()) != bounded_payload.size()) return 57;
        facman::platform::testing::set_relative_publish_post_rename_fault(true);
        const auto faulted_publish = faulted_output.publish_sibling_no_replace("faulted-published.txt");
        facman::platform::testing::set_relative_publish_post_rename_fault(false);
        if (faulted_publish.code != "output_published_unverified" ||
            faulted_publish.detail.find("output_post_rename_fault_injected: test seam") == std::string::npos ||
            !fs::exists(faulted_destination)) return 57;
        const auto faulted_discard = faulted_output.discard_open();
        if (faulted_discard.code != "output_published_unverified" || !fs::exists(faulted_destination)) return 57;
        fs::remove(faulted_destination, error);
        if (error) return 57;
        facman::platform::DurableOutputFile hardlinked_output;
        const fs::path hardlinked_staging = bounded.path() / "hardlinked.tmp";
        const fs::path hardlinked_alias = bounded.path() / "hardlinked-alias.tmp";
        if (!bounded.create_child_file_exclusive("hardlinked.tmp", 1024, hardlinked_output).ok() ||
            hardlinked_output.write_at(0, bounded_payload.data(), bounded_payload.size()) != bounded_payload.size()) return 51;
        error.clear();
        fs::create_hard_link(hardlinked_staging, hardlinked_alias, error);
        if (!error && hardlinked_output.publish_sibling_no_replace("hardlinked.txt").ok()) return 51;
        const auto hardlinked_discarded = hardlinked_output.discard_open();
#ifdef _WIN32
        if (!error && (!hardlinked_discarded.ok() || fs::exists(hardlinked_staging))) return 51;
#else
        if (!error && (hardlinked_discarded.ok() || !fs::exists(hardlinked_staging))) return 51;
#endif
        if (!error) {
            fs::remove(hardlinked_staging, error);
            if (error) return 51;
            fs::remove(hardlinked_alias, error);
            if (error) return 51;
        }
        facman::platform::DurableOutputFile terminal_output;
        if (!bounded.create_child_file_exclusive("terminal.tmp", 1024, terminal_output).ok() ||
            terminal_output.write_at(0, bounded_payload.data(), bounded_payload.size()) != bounded_payload.size() ||
            !terminal_output.flush_file_and_parent().ok() ||
            !bounded.create_child_file_exclusive("reused.tmp", 1024, terminal_output).ok() ||
            terminal_output.write_at(0, bounded_payload.data(), bounded_payload.size()) != bounded_payload.size()) return 52;
        const auto reused_discarded = terminal_output.discard_open();
#ifdef _WIN32
        if (!reused_discarded.ok() || fs::exists(bounded.path() / "reused.tmp")) return 52;
#else
        if (reused_discarded.ok() || !fs::exists(bounded.path() / "reused.tmp")) return 52;
        fs::remove(bounded.path() / "reused.tmp", error);
        if (error) return 52;
#endif
        facman::platform::DurableOutputFile assigned_output;
        if (!bounded.create_child_file_exclusive("move-replaced.tmp", 1024, assigned_output).ok()) return 53;
        {
            facman::platform::DurableOutputFile incoming_output;
            if (!bounded.create_child_file_exclusive("move-incoming.tmp", 1024, incoming_output).ok()) return 53;
            assigned_output = std::move(incoming_output);
        }
        fs::remove(bounded.path() / "move-replaced.tmp", error);
        if (error) return 53;
        const auto assigned_discarded = assigned_output.discard_open();
#ifdef _WIN32
        if (!assigned_discarded.ok() || fs::exists(bounded.path() / "move-incoming.tmp")) return 53;
#else
        if (assigned_discarded.ok() || !fs::exists(bounded.path() / "move-incoming.tmp")) return 53;
        fs::remove(bounded.path() / "move-incoming.tmp", error);
        if (error) return 53;
#endif
        std::ofstream(bounded.path() / "linked.txt", std::ios::binary) << bounded_payload;
    error.clear();
    fs::create_hard_link(bounded.path() / "linked.txt", bounded.path() / "linked-alias.txt", error);
    if (!error) {
        facman::platform::StableInputFile linked;
        if (bounded.open_child_file_no_follow_pinned("linked.txt", linked).ok()) return 41;
    }
    const fs::path reparse_target = bounded.path() / "reparse-target";
    fs::create_directory(reparse_target, error);
    error.clear();
    fs::create_directory_symlink(reparse_target, bounded.path() / "reparse", error);
    if (!error) {
        facman::platform::StableDirectoryObject reparse;
        if (bounded.open_child_directory_no_follow("reparse", reparse).ok()) return 42;
    }
    const fs::path moved_bounded = relative_root / "bounded-moved";
    error.clear();
    fs::rename(bounded.path(), moved_bounded, error);
    if (!error) {
        fs::create_directory(relative_root / "bounded", error);
        if (error) return 43;
        facman::platform::DurableOutputFile substituted;
        if (bounded.create_child_file_exclusive("must-not-create.tmp", 1024, substituted).ok() ||
            fs::exists(moved_bounded / "must-not-create.tmp") ||
            fs::exists(relative_root / "bounded" / "must-not-create.tmp")) return 44;
    }
    }
    fs::remove_all(relative_root, error);
    if (error) return 54;
    {
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
    }
    fs::remove_all(root, error);
    if (error) return 55;
    std::cout << "fl-platform-io-smoke: ok\n";
    return 0;
}
