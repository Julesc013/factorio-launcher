// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_file_io.h"
#include "fl_local_filesystem.h"
#include "fl_retained_rewrite_state.h"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <csignal>
#include <cstdint>
#include <cerrno>
#include <vector>
#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/xattr.h>
#include <unistd.h>
#include <sys/resource.h>
#include <sys/wait.h>
#if defined(__APPLE__)
#include <sys/acl.h>
#include <membership.h>
#endif

namespace {
namespace fs = std::filesystem;
using namespace facman::platform;
fs::path target;
std::string hook_phase, hook_effect;
void require(bool value, const char* detail)
{
    if (!value) throw std::runtime_error(detail);
}
std::string read(const fs::path& path)
{
    std::ifstream stream(path, std::ios::binary);
    return {std::istreambuf_iterator<char>(stream), {}};
}
void put(const fs::path& path, const std::string& bytes)
{
    std::ofstream stream(path, std::ios::binary | std::ios::trunc);
    stream << bytes; stream.close(); require(bool(stream), "fixture write");
}
void phase_hook(const char* phase)
{
    if (hook_phase != phase) return;
    if (hook_effect == "loss") throw std::runtime_error("injected-interruption");
    if (hook_effect == "stop_for_sigkill") {
        // The parent observes this exact phase stop before delivering SIGKILL.
        if (::raise(SIGSTOP) != 0) ::_exit(84);
        ::_exit(85); // Unexpected continuation must never look like death proof.
    }
    if (hook_effect == "bytes") put(target, "foreign bytes");
    if (hook_effect == "mode") require(::chmod(target.c_str(), 0600) == 0, "hook chmod");
    if (hook_effect == "alias") fs::create_hard_link(target, target.parent_path() / "alias.ini");
    if (hook_effect == "substitute") {
        fs::rename(target, target.parent_path() / "held.ini");
        put(target, "foreign bytes");
    }
    if (hook_effect == "flush") testing::set_retained_stream_rewrite_flush_fault(true);
}
struct ChildCustody {
    pid_t pid = -1;
    ~ChildCustody()
    {
        // Even a failed parent assertion must reap the stopped child.
        if (pid > 0) {
            (void)::kill(pid, SIGKILL);
            int status = 0;
            while (::waitpid(pid, &status, 0) < 0 && errno == EINTR) {}
        }
    }
};
FileIdentity identity(const fs::path& path)
{
    StableInputFile input; require(input.open_no_follow_pinned(path).ok(), "fixture identity");
    return input.identity();
}
std::string metadata(RetainedStreamRewriteFile& file)
{
    std::string value; require(file.readable_metadata_identity(value).ok(), "metadata available");
    return value;
}
void reset(const fs::path& parent, const std::string& original)
{
    fs::remove_all(parent); fs::create_directory(parent); target = parent / "config.ini";
    put(target, original); require(::chmod(target.c_str(), 0640) == 0, "fixture chmod");
}
int put_xattr(const fs::path& path, const char* name, const std::string& value)
{
#if defined(__APPLE__)
    return ::setxattr(path.c_str(), name, value.data(), value.size(), 0, 0);
#else
    return ::setxattr(path.c_str(), name, value.data(), value.size(), 0);
#endif
}
void set_xattr(const fs::path& path, const char* name, const std::string& value)
{
    require(put_xattr(path, name, value) == 0, "fixture xattr");
}
void set_access_acl(const fs::path& path)
{
#if defined(__APPLE__)
    const int fd = ::open(path.c_str(), O_RDWR | O_CLOEXEC);
    require(fd >= 0, "ACL fixture FD");
    acl_t acl = ::acl_init(1); acl_entry_t entry; acl_permset_t permissions;
    uuid_t principal;
    const bool ready = acl && ::mbr_uid_to_uuid(::getuid(), principal) == 0 &&
        ::acl_create_entry(&acl, &entry) == 0 && ::acl_set_tag_type(entry, ACL_EXTENDED_ALLOW) == 0 &&
        ::acl_set_qualifier(entry, principal) == 0 && ::acl_get_permset(entry, &permissions) == 0 &&
        ::acl_add_perm(permissions, ACL_READ_DATA) == 0 && ::acl_add_perm(permissions, ACL_WRITE_DATA) == 0 &&
        ::acl_set_permset(entry, permissions) == 0 && ::acl_set_fd_np(fd, acl, ACL_TYPE_EXTENDED) == 0;
    if (acl) ::acl_free(acl);
    ::close(fd); require(ready, "nonempty Darwin access ACL fixture");
#else
    // Linux ACL xattr version 2: owner, named user, group, mask, other.
    std::string acl;
    auto integer = [&](std::uint32_t value, unsigned bytes) {
        for (unsigned index = 0; index < bytes; ++index)
            acl.push_back(static_cast<char>((value >> (index * 8U)) & 255U));
    };
    integer(2U, 4);
    auto entry = [&](std::uint32_t tag, std::uint32_t permissions, std::uint32_t id) {
        integer(tag, 2); integer(permissions, 2); integer(id, 4);
    };
    entry(1U, 6U, 0xffffffffU);
    entry(2U, 4U, ::getuid() == 65534U ? 65533U : 65534U);
    entry(4U, 4U, 0xffffffffU); entry(16U, 4U, 0xffffffffU); entry(32U, 0U, 0xffffffffU);
    set_xattr(path, "system.posix_acl_access", acl);
#endif
}
constexpr const char* user_attribute =
#if defined(__APPLE__)
    "com.facman.rewrite-test";
#else
    "user.facman.rewrite-test";
#endif
} // namespace

int main()
{
    const auto root = fs::temp_directory_path() / ("facman-retained-rewrite-" + std::to_string(::getpid()));
    fs::create_directory(root);
    try {
        // Test the shared refusal policy without requiring a remote mount.
        struct statfs remote {};
#if defined(__APPLE__)
        remote.f_flags = 0;
#else
        remote.f_type = 0x6969; // NFS
#endif
        require(!facman::platform::detail::supported_posix_local_filesystem(remote), "unclassified/remote policy refusal");
        const auto parent_path = root / "config";
        const std::string original(5000, 'o');
        for (const std::size_t length : {3000U, 5000U, 7000U}) {
            reset(parent_path, original);
            set_xattr(target, user_attribute, std::string("\0\xff\x01", 3));
            set_access_acl(target);
            const auto bound = identity(target);
            StableDirectoryObject parent;
            require(parent.open_no_follow(parent_path).ok(), "open parent");
            RetainedStreamRewriteFile file;
            const std::string intended(length, 'i');
            const auto opened = parent.open_child_file_no_follow_for_retained_rewrite("config.ini", bound,
                original, intended, RetainedStreamRewriteState::original_only, file);
            if (!opened.ok()) throw std::runtime_error(opened.code + ": " + opened.detail);
            const auto before = metadata(file);
            require(!file.rewrite_to_intended().ok() && read(target) == original, "no durable authority no write");
            RetainedStreamRewriteFile contended;
            require(parent.open_child_file_no_follow_for_retained_rewrite("config.ini", bound, original, intended,
                RetainedStreamRewriteState::original_only, contended).code == "retained_rewrite_contended", "actual flock contention");
            require(file.admit_durable_mutation().ok() && !file.admit_durable_mutation().ok(), "same handle admission once");
            require(file.rewrite_to_intended().ok() && file.verify_intended().ok(), "real in-place rewrite");
            std::string observed; FileIdentity current;
            require(file.observe(observed, current).ok() && observed == intended && current.same_object(bound), "original inode retained");
            require(metadata(file) == before, "mode uid gid ACL birth flags readable xattrs retained");
            file = RetainedStreamRewriteFile{};
            RetainedStreamRewriteFile terminal;
            require(parent.open_child_file_no_follow_for_retained_rewrite("config.ini", bound, original, intended,
                RetainedStreamRewriteState::terminal_verify_only, terminal).ok(), "terminal exact effect open");
            testing::set_retained_stream_rewrite_flush_fault(true);
            require(terminal.verify_intended().ok() && !terminal.rewrite_to_intended().ok() &&
                !terminal.admit_durable_mutation().ok(), "terminal verification never writes or flushes");
            terminal = RetainedStreamRewriteFile{};
            RetainedStreamRewriteFile authorized;
            require(parent.open_child_file_no_follow_for_retained_rewrite("config.ini", bound, original, intended,
                RetainedStreamRewriteState::mutation_authorized, authorized).ok(), "authorized intended open");
            require(authorized.rewrite_to_intended().code == "retained_rewrite_effect_uncertain", "terminal left flush seam unconsumed");
            require(authorized.rewrite_to_intended().ok(), "flush retry on authorized exact effect");
        }
        // Simulated interruption before and after exact truncation, plus a
        // flushed intermediate prefix. Resume through the bound original inode.
        for (const std::string phase : {"after_prefix", "after_write", "after_truncate"}) {
            reset(parent_path, original); const auto bound = identity(target);
            const std::string intended(phase == "after_prefix" ? 7000U : 3000U, 'i');
            StableDirectoryObject parent; require(parent.open_no_follow(parent_path).ok(), "loss parent");
            {
                RetainedStreamRewriteFile file;
                require(parent.open_child_file_no_follow_for_retained_rewrite("config.ini", bound, original, intended,
                    RetainedStreamRewriteState::mutation_authorized, file).ok(), "loss bound open");
                hook_phase = phase; hook_effect = "loss"; testing::set_retained_stream_rewrite_phase_hook(phase_hook);
                bool lost = false;
                try { (void)file.rewrite_to_intended(); } catch (const std::runtime_error& e) {
                    lost = std::string(e.what()) == "injected-interruption";
                }
                testing::set_retained_stream_rewrite_phase_hook(nullptr);
                require(lost, "phase loss reached");
                const auto partial = read(target);
                require(facman::platform::detail::retained_rewrite_bytes_admissible(original, intended, partial), "reachable loss bytes");
                if (phase == "after_prefix") require(partial == intended.substr(0, 4096) + original.substr(4096), "exact first prefix");
                if (phase == "after_write") require(partial == intended + original.substr(intended.size()), "old tail before truncate");
                if (phase == "after_truncate") require(partial == intended, "exact truncated bytes");
            }
            RetainedStreamRewriteFile resumed;
            require(parent.open_child_file_no_follow_for_retained_rewrite("config.ini", bound, original, intended,
                RetainedStreamRewriteState::mutation_authorized, resumed).ok(), "reachable prefix reopen");
            require(resumed.rewrite_to_intended().ok() && resumed.verify_intended().ok(), "same inode simulated interruption resume");
        }
        // Real process death is distinct from the exception/reopen cases
        // above. The parent owns no writer when it forks: only the child holds
        // flock during mutation. SIGSTOP makes each kill boundary observable.
        for (const std::string phase : {"after_prefix", "after_write", "after_truncate"}) {
            reset(parent_path, original);
            set_xattr(target, user_attribute, std::string("\0\xff\x01", 3));
            set_access_acl(target);
            const auto bound = identity(target);
            const std::string intended(phase == "after_prefix" ? 7000U : 3000U, 'i');
            StableDirectoryObject parent;
            require(parent.open_no_follow(parent_path).ok(), "real death parent");
            std::string original_metadata;
            {
                RetainedStreamRewriteFile original_file;
                require(parent.open_child_file_no_follow_for_retained_rewrite("config.ini", bound, original, intended,
                    RetainedStreamRewriteState::original_only, original_file).ok(), "real death metadata binding");
                original_metadata = metadata(original_file);
            } // Release the parent's writer before fork; do not inherit flock.
            const pid_t child = ::fork();
            require(child >= 0, "fork real mutation child");
            if (child == 0) {
                try {
                    RetainedStreamRewriteFile child_file;
                    if (!parent.open_child_file_no_follow_for_retained_rewrite("config.ini", bound, original, intended,
                        RetainedStreamRewriteState::mutation_authorized, child_file).ok() ||
                        metadata(child_file) != original_metadata) ::_exit(81);
                    hook_phase = phase; hook_effect = "stop_for_sigkill";
                    testing::set_retained_stream_rewrite_phase_hook(phase_hook);
                    (void)child_file.rewrite_to_intended();
                    ::_exit(82); // The requested phase must stop before return.
                } catch (...) { ::_exit(83); }
            }
            ChildCustody custody; custody.pid = child;
            int status = 0;
            pid_t waited = -1;
            do { waited = ::waitpid(child, &status, WUNTRACED); } while (waited < 0 && errno == EINTR);
            if (waited == child && (WIFEXITED(status) || WIFSIGNALED(status))) custody.pid = -1;
            require(waited == child && WIFSTOPPED(status) && WSTOPSIG(status) == SIGSTOP,
                "child reached exact stopped rewrite phase");
            const std::string expected = phase == "after_prefix" ? intended.substr(0, 4096) + original.substr(4096) :
                phase == "after_write" ? intended + original.substr(intended.size()) : intended;
            require(read(target) == expected, "exact bytes at real child kill boundary");
            RetainedStreamRewriteFile still_contended;
            require(parent.open_child_file_no_follow_for_retained_rewrite("config.ini", bound, original, intended,
                RetainedStreamRewriteState::mutation_authorized, still_contended).code == "retained_rewrite_contended",
                "stopped child alone owns advisory flock");
            require(::kill(child, SIGKILL) == 0, "parent delivers SIGKILL to mutation child");
            do { waited = ::waitpid(child, &status, 0); } while (waited < 0 && errno == EINTR);
            if (waited == child) custody.pid = -1;
            require(waited == child && WIFSIGNALED(status) && WTERMSIG(status) == SIGKILL,
                "waitpid proves actual SIGKILL death");
            RetainedStreamRewriteFile recovered;
            require(parent.open_child_file_no_follow_for_retained_rewrite("config.ini", bound, original, intended,
                RetainedStreamRewriteState::mutation_authorized, recovered).ok(), "killed child releases flock");
            std::string observed; FileIdentity current;
            require(recovered.observe(observed, current).ok() && observed == expected && current.same_object(bound) &&
                current.link_count == 1U && metadata(recovered) == original_metadata,
                "real death preserves bound inode bytes and readable metadata");
            require(recovered.rewrite_to_intended().ok() && recovered.verify_intended().ok() &&
                recovered.observe(observed, current).ok() && observed == intended && current.same_object(bound) &&
                metadata(recovered) == original_metadata, "recover exact original binding after SIGKILL");
            recovered = RetainedStreamRewriteFile{};
            RetainedStreamRewriteFile terminal;
            require(parent.open_child_file_no_follow_for_retained_rewrite("config.ini", bound, original, intended,
                RetainedStreamRewriteState::terminal_verify_only, terminal).ok(), "real death terminal exact open");
            testing::set_retained_stream_rewrite_flush_fault(true);
            require(terminal.verify_intended().ok() && !terminal.rewrite_to_intended().ok() &&
                !terminal.admit_durable_mutation().ok() && terminal.observe(observed, current).ok() &&
                observed == intended && current.same_object(bound) && metadata(terminal) == original_metadata,
                "terminal after real death recovery never mutates");
            terminal = RetainedStreamRewriteFile{};
            RetainedStreamRewriteFile flush_probe;
            require(parent.open_child_file_no_follow_for_retained_rewrite("config.ini", bound, original, intended,
                RetainedStreamRewriteState::mutation_authorized, flush_probe).ok() &&
                flush_probe.rewrite_to_intended().code == "retained_rewrite_effect_uncertain" &&
                read(target) == intended, "terminal left flush fault unconsumed and exact bytes unchanged");
            std::cout << "real-process-death: " << phase << " SIGKILL observed; original inode/metadata recovered; flock released; terminal unchanged\n";
        }
        // Inject an actual uncooperative edit/rename/link after the preceding
        // observation. Each next effect must refuse and preserve the edit.
        for (const std::string phase : {"before_write", "after_prefix", "after_write"}) {
            for (const std::string effect : {"bytes", "mode", "alias", "substitute"}) {
                reset(parent_path, original); const auto bound = identity(target);
                StableDirectoryObject parent; require(parent.open_no_follow(parent_path).ok(), "interference parent");
                RetainedStreamRewriteFile file;
                const std::string intended(7000, 'i');
                require(parent.open_child_file_no_follow_for_retained_rewrite("config.ini", bound, original, intended,
                    RetainedStreamRewriteState::mutation_authorized, file).ok(), "interference open");
                hook_phase = phase; hook_effect = effect; testing::set_retained_stream_rewrite_phase_hook(phase_hook);
                const auto result = file.rewrite_to_intended(); testing::set_retained_stream_rewrite_phase_hook(nullptr);
                require(!result.ok(), "next effect refuses actual interference");
                if (effect == "bytes" || effect == "substitute") require(read(target) == "foreign bytes", "foreign target preserved");
                if (effect == "mode") { struct stat current {}; require(::stat(target.c_str(), &current) == 0 &&
                    (current.st_mode & 0777) == 0600, "metadata change not restored"); }
                if (effect == "alias") require(read(parent_path / "alias.ini") == read(target), "foreign alias not removed");
                if (effect == "substitute") {
                    const auto held = read(parent_path / "held.ini");
                    require(phase == "before_write" ? held == original :
                        phase == "after_prefix" ? held == intended.substr(0, 4096) + original.substr(4096) :
                        held == intended, "renamed held inode stops at preceding effect");
                }
            }
        }
        reset(parent_path, original); auto bound = identity(target);
        {
            // Restrict only this test process, then restore before assertions.
            // Crossing the size limit makes the second pwrite short or fail.
            struct rlimit previous {}, limited {};
            require(::getrlimit(RLIMIT_FSIZE, &previous) == 0, "read process file limit");
            limited = previous; limited.rlim_cur = 4097;
            StableDirectoryObject parent; require(parent.open_no_follow(parent_path).ok(), "short write parent");
            RetainedStreamRewriteFile file; const std::string intended(7000, 'i');
            require(parent.open_child_file_no_follow_for_retained_rewrite("config.ini", bound, original, intended,
                RetainedStreamRewriteState::mutation_authorized, file).ok(), "short write open");
            const auto old_signal = std::signal(SIGXFSZ, SIG_IGN);
            require(::setrlimit(RLIMIT_FSIZE, &limited) == 0, "bound test process file limit");
            const auto result = file.rewrite_to_intended();
            const int restored = ::setrlimit(RLIMIT_FSIZE, &previous);
            std::signal(SIGXFSZ, old_signal);
            require(restored == 0 && result.code == "retained_rewrite_effect_uncertain", "short pwrite fails with bounded prefix");
            require(facman::platform::detail::retained_rewrite_bytes_admissible(original, intended, read(target)), "short write reachable bytes");
            require(file.rewrite_to_intended().ok(), "short write retry");
        }
        reset(parent_path, original); bound = identity(target);
        {
            StableDirectoryObject parent; require(parent.open_no_follow(parent_path).ok(), "truncate flush parent");
            RetainedStreamRewriteFile file; const std::string intended(3000, 'i');
            require(parent.open_child_file_no_follow_for_retained_rewrite("config.ini", bound, original, intended,
                RetainedStreamRewriteState::mutation_authorized, file).ok(), "truncate flush open");
            hook_phase = "after_write"; hook_effect = "flush"; testing::set_retained_stream_rewrite_phase_hook(phase_hook);
            const auto result = file.rewrite_to_intended(); testing::set_retained_stream_rewrite_phase_hook(nullptr);
            require(result.code == "retained_rewrite_effect_uncertain" && read(target) == intended, "truncate flush failure preserves exact effect");
            require(file.rewrite_to_intended().ok(), "truncate flush retry");
        }
        reset(parent_path, original); bound = identity(target);
        {
            StableDirectoryObject parent; require(parent.open_no_follow(parent_path).ok(), "flush parent");
            RetainedStreamRewriteFile file; const std::string intended(7000, 'i');
            require(parent.open_child_file_no_follow_for_retained_rewrite("config.ini", bound, original, intended,
                RetainedStreamRewriteState::mutation_authorized, file).ok(), "flush open");
            testing::set_retained_stream_rewrite_flush_fault(true);
            require(file.rewrite_to_intended().code == "retained_rewrite_effect_uncertain" &&
                read(target) == intended.substr(0, 4096) + original.substr(4096), "flush failure preserves reachable prefix");
            require(file.rewrite_to_intended().ok(), "flush failure recovery");
        }
        reset(parent_path, original); bound = identity(target);
        {
            StableDirectoryObject parent; require(parent.open_no_follow(parent_path).ok(), "admit drift parent");
            RetainedStreamRewriteFile file;
            require(parent.open_child_file_no_follow_for_retained_rewrite("config.ini", bound, original, "intended",
                RetainedStreamRewriteState::original_only, file).ok(), "admit drift open");
            put(target, "foreign bytes");
            require(!file.admit_durable_mutation().ok() && !file.rewrite_to_intended().ok() &&
                read(target) == "foreign bytes", "drift before durable admission preserved");
        }
        for (const std::string effect : {"hardlink", "symlink", "substitute", "setid", "readonly", "empty", "torn", "oversized-xattr"}) {
            reset(parent_path, original); bound = identity(target);
            StableDirectoryObject parent; require(parent.open_no_follow(parent_path).ok(), "refusal parent");
            if (effect == "hardlink") fs::create_hard_link(target, parent_path / "alias.ini");
            if (effect == "symlink" || effect == "substitute") {
                fs::rename(target, parent_path / "held.ini");
                if (effect == "symlink") fs::create_symlink(parent_path / "held.ini", target);
                else put(target, original);
            }
            if (effect == "setid") require(::chmod(target.c_str(), 04640) == 0, "setid fixture");
            if (effect == "readonly") require(::chmod(target.c_str(), 0440) == 0, "readonly fixture");
            if (effect == "empty") put(target, "");
            if (effect == "torn") put(target, "torn-unowned-bytes");
            if (effect == "oversized-xattr" && put_xattr(target, user_attribute, std::string(33000, 'x')) != 0) {
                // Some local filesystems reject this fixture before an
                // oversized readable identity can exist. Record that limit.
                const int fixture_error = errno;
                require(fixture_error == E2BIG || fixture_error == ENOSPC || fixture_error == ENOTSUP, "oversized fixture failure category");
                require(read(target) == original, "filesystem-refused oversized fixture preserves data");
                std::cout << "SKIP product oversized-metadata proof: fixture write errno=" << fixture_error << '\n';
                continue;
            }
            const auto before_bytes = read(target);
            RetainedStreamRewriteFile file;
            require(!parent.open_child_file_no_follow_for_retained_rewrite("config.ini", bound, original, "intended",
                RetainedStreamRewriteState::mutation_authorized, file).ok() && read(target) == before_bytes,
                "unsafe admission preserves target");
        }
        reset(parent_path, original); bound = identity(target);
        {
            StableDirectoryObject parent; require(parent.open_no_follow(parent_path).ok(), "metadata parent");
            RetainedStreamRewriteFile file;
            require(parent.open_child_file_no_follow_for_retained_rewrite("config.ini", bound, original, "intended",
                RetainedStreamRewriteState::mutation_authorized, file).ok(), "metadata drift open");
            set_xattr(target, user_attribute, "foreign-readable-metadata");
            require(file.rewrite_to_intended().code == "retained_rewrite_metadata_changed" && read(target) == original,
                "readable xattr drift refuses before write");
        }
        reset(parent_path, original); bound = identity(target);
        {
            StableDirectoryObject parent; require(parent.open_no_follow(parent_path).ok(), "parent substitute open");
            RetainedStreamRewriteFile file;
            require(parent.open_child_file_no_follow_for_retained_rewrite("config.ini", bound, original, "intended",
                RetainedStreamRewriteState::mutation_authorized, file).ok(), "parent substitute file");
            fs::rename(parent_path, root / "moved"); fs::create_directory(parent_path); put(parent_path / "config.ini", "foreign bytes");
            require(file.rewrite_to_intended().code == "retained_rewrite_parent_changed" &&
                read(root / "moved/config.ini") == original && read(parent_path / "config.ini") == "foreign bytes",
                "parent substitution preserves both objects");
        }
        fs::remove_all(root);
        std::cout << "fl-retained-rewrite-smoke: ok\n";
        return 0;
    } catch (const std::exception& error) {
        testing::set_retained_stream_rewrite_phase_hook(nullptr);
        testing::set_retained_stream_rewrite_flush_fault(false);
        std::cerr << "fl-retained-rewrite-smoke: " << error.what() << '\n';
        fs::remove_all(root);
        return 1;
    }
}
