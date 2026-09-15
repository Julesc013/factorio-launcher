// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "windows_integration.h"
#include "fl_json.h"
#include "fl_path_safety.h"

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

fs::path expanded_long_path(const fs::path &path) {
  const fs::path lexical = normalized(path);
  std::vector<wchar_t> buffer(32768U, L'\0');
  fs::path existing = lexical;
  fs::path suffix;
  while (!existing.empty()) {
    const DWORD length = GetLongPathNameW(
        existing.c_str(), buffer.data(), static_cast<DWORD>(buffer.size()));
    if (length != 0U && length < buffer.size()) {
      return normalized(fs::path(std::wstring(buffer.data(), length)) / suffix);
    }
    if (existing == existing.root_path()) break;
    suffix = existing.filename() / suffix;
    existing = existing.parent_path();
  }
  return lexical;
}

bool same_path(const fs::path &left, const fs::path &right) {
  std::string detail;
  return left.is_absolute() && right.is_absolute() &&
         !facman::base::path_crosses_link_or_reparse_point(left, detail) &&
         !facman::base::path_crosses_link_or_reparse_point(right, detail) &&
         equal(expanded_long_path(left).wstring(),
               expanded_long_path(right).wstring());
}

std::wstring quoted(const fs::path &path) {
  const std::wstring value = normalized(path).wstring();
  std::wstring result(1, L'"');
  std::size_t backslashes = 0;
  for (const wchar_t character : value) {
    if (character == L'\\') {
      ++backslashes;
      continue;
    }
    result.append(character == L'"' ? backslashes * 2U + 1U : backslashes,
                  L'\\');
    result.push_back(character);
    backslashes = 0;
  }
  result.append(backslashes * 2U, L'\\');
  result.push_back(L'"');
  return result;
}

fs::path maintenance_launcher(const MaintenanceContext &context) {
  if (context.repair_source.empty() ||
      context.repair_source.extension() != ".zip") return {};
  return context.repair_source.parent_path() /
      fs::path(context.repair_source.stem().wstring() + L".FacManSetup.exe");
}

std::wstring uninstall_command(const MaintenanceContext &context) {
  return quoted(maintenance_launcher(context)) + L" uninstall --root " +
      quoted(context.install_root) + L" --state-root " +
      quoted(context.state_root) + L" --acceptance-root " +
      quoted(context.acceptance_root) +
      L" --yes --noninteractive --shell-integration";
}

std::wstring modify_command(const MaintenanceContext &context) {
  return quoted(maintenance_launcher(context)) + L" repair --package " +
      quoted(context.repair_source) + L" --root " +
      quoted(context.install_root) + L" --state-root " +
      quoted(context.state_root) + L" --acceptance-root " +
      quoted(context.acceptance_root) +
      L" --yes --noninteractive --shell-integration";
}

std::wstring legacy_uninstall_command(const MaintenanceContext &context) {
  const fs::path maintenance = normalized(context.install_root) /
      "maintenance" / "FacManSetup.exe";
  return quoted(maintenance) + L" uninstall --yes";
}

bool owns_current_registration(const MaintenanceContext &context,
                               const RegistrationIdentity &identity) {
  return !identity.unexpected_content && equal(identity.display_name, L"FacMan") &&
         same_path(context.install_root, identity.install_location) &&
         equal(identity.uninstall_command, uninstall_command(context));
}

bool owns_legacy_registration(const MaintenanceContext &context,
                              const RegistrationIdentity &identity) {
  return !identity.unexpected_content && equal(identity.display_name, L"FacMan") &&
         same_path(context.install_root, identity.install_location) &&
         equal(identity.uninstall_command, legacy_uninstall_command(context));
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
  LARGE_INTEGER file_start{};
  if (!SetFilePointerEx(file, file_start, nullptr, FILE_BEGIN)) return false;
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

Ownership registration_ownership(HKEY key, const MaintenanceContext &context) {
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
  if (owns_current_registration(context, identity)) return Ownership::owned;
  return owns_legacy_registration(context, identity)
      ? Ownership::owned_stale : Ownership::foreign;
}

Ownership open_registration(const MaintenanceContext &context, Key &key,
                            HANDLE transaction = nullptr) {
  const LSTATUS result = transaction == nullptr
      ? RegOpenKeyExW(HKEY_CURRENT_USER, registry_path, 0, KEY_READ, &key.value)
      : RegOpenKeyTransactedW(HKEY_CURRENT_USER, registry_path, 0,
                             KEY_READ | DELETE, &key.value, transaction, nullptr);
  if (result == ERROR_FILE_NOT_FOUND || result == ERROR_PATH_NOT_FOUND) return Ownership::absent;
  if (result != ERROR_SUCCESS) return Ownership::unreadable;
  return registration_ownership(key.value, context);
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

std::wstring wide(const std::string &value) {
  if (value.empty()) return {};
  const int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS,
      value.data(), static_cast<int>(value.size()), nullptr, 0);
  if (count <= 0) return {};
  std::wstring output(static_cast<std::size_t>(count), L'\0');
  MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(),
      static_cast<int>(value.size()), output.data(), count);
  return output;
}

bool set_registry_string(HKEY key, const wchar_t *name, const std::wstring &value) {
  return RegSetValueExW(key, name, 0, REG_SZ,
      reinterpret_cast<const BYTE *>(value.c_str()),
      static_cast<DWORD>((value.size() + 1) * sizeof(wchar_t))) == ERROR_SUCCESS;
}

bool set_registry_dword(HKEY key, const wchar_t *name, DWORD value) {
  return RegSetValueExW(key, name, 0, REG_DWORD,
      reinterpret_cast<const BYTE *>(&value), sizeof(value)) == ERROR_SUCCESS;
}

bool registry_dword(HKEY key, const wchar_t *name, DWORD expected) {
  DWORD type = 0, bytes = sizeof(DWORD), value = 0;
  return RegQueryValueExW(key, name, nullptr, &type,
      reinterpret_cast<BYTE *>(&value), &bytes) == ERROR_SUCCESS &&
      type == REG_DWORD && bytes == sizeof(DWORD) && value == expected;
}

bool desired_registration(HKEY key, const MaintenanceContext &context,
                          const std::string &product_version) {
  const fs::path root = normalized(context.install_root);
  const fs::path generation = root / "generations" / wide(product_version);
  const fs::path gui = generation / "FacMan.exe";
  const std::wstring uninstall = uninstall_command(context);
  std::wstring display_name, display_version, publisher, install_location,
      display_icon, uninstall_string, quiet_uninstall, modify_path;
  return registry_string(key, L"DisplayName", display_name) && display_name == L"FacMan" &&
      registry_string(key, L"DisplayVersion", display_version) && display_version == wide(product_version) &&
      registry_string(key, L"Publisher", publisher) && publisher == L"Jules C" &&
      registry_string(key, L"InstallLocation", install_location) && equal(install_location, root.wstring()) &&
      registry_string(key, L"DisplayIcon", display_icon) && display_icon == L"\"" + gui.wstring() + L"\"" &&
      registry_string(key, L"UninstallString", uninstall_string) && uninstall_string == uninstall &&
      registry_string(key, L"QuietUninstallString", quiet_uninstall) && quiet_uninstall == uninstall + L" --json" &&
      registry_string(key, L"ModifyPath", modify_path) && modify_path == modify_command(context) &&
      registry_dword(key, L"NoModify", 1) && registry_dword(key, L"NoRepair", 0) &&
      registration_ownership(key, context) == Ownership::owned;
}

CutoverOwnership shortcut_cutover_ownership(
    HANDLE file, const CutoverContext &context) {
  ShortcutIdentity identity;
  if (!read_shortcut(file, identity)) return CutoverOwnership::unreadable;
  const fs::path old_generation = normalized(context.source.install_root) /
      "generations" / wide(context.source_version);
  const fs::path new_generation = normalized(context.target.install_root) /
      "generations" / wide(context.target_version);
  if (same_path(identity.target, old_generation / "FacMan.exe") &&
      same_path(identity.working_directory, old_generation) &&
      identity.arguments.empty()) return CutoverOwnership::old_exact;
  if (same_path(identity.target, new_generation / "FacMan.exe") &&
      same_path(identity.working_directory, new_generation) &&
      identity.arguments.empty()) return CutoverOwnership::new_exact;
  if (owns_shortcut(context.source.install_root, identity) ||
      owns_shortcut(context.target.install_root, identity))
    return CutoverOwnership::facman_owned_other;
  return CutoverOwnership::foreign;
}

CutoverOwnership open_cutover_shortcut(const fs::path &path,
                                       const CutoverContext &context,
                                       bool removing, Handle &file) {
  file.value = CreateFileW(path.c_str(), GENERIC_READ | (removing ? DELETE : 0),
      FILE_SHARE_READ, nullptr, OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT,
      nullptr);
  if (file.value == INVALID_HANDLE_VALUE) {
    const DWORD problem = GetLastError();
    return problem == ERROR_FILE_NOT_FOUND || problem == ERROR_PATH_NOT_FOUND
        ? CutoverOwnership::absent : CutoverOwnership::unreadable;
  }
  return shortcut_cutover_ownership(file.value, context);
}

CutoverOwnership registration_cutover_ownership(
    HKEY key, const CutoverContext &context) {
  if (desired_registration(key, context.source, context.source_version))
    return CutoverOwnership::old_exact;
  if (desired_registration(key, context.target, context.target_version))
    return CutoverOwnership::new_exact;
  const Ownership old = registration_ownership(key, context.source);
  const Ownership target = registration_ownership(key, context.target);
  if (old == Ownership::unreadable || target == Ownership::unreadable)
    return CutoverOwnership::unreadable;
  if (old == Ownership::owned || old == Ownership::owned_stale ||
      target == Ownership::owned || target == Ownership::owned_stale)
    return CutoverOwnership::facman_owned_other;
  return CutoverOwnership::foreign;
}

CutoverOwnership open_cutover_registration(const CutoverContext &context,
                                            Key &key,
                                            HANDLE transaction = nullptr) {
  const LSTATUS result = transaction == nullptr
      ? RegOpenKeyExW(HKEY_CURRENT_USER, registry_path, 0, KEY_READ, &key.value)
      : RegOpenKeyTransactedW(HKEY_CURRENT_USER, registry_path, 0,
                             KEY_READ | KEY_WRITE, &key.value, transaction,
                             nullptr);
  if (result == ERROR_FILE_NOT_FOUND || result == ERROR_PATH_NOT_FOUND)
    return CutoverOwnership::absent;
  if (result != ERROR_SUCCESS) return CutoverOwnership::unreadable;
  return registration_cutover_ownership(key.value, context);
}

bool shortcut_bytes(const fs::path &target, const fs::path &working_directory,
                    std::vector<unsigned char> &bytes, std::string &detail) {
  Apartment apartment;
  IShellLinkW *shell_link = nullptr;
  HRESULT status = CoCreateInstance(CLSID_ShellLink, nullptr, CLSCTX_INPROC_SERVER,
                                    IID_IShellLinkW, reinterpret_cast<void **>(&shell_link));
  if (FAILED(status) || shell_link == nullptr) {
    detail = "Windows could not create the Start Menu shortcut object";
    return false;
  }
  status = shell_link->SetPath(target.c_str());
  if (SUCCEEDED(status)) status = shell_link->SetWorkingDirectory(working_directory.c_str());
  if (SUCCEEDED(status)) status = shell_link->SetDescription(L"FacMan");
  IPersistStream *persist = nullptr;
  if (SUCCEEDED(status)) status = shell_link->QueryInterface(
      IID_IPersistStream, reinterpret_cast<void **>(&persist));
  IStream *stream = nullptr;
  if (SUCCEEDED(status)) status = CreateStreamOnHGlobal(nullptr, TRUE, &stream);
  if (SUCCEEDED(status) && persist != nullptr) status = persist->Save(stream, TRUE);
  STATSTG stat{};
  if (SUCCEEDED(status)) status = stream->Stat(&stat, STATFLAG_NONAME);
  HGLOBAL memory = nullptr;
  if (SUCCEEDED(status)) {
    memory = nullptr;
    status = GetHGlobalFromStream(stream, &memory);
  }
  if (SUCCEEDED(status) && (stat.cbSize.QuadPart == 0 || stat.cbSize.QuadPart > 1024 * 1024)) status = E_FAIL;
  if (SUCCEEDED(status)) {
    void *data = GlobalLock(memory);
    if (data == nullptr) status = E_FAIL;
    else { bytes.assign(static_cast<unsigned char *>(data), static_cast<unsigned char *>(data) + stat.cbSize.QuadPart); GlobalUnlock(memory); }
  }
  if (persist != nullptr) persist->Release();
  if (stream != nullptr) stream->Release();
  shell_link->Release();
  if (FAILED(status)) {
    detail = "Windows could not serialize the FacMan Start Menu shortcut";
    return false;
  }
  return true;
}

struct PreparedShortcut {
  HANDLE handle = INVALID_HANDLE_VALUE;
  ~PreparedShortcut() {
    if (handle != INVALID_HANDLE_VALUE) {
      FILE_DISPOSITION_INFO disposition{TRUE};
      (void)SetFileInformationByHandle(handle, FileDispositionInfo, &disposition, sizeof(disposition));
      CloseHandle(handle);
    }
  }
};

bool rename_open_file_no_replace(HANDLE file, const fs::path &destination);

bool prepare_shortcut(const fs::path &target, const fs::path &working_directory,
                      const fs::path &link, PreparedShortcut &prepared,
                      std::string &detail) {
  std::vector<unsigned char> bytes;
  if (!shortcut_bytes(target, working_directory, bytes, detail)) return false;
  const fs::path temporary = link.parent_path() / (link.filename().wstring() +
      L".facman-pending." + std::to_wstring(GetCurrentProcessId()) + L"." +
      std::to_wstring(GetTickCount64()));
  prepared.handle = CreateFileW(temporary.c_str(), GENERIC_WRITE | DELETE,
      0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
  if (prepared.handle == INVALID_HANDLE_VALUE) { detail = "Windows could not create an exclusive shortcut temporary"; return false; }
  DWORD written = 0;
  if (!WriteFile(prepared.handle, bytes.data(), static_cast<DWORD>(bytes.size()), &written, nullptr) ||
      written != bytes.size() || !FlushFileBuffers(prepared.handle)) {
    detail = "Windows could not durably write the shortcut temporary"; return false;
  }
  return true;
}

bool publish_prepared_shortcut(PreparedShortcut &prepared, const fs::path &link) {
  if (!rename_open_file_no_replace(prepared.handle, link)) return false;
  CloseHandle(prepared.handle); prepared.handle = INVALID_HANDLE_VALUE;
  return true;
}

bool create_shortcut(const fs::path &target, const fs::path &working_directory,
                     const fs::path &link, std::string &detail) {
  PreparedShortcut prepared;
  return prepare_shortcut(target, working_directory, link, prepared, detail) &&
      publish_prepared_shortcut(prepared, link);
}

bool rename_open_file_no_replace(HANDLE file, const fs::path &destination) {
  const std::wstring name = destination.wstring();
  std::vector<unsigned char> bytes(sizeof(FILE_RENAME_INFO) +
      name.size() * sizeof(wchar_t));
  auto *info = reinterpret_cast<FILE_RENAME_INFO *>(bytes.data());
  info->ReplaceIfExists = FALSE;
  info->RootDirectory = nullptr;
  info->FileNameLength = static_cast<DWORD>(name.size() * sizeof(wchar_t));
  std::memcpy(info->FileName, name.data(), info->FileNameLength);
  return SetFileInformationByHandle(file, FileRenameInfo, info,
                                    static_cast<DWORD>(bytes.size())) != FALSE;
}

Result replace_stale_shortcut(const fs::path &link, const fs::path &root,
                              const fs::path &target,
                              const fs::path &working_directory) {
  PreparedShortcut prepared;
  std::string detail;
  if (!prepare_shortcut(target, working_directory, link, prepared, detail))
    return {false, detail, true};
  Handle existing;
  if (open_shortcut(link, root, true, existing) != Ownership::owned)
    return {false, "Start Menu shortcut changed before stale-owned replacement", true};
  const fs::path backup = link.parent_path() /
      (link.filename().wstring() + L".facman-backup." +
       std::to_wstring(GetCurrentProcessId()) + L"." +
       std::to_wstring(GetTickCount64()));
  if (!rename_open_file_no_replace(existing.value, backup))
    return {false, "Windows could not bind the stale shortcut to a private backup", true};
  if (!publish_prepared_shortcut(prepared, link)) {
    detail = "Windows could not publish the replacement Start Menu shortcut";
    // This is no-replace restoration through the same opened file.  If a
    // foreign caller has occupied the destination, retain our backup rather
    // than overwrite it and force durable recovery.
    if (!rename_open_file_no_replace(existing.value, link))
      detail += "; stale shortcut backup was retained for recovery";
    return {false, detail, true};
  }
  FILE_DISPOSITION_INFO disposition{TRUE};
  if (!SetFileInformationByHandle(existing.value, FileDispositionInfo,
                                  &disposition, sizeof(disposition)))
    return {false, "new shortcut was published but stale shortcut backup could not be retired", true};
  return {true, "owned shortcut updated"};
}

fs::path cutover_backup(const fs::path &link, const std::string &operation_id) {
  return link.parent_path() /
      fs::path(link.filename().wstring() + L".facman-backup." +
               wide(operation_id));
}

Result cutover_shortcut(const fs::path &link,
                        const CutoverContext &context) {
  std::string identifier_detail;
  if (!facman::base::validate_identifier(context.operation_id,
                                         identifier_detail))
    return {false, "shortcut cutover operation id is invalid", true};
  const fs::path backup = cutover_backup(link, context.operation_id);
  Handle backup_file;
  const CutoverOwnership backup_state = open_cutover_shortcut(
      backup, context, true, backup_file);
  Handle current;
  CutoverOwnership current_state = open_cutover_shortcut(
      link, context, true, current);
  if (backup_state != CutoverOwnership::absent &&
      backup_state != CutoverOwnership::old_exact)
    return {false, "operation-bound shortcut backup is foreign or unreadable", true};
  if (current_state == CutoverOwnership::new_exact) {
    // Retain the deterministic backup until the activation record is durable.
    return {true, "exact target shortcut is already active"};
  }
  if (current_state != CutoverOwnership::old_exact &&
      !(current_state == CutoverOwnership::absent &&
        backup_state == CutoverOwnership::old_exact))
    return {false, "Start Menu shortcut is not the exact reviewed source", true};

  const fs::path generation = normalized(context.target.install_root) /
      "generations" / wide(context.target_version);
  PreparedShortcut prepared;
  std::string detail;
  if (!prepare_shortcut(generation / "FacMan.exe", generation, link,
                        prepared, detail))
    return {false, detail, true};
  if (backup_state == CutoverOwnership::absent) {
    if (!rename_open_file_no_replace(current.value, backup))
      return {false, "source shortcut could not be bound to its durable backup", true};
    CloseHandle(current.value);
    current.value = INVALID_HANDLE_VALUE;
  }
  if (!publish_prepared_shortcut(prepared, link))
    return {false, "target shortcut could not be published; source backup was retained", true};
  Handle observed;
  if (open_cutover_shortcut(link, context, false, observed) !=
      CutoverOwnership::new_exact)
    return {false, "published target shortcut could not be verified", true};
  return {true, "exact Start Menu shortcut cutover completed"};
}

Result cutover_registration(const CutoverContext &context) {
  Handle transaction;
  transaction.value = CreateTransaction(nullptr, nullptr, 0, 0, 0, 0, nullptr);
  if (transaction.value == INVALID_HANDLE_VALUE)
    return {false, "Windows could not begin registration cutover", true};
  Key key;
  const CutoverOwnership current = open_cutover_registration(
      context, key, transaction.value);
  if (current == CutoverOwnership::new_exact)
    return {true, "exact target registration is already active"};
  if (current != CutoverOwnership::old_exact) {
    RollbackTransaction(transaction.value);
    return {false, "uninstall registration is not the exact reviewed source", true};
  }
  const fs::path root = normalized(context.target.install_root);
  const fs::path gui = root / "generations" /
      wide(context.target_version) / "FacMan.exe";
  const std::wstring uninstall = uninstall_command(context.target);
  const bool written =
      set_registry_string(key.value, L"DisplayName", L"FacMan") &&
      set_registry_string(key.value, L"DisplayVersion", wide(context.target_version)) &&
      set_registry_string(key.value, L"Publisher", L"Jules C") &&
      set_registry_string(key.value, L"InstallLocation", root.wstring()) &&
      set_registry_string(key.value, L"DisplayIcon", L"\"" + gui.wstring() + L"\"") &&
      set_registry_string(key.value, L"UninstallString", uninstall) &&
      set_registry_string(key.value, L"QuietUninstallString", uninstall + L" --json") &&
      set_registry_string(key.value, L"ModifyPath", modify_command(context.target)) &&
      set_registry_dword(key.value, L"NoModify", 1) &&
      set_registry_dword(key.value, L"NoRepair", 0);
  if (!written || !CommitTransaction(transaction.value)) {
    RollbackTransaction(transaction.value);
    return {false, "Windows could not commit exact registration cutover", true};
  }
  Key observed;
  if (open_cutover_registration(context, observed) !=
      CutoverOwnership::new_exact)
    return {false, "committed target registration could not be verified", true};
  return {true, "exact per-user registration cutover completed"};
}

Result write_registration_transacted(const MaintenanceContext &context,
                                     const fs::path &gui,
                                     const std::string &product_version) {
  const fs::path root = normalized(context.install_root);
  Handle transaction;
  transaction.value = CreateTransaction(nullptr, nullptr, 0, 0, 0, 0, nullptr);
  if (transaction.value == INVALID_HANDLE_VALUE)
    return {false, "Windows could not begin a per-user uninstall registration transaction", true};
  Key key;
  DWORD disposition = 0;
  const LSTATUS opened = RegCreateKeyTransactedW(
      HKEY_CURRENT_USER, registry_path, 0, nullptr, REG_OPTION_NON_VOLATILE,
      KEY_READ | KEY_WRITE, nullptr, &key.value, &disposition,
      transaction.value, nullptr);
  if (opened != ERROR_SUCCESS)
    return {false, "Windows could not open the per-user uninstall registration transaction", true};
  if (disposition != REG_CREATED_NEW_KEY) {
    const Ownership current = registration_ownership(key.value, context);
    if (current != Ownership::owned && current != Ownership::owned_stale) {
      RollbackTransaction(transaction.value);
      return {false, "per-user uninstall registration changed to a foreign or unreadable object", true};
    }
  }
  const std::wstring uninstall = uninstall_command(context);
  const bool written =
      set_registry_string(key.value, L"DisplayName", L"FacMan") &&
      set_registry_string(key.value, L"DisplayVersion", wide(product_version)) &&
      set_registry_string(key.value, L"Publisher", L"Jules C") &&
      set_registry_string(key.value, L"InstallLocation", root.wstring()) &&
      set_registry_string(key.value, L"DisplayIcon", L"\"" + gui.wstring() + L"\"") &&
      set_registry_string(key.value, L"UninstallString", uninstall) &&
      set_registry_string(key.value, L"QuietUninstallString", uninstall + L" --json") &&
      set_registry_string(key.value, L"ModifyPath", modify_command(context)) &&
      set_registry_dword(key.value, L"NoModify", 1) && set_registry_dword(key.value, L"NoRepair", 0);
  if (!written || !CommitTransaction(transaction.value)) {
    RollbackTransaction(transaction.value);
    return {false, "Windows could not commit the per-user uninstall registration update", true};
  }
  return {true, "owned uninstall registration installed"};
}

class WindowsEffects final : public Effects {
public:
  WindowsEffects(MaintenanceContext context, fs::path link = {})
      : context_(std::move(context)), root_(normalized(context_.install_root)),
        state_(context_.state_root),
        link_(link.empty() ? start_menu_link() : std::move(link)) {}

  Ownership inspect(Effect effect) override {
    if (effect == Effect::shortcut) {
      Handle file;
      return open_shortcut(link_, root_, false, file);
    }
    Key key;
    return open_registration(context_, key);
  }

  Ownership inspect_desired(Effect effect, const std::string &product_version) {
    if (product_version.empty()) return inspect(effect);
    if (effect == Effect::shortcut) {
      Handle file;
      const Ownership ownership = open_shortcut(link_, root_, false, file);
      if (ownership != Ownership::owned) return ownership;
      ShortcutIdentity identity;
      if (!read_shortcut(file.value, identity)) return Ownership::unreadable;
      const fs::path generation = root_ / "generations" / wide(product_version);
      return same_path(identity.target, generation / "FacMan.exe") &&
              same_path(identity.working_directory, generation) &&
              identity.arguments.empty() ? Ownership::owned : Ownership::owned_stale;
    }
    Key key;
    const Ownership ownership = open_registration(context_, key);
    if (ownership != Ownership::owned) return ownership;
    return desired_registration(key.value, context_, product_version)
        ? Ownership::owned : Ownership::owned_stale;
  }

  Result remove_owned(Effect effect) override {
    if (effect == Effect::shortcut) {
      Handle file;
      const auto ownership = open_shortcut(link_, root_, true, file);
      if (ownership == Ownership::absent) return {true, "shortcut already absent"};
      if (ownership != Ownership::owned && ownership != Ownership::owned_stale)
        return {false, "Start Menu shortcut ownership changed or could not be read", true};
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
    const auto ownership = open_registration(context_, key, transaction.value);
    if (ownership == Ownership::absent) return {true, "registration already absent"};
    if (ownership != Ownership::owned && ownership != Ownership::owned_stale)
      return {false, "Uninstall registration ownership changed or could not be read", true};
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
  MaintenanceContext context_;
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

bool owns_registration(const MaintenanceContext &context,
                       const RegistrationIdentity &identity) {
  return owns_current_registration(context, identity) ||
         owns_legacy_registration(context, identity);
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

Result inspect_existing_windows(const MaintenanceContext &context) {
  std::error_code error;
  const auto root = fs::absolute(context.install_root, error);
  if (error) return {false, "install root could not be made absolute"};
  MaintenanceContext normalized_context = context;
  normalized_context.install_root = normalized(root);
  WindowsEffects effects(std::move(normalized_context));
  for (const auto effect : {Effect::shortcut, Effect::registration}) {
    const auto ownership = effects.inspect(effect);
    if (ownership != Ownership::owned && ownership != Ownership::owned_stale &&
        ownership != Ownership::absent)
      return {false, "Existing Windows integration belongs to another install "
                     "or could not be read; it was preserved"};
  }
  return {true, "existing integration is absent or belongs to this install"};
}

Result remove_windows(const MaintenanceContext &context) {
  std::error_code error;
  const auto root = fs::absolute(context.install_root, error);
  if (error) return {false, "install root could not be made absolute"};
  MaintenanceContext normalized_context = context;
  normalized_context.install_root = normalized(root);
  WindowsEffects effects(std::move(normalized_context));
  return remove(effects);
}

Ownership inspect_windows_effect(Effect effect, const MaintenanceContext &context,
                                 const std::string &product_version,
                                 bool remove) {
  std::error_code error;
  const auto root = fs::absolute(context.install_root, error);
  if (error) return Ownership::unreadable;
  MaintenanceContext normalized_context = context;
  normalized_context.install_root = normalized(root);
  WindowsEffects effects(std::move(normalized_context));
  return remove ? effects.inspect(effect)
                : effects.inspect_desired(effect, product_version);
}

Result apply_windows_effect(Effect effect, const MaintenanceContext &context,
                            const std::string &product_version, bool remove) {
  std::error_code error;
  const auto root = fs::absolute(context.install_root, error);
  if (error) return {false, "install root could not be made absolute"};
  const fs::path normalized_root = normalized(root);
  MaintenanceContext normalized_context = context;
  normalized_context.install_root = normalized_root;
  WindowsEffects effects(normalized_context);
  if (remove) return effects.remove_owned(effect);
  const Ownership ownership = effects.inspect_desired(effect, product_version);
  if (ownership == Ownership::foreign || ownership == Ownership::unreadable)
    return {false, "Windows integration ownership changed or could not be read", true};
  const fs::path generation = normalized_root / "generations" / wide(product_version);
  const fs::path gui = generation / "FacMan.exe";
  const fs::path maintenance = normalized_root / "maintenance" / "FacManSetup.exe";
  const fs::path repair_source = normalized(context.repair_source);
  const fs::path launcher = normalized(maintenance_launcher(context));
  if (!fs::is_regular_file(gui, error) || error ||
      !fs::is_regular_file(maintenance, error) || error ||
      !fs::is_regular_file(repair_source, error) || error ||
      !fs::is_regular_file(launcher, error) || error)
    return {false, "installed FacMan or retained maintenance inputs are missing"};
  if (effect == Effect::shortcut) {
    const fs::path link = start_menu_link();
    if (link.empty()) return {false, "Windows could not resolve the current-user Start Menu"};
    fs::create_directories(link.parent_path(), error);
    if (error) return {false, "Windows could not create the Start Menu directory"};
    if (ownership == Ownership::owned_stale)
      return replace_stale_shortcut(link, normalized_root, gui, generation);
    std::string detail;
    return create_shortcut(gui, generation, link, detail) ? Result{true, "owned shortcut installed"}
                                                         : Result{false, detail, true};
  }
  return write_registration_transacted(normalized_context, gui, product_version);
}

CutoverOwnership inspect_windows_cutover_effect(
    Effect effect, const CutoverContext &context) {
  std::error_code status;
  CutoverContext normalized_context = context;
  normalized_context.source.install_root =
      fs::absolute(context.source.install_root, status).lexically_normal();
  if (status) return CutoverOwnership::unreadable;
  normalized_context.target.install_root =
      fs::absolute(context.target.install_root, status).lexically_normal();
  if (status) return CutoverOwnership::unreadable;
  if (effect == Effect::shortcut) {
    Handle file;
    return open_cutover_shortcut(start_menu_link(), normalized_context, false,
                                 file);
  }
  Key key;
  return open_cutover_registration(normalized_context, key);
}

Result apply_windows_cutover_effect(Effect effect,
                                    const CutoverContext &context) {
  std::error_code status;
  CutoverContext normalized_context = context;
  normalized_context.source.install_root =
      fs::absolute(context.source.install_root, status).lexically_normal();
  if (status) return {false, "source install root could not be made absolute", true};
  normalized_context.target.install_root =
      fs::absolute(context.target.install_root, status).lexically_normal();
  if (status) return {false, "target install root could not be made absolute", true};
  const fs::path target_generation = normalized_context.target.install_root /
      "generations" / wide(context.target_version);
  const fs::path target_gui = target_generation / "FacMan.exe";
  const fs::path target_maintenance = normalized_context.target.install_root /
      "maintenance" / "FacManSetup.exe";
  const fs::path retained_source = normalized(context.target.repair_source);
  const fs::path external_helper = normalized(maintenance_launcher(context.target));
  if (!fs::is_regular_file(target_gui, status) || status ||
      !fs::is_regular_file(target_maintenance, status) || status ||
      !fs::is_regular_file(retained_source, status) || status ||
      !fs::is_regular_file(external_helper, status) || status)
    return {false, "target generation or retained maintenance identity is missing", true};
  if (effect == Effect::shortcut) {
    const fs::path link = start_menu_link();
    if (link.empty()) return {false, "Windows could not resolve the current-user Start Menu", true};
    return cutover_shortcut(link, normalized_context);
  }
  return cutover_registration(normalized_context);
}

Ownership inspect_windows_shortcut_fixture(const fs::path &shortcut,
                                           const fs::path &install_root,
                                           const std::string &product_version) {
  std::error_code error;
  const auto root = fs::absolute(install_root, error);
  if (error || shortcut.empty()) return Ownership::unreadable;
  WindowsEffects effects({normalized(root), {}, {}, {}}, shortcut);
  return effects.inspect_desired(Effect::shortcut, product_version);
}

Result apply_windows_shortcut_fixture(const fs::path &shortcut,
                                      const fs::path &install_root,
                                      const std::string &product_version,
                                      bool remove) {
  std::error_code error;
  const auto root = fs::absolute(install_root, error);
  if (error || shortcut.empty()) return {false, "shortcut fixture root could not be made absolute"};
  const fs::path normalized_root = normalized(root);
  WindowsEffects effects({normalized_root, {}, {}, {}}, shortcut);
  if (remove) return effects.remove_owned(Effect::shortcut);
  const Ownership ownership = effects.inspect_desired(Effect::shortcut, product_version);
  if (ownership == Ownership::foreign || ownership == Ownership::unreadable)
    return {false, "Windows integration ownership changed or could not be read", true};
  const fs::path generation = normalized_root / "generations" / wide(product_version);
  const fs::path gui = generation / "FacMan.exe";
  const fs::path maintenance = normalized_root / "maintenance" / "FacManSetup.exe";
  if (!fs::is_regular_file(gui, error) || error || !fs::is_regular_file(maintenance, error) || error)
    return {false, "installed FacMan or maintenance entrypoint is missing"};
  if (!fs::create_directories(shortcut.parent_path(), error) && error)
    return {false, "Windows could not create the shortcut fixture directory"};
  std::string detail;
  if (!create_shortcut(gui, generation, shortcut, detail)) return {false, detail, true};
  return {true, "owned shortcut installed"};
}

CutoverOwnership inspect_windows_shortcut_cutover_fixture(
    const fs::path &shortcut, const CutoverContext &context) {
  if (shortcut.empty()) return CutoverOwnership::unreadable;
  Handle file;
  return open_cutover_shortcut(shortcut, context, false, file);
}

Result apply_windows_shortcut_cutover_fixture(
    const fs::path &shortcut, const CutoverContext &context) {
  if (shortcut.empty()) return {false, "shortcut fixture path is empty", true};
  return cutover_shortcut(shortcut, context);
}
} // namespace facman::setup::integration
