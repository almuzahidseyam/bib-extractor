# Bib Extractor

[![PyPI version](https://img.shields.io/pypi/v/bib-extractor.svg?color=blue)](https://pypi.org/project/bib-extractor/)
[![License: MIT](https://img.shields.io/pypi/l/bib-extractor.svg?color=green)](https://pypi.org/project/bib-extractor/)

A tiny, **pip‑installable** Python utility that scans a folder of PDF papers, extracts their DOI (or a title fallback), and produces a JSON file that can be turned into a BibTeX bibliography.

---

## ✨ Features
- Works on any folder of PDFs.
- **Pure Python**: Uses the `pypdf` package, installed automatically by pip. No Poppler or `pdftotext` required.
- Detects DOI strings with a robust regular expression.
- **Multiple API Support**: Queries `doi.org` and falls back to **Crossref** for metadata.
- **Auto-Rename**: Automatically renames PDFs to `Year - Author - Title.pdf`.
- **Simple Citations**: Generates plain-text APA/MLA/IEEE-style reference lists; check them against your required style guide.
- **Visual Progress**: Includes per-file progress indicators for high-volume processing.

---

## 📦 Installation
### From PyPI (recommended)
Requires Python 3.8 or newer. Metadata retrieval requires internet access.

```bash
pip install bib-extractor
```

### From source
1. **Clone the repository**
```bash
git clone https://github.com/msrtarit/bib-extractor.git
cd bib-extractor
```
2. (Optional) Create a virtual environment and install the package in editable mode:
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows PowerShell
# or source .venv/bin/activate on Unix
pip install -e .
```

---

## 🚀 Usage

### 1. Extract DOIs / Titles
This step scans your PDFs and creates a metadata JSON.

The extractor reads up to the first two pages of each PDF. It does not perform
OCR. If no DOI is found, the JSON retains a title candidate for manual lookup;
the fetch command currently needs a DOI and does not search by title. Verify
and add the DOI to that record before fetching it.

**Standard Command:**
```bash
bib-extractor --dir path/to/papers --output paper_info.json
```

**Windows / Path Fallback:**
If the command above says "not found", use the Python module directly:
```bash
python -m bib_extractor --dir path/to/papers --output paper_info.json
```

---

### 2. Fetch BibTeX & Auto-Rename
This step uses the JSON from step 1 to download metadata and (optionally) rename files.

**Standard Command:**
```bash
bib-fetch --input paper_info.json --output papers.bib --rename --dir path/to/papers
```

**Windows / Path Fallback:**
```bash
python -m bib_extractor.fetch_bibtex --input paper_info.json --output papers.bib --rename --dir path/to/papers
```

> [!TIP]
> **Windows Users**: If the short commands (`bib-extractor`) don't work, ensure your Python `Scripts` folder is added to your system environment variables. Alternatively, always use the `python -m` method shown above.
### 🛠️ Extraction options (`bib-extractor`)

| Flag | Description | Default |
| :--- | :--- | :--- |
| `--dir` | Directory containing PDF files | Current directory |
| `--output` | Path to save extracted JSON metadata | `paper_info.json` |

### Fetch options (`bib-fetch`)

| Flag | Description | Default |
| :--- | :--- | :--- |
| `--input` | JSON metadata file from step 1 | `paper_info.json` |
| `--output` | Path to save the BibTeX bibliography | `papers.bib` |
| `--dir` | Directory of original PDFs; required with `--rename` | Unset |
| `--citations` | Output file for a formatted reference list (e.g. `refs.txt`) | Optional |
| `--style` | Citation style for the reference list (`apa`, `mla`, or `ieee`) | `apa` |
| `--rename` | Automatically rename PDFs to `Year - Author - Title.pdf` | Optional |
| `--delay` | Delay in seconds between processing papers | `1.0` |

---

## 🤝 Contributing
Please see the [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to fork the repo, set up a development environment, and submit pull requests.

---

## 📜 License
This project is licensed under the **MIT License** – see the [LICENSE](LICENSE) file for details.
