#!/usr/bin/env python3
"""Conservative import inventory: absence of static imports NEVER proves dead code.

Run: python scripts/audit_static_reachability.py --root . --json
Check runtime, workflow, Streamlit Cloud, reflection and rollback before deletion.
"""
from __future__ import annotations

import argparse
import ast
import json
from collections import defaultdict
from pathlib import Path

ROOT_DIRS = ("infra", "repositories", "services", "shared", "ui", "ui_v2", "ui_v" + "3", "scripts", "tests")
ENTRYPOINTS = ("app.py", "ui_v2/app_preview.py", "ui_v" + "3/app_preview.py")


def scan(root: Path) -> dict:
    paths = [p for name in ROOT_DIRS if (root / name).is_dir()
             for p in (root / name).rglob("*.py")
             if not any(s in p.parts for s in ("__pycache__", ".venv", ".git"))]
    if (root / "app.py").is_file():
        paths.append(root / "app.py")
    paths.sort()
    def module(path: Path) -> str:
        parts = path.relative_to(root).with_suffix("").parts
        return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
    members = {module(p): p.relative_to(root).as_posix() for p in paths}
    imports: dict[str, set[str]] = defaultdict(set)
    dynamic: dict[str, list[int]] = defaultdict(list)
    errors: dict[str, str] = {}
    for file in paths:
        owner = module(file)
        package = owner if file.name == "__init__.py" else owner.rpartition(".")[0]
        try:
            tree = ast.parse(file.read_text(encoding="utf-8-sig"), filename=str(file))
        except (SyntaxError, UnicodeError, OSError) as exc:
            errors[owner] = type(exc).__name__
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    chunks = alias.name.split(".")
                    while chunks:
                        candidate = ".".join(chunks)
                        if candidate in members:
                            imports[owner].add(candidate)
                            break
                        chunks.pop()
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    parts = package.split(".") if package else []
                    if node.level > len(parts) + 1:
                        continue
                    prefix = parts[:len(parts) - node.level + 1]
                    base = ".".join(prefix + ([node.module] if node.module else []))
                else:
                    base = node.module or ""
                if base in members:
                    imports[owner].add(base)
                for alias in node.names:
                    candidate = ".".join(x for x in (base, alias.name) if x)
                    if candidate in members:
                        imports[owner].add(candidate)
            elif isinstance(node, ast.Call):
                fn = node.func
                if (isinstance(fn, ast.Name) and fn.id == "__import__") or (
                    isinstance(fn, ast.Attribute) and fn.attr == "import_module"
                ):
                    dynamic[owner].append(node.lineno)
    inbound: dict[str, set[str]] = defaultdict(set)
    for source, targets in imports.items():
        for target in targets:
            inbound[target].add(source)
    candidates = sorted(k for k in members if k not in inbound and k != "app")
    return {
        "classification": "TRIAGE_ONLY_NOT_SAFE_TO_DELETE",
        "module_count": len(members),
        "external_entrypoints_to_verify": list(ENTRYPOINTS),
        "without_static_importers": [{"module": k, "path": members[k]} for k in candidates],
        "dynamic_import_sites": [{"module": k, "lines": sorted(set(v))} for k, v in sorted(dynamic.items())],
        "parse_errors": errors,
        "imports": {k: sorted(v) for k, v in sorted(imports.items())},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = scan(args.root.resolve())
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Modules: {report['module_count']}; no static importers: {len(report['without_static_importers'])}")
        print("These are NOT confirmed dead code; check runtime, workflows, Cloud and rollback.")
        for x in report["without_static_importers"]:
            print(x["path"])
    return 1 if report["parse_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
