# Metadata and citation scope

DOI requests percent-encode reserved URL characters and try doi.org followed by
Crossref. A successful HTTP response must contain a single BibTeX entry with a
title; HTML/error responses fall through to the next provider. If both fail,
the exception includes the provider names and error details.

The metadata parser supports nested braces, quoted strings, escaped characters,
numeric values, and concatenation of literal values. It preserves the original
BibTeX response for bibliography output. It rejects malformed entries, multiple
entries, and external string macros rather than guessing their meanings. It is
intended for individual API responses, not arbitrary user-authored .bib files.

APA, MLA, and IEEE text output remains a simplified convenience reference. It is
not a complete implementation of any style manual, does not render all LaTeX
commands, and should be checked before submission. Use the original BibTeX with
a suitable LaTeX bibliography style for publication requirements.
