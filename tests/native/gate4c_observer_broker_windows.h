// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_TEST_GATE4C_OBSERVER_BROKER_WINDOWS_H
#define FACMAN_TEST_GATE4C_OBSERVER_BROKER_WINDOWS_H

#ifdef _WIN32

#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include <chrono>
#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace facman::gate4c {

struct ProcessSecurityIdentity {
    DWORD process_id = 0;
    DWORD windows_session_id = 0;
    DWORD integrity_rid = 0;
    std::string user_sid;
    std::filesystem::path image_path;
};

constexpr DWORD kMediumIntegrityRid = SECURITY_MANDATORY_MEDIUM_RID;
constexpr DWORD kHighIntegrityRid = SECURITY_MANDATORY_HIGH_RID;

ProcessSecurityIdentity current_process_security_identity();
ProcessSecurityIdentity inspect_process_security_identity(DWORD process_id);
bool is_exact_medium_integrity(const ProcessSecurityIdentity& identity) noexcept;
bool is_high_integrity(const ProcessSecurityIdentity& identity) noexcept;
std::string integrity_label(DWORD integrity_rid);
std::string secure_nonce_hex(std::size_t byte_count);

class PipeChannel {
public:
    PipeChannel() noexcept = default;
    explicit PipeChannel(HANDLE pipe) noexcept;
    ~PipeChannel();

    PipeChannel(const PipeChannel&) = delete;
    PipeChannel& operator=(const PipeChannel&) = delete;
    PipeChannel(PipeChannel&& other) noexcept;
    PipeChannel& operator=(PipeChannel&& other) noexcept;

    void write_frame(const std::string& value) const;
    std::string read_frame(std::size_t maximum_bytes) const;
    bool valid() const noexcept;
    HANDLE native_handle() const noexcept;
    void close() noexcept;

private:
    HANDLE pipe_ = INVALID_HANDLE_VALUE;
};

class ElevatedBrokerConnection {
public:
    ElevatedBrokerConnection() noexcept = default;
    ~ElevatedBrokerConnection();

    ElevatedBrokerConnection(const ElevatedBrokerConnection&) = delete;
    ElevatedBrokerConnection& operator=(const ElevatedBrokerConnection&) = delete;
    ElevatedBrokerConnection(ElevatedBrokerConnection&& other) noexcept;
    ElevatedBrokerConnection& operator=(ElevatedBrokerConnection&& other) noexcept;

    static ElevatedBrokerConnection launch(
        const std::filesystem::path& running_harness,
        const std::wstring& broker_mode,
        const std::vector<std::wstring>& trailing_arguments,
        std::chrono::milliseconds connect_timeout);

    PipeChannel& channel() noexcept;
    const ProcessSecurityIdentity& broker_identity() const noexcept;
    DWORD process_id() const noexcept;
    DWORD wait_for_exit(std::chrono::milliseconds timeout) const;
    void close_channel() noexcept;

private:
    PipeChannel channel_;
    HANDLE process_ = nullptr;
    ProcessSecurityIdentity broker_identity_;
};

struct BrokerServerConnection {
    PipeChannel channel;
    ProcessSecurityIdentity coordinator_identity;
};

BrokerServerConnection connect_to_coordinator(
    const std::wstring& pipe_name,
    DWORD expected_coordinator_process_id,
    const std::filesystem::path& running_harness,
    std::chrono::milliseconds timeout);

std::wstring utf8_to_wide(const std::string& value);
std::string wide_to_utf8(const std::wstring& value);

} // namespace facman::gate4c

#endif

#endif
