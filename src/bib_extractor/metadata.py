"""DOI retrieval and parsing of a single, self-contained BibTeX entry.

This is deliberately not a complete BibTeX processor: external string macros
are rejected rather than silently producing incorrect reference metadata.
"""

import re
import urllib.error
import urllib.parse
import urllib.request


MONTHS = dict(zip(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"),
    ("January", "February", "March", "April", "May", "June", "July", "August", "September",
     "October", "November", "December"),
))


def _value(text, pos):
    """Read one balanced braced, quoted, or numeric BibTeX value."""
    start = pos
    if pos >= len(text):
        raise ValueError("Missing BibTeX field value")
    opener = text[pos]
    if opener not in '{"':
        match = re.match(r"\d+", text[pos:])
        if not match:
            macro = re.match(r"[A-Za-z]+", text[pos:])
            if macro and macro.group().lower() in MONTHS:
                return MONTHS[macro.group().lower()], pos + macro.end()
            raise ValueError("Unsupported BibTeX string macro or malformed value")
        return match.group(), pos + len(match.group())
    depth = 1 if opener == "{" else 0
    pos += 1
    while pos < len(text):
        char = text[pos]
        if char == "\\":
            pos += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if opener == "{" and depth == 0:
                return text[start + 1:pos], pos + 1
            if depth < 0:
                break
        elif char == '"' and opener == '"' and depth == 0:
            return text[start + 1:pos], pos + 1
        pos += 1
    raise ValueError("Unterminated BibTeX field value")


def parse_bibtex(bib):
    """Parse fields without confusing booktitle/title or truncating braces."""
    header = re.match(r"\s*@([A-Za-z]+)\s*([{(])\s*([^,\s{}()]+)\s*,", bib)
    if not header or header.group(1).lower() in ("string", "comment", "preamble"):
        raise ValueError("Expected one BibTeX reference entry")
    closing = "}" if header.group(2) == "{" else ")"
    pos = header.end()
    fields = {}
    while pos < len(bib):
        while pos < len(bib) and bib[pos].isspace():
            pos += 1
        if pos < len(bib) and bib[pos] == closing:
            if bib[pos + 1:].strip():
                raise ValueError("Expected a single BibTeX entry")
            return fields
        field = re.match(r"([A-Za-z][\w:-]*)\s*=\s*", bib[pos:])
        if not field:
            raise ValueError("Malformed BibTeX field")
        name = field.group(1).lower()
        pos += field.end()
        value, pos = _value(bib, pos)
        while True:
            while pos < len(bib) and bib[pos].isspace():
                pos += 1
            if pos >= len(bib) or bib[pos] != "#":
                break
            pos += 1
            while pos < len(bib) and bib[pos].isspace():
                pos += 1
            part, pos = _value(bib, pos)
            value += part
        # Keep author grouping so corporate names containing 'and' survive.
        fields[name] = value.strip() if name == "author" else re.sub(r"(?<!\\)[{}]", "", value).strip()
        if pos < len(bib) and bib[pos] == ",":
            pos += 1
        elif pos >= len(bib) or bib[pos] != closing:
            raise ValueError("Expected a comma or closing delimiter in BibTeX")
    raise ValueError("Unterminated BibTeX entry")


def fetch_bibtex(doi, timeout=10):
    """Fetch valid BibTeX; encode DOI suffixes and report both API failures."""
    doi = doi.strip()
    if not re.match(r"^10\.\d{4,9}/\S+$", doi, re.IGNORECASE):
        raise ValueError("Invalid DOI: {}".format(doi))
    encoded = urllib.parse.quote(doi, safe="/")
    apis = [
        ("doi.org", "https://doi.org/{}".format(encoded)),
        ("Crossref", "https://api.crossref.org/works/{}/transform/application/x-bibtex".format(encoded)),
    ]
    errors = []
    for name, url in apis:
        request = urllib.request.Request(url, headers={
            "Accept": "application/x-bibtex", "User-Agent": "bib-extractor (https://github.com/msrtarit/bib-extractor)",
        })
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    raise ValueError("HTTP {}".format(response.status))
                bib = response.read().decode("utf-8-sig")
                data = parse_bibtex(bib)
                if not data.get("title"):
                    raise ValueError("BibTeX response has no title")
                return bib
        except (urllib.error.URLError, OSError, UnicodeError, ValueError) as exc:
            errors.append("{}: {}".format(name, exc))
    raise RuntimeError("Failed to fetch {} ({})".format(doi, "; ".join(errors)))


def _authors(author):
    """Split only unbraced BibTeX 'and' delimiters."""
    names = []
    start = depth = 0
    pos = 0
    while pos < len(author):
        if author[pos] == "\\":
            pos += 2
            continue
        if author[pos] == "{":
            depth += 1
        elif author[pos] == "}":
            depth -= 1
        separator = re.match(r"\s+and\s+", author[pos:], re.IGNORECASE) if depth == 0 else None
        if separator:
            names.append(author[start:pos].strip())
            pos += separator.end()
            start = pos
        else:
            pos += 1
    names.append(author[start:].strip())
    return [name for name in names if name] or ["Unknown Author"]


def _ieee_author(author):
    if author == "Unknown Author":
        return author
    if author.startswith("{") and author.endswith("}"):
        return author[1:-1]
    parts = [part.strip() for part in author.split(",")]
    if len(parts) > 1:
        last, first = parts[0], parts[-1]
        suffix = ", " + parts[1] if len(parts) > 2 and parts[1] else ""
    else:
        words = author.split()
        if len(words) < 2:
            return author or "Unknown Author"
        first, last, suffix = " ".join(words[:-1]), words[-1], ""
    initials = " ".join(word[0] + "." for word in first.split() if word)
    return " ".join(part for part in (initials, last + suffix) if part)


def generate_citation(bib_data, style="apa"):
    """Produce a simple plain-text reference, not a full CSL style rendering."""
    authors = _authors(bib_data.get("author") or "Unknown Author")
    year = bib_data.get("year") or "n.d."
    title = bib_data.get("title") or "Unknown Title"
    journal = bib_data.get("journal") or bib_data.get("booktitle") or bib_data.get("publisher", "")
    plain = [re.sub(r"(?<!\\)[{}]", "", author) for author in authors]
    if style.lower() == "apa":
        author = ", ".join(plain[:-1]) + " & " + plain[-1] if len(plain) > 1 else plain[0]
        return "{} ({}). {}.{}".format(author, year, title.rstrip("."), " {}.".format(journal) if journal else "")
    if style.lower() == "mla":
        author = ", ".join(plain[:-1]) + ", and " + plain[-1] if len(plain) > 1 else plain[0]
        venue = "{}, ".format(journal) if journal else ""
        return '{}. "{}." {}{}'.format(author, title.rstrip("."), venue, year).rstrip(".") + "."
    if style.lower() == "ieee":
        names = [_ieee_author(author) for author in authors]
        author = ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else names[0]
        prefix = '{}, "{},"'.format(author, title)
        pieces = [journal]
        for field, label in (("volume", "vol."), ("number", "no."), ("pages", "pp.")):
            if bib_data.get(field):
                pieces.append("{} {}".format(label, bib_data[field]))
        pieces.append(year)
        return "{} {}".format(prefix, ", ".join(piece for piece in pieces if piece)).rstrip(".") + "."
    return "{} ({}). {}.".format(" and ".join(plain), year, title)
