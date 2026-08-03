// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_runtime_verify.h"

#include "fl_sha256.h"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <map>
#include <sstream>
#include <string>

namespace fs = std::filesystem;

namespace {
constexpr const char* kFactorioBindingRevision = "1111111111111111111111111111111111111111";
constexpr const char* kSourceRevision = "2222222222222222222222222222222222222222";
constexpr const char* kUniversalLauncherRevision = "3333333333333333333333333333333333333333";
constexpr const char* kUniversalSetupRevision = "4444444444444444444444444444444444444444";

struct PlatformIdentity {
    const char* profile;
    const char* target_os;
    const char* package_type;
    const char* executable;
};

PlatformIdentity platform_identity()
{
#ifdef _WIN32
    return {"windows_portable_cli_x64", "windows", "portable_zip", "bin/facman.exe"};
#elif defined(__APPLE__)
    return {"macos_portable_cli_x64", "macos", "tarball", "bin/facman"};
#else
    return {"linux_portable_cli_x64", "linux", "tarball", "bin/facman"};
#endif
}

void write_file(const fs::path& path, const std::string& contents)
{
    fs::create_directories(path.parent_path());
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    output.write(contents.data(), static_cast<std::streamsize>(contents.size()));
    if (!output) throw std::runtime_error("cannot write test package file");
}

std::string file_digest(const fs::path& path)
{
    return facman::base::sha256_hex_file(path);
}

std::string component(
    const std::string& name,
    const std::string& source_target,
    const std::string& destination,
    const std::string& kind,
    const std::string& role,
    const fs::path& root)
{
    std::ostringstream output;
    output << "{\"name\":\"" << name
           << "\",\"source_target\":\"" << source_target
           << "\",\"destination\":\"" << destination
           << "\",\"kind\":\"" << kind
           << "\",\"runtime_role\":\"" << role
           << "\",\"sha256\":\"" << file_digest(root / fs::u8path(destination))
           << "\",\"size\":" << fs::file_size(root / fs::u8path(destination)) << "}";
    return output.str();
}

std::string expected_contract_digest(const std::string& contents)
{
    std::string normalized;
    normalized.reserve(contents.size());
    for (std::size_t index = 0; index < contents.size(); ++index) {
        if (contents[index] == '\r') {
            normalized.push_back('\n');
            if (index + 1 < contents.size() && contents[index + 1] == '\n') ++index;
        } else {
            normalized.push_back(contents[index]);
        }
    }
    facman::base::Sha256Hasher hasher;
    const std::string relative = "contracts/schema/test.schema.json";
    const unsigned char separator = 0;
    hasher.update(reinterpret_cast<const unsigned char*>(relative.data()), relative.size());
    hasher.update(&separator, 1);
    hasher.update(reinterpret_cast<const unsigned char*>(normalized.data()), normalized.size());
    hasher.update(&separator, 1);
    return hasher.finish();
}

class TemporaryPackage {
public:
    TemporaryPackage()
    {
        const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
        base = fs::temp_directory_path() / "facman-runtime-package-identity-smoke";
        root = base /
            ("facman-runtime-package-identity-" + std::to_string(nonce));
        fs::create_directories(root);
    }

    ~TemporaryPackage()
    {
        std::error_code ignored;
        fs::remove_all(root, ignored);
        fs::remove(base, ignored);
    }

    fs::path base;
    fs::path root;
};
}

int main()
{
    try {
        TemporaryPackage package;
        const PlatformIdentity platform = platform_identity();
        const std::string contract_contents = "{\r\n  \"type\": \"object\"\r}\r\n";
        write_file(package.root / fs::u8path(platform.executable), "synthetic-backend\n");
        write_file(package.root / "contracts/schema/test.schema.json", contract_contents);
        write_file(package.root / "content/factorio/discovery/test.toml", "provider = \"test\"\n");
        write_file(package.root / "manifest/build_info.v1.json", "{}\n");

        std::ostringstream manifest;
        manifest << "schema = \"facman.built_package.v1\"\n"
                 << "profile_id = \"" << platform.profile << "\"\n"
                 << "lane = \"test\"\n"
                 << "target_os = \"" << platform.target_os << "\"\n"
                 << "target_arch = \"x64\"\n"
                 << "package_type = \"" << platform.package_type << "\"\n"
                 << "entrypoint = \"" << platform.executable << "\"\n"
                 << "linkage_model = \"static_first\"\n"
                 << "release_profile = \"release/profiles/test/profile.toml\"\n"
                 << "package_manifest = \"release/packaging/test.v1.toml\"\n"
                 << "workspace_lock = \"release/index/workspace_lock.v1.toml\"\n"
                 << "source_revision = \"" << kSourceRevision << "\"\n"
                 << "proof_baseline_revision = \"" << kFactorioBindingRevision << "\"\n"
                 << "universal_launcher_revision = \"" << kUniversalLauncherRevision << "\"\n"
                 << "universal_setup_revision = \"" << kUniversalSetupRevision << "\"\n"
                 << "artifact_level = \"built-artifact\"\n"
                 << "signed = false\n"
                 << "published = false\n"
                 << "source_dirty = false\n"
                 << "python_runtime = false\n"
                 << "bundles_factorio_binaries = false\n";
        write_file(package.root / "manifest/package.v1.toml", manifest.str());

        std::ostringstream workspace_lock;
        workspace_lock << "[[component]]\nid = \"factorio_binding\"\npin = \""
                       << kFactorioBindingRevision
                       << "\"\n[[component]]\nid = \"universal_launcher\"\npin = \""
                       << kUniversalLauncherRevision
                       << "\"\n[[component]]\nid = \"universal_setup\"\npin = \""
                       << kUniversalSetupRevision << "\"\n";
        write_file(package.root / "release/index/workspace_lock.v1.toml", workspace_lock.str());

        const std::string executable_component = component(
            "console_cli", "facman_cli", platform.executable,
            "frontend", "runtime_required", package.root);
        const std::string contract_component = component(
            "test_contract", "contracts/schema", "contracts/schema/test.schema.json",
            "contracts", "compatibility_reference", package.root);
        const std::string content_component = component(
            "test_content", "content/factorio", "content/factorio/discovery/test.toml",
            "content", "compatibility_reference", package.root);
        write_file(
            package.root / "manifest/components.v1.json",
            "{\"schema\":\"facman.package_components.v1\",\"components\":[" +
                executable_component + "," + contract_component + "," + content_component + "]}\n");

        std::map<std::string, std::string> hashes;
        for (const fs::directory_entry& entry : fs::recursive_directory_iterator(package.root)) {
            if (!entry.is_regular_file()) continue;
            const std::string relative = entry.path().lexically_relative(package.root).generic_string();
            if (relative == "manifest/hashes.sha256") continue;
            hashes.emplace(relative, file_digest(entry.path()));
        }
        std::ostringstream hash_manifest;
        for (const auto& entry : hashes) {
            hash_manifest << entry.second << "  " << entry.first << "\n";
        }
        write_file(package.root / "manifest/hashes.sha256", hash_manifest.str());

        const facman::package::RuntimePackageEvidence evidence =
            facman::package::inspect_package(
                package.root,
                package.root / fs::u8path(platform.executable));
        if (!evidence.packaged || !evidence.verified) return 10;
        if (evidence.profile_id != platform.profile ||
            evidence.source_revision != kSourceRevision ||
            evidence.source_dirty || !evidence.source_dirty_known ||
            evidence.universal_launcher_revision != kUniversalLauncherRevision ||
            evidence.universal_setup_revision != kUniversalSetupRevision) return 11;
        if (evidence.backend_relative_path != platform.executable ||
            evidence.backend_sha256 != file_digest(package.root / fs::u8path(platform.executable))) return 12;
        if (evidence.manifest_sha256 != file_digest(package.root / "manifest/package.v1.toml") ||
            evidence.closure_sha256 != file_digest(package.root / "manifest/hashes.sha256")) return 13;
        if (evidence.contract_set_sha256 != expected_contract_digest(contract_contents)) return 14;
        if (evidence.files_verified != hashes.size()) return 15;

        write_file(package.root / "contracts/schema/test.schema.json", "{}\n");
        const facman::package::RuntimePackageEvidence mutated =
            facman::package::inspect_package(
                package.root,
                package.root / fs::u8path(platform.executable));
        if (!mutated.packaged || mutated.verified ||
            mutated.detail.find("SHA-256 mismatch") == std::string::npos) return 16;
        return 0;
    } catch (...) {
        return 99;
    }
}
