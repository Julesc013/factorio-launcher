// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_json.h"
#include "fl_file_io.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_system_services.h"
#include "flb_factorio_execution.h"
#include "last_run_provider.h"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <string>
#include <thread>
#include <vector>

#if defined(_WIN32)
#include <windows.h>
#endif

namespace {
namespace fs = std::filesystem;
namespace application = facman::factorio::application;
namespace json = facman::core::json;
namespace launch = facman::factorio::launch;

#if defined(_WIN32)
constexpr const char* kRequiredAcknowledgement =
    "TEST-HARNESS-NO-REAL-RELEASE-AUTHORITY";

std::string path_text(const fs::path& path)
{
    return facman::platform::path_to_utf8(path.lexically_normal());
}

fs::path normalized_absolute(const fs::path& path)
{
    std::error_code error;
    fs::path value = fs::absolute(path, error);
    return error ? path.lexically_normal() : value.lexically_normal();
}

bool path_within(const fs::path& parent, const fs::path& child)
{
    const fs::path left = normalized_absolute(parent);
    const fs::path right = normalized_absolute(child);
    auto parent_part = left.begin();
    auto child_part = right.begin();
    for (; parent_part != left.end(); ++parent_part, ++child_part) {
        if (child_part == right.end()) return false;
#if defined(_WIN32)
        std::wstring parent_text = parent_part->wstring();
        std::wstring child_text = child_part->wstring();
        if (_wcsicmp(parent_text.c_str(), child_text.c_str()) != 0) return false;
#else
        if (*parent_part != *child_part) return false;
#endif
    }
    return true;
}

std::string read_bounded(const fs::path& path, std::size_t maximum = 4U * 1024U * 1024U)
{
    std::ifstream input(path, std::ios::binary);
    if (!input) return {};
    std::string value((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
    return value.size() <= maximum ? value : std::string {};
}

std::string environment_text(const char* name)
{
    const char* value = std::getenv(name);
    return value == nullptr ? std::string {} : std::string(value);
}

struct Options {
    fs::path task_root;
    fs::path workspace;
    fs::path source_root;
    fs::path instance_root;
    fs::path executable;
    fs::path route_record;
    fs::path config;
    fs::path mod_directory;
    fs::path result_file;
    std::string instance_id;
    std::string acknowledgement;
    unsigned int close_after_seconds = 45U;
    unsigned int timeout_seconds = 150U;
};

bool option_value(int argc, char** argv, int& index, std::string& output)
{
    if (index + 1 >= argc) return false;
    output = argv[++index];
    return true;
}

bool parse_options(int argc, char** argv, Options& output)
{
    std::map<std::string, std::string> values;
    for (int index = 1; index < argc; ++index) {
        const std::string key = argv[index];
        std::string value;
        if (!option_value(argc, argv, index, value)) return false;
        if (!values.emplace(key, value).second) return false;
    }
    const auto required = [&](const char* key) -> std::string {
        const auto found = values.find(key);
        return found == values.end() ? std::string {} : found->second;
    };
    output.task_root = facman::platform::path_from_utf8(required("--task-root"));
    output.workspace = facman::platform::path_from_utf8(required("--workspace"));
    output.source_root = facman::platform::path_from_utf8(required("--source-root"));
    output.instance_root = facman::platform::path_from_utf8(required("--instance-root"));
    output.executable = facman::platform::path_from_utf8(required("--executable"));
    output.route_record = facman::platform::path_from_utf8(required("--route-record"));
    output.config = facman::platform::path_from_utf8(required("--config"));
    output.mod_directory = facman::platform::path_from_utf8(required("--mod-directory"));
    output.result_file = facman::platform::path_from_utf8(required("--result-file"));
    output.instance_id = required("--instance-id");
    output.acknowledgement = required("--acknowledge");
    try {
        const std::string close = required("--close-after-seconds");
        const std::string timeout = required("--timeout-seconds");
        if (!close.empty()) output.close_after_seconds = static_cast<unsigned int>(std::stoul(close));
        if (!timeout.empty()) output.timeout_seconds = static_cast<unsigned int>(std::stoul(timeout));
    } catch (const std::exception&) {
        return false;
    }
    return values.size() == 13U && !output.result_file.empty() &&
        output.close_after_seconds >= 20U &&
        output.close_after_seconds <= 300U &&
        output.timeout_seconds > output.close_after_seconds + 20U &&
        output.timeout_seconds <= 600U;
}

bool safe_existing_path(const fs::path& task_root, const fs::path& path, bool directory)
{
    std::error_code error;
    std::string detail;
    return path_within(task_root, path) &&
        (directory ? fs::is_directory(path, error) : fs::is_regular_file(path, error)) &&
        !error && !facman::base::path_crosses_link_or_reparse_point(path, detail);
}

bool route_record_valid(const fs::path& route_record, std::string& route_digest)
{
    const std::string text = read_bounded(route_record);
    if (text.empty()) return false;
    route_digest = facman::base::sha256_hex_file(route_record);
    const std::vector<std::string> anchors = {
        "schema = \"facman.factorio_route_version_decision.v1\"",
        std::string("selected_engineering_route_id = \"") +
            FACMAN_ENGINEERING_ROUTE_ID + "\"",
        "selected_engineering_version = \"2.1.14\"",
        std::string("sha256 = \"") + FACMAN_ENGINEERING_EXECUTABLE_SHA256 + "\"",
        "product_execution = false",
        "release_route_activation = false",
        "publication = false",
    };
    if (route_digest != FACMAN_ENGINEERING_ROUTE_RECORD_SHA256) return false;
    for (const std::string& anchor : anchors) {
        if (text.find(anchor) == std::string::npos) return false;
    }
    return true;
}

struct TreeInventory {
    std::string digest;
    std::uint64_t files = 0;
    std::uint64_t bytes = 0;
};

bool tree_inventory(const fs::path& root, TreeInventory& output, std::string& detail)
{
    std::vector<fs::path> files;
    std::error_code error;
    for (fs::recursive_directory_iterator iterator(
             root, fs::directory_options::skip_permission_denied, error), end;
         iterator != end && !error;
         iterator.increment(error)) {
        const fs::file_status status = iterator->symlink_status(error);
        if (error) break;
        if (fs::is_symlink(status)) {
            detail = "source tree contains a symbolic link: " + path_text(iterator->path());
            return false;
        }
        if (fs::is_regular_file(status)) files.push_back(iterator->path());
    }
    if (error) {
        detail = "source tree enumeration failed: " + error.message();
        return false;
    }
    std::sort(files.begin(), files.end(), [&](const fs::path& left, const fs::path& right) {
        return path_text(left.lexically_relative(root)) < path_text(right.lexically_relative(root));
    });
    facman::base::Sha256Hasher inventory;
    try {
        for (const fs::path& path : files) {
            std::string link_detail;
            if (facman::base::path_crosses_link_or_reparse_point(path, link_detail)) {
                detail = "source tree path is unsafe: " + link_detail;
                return false;
            }
            const std::uint64_t size = fs::file_size(path);
            const std::string separator(1U, '\0');
            const std::string record = path_text(path.lexically_relative(root)) + separator +
                std::to_string(size) + separator + facman::base::sha256_hex_file(path) + "\n";
            inventory.update(
                reinterpret_cast<const unsigned char*>(record.data()), record.size());
            ++output.files;
            output.bytes += size;
        }
        output.digest = inventory.finish();
    } catch (const std::exception& exception) {
        detail = exception.what();
        return false;
    }
    return true;
}

struct CloseWindowsContext {
    DWORD process_id = 0;
    bool posted = false;
};

BOOL CALLBACK close_process_window(HWND window, LPARAM parameter)
{
    auto* context = reinterpret_cast<CloseWindowsContext*>(parameter);
    DWORD process_id = 0;
    GetWindowThreadProcessId(window, &process_id);
    if (process_id == context->process_id && IsWindowVisible(window)) {
        if (PostMessageW(window, WM_CLOSE, 0, 0)) context->posted = true;
    }
    return TRUE;
}

void close_after_delay(std::uint64_t process_id, unsigned int seconds)
{
    std::this_thread::sleep_for(std::chrono::seconds(seconds));
    for (unsigned int attempt = 0; attempt < 20U; ++attempt) {
        CloseWindowsContext context {static_cast<DWORD>(process_id), false};
        EnumWindows(close_process_window, reinterpret_cast<LPARAM>(&context));
        if (context.posted) return;
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
}
#endif

int fail(const std::string& code, const std::string& detail)
{
    json::ObjectBuilder error;
    error.add_string("schema", "facman.engineering_play_result.v1");
    error.add_string("status", "refused");
    error.add_string("code", code);
    error.add_string("detail", detail);
    std::cerr << error.serialize() << '\n';
    return 2;
}

} // namespace

int main(int argc, char** argv)
{
#if !defined(_WIN32)
    (void)argc;
    (void)argv;
    return fail("unsupported_platform", "The reviewed engineering route is Windows x64 only");
#else
    Options options;
    if (!parse_options(argc, argv, options)) {
        return fail("invalid_arguments", "Exact task, workspace, source, instance, executable, route record, config, mod, result, acknowledgement, close, and timeout values are required");
    }
    options.task_root = normalized_absolute(options.task_root);
    options.workspace = normalized_absolute(options.workspace);
    options.source_root = normalized_absolute(options.source_root);
    options.instance_root = normalized_absolute(options.instance_root);
    options.executable = normalized_absolute(options.executable);
    options.route_record = normalized_absolute(options.route_record);
    options.config = normalized_absolute(options.config);
    options.mod_directory = normalized_absolute(options.mod_directory);
    options.result_file = normalized_absolute(options.result_file);

    if (options.acknowledgement != kRequiredAcknowledgement) {
        return fail("engineering_acknowledgement_required", kRequiredAcknowledgement);
    }
    if (options.instance_id.empty() ||
        !safe_existing_path(options.task_root, options.source_root, true) ||
        !safe_existing_path(options.task_root, options.workspace, true) ||
        !safe_existing_path(options.task_root, options.instance_root, true) ||
        !safe_existing_path(options.task_root, options.executable, false) ||
        !safe_existing_path(options.task_root, options.route_record, false) ||
        !safe_existing_path(options.task_root, options.config, false) ||
        !safe_existing_path(options.task_root, options.mod_directory, true) ||
        !safe_existing_path(options.task_root, options.result_file.parent_path(), true) ||
        !path_within(options.task_root, options.result_file) ||
        fs::exists(options.result_file) ||
        !path_within(options.source_root, options.executable) ||
        !path_within(options.workspace, options.instance_root) ||
        !path_within(options.instance_root, options.config) ||
        !path_within(options.instance_root, options.mod_directory) ||
        path_within(options.source_root, options.instance_root) ||
        path_within(options.instance_root, options.source_root)) {
        return fail("engineering_path_refused", "All inputs must be safe, exact, disjoint descendants of the task root");
    }
    const std::string executable_sha256 = facman::base::sha256_hex_file(options.executable);
    if (executable_sha256 != FACMAN_ENGINEERING_EXECUTABLE_SHA256) {
        return fail("engineering_executable_identity_mismatch", executable_sha256);
    }
    const std::string config = read_bounded(options.config);
    const std::string expected_read = "read-data=" + path_text(options.source_root / "data");
    const std::string expected_write = "write-data=" + path_text(options.instance_root);
    if (config.find(expected_read) == std::string::npos ||
        config.find(expected_write) == std::string::npos ||
        config.find("check-updates=false") == std::string::npos) {
        return fail("engineering_config_refused", "The exact FacMan config does not route read/write data or disable updates as reviewed");
    }
    std::string route_record_sha256;
    if (!route_record_valid(options.route_record, route_record_sha256)) {
        return fail("engineering_route_record_mismatch", "The compiled route-decision record changed or opens authority");
    }
    TreeInventory source_before;
    std::string inventory_detail;
    if (!tree_inventory(options.source_root, source_before, inventory_detail)) {
        return fail("engineering_source_inventory_failed", inventory_detail);
    }

    const fs::path redirected = options.instance_root / "host-state";
    std::error_code error;
    for (const char* child : {"appdata", "localappdata", "programdata", "profile", "temp"}) {
        fs::create_directories(redirected / child, error);
        if (error) return fail("engineering_host_state_refused", error.message());
    }

    facman::platform::RealClock clock;
    facman::platform::RandomIdGenerator ids;
    launch::PlatformProcessSupervisor supervisor;
    launch::LaunchExecutionService service(supervisor, clock, ids);
    launch::LaunchExecutionRequest request;
    request.ulk_session_journal_root = application::ulk_session_journal_root(options.workspace);
    request.runnable_reference = "facman.instance:" + options.instance_id;
    request.relaunch_reference = "relaunch:" + options.instance_id;
    request.instance_id = options.instance_id;
    request.instance_root = options.instance_root;
    request.executable = options.executable;
    request.engineering_task_root = options.task_root;
    request.engineering_source_root = options.source_root;
    request.arguments = {
        "--config", path_text(options.config),
        "--mod-directory", path_text(options.mod_directory),
        "--fullscreen=false", "--disable-audio", "--window-size", "1280x720",
        "--no-log-rotation",
    };
    request.working_directory = options.instance_root;
    request.environment = {
        {"APPDATA", path_text(redirected / "appdata")},
        {"LOCALAPPDATA", path_text(redirected / "localappdata")},
        {"PROGRAMDATA", path_text(redirected / "programdata")},
        {"USERPROFILE", path_text(redirected / "profile")},
        {"TEMP", path_text(redirected / "temp")},
        {"TMP", path_text(redirected / "temp")},
        {"SystemRoot", environment_text("SystemRoot")},
        {"WINDIR", environment_text("WINDIR")},
        {"ComSpec", environment_text("ComSpec")},
        {"PATH", environment_text("PATH")},
    };
    request.execution_mode = "isolated_engineering";
    request.engineering_route_id = FACMAN_ENGINEERING_ROUTE_ID;
    request.expected_executable_sha256 = FACMAN_ENGINEERING_EXECUTABLE_SHA256;
    request.immutable_plan_identity = facman::base::sha256_hex_file(options.config);
    request.authority = launch::ExecutionAuthority::isolated_engineering_process;
    request.timeout = std::chrono::seconds(options.timeout_seconds);
    request.maximum_standard_output = 4U * 1024U * 1024U;
    request.maximum_standard_error = 4U * 1024U * 1024U;

    std::thread closer;
    request.process_started = [&](const facman::platform::ProcessIdentity& identity) {
        closer = std::thread(close_after_delay, identity.process_id, options.close_after_seconds);
    };
    auto result = service.execute(request);
    if (closer.joinable()) closer.join();
    if (!result) return fail(result.error().code, result.error().message + ": " + result.error().detail);
    TreeInventory source_after;
    if (!tree_inventory(options.source_root, source_after, inventory_detail)) {
        return fail("engineering_source_inventory_failed", inventory_detail);
    }
    const bool source_unchanged = source_before.digest == source_after.digest &&
        source_before.files == source_after.files && source_before.bytes == source_after.bytes;

    const std::string session_text = launch::launch_session_json(result.value());
    auto session = json::parse(session_text);
    auto last_run_provider = application::make_ulk_session_last_run_provider(options.workspace);
    const auto last_run = last_run_provider->last_run(request.runnable_reference);
    auto last_run_value = json::parse(last_run.record_json);
    if (!session || !last_run_value) {
        return fail("engineering_result_encoding_failed", "Session or Last Run output is not valid JSON");
    }
    json::ObjectBuilder output;
    output.add_string("schema", "facman.engineering_play_result.v1");
    output.add_string("status", result.value().successful ? "completed" : "terminal_non_success");
    output.add_string("classification", "test_harness_no_release_authority");
    output.add_string("route_id", FACMAN_ENGINEERING_ROUTE_ID);
    output.add_string("route_record_sha256", route_record_sha256);
    output.add_string("executable_sha256", executable_sha256);
    json::ObjectBuilder source_inventory;
    source_inventory.add_string("before_sha256", source_before.digest);
    source_inventory.add_string("after_sha256", source_after.digest);
    source_inventory.add_unsigned_integer("files", source_after.files);
    source_inventory.add_unsigned_integer("bytes", source_after.bytes);
    source_inventory.add_bool("unchanged", source_unchanged);
    output.add_object("source_inventory", source_inventory);
    output.add_string("last_run_authority_state", application::last_run_authority_state_name(last_run.state));
    output.add_value("session", session.value());
    output.add_value("last_run", last_run_value.value());
    const std::string output_text = output.serialize() + "\n";
    std::string result_detail;
    if (!facman::base::write_text_new_atomic(
            options.result_file, output_text, result_detail)) {
        return fail("engineering_result_write_failed", result_detail);
    }
    std::cout << output_text;
    return result.value().successful && result.value().authoritative_last_run_recorded &&
        source_unchanged ? 0 : 3;
#endif
}
