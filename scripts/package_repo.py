from __future__ import annotations

from pathlib import Path
import zipfile


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    out = repo_root.parent / f"{repo_root.name}-export.zip"

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in repo_root.rglob("*"):
            if ".git" in path.parts:
                continue
            if path.is_file():
                zf.write(path, path.relative_to(repo_root))

    print(out)


if __name__ == "__main__":
    main()
