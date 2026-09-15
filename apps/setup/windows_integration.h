// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_SETUP_WINDOWS_INTEGRATION_H
#define FACMAN_SETUP_WINDOWS_INTEGRATION_H

#include <filesystem>
#include <string>

namespace facman::setup::integration {

enum class Effect { shortcut, registration };
enum class Ownership { absent, owned, owned_stale, foreign, unreadable };
enum class CutoverOwnership {
  absent,
  old_exact,
  new_exact,
  facman_owned_other,
  foreign,
  unreadable,
};

struct Result {
  bool ok = false;
  std::string detail;
  bool recovery_required = false;
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

struct MaintenanceContext {
  std::filesystem::path install_root;
  std::filesystem::path state_root;
  std::filesystem::path acceptance_root;
  std::filesystem::path repair_source;
};

struct CutoverContext {
  MaintenanceContext source;
  MaintenanceContext target;
  std::string source_version;
  std::string target_version;
  std::string operation_id;
};

bool owns_shortcut(const std::filesystem::path &install_root,
                   const ShortcutIdentity &identity);
bool owns_registration(const MaintenanceContext &context,
                       const RegistrationIdentity &identity);
using ReceiptPublishHook = void (*)(const std::filesystem::path &, void *);
Result publish_receipt(const std::filesystem::path &destination,
                       const std::string &bytes,
                       ReceiptPublishHook before_publish = nullptr,
                       void *hook_context = nullptr);
Result inspect_existing_windows(const MaintenanceContext &context);
Result remove_windows(const MaintenanceContext &context);
// Per-effect entrypoints used by the portable setup-operation coordinator.
// They remain current-user only and re-check ownership at the mutation edge.
Ownership inspect_windows_effect(Effect effect,
                                 const MaintenanceContext &context,
                                 const std::string &product_version = {},
                                 bool remove = false);
Result apply_windows_effect(Effect effect,
                            const MaintenanceContext &context,
                            const std::string &product_version,
                            bool remove);
CutoverOwnership inspect_windows_cutover_effect(
    Effect effect, const CutoverContext &context);
// Reconciles an interrupted exact old->new transition. Shortcut replacement
// uses an operation-bound same-directory backup; registration uses one KTM
// transaction. Foreign, unreadable, and different owned generations are
// preserved for recovery.
Result apply_windows_cutover_effect(Effect effect,
                                    const CutoverContext &context);
// Native smoke-test helpers bind a shortcut operation to an isolated fixture
// path; production entry points always resolve the current-user Start Menu.
Ownership inspect_windows_shortcut_fixture(const std::filesystem::path &shortcut,
                                           const std::filesystem::path &install_root,
                                           const std::string &product_version = {});
Result apply_windows_shortcut_fixture(const std::filesystem::path &shortcut,
                                      const std::filesystem::path &install_root,
                                      const std::string &product_version,
                                      bool remove);
CutoverOwnership inspect_windows_shortcut_cutover_fixture(
    const std::filesystem::path &shortcut, const CutoverContext &context);
Result apply_windows_shortcut_cutover_fixture(
    const std::filesystem::path &shortcut, const CutoverContext &context);
} // namespace facman::setup::integration
#endif
