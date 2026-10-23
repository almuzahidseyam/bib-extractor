# Contributing to Bib Extractor

Thank you for considering contributing to **Bib Extractor**! 🎉

## How to Get Started

1. **Fork the repository** on GitHub.
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/bib-extractor.git
   cd bib-extractor
   ```
3. **Create a new branch** for your change:
   ```bash
   git checkout -b my-feature-or-fix
   ```

## Development Setup

- Use Python 3.8 or newer and create a virtual environment with `python -m venv .venv`.
- Activate it using `.venv\Scripts\Activate.ps1` in Windows PowerShell or `source .venv/bin/activate` on Unix.
- Run `python -m pip install -e .` to install the project and its `pypdf` dependency.
- Install development tools with `python -m pip install flake8 build twine`.
- Poppler and `pdftotext` are not required. Live metadata retrieval needs internet access.

## Code Style & Linting

- Follow the existing code style (PEP 8). The CI workflow runs `flake8` with the following settings:
  - Max line length: **127** characters
  - Max complexity: **10**
- Run lint locally before committing:
  ```bash
  python -m flake8 src tests --max-line-length=127
  ```

## Testing

Run the standard-library test suite and verify distribution metadata:

```bash
python -m unittest discover -s tests -v
python -m build
python -m twine check dist/*
```

Place regression tests in `tests/test_*.py`. Tests must use temporary files and
mock API requests so that CI does not depend on network availability or modify
real research papers. CI runs tests on Linux and Windows with Python 3.8, 3.12,
and 3.14, and builds both the wheel and source distribution.

For a manual end-to-end check, use copies of a small PDF collection, run both
commands, and inspect the JSON and BibTeX. Keep copyrighted papers and generated
bibliographies out of the repository.

## Submitting a Pull Request

1. **Commit your changes** with clear, concise messages.
2. **Push** the branch to your fork:
   ```bash
   git push origin my-feature-or-fix
   ```
3. Open a **Pull Request** against the `main` branch of the original repository.
4. Fill out the PR template (if present) and describe the changes.
5. CI runs syntax/undefined-name checks, tests, and distribution validation. Make sure it passes before merging.

## Reporting Issues

If you encounter a bug or have a feature request, please open an issue on GitHub with:
- A clear title.
- Steps to reproduce (for bugs).
- Expected vs. actual behavior.
- Any relevant logs or screenshots.

## License

By contributing, you agree that your contributions will be licensed under the same **MIT License** as the project.

---

Happy coding! 🚀
