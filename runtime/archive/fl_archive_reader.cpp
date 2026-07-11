#include "fl_archive.h"

#include "fl_archive_platform.h"
#include "fl_archive_policy.h"
#include "miniz.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstring>
#include <fstream>
#include <limits>
#include <set>
#include <vector>

namespace facman::archive {
namespace {

constexpr std::uint32_t kLocalSignature = 0x04034b50U;
constexpr std::uint32_t kCentralSignature = 0x02014b50U;
constexpr std::uint32_t kDescriptorSignature = 0x08074b50U;
constexpr std::uint32_t kEocdSignature = 0x06054b50U;
constexpr std::uint32_t kZip64EocdSignature = 0x06064b50U;
constexpr std::uint32_t kZip64LocatorSignature = 0x07064b50U;
constexpr std::uint16_t kZip64ExtraId = 0x0001U;

struct RawEntry {
    Entry entry;
    std::uint16_t version_made_by = 0;
    std::uint16_t flags = 0;
};

std::uint16_t le16(const unsigned char* data)
{
    return static_cast<std::uint16_t>(data[0]) |
        (static_cast<std::uint16_t>(data[1]) << 8);
}

std::uint32_t le32(const unsigned char* data)
{
    return static_cast<std::uint32_t>(data[0]) |
        (static_cast<std::uint32_t>(data[1]) << 8) |
        (static_cast<std::uint32_t>(data[2]) << 16) |
        (static_cast<std::uint32_t>(data[3]) << 24);
}

std::uint64_t le64(const unsigned char* data)
{
    return static_cast<std::uint64_t>(le32(data)) |
        (static_cast<std::uint64_t>(le32(data + 4)) << 32);
}

Status read_exact(
    RandomAccessFile& file,
    std::uint64_t offset,
    void* data,
    std::size_t size,
    const char* code)
{
    if (file.read(offset, data, size) != size) {
        return Status::failure(code, "archive is truncated at offset " + std::to_string(offset));
    }
    return Status::success();
}

bool add_within(std::uint64_t left, std::uint64_t right, std::uint64_t limit)
{
    return right <= std::numeric_limits<std::uint64_t>::max() - left && left + right <= limit;
}

Status validate_extra_records(const std::vector<unsigned char>& extra)
{
    std::size_t offset = 0;
    std::set<std::uint16_t> singleton_ids;
    while (offset < extra.size()) {
        if (extra.size() - offset < 4) {
            return Status::failure("archive_extra_malformed", "truncated extra-field header");
        }
        const std::uint16_t id = le16(extra.data() + offset);
        const std::uint16_t size = le16(extra.data() + offset + 2);
        offset += 4;
        if (size > extra.size() - offset) {
            return Status::failure("archive_extra_malformed", "extra-field payload exceeds record");
        }
        if (id == kZip64ExtraId && !singleton_ids.insert(id).second) {
            return Status::failure("archive_zip64_extra_duplicate", "duplicate ZIP64 extra field");
        }
        offset += size;
    }
    return Status::success();
}

Status apply_zip64_extra(
    const std::vector<unsigned char>& extra,
    bool need_expanded,
    bool need_compressed,
    bool need_local_offset,
    bool need_disk,
    std::uint64_t& expanded,
    std::uint64_t& compressed,
    std::uint64_t& local_offset,
    std::uint32_t& disk)
{
    Status status = validate_extra_records(extra);
    if (!status.ok()) {
        return status;
    }
    std::size_t offset = 0;
    while (offset < extra.size()) {
        const std::uint16_t id = le16(extra.data() + offset);
        const std::uint16_t size = le16(extra.data() + offset + 2);
        offset += 4;
        if (id != kZip64ExtraId) {
            offset += size;
            continue;
        }
        std::size_t cursor = offset;
        const std::size_t end = offset + size;
        auto take64 = [&](std::uint64_t& value) -> bool {
            if (end - cursor < 8) return false;
            value = le64(extra.data() + cursor);
            cursor += 8;
            return true;
        };
        if (need_expanded && !take64(expanded)) {
            return Status::failure("archive_zip64_extra_malformed", "missing expanded size");
        }
        if (need_compressed && !take64(compressed)) {
            return Status::failure("archive_zip64_extra_malformed", "missing compressed size");
        }
        if (need_local_offset && !take64(local_offset)) {
            return Status::failure("archive_zip64_extra_malformed", "missing local-header offset");
        }
        if (need_disk) {
            if (end - cursor < 4) {
                return Status::failure("archive_zip64_extra_malformed", "missing disk number");
            }
            disk = le32(extra.data() + cursor);
        }
        return Status::success();
    }
    if (need_expanded || need_compressed || need_local_offset || need_disk) {
        return Status::failure("archive_zip64_extra_missing", "ZIP64 sentinel has no ZIP64 extra field");
    }
    return Status::success();
}

Status locate_central_directory(
    RandomAccessFile& file,
    Plan& plan,
    std::uint64_t& entry_count)
{
    const std::uint64_t tail_size = std::min<std::uint64_t>(file.size(), 65557);
    std::vector<unsigned char> tail(static_cast<std::size_t>(tail_size));
    Status status = read_exact(file, file.size() - tail_size, tail.data(), tail.size(), "archive_eocd_truncated");
    if (!status.ok()) return status;

    std::size_t eocd_in_tail = std::numeric_limits<std::size_t>::max();
    if (tail.size() >= 22) {
        for (std::size_t candidate = tail.size() - 22;; --candidate) {
            if (le32(tail.data() + candidate) == kEocdSignature) {
                const std::uint16_t comment = le16(tail.data() + candidate + 20);
                if (candidate + 22 + comment == tail.size()) {
                    eocd_in_tail = candidate;
                    break;
                }
            }
            if (candidate == 0) break;
        }
    }
    if (eocd_in_tail == std::numeric_limits<std::size_t>::max()) {
        return Status::failure("archive_eocd_missing", "end-of-central-directory record was not found");
    }
    const unsigned char* eocd = tail.data() + eocd_in_tail;
    const std::uint64_t eocd_offset = file.size() - tail_size + eocd_in_tail;
    const std::uint16_t disk = le16(eocd + 4);
    const std::uint16_t central_disk = le16(eocd + 6);
    const std::uint16_t entries_on_disk = le16(eocd + 8);
    const std::uint16_t entries_total = le16(eocd + 10);
    const std::uint32_t central_size32 = le32(eocd + 12);
    const std::uint32_t central_offset32 = le32(eocd + 16);
    const bool needs_zip64 = entries_on_disk == 0xffffU || entries_total == 0xffffU ||
        central_size32 == 0xffffffffU || central_offset32 == 0xffffffffU;

    std::array<unsigned char, 20> locator {};
    bool has_zip64_locator = false;
    if (eocd_offset >= locator.size() &&
        file.read(eocd_offset - locator.size(), locator.data(), locator.size()) == locator.size()) {
        has_zip64_locator = le32(locator.data()) == kZip64LocatorSignature;
    }
    if (disk != 0 || central_disk != 0) {
        return Status::failure("archive_multidisk_unsupported", "EOCD declares a nonzero disk");
    }

    if (!needs_zip64 && !has_zip64_locator) {
        if (entries_on_disk != entries_total) {
            return Status::failure("archive_multidisk_unsupported", "EOCD declares multiple disks");
        }
        entry_count = entries_total;
        plan.central_directory_size = central_size32;
        plan.central_directory_offset = central_offset32;
        plan.zip64 = false;
    } else {
        if (eocd_offset < 20) {
            return Status::failure("archive_zip64_locator_missing", "ZIP64 locator is truncated");
        }
        if (!has_zip64_locator || le32(locator.data() + 4) != 0 ||
            le32(locator.data() + 16) != 1) {
            return Status::failure("archive_multidisk_unsupported", "invalid or multi-disk ZIP64 locator");
        }
        const std::uint64_t zip64_offset = le64(locator.data() + 8);
        std::array<unsigned char, 56> zip64 {};
        status = read_exact(file, zip64_offset, zip64.data(), zip64.size(), "archive_zip64_eocd_truncated");
        if (!status.ok()) return status;
        const std::uint64_t zip64_record_size = le64(zip64.data() + 4);
        if (le32(zip64.data()) != kZip64EocdSignature || zip64_record_size < 44 ||
            le32(zip64.data() + 16) != 0 || le32(zip64.data() + 20) != 0 ||
            le64(zip64.data() + 24) != le64(zip64.data() + 32)) {
            return Status::failure("archive_multidisk_unsupported", "invalid or multi-disk ZIP64 EOCD");
        }
        entry_count = le64(zip64.data() + 32);
        plan.central_directory_size = le64(zip64.data() + 40);
        plan.central_directory_offset = le64(zip64.data() + 48);
        if (zip64_record_size > std::numeric_limits<std::uint64_t>::max() - 12 ||
            !add_within(zip64_offset, 12 + zip64_record_size, eocd_offset - locator.size()) ||
            zip64_offset + 12 + zip64_record_size != eocd_offset - locator.size()) {
            return Status::failure("archive_zip64_eocd_bounds", "ZIP64 EOCD does not end at its locator");
        }
        if ((entries_on_disk != 0xffffU && entries_on_disk != entry_count) ||
            (entries_total != 0xffffU && entries_total != entry_count) ||
            (central_size32 != 0xffffffffU && central_size32 != plan.central_directory_size) ||
            (central_offset32 != 0xffffffffU && central_offset32 != plan.central_directory_offset)) {
            return Status::failure("archive_zip64_eocd_mismatch", "classic and ZIP64 EOCD records disagree");
        }
        plan.zip64 = true;
        if (!add_within(plan.central_directory_offset, plan.central_directory_size, zip64_offset)) {
            return Status::failure("archive_central_directory_bounds", "central directory overlaps ZIP64 EOCD");
        }
        return Status::success();
    }
    if (!add_within(plan.central_directory_offset, plan.central_directory_size, eocd_offset)) {
        return Status::failure("archive_central_directory_bounds", "central directory overlaps or exceeds EOCD");
    }
    return Status::success();
}

Status descriptor_end(
    RandomAccessFile& file,
    const Entry& entry,
    std::uint64_t descriptor_offset,
    std::uint64_t central_offset,
    bool prefer_zip64,
    std::uint64_t& end)
{
    const std::uint64_t available = central_offset > descriptor_offset ? central_offset - descriptor_offset : 0;
    const std::size_t wanted = static_cast<std::size_t>(std::min<std::uint64_t>(24, available));
    std::array<unsigned char, 24> bytes {};
    if (wanted < 12 || file.read(descriptor_offset, bytes.data(), wanted) != wanted) {
        return Status::failure("archive_descriptor_truncated", entry.path);
    }
    std::array<std::size_t, 2> cursors = {0, 0};
    std::size_t cursor_count = 1;
    if (le32(bytes.data()) == kDescriptorSignature) {
        cursors = {4, 0};
        cursor_count = 2;
    }
    for (std::size_t cursor_index = 0; cursor_index < cursor_count; ++cursor_index) {
        const std::size_t cursor = cursors[cursor_index];
        if (prefer_zip64 && wanted >= cursor + 20 && le32(bytes.data() + cursor) == entry.crc32 &&
            le64(bytes.data() + cursor + 4) == entry.compressed_size &&
            le64(bytes.data() + cursor + 12) == entry.expanded_size) {
            end = descriptor_offset + cursor + 20;
            return Status::success();
        }
        if (wanted >= cursor + 12 && le32(bytes.data() + cursor) == entry.crc32 &&
            le32(bytes.data() + cursor + 4) == entry.compressed_size &&
            le32(bytes.data() + cursor + 8) == entry.expanded_size) {
            end = descriptor_offset + cursor + 12;
            return Status::success();
        }
        if (wanted >= cursor + 20 && le32(bytes.data() + cursor) == entry.crc32 &&
            le64(bytes.data() + cursor + 4) == entry.compressed_size &&
            le64(bytes.data() + cursor + 12) == entry.expanded_size) {
            end = descriptor_offset + cursor + 20;
            return Status::success();
        }
    }
    return Status::failure("archive_descriptor_mismatch", entry.path);
}

Status validate_local_header(
    RandomAccessFile& file,
    const RawEntry& raw,
    std::uint64_t central_offset,
    Entry& entry)
{
    std::array<unsigned char, 30> local {};
    Status status = read_exact(file, entry.local_header_offset, local.data(), local.size(), "archive_local_header_truncated");
    if (!status.ok()) return status;
    if (le32(local.data()) != kLocalSignature) {
        return Status::failure("archive_local_header_signature", entry.path);
    }
    const std::uint16_t flags = le16(local.data() + 6);
    const std::uint16_t method = le16(local.data() + 8);
    const std::uint16_t name_size = le16(local.data() + 26);
    const std::uint16_t extra_size = le16(local.data() + 28);
    if (flags != raw.flags || method != (entry.method == CompressionMethod::stored ? 0 : 8)) {
        return Status::failure("archive_local_central_mismatch", entry.path);
    }
    if ((flags & 0x0001U) != 0 || (flags & 0x0040U) != 0) {
        return Status::failure("archive_entry_encrypted", entry.path);
    }
    const std::uint64_t variable_offset = entry.local_header_offset + local.size();
    const std::uint64_t variable_size = static_cast<std::uint64_t>(name_size) + extra_size;
    if (!add_within(variable_offset, variable_size, central_offset)) {
        return Status::failure("archive_local_header_bounds", entry.path);
    }
    std::vector<unsigned char> variable(static_cast<std::size_t>(variable_size));
    status = read_exact(file, variable_offset, variable.data(), variable.size(), "archive_local_header_truncated");
    if (!status.ok()) return status;
    const std::string local_name(variable.begin(), variable.begin() + name_size);
    if (local_name != entry.path) {
        return Status::failure("archive_local_name_mismatch", entry.path);
    }
    std::vector<unsigned char> extra(variable.begin() + name_size, variable.end());
    std::uint64_t local_expanded = le32(local.data() + 22);
    std::uint64_t local_compressed = le32(local.data() + 18);
    const bool local_zip64 = local_expanded == 0xffffffffU || local_compressed == 0xffffffffU;
    std::uint64_t unused_offset = 0;
    std::uint32_t unused_disk = 0;
    status = apply_zip64_extra(
        extra,
        local_expanded == 0xffffffffU,
        local_compressed == 0xffffffffU,
        false,
        false,
        local_expanded,
        local_compressed,
        unused_offset,
        unused_disk);
    if (!status.ok()) return status;

    entry.data_offset = variable_offset + variable_size;
    if (!add_within(entry.data_offset, entry.compressed_size, central_offset)) {
        return Status::failure("archive_entry_data_bounds", entry.path);
    }
    const std::uint64_t compressed_end = entry.data_offset + entry.compressed_size;
    if ((flags & 0x0008U) != 0) {
        return descriptor_end(file, entry, compressed_end, central_offset, local_zip64, entry.occupied_end);
    }
    if (le32(local.data() + 14) != entry.crc32 || local_expanded != entry.expanded_size ||
        local_compressed != entry.compressed_size) {
        return Status::failure("archive_local_size_crc_mismatch", entry.path);
    }
    entry.occupied_end = compressed_end;
    return Status::success();
}

Status parse_entries(
    RandomAccessFile& file,
    const Limits& limits,
    std::uint64_t entry_count,
    Plan& plan)
{
    if (entry_count > limits.maximum_entry_count || entry_count > std::numeric_limits<std::uint32_t>::max()) {
        return Status::failure("archive_entry_count_limit", std::to_string(entry_count));
    }
    CollisionTracker collisions;
    std::vector<RawEntry> raw_entries;
    std::uint64_t cursor = plan.central_directory_offset;
    const std::uint64_t central_end = plan.central_directory_offset + plan.central_directory_size;
    for (std::uint64_t index = 0; index < entry_count; ++index) {
        std::array<unsigned char, 46> fixed {};
        Status status = read_exact(file, cursor, fixed.data(), fixed.size(), "archive_central_header_truncated");
        if (!status.ok()) return status;
        if (le32(fixed.data()) != kCentralSignature) {
            return Status::failure("archive_central_header_signature", std::to_string(index));
        }
        const std::uint16_t name_size = le16(fixed.data() + 28);
        const std::uint16_t extra_size = le16(fixed.data() + 30);
        const std::uint16_t comment_size = le16(fixed.data() + 32);
        const std::uint64_t variable_size = static_cast<std::uint64_t>(name_size) + extra_size + comment_size;
        if (!add_within(cursor + fixed.size(), variable_size, central_end)) {
            return Status::failure("archive_central_header_bounds", std::to_string(index));
        }
        std::vector<unsigned char> variable(static_cast<std::size_t>(variable_size));
        status = read_exact(file, cursor + fixed.size(), variable.data(), variable.size(), "archive_central_header_truncated");
        if (!status.ok()) return status;

        RawEntry raw;
        raw.entry.index = static_cast<std::uint32_t>(index);
        raw.version_made_by = le16(fixed.data() + 4);
        raw.flags = le16(fixed.data() + 8);
        raw.entry.path.assign(variable.begin(), variable.begin() + name_size);
        raw.entry.directory = !raw.entry.path.empty() && raw.entry.path.back() == '/';
        const std::uint16_t method = le16(fixed.data() + 10);
        if (method != 0 && method != 8) {
            return Status::failure("archive_method_unsupported", raw.entry.path);
        }
        raw.entry.method = method == 0 ? CompressionMethod::stored : CompressionMethod::deflate;
        if ((raw.flags & 0x0001U) != 0 || (raw.flags & 0x0040U) != 0) {
            return Status::failure("archive_entry_encrypted", raw.entry.path);
        }
        raw.entry.crc32 = le32(fixed.data() + 16);
        raw.entry.compressed_size = le32(fixed.data() + 20);
        raw.entry.expanded_size = le32(fixed.data() + 24);
        raw.entry.external_attributes = le32(fixed.data() + 38);
        raw.entry.local_header_offset = le32(fixed.data() + 42);
        std::uint32_t disk = le16(fixed.data() + 34);
        std::vector<unsigned char> extra(
            variable.begin() + name_size,
            variable.begin() + name_size + extra_size);
        status = apply_zip64_extra(
            extra,
            raw.entry.expanded_size == 0xffffffffU,
            raw.entry.compressed_size == 0xffffffffU,
            raw.entry.local_header_offset == 0xffffffffU,
            disk == 0xffffU,
            raw.entry.expanded_size,
            raw.entry.compressed_size,
            raw.entry.local_header_offset,
            disk);
        if (!status.ok()) return status;
        if (disk != 0) {
            return Status::failure("archive_multidisk_unsupported", raw.entry.path);
        }
        PathKeys keys;
        status = validate_archive_path(raw.entry.path, raw.entry.directory, limits, keys);
        if (!status.ok()) return status;
        status = validate_external_attributes(
            raw.entry.path,
            raw.entry.directory,
            raw.version_made_by,
            raw.entry.external_attributes);
        if (!status.ok()) return status;
        status = collisions.add(keys, raw.entry.directory);
        if (!status.ok()) return status;
        status = enforce_entry_limits(
            raw.entry.compressed_size,
            raw.entry.expanded_size,
            plan.total_expanded_size,
            limits);
        if (!status.ok()) return status;
        raw_entries.push_back(raw);
        cursor += fixed.size() + variable_size;
    }
    if (cursor != central_end) {
        return Status::failure("archive_central_directory_size_mismatch", std::to_string(central_end - cursor));
    }

    std::vector<std::pair<std::uint64_t, std::uint64_t>> ranges;
    plan.entries.clear();
    for (RawEntry& raw : raw_entries) {
        Status status = validate_local_header(file, raw, plan.central_directory_offset, raw.entry);
        if (!status.ok()) return status;
        ranges.push_back({raw.entry.local_header_offset, raw.entry.occupied_end});
        plan.entries.push_back(raw.entry);
    }
    std::sort(ranges.begin(), ranges.end());
    for (std::size_t index = 1; index < ranges.size(); ++index) {
        if (ranges[index].first < ranges[index - 1].second) {
            return Status::failure("archive_entry_ranges_overlap", std::to_string(ranges[index].first));
        }
    }
    return Status::success();
}

std::size_t miniz_read(void* opaque, mz_uint64 offset, void* buffer, std::size_t size)
{
    return static_cast<RandomAccessFile*>(opaque)->read(offset, buffer, size);
}

Status open_miniz_reader(
    const std::filesystem::path& path,
    RandomAccessFile& file,
    mz_zip_archive& zip)
{
    Status status = file.open(path);
    if (!status.ok()) return status;
    std::memset(&zip, 0, sizeof(zip));
    zip.m_pRead = miniz_read;
    zip.m_pIO_opaque = &file;
    if (!mz_zip_reader_init(&zip, file.size(), 0)) {
        return Status::failure("archive_miniz_reader_init_failed", mz_zip_get_error_string(zip.m_last_error));
    }
    return Status::success();
}

Status consume_entry(
    mz_zip_archive& zip,
    const Entry& entry,
    const Limits& limits,
    const DataSink& sink,
    const std::chrono::steady_clock::time_point& started)
{
    if (entry.directory) return Status::success();
    mz_zip_archive_file_stat stat {};
    if (!mz_zip_reader_file_stat(&zip, entry.index, &stat) || stat.m_is_encrypted || !stat.m_is_supported ||
        stat.m_crc32 != entry.crc32 || stat.m_comp_size != entry.compressed_size ||
        stat.m_uncomp_size != entry.expanded_size || stat.m_method != (entry.method == CompressionMethod::stored ? 0 : 8)) {
        return Status::failure("archive_miniz_metadata_mismatch", entry.path);
    }
    mz_zip_reader_extract_iter_state* iterator = mz_zip_reader_extract_iter_new(&zip, entry.index, 0);
    if (iterator == nullptr) {
        return Status::failure("archive_extract_begin_failed", mz_zip_get_error_string(zip.m_last_error));
    }
    std::array<unsigned char, 64 * 1024> buffer {};
    std::uint64_t consumed = 0;
    bool sink_ok = true;
    while (consumed < entry.expanded_size) {
        const std::size_t count = mz_zip_reader_extract_iter_read(iterator, buffer.data(), buffer.size());
        if (count == 0) break;
        consumed += count;
        if (consumed > entry.expanded_size || !sink(buffer.data(), count)) {
            sink_ok = false;
            break;
        }
        const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - started).count();
        if (elapsed >= static_cast<long long>(limits.maximum_read_milliseconds)) {
            sink_ok = false;
            break;
        }
    }
    const bool iterator_ok = mz_zip_reader_extract_iter_free(iterator) != MZ_FALSE;
    if (!sink_ok) {
        return Status::failure("archive_read_limit_or_sink_failed", entry.path);
    }
    if (!iterator_ok || consumed != entry.expanded_size) {
        return Status::failure("archive_crc_or_size_verification_failed", entry.path);
    }
    return Status::success();
}

Status verify_contents(const Plan& plan, const Limits& limits)
{
    RandomAccessFile file;
    mz_zip_archive zip {};
    Status status = open_miniz_reader(plan.archive_path, file, zip);
    if (!status.ok()) return status;
    if (zip.m_total_files != plan.entries.size()) {
        mz_zip_reader_end(&zip);
        return Status::failure("archive_miniz_entry_count_mismatch", std::to_string(zip.m_total_files));
    }
    const auto started = std::chrono::steady_clock::now();
    const DataSink discard = [](const unsigned char*, std::size_t) { return true; };
    for (const Entry& entry : plan.entries) {
        status = consume_entry(zip, entry, limits, discard, started);
        if (!status.ok()) break;
    }
    if (!mz_zip_reader_end(&zip) && status.ok()) {
        return Status::failure("archive_reader_close_failed", "Miniz reader cleanup failed");
    }
    return status;
}

} // namespace

Status inspect_archive(
    const std::filesystem::path& archive_path,
    const Limits& limits,
    Plan& plan)
{
    plan = {};
    plan.archive_path = archive_path;
    RandomAccessFile file;
    Status status = file.open(archive_path);
    if (!status.ok()) return status;
    plan.archive_size = file.size();
    if (plan.archive_size > limits.maximum_archive_bytes) {
        return Status::failure("archive_size_limit", std::to_string(plan.archive_size));
    }
    std::uint64_t entry_count = 0;
    status = locate_central_directory(file, plan, entry_count);
    if (!status.ok()) return status;
    status = parse_entries(file, limits, entry_count, plan);
    if (!status.ok()) return status;
    return verify_contents(plan, limits);
}

Status stream_entry(
    const Plan& plan,
    std::uint32_t entry_index,
    const Limits& limits,
    const DataSink& sink)
{
    if (entry_index >= plan.entries.size()) {
        return Status::failure("archive_entry_index_invalid", std::to_string(entry_index));
    }
    RandomAccessFile file;
    mz_zip_archive zip {};
    Status status = open_miniz_reader(plan.archive_path, file, zip);
    if (!status.ok()) return status;
    const auto started = std::chrono::steady_clock::now();
    status = consume_entry(zip, plan.entries[entry_index], limits, sink, started);
    if (!mz_zip_reader_end(&zip) && status.ok()) {
        return Status::failure("archive_reader_close_failed", "Miniz reader cleanup failed");
    }
    return status;
}

Status extract_to_new_owned_staging(
    const Plan& plan,
    const std::filesystem::path& staging_root,
    const Limits& limits)
{
    Status status = create_owned_staging_root(staging_root);
    if (!status.ok()) return status;
    auto fail = [&](Status failure) {
        const Status cleanup = cleanup_owned_staging_root(staging_root);
        if (!cleanup.ok()) {
            failure.detail += "; cleanup: " + cleanup.detail;
        }
        return failure;
    };
    for (const Entry& entry : plan.entries) {
        const std::filesystem::path destination = staging_root / std::filesystem::u8path(entry.path);
        std::error_code error;
        if (entry.directory) {
            if (!std::filesystem::create_directories(destination, error) && error) {
                return fail(Status::failure("archive_extract_directory_failed", error.message()));
            }
            continue;
        }
        std::filesystem::create_directories(destination.parent_path(), error);
        if (error || std::filesystem::exists(destination, error)) {
            return fail(Status::failure("archive_extract_target_collision", destination.u8string()));
        }
        std::ofstream output(destination, std::ios::binary | std::ios::out);
        if (!output) {
            return fail(Status::failure("archive_extract_output_create_failed", destination.u8string()));
        }
        status = stream_entry(plan, entry.index, limits, [&](const unsigned char* data, std::size_t size) {
            output.write(reinterpret_cast<const char*>(data), static_cast<std::streamsize>(size));
            return static_cast<bool>(output);
        });
        output.flush();
        const bool output_ok = static_cast<bool>(output);
        output.close();
        if (!status.ok()) return fail(status);
        if (!output_ok || output.fail()) {
            return fail(Status::failure("archive_extract_output_flush_failed", destination.u8string()));
        }
    }
    return Status::success();
}

} // namespace facman::archive
