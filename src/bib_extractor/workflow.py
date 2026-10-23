"""Validated CLI processing and file operations for bib-fetch."""

import argparse
import json
import math
import os
import re
import sys
import tempfile
import time
from pathlib import Path


def validate_papers(papers):
    if not isinstance(papers, list):
        raise ValueError("Input JSON must be an array of paper objects.")
    for index, paper in enumerate(papers, 1):
        if not isinstance(paper, dict):
            raise ValueError("Paper {} must be an object.".format(index))
        name = paper.get("file")
        if (not isinstance(name, str) or not name.lower().endswith(".pdf")
                or any(char in name for char in '/\\:\x00') or name in (".", "..")):
            raise ValueError("Paper {} must have a PDF basename without directories.".format(index))
        for field in ("doi", "title", "error"):
            if field in paper and paper[field] is not None and not isinstance(paper[field], str):
                raise ValueError("Paper {}: {} must be a string or null.".format(index, field))
    return papers


def sanitize_filename(filename):
    value = re.sub(r'[/\\:*?"<>|\x00-\x1f\x7f]', "", filename).rstrip(" .")
    if not value:
        return "Unknown"
    if value.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL"} | {
        "{}{}".format(prefix, number) for prefix in ("COM", "LPT") for number in range(1, 10)
    }:
        value = "_" + value
    return value


def safe_source(root, filename):
    root = root.resolve()
    source = root / filename
    if source.is_symlink() or source.resolve().parent != root:
        raise ValueError("PDF path must stay inside --dir and must not be a symlink: {}".format(filename))
    if not source.is_file():
        raise FileNotFoundError("PDF not found: {}".format(source))
    return source


def rename_paper(old_path, bib_data, dry_run=False):
    """Use an exclusive hard link then unlink, so a race cannot overwrite PDFs."""
    if old_path.is_symlink() or not old_path.is_file():
        raise FileNotFoundError("PDF is missing, not a regular file, or a symlink: {}".format(old_path))
    year = (bib_data.get("year") or "UnknownYear")[:16]
    author = (bib_data.get("author") or "UnknownAuthor").split(" and ")[0].split(",")[0][:60]
    title = (bib_data.get("title") or "UnknownTitle")[:60]
    stem = sanitize_filename("{} - {} - {}".format(year, author, title))
    stem = stem.encode("utf-8")[:220].decode("utf-8", errors="ignore").rstrip(" .")
    counter = 0
    while True:
        suffix = "_{}".format(counter) if counter else ""
        target = old_path.with_name(stem + suffix + ".pdf")
        if target == old_path:
            return old_path
        if dry_run:
            if not target.exists():
                return target
        else:
            try:
                os.link(str(old_path), str(target))
            except FileExistsError:
                counter += 1
                continue
            try:
                old_path.unlink()
            except OSError:
                target.unlink()
                raise
            return target
        counter += 1


def print_progress_bar(iteration, total, prefix="", suffix="", decimals=1, length=40, fill="="):
    if total <= 0:
        return
    fraction = max(0, min(iteration, total)) / float(total)
    filled = int(length * fraction)
    percent = format(100 * fraction, ".{}f".format(decimals))
    line = "\r{} |{}{}| {}% {}".format(prefix, fill * filled, "-" * (length - filled), percent, suffix)
    sys.stdout.write(line + ("\n" if iteration >= total else ""))
    sys.stdout.flush()


def _same_path(first, second):
    return first.resolve() == second.resolve() or (
        first.exists() and second.exists() and os.path.samefile(str(first), str(second))
    )


def _outputs(args, papers):
    outputs = [args.output] + [path for path in (args.citations, args.report) if path is not None]
    protected = [args.input]
    if args.dir:
        protected.extend(args.dir / paper["file"] for paper in papers)
    for index, path in enumerate(outputs):
        if path.suffix.lower() == ".pdf":
            raise ValueError("Output must not be a PDF: {}".format(path))
        if any(_same_path(path, other) for other in protected + outputs[:index]):
            raise ValueError("Outputs must be distinct from the input, PDFs, and each other: {}".format(path))
        if path.exists() and not path.is_file():
            raise ValueError("Output is not a file: {}".format(path))
        path.parent.mkdir(parents=True, exist_ok=True)
    return outputs


def _atomic_write(path, content):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.replace(str(temporary), str(path))
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _unique_entry(bib, used):
    match = re.match(r"(\s*@[A-Za-z]+\s*[{(]\s*)([^,\s]+)(\s*,)", bib)
    if not match:
        raise ValueError("Missing BibTeX entry key")
    key = match.group(2)
    candidate = key
    counter = 2
    while candidate in used:
        candidate = "{}_{}".format(key, counter)
        counter += 1
    used.add(candidate)
    return bib[:match.start(2)] + candidate + bib[match.end(2):]


def run(argv, load_papers, fetch_bibtex, parse_bibtex, generate_citation):
    parser = argparse.ArgumentParser(description="Fetch BibTeX and simple citations, with optional PDF renaming.")
    parser.add_argument("--input", type=Path, default=Path("paper_info.json"))
    parser.add_argument("--output", type=Path, default=Path("papers.bib"))
    parser.add_argument("--citations", type=Path)
    parser.add_argument("--style", default="apa", choices=["apa", "mla", "ieee"])
    parser.add_argument("--rename", action="store_true")
    parser.add_argument("--dir", type=Path)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--dry-run", action="store_true", help="Preview renames; still write bibliography/report outputs.")
    parser.add_argument("--report", type=Path, help="Write per-file results as JSON.")
    args = parser.parse_args(argv)
    try:
        if not math.isfinite(args.delay) or args.delay < 0:
            raise ValueError("--delay must be a finite nonnegative number.")
        if args.rename and (args.dir is None or not args.dir.is_dir()):
            raise ValueError("--rename requires --dir pointing to an existing directory.")
        if args.dry_run and not args.rename:
            raise ValueError("--dry-run requires --rename.")
        papers = load_papers(args.input)
        _outputs(args, papers)
        return _process(args, papers, fetch_bibtex, parse_bibtex, generate_citation)
    except (OSError, ValueError) as exc:
        print("[ERROR] {}".format(exc), file=sys.stderr)
        return 1


def _process(args, papers, fetch_bibtex, parse_bibtex, generate_citation):
    entries, citations, results, renames = [], [], [], []
    cache, used_keys = {}, set()
    attempts = 0
    for paper in papers:
        record = {"file": paper["file"], "status": "success"}
        results.append(record)
        doi = (paper.get("doi") or "").strip()
        if not doi:
            record.update(status="skipped", reason=paper.get("error") or "No DOI; add a verified DOI to the JSON input.")
            print("[SKIP] {}: {}".format(paper["file"], record["reason"]), file=sys.stderr)
            continue
        record["doi"] = doi
        try:
            source = safe_source(args.dir, paper["file"]) if args.rename else None
            key = doi.lower()
            if key not in cache:
                if attempts:
                    time.sleep(args.delay)
                attempts += 1
                bib = fetch_bibtex(doi)
                data = parse_bibtex(bib)
                if not data.get("title"):
                    raise ValueError("BibTeX response has no title.")
                citation = generate_citation(data, args.style) if args.citations else None
                bib = _unique_entry(bib, used_keys)
                cache[key] = data
                entries.append(bib.rstrip())
                if citation is not None:
                    citations.append(citation)
            if source is not None:
                renames.append((source, cache[key], record))
        except Exception as exc:
            record.update(status="failed", reason=str(exc))
            print("[ERROR] {}: {}".format(paper["file"], exc), file=sys.stderr)

    # Preserve references before changing any source filename. Empty runs replace
    # stale outputs with empty files, while skipped/failed records return failure.
    _atomic_write(args.output, "\n\n".join(entries) + ("\n" if entries else ""))
    if args.citations:
        _atomic_write(args.citations, "\n\n".join(citations) + ("\n" if citations else ""))
    if args.report:
        _atomic_write(args.report, json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    for source, data, record in renames:
        try:
            target = rename_paper(source, data, dry_run=args.dry_run)
            field = "planned_file" if args.dry_run else "renamed_file"
            record[field] = target.name
            print("[{}] {} -> {}".format("PREVIEW" if args.dry_run else "RENAME", source.name, target.name))
        except OSError as exc:
            record.update(status="failed", reason="Rename failed: {}".format(exc))
            print("[ERROR] {}: {}".format(source.name, record["reason"]), file=sys.stderr)
    if args.report:
        _atomic_write(args.report, json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    failures = sum(record["status"] != "success" for record in results)
    print("[DONE] {} unique references; {} successful files; {} skipped/failed.".format(
        len(entries), len(results) - failures, failures))
    return 1 if failures else 0
