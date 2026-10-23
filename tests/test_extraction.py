import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pypdf import PdfWriter

from bib_extractor.extract_bib_info import extract_papers, find_doi, main


class DoiTests(unittest.TestCase):
    def test_doi_variants(self):
        cases = {
            "doi: 10.1234/example.": "10.1234/example",
            "https://doi.org/10.1 234/ example": "10.1234/example",
            "10.1234/example.\n123": "10.1234/example.123",
            "(10.1234/example).": "10.1234/example",
            "10.1002/(SICI)1099-0844(199912)17:4<290::AID-CBF849>3.0.CO;2-P":
                "10.1002/(SICI)1099-0844(199912)17:4<290::AID-CBF849>3.0.CO;2-P",
            "10.1234/exam\u200bple": "10.1234/example",
            "10.1234/exam\u00adple": "10.1234/example",
            "10.1234/example\nIntroduction": "10.1234/example",
            "10.1234/example.\nIntroduction": "10.1234/example",
            "10.123/a": None,
            "10.1234567890/a": None,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(find_doi(text), expected)


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stdout = contextlib.redirect_stdout(io.StringIO())
        self.stdout.__enter__()
        self.addCleanup(self.stdout.__exit__, None, None, None)

    def pdf(self, name, metadata=None):
        path = self.root / name
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        if metadata:
            writer.add_metadata(metadata)
        with path.open("wb") as stream:
            writer.write(stream)
        return path

    def test_real_pdf_metadata_doi_without_text(self):
        self.pdf("scan.pdf", {"/doi": "https://doi.org/10.1234/scan"})
        self.assertEqual(extract_papers(self.root), [{"file": "scan.pdf", "doi": "10.1234/scan"}])

    def test_real_pdf_metadata_title(self):
        self.pdf("scan.PDF", {"/Title": "A useful title"})
        self.assertEqual(extract_papers(self.root), [{"file": "scan.PDF", "title": "A useful title"}])

    def test_directories_named_pdf_are_ignored(self):
        (self.root / "folder.pdf").mkdir()
        self.assertEqual(extract_papers(self.root), [])

    def test_none_text_and_deterministic_sort(self):
        for name in ["b.pdf", "a.pdf", "2.pdf", "1.pdf"]:
            (self.root / name).touch()
        reader = MagicMock()
        reader.metadata = None
        reader.pages = [MagicMock()]
        reader.pages[0].extract_text.return_value = None
        with patch("bib_extractor.extract_bib_info.PdfReader", return_value=reader):
            papers = extract_papers(self.root)
        self.assertEqual([paper["file"] for paper in papers], ["1.pdf", "2.pdf", "a.pdf", "b.pdf"])
        self.assertTrue(all(paper["title"] == "Unknown" for paper in papers))

    def test_first_two_pages_are_separated(self):
        (self.root / "paper.pdf").touch()
        reader = MagicMock()
        reader.metadata = {}
        reader.pages = [MagicMock(), MagicMock(), MagicMock()]
        reader.pages[0].extract_text.return_value = "10.1234/paper"
        reader.pages[1].extract_text.return_value = "Introduction"
        with patch("bib_extractor.extract_bib_info.PdfReader", return_value=reader):
            self.assertEqual(extract_papers(self.root)[0]["doi"], "10.1234/paper")
        reader.pages[2].extract_text.assert_not_called()

    def test_corrupt_pdf_is_reported_and_other_pdfs_continue(self):
        (self.root / "1.pdf").write_bytes(b"not a PDF")
        self.pdf("2.pdf")
        with contextlib.redirect_stderr(io.StringIO()):
            papers = extract_papers(self.root)
        self.assertIn("error", papers[0])
        self.assertEqual(papers[1]["title"], "Unknown")

    def test_missing_directory_returns_failure(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--dir", str(self.root / "missing")]), 1)

    def test_partial_failure_writes_json_and_returns_failure(self):
        (self.root / "bad.pdf").write_bytes(b"broken")
        output = self.root / "results" / "papers.json"
        with contextlib.redirect_stderr(io.StringIO()):
            code = main(["--dir", str(self.root), "--output", str(output)])
        self.assertEqual(code, 1)
        self.assertIn("error", json.loads(output.read_text(encoding="utf-8"))[0])

    def test_output_cannot_overwrite_source_pdf(self):
        source = self.pdf("paper.pdf")
        before = source.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--dir", str(self.root), "--output", str(source)]), 1)
        self.assertEqual(source.read_bytes(), before)

    def test_failed_write_preserves_existing_json(self):
        output = self.root / "output.json"
        output.write_text("previous result", encoding="utf-8")
        with patch("bib_extractor.extract_bib_info.json.dump", side_effect=OSError("disk full")):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["--dir", str(self.root), "--output", str(output)]), 1)
        self.assertEqual(output.read_text(encoding="utf-8"), "previous result")
        self.assertEqual(list(self.root.iterdir()), [output])


if __name__ == "__main__":
    unittest.main()
