import sys
writers = set()
for line in open("_recon/gswrite_raw_page03.txt", encoding="utf-8"):
    f, ln, fn, recv = line.rstrip("\n").split("\t")
    if recv.split(".")[0].lstrip("_") in {"ws", "sh", "client", "worksheet", "sheet",
                                          "spreadsheet"} or recv.startswith("self._sh"):
        mod = f[:-3].replace("/", ".").replace(".__init__", "")
        writers.add((mod, fn.split("::")[-1]))
reach = set()
for line in open(sys.argv[1], encoding="utf-8"):
    m, fn = line.strip().split("::")
    reach.add((m, fn))
hit = sorted(writers & reach)
print(f"寫入函式數 = {len(writers)}   可達函式數 = {len(reach)}")
print(f"交集（＝可達的 GS 寫入函式）= {len(hit)}")
for h in hit:
    print("  !!", h[0] + "::" + h[1])
print("--- 全部寫入函式（供對照）---")
for w in sorted(writers):
    print(("  可達 " if w in reach else "  不可達 ") + w[0] + "::" + w[1])
