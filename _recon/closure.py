"""AST 傳遞 import 閉包 —— 只跟本 repo 內的模組（第一方），含函式內 lazy import。

用法: python3 _recon/closure.py <entry_module> [<entry_module> ...]
輸出: 每行一個可達的第一方模組（module dotted name -> 檔案路徑）
"""
import ast, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def mod_to_paths(mod: str) -> list[str]:
    """一個 dotted name 可能對到 pkg/__init__.py 或 mod.py。"""
    rel = mod.replace(".", os.sep)
    out = []
    for cand in (os.path.join(ROOT, rel + ".py"), os.path.join(ROOT, rel, "__init__.py")):
        if os.path.isfile(cand):
            out.append(cand)
    return out


def parents(mod: str) -> list[str]:
    """import a.b.c 會執行 a、a.b、a.b.c 三個 __init__ —— 全部算進閉包。"""
    parts = mod.split(".")
    return [".".join(parts[:i]) for i in range(1, len(parts) + 1)]


def imports_of(path: str, selfmod: str) -> set[str]:
    """回傳這個檔案 import 的所有 dotted name（含 from X import Y 的 X.Y 形式）。"""
    try:
        tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
    except SyntaxError:
        return set()
    got: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                got.update(parents(a.name))
        elif isinstance(n, ast.ImportFrom):
            if n.level:  # relative import
                base = selfmod.split(".")
                # 對 pkg/__init__.py 而言 selfmod 就是 pkg 本身
                if not path.endswith("__init__.py"):
                    base = base[:-1]
                base = base[: len(base) - (n.level - 1)] if n.level > 1 else base
                mod = ".".join(base + ([n.module] if n.module else []))
            else:
                mod = n.module or ""
            if not mod:
                continue
            got.update(parents(mod))
            # from pkg import submodule  → pkg.submodule 也可能是模組
            for a in n.names:
                got.update(parents(f"{mod}.{a.name}"))
    return got


def closure(entries: list[str]) -> dict[str, str]:
    seen: dict[str, str] = {}
    stack = list(entries)
    while stack:
        mod = stack.pop()
        if mod in seen:
            continue
        paths = mod_to_paths(mod)
        if not paths:
            continue  # 第三方或不存在 → 不跟
        p = paths[0]
        seen[mod] = p
        for nxt in imports_of(p, mod):
            if nxt not in seen and mod_to_paths(nxt):
                stack.append(nxt)
    return seen


if __name__ == "__main__":
    res = closure(sys.argv[1:])
    for m in sorted(res):
        print(f"{m}\t{os.path.relpath(res[m], ROOT)}")
