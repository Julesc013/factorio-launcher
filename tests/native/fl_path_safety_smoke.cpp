#include "fl_path_safety.h"

#include <atomic>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <string>
#include <thread>

namespace fs = std::filesystem;

namespace {

std::string read_text(const fs::path& path)
{
    std::ifstream input(path, std::ios::binary);
    return std::string(std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>());
}

fs::path unique_test_root()
{
    auto tick = std::chrono::steady_clock::now().time_since_epoch().count();
    return fs::temp_directory_path() / ("facman-path-safety-" + std::to_string(tick));
}

} // namespace

int main()
{
    fs::path root = unique_test_root();
    fs::create_directories(root);

    fs::path target = root / "race.txt";
    std::atomic<bool> start {false};
    std::atomic<int> successes {0};
    auto writer = [&](const std::string& value) {
        while (!start.load()) std::this_thread::yield();
        std::string detail;
        if (facman::base::write_text_new_atomic(target, value, detail)) ++successes;
    };
    std::thread first(writer, "first\n");
    std::thread second(writer, "second\n");
    start = true;
    first.join();
    second.join();
    if (successes != 1 || !fs::is_regular_file(target)) return 10;
    std::string content = read_text(target);
    if (content != "first\n" && content != "second\n") return 11;

    std::size_t temporary_files = 0;
    for (const fs::directory_entry& entry : fs::directory_iterator(root)) {
        if (entry.path().filename().string().find(".race.txt.tmp-") == 0) ++temporary_files;
    }
    if (temporary_files != 0) return 12;

    fs::path destination = root / "committed-directory";
    fs::path staging_one = root / "staging-one";
    fs::path staging_two = root / "staging-two";
    fs::create_directories(staging_one);
    fs::create_directories(staging_two);
    std::ofstream(staging_one / "winner.txt", std::ios::binary) << "one\n";
    std::ofstream(staging_two / "winner.txt", std::ios::binary) << "two\n";

    start = false;
    successes = 0;
    auto committer = [&](const fs::path& staging) {
        while (!start.load()) std::this_thread::yield();
        std::string detail;
        if (facman::base::commit_directory_no_clobber(staging, destination, detail)) ++successes;
    };
    std::thread directory_one(committer, staging_one);
    std::thread directory_two(committer, staging_two);
    start = true;
    directory_one.join();
    directory_two.join();
    if (successes != 1 || !fs::is_regular_file(destination / "winner.txt")) return 20;
    content = read_text(destination / "winner.txt");
    if (content != "one\n" && content != "two\n") return 21;

    std::error_code cleanup_error;
    fs::remove_all(root, cleanup_error);
    return cleanup_error ? 30 : 0;
}
