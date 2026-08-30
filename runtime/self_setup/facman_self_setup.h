// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_SELF_SETUP_H
#define FACMAN_SELF_SETUP_H

#include "fl_result.h"

#include <filesystem>
#include <string>

namespace facman::self_setup {

enum class Operation { install, verify, repair, uninstall };

struct Request {
  Operation operation = Operation::verify;
  std::filesystem::path package;
  std::filesystem::path install_root;
  std::filesystem::path state_root;
  std::filesystem::path acceptance_root;
  std::string product_version;
  bool apply = false;
};

struct Response {
  std::string operation;
  std::string phase;
  std::string provider_json;
};

facman::core::Result<Response> execute(const Request &request);
std::string provider_revision();

} // namespace facman::self_setup

#endif
