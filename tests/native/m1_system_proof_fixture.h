// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_TESTS_M1_SYSTEM_PROOF_FIXTURE_H
#define FACMAN_TESTS_M1_SYSTEM_PROOF_FIXTURE_H

#include "usk_lifecycle.h"
#include "ulk/ulk_setup_handoff.h"

#include <filesystem>
#include <string>
#include <vector>

namespace facman::tests::m1 {

struct SyntheticArchive {
    std::filesystem::path path;
    std::vector<usk::lifecycle::PayloadFile> payload;
};

struct Fixture {
    std::filesystem::path root;
    std::filesystem::path workspace;
    usk::lifecycle::LifecycleRoots setup_roots;

    Fixture();
    ~Fixture();
    Fixture(const Fixture&) = delete;
    Fixture& operator=(const Fixture&) = delete;
};

SyntheticArchive make_factorio_archive(const std::filesystem::path& root);
usk::lifecycle::RecipeBinding factorio_recipe(
    const std::string& recipe_digest,
    const std::string& archive_digest);
ulk_string_view view(const std::string& value);
std::string text(ulk_string_view value);
void write_text(const std::filesystem::path& path, const std::string& value);

} // namespace facman::tests::m1

#endif
