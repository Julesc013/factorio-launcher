// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_workspace_store.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_transaction.h"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>

namespace fs = std::filesystem;
using facman::core::InstanceId;
using facman::core::InstallId;
using facman::core::TransactionId;
using facman::workspace::InstallRecord;
using facman::workspace::InstallRepository;
using facman::workspace::InstanceRepository;
using facman::workspace::ModsetRepository;
using facman::workspace::TransactionRepository;
using facman::workspace::WorkspaceLayout;
using facman::workspace::WorkspaceRepository;

namespace {

bool write_file(const fs::path& path, const std::string& text)
{
    std::error_code error;
    fs::create_directories(path.parent_path(), error);
    if (error) return false;
    std::ofstream output(path, std::ios::binary);
    output << text;
    return static_cast<bool>(output);
}

std::string read_file(const fs::path& path)
{
    std::ifstream input(path, std::ios::binary);
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}

bool uuid_v4(const std::string& value)
{
    if (value.size() != 36 || value[8] != '-' || value[13] != '-' || value[18] != '-' || value[23] != '-' ||
        value[14] != '4' || std::string("89ab").find(value[19]) == std::string::npos) return false;
    for (std::size_t index = 0; index < value.size(); ++index) {
        if (index == 8 || index == 13 || index == 18 || index == 23) continue;
        if (std::string("0123456789abcdef").find(value[index]) == std::string::npos) return false;
    }
    return true;
}

std::string install_json(const std::string& id, const fs::path& root)
{
    return "{\"schema\":\"factorio.install_ref.v1\",\"install_id\":\"" + id +
        "\",\"root\":" + facman::core::json::escape_string(facman::platform::path_to_utf8(root)) +
        ",\"executable\":\"factorio.exe\",\"version\":\"2.0\",\"ownership\":\"imported\","
        "\"source\":\"test\",\"platform\":\"windows\",\"verification\":{\"status\":\"structural\"}}";
}

std::string managed_install_json(const std::string& id, const fs::path& root)
{
    return "{\"schema\":\"factorio.install_ref.v1\",\"install_id\":\"" + id +
        "\",\"root\":" + facman::core::json::escape_string(facman::platform::path_to_utf8(root)) +
        ",\"executable\":\"factorio.exe\",\"version\":\"2.0.77\",\"ownership\":\"managed\","
        "\"source\":\"universal-setup\",\"platform\":\"windows\","
        "\"setup_state_ref\":\"state/managed.json\",\"lifecycle_status\":\"active\","
        "\"last_verification_identity\":\"verify-managed\",\"state_revision\":\"revision-managed\","
        "\"verification\":{\"status\":\"structural\"}}";
}

std::string instance_json(const std::string& id, const std::string& install, const std::string& schema = "factorio.instance.v1")
{
    return "{\"schema\":\"" + schema + "\",\"instance_id\":\"" + id +
        "\",\"display_name\":\"Test\",\"install_ref\":\"" + install +
        "\",\"factorio_version\":\"2.0\",\"profile\":\"gui\",\"template\":\"vanilla\"}";
}

int prove_store(const fs::path& root)
{
    WorkspaceLayout layout(root);
    WorkspaceRepository workspaces(layout);
    auto created = workspaces.ensure();
    if (!created || created.value().legacy_local_identity || created.value().id.str() == "local" ||
        !uuid_v4(created.value().id.str())) {
        return 10;
    }
    const std::string stable_id = created.value().id.str();
    auto repeated = workspaces.ensure();
    if (!repeated || repeated.value().id.str() != stable_id) return 11;

    const fs::path install_root = root / "fixture install";
    fs::create_directories(install_root / "data");
    InstallRepository installs(layout);
    InstallRecord install;
    install.id = InstallId::parse("fixture").take_value();
    const std::string install_text = install_json("fixture", install_root);
    auto written = installs.create(install, install_text);
    auto loaded = installs.load(InstallId::parse("fixture").value());
    if (!written || !loaded || loaded.value().root != install_root || loaded.value().legacy_path ||
        loaded.value().verification_status != "structural") return 12;

    InstallRecord managed;
    managed.id = InstallId::parse("managed-fixture").take_value();
    auto managed_written = installs.create(
        managed, managed_install_json("managed-fixture", install_root));
    auto managed_loaded = installs.load(InstallId::parse("managed-fixture").value());
    if (!managed_written || !managed_loaded || managed_loaded.value().ownership != "managed" ||
        managed_loaded.value().setup_state_ref != "state/managed.json" ||
        managed_loaded.value().lifecycle_status != "active" ||
        managed_loaded.value().last_verification_identity != "verify-managed" ||
        managed_loaded.value().state_revision != "revision-managed") return 26;

    auto instance_path = layout.instance_manifest(InstanceId::parse("main").value());
    if (!instance_path || !write_file(instance_path.value(), instance_json("main", "fixture"))) return 13;
    InstanceRepository instances(layout);
    auto instance = instances.load(InstanceId::parse("main").value());
    if (!instance || instance.value().id.str() != "main" || instance.value().install_ref.str() != "fixture" ||
        instance.value().legacy_path) return 14;

    auto legacy_instance_path = layout.legacy_instance_manifest(InstanceId::parse("legacy-instance").value());
    if (!legacy_instance_path || !write_file(
            legacy_instance_path.value(),
            "{\"instance_id\":\"legacy-instance\",\"install_ref\":\"fixture\",\"factorio_version\":\"2.0\"}")) return 15;
    auto legacy_instance = instances.load(InstanceId::parse("legacy-instance").value());
    if (!legacy_instance || !legacy_instance.value().legacy_path) return 16;

    auto future_instance_path = layout.instance_manifest(InstanceId::parse("future").value());
    if (!future_instance_path || !write_file(future_instance_path.value(), instance_json("future", "fixture", "factorio.instance.v2")) ||
        instances.load(InstanceId::parse("future").value())) return 17;

    auto legacy_install_path = layout.legacy_install_ref(InstallId::parse("legacy-install").value());
    const std::string legacy_text = install_json("legacy-install", install_root);
    if (!legacy_install_path || !write_file(legacy_install_path.value(), legacy_text)) return 18;
    auto legacy_install = installs.load(InstallId::parse("legacy-install").value());
    if (!legacy_install || !legacy_install.value().legacy_path) return 19;
    auto inspected = workspaces.inspect_migration();
    auto planned = workspaces.plan_migration();
    if (!inspected || !planned || inspected.value().actions.size() != 2 || planned.value().apply_enabled ||
        read_file(legacy_install_path.value()) != legacy_text) return 20;
    auto applied = workspaces.apply_migration();
    if (applied || applied.error().code != "workspace_migration_apply_unproven") return 21;
    const std::string report = facman::workspace::migration_report_json(planned.value());
    if (report.find("canonicalize_legacy_install_ref") == std::string::npos ||
        report.find("canonicalize_legacy_instance_manifest") == std::string::npos) return 22;

    ModsetRepository modsets(layout);
    auto local_lock = layout.instance_modset_lock(InstanceId::parse("main").value());
    if (!local_lock || !write_file(local_lock.value(), "{\"schema\":\"factorio.modset_lock.v1\"}") || !modsets.load_lock(InstanceId::parse("main").value())) return 23;
    TransactionRepository transactions(layout);
    auto journal = transactions.journal(TransactionId::parse("tx-test").value());
    if (!journal || !write_file(journal.value(), "{\"schema\":\"facman.transaction.v1\"}") || !transactions.load_journal(TransactionId::parse("tx-test").value())) return 24;
    if (InstallId::parse("../escape") || layout.diagnostic_output("../escape.zip")) return 25;
    return 0;
}

int prove_identity_migration(const fs::path& root)
{
    WorkspaceLayout layout(root);
    if (!write_file(
            layout.manifest(),
            "{\"schema\":\"facman.factorio.workspace.v1\",\"workspace_id\":\"local\",\"layout_version\":1}")) return 30;
    WorkspaceRepository repository(layout);
    auto loaded = repository.load();
    auto plan = repository.plan_migration();
    if (!loaded || !loaded.value().legacy_local_identity || !plan || plan.value().actions.size() != 1 ||
        plan.value().actions.front().kind != "replace_literal_local_workspace_identity") return 31;
    return 0;
}

int prove_compatibility_corpus(const fs::path& root)
{
    const fs::path corpus = fs::path(FACMAN_TEST_SOURCE_ROOT) / "tests" / "fixtures" / "compatibility";
    {
        WorkspaceLayout layout(root / "r3.2");
        if (!write_file(layout.manifest(), read_file(corpus / "r3.2" / "workspace.v1.json"))) return 40;
        auto install = layout.legacy_install_ref(InstallId::parse("legacy-install").value());
        auto instance = layout.legacy_instance_manifest(InstanceId::parse("legacy-instance").value());
        if (!install || !instance ||
            !write_file(install.value(), read_file(corpus / "r3.2" / "legacy-install.json")) ||
            !write_file(instance.value(), read_file(corpus / "r3.2" / "legacy-instance.json"))) return 41;
        auto workspace = WorkspaceRepository(layout).load();
        auto loaded_install = InstallRepository(layout).load(InstallId::parse("legacy-install").value());
        auto loaded_instance = InstanceRepository(layout).load(InstanceId::parse("legacy-instance").value());
        if (!workspace || !workspace.value().legacy_local_identity || !loaded_install ||
            !loaded_install.value().legacy_path || !loaded_instance || !loaded_instance.value().legacy_path) return 42;
    }
    for (const std::string release : {"r3.3", "r3.4"}) {
        WorkspaceLayout layout(root / release);
        if (!write_file(layout.manifest(), read_file(corpus / release / "workspace.v1.json"))) return 43;
        const std::string transaction_id = release == "r3.3" ? "tx-r33" : "tx-r34";
        const fs::path fixture = corpus / release / (release == "r3.3" ? "transaction.v1.json" : "transaction.v2.json");
        auto journal = layout.transaction_journal(TransactionId::parse(transaction_id).value());
        if (!journal || !write_file(journal.value(), read_file(fixture))) return 44;
        if (!WorkspaceRepository(layout).load()) return 45;
        auto recovery = facman::transaction::inspect(layout.root());
        if (!std::holds_alternative<facman::transaction::RecoveryResult>(recovery) ||
            std::get<facman::transaction::RecoveryResult>(recovery).json.find(transaction_id) == std::string::npos) return 46;
    }
    return 0;
}

} // namespace

int main()
{
    const fs::path root = fs::current_path() / fs::u8path("workspace-store-unicode-\xE2\x98\x83") /
        std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
    std::error_code error;
    fs::create_directories(root, error);
    if (error) return 1;
    int result = prove_store(root / "current");
    if (result == 0) result = prove_identity_migration(root / "local identity");
    if (result == 0) result = prove_compatibility_corpus(root / "compatibility");
    fs::remove_all(root, error);
    if (error && result == 0) result = 2;
    if (result != 0) std::cerr << "workspace-store-smoke-stage-code=" << result << "\n";
    return result;
}
