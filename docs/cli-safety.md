# Fetching results and renaming PDFs

`bib-fetch --report results.json` writes per-file statuses and failure reasons.
Exit status is 0 on complete success, 1 for processing/output errors or any
skipped paper, and 2 for argparse syntax errors. PDFs without a DOI are reported
as skipped: their extracted title is a candidate for manual lookup, not an
automatic match. Add the verified DOI to the input JSON and retry.

Repeated DOIs (case-insensitive) are fetched and written once, but each associated
PDF can still be renamed. Different DOIs with the same bibliography key receive
distinct keys, for example `Smith2026` and `Smith2026_2`.

Use `--rename --dir papers --dry-run` to preview names. This leaves PDFs alone
but still retrieves metadata and writes the requested bibliography, citations,
and report. Previewed collision suffixes may change by the actual rename time.

Input records must have a PDF basename, never an absolute path or directory
traversal. Symlink PDFs are refused during renaming. Output paths cannot alias
the metadata input, source PDFs, or one another. Bibliography and citation
outputs are saved before renaming starts. Individual writes use a temporary file
and atomic replacement; multiple output files are not one filesystem transaction.
An empty result replaces stale bibliography/citation files with empty files.

Renaming uses an exclusive hard link and then removes the old directory entry,
so even concurrent filename collisions cannot overwrite another PDF. Filesystems
without hard-link support report a rename error and retain the original PDF.
Missing PDFs and rename failures are reported, while fetched references remain
available in the bibliography. Check the final report and exit status.
