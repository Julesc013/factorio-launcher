// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "windows_integration.h"

#include <array>
#include <cstdlib>
#include <iostream>
#include <fstream>
#include <iterator>

#ifdef FACMAN_TEST_WINDOWS_INTEGRATION_ADAPTER
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif
#include <string>
#include <utility>
#include <vector>

namespace integration = facman::setup::integration;
using integration::Effect;
using integration::Ownership;
using integration::RemovalRecord;
using integration::Result;

namespace {
int checks = 0;
void require(bool condition, const char *message) {
  ++checks;
  if (!condition) {
    std::cerr << "FAIL: " << message << '\n';
    std::exit(1);
  }
}

struct FakeEffects final : integration::Effects {
  std::array<Ownership, 2> objects{Ownership::owned, Ownership::owned};
  std::vector<std::string> events;
  std::vector<RemovalRecord> durable;
  std::array<int, 2> deletes{0, 0};
  int writes = 0;
  int fail_write = -1;
  int fail_delete = -1;
  int replace_before_delete = -1;
  bool fail_after_effect = false;

  Ownership inspect(Effect effect) override {
    const auto index = static_cast<std::size_t>(effect);
    events.push_back("inspect:" + std::to_string(index));
    return objects[index];
  }
  Result remove_owned(Effect effect) override {
    const auto index = static_cast<std::size_t>(effect);
    events.push_back("remove:" + std::to_string(index));
    if (replace_before_delete == static_cast<int>(index)) objects[index] = Ownership::foreign;
    if (objects[index] == Ownership::foreign || objects[index] == Ownership::unreadable)
      return {false, "identity changed"};
    if (fail_delete == static_cast<int>(index) && !fail_after_effect)
      return {false, "injected native failure"};
    if (objects[index] == Ownership::owned) {
      objects[index] = Ownership::absent;
      ++deletes[index];
    }
    if (fail_delete == static_cast<int>(index))
      return {false, "effect happened; completion response lost"};
    return {true, "removed or absent"};
  }
  Result persist(const RemovalRecord &record) override {
    events.push_back("persist:" + record.phase);
    if (++writes == fail_write) return {false, "injected storage failure"};
    durable.push_back(record);
    return {true, "saved"};
  }
};

void policy_cases() {
  for (const auto ownership : {Ownership::foreign, Ownership::unreadable}) {
    for (const auto effect : {0U, 1U}) {
      FakeEffects fake;
      fake.objects[effect] = ownership;
      require(!integration::remove(fake).ok, "unowned/unreadable entries refuse deletion");
      require(fake.deletes == std::array<int, 2>{0, 0}, "preflight failure preserves both entries");
      require(fake.durable.back().phase == "blocked", "ownership refusal is recoverable");
    }
  }
  for (const auto shortcut : {Ownership::absent, Ownership::owned}) {
    for (const auto registry : {Ownership::absent, Ownership::owned}) {
      FakeEffects fake;
      fake.objects = {shortcut, registry};
      require(integration::remove(fake).ok, "owned/absent combinations remove successfully");
      require(fake.objects == std::array<Ownership, 2>{Ownership::absent, Ownership::absent},
              "all owned native effects removed");
      require(fake.durable.back().phase == "complete", "completion persisted");
      require(fake.events[0] == "inspect:0" && fake.events[1] == "inspect:1" &&
              fake.events[2] == "persist:pending", "both ownership checks and intent precede effects");
      const auto count = fake.deletes;
      require(integration::remove(fake).ok && count == fake.deletes,
              "retry of complete removal never repeats an effect");
    }
  }
  {
    FakeEffects fake;
    fake.fail_write = 1;
    require(!integration::remove(fake).ok, "intent persistence failure refuses removal");
    require(fake.deletes == std::array<int, 2>{0, 0}, "no native effect without durable intent");
  }
  for (const auto effect : {0, 1}) {
    FakeEffects fake;
    fake.replace_before_delete = effect;
    require(!integration::remove(fake).ok, "identity substitution at native boundary refuses deletion");
    require(fake.objects[effect] == Ownership::foreign && fake.deletes[effect] == 0,
            "substituted foreign object remains intact");
    require(fake.durable.back().phase == "incomplete", "substitution retains recoverable state");
  }
  for (const auto effect : {0, 1}) {
    for (const bool response_lost : {false, true}) {
      FakeEffects fake;
      fake.fail_delete = effect;
      fake.fail_after_effect = response_lost;
      require(!integration::remove(fake).ok, "native partial failure is not a success");
      require(fake.durable.back().phase == "incomplete", "partial failure is durable");
      fake.fail_delete = -1;
      require(integration::remove(fake).ok, "retry re-observes and finishes partial state");
      require(fake.deletes == std::array<int, 2>{1, 1}, "retry never repeats completed deletion");
    }
  }
  for (const auto failure : {2, 3, 4}) {
    FakeEffects fake;
    fake.fail_write = failure;
    require(!integration::remove(fake).ok, "progress/final receipt failure is visible");
    require(!fake.durable.empty(), "previous durable pending/progress record retained");
    fake.fail_write = -1;
    require(integration::remove(fake).ok, "restart after receipt failure reconciles native state");
    require(fake.deletes == std::array<int, 2>{1, 1}, "receipt failure cannot cause duplicate deletion");
  }
  {
    FakeEffects fake;
    fake.objects[0] = Ownership::foreign;
    fake.fail_write = 1;
    const auto result = integration::remove(fake);
    require(!result.ok && result.detail.find("receipt failed") != std::string::npos,
            "blocked receipt failure is reported without deleting foreign effects");
  }
}

#ifdef FACMAN_TEST_WINDOWS_INTEGRATION_ADAPTER
struct PublishAttack {
  std::filesystem::path temporary;
  bool replacement_denied = false;
  bool deletion_denied = false;
};

void substitute_temporary(const std::filesystem::path &temporary, void *raw) {
  auto &attack = *static_cast<PublishAttack *>(raw);
  attack.temporary = temporary;
  HANDLE replacement = CreateFileW(temporary.c_str(), GENERIC_WRITE,
      FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
      CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
  attack.replacement_denied = replacement == INVALID_HANDLE_VALUE &&
                              GetLastError() == ERROR_SHARING_VIOLATION;
  if (replacement != INVALID_HANDLE_VALUE) CloseHandle(replacement);
  attack.deletion_denied = !DeleteFileW(temporary.c_str()) &&
                          GetLastError() == ERROR_SHARING_VIOLATION;
}

std::string contents(const std::filesystem::path &path) {
  std::ifstream input(path, std::ios::binary);
  return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}

void receipt_publication_cases() {
  namespace fs = std::filesystem;
  const fs::path parent = fs::path(FACMAN_TEST_TEMP_ROOT);
  fs::create_directories(parent);
  const fs::path fixture = parent / ("publication-" + std::to_string(GetCurrentProcessId()));
  require(fs::create_directory(fixture), "receipt fixture directory must be newly owned");
  const fs::path destination = fixture / "receipt.json";
  PublishAttack attack;
  const std::string pending = "{\"phase\":\"pending\"}\n";
  const auto saved = integration::publish_receipt(
      destination, pending, substitute_temporary, &attack);
  require(saved.ok, "handle-bound receipt publication succeeds");
  require(attack.replacement_denied && attack.deletion_denied,
          "temporary substitution and deletion are denied through publication");
  require(contents(destination) == pending, "only the original flushed bytes are published");
  require(!fs::exists(attack.temporary), "original temporary object becomes the receipt");

  HANDLE locked_destination = CreateFileW(destination.c_str(), GENERIC_READ,
      FILE_SHARE_READ, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
  require(locked_destination != INVALID_HANDLE_VALUE, "fixture destination lock acquired");
  PublishAttack failed;
  const auto rejected = integration::publish_receipt(
      destination, "{\"phase\":\"complete\"}\n", substitute_temporary, &failed);
  CloseHandle(locked_destination);
  require(!rejected.ok, "locked destination refuses receipt publication");
  require(contents(destination) == pending, "failed replacement preserves previous durable receipt");
  require(failed.replacement_denied && failed.deletion_denied,
          "failed publication also retains source ownership through the attempt");
  require(failed.temporary.parent_path() == fixture &&
          contents(failed.temporary) == "{\"phase\":\"complete\"}\n",
          "failed publication retains the exact temporary object for recovery");
  // All cleanup is nonrecursive and limited to the newly created fixture.
  fs::remove(failed.temporary);
  fs::remove(destination);
  require(fs::remove(fixture), "owned empty fixture directory retired");
}

void shortcut_lifecycle_cases() {
  namespace fs = std::filesystem;
  const fs::path fixture = fs::path(FACMAN_TEST_TEMP_ROOT) /
      ("shortcut-lifecycle-" + std::to_string(GetCurrentProcessId()));
  const fs::path root = fixture / "install";
  const fs::path shortcut = fixture / "Programs" / "FacMan.lnk";
  std::error_code error;
  fs::create_directories(fixture.parent_path(), error);
  require(!error, "shortcut lifecycle fixture parent created");
  fs::remove_all(fixture, error);
  fs::create_directories(root / "generations" / "1.0.0", error);
  require(!error, "shortcut lifecycle fixture generation directory created");
  fs::create_directories(root / "maintenance", error);
  require(!error, "shortcut lifecycle fixture maintenance directory created");
  std::ofstream(root / "generations" / "1.0.0" / "FacMan.exe", std::ios::binary) << "fixture";
  std::ofstream(root / "maintenance" / "FacManSetup.exe", std::ios::binary) << "fixture";

  const auto created = integration::apply_windows_shortcut_fixture(shortcut, root, "1.0.0", false);
  require(created.ok, "owned real shortcut created in the isolated fixture");
  const auto first = integration::inspect_windows_shortcut_fixture(shortcut, root, "1.0.0");
  const auto repeated = integration::inspect_windows_shortcut_fixture(shortcut, root, "1.0.0");
  require(first == Ownership::owned && repeated == Ownership::owned,
          "an owned real shortcut remains inspectable after repeated reads");
  fs::remove_all(root, error);
  require(!error, "shortcut lifecycle target root deleted");
  require(integration::inspect_windows_shortcut_fixture(shortcut, root, "1.0.0") == Ownership::owned,
          "owned shortcut remains owned after its target root is deleted");
  const auto removed = integration::apply_windows_shortcut_fixture(shortcut, root, "", true);
  require(removed.ok, "owned real shortcut is removable after target root deletion");

  const fs::path foreign_root = fixture / "foreign";
  fs::create_directories(foreign_root / "generations" / "9.9.9", error);
  require(!error, "foreign shortcut fixture generation directory created");
  fs::create_directories(foreign_root / "maintenance", error);
  require(!error, "foreign shortcut fixture maintenance directory created");
  std::ofstream(foreign_root / "generations" / "9.9.9" / "FacMan.exe",
                std::ios::binary) << "foreign fixture";
  std::ofstream(foreign_root / "maintenance" / "FacManSetup.exe",
                std::ios::binary) << "foreign fixture";
  const auto substituted = integration::apply_windows_shortcut_fixture(
      shortcut, foreign_root, "9.9.9", false);
  require(substituted.ok, "foreign substitute shortcut created inside the isolated fixture");
  const auto refused = integration::apply_windows_shortcut_fixture(shortcut, root, "", true);
  require(!refused.ok && refused.recovery_required && fs::is_regular_file(shortcut),
          "mutation-edge shortcut substitution requires recovery and is preserved");
  fs::remove_all(fixture, error);
  require(!error, "owned shortcut lifecycle fixture retired");
}

void shortcut_cutover_cases() {
  namespace fs = std::filesystem;
  const fs::path fixture = fs::path(FACMAN_TEST_TEMP_ROOT) /
      ("shortcut-cutover-" + std::to_string(GetCurrentProcessId()));
  const fs::path old_root = fixture / "FacMan.old";
  const fs::path new_root = fixture / "FacMan.new";
  const fs::path shortcut = fixture / "Programs" / "FacMan.lnk";
  std::error_code error;
  fs::remove_all(fixture, error);
  for (const auto &root_version :
       {std::pair<fs::path, std::string>{old_root, "1.0.0"},
        std::pair<fs::path, std::string>{new_root, "2.0.0"}}) {
    fs::create_directories(root_version.first / "generations" /
                               root_version.second,
                           error);
    require(!error, "cutover generation directory created");
    fs::create_directories(root_version.first / "maintenance", error);
    require(!error, "cutover maintenance directory created");
    std::ofstream(root_version.first / "generations" /
                      root_version.second / "FacMan.exe",
                  std::ios::binary) << root_version.second;
    std::ofstream(root_version.first / "maintenance" / "FacManSetup.exe",
                  std::ios::binary) << "setup";
  }
  require(integration::apply_windows_shortcut_fixture(
              shortcut, old_root, "1.0.0", false).ok,
          "source shortcut created");
  integration::CutoverContext context{
      {old_root, {}, {}, {}}, {new_root, {}, {}, {}},
      "1.0.0", "2.0.0", "maintenance.update.fixture"};
  require(integration::inspect_windows_shortcut_cutover_fixture(
              shortcut, context) == integration::CutoverOwnership::old_exact,
          "source shortcut is classified exactly");
  require(integration::apply_windows_shortcut_cutover_fixture(
              shortcut, context).ok,
          "side-by-side shortcut cutover completes");
  require(integration::inspect_windows_shortcut_cutover_fixture(
              shortcut, context) == integration::CutoverOwnership::new_exact,
          "target shortcut is classified exactly");
  const fs::path backup = shortcut.parent_path() /
      (shortcut.filename().wstring() +
       L".facman-backup.maintenance.update.fixture");
  require(fs::is_regular_file(backup),
          "operation-bound source shortcut backup is retained");
  fs::remove(shortcut, error);
  require(!error, "published shortcut removed to simulate lost publication");
  require(integration::apply_windows_shortcut_cutover_fixture(
              shortcut, context).ok,
          "cutover resumes from exact operation-bound backup");
  require(integration::inspect_windows_shortcut_cutover_fixture(
              shortcut, context) == integration::CutoverOwnership::new_exact,
          "resumed cutover publishes the exact target");
  require(fs::is_regular_file(backup),
          "resumed cutover retains its source backup until durable activation");
  require(integration::retire_windows_shortcut_cutover_fixture(
              shortcut, context).ok && !fs::exists(backup),
          "durably activated cutover retires the exact source backup");
  require(integration::retire_windows_shortcut_cutover_fixture(
              shortcut, context).ok,
          "shortcut backup retirement is idempotent when already absent");
  require(integration::inspect_windows_shortcut_cutover_fixture(
              shortcut, context) == integration::CutoverOwnership::new_exact,
          "backup retirement preserves the active target shortcut");
  require(integration::apply_windows_shortcut_fixture(
              backup, new_root, "2.0.0", false).ok,
          "non-source operation-bound backup fixture created");
  const auto foreign_backup =
      integration::retire_windows_shortcut_cutover_fixture(shortcut, context);
  require(!foreign_backup.ok && foreign_backup.recovery_required &&
              fs::is_regular_file(backup),
          "non-source operation-bound backup is refused and preserved");
  fs::remove_all(fixture, error);
  require(!error, "shortcut cutover fixture retired");
}
#endif

#ifdef FACMAN_TEST_WINDOWS_INTEGRATION_ADAPTER
void identity_cases() {
  namespace fs = std::filesystem;
  const fs::path root = LR"(C:\Users\Tester\Programs\FacMan)";
  integration::ShortcutIdentity shortcut{
      root / "generations" / "0.1.0-alpha.6" / "FacMan.exe",
      root / "generations" / "0.1.0-alpha.6", L""};
  require(integration::owns_shortcut(root, shortcut), "owned generation shortcut accepted");
  require(integration::owns_shortcut(LR"(c:\users\TESTER\programs\facman\)", shortcut),
          "Windows case and trailing separator compare consistently");
  auto changed = shortcut;
  changed.target = root.parent_path() / "Foreign" / "generations" / "v1" / "FacMan.exe";
  changed.working_directory = changed.target.parent_path();
  require(!integration::owns_shortcut(root, changed), "foreign install generation refused");
  changed = shortcut;
  changed.target = root / "generations" / "v1" / ".." / ".." / "foreign" / "FacMan.exe";
  changed.working_directory = changed.target.parent_path();
  require(!integration::owns_shortcut(root, changed), "dot traversal cannot claim generation ownership");
  changed = shortcut;
  changed.arguments = L"--foreign-mode";
  require(!integration::owns_shortcut(root, changed), "custom argument shortcut preserved");
  changed = shortcut;
  changed.working_directory = root / "foreign";
  require(!integration::owns_shortcut(root, changed), "foreign working directory preserved");
  changed = shortcut;
  changed.target = root / "generations" / "v1" / "nested" / "FacMan.exe";
  changed.working_directory = changed.target.parent_path();
  require(!integration::owns_shortcut(root, changed), "nested target cannot claim generation ownership");
  changed = shortcut;
  changed.target = "FacMan.exe";
  require(!integration::owns_shortcut(root, changed), "relative shortcut target refused");
  require(!integration::owns_shortcut("FacMan", shortcut), "relative owner root refused");

  const fs::path alias_fixture = fs::path(FACMAN_TEST_TEMP_ROOT) /
      ("path-alias-" + std::to_string(GetCurrentProcessId()));
  std::error_code alias_error;
  fs::remove_all(alias_fixture, alias_error);
  fs::create_directories(alias_fixture / "generations" / "1.0.0", alias_error);
  require(!alias_error, "path-alias fixture created");
  std::ofstream(alias_fixture / "generations" / "1.0.0" / "FacMan.exe",
                std::ios::binary) << "fixture";
  std::array<wchar_t, 32768> short_buffer{};
  const DWORD short_length = GetShortPathNameW(
      alias_fixture.c_str(), short_buffer.data(),
      static_cast<DWORD>(short_buffer.size()));
  require(short_length != 0U && short_length < short_buffer.size(),
          "Windows short spelling for owned fixture is available");
  const fs::path alias_root(std::wstring(short_buffer.data(), short_length));
  integration::ShortcutIdentity alias_shortcut{
      alias_fixture / "generations" / "1.0.0" / "FacMan.exe",
      alias_fixture / "generations" / "1.0.0", L""};
  require(integration::owns_shortcut(alias_root, alias_shortcut),
          "Windows short and long spellings bind the same owned shortcut");
  fs::remove_all(alias_fixture, alias_error);
  require(!alias_error, "path-alias fixture retired");

  const fs::path state = LR"(C:\Users\Tester\AppData\Local\FacMan\setup)";
  const fs::path acceptance = LR"(C:\Users\Tester\AppData\Local)";
  const fs::path source = state / "repair-sources" /
      (std::string(64, 'a') + ".zip");
  integration::MaintenanceContext context{root, state, acceptance, source};
  const fs::path launcher = source.parent_path() /
      (std::string(64, 'a') + ".FacManSetup.exe");
  const std::wstring uninstall = L"\"" +
      launcher.wstring() +
      L"\" uninstall --root \"" + root.wstring() +
      L"\" --state-root \"" + state.wstring() +
      L"\" --acceptance-root \"" + acceptance.wstring() +
      L"\" --yes --noninteractive --shell-integration";
  integration::RegistrationIdentity registration{root, L"FacMan", uninstall, false};
  require(integration::owns_registration(context, registration), "owned registration accepted");
  auto legacy = registration;
  legacy.uninstall_command = L"\"" +
      (root / "maintenance" / "FacManSetup.exe").wstring() +
      L"\" uninstall --yes";
  require(integration::owns_registration(context, legacy),
          "exact earlier FacMan registration remains owned for migration");
  auto case_context = context;
  case_context.install_root = LR"(c:\users\TESTER\programs\facman\)";
  require(integration::owns_registration(case_context, registration),
          "registration owner path follows Windows path comparison");
  auto foreign = registration;
  foreign.install_location = root.parent_path() / "Other";
  require(!integration::owns_registration(context, foreign), "foreign InstallLocation refused");
  foreign = registration;
  foreign.uninstall_command += L" & foreign.exe";
  require(!integration::owns_registration(context, foreign), "foreign maintenance command refused");
  foreign = registration;
  foreign.display_name = L"Other product";
  require(!integration::owns_registration(context, foreign), "foreign product identity refused");
  foreign = registration;
  foreign.unexpected_content = true;
  require(!integration::owns_registration(context, foreign), "unknown registry values/subkeys preserved");
}
#endif
} // namespace

int main() {
  policy_cases();
  #ifdef FACMAN_TEST_WINDOWS_INTEGRATION_ADAPTER
  identity_cases();
  receipt_publication_cases();
  shortcut_lifecycle_cases();
  shortcut_cutover_cases();
  #endif
  std::cout << "PASS: " << checks << " native integration ownership checks; "
            << "native effects injected; shortcut fixture stays under the CMake test root\n";
}
