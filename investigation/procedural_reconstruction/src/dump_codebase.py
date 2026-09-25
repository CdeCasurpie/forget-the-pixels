#!/usr/bin/env python3
"""Dump de la carpeta src/: tree + contenido de .py y .md.

Excluye __pycache__, *.pyc/*.pyo y cachés. Solo vuelca .py y .md.

Uso:
    python3 dump_codebase.py                       # genera codebase_dump.txt junto al script
    python3 dump_codebase.py -o /tmp/dump.txt      # salida personalizada
    python3 dump_codebase.py --no-tree             # sin el tree inicial
"""

from __future__ import annotations

import argparse
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = SRC_DIR / "codebase_dump.txt"

SKIP_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".pyd", ".so"}
INCLUDE_SUFFIXES = {".py", ".md"}


def collect_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix in SKIP_SUFFIXES:
            continue
        if path.suffix not in INCLUDE_SUFFIXES:
            continue
        if path.resolve() == DEFAULT_OUTPUT.resolve():
            continue
        files.append(path)
    return files


def build_tree(files: list[Path], root: Path) -> str:
    tree: dict = {}
    for f in files:
        node = tree
        for part in f.relative_to(root).parts:
            node = node.setdefault(part, {})
    lines = [f"{root.name}/"]

    def walk(node: dict, prefix: str) -> None:
        names = sorted(node)
        for i, name in enumerate(names):
            last = i == len(names) - 1
            branch = "└── " if last else "├── "
            lines.append(f"{prefix}{branch}{name}")
            if node[name]:
                walk(node[name], prefix + ("    " if last else "│   "))

    walk(tree, "")
    return "\n".join(lines)


def dump(root: Path, output: Path, with_tree: bool) -> None:
    files = collect_files(root)
    parts: list[str] = []
    if with_tree:
        parts.append("=" * 72)
        parts.append("TREE de src/ (solo .py y .md, sin __pycache__ ni inservibles)")
        parts.append("=" * 72)
        parts.append(build_tree(files, root))
        parts.append("")
    total_lines = 0
    for f in files:
        rel = f.relative_to(root)
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = f.read_text(encoding="utf-8", errors="replace")
        nlines = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
        total_lines += nlines
        parts.append("=" * 72)
        parts.append(f"FILE: {rel} ({nlines} lineas)")
        parts.append("=" * 72)
        parts.append(text.rstrip("\n"))
        parts.append("")
    parts.append(f"[dump] {len(files)} archivos, {total_lines} lineas totales.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"{len(files)} archivos, {total_lines} lineas -> {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--root", type=Path, default=SRC_DIR)
    parser.add_argument("--no-tree", action="store_true")
    args = parser.parse_args()
    dump(args.root.resolve(), args.output.resolve(), with_tree=not args.no_tree)


if __name__ == "__main__":
    main()
