"""services/fund_batch.py — 批次基金分析 L2 攤平器(400 檔上傳→逐檔 → 表格列)。

⚠️ **RETAINED-LEGACY(v19.413)**:批次分頁已改用「組合健診大表」引擎
`ui.helpers.fund_grp_health.unified.build_batch_unified_row`,本模組 `analyze_fund_row`
+ 舊 flat schema(`ROW_COLUMNS` / `COLUMN_LABELS_ZH`)**production 0 caller**,僅 test
覆蓋。**保留不刪**(§-1 不主動拔;`tests/test_fund_batch.py` 續驗其單檔攤平契約)。
新功能請改 `build_batch_unified_row`,**勿再擴充本檔**避免兩套 batch schema 分歧。

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
    # 評分(4D 健康度,復用組合健診 SSOT)
    "grade_4d", "score_4d",
    # 淨值
    "nav", "nav_date", "nav_points",
    # 報酬(純 NAV,%);ret_1y_total_pct = 含息
    "ret_1m_pct", "ret_3m_pct", "ret_6m_pct", "ret_1y_pct", "ret_1y_total_pct",
    "ret_3y_ann_pct", "ret_5y_ann_pct",
    # 風險
    "sharpe", "sortino", "calmar", "vol_1y_pct", "max_drawdown_pct",
    # 配息 / 費用(monthly_div_twd = 以 100 萬 TWD 為基準的每月配息)
    "div_yield_pct", "monthly_div_twd", "div_freq", "mgmt_fee",
    # 血緣(§2.2)
    "data_source", "is_sparse",
]

# 批次每月配息基準本金(TWD)—— 對齊組合健診 DEFAULT_PRINCIPAL_TWD,可比較
BATCH_PRINCIPAL_TWD = 1_000_000.0

# status 分類(誠實標示每檔結局)
STATUS_OK = "ok"                 # 指標算成功
STATUS_PARTIAL = "partial"       # 有 NAV 序列但指標不足(序列過短 / 稀疏砍值)
STATUS_NO_NAV = "no_nav"         # 抓到回應但無淨值序列(停售/清算/子網域 403)
STATUS_FETCH_FAIL = "fetch_fail"  # auto_fetch_moneydj 回 error/空 或拋例外
STATUS_UNKNOWN_CODE = "unknown_code"  # 空白 / 無效代號

_DIV_FREQ_LABEL = {12: "月配", 4: "季配", 2: "半年配", 1: "年配"}

# 顯示 / 下載用中文欄名(SSOT;內部 dict key 仍用英文,只在輸出層改名)
COLUMN_LABELS_ZH: dict[str, str] = {
    "code": "代號",
    "name": "名稱",
    "status": "狀態",
    "note": "備註",
    "currency": "計價幣別",
    "grade_4d": "評分(4D)",
    "score_4d": "健康分數",
    "nav": "最新淨值(原幣)",
    "nav_date": "淨值日期",
    "nav_points": "資料筆數",
    "ret_1m_pct": "近1月報酬%",
    "ret_3m_pct": "近3月報酬%",
    "ret_6m_pct": "近6月報酬%",
    "ret_1y_pct": "近1年報酬%",
    "ret_1y_total_pct": "近1年含息報酬%",
    "ret_3y_ann_pct": "近3年年化%",
    "ret_5y_ann_pct": "近5年年化%",
    "sharpe": "夏普值",
    "sortino": "索提諾值",
    "calmar": "卡瑪值",
    "vol_1y_pct": "年化波動%",
    "max_drawdown_pct": "最大回撤%",
    "div_yield_pct": "配息年化率%",
    "monthly_div_twd": "每月配息(基準100萬)",
    "div_freq": "配息頻率",
    "mgmt_fee": "經理費",
    "data_source": "資料來源",
    "is_sparse": "序列稀疏",
}

# status 值 → 中文標籤(顯示 / 下載用)
STATUS_LABELS_ZH: dict[str, str] = {
    STATUS_OK: "✅ 成功",
    STATUS_PARTIAL: "🟡 部分",
    STATUS_NO_NAV: "⬜ 無淨值",
    STATUS_FETCH_FAIL: "❌ 抓取失敗",
    STATUS_UNKNOWN_CODE: "⚠️ 無效代號",
}


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

    # v19.409 hotfix:fd["series"] 常是 pandas Series,**不可**用 `not <Series>`
    # 判真假(觸發 Series.__bool__「ambiguous truth value」ValueError)。當某檔 fallback
    # 回來同時帶 error + 非空 series 時舊寫法即炸。改先用 `is None` / `len()` 安全判斷。
    _series = fd.get("series") if isinstance(fd, dict) else None
    _has_series = _series is not None and len(_series) > 0
    if not fd or (fd.get("error") and not _has_series):
        note = (fd or {}).get("error") or "無資料"
        return _empty_row(code, status=STATUS_FETCH_FAIL, note=str(note)[:100])

    s = _series
    name = fd.get("fund_name") or fd.get("full_key") or code
    if not _has_series:
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

    # v19.412:評分(4D) + 每月配息(100 萬基準)—— 復用組合健診 SSOT builder,單檔失敗不擋整列
    try:
        from services.fx_regime_service import fx_regime_by_ccy as _fxr_fb
        from services.health.report import build_health_analysis_row
        # Layer 3-C:第 5 維(匯率風險)。快取住在 L2 就是為了讓這裡也拿得到 ——
        # 本模組是 L2,構不到 L3 的 helper(§8.2),若少傳會讓同一檔基金
        # 在批次與健診出現不同等第。
        _h = build_health_analysis_row(fd, code, fx_cv_by_ccy=(_fxr_fb() or {}))
        row["grade_4d"] = _h.get("4D Grade")
        row["score_4d"] = _num(_h.get("4D Score"))
    except Exception:  # noqa: BLE001 — 評分算不出 → 留 None,不擋核心列
        pass
    try:
        from services.fund_service import get_latest_fx
        from services.health.report import build_dividend_summary_row
        _fx = 1.0 if ccy == "TWD" else (get_latest_fx(f"{ccy}TWD=X") or None)
        if _fx:
            _d = build_dividend_summary_row(fd, code, principal_twd=BATCH_PRINCIPAL_TWD, fx=_fx)
            row["monthly_div_twd"] = _num(_d.get("每月配息 (TWD)"))
    except Exception:  # noqa: BLE001 — FX/配息算不出 → 留 None(§1 不偽造)
        pass

    return row
