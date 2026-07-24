// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "gate4c_observer_broker_windows.h"

#ifdef _WIN32

#include "fl_random.h"

#include <sddl.h>
#include <shellapi.h>

#include <algorithm>
#include <array>
#include <limits>
#include <memory>
#include <stdexcept>
#include <utility>

namespace facman::gate4c {
namespace {

class ScopedHandle {
public:
    explicit ScopedHandle(HANDLE value = nullptr) noexcept : value_(value) {}
    ~ScopedHandle()
    {
        if (value_ != nullptr && value_ != INVALID_HANDLE_VALUE) CloseHandle(value_);
    }
    ScopedHandle(const ScopedHandle&) = delete;
    ScopedHandle& operator=(const ScopedHandle&) = delete;
    ScopedHandle(ScopedHandle&& other) noexcept : value_(other.release()) {}
    ScopedHandle& operator=(ScopedHandle&& other) noexcept
    {
        if (this != &other) {
            reset(other.release());
        }
        return *this;
    }
    HANDLE get() const noexcept { return value_; }
    HANDLE release() noexcept
    {
        HANDLE result = value_;
        value_ = nullptr;
        return result;
    }
    void reset(HANDLE value = nullptr) noexcept
    {
        if (value_ != nullptr && value_ != INVALID_HANDLE_VALUE) CloseHandle(value_);
        value_ = value;
    }

private:
    HANDLE value_;
};

std::runtime_error windows_error(const std::string& operation)
{
    return std::runtime_error(
        operation + " failed with Windows error " + std::to_string(GetLastError()));
}

std::vector<unsigned char> token_information(
    HANDLE token,
    TOKEN_INFORMATION_CLASS information_class)
{
    DWORD required = 0;
    (void)GetTokenInformation(token, information_class, nullptr, 0, &required);
    if (required == 0U) throw windows_error("GetTokenInformation(size)");
    std::vector<unsigned char> buffer(required);
    if (!GetTokenInformation(
            token, information_class, buffer.data(), required, &required)) {
        throw windows_error("GetTokenInformation");
    }
    return buffer;
}

ProcessSecurityIdentity inspect_process_handle(HANDLE process, DWORD process_id)
{
    ScopedHandle token;
    HANDLE token_value = nullptr;
    if (!OpenProcessToken(process, TOKEN_QUERY, &token_value)) {
        throw windows_error("OpenProcessToken");
    }
    token.reset(token_value);

    const auto user_bytes = token_information(token.get(), TokenUser);
    const auto* token_user =
        reinterpret_cast<const TOKEN_USER*>(user_bytes.data());
    LPWSTR sid_text = nullptr;
    if (!ConvertSidToStringSidW(token_user->User.Sid, &sid_text)) {
        throw windows_error("ConvertSidToStringSidW");
    }
    std::unique_ptr<wchar_t, decltype(&LocalFree)> sid_owner(
        sid_text, &LocalFree);

    const auto integrity_bytes =
        token_information(token.get(), TokenIntegrityLevel);
    const auto* integrity =
        reinterpret_cast<const TOKEN_MANDATORY_LABEL*>(integrity_bytes.data());
    PSID integrity_sid = integrity->Label.Sid;
    const UCHAR subauthority_count = *GetSidSubAuthorityCount(integrity_sid);
    if (subauthority_count == 0U) {
        throw std::runtime_error("process token has no integrity subauthority");
    }
    const DWORD integrity_rid =
        *GetSidSubAuthority(integrity_sid, subauthority_count - 1U);

    DWORD session_id = 0;
    if (!ProcessIdToSessionId(process_id, &session_id)) {
        throw windows_error("ProcessIdToSessionId");
    }

    std::wstring image(32768U, L'\0');
    DWORD image_size = static_cast<DWORD>(image.size());
    if (!QueryFullProcessImageNameW(process, 0, image.data(), &image_size)) {
        throw windows_error("QueryFullProcessImageNameW");
    }
    image.resize(image_size);

    return {
        process_id,
        session_id,
        integrity_rid,
        wide_to_utf8(sid_owner.get()),
        std::filesystem::path(image).lexically_normal(),
    };
}

std::wstring quote_windows_argument(const std::wstring& value)
{
    if (value.empty()) return L"\"\"";
    if (value.find_first_of(L" \t\n\v\"") == std::wstring::npos) return value;
    std::wstring output = L"\"";
    std::size_t backslashes = 0;
    for (wchar_t character : value) {
        if (character == L'\\') {
            ++backslashes;
            continue;
        }
        if (character == L'"') {
            output.append(backslashes * 2U + 1U, L'\\');
            output.push_back(L'"');
            backslashes = 0;
            continue;
        }
        output.append(backslashes, L'\\');
        backslashes = 0;
        output.push_back(character);
    }
    output.append(backslashes * 2U, L'\\');
    output.push_back(L'"');
    return output;
}

void write_exact(HANDLE pipe, const void* data, std::size_t size)
{
    const auto* bytes = static_cast<const unsigned char*>(data);
    std::size_t offset = 0;
    while (offset < size) {
        const DWORD chunk = static_cast<DWORD>(std::min<std::size_t>(
            size - offset, std::numeric_limits<DWORD>::max()));
        DWORD written = 0;
        if (!WriteFile(pipe, bytes + offset, chunk, &written, nullptr) ||
            written == 0U) {
            throw windows_error("WriteFile(named pipe)");
        }
        offset += written;
    }
}

void read_exact(HANDLE pipe, void* data, std::size_t size)
{
    auto* bytes = static_cast<unsigned char*>(data);
    std::size_t offset = 0;
    while (offset < size) {
        const DWORD chunk = static_cast<DWORD>(std::min<std::size_t>(
            size - offset, std::numeric_limits<DWORD>::max()));
        DWORD read = 0;
        if (!ReadFile(pipe, bytes + offset, chunk, &read, nullptr) ||
            read == 0U) {
            throw windows_error("ReadFile(named pipe)");
        }
        offset += read;
    }
}

bool same_image(
    const std::filesystem::path& first,
    const std::filesystem::path& second)
{
    std::error_code first_error;
    std::error_code second_error;
    const auto first_canonical =
        std::filesystem::weakly_canonical(first, first_error);
    const auto second_canonical =
        std::filesystem::weakly_canonical(second, second_error);
    return !first_error && !second_error &&
        _wcsicmp(
            first_canonical.c_str(), second_canonical.c_str()) == 0;
}

void verify_peer(
    const ProcessSecurityIdentity& current,
    const ProcessSecurityIdentity& peer,
    const std::filesystem::path& running_harness,
    bool peer_must_be_high)
{
    if (peer.user_sid != current.user_sid ||
        peer.windows_session_id != current.windows_session_id ||
        !same_image(peer.image_path, running_harness) ||
        (peer_must_be_high
                ? !is_high_integrity(peer)
                : !is_exact_medium_integrity(peer))) {
        throw std::runtime_error(
            "named-pipe peer identity or integrity did not match");
    }
}

} // namespace

std::wstring utf8_to_wide(const std::string& value)
{
    if (value.empty()) return {};
    const int required = MultiByteToWideChar(
        CP_UTF8, MB_ERR_INVALID_CHARS, value.data(),
        static_cast<int>(value.size()), nullptr, 0);
    if (required <= 0) throw windows_error("MultiByteToWideChar(size)");
    std::wstring output(static_cast<std::size_t>(required), L'\0');
    if (MultiByteToWideChar(
            CP_UTF8, MB_ERR_INVALID_CHARS, value.data(),
            static_cast<int>(value.size()), output.data(), required) != required) {
        throw windows_error("MultiByteToWideChar");
    }
    return output;
}

std::string wide_to_utf8(const std::wstring& value)
{
    if (value.empty()) return {};
    const int required = WideCharToMultiByte(
        CP_UTF8, WC_ERR_INVALID_CHARS, value.data(),
        static_cast<int>(value.size()), nullptr, 0, nullptr, nullptr);
    if (required <= 0) throw windows_error("WideCharToMultiByte(size)");
    std::string output(static_cast<std::size_t>(required), '\0');
    if (WideCharToMultiByte(
            CP_UTF8, WC_ERR_INVALID_CHARS, value.data(),
            static_cast<int>(value.size()), output.data(), required, nullptr,
            nullptr) != required) {
        throw windows_error("WideCharToMultiByte");
    }
    return output;
}

ProcessSecurityIdentity current_process_security_identity()
{
    return inspect_process_handle(GetCurrentProcess(), GetCurrentProcessId());
}

ProcessSecurityIdentity inspect_process_security_identity(DWORD process_id)
{
    ScopedHandle process(OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, FALSE, process_id));
    if (process.get() == nullptr) throw windows_error("OpenProcess");
    return inspect_process_handle(process.get(), process_id);
}

bool is_exact_medium_integrity(
    const ProcessSecurityIdentity& identity) noexcept
{
    return identity.integrity_rid >= SECURITY_MANDATORY_MEDIUM_RID &&
        identity.integrity_rid < SECURITY_MANDATORY_HIGH_RID;
}

bool is_high_integrity(const ProcessSecurityIdentity& identity) noexcept
{
    return identity.integrity_rid >= SECURITY_MANDATORY_HIGH_RID;
}

std::string integrity_label(DWORD integrity_rid)
{
    if (integrity_rid >= SECURITY_MANDATORY_SYSTEM_RID) return "system";
    if (integrity_rid >= SECURITY_MANDATORY_HIGH_RID) return "high";
    if (integrity_rid >= SECURITY_MANDATORY_MEDIUM_RID) return "medium";
    if (integrity_rid >= SECURITY_MANDATORY_LOW_RID) return "low";
    return "untrusted";
}

std::string secure_nonce_hex(std::size_t byte_count)
{
    if (byte_count == 0U || byte_count > 64U) {
        throw std::runtime_error("secure nonce size is outside the closed bound");
    }
    std::vector<unsigned char> bytes(byte_count);
    facman::platform::fill_secure_random(bytes.data(), bytes.size());
    constexpr char digits[] = "0123456789abcdef";
    std::string output;
    output.reserve(bytes.size() * 2U);
    for (unsigned char byte : bytes) {
        output.push_back(digits[(byte >> 4U) & 0x0fU]);
        output.push_back(digits[byte & 0x0fU]);
    }
    std::fill(bytes.begin(), bytes.end(), static_cast<unsigned char>(0));
    return output;
}

PipeChannel::PipeChannel(HANDLE pipe) noexcept : pipe_(pipe) {}

PipeChannel::~PipeChannel()
{
    close();
}

PipeChannel::PipeChannel(PipeChannel&& other) noexcept : pipe_(other.pipe_)
{
    other.pipe_ = INVALID_HANDLE_VALUE;
}

PipeChannel& PipeChannel::operator=(PipeChannel&& other) noexcept
{
    if (this != &other) {
        close();
        pipe_ = other.pipe_;
        other.pipe_ = INVALID_HANDLE_VALUE;
    }
    return *this;
}

void PipeChannel::write_frame(const std::string& value) const
{
    if (!valid() || value.empty() || value.size() > 1024U * 1024U) {
        throw std::runtime_error("named-pipe frame is outside the closed bound");
    }
    const std::uint32_t size = static_cast<std::uint32_t>(value.size());
    std::array<unsigned char, 4U> header{
        static_cast<unsigned char>(size & 0xffU),
        static_cast<unsigned char>((size >> 8U) & 0xffU),
        static_cast<unsigned char>((size >> 16U) & 0xffU),
        static_cast<unsigned char>((size >> 24U) & 0xffU),
    };
    write_exact(pipe_, header.data(), header.size());
    write_exact(pipe_, value.data(), value.size());
}

std::string PipeChannel::read_frame(std::size_t maximum_bytes) const
{
    if (!valid() || maximum_bytes == 0U || maximum_bytes > 1024U * 1024U) {
        throw std::runtime_error("named-pipe read bound is invalid");
    }
    std::array<unsigned char, 4U> header{};
    read_exact(pipe_, header.data(), header.size());
    const std::uint32_t size =
        static_cast<std::uint32_t>(header[0]) |
        (static_cast<std::uint32_t>(header[1]) << 8U) |
        (static_cast<std::uint32_t>(header[2]) << 16U) |
        (static_cast<std::uint32_t>(header[3]) << 24U);
    if (size == 0U || size > maximum_bytes) {
        throw std::runtime_error("named-pipe frame length is outside the closed bound");
    }
    std::string output(size, '\0');
    read_exact(pipe_, output.data(), output.size());
    return output;
}

bool PipeChannel::valid() const noexcept
{
    return pipe_ != nullptr && pipe_ != INVALID_HANDLE_VALUE;
}

HANDLE PipeChannel::native_handle() const noexcept
{
    return pipe_;
}

void PipeChannel::close() noexcept
{
    if (valid()) {
        CloseHandle(pipe_);
        pipe_ = INVALID_HANDLE_VALUE;
    }
}

ElevatedBrokerConnection::~ElevatedBrokerConnection()
{
    close_channel();
    if (process_ != nullptr) {
        CloseHandle(process_);
        process_ = nullptr;
    }
}

ElevatedBrokerConnection::ElevatedBrokerConnection(
    ElevatedBrokerConnection&& other) noexcept
    : channel_(std::move(other.channel_)),
      process_(other.process_),
      broker_identity_(std::move(other.broker_identity_))
{
    other.process_ = nullptr;
}

ElevatedBrokerConnection& ElevatedBrokerConnection::operator=(
    ElevatedBrokerConnection&& other) noexcept
{
    if (this != &other) {
        close_channel();
        if (process_ != nullptr) CloseHandle(process_);
        channel_ = std::move(other.channel_);
        process_ = other.process_;
        broker_identity_ = std::move(other.broker_identity_);
        other.process_ = nullptr;
    }
    return *this;
}

ElevatedBrokerConnection ElevatedBrokerConnection::launch(
    const std::filesystem::path& running_harness,
    const std::wstring& broker_mode,
    const std::vector<std::wstring>& trailing_arguments,
    std::chrono::milliseconds connect_timeout)
{
    const ProcessSecurityIdentity coordinator =
        current_process_security_identity();
    if (!is_exact_medium_integrity(coordinator)) {
        throw std::runtime_error(
            "Gate 4C coordinator must run at medium integrity, observed " +
            integrity_label(coordinator.integrity_rid));
    }

    const std::wstring pipe_name =
        L"\\\\.\\pipe\\facman-gate4c-observer-" +
        utf8_to_wide(secure_nonce_hex(24U));
    const std::wstring sddl =
        L"D:P(A;;GA;;;" + utf8_to_wide(coordinator.user_sid) + L")";
    PSECURITY_DESCRIPTOR descriptor = nullptr;
    if (!ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl.c_str(), SDDL_REVISION_1, &descriptor, nullptr)) {
        throw windows_error(
            "ConvertStringSecurityDescriptorToSecurityDescriptorW");
    }
    std::unique_ptr<void, decltype(&LocalFree)> descriptor_owner(
        descriptor, &LocalFree);
    SECURITY_ATTRIBUTES attributes{
        sizeof(SECURITY_ATTRIBUTES), descriptor, FALSE};
    ScopedHandle pipe(CreateNamedPipeW(
        pipe_name.c_str(),
        PIPE_ACCESS_DUPLEX | FILE_FLAG_FIRST_PIPE_INSTANCE |
            FILE_FLAG_OVERLAPPED,
        PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT |
            PIPE_REJECT_REMOTE_CLIENTS,
        1U, 64U * 1024U, 64U * 1024U,
        static_cast<DWORD>(connect_timeout.count()), &attributes));
    if (pipe.get() == INVALID_HANDLE_VALUE) {
        throw windows_error("CreateNamedPipeW");
    }

    if ((broker_mode != L"--observer-broker" &&
            broker_mode != L"--observer-broker-probe") ||
        trailing_arguments.size() > 4U) {
        throw std::runtime_error(
            "elevated observer broker launch mode is outside the closed surface");
    }
    std::wstring parameters =
        broker_mode + L" " + quote_windows_argument(pipe_name);
    for (const std::wstring& argument : trailing_arguments) {
        parameters += L" " + quote_windows_argument(argument);
    }
    SHELLEXECUTEINFOW execute{};
    execute.cbSize = sizeof(execute);
    execute.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC |
        SEE_MASK_FLAG_NO_UI;
    execute.lpVerb = L"runas";
    execute.lpFile = running_harness.c_str();
    execute.lpParameters = parameters.c_str();
    const std::wstring working_directory =
        running_harness.parent_path().wstring();
    execute.lpDirectory = working_directory.c_str();
    execute.nShow = SW_HIDE;
    if (!ShellExecuteExW(&execute) || execute.hProcess == nullptr) {
        throw windows_error("ShellExecuteExW(runas observer broker)");
    }
    ScopedHandle broker_process(execute.hProcess);

    ScopedHandle event(CreateEventW(nullptr, TRUE, FALSE, nullptr));
    if (event.get() == nullptr) throw windows_error("CreateEventW");
    OVERLAPPED overlapped{};
    overlapped.hEvent = event.get();
    const BOOL connected = ConnectNamedPipe(pipe.get(), &overlapped);
    const DWORD connect_error = connected ? ERROR_SUCCESS : GetLastError();
    if (!connected && connect_error != ERROR_IO_PENDING &&
        connect_error != ERROR_PIPE_CONNECTED) {
        throw windows_error("ConnectNamedPipe");
    }
    if (connect_error == ERROR_IO_PENDING) {
        const std::array<HANDLE, 2U> handles{event.get(), broker_process.get()};
        const DWORD waited = WaitForMultipleObjects(
            static_cast<DWORD>(handles.size()), handles.data(), FALSE,
            static_cast<DWORD>(connect_timeout.count()));
        if (waited != WAIT_OBJECT_0) {
            (void)CancelIoEx(pipe.get(), &overlapped);
            if (waited == WAIT_OBJECT_0 + 1U) {
                throw std::runtime_error(
                    "elevated observer broker exited before pipe authentication");
            }
            throw std::runtime_error(
                "timed out waiting for elevated observer broker");
        }
        DWORD transferred = 0;
        if (!GetOverlappedResult(pipe.get(), &overlapped, &transferred, FALSE)) {
            throw windows_error("GetOverlappedResult(ConnectNamedPipe)");
        }
    }

    ULONG client_process_id = 0;
    if (!GetNamedPipeClientProcessId(pipe.get(), &client_process_id)) {
        throw windows_error("GetNamedPipeClientProcessId");
    }
    const DWORD launched_process_id = GetProcessId(broker_process.get());
    if (client_process_id != launched_process_id) {
        throw std::runtime_error(
            "named-pipe client is not the launched observer broker");
    }
    const ProcessSecurityIdentity broker =
        inspect_process_security_identity(client_process_id);
    verify_peer(coordinator, broker, running_harness, true);

    ElevatedBrokerConnection output;
    output.channel_ = PipeChannel(pipe.release());
    output.process_ = broker_process.release();
    output.broker_identity_ = broker;
    return output;
}

PipeChannel& ElevatedBrokerConnection::channel() noexcept
{
    return channel_;
}

const ProcessSecurityIdentity&
ElevatedBrokerConnection::broker_identity() const noexcept
{
    return broker_identity_;
}

DWORD ElevatedBrokerConnection::process_id() const noexcept
{
    return broker_identity_.process_id;
}

DWORD ElevatedBrokerConnection::wait_for_exit(
    std::chrono::milliseconds timeout) const
{
    if (process_ == nullptr) return WAIT_FAILED;
    return WaitForSingleObject(
        process_, static_cast<DWORD>(timeout.count()));
}

void ElevatedBrokerConnection::close_channel() noexcept
{
    channel_.close();
}

BrokerServerConnection connect_to_coordinator(
    const std::wstring& pipe_name,
    DWORD expected_coordinator_process_id,
    const std::filesystem::path& running_harness,
    std::chrono::milliseconds timeout)
{
    const ProcessSecurityIdentity broker = current_process_security_identity();
    if (!is_high_integrity(broker)) {
        throw std::runtime_error(
            "observer broker must run at high integrity");
    }
    if (pipe_name.rfind(L"\\\\.\\pipe\\facman-gate4c-observer-", 0U) != 0U ||
        pipe_name.size() !=
            std::wstring(L"\\\\.\\pipe\\facman-gate4c-observer-").size() +
                48U) {
        throw std::runtime_error("observer broker pipe identity is malformed");
    }
    if (!WaitNamedPipeW(
            pipe_name.c_str(), static_cast<DWORD>(timeout.count()))) {
        throw windows_error("WaitNamedPipeW");
    }
    ScopedHandle pipe(CreateFileW(
        pipe_name.c_str(), GENERIC_READ | GENERIC_WRITE, 0, nullptr,
        OPEN_EXISTING, SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION, nullptr));
    if (pipe.get() == INVALID_HANDLE_VALUE) {
        throw windows_error("CreateFileW(named pipe)");
    }
    ULONG server_process_id = 0;
    if (!GetNamedPipeServerProcessId(pipe.get(), &server_process_id) ||
        server_process_id != expected_coordinator_process_id) {
        throw std::runtime_error(
            "named-pipe server is not the expected coordinator");
    }
    const ProcessSecurityIdentity coordinator =
        inspect_process_security_identity(server_process_id);
    verify_peer(broker, coordinator, running_harness, false);
    BrokerServerConnection output{
        PipeChannel(pipe.release()),
        coordinator,
    };
    return output;
}

} // namespace facman::gate4c

#endif
