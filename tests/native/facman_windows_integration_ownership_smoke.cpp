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

  integration::RegistrationIdentity registration{
      root, L"FacMan", L"\"" + (root / "maintenance" / "FacManSetup.exe").wstring() +
                            L"\" uninstall --yes", false};
  require(integration::owns_registration(root, registration), "owned registration accepted");
  require(integration::owns_registration(LR"(c:\users\TESTER\programs\facman\)", registration),
          "registration owner path follows Windows path comparison");
  auto foreign = registration;
  foreign.install_location = root.parent_path() / "Other";
  require(!integration::owns_registration(root, foreign), "foreign InstallLocation refused");
  foreign = registration;
  foreign.uninstall_command += L" & foreign.exe";
  require(!integration::owns_registration(root, foreign), "foreign maintenance command refused");
  foreign = registration;
  foreign.display_name = L"Other product";
  require(!integration::owns_registration(root, foreign), "foreign product identity refused");
  foreign = registration;
  foreign.unexpected_content = true;
  require(!integration::owns_registration(root, foreign), "unknown registry values/subkeys preserved");
}
#endif
} // namespace

int main() {
  policy_cases();
  #ifdef FACMAN_TEST_WINDOWS_INTEGRATION_ADAPTER
  identity_cases();
  receipt_publication_cases();
  #endif
  std::cout << "PASS: " << checks << " native integration ownership checks; "
            << "native effects injected; local receipt fixture only, no real registry or shortcut mutations\n";
}