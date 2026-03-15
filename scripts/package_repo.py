from __future__ import annotations

from pathlib import Path
import zipfile


EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
}

EXCLUDED_FILES = {
    Path("middleware/config.yaml"),
}

EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".pyd",
}


def _should_include(path: Path, repo_root: Path) -> bool:
    rel = path.relative_to(repo_root)
    if any(part in EXCLUDED_DIRS for part in rel.parts):
        return False
    if rel in EXCLUDED_FILES:
        return False
    if rel.name.startswith(".env"):
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    return True


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    out = repo_root.parent / f"{repo_root.name}-export.zip"

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in repo_root.rglob("*"):
            if path.is_file() and _should_include(path, repo_root):
                zf.write(path, path.relative_to(repo_root))

    print(out)


if __name__ == "__main__":
    main()
