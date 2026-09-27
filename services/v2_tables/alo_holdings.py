# -*- coding: utf-8 -*-
"""資產配置（alo）讀表的 L2：保單分頁＋兩張補充分頁 → `44` 4.1 `holding`、4.4 `policy` 的列。

ui_v2 只經由 `ui_v2/<頁>/source.py` 碰到本檔（`49` §3.3 方案 A；**本輪不接任何 UI**）。
本檔只呼叫 L1 `repositories/policy_supplement_repository.py`，不碰 gspread、不讀 secrets。
**本輪只讀，不寫試算表**（C4）；類別 `bucket` 唯讀（C1、D3），本檔沒有任何寫入路徑。

規則出處（客戶 2026-09-27 及之前的裁示；規格見 scratchpad `alo_sheet_tabs_spec.md` 定稿版）：
- T6：三個來源（保單分頁、`_持倉補充`、`_保單資料`）都讀 `POLICY_SHEET_ID` 那一本；沒設就 fail loud（L1）。
- `_持倉補充` 鍵（保單編號, 基金代號）；比對前兩邊只去前後空白，不改大小寫、不補前導 0。
- R1＝B：`最後核對日` 只收 `YYYY-MM-DD`，換成當日 12:00 台灣時間 ＝ `YYYY-MM-DDT04:00:00Z`，
  填 `holding.last_synced_at`。時刻為推定值（`ACCEPTANCE.md` 第八節 8.1 登記）。不得以讀取時間冒充。
  其他格式（含帶時間、帶時區、沒有時區）一律拒收；U6 在 R1 下只保留紀錄，沒有套用對象。
- U7：`_持倉補充` 同鍵兩列以上 → 整組不採用；`_保單資料` 同保單編號兩列以上 → 整組不採用；
  孤兒列略過並列出；保單分頁有、補充分頁沒有 → 該持倉（或該保單列）不寫入並列出。
- U9：`DIRECT` 列（保單分頁裡 `policy_id` 為 `DIRECT` 的持倉列、`_保單資料` 裡保單編號為 `DIRECT` 的列）
  照讀，但不寫 `policy` 的 `issuer`、`ccy`、`opened_on` 三欄（`44` 4.4 沒有給 DIRECT 值的那三欄；
  **不是** `_持倉補充` 的持有起始日、最後核對日、類別 —— 那三欄照常讀，總管 2026-09-27 更正），
  不產生 `holding`／`policy` 列，並逐筆產生警示，字樣逐字為 `DIRECT_WARNING`。
  `_持倉補充` 裡 DIRECT 鍵的列格式不符時照規格列入 `bad_rows`，不因 DIRECT 而豁免。**這與 `44` HLD-5 的「直接持有」是兩件事**（`ACCEPTANCE.md` 8.2）：
  本檔不產生任何「直接持有」字樣，也不產生 `DIRECT` 保留列（`49` 2.2 補註：第一階段轉換層不產生）。
- U10：`淨投資金額` 空白＝沒填 → 該筆持倉不寫入，不補 0。⚠️ 既有讀取函式把空白讀成 0，
  本層分不出「空白」與「填了 0」，兩者一律當沒填（規格 3.1：不把 0 當成本）。
- U11：基金代號、保單編號必須是字串才比對；既有讀取若把純數字代號轉成數字（前導 0 已消失），
  該筆不寫入並寫明原因，不猜原本的字串。
- U4：`fee_rate_pct` 本輪恆為空（畫面顯示 ⬜）。
- Q4 (a)：`units_shares` 取 `持有單位數`；`cost_orig_ccy` ＝ `持有單位數` × `平均買入單位成本`；任一為 0 或空白 → 沒填。
- Q8：`bucket` 取 `_持倉補充` 的 `類別`，不取保單分頁的 `級別`。空白 → 空值（未分類）。
- T2（總管自決）：`holding_id` ＝ `<保單編號>|<基金代號>|<n>`，n 為同一組鍵在保單分頁讀取順序中的第幾列（從 1 起）。
  同鍵分多列時各自一列（`44` 4.1：顯示時才加總）；組法寫死、同一份來源重跑得同一組 ID。
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from repositories import policy_supplement_repository as repo
from services.v2_tables import contract
from services.v2_tables.masking import mask_message

PolicySupplementError = repo.PolicySupplementError

DIRECT = contract.DIRECT_POLICY_ID
# U9：客戶逐字給出的警示字樣。
DIRECT_WARNING = "DIRECT 列暫不支援，該筆不計入配置"
# U9：DIRECT 列不寫的三欄（`44` 4.4 沒有給 DIRECT 值的欄）。
DIRECT_UNWRITTEN_COLUMNS = ("issuer", "ccy", "opened_on")

# R1＝B：當日 12:00 台灣時間（UTC+8）。
CHECK_DATE_LOCAL_HOUR = 12
TAIPEI = timezone(timedelta(hours=8))

TAB_SUPPLEMENT = repo.TAB_HOLDING_SUPPLEMENT
TAB_PROFILE = repo.TAB_POLICY_PROFILE


def masker(secret_values) -> Callable[[str], str]:
    """秘密值清單 → `mask`。拒收字串（`list("abc")` 會把金鑰拆成單字元去遮）。"""
    if isinstance(secret_values, (str, bytes)):
        raise TypeError("secret_values 須為秘密值的清單，不可直接傳字串")
    values = list(secret_values)
    return lambda message: mask_message(message, values)


def last_synced_at_from_check_date(text) -> str:
    """R1＝B：`YYYY-MM-DD` → 當日 12:00 台灣時間的世界協調時間字串 `YYYY-MM-DDT04:00:00Z`。

    只收整格恰好 `YYYY-MM-DD` 且真實存在的日期；其他一律 ValueError，不猜、不截掉時間、不補零。
    """
    if not isinstance(text, str) or not repo.is_iso_date(text):
        raise ValueError(f"最後核對日只收 YYYY-MM-DD 日期（{text!r}）")
    day = date.fromisoformat(text)
    local = datetime(day.year, day.month, day.day, CHECK_DATE_LOCAL_HOUR, 0, 0, tzinfo=TAIPEI)
    return local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _key_text(value):
    """鍵欄：必須是非空字串；只去前後空白。不是字串 → None（U11：不猜原本的字串）。"""
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _positive_number(value):
    """> 0 的有限數值 → float；0、空白、None、非數值 → None（Q4 (a)：0 或空白＝沒填）。"""
    if not _is_number(value):
        return None
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        return None
    return number


def _holding_reasons(row: dict):
    """保單分頁一列 → (部分欄位, 不寫入的原因清單)。鍵以外的欄。"""
    reasons = []
    fund_name = row.get("fund_name")
    fund_name = fund_name.strip() if isinstance(fund_name, str) else None
    if not fund_name:
        reasons.append("基金名稱空白")
    ccy = row.get("currency")
    ccy = ccy.strip() if isinstance(ccy, str) else None
    if not ccy:
        reasons.append("幣別空白")
    units = _positive_number(row.get("units"))
    if units is None:
        reasons.append("持有單位數空白或為 0（沒填）")
    avg_nav = _positive_number(row.get("avg_nav"))
    if avg_nav is None:
        reasons.append("平均買入單位成本空白或為 0（沒填）")
    invest = row.get("invest_twd")
    cost_twd = None
    if invest is None or invest == "" or (_is_number(invest) and invest == 0):
        reasons.append("淨投資金額空白（沒填）")   # U10：不補 0
    elif isinstance(invest, int) and not isinstance(invest, bool) and invest > 0:
        cost_twd = int(invest)
    else:
        reasons.append(f"淨投資金額不是正整數（{invest!r}）")
    fields = {"fund_name": fund_name, "ccy": ccy, "units_shares": units,
              "cost_orig_ccy": (units * avg_nav) if (units and avg_nav) else None,
              "cost_twd": cost_twd}
    return fields, reasons


def _direct_warning(source: str, **where) -> dict:
    return {"code": "direct_unsupported", "message": DIRECT_WARNING, "source": source, **where}


def _group(records, key_fn):
    groups: dict = {}
    for rec in records:
        groups.setdefault(key_fn(rec), []).append(rec)
    unique = {k: v[0] for k, v in groups.items() if len(v) == 1}
    duplicates = [{"key": k, "rows": [r["_row"] for r in v]} for k, v in groups.items() if len(v) > 1]
    return unique, duplicates


def build_alo_tables(policy_rows, tabs: dict, *, skipped_tabs=(), invest_twd_parse_errors=()) -> dict:
    """純函式：三個來源 → `44` `holding`／`policy` 的列，外加每一種不寫入的原因。

    `policy_rows`：保單分頁的列（`ALL_COLS_V2` 欄名，L1 `load_policy_holding_rows()["rows"]`）。
    `tabs`：L1 `load_supplement_tabs()` 的回傳。
    回傳：
    - `holding`、`policy`：通過 `contract.*_row_problems` 的列（`44` 形狀）；
    - `direct`、`warnings`：U9 的 DIRECT 列與逐筆警示（字樣 `DIRECT_WARNING`）；
    - `skipped_holdings`：保單分頁上沒寫進 `holding` 的列與原因；
    - `missing_supplement`／`duplicate_supplement`／`orphan_supplement`；
    - `missing_profile`／`duplicate_profile`／`orphan_profile`；
    - `bad_rows`、`blank_rows`、`tab_missing`（依分頁）；`skipped_tabs`、`invest_twd_parse_errors` 原樣轉交。
    """
    supp = tabs[TAB_SUPPLEMENT]
    prof = tabs[TAB_PROFILE]
    direct, warnings = [], []

    # ── `_保單資料` ──
    profile_records, profile_bad = [], []
    for rec in prof["records"]:
        if rec["policy_id"].strip() == DIRECT:
            entry = {"source": TAB_PROFILE, "row": rec["_row"], "policy_id": DIRECT,
                     "policy_name": rec["policy_name"], "premium_paid_twd": rec["premium_paid_twd"],
                     "status": rec["status"]}
            direct.append(entry)
            warnings.append(_direct_warning(TAB_PROFILE, row=rec["_row"], policy_id=DIRECT))
        else:
            profile_records.append(rec)
    for bad in prof["bad_rows"]:
        if bad["cells"] and bad["cells"][0].strip() == DIRECT:
            # U9：照讀（不因三欄沒填就當格式不符），但不取任何欄值，只列出並警示。
            direct.append({"source": TAB_PROFILE, "row": bad["row"], "policy_id": DIRECT})
            warnings.append(_direct_warning(TAB_PROFILE, row=bad["row"], policy_id=DIRECT))
        else:
            profile_bad.append(bad)
    profiles, duplicate_profile = _group(profile_records, lambda r: r["policy_id"].strip())

    # ── `_持倉補充` ──
    supp_records = []
    for rec in supp["records"]:
        if rec["policy_id"].strip() == DIRECT:
            # U9 的「三欄不寫」指 `policy` 的 issuer／ccy／opened_on，不是本分頁的三欄（總管 2026-09-27 更正）：
            # DIRECT 持倉的持有起始日、最後核對日、類別照常讀、照常換算；只是不產生 `holding` 列。
            direct.append({"source": TAB_SUPPLEMENT, "row": rec["_row"], "policy_id": DIRECT,
                           "fund_code": rec["fund_code"].strip(), "opened_on": rec["opened_on"],
                           "last_synced_at": last_synced_at_from_check_date(rec["last_checked_on"]),
                           "bucket": rec["bucket"] if rec["bucket"] else None})
            warnings.append(_direct_warning(TAB_SUPPLEMENT, row=rec["_row"], policy_id=DIRECT,
                                            fund_code=rec["fund_code"].strip()))
        else:
            supp_records.append(rec)
    # 格式不符的列（含 DIRECT 鍵的列）照規格：不收，列入 bad_rows。
    supp_bad = list(supp["bad_rows"])
    supplements, duplicate_supplement = _group(
        supp_records, lambda r: (r["policy_id"].strip(), r["fund_code"].strip()))
    duplicate_keys = {d["key"] for d in duplicate_supplement}

    # ── 保單分頁的持倉列 ──
    holdings, skipped, missing_supplement = [], [], []
    used_keys, policy_ids = set(), set()
    occurrence: dict = {}
    for index, row in enumerate(policy_rows):
        pid, code = _key_text(row.get("policy_id")), _key_text(row.get("fund_code"))
        if pid == DIRECT:
            entry = {"source": "保單分頁", "index": index, "policy_id": DIRECT,
                     "fund_code": code, "fund_name": row.get("fund_name")}
            direct.append(entry)
            warnings.append(_direct_warning("保單分頁", index=index, policy_id=DIRECT, fund_code=code))
            if code is not None:
                used_keys.add((DIRECT, code))
            continue
        if pid is None or code is None:
            # U11：純數字代號可能已被讀成數字、前導 0 消失；不拿 str(數字) 去猜原本的字串。
            skipped.append({"index": index, "policy_id": row.get("policy_id"),
                            "fund_code": row.get("fund_code"),
                            "reasons": ["保單編號或基金代號不是文字（可能被試算表轉成數字、前導 0 已遺失），不比對"]})
            continue
        key = (pid, code)
        policy_ids.add(pid)
        used_keys.add(key)
        occurrence[key] = occurrence.get(key, 0) + 1
        holding_id = f"{pid}|{code}|{occurrence[key]}"
        if key in duplicate_keys:
            skipped.append({"index": index, "policy_id": pid, "fund_code": code,
                            "reasons": ["_持倉補充 同一組鍵有兩列以上，整組不採用"]})
            continue
        extra = supplements.get(key)
        if extra is None:
            missing_supplement.append({"policy_id": pid, "fund_code": code})
            skipped.append({"index": index, "policy_id": pid, "fund_code": code,
                            "reasons": ["缺持倉補充"]})
            continue
        fields, reasons = _holding_reasons(row)
        if reasons:
            skipped.append({"index": index, "policy_id": pid, "fund_code": code, "reasons": reasons})
            continue
        out = {
            "holding_id": holding_id,
            "policy_id": pid,
            "fund_code": code,
            "fund_name": fields["fund_name"],
            "ccy": fields["ccy"],
            "units_shares": fields["units_shares"],
            "cost_orig_ccy": fields["cost_orig_ccy"],
            "cost_twd": fields["cost_twd"],
            "opened_on": extra["opened_on"],
            "bucket": extra["bucket"] if extra["bucket"] else None,   # 空白＝未分類（空值）
            "last_synced_at": last_synced_at_from_check_date(extra["last_checked_on"]),
        }
        problems = contract.holding_row_problems(out)
        if problems:
            skipped.append({"index": index, "policy_id": pid, "fund_code": code, "reasons": problems})
            continue
        holdings.append(out)

    orphan_supplement = sorted(
        ({"row": rec["_row"], "key": k} for k, rec in supplements.items() if k not in used_keys),
        key=lambda item: item["row"])

    # ── `policy` 表 ──
    policies, missing_profile, orphan_profile = [], [], []
    duplicate_pids = {d["key"] for d in duplicate_profile}
    for pid, rec in sorted(profiles.items(), key=lambda item: item[1]["_row"]):
        if pid not in policy_ids:
            orphan_profile.append({"row": rec["_row"], "key": pid})
            continue
        out = {"policy_id": pid, "policy_name": rec["policy_name"], "issuer": rec["issuer"],
               "ccy": rec["ccy"], "premium_paid_twd": rec["premium_paid_twd"],
               "fee_rate_pct": None,   # U4：本輪不放，畫面顯示 ⬜；不以 0 代替
               "opened_on": rec["opened_on"], "status": rec["status"]}
        problems = contract.policy_row_problems(out)
        if problems:
            profile_bad.append({"row": rec["_row"], "reason": "；".join(problems),
                                "cells": list(rec["_raw"])})
            continue
        policies.append(out)
    for pid in sorted(policy_ids):
        if pid not in profiles and pid not in duplicate_pids:
            missing_profile.append(pid)

    return {
        "holding": holdings,
        "policy": policies,
        "direct": direct,
        "warnings": warnings,
        "skipped_holdings": skipped,
        "missing_supplement": missing_supplement,
        "duplicate_supplement": duplicate_supplement,
        "orphan_supplement": orphan_supplement,
        "missing_profile": missing_profile,
        "duplicate_profile": duplicate_profile,
        "orphan_profile": orphan_profile,
        "bad_rows": {TAB_SUPPLEMENT: supp_bad, TAB_PROFILE: profile_bad},
        "blank_rows": {TAB_SUPPLEMENT: supp["blank_rows"], TAB_PROFILE: prof["blank_rows"]},
        "tab_missing": {TAB_SUPPLEMENT: supp["tab_missing"], TAB_PROFILE: prof["tab_missing"]},
        "skipped_tabs": list(skipped_tabs),
        "invest_twd_parse_errors": list(invest_twd_parse_errors),
    }


def load_alo_tables(secret_values) -> dict:
    """L3 → 這裡 → L1。讀三個來源後交給 `build_alo_tables`。

    L1 失敗（沒設 `POLICY_SHEET_ID`、標頭不符、上游讀取失敗）→ `PolicySupplementError` 往上拋，
    不吞、不退回別本、不回空表冒充成功。
    """
    mask = masker(secret_values)
    tabs = repo.load_supplement_tabs(mask=mask)
    policy = repo.load_policy_holding_rows(mask=mask)
    return build_alo_tables(policy["rows"], tabs, skipped_tabs=policy["skipped_tabs"],
                            invest_twd_parse_errors=policy["invest_twd_parse_errors"])
