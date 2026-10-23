"""Small public-interface checks that also run against the original baseline."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bib_extractor.fetch_bibtex import parse_bibtex, rename_paper


class SmokeTests(unittest.TestCase):
    def test_both_module_commands_have_help(self):
        for module in ("bib_extractor", "bib_extractor.fetch_bibtex"):
            with self.subTest(module=module):
                result = subprocess.run([sys.executable, "-m", module, "--help"],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("--output", result.stdout)

    def test_simple_bibtex_entry(self):
        self.assertEqual(parse_bibtex('@article{x,title={Example},year={2026}}')["year"], "2026")

    def test_rename_collision_preserves_both_files(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "paper.pdf"
            source.write_bytes(b"source")
            existing = Path(directory) / "2026 - Smith - Example.pdf"
            existing.write_bytes(b"existing")
            target = rename_paper(source, {"year": "2026", "author": "Smith", "title": "Example"})
            self.assertEqual(existing.read_bytes(), b"existing")
            self.assertEqual(target.read_bytes(), b"source")
            self.assertNotEqual(existing, target)


if __name__ == "__main__":
    unittest.main()
