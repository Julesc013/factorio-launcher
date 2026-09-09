// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "fl_resource_export_inspection.h"
#include "fl_resource_export_path_policy.h"
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <winternl.h>
#include <chrono>
#include <cstring>
namespace facman::resources::detail {
namespace {
struct Handle {
    HANDLE value = INVALID_HANDLE_VALUE;
    ~Handle() { if (value != INVALID_HANDLE_VALUE && value != nullptr) CloseHandle(value); }
};
using OpenRelative = NTSTATUS (NTAPI*)(PHANDLE, ACCESS_MASK, POBJECT_ATTRIBUTES,
    PIO_STATUS_BLOCK, PLARGE_INTEGER, ULONG, ULONG, ULONG, ULONG, PVOID, ULONG);
DestinationObservation unavailable(const char* detail)
{
    return {"unavailable", "unknown", 0, 0, detail};
}
}
DestinationObservation observe_export_path(const std::filesystem::path& root,
    const std::vector<std::filesystem::path>& components)
{
    // Literal NT-relative opens must never reinterpret a Win32 device spelling.
    for (const auto& component : components)
        if (!windows_export_component_admitted(component.native()))
            return {"unsafe", "unknown", 0, 0, "Ambiguous Win32 component refused"};
    auto drive = root.native();
    if (drive.size() == 3 && drive[2] == L'/') drive[2] = L'\\';
    if (drive.size() != 3 || drive[1] != L':' || drive[2] != L'\\' ||
        !((drive[0] >= L'A' && drive[0] <= L'Z') || (drive[0] >= L'a' && drive[0] <= L'z')) ||
        GetDriveTypeW(drive.c_str()) != DRIVE_FIXED)
        return unavailable("Only a local fixed DOS drive root is supported");
    OpenRelative open_relative = nullptr;
    const auto module = GetModuleHandleW(L"ntdll.dll");
    const auto address = module ? GetProcAddress(module, "NtCreateFile") : nullptr;
    static_assert(sizeof(open_relative) == sizeof(address));
    std::memcpy(&open_relative, &address, sizeof(address));
    if (!open_relative) return unavailable("Relative metadata open is unavailable");
    Handle parent;
    parent.value = CreateFileW(drive.c_str(), FILE_READ_ATTRIBUTES | FILE_TRAVERSE,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr, OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
    if (parent.value == INVALID_HANDLE_VALUE) return unavailable("Drive root metadata open failed");
    const auto start = std::chrono::steady_clock::now();
    for (std::size_t i = 0; i < components.size(); ++i) {
        if (std::chrono::steady_clock::now() - start >= std::chrono::seconds(2))
            return unavailable("Observation time budget exhausted");
        const auto name = components[i].native();
        UNICODE_STRING unicode {};
        unicode.Buffer = const_cast<PWSTR>(name.data());
        unicode.Length = static_cast<USHORT>(name.size() * sizeof(wchar_t));
        unicode.MaximumLength = unicode.Length;
        OBJECT_ATTRIBUTES attributes {};
        attributes.Length = sizeof(attributes);
        attributes.RootDirectory = parent.value;
        attributes.ObjectName = &unicode;
        // Refuse a reparse during relative lookup, including a concurrently
        // changed parent; same local Win32 case lookup convention.
        attributes.Attributes = 0x1040; // OBJ_DONT_REPARSE | OBJ_CASE_INSENSITIVE.
        IO_STATUS_BLOCK io {};
        Handle next;
        // FILE_OPEN (never create), FILE_OPEN_REPARSE_POINT; single component
        // relative to held parent. No file data or directory list access.
        const NTSTATUS status = open_relative(&next.value, FILE_READ_ATTRIBUTES | SYNCHRONIZE |
            (i + 1 < components.size() ? FILE_TRAVERSE : 0),
            &attributes, &io, nullptr, 0, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            1, 0x00200000 | 0x00000020, nullptr, 0);
        if (status < 0) {
            const auto code = static_cast<ULONG>(status);
            if (code == 0xc0000034UL || code == 0xc000003aUL)
                return {"absent", "absent", 0, 0, "Destination or ancestor is absent"};
            if (code == 0xc000050bUL)
                return {"unsafe", "link", 0, 0, "Reparse encountered during relative lookup"};
            return unavailable("Relative destination metadata open failed");
        }
        BY_HANDLE_FILE_INFORMATION info {};
        if (!GetFileInformationByHandle(next.value, &info))
            return unavailable("Held destination metadata query failed");
        if ((info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0)
            return {"unsafe", "link", 0, 0, "Reparse point refused without traversal"};
        if (GetFileType(next.value) != FILE_TYPE_DISK)
            return {"unsafe", "other", 0, 0, "Special object refused"};
        const bool directory = (info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
        if (i + 1 == components.size())
            return {"present", directory ? "directory" : "regular_file", info.dwVolumeSerialNumber,
                (static_cast<std::uint64_t>(info.nFileIndexHigh) << 32U) | info.nFileIndexLow,
                "Sequential destination observation; contents and ownership not inspected"};
        if (!directory) return {"unsafe", "regular_file", 0, 0, "Ancestor is not a directory"};
        CloseHandle(parent.value);
        parent.value = next.value;
        next.value = INVALID_HANDLE_VALUE;
    }
    return unavailable("No destination component");
}
}
