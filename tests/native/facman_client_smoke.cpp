// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_client.h"

#include <filesystem>
#include <atomic>
#include <memory>
#include <string>
#include <thread>
#include <vector>

namespace {

class RecordingProgress final : public facman::client::ProgressSink {
public:
    void report(const facman::client::ProgressUpdate& update) noexcept override
    {
        stages.push_back(update.stage);
    }
    std::vector<std::string> stages;
};

}

int main()
{
    namespace fs = std::filesystem;
    const fs::path workspace = fs::temp_directory_path() / "facman-client-smoke";
    facman::client::FacManClient client(
        std::make_unique<facman::client::DirectFlbTransport>(workspace));
    auto product = client.execute({"product.inspect", "{}", true});
    if (!product || !product.value().ok() || product.value().payload.find("\"product_id\":\"factorio\"") == std::string::npos) return 1;
    auto unavailable = client.execute({"run.execute", "{}", false});
    if (!unavailable || unavailable.value().ok() || unavailable.value().error_code != "isolation_not_proven") return 2;
    if (product.value().payload_string("product_id") != "factorio" ||
        product.value().payload_string("product_id") != "factorio") return 4;
    std::atomic<int> failures {0};
    std::vector<std::thread> readers;
    for (int index = 0; index < 8; ++index) {
        readers.emplace_back([&client, &failures]() {
            auto response = client.execute({"product.inspect", "{}", true});
            if (!response || !response.value().ok() || response.value().payload_string("product_id") != "factorio") {
                ++failures;
            }
        });
    }
    for (auto& reader : readers) reader.join();
    if (failures != 0) return 5;
    auto progress = std::make_shared<RecordingProgress>();
    facman::client::CommandRequest observed {"product.inspect", "{}", true};
    observed.progress = progress;
    auto observed_response = client.execute(observed);
    if (!observed_response || progress->stages.empty() || progress->stages.back() != "completed") return 6;
    auto cancellation = std::make_shared<facman::client::CancellationToken>();
    cancellation->request_cancellation();
    facman::client::CommandRequest cancelled {"product.inspect", "{}", true};
    cancelled.cancellation = cancellation;
    auto cancelled_response = client.execute(cancelled);
    if (cancelled_response || cancelled_response.error().code != "client_operation_cancelled") return 7;
    facman::client::CommandRequest invalid_timeout {"product.inspect", "{}", true};
    invalid_timeout.timeout = std::chrono::milliseconds(0);
    auto timeout_response = client.execute(invalid_timeout);
    if (timeout_response || timeout_response.error().code != "client_timeout_invalid") return 8;
    facman::client::FacManClient daemon(std::make_unique<facman::client::DaemonTransport>());
    if (daemon.execute({"product.inspect", "{}", true})) return 3;
    return 0;
}
