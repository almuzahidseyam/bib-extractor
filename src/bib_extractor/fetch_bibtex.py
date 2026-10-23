import argparse
import json
import time
import urllib.request
import re
import sys
from pathlib import Path
from typing import List, Dict, Any

def load_papers(json_path: Path) -> List[Dict[str, Any]]:
    """Load the JSON file produced by ``extract_bib_info.py``."""
    from bib_extractor.workflow import validate_papers

    if not json_path.is_file():
        raise FileNotFoundError(f"Input file not found: {json_path}")
    with json_path.open(encoding="utf-8") as f:
        return validate_papers(json.load(f))

def fetch_bibtex(doi: str, timeout: int = 10) -> str:
    """Retrieve a BibTeX entry for a DOI, trying multiple APIs."""
    apis = [
        {"name": "doi.org", "url": f"https://doi.org/{doi}", "headers": {"Accept": "application/x-bibtex"}},
        {"name": "Crossref", "url": f"https://api.crossref.org/works/{doi}/transform/application/x-bibtex", "headers": {}}
    ]
    
    for api in apis:
        try:
            req = urllib.request.Request(api["url"], headers=api["headers"])
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status == 200:
                    return response.read().decode("utf-8")
        except Exception:
            continue
    raise Exception(f"Failed to fetch BibTeX for {doi} from all available APIs.")

def parse_bibtex(bib: str) -> Dict[str, str]:
    """Simple regexâ€‘based parser to extract key fields from a BibTeX entry."""
    data = {}
    # Fields to extract
    fields = ["title", "year", "author", "journal", "volume", "number", "pages", "publisher"]
    for field in fields:
        match = re.search(f"{field}\\s*=\\s*[\\{{\"](.*?)[\\}}\"]", bib, re.IGNORECASE | re.DOTALL)
        if match:
            content = match.group(1).strip()
            content = re.sub(r"[\{\}]", "", content)
            data[field] = content
    return data

def generate_citation(bib_data: Dict[str, str], style: str = "apa") -> str:
    """Generate a simple citation string from BibTeX data."""
    author = bib_data.get("author", "Unknown Author")
    year = bib_data.get("year", "n.d.")
    title = bib_data.get("title", "Unknown Title")
    journal = bib_data.get("journal", bib_data.get("publisher", ""))
    volume = bib_data.get("volume", "")
    number = bib_data.get("number", "")
    pages = bib_data.get("pages", "")
    
    # Handle multiple authors
    authors_list = author.split(" and ")
    
    if style.lower() == "apa":
        # APA: "Smith, J., & Jones, M. (Year). Title. Journal."
        if len(authors_list) > 1:
            author_str = ", ".join(authors_list[:-1]) + " & " + authors_list[-1]
        else:
            author_str = authors_list[0]
        citation = f"{author_str} ({year}). {title}."
        if journal:
            citation += f" {journal}."

    elif style.lower() == "mla":
        # MLA: "Author. \"Title.\" Journal, Year."
        if len(authors_list) > 1:
            author_str = ", ".join(authors_list[:-1]) + ", and " + authors_list[-1]
        else:
            author_str = authors_list[0]
        citation = f"{author_str}. \"{title}.\" {journal}, {year}."

    elif style.lower() == "ieee":
        # IEEE: "Author(s), \"Title,\" Journal, vol. x, no. x, pp. x, Year."
        formatted_authors = []
        for a in authors_list:
            if "," in a: # Last, First
                parts = a.split(",")
                last = parts[0].strip()
                first = parts[1].strip()
                formatted_authors.append(f"{first[0]}. {last}")
            else: # First Last
                parts = a.split()
                if len(parts) > 1:
                    formatted_authors.append(f"{parts[0][0]}. {parts[-1]}")
                else:
                    formatted_authors.append(a)
        
        if len(formatted_authors) > 1:
            author_str = ", ".join(formatted_authors[:-1]) + " and " + formatted_authors[-1]
        else:
            author_str = formatted_authors[0]
            
        citation = f"{author_str}, \"{title},\" {journal}"
        if volume: citation += f", vol. {volume}"
        if number: citation += f", no. {number}"
        if pages: citation += f", pp. {pages}"
        citation += f", {year}."

    else:
        author_str = " and ".join(authors_list)
        citation = f"{author_str}, {title} ({year})."
    
    return citation

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
