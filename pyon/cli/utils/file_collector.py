from __future__ import annotations

from pathlib import Path

import pyon

IGNORED_DIRS = {
    "__pycache__",
    ".git",
    "node_modules",
    "dev",
    "tests",
    "venv",
    ".venv",
    "env",
    ".env",
    "cli",
    "dist",
    "build",
    "pyodide_cache",
    "packages_cache"
}

PYON_PKG_DIR = Path(pyon.__file__).resolve().parent


def collect_project_files(project_root: Path | None = None) -> list[tuple[str, Path]]:
    """
    Recursively scan framework files and project root files.
    Returns a sorted list of tuples: (relative_target_path_str, source_absolute_path).
    
    The list is sorted by directory depth, then __init__.py priority, then path string.
    """
    if project_root is None:
        project_root = Path.cwd()

    items: list[tuple[Path, Path]] = []

    # 1. Collect framework files
    for path in sorted(PYON_PKG_DIR.rglob("*.py")):
        rel_pkg = path.relative_to(PYON_PKG_DIR)
        if any(part in IGNORED_DIRS for part in rel_pkg.parts):
            continue
        rel_target = path.relative_to(PYON_PKG_DIR.parent)
        items.append((rel_target, path))

    # 2. Collect user files
    for path in sorted(project_root.rglob("*.py")):
        try:
            rel = path.relative_to(project_root)
        except ValueError:
            continue
        
        # Skip ignored folders
        if any(part in IGNORED_DIRS for part in rel.parts):
            continue

        # Prevent duplicate entries if the dev server/build is running from within the pyon-py framework repo itself
        if rel.parts and rel.parts[0] == "pyon":
            continue

        items.append((rel, path))

    # Sort by length, then by whether it's an __init__.py file, and finally by path
    def sort_key(item: tuple[Path, Path]) -> tuple:
        p = item[0]
        is_init = 0 if p.name == "__init__.py" else 1
        return (len(p.parts), is_init, str(p))

    items.sort(key=sort_key)

    result = [(str(target).replace("\\", "/"), src) for target, src in items]
    return result


def collect_py_files(project_root: Path | None = None) -> list[str]:
    """
    Returns only the list of relative target path strings (for loader.js).
    """
    return [target for target, _ in collect_project_files(project_root)]
