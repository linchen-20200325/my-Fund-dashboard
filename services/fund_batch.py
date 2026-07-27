"""services/fund_batch.py — 批次基金分析 L2 攤平器(400 檔上傳→逐檔 → 表格列)。

單一職責:給「一個基金代號」,呼既有單檔引擎 `auto_fetch_moneydj`(內部走
enriched wrapper → `finalize_fund_metrics` → `calc_metrics`),把回傳結構
**攤平成一列 flat dict** + `status`,供 L3 批次 UI 累積成表下載。

§1 Fail Loud:任一檔抓不到 / 幣別未知 / NAV 序列過短 → 回 `status != "ok"` 的列,
數值欄一律留 `None`(**絕不填 0、絕不靜默丟棄**),原因寫進 `note`。呼叫端據 `status`
統計成功/失敗,失敗檔仍完整出現在下載表裡(可追溯)。

§4.1 單位陷阱:數值欄名一律編碼單位(`*_pct` = 百分比、`nav` = 原幣淨值、
`vol_1y_pct` = 年化標準差%);報酬為「純 NAV 報酬」,含息另列 `ret_1y_total_pct`。

架構(§8.2):L3 批次 UI → 本模組(L2)→ `services.moneydj_fetcher.auto_fetch_moneydj`
(L2)→ `services.fund_service`(L2)→ `repositories/fund*`(L1)。純編排,無 I/O、
無 streamlit、無上行 import。本模組為純函式,fastmcp/streamlit 皆非依賴,可獨立單元測試。
"""
from __future__ import annotations

from typing import Any

# 攤平欄位順序(SSOT)—— UI 下載表依此順序輸出。§4.1:欄名編碼單位。
ROW_COLUMNS: list[str] = [
    # 身分 / 狀態
    "code", "name", "status", "note", "currency",
    # 淨值
    "nav", "nav_date", "nav_points",
    # 報酬(純 NAV,%);ret_1y_total_pct = 含息
    "ret_1m_pct", "ret_3m_pct", "ret_6m_pct", "ret_1y_pct", "ret_1y_total_pct",
    "ret_3y_ann_pct", "ret_5y_ann_pct",
    # 風險
    "sharpe", "sortino", "calmar", "vol_1y_pct", "max_drawdown_pct",
    # 配息 / 費用
    "div_yield_pct", "div_freq", "mgmt_fee",
    # 血緣(§2.2)
    "data_source", "is_sparse",
]

# status 分類(誠實標示每檔結局)
STATUS_OK = "ok"                 # 指標算成功
STATUS_PARTIAL = "partial"       # 有 NAV 序列但指標不足(序列過短 / 稀疏砍值)
STATUS_NO_NAV = "no_nav"         # 抓到回應但無淨值序列(停售/清算/子網域 403)
STATUS_FETCH_FAIL = "fetch_fail"  # auto_fetch_moneydj 回 error/空 或拋例外
STATUS_UNKNOWN_CODE = "unknown_code"  # 空白 / 無效代號

_DIV_FREQ_LABEL = {12: "月配", 4: "季配", 2: "半年配", 1: "年配"}


def _num(v: Any) -> "float | None":
    """§1:數值化,NaN / inf / bool / 無法轉 → None(絕不偽造成 0)。收口 SSOT safe_num。"""
    from shared.converters import safe_num
    return safe_num(v)


def _empty_row(code: str, name: str = "", *, status: str, note: str = "") -> dict:
    """建一列全 None 的骨架,只填身分 + 狀態(數值欄留 None)。"""
    row: dict[str, Any] = {c: None for c in ROW_COLUMNS}
    row["code"] = code
    row["name"] = name or code
    row["status"] = status
    row["note"] = note or None
    return row


def analyze_fund_row(code: str) -> dict:
    """單檔基金 → 一列 flat dict(欄位見 ROW_COLUMNS)。

    fail-loud:任何失敗都回「一列」而非拋例外(整批不可被單檔拖垮),
    以 `status` + `note` 誠實標示,數值欄留 None。

    回傳的 dict **保證** key 集合 == ROW_COLUMNS(UI 可安全轉 DataFrame)。
    """
    code = (code or "").strip().upper()
    if not code:
        return _empty_row(code, status=STATUS_UNKNOWN_CODE, note="空白代號")

    # lazy import:避免 test 只驗攤平邏輯時被迫載入整條抓取鏈
    from services.moneydj_fetcher import auto_fetch_moneydj
    from services.currency import normalize_ccy

    # ── 抓取(單檔炸掉 → 收成 fetch_fail 列,不外拋)──────────────
    try:
        fd = auto_fetch_moneydj(code)
    except Exception as e:  # noqa: BLE001 — 邊界層:單檔例外翻成失敗列
        return _empty_row(code, status=STATUS_FETCH_FAIL,
                          note=f"{type(e).__name__}: {str(e)[:80]}")

    if not fd or (fd.get("error") and not fd.get("series")):
        note = (fd or {}).get("error") or "無資料"
        return _empty_row(code, status=STATUS_FETCH_FAIL, note=str(note)[:100])

    s = fd.get("series")
    name = fd.get("fund_name") or fd.get("full_key") or code
    if s is None or len(s) == 0:
        return _empty_row(code, name, status=STATUS_NO_NAV, note="無淨值序列(停售/清算/子網域封鎖?)")

    metrics = fd.get("metrics") or {}
    ccy = normalize_ccy(fd.get("currency"), default="") or (metrics.get("currency") or "")

    # 指標空 = calc_metrics 因序列過短(<10 筆)未計算 → partial,誠實標示
    status = STATUS_OK if metrics else STATUS_PARTIAL

    row = _empty_row(code, name, status=status)
    row["currency"] = ccy or None
    row["nav"] = _num(metrics.get("nav"))
    try:
        row["nav_date"] = str(s.index[-1])[:10]
    except Exception:  # noqa: BLE001 — index 非日期時退為 None
        row["nav_date"] = None
    row["nav_points"] = int(len(s))

    # 報酬(§4.1:純 NAV 報酬 %;含息單列)
    row["ret_1m_pct"] = _num(metrics.get("ret_1m"))
    row["ret_3m_pct"] = _num(metrics.get("ret_3m"))
    row["ret_6m_pct"] = _num(metrics.get("ret_6m"))
    row["ret_1y_pct"] = _num(metrics.get("ret_1y"))
    row["ret_1y_total_pct"] = _num(metrics.get("ret_1y_total"))
    row["ret_3y_ann_pct"] = _num(metrics.get("ret_3y_ann"))
    row["ret_5y_ann_pct"] = _num(metrics.get("ret_5y_ann"))

    # 風險
    row["sharpe"] = _num(metrics.get("sharpe"))
    row["sortino"] = _num(metrics.get("sortino"))
    row["calmar"] = _num(metrics.get("calmar"))
    row["vol_1y_pct"] = _num(metrics.get("std_1y"))
    row["max_drawdown_pct"] = _num(metrics.get("max_drawdown"))

    # 配息 / 費用
    row["div_yield_pct"] = _num(metrics.get("annual_div_rate"))
    _freq = metrics.get("div_freq_n")
    row["div_freq"] = _DIV_FREQ_LABEL.get(_freq) if _freq in _DIV_FREQ_LABEL else None
    row["mgmt_fee"] = (fd.get("mgmt_fee") or "").strip() or None

    # 血緣 + 稀疏誠實旗標(§1 / §2.2)
    row["data_source"] = fd.get("data_source") or None
    _sparse = bool(metrics.get("is_sparse", False))
    row["is_sparse"] = _sparse
    if _sparse and metrics.get("sparse_reason"):
        # finalize 已把稀疏期的年化自算值砍成 None;此處把原因寫進 note 供閱讀
        row["note"] = str(metrics.get("sparse_reason"))[:150]

    return row
