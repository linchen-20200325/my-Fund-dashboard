import ast, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgraph as CG

entry_mod, entry_fn, tgt_mod, tgt_fn = sys.argv[1:5]
infos, byname = CG.build(entry_mod)
start = (entry_mod, entry_fn); goal = (tgt_mod, tgt_fn)
prev = {start: None}
stack = [start]
while stack:
    cur = stack.pop()
    m, fn = cur
    if m not in infos or fn not in infos[m].funcs:
        continue
    for nxt in CG.callees(infos[m], infos[m].funcs[fn], infos, byname):
        if nxt not in prev:
            prev[nxt] = cur
            if nxt == goal:
                stack = []
                break
            stack.append(nxt)
if goal not in prev:
    print("不可達"); raise SystemExit(0)
chain, n = [], goal
while n:
    chain.append(n); n = prev[n]
for i, (m, f) in enumerate(reversed(chain)):
    print("  " * i + f"→ {m}::{f}")
