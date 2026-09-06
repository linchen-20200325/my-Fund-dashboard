"""第一方函式呼叫圖的可達性（過度近似，寧可多抓）。

節點 = (module, qualname)。邊的來源：
  1. 同模組內以裸名呼叫的 top-level 函式
  2. `from X import f` 之後呼叫 `f(...)`  → X.f
  3. `import X` / `from X import Y` 之後呼叫 `X.f(...)` / `Y.f(...)` → 該模組的 f
  4. 任何 `obj.method(...)`：**若某個可達模組裡剛好有同名 top-level 函式，一律當成可達**
     （過度近似；寧可多抓，見 §8 教訓：pattern 假設唯一寫法會漏抓）
函式內的 lazy import 一併處理（走 ast.walk，不只看 module level）。
"""
import ast, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from closure import closure, mod_to_paths  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ModInfo:
    def __init__(self, mod, path):
        self.mod, self.path = mod, path
        self.tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
        self.funcs = {}          # qualname -> node
        self.alias2mod = {}      # 本地名 -> 來源模組
        self._collect()

    def _collect(self):
        for n in ast.walk(self.tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.funcs.setdefault(n.name, n)
            elif isinstance(n, ast.Import):
                for a in n.names:
                    self.alias2mod[a.asname or a.name.split(".")[0]] = a.name
            elif isinstance(n, ast.ImportFrom):
                if n.level:
                    base = self.mod.split(".")
                    if not self.path.endswith("__init__.py"):
                        base = base[:-1]
                    src = ".".join(base + ([n.module] if n.module else []))
                else:
                    src = n.module or ""
                for a in n.names:
                    self.alias2mod[a.asname or a.name] = f"{src}::{a.name}"


def build(entries_mod):
    mods = closure([entries_mod])
    infos = {}
    for m, p in mods.items():
        try:
            infos[m] = ModInfo(m, p)
        except SyntaxError:
            pass
    # 全域函式名 -> 擁有它的模組（過度近似用）
    byname = {}
    for m, i in infos.items():
        for f in i.funcs:
            byname.setdefault(f, set()).add(m)
    return infos, byname


def _add_name(name, info, infos, byname, out):
    """一個裸名可能是：本模組函式 / from-import 進來的函式 / 任何同名 top-level 函式。"""
    if name in info.funcs:
        out.add((info.mod, name))
    tgt = info.alias2mod.get(name, "")
    if "::" in tgt:
        srcmod, sym = tgt.split("::")
        for cand in (srcmod, f"{srcmod}.{sym}"):
            if cand in infos and sym in infos[cand].funcs:
                out.add((cand, sym))
    for m in byname.get(name, ()):
        out.add((m, name))


def callees(info, node, infos, byname):
    out = set()
    # ① 函式被當成「值」傳出去（safe_section(BLOCK, _render_x) 這種)也算可達 ——
    #    不收的話 callback 形態的整條鏈會被漏掉（本 repo 的 safe_section 就是這型）。
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            _add_name(n.id, info, infos, byname, out)
        elif isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load):
            for m in byname.get(n.attr, ()):
                out.add((m, n.attr))
    for n in ast.walk(node):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Name):
            name = f.id
            if name in info.funcs:
                out.add((info.mod, name))
            tgt = info.alias2mod.get(name, "")
            if "::" in tgt:
                srcmod, sym = tgt.split("::")
                for cand in (srcmod, f"{srcmod}.{sym}"):
                    if cand in infos and sym in infos[cand].funcs:
                        out.add((cand, sym))
                if srcmod in infos and sym in infos[srcmod].funcs:
                    out.add((srcmod, sym))
            for m in byname.get(name, ()):
                out.add((m, name))
        elif isinstance(f, ast.Attribute):
            name = f.attr
            for m in byname.get(name, ()):
                out.add((m, name))
    return out


def reach(entry_mod, entry_fn):
    infos, byname = build(entry_mod)
    seen, stack = set(), [(entry_mod, entry_fn)]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        m, fn = cur
        if m not in infos or fn not in infos[m].funcs:
            continue
        seen.add(cur)
        for nxt in callees(infos[m], infos[m].funcs[fn], infos, byname):
            if nxt not in seen:
                stack.append(nxt)
    return seen, infos


if __name__ == "__main__":
    em, ef = sys.argv[1], sys.argv[2]
    seen, _ = reach(em, ef)
    for m, f in sorted(seen):
        print(f"{m}::{f}")
