# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""FacMan-owned deterministic product composition compiler."""

from .compiler import CompilerInputs, ResolutionFailure, load_inputs, resolve

__all__ = ["CompilerInputs", "ResolutionFailure", "load_inputs", "resolve"]
