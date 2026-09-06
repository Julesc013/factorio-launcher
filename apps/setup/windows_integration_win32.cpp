// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "windows_integration.h"
#include "fl_json.h"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <ktmw32.h>
#include <shlobj.h>
#include <shobjidl.h>

#include <array>
#include <atomic>
#include <cstring>
#include <vector>

namespace facman::setup::integration {
namespace {
namespace fs = std::filesystem;
constexpr wchar_t registry_path[] =
    L"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\FacMan";

struct Handle {
  HANDLE value = INVALID_HANDLE_VALUE;
  ~Handle() { if (value != INVALID_HANDLE_VALUE && value != nullptr) CloseHandle(value); }
};
struct Key {
  HKEY value = nullptr;
  ~Key() { if (value != nullptr) RegCloseKey(value); }
};
struct Apartment {
  HRESULT status = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE);
  ~Apartment() { if (SUCCEEDED(status)) CoUninitialize(); }
};

bool equal(const std::wstring &left, const std::wstring &right) {
  return CompareStringOrdinal(left.c_str(), static_cast<int>(left.size()),
                              right.c_str(), static_cast<int>(right.size()),
                              TRUE) == CSTR_EQUAL;
}

fs::path normalized(const fs::path &path) {
  fs::path result = path.lexically_normal();
  while (!result.empty() && result.filename().empty() && result != result.root_path())
    result = result.parent_path();
  return result;
}

bool same_path(const fs::path &left, const fs::path &right) {
  return left.is_absolute() && right.is_absolute() &&
         equal(normalized(left).wstring(), normalized(right).wstring());
}

std::wstring uninstall_command(const fs::path &root) {
  return L"\"" + (root / "maintenance" / "FacManSetup.exe").wstring() +
         L"\" uninstall --yes";
}

fs::path start_menu_link() {
  PWSTR raw = nullptr;
  // Observation/removal must never create the user's Start Menu.
  const HRESULT status = SHGetKnownFolderPath(FOLDERID_Programs, 0, nullptr, &raw);
  fs::path result;
  if (SUCCEEDED(status) && raw != nullptr) result = fs::path(raw) / "FacMan.lnk";
  CoTaskMemFree(raw);
  return result;
}

bool read_shortcut(HANDLE file, ShortcutIdentity &identity) {
  BY_HANDLE_FILE_INFORMATION info{};
  LARGE_INTEGER size{};
  if (!GetFileInformationByHandle(file, &info) ||
      (info.dwFileAttributes & (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DIRECTORY)) ||
      !GetFileSizeEx(file, &size) || size.QuadPart <= 0 || size.QuadPart > 1024 * 1024)
    return false;
  std::vector<unsigned char> bytes(static_cast<std::size_t>(size.QuadPart));
  DWORD read = 0;
  if (!ReadFile(file, bytes.data(), static_cast<DWORD>(bytes.size()), &read, nullptr) ||
      read != bytes.size()) return false;
  Apartment apartment;
  IShellLinkW *link = nullptr;
  if (FAILED(CoCreateInstance(CLSID_ShellLink, nullptr, CLSCTX_INPROC_SERVER,
                              IID_IShellLinkW, reinterpret_cast<void **>(&link))))
    return false;
  IStream *stream = nullptr;
  IPersistStream *persist = nullptr;
  HRESULT status = CreateStreamOnHGlobal(nullptr, TRUE, &stream);
  if (SUCCEEDED(status)) {
    ULONG written = 0;
    status = stream->Write(bytes.data(), static_cast<ULONG>(bytes.size()), &written);
    if (SUCCEEDED(status) && written != bytes.size()) status = E_FAIL;
  }
  if (SUCCEEDED(status)) {
    LARGE_INTEGER zero{};
    status = stream->Seek(zero, STREAM_SEEK_SET, nullptr);
  }
  if (SUCCEEDED(status))
    status = link->QueryInterface(IID_IPersistStream, reinterpret_cast<void **>(&persist));
  if (SUCCEEDED(status)) status = persist->Load(stream);
  std::array<wchar_t, 32768> target{}, directory{}, arguments{};
  if (SUCCEEDED(status))
    status = link->GetPath(target.data(), static_cast<int>(target.size()), nullptr, SLGP_RAWPATH);
  if (SUCCEEDED(status))
    status = link->GetWorkingDirectory(directory.data(), static_cast<int>(directory.size()));
  if (SUCCEEDED(status))
    status = link->GetArguments(arguments.data(), static_cast<int>(arguments.size()));
  if (persist != nullptr) persist->Release();
  if (stream != nullptr) stream->Release();
  link->Release();
  if (FAILED(status)) return false;
  identity = {fs::path(target.data()), fs::path(directory.data()), arguments.data()};
  return true;
}

Ownership shortcut_ownership(HANDLE file, const fs::path &root) {
  ShortcutIdentity identity;
  if (!read_shortcut(file, identity)) return Ownership::unreadable;
  return owns_shortcut(root, identity) ? Ownership::owned : Ownership::foreign;
}

Ownership open_shortcut(const fs::path &link, const fs::path &root,
                        bool removing, Handle &file) {
  if (link.empty()) return Ownership::unreadable;
  file.value = CreateFileW(link.c_str(), GENERIC_READ | (removing ? DELETE : 0),
                          FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                          FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
  if (file.value == INVALID_HANDLE_VALUE) {
    const DWORD error = GetLastError();
    return error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND
               ? Ownership::absent : Ownership::unreadable;
  }
  return shortcut_ownership(file.value, root);
}

bool registry_string(HKEY key, const wchar_t *name, std::wstring &value) {
  DWORD type = 0, bytes = 0;
  if (RegQueryValueExW(key, name, nullptr, &type, nullptr, &bytes) != ERROR_SUCCESS ||
      type != REG_SZ || bytes < sizeof(wchar_t) || bytes > 65536 ||
      bytes % sizeof(wchar_t) != 0) return false;
  std::vector<wchar_t> buffer(bytes / sizeof(wchar_t));
  DWORD actual = bytes;
  if (RegQueryValueExW(key, name, nullptr, &type,
                       reinterpret_cast<BYTE *>(buffer.data()), &actual) != ERROR_SUCCESS ||
      type != REG_SZ || actual != bytes || buffer.back() != L'\0') return false;
  value.assign(buffer.data(), buffer.size() - 1);
  return value.find(L'\0') == std::wstring::npos;
}

Ownership registration_ownership(HKEY key, const fs::path &root) {
  RegistrationIdentity identity;
  std::wstring location;
  if (!registry_string(key, L"InstallLocation", location) ||
      !registry_string(key, L"DisplayName", identity.display_name) ||
      !registry_string(key, L"UninstallString", identity.uninstall_command))
    return Ownership::unreadable;
  identity.install_location = location;
  DWORD subkeys = 0, values = 0;
  if (RegQueryInfoKeyW(key, nullptr, nullptr, nullptr, &subkeys, nullptr, nullptr,
                      &values, nullptr, nullptr, nullptr, nullptr) != ERROR_SUCCESS)
    return Ownership::unreadable;
  const std::array<const wchar_t *, 10> expected{
      L"DisplayName", L"DisplayVersion", L"Publisher", L"InstallLocation",
      L"DisplayIcon", L"UninstallString", L"QuietUninstallString", L"ModifyPath",
      L"NoModify", L"NoRepair"};
  identity.unexpected_content = subkeys != 0 || values > expected.size();
  for (DWORD index = 0; index < values && !identity.unexpected_content; ++index) {
    std::array<wchar_t, 256> name{};
    DWORD length = static_cast<DWORD>(name.size());
    if (RegEnumValueW(key, index, name.data(), &length, nullptr, nullptr, nullptr, nullptr) != ERROR_SUCCESS)
      return Ownership::unreadable;
    bool recognized = false;
    for (const auto *allowed : expected) recognized = recognized || equal(name.data(), allowed);
    identity.unexpected_content = !recognized;
  }
  return owns_registration(root, identity) ? Ownership::owned : Ownership::foreign;
}

Ownership open_registration(const fs::path &root, Key &key, HANDLE transaction = nullptr) {
  const LSTATUS result = transaction == nullptr
      ? RegOpenKeyExW(HKEY_CURRENT_USER, registry_path, 0, KEY_READ, &key.value)
      : RegOpenKeyTransactedW(HKEY_CURRENT_USER, registry_path, 0,
                             KEY_READ | DELETE, &key.value, transaction, nullptr);
  if (result == ERROR_FILE_NOT_FOUND || result == ERROR_PATH_NOT_FOUND) return Ownership::absent;
  if (result != ERROR_SUCCESS) return Ownership::unreadable;
  return registration_ownership(key.value, root);
}

std::string utf8(const std::wstring &value) {
  if (value.empty()) return {};
  const int count = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value.data(),
      static_cast<int>(value.size()), nullptr, 0, nullptr, nullptr);
  if (count <= 0) return {};
  std::string output(static_cast<std::size_t>(count), '\0');
  WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value.data(),
      static_cast<int>(value.size()), output.data(), count, nullptr, nullptr);
  return output;
}

class WindowsEffects final : public Effects {
public:
  WindowsEffects(fs::path root, fs::path state)
      : root_(std::move(root)), state_(std::move(state)), link_(start_menu_link()) {}

  Ownership inspect(Effect effect) override {
    if (effect == Effect::shortcut) {
      Handle file;
      return open_shortcut(link_, root_, false, file);
    }
    Key key;
    return open_registration(root_, key);
  }

  Result remove_owned(Effect effect) override {
    if (effect == Effect::shortcut) {
      Handle file;
      const auto ownership = open_shortcut(link_, root_, true, file);
      if (ownership == Ownership::absent) return {true, "shortcut already absent"};
      if (ownership != Ownership::owned)
        return {false, "Start Menu shortcut ownership changed or could not be read"};
      FILE_DISPOSITION_INFO disposition{TRUE};
      if (!SetFileInformationByHandle(file.value, FileDispositionInfo,
                                     &disposition, sizeof(disposition)))
        return {false, "Windows could not remove the owned Start Menu shortcut"};
      return {true, "owned shortcut removed"};
    }

    // Inspection and deletion share a registry transaction. A concurrent
    // non-transacted mutation aborts it; failure never falls back to tree deletion.
    Handle transaction;
    transaction.value = CreateTransaction(nullptr, nullptr, 0, 0, 0, 0, nullptr);
    if (transaction.value == INVALID_HANDLE_VALUE)
      return {false, "Windows could not begin an uninstall registration transaction"};
    Key key;
    const auto ownership = open_registration(root_, key, transaction.value);
    if (ownership == Ownership::absent) return {true, "registration already absent"};
    if (ownership != Ownership::owned)
      return {false, "Uninstall registration ownership changed or could not be read"};
    const LSTATUS removed = RegDeleteKeyTransactedW(
        HKEY_CURRENT_USER, registry_path, 0, 0, transaction.value, nullptr);
    if (removed != ERROR_SUCCESS || !CommitTransaction(transaction.value)) {
      RollbackTransaction(transaction.value);
      return {false, "Windows could not commit removal of the owned uninstall registration"};
    }
    return {true, "owned registration removed"};
  }

  Result persist(const RemovalRecord &record) override {
    std::error_code error;
    const fs::path directory = state_ / "integration-receipts";
    fs::create_directories(directory, error);
    if (error) return {false, "integration receipt directory could not be created"};
    core::json::ObjectBuilder document;
    document.add_string("schema", "facman.windows_integration_removal.v1");
    document.add_string("operation", "uninstall");
    document.add_string("scope", "current_user");
    document.add_string("install_root", utf8(root_.wstring()));
    document.add_string("start_menu_link", utf8(link_.wstring()));
    document.add_string("uninstall_registry_key", "HKCU\\" + utf8(registry_path));
    document.add_string("phase", record.phase);
    document.add_string("shortcut", record.shortcut);
    document.add_string("registration", record.registration);
    document.add_string("detail", record.detail);
    return publish_receipt(directory / "uninstall.v1.json", document.serialize() + "\n");
  }

private:
  fs::path root_, state_, link_;
};
} // namespace

bool owns_shortcut(const fs::path &install_root, const ShortcutIdentity &identity) {
  if (!install_root.is_absolute() || !identity.target.is_absolute() ||
      !identity.arguments.empty()) return false;
  const fs::path target = normalized(identity.target);
  const fs::path generation = target.parent_path();
  return equal(target.filename().wstring(), L"FacMan.exe") &&
         !generation.filename().empty() &&
         same_path(generation.parent_path(), normalized(install_root) / "generations") &&
         same_path(generation, identity.working_directory);
}

bool owns_registration(const fs::path &install_root, const RegistrationIdentity &identity) {
  return !identity.unexpected_content && equal(identity.display_name, L"FacMan") &&
         same_path(install_root, identity.install_location) &&
         equal(identity.uninstall_command, uninstall_command(identity.install_location));
}

Result publish_receipt(const fs::path &destination, const std::string &bytes,
                       ReceiptPublishHook before_publish, void *hook_context) {
  if (bytes.size() > 8U * 1024U * 1024U)
    return {false, "integration receipt exceeds its byte limit"};
  std::error_code error;
  const fs::path absolute = fs::absolute(destination, error);
  if (error) return {false, "integration receipt path could not be made absolute"};
  fs::create_directories(absolute.parent_path(), error);
  if (error) return {false, "integration receipt directory could not be created"};
  static std::atomic<unsigned long> sequence{0};
  const fs::path temporary = absolute.parent_path() /
      (absolute.filename().wstring() + L".pending." +
       std::to_wstring(GetCurrentProcessId()) + L"." +
       std::to_wstring(++sequence) + L".tmp");
  Handle file;
  file.value = CreateFileW(temporary.c_str(), GENERIC_WRITE | DELETE, 0,
                          nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
  if (file.value == INVALID_HANDLE_VALUE)
    return {false, "integration receipt could not be opened"};
  DWORD written = 0;
  if (!WriteFile(file.value, bytes.data(), static_cast<DWORD>(bytes.size()), &written, nullptr) ||
      written != bytes.size() || !FlushFileBuffers(file.value))
    return {false, "integration receipt could not be durably written"};
  if (before_publish != nullptr) before_publish(temporary, hook_context);

  // Keep the same exclusive source handle through publication. Reopening a
  // temporary pathname after close could publish another actor's replacement.
  const std::wstring name = absolute.wstring();
  const std::size_t size = sizeof(FILE_RENAME_INFO) + name.size() * sizeof(wchar_t);
  std::vector<unsigned char> storage(size, 0);
  auto *rename = reinterpret_cast<FILE_RENAME_INFO *>(storage.data());
  rename->ReplaceIfExists = TRUE;
  rename->RootDirectory = nullptr;
  rename->FileNameLength = static_cast<DWORD>(name.size() * sizeof(wchar_t));
  std::memcpy(rename->FileName, name.c_str(), (name.size() + 1) * sizeof(wchar_t));
  if (!SetFileInformationByHandle(file.value, FileRenameInfo, rename, static_cast<DWORD>(size)))
    return {false, "integration receipt could not be atomically committed"};
  if (!FlushFileBuffers(file.value))
    return {false, "published integration receipt could not be flushed"};
  // Failures retain the original temporary object; no pathname-based deletion.
  return {true, "integration receipt saved"};
}

Result inspect_existing_windows(const fs::path &install_root) {
  std::error_code error;
  const auto root = fs::absolute(install_root, error);
  if (error) return {false, "install root could not be made absolute"};
  WindowsEffects effects(normalized(root), {});
  for (const auto effect : {Effect::shortcut, Effect::registration}) {
    const auto ownership = effects.inspect(effect);
    if (ownership != Ownership::owned && ownership != Ownership::absent)
      return {false, "Existing Windows integration belongs to another install "
                     "or could not be read; it was preserved"};
  }
  return {true, "existing integration is absent or belongs to this install"};
}

Result remove_windows(const fs::path &install_root, const fs::path &state_root) {
  std::error_code error;
  const auto root = fs::absolute(install_root, error);
  if (error) return {false, "install root could not be made absolute"};
  WindowsEffects effects(normalized(root), state_root);
  return remove(effects);
}
} // namespace facman::setup::integration