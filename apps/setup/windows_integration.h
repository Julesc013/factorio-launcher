// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_SETUP_WINDOWS_INTEGRATION_H
#define FACMAN_SETUP_WINDOWS_INTEGRATION_H

#include <filesystem>
#include <string>

namespace facman::setup::integration {

enum class Effect { shortcut, registration };
enum class Ownership { absent, owned, foreign, unreadable };

struct Result {
  bool ok = false;
  std::string detail;
};

struct RemovalRecord {
  std::string phase = "pending";
  std::string shortcut = "unobserved";
  std::string registration = "unobserved";
  std::string detail;
};

// The adapter must bind the ownership observation to the object it removes.
// A failed operation may have taken effect: the caller must preserve the
// pending receipt and re-observe on retry instead of trusting a local flag.
class Effects {
public:
  virtual ~Effects() = default;
  virtual Ownership inspect(Effect effect) = 0;
  virtual Result remove_owned(Effect effect) = 0;
  virtual Result persist(const RemovalRecord &record) = 0;
};

Result remove(Effects &effects);

struct ShortcutIdentity {
  std::filesystem::path target;
  std::filesystem::path working_directory;
  std::wstring arguments;
};

struct RegistrationIdentity {
  std::filesystem::path install_location;
  std::wstring display_name;
  std::wstring uninstall_command;
  bool unexpected_content = false;
};

bool owns_shortcut(const std::filesystem::path &install_root,
                   const ShortcutIdentity &identity);
bool owns_registration(const std::filesystem::path &install_root,
                       const RegistrationIdentity &identity);
using ReceiptPublishHook = void (*)(const std::filesystem::path &, void *);
Result publish_receipt(const std::filesystem::path &destination,
                       const std::string &bytes,
                       ReceiptPublishHook before_publish = nullptr,
                       void *hook_context = nullptr);
Result inspect_existing_windows(const std::filesystem::path &install_root);
Result remove_windows(const std::filesystem::path &install_root,
                      const std::filesystem::path &state_root);
} // namespace facman::setup::integration
#endif