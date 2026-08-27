// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "command_dispatch.h"
#include "facman_client_c.h"

#ifdef _WIN32
#include <stdio.h>
#include <stdlib.h>
#include <windows.h>

static char* facman_utf8_argument(const wchar_t* value)
{
    int required;
    char* result;

    if (value == NULL) return NULL;
    required = WideCharToMultiByte(
        CP_UTF8, WC_ERR_INVALID_CHARS, value, -1, NULL, 0, NULL, NULL);
    if (required <= 0) return NULL;
    result = (char*)malloc((size_t)required);
    if (result == NULL) return NULL;
    if (WideCharToMultiByte(
            CP_UTF8, WC_ERR_INVALID_CHARS, value, -1, result, required, NULL, NULL) <= 0) {
        free(result);
        return NULL;
    }
    return result;
}

int wmain(int argc, wchar_t** argv)
{
    char** utf8_argv;
    int index;
    int result;

    utf8_argv = (char**)calloc((size_t)argc + 1, sizeof(*utf8_argv));
    if (utf8_argv == NULL) {
        fputs("facman: cannot allocate UTF-8 command line\n", stderr);
        return 1;
    }
    for (index = 0; index < argc; ++index) {
        utf8_argv[index] = facman_utf8_argument(argv[index]);
        if (utf8_argv[index] == NULL) {
            int cleanup;
            fputs("facman: command line contains invalid Unicode\n", stderr);
            for (cleanup = 0; cleanup < index; ++cleanup) free(utf8_argv[cleanup]);
            free(utf8_argv);
            return 1;
        }
    }

    facman_client_initialize_process(argc > 0 ? utf8_argv[0] : NULL);
    result = flaunch_dispatch_command(argc, utf8_argv);
    for (index = 0; index < argc; ++index) free(utf8_argv[index]);
    free(utf8_argv);
    return result;
}
#else
int main(int argc, char** argv)
{
    facman_client_initialize_process(argc > 0 ? argv[0] : 0);
    return flaunch_dispatch_command(argc, argv);
}
#endif
