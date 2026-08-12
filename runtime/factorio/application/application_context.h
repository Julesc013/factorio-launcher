// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_CONTEXT_H
#define FACMAN_FACTORIO_APPLICATION_CONTEXT_H

#include "application_configuration.h"
#include "fl_system_services.h"
#include "fl_workspace_store.h"
#include "last_run_provider.h"
#include "setup_gateway.h"

#include <filesystem>

namespace facman::factorio::application {

// Owns the narrow process-lifetime services shared by typed command handlers.
// Domain handlers still use real temporary directories and native I/O; this is
// intentionally not a mock-filesystem boundary.
class ApplicationContext {
public:
    explicit ApplicationContext(std::filesystem::path workspace);
    explicit ApplicationContext(ApplicationConfiguration configuration);
    ApplicationContext(
        ApplicationConfiguration configuration,
        std::unique_ptr<LastRunProvider> last_run_provider);

    const std::filesystem::path& workspace() const noexcept { return configuration_.workspace(); }
    const ApplicationConfiguration& configuration() const noexcept { return configuration_; }
    facman::workspace::WorkspaceLayout& layout() noexcept { return layout_; }
    facman::workspace::InstallRepository& installs() noexcept { return installs_; }
    facman::workspace::InstanceRepository& instances() noexcept { return instances_; }
    facman::workspace::ModsetRepository& modsets() noexcept { return modsets_; }
    facman::workspace::TransactionRepository& transactions() noexcept { return transactions_; }
    facman::workspace::WorkspaceRepository& workspace_repository() noexcept { return workspace_repository_; }
    facman::core::Clock& clock() noexcept { return clock_; }
    facman::core::IdGenerator& ids() noexcept { return ids_; }
    SetupGateway& setup() noexcept { return *setup_; }
    LastRunProvider& last_run_provider() noexcept { return *last_run_provider_; }

private:
    ApplicationConfiguration configuration_;
    facman::workspace::WorkspaceLayout layout_;
    facman::workspace::InstallRepository installs_;
    facman::workspace::InstanceRepository instances_;
    facman::workspace::ModsetRepository modsets_;
    facman::workspace::TransactionRepository transactions_;
    facman::workspace::WorkspaceRepository workspace_repository_;
    facman::platform::RealClock clock_;
    facman::platform::RandomIdGenerator ids_;
    std::unique_ptr<SetupGateway> setup_;
    std::unique_ptr<LastRunProvider> last_run_provider_;
};

} // namespace facman::factorio::application

#endif
