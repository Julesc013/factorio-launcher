// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#ifndef FL_TRANSACTION_PACK_IMPORT_H
#define FL_TRANSACTION_PACK_IMPORT_H
#include "fl_transaction.h"
namespace facman::transaction {
bool bind_pack_import_install(Record& record, const std::filesystem::path& workspace,
    const std::string& install_id, const std::vector<std::filesystem::path>& metadata, std::string& detail);
bool verify_pack_import_install(const Record& record, const std::filesystem::path& workspace, std::string& detail);
bool verify_pack_import_tree(const Record& record, const std::filesystem::path& root,
    bool published, std::string& detail);
bool finalize_pack_import(const Record& record, std::string& detail);
// The caller holds the existing transaction recovery lock.
bool recover_pack_import(const std::filesystem::path& workspace, Record& record, std::string& detail);
}
#endif
