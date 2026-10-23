import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bib_extractor.fetch_bibtex import main
from bib_extractor.workflow import print_progress_bar, rename_paper, sanitize_filename, validate_papers


BIB = '@article{samekey,title={Example},author={Smith, John},year={2026}}'


class ValidationTests(unittest.TestCase):
    def test_bad_json_shapes_and_paths(self):
        for papers in [{}, [1], [{}], [{"file": "../outside.pdf"}], [{"file": "..\\outside.pdf"}],
                       [{"file": "C:outside.pdf"}], [{"file": "/outside.pdf"}],
                       [{"file": "a.pdf", "doi": 12}], [{"file": "a.pdf", "title": []}]]:
            with self.subTest(papers=papers):
                with self.assertRaises(ValueError):
                    validate_papers(papers)

    def test_filename_controls_and_windows_device_names(self):
        self.assertEqual(sanitize_filename('A\x00B\x1f:C. '), "ABC")
        self.assertEqual(sanitize_filename("CON"), "_CON")

    def test_empty_progress_bar_does_not_divide_by_zero(self):
        print_progress_bar(0, 0)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = self.root / "input.json"
        self.output = self.root / "out.bib"
        self.report = self.root / "nested" / "report.json"
        self.pdfs = self.root / "papers"
        self.pdfs.mkdir()
        self.input.write_text(json.dumps([{"file": "a.pdf", "doi": "10.1234/a"}]), encoding="utf-8")
        (self.pdfs / "a.pdf").write_bytes(b"original PDF bytes")
        for redirect in [contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO())]:
            redirect.__enter__()
            self.addCleanup(redirect.__exit__, None, None, None)

    def run_cli(self, extra=None, responses=None):
        args = ["--input", str(self.input), "--output", str(self.output), "--report", str(self.report), "--delay", "0"]
        with patch("bib_extractor.fetch_bibtex.fetch_bibtex", side_effect=responses, return_value=BIB) as fetch:
            code = main(args + (extra or []))
        return code, fetch

    def test_success_and_report(self):
        code, _ = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("Example", self.output.read_text(encoding="utf-8"))
        self.assertEqual(json.loads(self.report.read_text(encoding="utf-8"))[0]["status"], "success")

    def test_duplicate_doi_is_fetched_and_written_once(self):
        self.input.write_text(json.dumps([{"file": "a.pdf", "doi": "10.1234/A"},
                                          {"file": "b.pdf", "doi": "10.1234/a"}]), encoding="utf-8")
        code, fetch = self.run_cli()
        self.assertEqual(code, 0)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(self.output.read_text(encoding="utf-8").count("@article"), 1)

    def test_distinct_doi_keys_are_disambiguated(self):
        self.input.write_text(json.dumps([{"file": "a.pdf", "doi": "10.1234/a"},
                                          {"file": "b.pdf", "doi": "10.1234/b"}]), encoding="utf-8")
        self.assertEqual(self.run_cli()[0], 0)
        self.assertIn("@article{samekey_2,", self.output.read_text(encoding="utf-8"))

    def test_partial_failure_keeps_success_and_returns_nonzero(self):
        self.input.write_text(json.dumps([{"file": "a.pdf", "doi": "10.1234/a"},
                                          {"file": "b.pdf", "doi": "10.1234/b"}]), encoding="utf-8")
        code, _ = self.run_cli(responses=[BIB, RuntimeError("offline")])
        self.assertEqual(code, 1)
        self.assertEqual(self.output.read_text(encoding="utf-8").count("@article"), 1)
        self.assertEqual(json.loads(self.report.read_text(encoding="utf-8"))[1]["reason"], "offline")

    def test_no_doi_and_extraction_error_are_reported(self):
        self.input.write_text('[{"file":"a.pdf","title":"A title"},{"file":"b.pdf","error":"encrypted"}]',
                              encoding="utf-8")
        code, fetch = self.run_cli()
        self.assertEqual(code, 1)
        fetch.assert_not_called()
        records = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual(records[1]["reason"], "encrypted")
        self.assertEqual(records[0]["status"], "skipped")

    def test_all_failed_replaces_stale_output_with_empty(self):
        self.output.write_text("stale bibliography", encoding="utf-8")
        self.assertEqual(self.run_cli(responses=RuntimeError("offline"))[0], 1)
        self.assertEqual(self.output.read_text(encoding="utf-8"), "")

    def test_empty_input_is_valid(self):
        self.input.write_text("[]", encoding="utf-8")
        code, fetch = self.run_cli()
        self.assertEqual(code, 0)
        fetch.assert_not_called()

    def test_invalid_input_is_rejected_before_fetch(self):
        for content in ["not json", "{}", '[{"file":"../outside.pdf","doi":"10.1234/a"}]']:
            with self.subTest(content=content):
                self.input.write_text(content, encoding="utf-8")
                code, fetch = self.run_cli()
                self.assertEqual(code, 1)
                fetch.assert_not_called()

    def test_invalid_delay_is_rejected_before_fetch(self):
        for delay in ["-1", "nan", "inf"]:
            with self.subTest(delay=delay):
                code, fetch = self.run_cli(["--delay", delay])
                self.assertEqual(code, 1)
                fetch.assert_not_called()

    def test_aliasing_input_is_rejected_without_modification(self):
        before = self.input.read_bytes()
        code, fetch = self.run_cli(["--output", str(self.input)])
        self.assertEqual(code, 1)
        fetch.assert_not_called()
        self.assertEqual(self.input.read_bytes(), before)

    def test_hardlink_alias_to_input_is_rejected(self):
        alias = self.root / "alias.json"
        os.link(self.input, alias)
        self.assertEqual(self.run_cli(["--output", str(alias)])[0], 1)
        self.assertTrue(self.input.read_text(encoding="utf-8").startswith("["))

    def test_output_paths_must_be_distinct(self):
        code, fetch = self.run_cli(["--citations", str(self.output)])
        self.assertEqual(code, 1)
        fetch.assert_not_called()

    def test_output_pdf_is_refused(self):
        source = self.pdfs / "a.pdf"
        before = source.read_bytes()
        self.assertEqual(self.run_cli(["--output", str(source)])[0], 1)
        self.assertEqual(source.read_bytes(), before)

    def test_missing_rename_directory_is_rejected(self):
        code, fetch = self.run_cli(["--rename"])
        self.assertEqual(code, 1)
        fetch.assert_not_called()

    def test_dry_run_keeps_original_pdf(self):
        code, _ = self.run_cli(["--rename", "--dir", str(self.pdfs), "--dry-run"])
        self.assertEqual(code, 0)
        self.assertEqual([path.name for path in self.pdfs.iterdir()], ["a.pdf"])
        self.assertIn("planned_file", json.loads(self.report.read_text(encoding="utf-8"))[0])

    def test_rename_keeps_bytes(self):
        code, _ = self.run_cli(["--rename", "--dir", str(self.pdfs)])
        self.assertEqual(code, 0)
        renamed = self.pdfs / "2026 - Smith - Example.pdf"
        self.assertEqual(renamed.read_bytes(), b"original PDF bytes")
        self.assertFalse((self.pdfs / "a.pdf").exists())

    def test_collision_preserves_existing_pdf(self):
        existing = self.pdfs / "2026 - Smith - Example.pdf"
        existing.write_bytes(b"different paper")
        self.assertEqual(self.run_cli(["--rename", "--dir", str(self.pdfs)])[0], 0)
        self.assertEqual(existing.read_bytes(), b"different paper")
        self.assertEqual((self.pdfs / "2026 - Smith - Example_1.pdf").read_bytes(), b"original PDF bytes")

    def test_concurrent_collision_retries_without_overwrite(self):
        link = os.link
        calls = []

        def racing_link(source, target):
            calls.append(target)
            if len(calls) == 1:
                Path(target).write_bytes(b"concurrent paper")
            link(source, target)

        with patch("bib_extractor.workflow.os.link", side_effect=racing_link):
            self.assertEqual(self.run_cli(["--rename", "--dir", str(self.pdfs)])[0], 0)
        self.assertEqual(Path(calls[0]).read_bytes(), b"concurrent paper")
        self.assertEqual(Path(calls[1]).read_bytes(), b"original PDF bytes")

    def test_output_failure_prevents_rename(self):
        with patch("bib_extractor.workflow._atomic_write", side_effect=OSError("disk full")):
            self.assertEqual(self.run_cli(["--rename", "--dir", str(self.pdfs)])[0], 1)
        self.assertTrue((self.pdfs / "a.pdf").exists())

    def test_failed_atomic_replace_preserves_previous_output(self):
        self.output.write_text("previous", encoding="utf-8")
        with patch("bib_extractor.workflow.os.replace", side_effect=OSError("disk full")):
            self.assertEqual(self.run_cli()[0], 1)
        self.assertEqual(self.output.read_text(encoding="utf-8"), "previous")
        self.assertFalse(list(self.root.glob("tmp*")))

    def test_rename_failure_keeps_bibliography_and_reports_error(self):
        with patch("bib_extractor.workflow.os.link", side_effect=OSError("hard links unsupported")):
            self.assertEqual(self.run_cli(["--rename", "--dir", str(self.pdfs)])[0], 1)
        self.assertTrue((self.pdfs / "a.pdf").exists())
        self.assertIn("Example", self.output.read_text(encoding="utf-8"))
        self.assertIn("Rename failed", json.loads(self.report.read_text(encoding="utf-8"))[0]["reason"])

    def test_long_unicode_metadata_fits_filename_limit(self):
        target = rename_paper(self.pdfs / "a.pdf", {"author": "আ" * 100, "title": "আ" * 100}, dry_run=True)
        self.assertLessEqual(len(target.name.encode("utf-8")), 255)

    def test_symlink_source_is_refused(self):
        outside = self.root / "outside.pdf"
        outside.write_bytes(b"outside")
        source = self.pdfs / "a.pdf"
        source.unlink()
        try:
            source.symlink_to(outside)
        except OSError:
            self.skipTest("Creating symlinks requires additional privileges on this Windows host")
        code, fetch = self.run_cli(["--rename", "--dir", str(self.pdfs)])
        self.assertEqual(code, 1)
        fetch.assert_not_called()
        self.assertEqual(outside.read_bytes(), b"outside")


if __name__ == "__main__":
    unittest.main()
