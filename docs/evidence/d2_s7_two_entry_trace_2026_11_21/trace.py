"""S7 兩入口離線追蹤（只讀、純離線；不發網路、不讀 Sheet、不寫檔；只 stdout）。
用法（任意工作目錄）：python docs/evidence/d2_s7_two_entry_trace_2026_11_21/trace.py > output.json
需要 pandas（repo 既有依賴）；不需要 streamlit。合成代碼 ZZ9999／ZZ9999-SFX01 不在別名表、非任何真實基金。"""
import json, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests" / "ui_v3"))
from services.v2_tables import fund_keys as FK, exp_profile as EP, nav_dividend as ND
from repositories.fund import declared_profile as dp
from ui_v3.adapters import fund_lookup as FL
import assets_source_support as X
from ui_v3.adapters import assets_source as M
import pandas as pd

BARE, SUFFIXED = "ZZ9999", "ZZ9999-SFX01"   # 合成：不在內建別名表、非任何真實基金
out = {}

# ── 0. 對照：現行 resolver（注入空別名表，排除 csv／內建表影響）
res = FK.resolve_full_keys([BARE, SUFFIXED], mapping={})
out["0_resolver_current"] = res["results"]

# ── 入口 2：🔍 找基金（ui_v3 adapter → L2 resolve_full_keys → build_profiles；三來源以離線 spy 取代）
def make_fetchers(spy):
    def mk(name):
        def f(full_key):
            spy.append((name, full_key))
            return {"status": dp.STATUS_NOT_FOUND if name == "MoneyDJ" else dp.STATUS_NOT_LISTED, "fields": {}, "error": None,
                    "cooling": False, "cooling_remaining_sec": None}
        return f
    return {s: mk(s) for s in ("MoneyDJ", "TDCC", "FundClear")}

def lookup_entry(text, resolver=FK.resolve_full_keys):
    spy, calls = [], []
    def loader(q):
        calls.append(q)
        return EP.build_profiles(resolver([q], mapping={}), fetchers=make_fetchers(spy))
    view = FL.lookup_fund(loader, text)
    return {"screen_input": FL.screen_input(text), "loader_calls": calls, "L1_fetch_calls(source,full_key)": spy,
            "state": str(view.state), "reason": view.reason_code}
out["2_lookup_current"] = {BARE: lookup_entry(BARE), SUFFIXED: lookup_entry(SUFFIXED)}

# ── 入口 1a：💼 Sheet 持倉（ui_v3 assets_source；成本基準；resolver 不在此鏈上）
def assets_entry(code):
    hold = X.loaded_tables([X.holding_row(code=code)])
    reads, calls = X.make_reads(M, holdings=hold, known_codes=None)
    r = M.load({}, [X.SECRET], reads=reads)
    p = r.to_primitive()
    return {"status": p["status"], "blocked_reason": p["blocked_reason"], "problems": p["problems"],
            "holding_failure_code": p["holding_failure_code"],
            "evidence_nav_state": [h.get("nav_state") for h in (p["evidence"] or {}).get("holdings", [])] if p["evidence"] else None,
            "evidence_fund_codes": [h.get("fund_code") for h in (p["evidence"] or {}).get("holdings", [])] if p["evidence"] else None}
out["1a_assets_current"] = {BARE: assets_entry(BARE), SUFFIXED: assets_entry(SUFFIXED)}

# ── 入口 1b：Sheet 持倉 → ui_v2 hld／alo 取數鏈（resolver → build_nav_dividend_tables → A 鏈）
# A 鏈以離線替身取代 `ND.auto_fetch_moneydj`。替身的 full_key 規則取自對 `repositories/fund/fund_orchestration.py`
# （約 :1365-1395）的靜態閱讀：code ＝ parse_moneydj_input(輸入) → 別名表 → `result["full_key"] = code`（無別名命中時＝輸入整段，含後綴）。
# 真實 A 鏈對未知後綴碼實際回什麼＝NOT VERIFIED（需真取數）；mode="normalize_to_base" 是「若真實 A 鏈會去後綴」的推演。
from datetime import datetime, timezone
NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
def hld_entry(codes, resolver=FK.resolve_full_keys, mode="echo"):
    kr = resolver(list(codes), mapping={})["results"]
    resolved = {r["input"]: r for r in kr if r["ok"] is True}
    spy = []
    def fake_auto(chain_code, return_page_type=False, **kw):
        spy.append(chain_code)
        key = chain_code.upper() if mode == "echo" else chain_code.upper().split("-")[0]
        s_ = pd.Series([10.0, 10.1], index=pd.to_datetime(["2026-11-18", "2026-11-19"]))
        s_.attrs.update({"currency": "USD", "source": "FAKE:offline", "fetched_at": "2026-11-20T11:00:00Z"})
        res = {"full_key": key, "fund_code": key, "series": s_, "dividends": [], "data_source": "FAKE", "chain_started_at": "2026-11-20T11:00:00Z"}
        return (res, "yp010001") if return_page_type else res
    funds = [{"fund_code": c, "full_key": resolved[c]["full_key"], "portal": resolved[c]["portal"],
              "chain_code": resolved[c]["parsed_code"], "holding_ccy": "USD"} for c in codes if c in resolved]
    orig = ND.auto_fetch_moneydj; ND.auto_fetch_moneydj = fake_auto
    try:
        both = ND.build_nav_dividend_tables(funds, now=NOW) if funds else None
    finally:
        ND.auto_fetch_moneydj = orig
    nav = None if both is None else both["nav"]
    return {"key_ok": {r["input"]: r["ok"] for r in kr}, "key_failed_inputs": [r["input"] for r in kr if r["ok"] is False],
            "A_chain_calls(chain_code)": spy,
            "nav_rows": None if nav is None else [(r["fund_code"], r.get("nav_date"), r.get("nav_orig_ccy", r.get("nav"))) for r in nav["rows"]],
            "nav_errors": None if nav is None else {k: str(v)[:140] for k, v in nav["errors"].items()},
            "nav_withheld": None if nav is None else sorted(nav["withheld"])}
out["1b_hld_chain_current(echo)"] = hld_entry([BARE, SUFFIXED])
out["1b_hld_chain_INFER(chain normalizes to base)"] = hld_entry([BARE, SUFFIXED], mode="normalize_to_base")

# ── 推演（不是實作）：以包裝 resolver 模擬「標示並阻擋」（A）與「標示但保留取數」（A0）
def resolver_A(codes, *, mapping=None):
    r = FK.resolve_full_keys(codes, mapping=mapping)
    for x in r["results"]:
        if "-" in x["input"] and x["ok"]:
            x.update(ok=False, full_key=None, portal=None, error="[推演] 後綴違反（阻擋）")
    return r
def resolver_A0(codes, *, mapping=None):
    r = FK.resolve_full_keys(codes, mapping=mapping)
    for x in r["results"]:
        if "-" in x["input"] and x["ok"]:
            x["sheet_code_contract_violation"] = True   # [推演] 僅附標記，ok／full_key 不變
    return r
out["SIM_A_block"] = {"2_lookup": lookup_entry(SUFFIXED, resolver_A), "1b_hld": hld_entry([BARE, SUFFIXED], resolver_A)}
out["SIM_A0_flag_only"] = {"2_lookup": lookup_entry(SUFFIXED, resolver_A0), "1b_hld": hld_entry([BARE, SUFFIXED], resolver_A0)}

# ── Evidence 一步：持倉帶後綴碼、市價基準、NAV 列缺時，「被標 key_failed」與「沒標」在 Complete Evidence（候選）上的差別。
# 直接呼叫既有生產者（借用測試檔的建構器；Evidence 只把代碼當不透明字串，後綴本身不影響它）。
sys.path.insert(0, str(ROOT / "tests"))
import test_v2_domain_allocation_evidence as T
def evidence_probe():
    E, G, C = T.REAL, T.G, SUFFIXED
    ds = G.DS([G.H(C)], [G.N(BARE, "2026-10-03", 10.0, "USD")], T.FX_STD(), basis=T.MV)
    res = {}
    for label, prov in (("key_failed=[code]", {**T._PROV_CLEAR, "key_failed": [C]}), ("無 key_failed 標記（NAV 列缺）", T._PROV_CLEAR)):
        h = T._by_code(T.build(E, ds, prov=prov, nav_input_state="assembled"), C)
        res[label] = {"nav_state": h.nav_state, "value_twd": h.value_twd, "reason_code": h.reason.code, "nav_cause.key_failed": h.nav_cause.key_failed}
    return res
out["3_evidence_probe"] = evidence_probe()
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
