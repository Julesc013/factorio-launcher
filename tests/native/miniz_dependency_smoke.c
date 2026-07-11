// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "miniz.h"

#include <stdio.h>
#include <string.h>

static int prove_deflate_validation_and_streaming(void)
{
    static const char archive_name[] = "unicode-\xE2\x98\x83/payload.txt";
    static const char payload[] = "FacMan miniz admission smoke\n";
    mz_zip_archive writer;
    mz_zip_archive reader;
    mz_zip_archive_file_stat entry;
    mz_zip_reader_extract_iter_state *iterator;
    void *archive_bytes = NULL;
    size_t archive_size = 0;
    char extracted[sizeof(payload)] = {0};
    size_t extracted_size = 0;

    memset(&writer, 0, sizeof(writer));
    if (!mz_zip_writer_init_heap(&writer, 0, 0)) return 2;
    if (!mz_zip_writer_add_mem(
            &writer,
            archive_name,
            payload,
            sizeof(payload) - 1,
            MZ_BEST_COMPRESSION)) {
        mz_zip_writer_end(&writer);
        return 3;
    }
    if (!mz_zip_writer_finalize_heap_archive(&writer, &archive_bytes, &archive_size)) {
        mz_zip_writer_end(&writer);
        return 4;
    }
    if (!mz_zip_writer_end(&writer)) {
        mz_free(archive_bytes);
        return 5;
    }

    memset(&reader, 0, sizeof(reader));
    if (!mz_zip_reader_init_mem(&reader, archive_bytes, archive_size, 0)) {
        mz_free(archive_bytes);
        return 6;
    }
    if (!mz_zip_validate_archive(&reader, 0)) {
        mz_zip_reader_end(&reader);
        mz_free(archive_bytes);
        return 7;
    }
    if (!mz_zip_reader_file_stat(&reader, 0, &entry) ||
        entry.m_method != MZ_DEFLATED || entry.m_is_encrypted ||
        strcmp(entry.m_filename, archive_name) != 0) {
        mz_zip_reader_end(&reader);
        mz_free(archive_bytes);
        return 8;
    }
    iterator = mz_zip_reader_extract_iter_new(&reader, 0, 0);
    if (!iterator) {
        mz_zip_reader_end(&reader);
        mz_free(archive_bytes);
        return 9;
    }
    while (extracted_size < sizeof(extracted) - 1) {
        size_t count = mz_zip_reader_extract_iter_read(
            iterator,
            extracted + extracted_size,
            3);
        if (count == 0) break;
        extracted_size += count;
    }
    if (!mz_zip_reader_extract_iter_free(iterator) ||
        extracted_size != sizeof(payload) - 1 || strcmp(extracted, payload) != 0) {
        mz_zip_reader_end(&reader);
        mz_free(archive_bytes);
        return 10;
    }
    if (!mz_zip_reader_end(&reader)) {
        mz_free(archive_bytes);
        return 11;
    }
    mz_free(archive_bytes);
    return 0;
}

static int prove_forced_zip64_read_write(void)
{
    static const char payload[] = "zip64\n";
    mz_zip_archive writer;
    mz_zip_archive reader;
    mz_zip_archive_file_stat entry;
    void *archive_bytes = NULL;
    size_t archive_size = 0;
    char extracted[sizeof(payload)] = {0};

    memset(&writer, 0, sizeof(writer));
    if (!mz_zip_writer_init_heap_v2(&writer, 0, 0, MZ_ZIP_FLAG_WRITE_ZIP64)) return 20;
    if (!mz_zip_writer_add_mem(
            &writer,
            "zip64.txt",
            payload,
            sizeof(payload) - 1,
            MZ_NO_COMPRESSION)) {
        mz_zip_writer_end(&writer);
        return 21;
    }
    if (!mz_zip_writer_finalize_heap_archive(&writer, &archive_bytes, &archive_size)) {
        mz_zip_writer_end(&writer);
        return 22;
    }
    if (!mz_zip_writer_end(&writer)) {
        mz_free(archive_bytes);
        return 23;
    }
    memset(&reader, 0, sizeof(reader));
    if (!mz_zip_reader_init_mem(&reader, archive_bytes, archive_size, 0) ||
        !mz_zip_is_zip64(&reader) ||
        !mz_zip_reader_file_stat(&reader, 0, &entry) ||
        entry.m_method != 0 ||
        !mz_zip_reader_extract_to_mem(
            &reader,
            0,
            extracted,
            sizeof(extracted) - 1,
            0) ||
        strcmp(extracted, payload) != 0) {
        mz_zip_reader_end(&reader);
        mz_free(archive_bytes);
        return 24;
    }
    if (!mz_zip_reader_end(&reader)) {
        mz_free(archive_bytes);
        return 25;
    }
    mz_free(archive_bytes);
    return 0;
}

int main(void)
{
    int result = prove_deflate_validation_and_streaming();
    if (result != 0) return result;
    result = prove_forced_zip64_read_write();
    if (result != 0) return result;
    printf("miniz-dependency-smoke: %s\n", mz_version());
    return 0;
}
