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
    from bib_extractor.workflow import validate_papers

    if not json_path.is_file():
        raise FileNotFoundError(f"Input file not found: {json_path}")
    with json_path.open(encoding="utf-8") as f:
        return validate_papers(json.load(f))

def sanitize_filename(filename: str) -> str:
    """Remove characters that are invalid in filenames."""
    return re.sub(r'[/\\:*?"<>|]', "", filename)

def rename_paper(old_path, bib_data, dry_run=False):
    from bib_extractor.workflow import rename_paper as rename
    return rename(old_path, bib_data, dry_run=dry_run)


def print_progress_bar(*args, **kwargs):
    from bib_extractor.workflow import print_progress_bar as progress
    return progress(*args, **kwargs)


def main(argv=None):
    from bib_extractor.workflow import run
    return run(argv, load_papers, fetch_bibtex, parse_bibtex, generate_citation)


if __name__ == "__main__":
    sys.exit(main())
