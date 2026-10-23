import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from bib_extractor.fetch_bibtex import fetch_bibtex, generate_citation, parse_bibtex


class ParsingTests(unittest.TestCase):
    def test_nested_braces_numbers_and_field_boundaries(self):
        data = parse_bibtex('@article{x, booktitle={Proceedings}, title={A {Nested} Title}, year=2026}')
        self.assertEqual(data, {"booktitle": "Proceedings", "title": "A Nested Title", "year": "2026"})
        self.assertNotIn("title", parse_bibtex('@article{x, booktitle={Proceedings}}'))

    def test_quotes_concatenation_and_case(self):
        data = parse_bibtex('@article(x, TITLE="A {Protected} title" # { continued}, YEAR="2026",)')
        self.assertEqual(data["title"], "A Protected title continued")
        self.assertEqual(data["year"], "2026")

    def test_escaped_braces_and_quotes(self):
        data = parse_bibtex(r'@article{x, title="A \"quoted\" title with \{literal\} braces"}')
        self.assertIn(r'\"quoted\"', data["title"])
        self.assertIn(r'\{literal\}', data["title"])

    def test_malformed_responses_are_not_accepted(self):
        for bib in ["<html>error</html>", "", "@article{x,title={broken}",
                    "@article{x,title=macro}", "@article{x,title={a} year=2026}",
                    "@article{x,title={a}} @article{y,title={b}}"]:
            with self.subTest(bib=bib):
                with self.assertRaises(ValueError):
                    parse_bibtex(bib)


class FetchTests(unittest.TestCase):
    def response(self, body):
        response = MagicMock()
        response.status = 200
        response.read.return_value = body
        response.__enter__.return_value = response
        return response

    def test_reserved_doi_characters_are_encoded(self):
        with patch("urllib.request.urlopen", return_value=self.response(b'@article{x,title={Example}}')) as request:
            fetch_bibtex("10.1234/a?b#c&d", timeout=4)
        self.assertEqual(request.call_args[0][0].full_url, "https://doi.org/10.1234/a%3Fb%23c%26d")
        self.assertEqual(request.call_args.kwargs["timeout"], 4)

    def test_invalid_success_response_uses_fallback(self):
        with patch("urllib.request.urlopen", side_effect=[
            self.response(b"<html>Not BibTeX</html>"), self.response(b'@article{x,title={Example},year=2026}')
        ]) as request:
            self.assertIn("Example", fetch_bibtex("10.1234/a"))
        self.assertEqual(request.call_count, 2)
        self.assertIn("api.crossref.org", request.call_args[0][0].full_url)

    def test_all_failures_have_api_context(self):
        with patch("urllib.request.urlopen", side_effect=URLError("offline")):
            with self.assertRaisesRegex(RuntimeError, "doi.org:.*Crossref:"):
                fetch_bibtex("10.1234/a")

    def test_invalid_doi_never_uses_network(self):
        with patch("urllib.request.urlopen") as request:
            with self.assertRaises(ValueError):
                fetch_bibtex("not a doi")
        request.assert_not_called()


class CitationTests(unittest.TestCase):
    def test_empty_given_name_does_not_crash(self):
        self.assertIn("Smith", generate_citation({"author": "Smith,", "title": "Example"}, "ieee"))

    def test_corporate_authors_and_suffixes(self):
        citation = generate_citation({"author": "{Research and Development Group} and Smith, Jr., John Paul",
                                      "title": "Example", "year": "2026"}, "ieee")
        self.assertIn("Research and Development Group and J. P. Smith, Jr.", citation)

    def test_empty_fields_use_defaults(self):
        for style in ["apa", "mla", "ieee"]:
            with self.subTest(style=style):
                citation = generate_citation({"author": "", "title": "", "year": ""}, style)
                self.assertIn("Unknown Author", citation)
                self.assertIn("Unknown Title", citation)
                self.assertIn("n.d.", citation)

    def test_conference_venue_is_used(self):
        self.assertIn("Proceedings", generate_citation({"booktitle": "Proceedings"}))


if __name__ == "__main__":
    unittest.main()
