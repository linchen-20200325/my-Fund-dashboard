#!/usr/bin/env python3
"""scripts/probe_moneydj_nav_equivalence.py — MoneyDJ NAV 等價性探測（只讀 evidence gathering，不接 production）。

客戶裁示（`DEC-2026-10-29-02`，逐字：`docs/evidence/decisions/2026-10-29_dg2_nav_probe_ruling.md`）採方案 A：
對 `TLZF9`／`TLZF9-AL001`／`TLZF9-24A7`／`ACDD01`／`ACDD01-EQTAL005` 取 MoneyDJ 頁面實際 NAV，
判斷「通路後綴是否改變 fund NAV」。**本檔只蒐證**：不改 resolver、不改 NAV precedence、不寫 Sheet／nav_history／cache、
不啟用 DG-2 shadow flag；不因探測成功就把任何 MoneyDJ URL 升格為 production source。

## 做什麼

- 每個輸入：用 `services.fund_identity.resolve_fund_identity`（唯讀呼叫）解出 base 碼與證據；
  再發 GET（依序、間隔 ≥1 秒、timeout 20 秒、最多重試 1 次、回應大小上限）：
  1. `prod_nav30`：production `sources._src_nav_30day` 同款網址 `https://{tcbbankfund|www}.moneydj.com/funddj/ya/{yp010001|yp010000}.djhtm?a={輸入}`；
  2. `platform_hist`／`platform_wb`：輸入命中 `sources._BANK_PLATFORM_CODES` 的完整代碼時，`_src_bank_platform_nav` 會用的平台網址
     （`yf/yp004002.djhtm` 近 30 日窗與 `w/wb/{頁}.djhtm`）；
  3. `basic_info`：`declared_profile._moneydj_urls` 的基本資料頁（只取「基金名稱」「計價幣別」自報欄位）。
  NAV 表解析一律用 production 的 `nav_metrics._parse_nav_html`（唯讀 import，不改它）。
- 兩條連線路徑各量一次：`direct`（runner IP 直連）與 `nas_proxy`（`PROXY_URL` 環境變數 → requests Session proxies，
  比照 `scripts/probe_twse_eps.py`）；未設 `PROXY_URL` → `proxy_not_configured`，不發請求。每筆紀錄標明走哪條。
- 比較引擎（純函式，`compare_observations`／`summarize_group`）：同 base、幣別雙方明示且相同、有共同 NAV 日（取最新共同日）才可比較；
  share class 無法確認一律 `unknown`。結果 `consistent`／`not_comparable`／`conflict`。
  `conflict` 只列「候選原因」（as-of、publication lag、頁型、幣別、share class、平台 stale cache、parser、來源不一致）
  與各自支持／排除的證據，**絕不**下「不同基金」的結論。缺值一律 `None`，不用 0。
- MoneyDJ 連不上 → 記錄實際（遮蔽後）錯誤文字於 `network_blocked`，**停止，不做任何繞路**。

## 2026-10-29 最終整合裁示後的解讀（v1.1）

- TLZF9 家族：保留上面的 strict 規則（幣別需雙方明示），**另加**並列的 `observational`（`strong_observational_evidence`／`conflict`／`incomplete`），
  幣別證據分兩欄記錄（`base_page_reports`、`platform_pages_currency_stated`），**不推定平台頁幣別**。
- ACDD01：以 MoneyDJ 基本基金頁為 baseline（`baseline_verified`／`baseline_failed`）；`EQTAL005` 是保險商品代碼，
  只在 `product_mapping` 區回報（來源＝客戶確認，`mapping_verified_against_moneydj` 預設 None），`ACDD01-EQTAL005` 頁面只當原始觀測、不進 verdict。

## 安全

絕不輸出或記錄 `PROXY_URL`、帳密、host、port（錯誤原文先遮蔽）。報告不存 cookie／header。
唯一輸出是 `--out` 指定的 gzip JSON。本檔不 import 任何寫入模組（守衛測試釘住）。

CLI：`python scripts/probe_moneydj_nav_equivalence.py --out probe_out/moneydj_nav_report.json.gz`
退出碼：報告一律先寫出；沒有任何一頁成功解析出 NAV → 1，否則 0。
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import itertools
import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

_REPO = Path(__file__).resolve().parent.parent
for _p in (str(_REPO), str(_REPO / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from probe_twse_eps import mask_text, secret_literals  # noqa: E402  (stdlib-only 遮蔽工具，同一組 probe 慣例)

SCRIPT_VERSION = "moneydj_nav_equivalence/1.1"
INPUTS: tuple[str, ...] = ("TLZF9", "TLZF9-AL001", "TLZF9-24A7", "ACDD01", "ACDD01-EQTAL005")
# 2026-10-29 客戶最終整合裁示第 5、6 節：ACDD01 家族不再做「NAV 等價」比較——
#   ACDD01 ＝ MoneyDJ 基本基金頁 baseline（`baseline_assessment`）；
#   EQTAL005 ＝ 保險商品代碼（不是 share class／另一檔基金／另一條 NAV 序列），只回報 `product_mapping`，
#   `ACDD01-EQTAL005` 的頁面仍當原始觀測請求（便宜），但不進任何 verdict／comparison。
FAMILIES: dict = {"TLZF9": ("TLZF9", "TLZF9-AL001", "TLZF9-24A7")}
BASELINE_INPUT = "ACDD01"
RAW_ONLY_INPUTS: tuple[str, ...] = ("ACDD01-EQTAL005",)
PRODUCT_MAPPING_REFERENCE_URL = "https://m.moneydj.com/a1.aspx?a=acdd01"   # 客戶 2026-10-29 提供的有效 MoneyDJ 基本頁
SPACING_SEC = 1.0
TIMEOUT_SEC = 20
RETRIES = 1
MAX_BYTES = 3 * 1024 * 1024
RAW_HTML_MAX = 30_000          # 小於此值才把原始 HTML（gzip＋base64）放進報告
SNIPPET_CHARS = 600
RECENT_POINTS = 12
BLOCK_PROBE_N = 3              # 某路徑前 N 個請求都沒拿到 HTTP 200 → 判定該路徑被擋，停止該路徑
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
TRANSPORTS = ("direct", "nas_proxy")

V_CONSISTENT, V_NOT_COMPARABLE, V_CONFLICT, V_BLOCKED = "consistent", "not_comparable", "conflict", "blocked"
# 觀察性裁定（與上面的 strict 規則並列、明確區分；不是 strictly_comparable）
V_STRONG_OBS, V_OBS_CONFLICT, V_OBS_INCOMPLETE = "strong_observational_evidence", "conflict", "incomplete"
V_BASELINE_VERIFIED, V_BASELINE_FAILED = "baseline_verified", "baseline_failed"
CMP_CONSISTENT, CMP_NOT_COMPARABLE, CMP_CONFLICT = "consistent", "not_comparable", "conflict"
UNKNOWN = "unknown"


# ───────────────────────── 純函式：比較引擎 ─────────────────────────

def _recent_map(obs: dict) -> dict:
    return {d: v for d, v in (obs.get("recent") or [])}


def _same_ccy(a, b) -> bool:
    return bool(a) and bool(b) and str(a).strip().upper() == str(b).strip().upper()


def candidate_causes(a: dict, b: dict, compared_date: Optional[str]) -> list:
    """NAV 在可比條件下不一致時的候選原因。每項 `{cause, status, evidence}`；status ∈ supported／ruled_out／unverified。"""
    out = []
    da, db = a.get("nav_date"), b.get("nav_date")
    if da and db and da != db:
        out.append({"cause": "as_of_differs", "status": "supported",
                    "evidence": f"最新 NAV 日不同（{da} vs {db}）；比較取共同日 {compared_date}"})
    else:
        out.append({"cause": "as_of_differs", "status": "ruled_out",
                    "evidence": f"兩邊最新 NAV 日相同或已取共同日 {compared_date} 比較"})
    lag = [x for x in (a, b) if da and db and da != db and x.get("nav_date") == min(da, db)]
    out.append({"cause": "publication_lag",
                "status": "supported" if lag else "unverified",
                "evidence": (f"較舊的一邊（{lag[0].get('input')}／{lag[0].get('kind')}）最新日落後" if lag
                             else "最新日相同，無法證明或排除發布延遲")})
    if a.get("kind") != b.get("kind"):
        out.append({"cause": "page_type", "status": "supported",
                    "evidence": f"頁型不同（{a.get('kind')} vs {b.get('kind')}）"})
    else:
        out.append({"cause": "page_type", "status": "ruled_out", "evidence": f"同頁型 {a.get('kind')}"})
    out.append({"cause": "currency",
                "status": "ruled_out" if _same_ccy(a.get("currency"), b.get("currency")) else "unverified",
                "evidence": f"雙方明示幣別 {a.get('currency')} / {b.get('currency')}"})
    out.append({"cause": "share_class", "status": "unverified",
                "evidence": "頁面未明示 share class，無法確認（一律 unknown）"})
    plat = [x for x in (a, b) if str(x.get("kind", "")).startswith("platform_")]
    other = [x for x in (a, b) if x not in plat]
    stale = bool(plat and other and plat[0].get("nav_date") and other[0].get("nav_date")
                 and plat[0]["nav_date"] < other[0]["nav_date"])
    out.append({"cause": "platform_stale_cache", "status": "supported" if stale else "unverified",
                "evidence": ("平台頁最新日早於另一邊" if stale else "無平台頁落後的證據")})
    out.append({"cause": "parser_difference",
                "status": "ruled_out" if a.get("parser") == b.get("parser") else "unverified",
                "evidence": f"兩邊皆用 {a.get('parser')}（同一個 production 解析函式）"
                if a.get("parser") == b.get("parser") else "解析器不同"})
    out.append({"cause": "source_inconsistency", "status": "unverified",
                "evidence": "上列原因皆未能解釋時，來源本身不一致仍無法排除"})
    return out


def compare_observations(a: dict, b: dict) -> dict:
    """比較兩筆 NAV 觀測。回傳 `{status, reasons, compared_date, nav_a, nav_b, share_class, candidate_causes, scope}`。

    可比條件（裁示第 1 節）：同 base fund、同幣別（雙方明示且相同）、同 NAV 日（取兩邊最近序列的最新共同日）；
    share class 無法確認 → `unknown`。任一必要欄位缺失 → `not_comparable`（缺值是 `None`，不是 0）。
    """
    res = {"a": f"{a.get('input')}|{a.get('kind')}|{a.get('transport')}",
           "b": f"{b.get('input')}|{b.get('kind')}|{b.get('transport')}",
           "scope": "same_input" if a.get("input") == b.get("input") else "cross_input",
           "status": CMP_NOT_COMPARABLE, "reasons": [], "compared_date": None,
           "nav_a": None, "nav_b": None, "share_class": UNKNOWN, "candidate_causes": [],
           "kind_a": a.get("kind"), "kind_b": b.get("kind"),
           # 頁面自報基金名稱不同 → 旗標（僅提示，不是「不同基金」的結論）
           "fund_name_mismatch": bool(a.get("fund_name") and b.get("fund_name")
                                      and str(a["fund_name"]).strip() != str(b["fund_name"]).strip())}
    for x in (a, b):
        if x.get("parse_status") != "ok":
            res["reasons"].append(f"parse_failure:{x.get('input')}|{x.get('kind')}|{x.get('transport')}:{x.get('parse_status')}")
    if res["reasons"]:
        return res
    if not a.get("base") or a.get("base") != b.get("base"):
        res["reasons"].append(f"base_differs_or_missing:{a.get('base')}/{b.get('base')}")
    if not a.get("currency") or not b.get("currency"):
        res["reasons"].append("currency_missing_not_explicit")
    elif not _same_ccy(a["currency"], b["currency"]):
        res["reasons"].append(f"currency_differs:{a['currency']}/{b['currency']}")
    ma, mb = _recent_map(a), _recent_map(b)
    common = sorted(set(ma) & set(mb))
    if not common:
        res["reasons"].append(f"no_common_nav_date(latest {a.get('nav_date')} vs {b.get('nav_date')})")
    if res["reasons"]:
        return res
    d = common[-1]
    res.update(compared_date=d, nav_a=ma[d], nav_b=mb[d])
    if math.isclose(ma[d], mb[d], rel_tol=1e-9, abs_tol=1e-12):
        res["status"] = CMP_CONSISTENT
    else:
        res["status"] = CMP_CONFLICT
        res["candidate_causes"] = candidate_causes(a, b, d)
        res["conclusion"] = "source_conflict_UNVERIFIED（不得據此判定為不同基金）"
    return res


def summarize_group(inputs: tuple, observations: list, comparisons: list, blocked: bool = False) -> dict:
    """單一 family 的裁定。verdict ∈ consistent／not_comparable／conflict／blocked。

    只看 `cross_input` 且該組輸入之間的比較。consistent ＝ 沒有 conflict，且每個輸入都至少出現在一個 consistent 比較裡；
    只有部分輸入被覆蓋 → not_comparable（附 covered／uncovered）。`blocked` ＝ 沒有任何 HTTP 成功的觀測。
    """
    ins = set(inputs)
    mine = [o for o in observations if o.get("input") in ins]
    if blocked or not any(o.get("http_status") == 200 for o in mine):
        return {"verdict": V_BLOCKED, "detail": "沒有任何 HTTP 200 的觀測（見 network_blocked）",
                "covered_inputs": [], "uncovered_inputs": sorted(ins),
                "supports_suffix_does_not_change_nav": None}
    cross = [c for c in comparisons if c["scope"] == "cross_input"
             and c["a"].split("|")[0] in ins and c["b"].split("|")[0] in ins]
    flags = {"fund_name_mismatch_pairs": [f'{c["a"]} ~ {c["b"]}' for c in cross if c.get("fund_name_mismatch")],
             "same_input_conflicts": [f'{c["a"]} ~ {c["b"]}' for c in comparisons if c["scope"] == "same_input"
                                      and c["status"] == CMP_CONFLICT and c["a"].split("|")[0] in ins]}
    conflicts = [c for c in cross if c["status"] == CMP_CONFLICT]
    cons = [c for c in cross if c["status"] == CMP_CONSISTENT]

    def _valid(c):   # 帶後綴的輸入，其一側必須是 platform_* 頁；否則 prod 頁可能只是回傳 base 基金頁（tautology）
        for side in ("a", "b"):
            inp, kind = c[side].split("|")[:2]
            if "-" in inp and not kind.startswith("platform_"):
                return False
        return True
    valid = [c for c in cons if _valid(c)]
    kinds = sorted({f'{c["kind_a"]}~{c["kind_b"]}' for c in cons})
    covered = sorted({c[s].split("|")[0] for c in valid for s in ("a", "b")})
    uncovered = sorted(ins - set(covered))
    extra = f"；一致比較的頁型配對：{kinds}" + (f"；旗標：{ {k: v for k, v in flags.items() if v} }" if any(flags.values()) else "")
    base = {"covered_inputs": covered, "uncovered_inputs": uncovered, **flags}
    if conflicts:
        return {"verdict": V_CONFLICT, "detail": f"{len(conflicts)} 組可比條件下 NAV 不一致（source conflict／UNVERIFIED，非不同基金結論）" + extra,
                **base, "supports_suffix_does_not_change_nav": False}
    if valid and not uncovered:
        return {"verdict": V_CONSISTENT, "detail": f"{len(valid)} 組可比比較全部一致，所有輸入皆被覆蓋（帶後綴者皆有 platform 頁佐證）" + extra,
                **base, "supports_suffix_does_not_change_nav": True}
    reasons = sorted({r.split(":")[0].split("(")[0] for c in cross for r in c["reasons"]})
    if cons and not valid:
        why = "only prod pages compared（帶後綴輸入無 platform 頁佐證，一致可能只是同一 base 頁）"
    elif valid:
        why = "部分一致但未覆蓋全部輸入"
    else:
        why = "沒有任何可比的跨輸入比較"
    return {"verdict": V_NOT_COMPARABLE, "detail": why + f"；不可比原因：{reasons}" + extra,
            **base, "supports_suffix_does_not_change_nav": None}


def _ok_nav(o: dict) -> bool:
    return o.get("kind") != "basic_info" and o.get("parse_status") == "ok" and o.get("nav") is not None and bool(o.get("nav_date"))


def observational_assessment(observations: list, inputs: tuple = FAMILIES["TLZF9"]) -> dict:
    """觀察性裁定（客戶 2026-10-29 最終整合第 7～9 節）。

    base 輸入（prod 頁）與其餘每個平台輸入（platform_* 頁；prod 頁對帶後綴輸入可能只是回傳 base 頁，不算）
    的最新 NAV 日、NAV 值全部相同、且頁面自報基金名稱（有的話）一致、無 identity conflict →
    `strong_observational_evidence`（**僅此一日**；跨日累積由 `scripts/analyze_moneydj_nav_series.py` 計不同 NAV 日）。
    任一不同 → `conflict`（附候選原因，不下「不同基金」結論）；缺任一角色 → `incomplete`。
    **永不**輸出 strictly_comparable；**不推定幣別**：`currency_evidence` 把兩件事分開記，不合併。
    """
    base_in, plat_ins = inputs[0], inputs[1:]
    roles = {base_in: [o for o in observations if o.get("input") == base_in and o.get("kind") in ("prod_nav30", "prod_nav30_alt") and _ok_nav(o)]}
    for pin in plat_ins:
        roles[pin] = [o for o in observations if o.get("input") == pin and str(o.get("kind", "")).startswith("platform_") and _ok_nav(o)]
    plat_obs = [o for pin in plat_ins for o in roles[pin]]
    base_ccy = next((o.get("currency") for o in observations if o.get("input") == base_in and o.get("currency")), None)
    plat_stated = [o.get("currency") for o in plat_obs
                   if o.get("currency") and not str(o.get("currency_source") or "").startswith("basic_info_url")]
    res = {"verdict": V_OBS_INCOMPLETE, "strictly_comparable": False,
           "currency_evidence": {"base_page_reports": base_ccy,
                                 "platform_pages_currency_stated": bool(plat_stated),
                                 "currency_inferred": False,
                                 "note": "missing ≠ known：平台頁未明示幣別時不以 base 頁幣別補入，兩欄各自獨立"},
           "points": [], "differences": [], "candidate_causes": [], "missing_roles": []}
    res["missing_roles"] = [k for k, v in roles.items() if not v]
    all_obs = [o for v in roles.values() for o in v]
    res["points"] = sorted({(o["input"], o["kind"], o["transport"], o["nav_date"], o["nav"]) for o in all_obs})
    res["points"] = [list(p) for p in res["points"]]
    if res["missing_roles"]:
        return res
    dates = {o["nav_date"] for o in all_obs}
    navs = sorted({o["nav"] for o in all_obs})
    nav_differs = any(not math.isclose(navs[0], x, rel_tol=1e-9, abs_tol=1e-12) for x in navs[1:])
    names = {str(o["fund_name"]).strip() for o in all_obs if o.get("fund_name")}
    if len(dates) > 1:
        res["differences"].append(f"nav_date_differs:{sorted(dates)}")
    if nav_differs:
        res["differences"].append(f"nav_value_differs:{navs}")
    if len(names) > 1:
        res["differences"].append(f"fund_name_differs:{sorted(names)}")
    if res["differences"]:
        res["verdict"] = V_OBS_CONFLICT
        a = roles[base_in][0]
        b = next((o for o in all_obs if o is not a and (o["nav_date"] != a["nav_date"] or not math.isclose(o["nav"], a["nav"], rel_tol=1e-9, abs_tol=1e-12))), plat_obs[0])
        res["candidate_causes"] = candidate_causes(a, b, a["nav_date"] if a["nav_date"] == b["nav_date"] else None)
        res["conclusion"] = "conflict_UNVERIFIED（不得據此判定為不同基金）"
        return res
    res["verdict"] = V_STRONG_OBS
    res["nav_date"], res["nav"] = next(iter(dates)), navs[0]
    return res


def baseline_assessment(observations: list, blocked: bool = False) -> dict:
    """ACDD01 baseline（裁示第 5 節）：MoneyDJ 基本基金頁的基金名稱＋幣別（頁面明示）與 NAV／NAV 日都取得 → `baseline_verified`。"""
    mine = [o for o in observations if o.get("input") == BASELINE_INPUT]
    if blocked or not any(o.get("http_status") == 200 for o in mine):
        return {"verdict": V_BLOCKED, "detail": "沒有任何 HTTP 200 的觀測（見 network_blocked）"}
    basic = next((o for o in mine if o.get("kind") == "basic_info" and o.get("parse_status") == "ok"), None)
    nav = next((o for o in mine if _ok_nav(o)), None)
    problems = []
    if not basic or not basic.get("fund_name"):
        problems.append("basic_page_missing_fund_name")
    if not basic or not basic.get("currency"):
        problems.append("currency_not_explicit_on_basic_page")
    if not nav:
        problems.append("nav_or_nav_date_missing")
    out = {"verdict": V_BASELINE_FAILED if problems else V_BASELINE_VERIFIED, "problems": problems,
           "fund_name": basic and basic.get("fund_name"), "currency": basic and basic.get("currency"),
           "currency_source": "basic_info page (explicit)" if basic and basic.get("currency") else None,
           "nav": nav and nav.get("nav"), "nav_date": nav and nav.get("nav_date")}
    return out


def product_mapping_section(observations: list) -> dict:
    """EQTAL005 → ACDD01 是商品對應問題，不是 NAV 等價問題（裁示第 6 節）。

    來源（provenance）＝客戶 2026-10-29 確認；`mapping_verified_against_moneydj` 預設 None（UNVERIFIED），
    只有當請求回來的 `ACDD01-EQTAL005` 頁面片段真的出現 EQTAL005 字樣才改 True。這些頁面只是原始觀測，不進 verdict。
    """
    raw = [o for o in observations if o.get("input") in RAW_ONLY_INPUTS]
    seen = any(o.get("parse_status") == "ok" and "EQTAL005" in str((o.get("raw") or {}).get("snippet_text") or "")
               and "ACDD01" in str((o.get("raw") or {}).get("snippet_text") or "") for o in raw)
    return {"product_code": "EQTAL005", "fund_code": BASELINE_INPUT, "provenance": "customer_confirmed_2026-10-29",
            "reference_evidence_url": PRODUCT_MAPPING_REFERENCE_URL,
            "mapping_verified_against_moneydj": True if seen else None,
            "status": "OBSERVED_ON_PAGE" if seen else "UNVERIFIED",
            "excluded_from_verdicts": True,
            "raw_observations": [{"kind": o.get("kind"), "transport": o.get("transport"), "http_status": o.get("http_status"),
                                  "parse_status": o.get("parse_status"), "nav_date": o.get("nav_date"), "nav": o.get("nav")}
                                 for o in raw],
            "note": "EQTAL005 不是 share class／另一檔基金／另一條 NAV 序列；本區不是 NAV 等價比較"}


# ───────────────────────── 解析（借用 production 函式，唯讀） ─────────────────────────

_TS_RE = re.compile(r"(資料日期|更新日期|更新時間|淨值日期|最新淨值日期)\s*[:：]?\s*([0-9]{2,4}[/\-][0-9]{1,2}(?:[/\-][0-9]{1,2})?(?:\s+[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?)?)")


def parse_nav_page(html: str) -> dict:
    """NAV 頁 → `{series:[(iso,float)...], source_timestamp, title}`；用 production `nav_metrics._parse_nav_html`。"""
    from bs4 import BeautifulSoup
    from repositories.fund.nav_metrics import _parse_nav_html
    s = _parse_nav_html(html)
    series = [(d.date().isoformat(), float(v)) for d, v in s.items()]
    text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    m = _TS_RE.search(text)
    return {"series": series, "source_timestamp": (m.group(0) if m else None)}


def parse_basic_page(html: str) -> dict:
    """基本資料頁 → `{fund_name, currency}`（自報原字面；缺 → None）。用 `declared_profile._parse_label_table`。"""
    from bs4 import BeautifulSoup
    from repositories.fund.declared_profile import _parse_label_table
    fields, _conf = _parse_label_table(BeautifulSoup(html, "lxml"))
    f = fields or {}
    return {"fund_name": f.get("基金名稱") or None, "currency": f.get("計價幣別") or None}


def raw_evidence(body: bytes, html: str, series: list) -> dict:
    """bounded、無 cookie／header 的原始證據參照：sha256＋長度＋純文字片段（＋小頁才附 gzip base64 原文）。"""
    from bs4 import BeautifulSoup
    snippet = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    ev = {"sha256": hashlib.sha256(body).hexdigest(), "length": len(body)}
    if series:
        d, v = series[-1]
        i = snippet.find(d[5:].replace("-", "/"))
        i = max(i - 80, 0) if i >= 0 else 0
        ev["snippet_text"] = snippet[i:i + SNIPPET_CHARS]
    else:
        ev["snippet_text"] = snippet[:SNIPPET_CHARS]
    if len(body) <= RAW_HTML_MAX:
        ev["raw_html_gzip_b64"] = base64.b64encode(gzip.compress(body)).decode()
    return ev


def build_observation(*, input_code: str, base, kind: str, transport: str, url: str, resp: dict,
                      parser_version: str, basic: Optional[dict] = None) -> dict:
    """一次 HTTP 結果 → 觀測紀錄。`basic`：同輸入基本資料頁的 `{fund_name, currency}`（頁面自報；缺 → None）。"""
    obs = {"input": input_code, "base": base, "kind": kind, "transport": transport, "url": url,
           "http_status": resp.get("status"), "latency_ms": resp.get("latency_ms"),
           "error": resp.get("error"), "parse_status": "http_failed", "parser": parser_version,
           "fund_name": None, "nav": None, "nav_date": None, "currency": None, "source_timestamp": None,
           "currency_source": None, "fund_name_source": None, "error_snippet": None,
           "recent": [], "raw": None}
    body = resp.get("body")
    if resp.get("status") != 200 or not body:
        if body:   # 非 200：留一小段遮蔽後的純文字，利於判讀（不存 header／cookie）
            txt = re.sub(r"<[^>]+>", " ", decode_body(body, resp.get("content_type")))
            obs["error_snippet"] = mask_text(" ".join(txt.split())[:300], secret_literals())
        return obs
    html = decode_body(body, resp.get("content_type"))
    if kind == "basic_info":
        b = parse_basic_page(html)
        obs.update(fund_name=b["fund_name"], currency=b["currency"],
                   currency_source="basic_info_url(self)", fund_name_source="basic_info_url(self)",
                   parse_status="ok" if b["fund_name"] else "no_name_table",
                   raw=raw_evidence(body, html, []))
        return obs
    p = parse_nav_page(html)
    series = p["series"]
    obs["raw"] = raw_evidence(body, html, series)
    obs["source_timestamp"] = p["source_timestamp"]
    if not series:
        obs["parse_status"] = "no_nav_table"
        return obs
    obs.update(parse_status="ok", nav=series[-1][1], nav_date=series[-1][0], recent=series[-RECENT_POINTS:])
    if basic:
        obs["fund_name"] = basic.get("fund_name")
        obs["currency"] = basic.get("currency")
        obs["currency_source"] = obs["fund_name_source"] = basic.get("url") and "basic_info_url"
    return obs


def decode_body(body: bytes, content_type: Optional[str]) -> str:
    m = re.search(r"charset=([\w\-]+)", content_type or "", re.I)
    for enc in ([m.group(1)] if m else []) + ["utf-8", "big5hkscs"]:
        try:
            return body.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return body.decode("utf-8", errors="replace")


# ───────────────────────── 網址計畫（網址形狀取自 production，不另造） ─────────────────────────

def plan_urls(input_code: str, channel_table: dict, is_domestic: Callable[[str], bool],
              today: Optional[datetime] = None) -> list:
    """回傳 `[(kind, url, note)]`。prod_nav30 先試首選頁型；平台網址只在輸入命中通路表完整代碼時產生。"""
    code = input_code.strip().upper()
    primary = "yp010000" if is_domestic(code) else "yp010001"
    alt = "yp010001" if primary == "yp010000" else "yp010000"
    plans = []
    for host in ("tcbbankfund.moneydj.com", "www.moneydj.com"):
        plans.append(("prod_nav30", f"https://{host}/funddj/ya/{primary}.djhtm?a={code}", f"page={primary}"))
    for host in ("tcbbankfund.moneydj.com", "www.moneydj.com"):
        plans.append(("prod_nav30_alt", f"https://{host}/funddj/ya/{alt}.djhtm?a={code}", f"fallback page={alt}"))
    now = today or datetime.now(timezone.utc)
    end = now.strftime("%Y%m%d")
    start = (now - timedelta(days=30)).strftime("%Y%m%d")
    for base, rows in channel_table.items():
        for domain, full_code, ptype in rows:
            if full_code.upper() == code and ptype.startswith("moneydj_"):
                page = ptype.split("_")[1]
                plans.append(("platform_hist", f"https://{domain}/funddj/yf/yp004002.djhtm?A={full_code}&B={start}&C={end}",
                              f"_BANK_PLATFORM_CODES:{base}:{ptype}（production 為 2000 日窗，此處縮為 30 日）"))
                plans.append(("platform_wb", f"https://{domain}/w/wb/{page}.djhtm?a={full_code}",
                              f"_BANK_PLATFORM_CODES:{base}:{ptype}"))
    plans.append(("basic_info", None, "declared_profile._moneydj_urls"))   # 網址於執行期由 production 函式產生
    return plans


# ───────────────────────── HTTP ─────────────────────────

def make_http_get(secrets: tuple, session_factory: Optional[Callable] = None):
    """回傳 `http_get(url, transport) -> dict(status, content_type, latency_ms, bytes, body, error)`。GET only。"""
    proxy_url = os.environ.get("PROXY_URL", "").strip()
    sessions: dict = {}

    def _session(transport):
        s = sessions.get(transport)
        if s is None:
            if session_factory:
                s = session_factory(transport)
            else:
                import requests
                s = requests.Session()
                s.trust_env = False
                s.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8",
                                  "Accept-Language": "zh-TW,zh;q=0.9"})
                if transport == "nas_proxy":
                    s.proxies.update({"http": proxy_url, "https": proxy_url})
                    s.verify = False   # Squid CONNECT 相容，比照 fetch_nav_cache.py／probe_twse_eps.py
                    try:
                        import urllib3
                        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    except Exception:  # noqa: BLE001
                        pass
            sessions[transport] = s
        return s

    def http_get(url, transport):
        out = {"status": None, "content_type": None, "latency_ms": None, "bytes": None, "body": None, "error": None}
        last_err = None
        for attempt in range(RETRIES + 1):
            t0 = time.monotonic()
            try:
                r = _session(transport).get(url, timeout=TIMEOUT_SEC, stream=True, allow_redirects=True)
                chunks, total = [], 0
                for ch in r.iter_content(65536):
                    total += len(ch)
                    if total > MAX_BYTES:
                        out["error"] = f"response exceeds {MAX_BYTES} bytes; truncated"
                        break
                    chunks.append(ch)
                r.close()
                out.update(status=r.status_code, content_type=r.headers.get("Content-Type"),
                           latency_ms=round((time.monotonic() - t0) * 1000, 1), bytes=total, body=b"".join(chunks))
                if r.status_code >= 500 and attempt < RETRIES:
                    time.sleep(2)
                    continue
                return out
            except Exception as e:  # noqa: BLE001 — 例外原文照錄（遮蔽後），Fail Loud
                last_err = mask_text(f"{type(e).__name__}: {e}", secrets)
                out.update(status=None, content_type=None, bytes=None, body=None,
                           latency_ms=round((time.monotonic() - t0) * 1000, 1))
                if attempt < RETRIES:
                    time.sleep(2)
        out["error"] = last_err
        return out

    return http_get


# ───────────────────────── 主流程 ─────────────────────────

def _executed_sha() -> str:
    sha = os.environ.get("PROBE_EXECUTED_SHA", "").strip()
    if sha:
        return sha
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(_REPO), capture_output=True, text=True,
                              timeout=10).stdout.strip() or UNKNOWN
    except Exception:  # noqa: BLE001
        return UNKNOWN


def run_probe(http_get: Callable, *, sleep: Callable = time.sleep, secrets: tuple = (),
              inputs: tuple = INPUTS, transports_enabled: Optional[dict] = None,
              on_progress: Optional[Callable] = None) -> dict:
    """依序探測所有輸入；回傳完整報告 dict。`http_get` 可注入（測試用假 fetcher，不連網）。"""
    from repositories.fund.declared_profile import _moneydj_urls
    from repositories.fund.sources import _BANK_PLATFORM_CODES, _is_domestic_code
    from services.fund_identity import resolve_fund_identity

    sha = _executed_sha()
    parser_version = f"{SCRIPT_VERSION}@{sha}"
    enabled = transports_enabled or {"direct": True, "nas_proxy": bool(os.environ.get("PROXY_URL", "").strip())}
    blocked = {t: {"blocked": False, "requests": 0, "ok": 0, "errors": [], "statuses": []} for t in TRANSPORTS}
    report = {"script_version": SCRIPT_VERSION, "executed_sha": sha, "parser_version": parser_version,
              "generated_at_utc": datetime.now(timezone.utc).isoformat(), "complete": False,
              "trigger_sha": os.environ.get("GITHUB_SHA") or None,
              "github_run_id": os.environ.get("GITHUB_RUN_ID") or None,
              "transports": {t: ("enabled" if enabled.get(t) else "proxy_not_configured" if t == "nas_proxy" else "disabled")
                             for t in TRANSPORTS},
              "network_path": "direct＝GitHub runner IP 直連；nas_proxy＝PROXY_URL 環境變數經 NAS 中繼（未設則不發請求）。"
                              "每筆 observation 的 transport 欄標明實際走哪條。",
              "inputs": [], "observations": [], "comparisons": [], "summary": {}, "network_blocked": blocked,
              "safety": "只讀 GET；不寫 Sheet／nav_history／cache；不改 resolver／precedence／flag"}
    last_req = [0.0]

    def fetch(url, transport):
        gap = SPACING_SEC - (time.monotonic() - last_req[0])
        if last_req[0] and gap > 0:
            sleep(gap)
        resp = http_get(url, transport)
        last_req[0] = time.monotonic()
        b = blocked[transport]
        b["requests"] += 1
        b["statuses"].append(resp.get("status"))
        if resp.get("status") == 200:
            b["ok"] += 1
        elif resp.get("error") and len(b["errors"]) < 5:
            b["errors"].append(mask_text(resp["error"], secrets))
        if b["requests"] >= BLOCK_PROBE_N and b["ok"] == 0:
            b["blocked"] = True
        return resp

    for inp in inputs:
        ident = resolve_fund_identity(inp, namespace="moneydj", channel_table=_BANK_PLATFORM_CODES)
        base = ident.base_fund_code
        report["inputs"].append({"original_input": inp, "base_fund_code": base,
                                 "resolver_status": ident.verification_status, "platform_suffix": ident.platform_suffix,
                                 "suffix_provenance": ident.suffix_provenance, "channel_code": ident.channel_code,
                                 "resolver": "services.fund_identity.resolve_fund_identity(namespace='moneydj', shadow)"})
        for transport in TRANSPORTS:
            if not enabled.get(transport) or blocked[transport]["blocked"]:
                continue
            basic = None
            nav_ok = False
            for kind, url, note in plan_urls(inp, _BANK_PLATFORM_CODES, _is_domestic_code):
                if blocked[transport]["blocked"]:
                    break
                if kind == "prod_nav30_alt" and nav_ok:
                    continue
                urls = [(kind, url)] if url else [("basic_info", u) for _h, _p, u in _moneydj_urls(inp)]
                for k, u in urls:
                    if blocked[transport]["blocked"]:
                        break
                    resp = fetch(u, transport)
                    obs = build_observation(input_code=inp, base=base, kind=k, transport=transport, url=u, resp=resp,
                                            parser_version=parser_version, basic=basic)
                    obs["url_note"] = note
                    report["observations"].append(obs)
                    if k == "basic_info" and obs["parse_status"] == "ok":
                        basic = {"fund_name": obs["fund_name"], "currency": obs["currency"], "url": u}
                        break
                    if k in ("prod_nav30", "prod_nav30_alt") and obs["parse_status"] == "ok":
                        nav_ok = True
            # 基本資料頁最後才取（名稱／幣別需回填到本輸入此路徑的 NAV 觀測）
            if basic:
                for o in report["observations"]:
                    if o["input"] == inp and o["transport"] == transport and o["kind"] != "basic_info" and o["parse_status"] == "ok":
                        o["fund_name"], o["currency"] = basic["fund_name"], basic["currency"]
                        o["currency_source"] = o["fund_name_source"] = f'basic_info_url:{basic["url"]}'

        if on_progress:
            on_progress(report)
    # 比較（只用 parse ok 的 NAV 觀測）
    navs = [o for o in report["observations"] if o["kind"] != "basic_info" and o["parse_status"] == "ok"]
    for fam_inputs in FAMILIES.values():
        fam = [o for o in navs if o["input"] in fam_inputs]
        for x, y in itertools.combinations(fam, 2):
            report["comparisons"].append(compare_observations(x, y))
    all_blocked = all((not enabled.get(t)) or blocked[t]["blocked"] for t in TRANSPORTS)
    for name, fam_inputs in FAMILIES.items():
        report["summary"][name] = summarize_group(fam_inputs, report["observations"], report["comparisons"],
                                                  blocked=all_blocked)
        report["summary"][name]["observational"] = (
            {"verdict": V_BLOCKED} if report["summary"][name]["verdict"] == V_BLOCKED
            else observational_assessment(report["observations"], fam_inputs))
    report["summary"][BASELINE_INPUT] = baseline_assessment(report["observations"], blocked=all_blocked)
    report["product_mapping"] = product_mapping_section(report["observations"])
    report["complete"] = True
    return report


def write_report(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(report, ensure_ascii=False, indent=1, allow_nan=False).encode("utf-8")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(gzip.compress(data, 9, mtime=0) if path.name.endswith(".gz") else data)
    tmp.replace(path)


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="probe_out/moneydj_nav_report.json.gz")
    args = ap.parse_args(argv)
    out = Path(args.out)
    secrets = secret_literals()
    report = run_probe(make_http_get(secrets), secrets=secrets,
                       on_progress=lambda r: write_report(r, out))
    # 整份報告再遮蔽一次高熵片段（防錯誤原文漏網）
    text = mask_text(json.dumps(report, ensure_ascii=False), secret_literals(strong_only=True))
    write_report(json.loads(text), out)
    got = any(o["parse_status"] == "ok" and o["kind"] != "basic_info" for o in report["observations"])
    print(f"報告已寫出：{out}；summary={ {k: v['verdict'] for k, v in report['summary'].items()} }")
    return 0 if got else 1


if __name__ == "__main__":
    sys.exit(main())
