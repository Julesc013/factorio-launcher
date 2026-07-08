from __future__ import annotations

import unittest

from tools import gui_surface_check


class GuiSurfaceTests(unittest.TestCase):
    def test_gui_surface_check(self) -> None:
        self.assertEqual(gui_surface_check.main(), 0)


if __name__ == "__main__":
    unittest.main()
