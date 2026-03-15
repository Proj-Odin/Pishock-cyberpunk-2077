from __future__ import annotations

import argparse
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a zip export of the repository")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output zip path. Defaults to ../<repo-name>-export.zip",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    out = args.output if args.output is not None else (repo_root.parent / f"{repo_root.name}-export.zip")
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in repo_root.rglob("*"):
            if path.is_file() and _should_include(path, repo_root):
                zf.write(path, path.relative_to(repo_root))

    print(out)


if __name__ == "__main__":
    main()
