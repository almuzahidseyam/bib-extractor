import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from pypdf import PdfReader


DOI_PATTERN = re.compile(
    r"10\.\s*(?:\d\s*){4,9}/\s*[-._;()/:A-Z0-9<>+&%?=#]+",
    re.IGNORECASE,
)


def get_num(s: str) -> int:
    """Extract leading number from filename for sorting."""
    match = re.match(r"(\d+)", s)
    return int(match.group(1)) if match else 999


def find_doi(text: str):
    """Find a DOI, preserving suffix punctuation and balanced parentheses."""
    text = text.replace("\u200b", "").replace("\u00ad", "")
    # Join only after a separator: an ordinary next line may be body text.
    text = re.sub(r"(?<=[/_-])\r?\n[ \t]*(?=[A-Za-z0-9])", "", text)
    text = re.sub(r"(?<=\.)\r?\n[ \t]*(?=[0-9])", "", text)
    match = DOI_PATTERN.search(text)
    if not match:
        return None
    doi = re.sub(r"\s+", "", match.group())
    doi = doi.rstrip(".,;:")
    while doi.endswith(")") and doi.count(")") > doi.count("("):
        doi = doi[:-1].rstrip(".,;:")
    return doi


def extract_papers(dir_path: Path) -> list:
    """Read metadata and the first two pages of each PDF in a directory."""
    if not dir_path.is_dir():
        raise NotADirectoryError("PDF directory does not exist or is not a directory: {}".format(dir_path))
    files = sorted(
        (path for path in dir_path.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"),
        key=lambda path: (get_num(path.name), path.name.lower(), path.name),
    )
    results = []
    for path in files:
        print("Processing {}...".format(path.name))
        try:
            with path.open("rb") as stream:
                reader = PdfReader(stream)
                metadata = reader.metadata or {}
                metadata_doi = None
                for key in ("/doi", "/DOI", "/Subject", "/Keywords"):
                    metadata_doi = find_doi(str(metadata.get(key) or ""))
                    if metadata_doi:
                        break
                content = ""
                if not metadata_doi:
                    content = "\n".join(
                        reader.pages[i].extract_text() or ""
                        for i in range(min(2, len(reader.pages)))
                    )
                doi = metadata_doi or find_doi(content)
                if doi:
                    results.append({"file": path.name, "doi": doi})
                    print("  Found DOI: {}".format(doi))
                else:
                    title = str(metadata.get("/Title") or "").strip()
                    lines = [line.strip() for line in content.splitlines() if line.strip()]
                    title = title or " ".join(lines[:3]) or "Unknown"
                    results.append({"file": path.name, "title": title})
                    print("  No DOI found. Title candidate: {}...".format(title[:50]))
        except Exception as exc:
            # Keep the other results if one PDF is unreadable or encrypted.
            results.append({"file": path.name, "error": str(exc)})
            print("  Error: {}".format(exc), file=sys.stderr)
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Extract DOIs or titles from PDF papers in a folder.")
    parser.add_argument("--dir", type=Path, default=Path.cwd(), help="Directory containing PDF files.")
    parser.add_argument("--output", type=Path, default=Path("paper_info.json"), help="Path to write the JSON output.")
    args = parser.parse_args(argv)
    try:
        results = extract_papers(args.dir)
        source_paths = {path.resolve() for path in args.dir.iterdir() if path.suffix.lower() == ".pdf"}
        if args.output.resolve() in source_paths:
            raise ValueError("JSON output must not overwrite a source PDF.")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.output.parent,
                                             delete=False) as output:
                temporary = Path(output.name)
                json.dump(results, output, indent=2, ensure_ascii=False)
            os.replace(str(temporary), str(args.output))
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
    except (OSError, ValueError) as exc:
        print("[ERROR] {}".format(exc), file=sys.stderr)
        return 1
    print("Done! Saved results to {}".format(args.output))
    return 1 if any("error" in paper for paper in results) else 0


if __name__ == "__main__":
    sys.exit(main())
