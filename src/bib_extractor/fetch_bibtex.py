import argparse
import json
import time
import re
import sys
from pathlib import Path
from typing import List, Dict, Any

from bib_extractor.metadata import fetch_bibtex, generate_citation, parse_bibtex

def load_papers(json_path: Path) -> List[Dict[str, Any]]:
    """Load the JSON file produced by ``extract_bib_info.py``."""
    if not json_path.is_file():
        raise FileNotFoundError(f"Input file not found: {json_path}")
    with json_path.open(encoding="utf-8") as f:
        return json.load(f)

def sanitize_filename(filename: str) -> str:
    """Remove characters that are invalid in filenames."""
    return re.sub(r'[/\\:*?"<>|]', "", filename)

def rename_paper(old_path: Path, bib_data: Dict[str, str]) -> Path:
    """Rename a PDF file based on BibTeX data."""
    if not old_path.exists():
        return old_path

    year = bib_data.get("year", "UnknownYear")
    author = bib_data.get("author", "UnknownAuthor").split(" and ")[0].split(",")[0]
    title = bib_data.get("title", "UnknownTitle")
    
    new_name = f"{year} - {author} - {title[:60]}"
    new_name = sanitize_filename(new_name) + ".pdf"
    new_path = old_path.parent / new_name
    
    if old_path != new_path:
        counter = 1
        final_path = new_path
        while final_path.exists():
            final_path = new_path.with_name(f"{new_path.stem}_{counter}.pdf")
            counter += 1
        old_path.rename(final_path)
        return final_path
    return old_path

def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=40, fill='█'):
    """Call in a loop to create terminal progress bar."""
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}')
    sys.stdout.flush()
    if iteration == total:
        sys.stdout.write('\n')

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch BibTeX and citations for papers, with optional auto-renaming."
    )
    parser.add_argument("--input", type=Path, default=Path("paper_info.json"), help="Input JSON file.")
    parser.add_argument("--output", type=Path, default=Path("papers.bib"), help="Output BibTeX file.")
    parser.add_argument("--citations", type=Path, help="Output file for formatted citations.")
    parser.add_argument("--style", type=str, default="apa", choices=["apa", "mla", "ieee"], help="Citation style.")
    parser.add_argument("--rename", action="store_true", help="Rename original PDFs.")
    parser.add_argument("--dir", type=Path, help="Directory of original PDFs.")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests.")
    args = parser.parse_args()

    if args.rename and not args.dir:
        print("[ERROR] You must provide --dir when using --rename.")
        return

    try:
        papers = load_papers(args.input)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return

    bib_entries: List[str] = []
    citations: List[str] = []
    total = len(papers)
    
    print(f"Processing {total} papers...")
    for i, paper in enumerate(papers):
        doi = paper.get("doi")
        print_progress_bar(i + 1, total, prefix='Progress:', suffix=f'Complete ({paper.get("file", "...")})', length=30)
        
        if not doi:
            continue
            
        try:
            bib = fetch_bibtex(doi)
            bib_entries.append(bib)
            bib_data = parse_bibtex(bib)
            
            if args.citations:
                citations.append(generate_citation(bib_data, args.style))
            
            if args.rename:
                old_file = args.dir / paper["file"]
                if old_file.exists():
                    rename_paper(old_file, bib_data)
                    
        except Exception:
            pass # Silently skip errors during progress bar view
        time.sleep(args.delay)

    # Save BibTeX
    if bib_entries:
        output_path = args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            for entry in bib_entries:
                f.write(entry.rstrip() + "\n\n")
        print(f"[DONE] Saved {len(bib_entries)} BibTeX entries to {args.output}")

    # Save Citations
    if citations:
        with args.citations.open("w", encoding="utf-8") as f:
            for citation in citations:
                f.write(citation + "\n\n")
        print(f"[DONE] Saved {len(citations)} citations ({args.style.upper()}) to {args.citations}")

if __name__ == "__main__":
    main()
