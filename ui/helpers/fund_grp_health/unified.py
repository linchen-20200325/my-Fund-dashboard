"""ui/helpers/fund_grp_health/unified.py — 健診總表寬表合併器(v19.408)。

user 要求:組合健診原本對同一批基金重複畫 3 張逐檔表(HWM σ / 風險對比 / MK 買賣點),
去重複合併進「健診總表」成一張大表。本模組提供純函式合併器(無 streamlit,可單元測試):
把 3 組 by-code 欄位 join 成 (欄序, code→欄值),現價等重複欄「先到先得」去重。

資料來源仍是各表的單一 data 函式(`risk.hwm_sigma_by_code` / `risk.risk_compare_by_code` /
`signals.mk_signal_by_code`)—— 不重算、不偽造(§1);缺值由來源填 '—'。
"""
from __future__ import annotations


def build_merged_extra_columns(funds: list, phase: str = "", score=None) -> tuple:
    """回傳 (col_order, combined)。

    - col_order:list[str],新欄依 HWM σ → 風險 → MK 出現順序、去重後的欄名。
    - combined:dict[code -> {欄名: 值}],同名欄「先到先得」(如「現價」HWM 版優先,MK 版略過)。

    phase/score 給 MK 訊號用(由呼叫端從 session_state.phase_info 取);缺則 MK 訊號欄 '—'。
    """
    from ui.helpers.fund_grp_health.risk import hwm_sigma_by_code, risk_compare_by_code
    from ui.helpers.fund_grp_health.signals import mk_signal_by_code

    maps = [
        hwm_sigma_by_code(funds),
        risk_compare_by_code(funds),
        mk_signal_by_code(funds, phase, score),
    ]
    combined: dict = {}
    col_order: list[str] = []
    for _m in maps:
        for _code, _cols in _m.items():
            slot = combined.setdefault(_code, {})
            for _k, _v in _cols.items():
                if _k not in slot:          # 先到先得 → 重複欄(現價)去重
                    slot[_k] = _v
        for _cols in _m.values():
            for _k in _cols:
                if _k not in col_order:
                    col_order.append(_k)
    return col_order, combined


# 合併大表(①②③ 去重複)欄序 + 各欄來源(SSOT)。v19.411。
# source:health(① 4D/6F/3-3-3)/ div(② 配息 official + 每月配息 + 換標的)/
#         extra(σ/HWM/MK 買賣點,build_merged_extra_columns 產物)/ base(③ 健診總表本身)。
# 去重原則:同一指標只留一份 —— Sharpe/Sortino/Calmar/Alpha 用 ①(extra 版略);
# 吃本金/MK 3-3-3 用 ③(base;②①的同義欄略);現價由 extra 提供。
_UNIFIED_FRONT: list = [
    # ① 分類 + 評分
    ("基金類別", "health"), ("核心/衛星", "health"), ("分類依據", "health"),
    ("4D Grade", "health"), ("4D Score", "health"),
    # ① 報酬 / 風險 6 進階指標
    ("Sharpe 1Y", "health"), ("Sortino", "health"), ("Calmar", "health"),
    ("Alpha %", "health"), ("費用率 %", "health"), ("Max DD %", "health"),
    ("3Y 年化 %", "health"), ("5Y 年化 %", "health"),
    # ② 配息 official(wb01/wb05)+ 每月配息
    ("1Y 含息 %", "div"), ("1Y 來源", "div"), ("年化配息率 %", "div"),
    ("每月配息 (TWD)", "div"), ("每月配息單位數", "div"), ("配息來源", "div"),
    # 判定(吃本金/換標的/3-3-3)
    ("吃本金燈號 (1Y · MK)", "base"), ("換標的建議", "div"), ("MK 3-3-3 篩", "base"),
    # σ 位階 / MK 買賣點(extra;Sharpe/Sortino/Calmar/Alpha 已由 ① 提供故此處不重列)
    ("現價", "extra"), ("HWM", "extra"), ("距 HWM %", "extra"), ("σ rank", "extra"),
    ("HWM 位階", "extra"), ("σ (年化%)", "extra"), ("Beta", "extra"),
    ("資產屬性", "extra"), ("操作訊號", "extra"),
    ("買 3 (深跌)", "extra"), ("買 1 (小跌)", "extra"),
    ("賣 1 (小漲)", "extra"), ("賣 3 (大漲)", "extra"), ("現價位階", "extra"),
]


def _unified_columns(base_cols: list) -> tuple:
    """依 base 欄名算出 (最終欄序, 各欄來源) —— build_unified_health_df / build_unified_row 共用。"""
    front_names = {c for c, _ in _UNIFIED_FRONT}
    remaining_base = [c for c in base_cols if c not in ("code", "基金名") and c not in front_names]
    columns = ["code", "基金名"] + [c for c, _ in _UNIFIED_FRONT] + remaining_base
    col_source = {"code": "base", "基金名": "base"}
    for c, s in _UNIFIED_FRONT:
        col_source[c] = s
    for c in remaining_base:
        col_source[c] = "base"
    return columns, col_source


def build_unified_row(base_row: dict, health_row: dict, div_row: dict, extra_row: dict) -> dict:
    """單檔版 build_unified_health_df:①②③+extra 併成一列 flat dict(去 base 底線私有欄)。"""
    base = {k: v for k, v in (base_row or {}).items() if not str(k).startswith("_")}
    columns, col_source = _unified_columns(list(base.keys()))
    src = {"base": base, "health": health_row or {}, "div": div_row or {}, "extra": extra_row or {}}
    return {col: src[col_source[col]].get(col) for col in columns}


def build_unified_health_df(base_df, health_by_code: dict, div_by_code: dict,
                            extra_by_code: dict):
    """把 ①②③ + σ/風險/MK 依 code join 成一張去重複寬表(§1:缺欄留 None)。

    - base_df:③ 健診總表 DataFrame(含 code 欄 + 全期實際/年化 self-calc + 持有 meta)。
    - health_by_code / div_by_code / extra_by_code:①/②/σ風險MK 的 {code: {欄:值}}。

    欄序:code, 基金名 → _UNIFIED_FRONT(①②+extra 去重)→ 其餘 base ③ 欄(持有 meta,末端)。
    回傳新 DataFrame(欄固定、依 base_df 的 code 順序)。
    """
    import pandas as pd

    base_by_code: dict = {}
    codes: list = []
    _cols = list(getattr(base_df, "columns", []))
    if "code" in _cols:
        for _rec in base_df.to_dict("records"):
            _c = str(_rec.get("code"))
            base_by_code[_c] = _rec
            codes.append(_c)

    _src = {"health": health_by_code or {}, "div": div_by_code or {},
            "extra": extra_by_code or {}, "base": base_by_code}

    # 來源整組沒供資料(如 Tab3 持倉健診不傳 extra)→ 該組欄整批不出現,避免一排空白欄
    # 讓使用者誤以為「資料壞了」(對抗式驗證發現的 UX 回歸)。
    _front = [(c, s) for c, s in _UNIFIED_FRONT if _src.get(s)]
    front_names = {c for c, _ in _front}
    remaining_base = [c for c in _cols if c not in ("code", "基金名") and c not in front_names]

    columns = ["code", "基金名"] + [c for c, _ in _front] + remaining_base
    col_source = {"code": "base", "基金名": "base"}
    for c, s in _front:
        col_source[c] = s
    for c in remaining_base:
        col_source[c] = "base"

    out = [
        {col: _src[col_source[col]].get(_c, {}).get(col) for col in columns}
        for _c in codes
    ]
    df = pd.DataFrame(out, columns=columns)
    # ①② 數值欄來自 dict → object dtype(None 會顯示字面「None」);顯式轉 numeric →
    # NumberColumn format 後 None/NaN 顯示空白(對齊原 ①② 表 v19.191 to_numeric 處理)。
    for _c in _UNIFIED_NUMERIC:
        if _c in df.columns:
            df[_c] = pd.to_numeric(df[_c], errors="coerce")
    return df


# ①② 併入後需轉 numeric 的欄(extra σ/MK 欄為預格式化字串,保持字串不轉)
_UNIFIED_NUMERIC: list = [
    "4D Score", "Sharpe 1Y", "Sortino", "Calmar", "Alpha %", "費用率 %",
    "Max DD %", "3Y 年化 %", "5Y 年化 %",
    "1Y 含息 %", "年化配息率 %", "每月配息 (TWD)", "每月配息單位數",
]


# ── 批次分析:每檔跑成一列「組合健診大表」flat row(JSON-safe → 可存 checkpoint)v19.413 ──
# process_one_fund 回傳的非底線 base 欄(供 failed 檔也對齊完整欄位)
_BATCH_BASE_KEYS: list = [
    "code", "基金名", "幣別偵測", "ccy", "fx_spot", "principal_ccy 🧮", "units 🧮",
    "配息次數", "累積 TWD 配息 🧮", "年均配息 TWD 🧮",
    "配息率% (全期實際)", "淨值% (全期實際)", "含息% (全期實際)",
    "配息率% (年化)", "淨值% (年化)", "含息% (年化)",
    "吃本金燈號 (1Y · MK)", "MK 3-3-3 篩", "MK 倉位", "最高經理費%", "配息頻率", "換匯資訊 🧮",
]
# 批次寬表固定欄序:code, 基金名, 狀態, 備註 → ①②extra(FRONT)→ base 末段
_batch_data_cols, _ = _unified_columns(_BATCH_BASE_KEYS)
BATCH_UNIFIED_COLUMNS: list = (
    ["code", "基金名", "狀態", "備註"]
    + [c for c in _batch_data_cols if c not in ("code", "基金名")]
)
# 批次寬表需轉 numeric 的欄(供 UI NumberColumn;含批次獨有 fx_spot 等 base 數值)
BATCH_NUMERIC_COLUMNS: list = _UNIFIED_NUMERIC + [
    "fx_spot", "principal_ccy 🧮", "units 🧮", "配息次數",
    "累積 TWD 配息 🧮", "年均配息 TWD 🧮",
    "配息率% (全期實際)", "淨值% (全期實際)", "含息% (全期實際)",
    "配息率% (年化)", "淨值% (年化)", "含息% (年化)",
]


def build_batch_unified_row(code: str, principal_twd: float = 1_000_000.0,
                            phase: str = "", score=None) -> dict:
    """批次:單檔 → 一列「組合健診大表」flat row(欄 = BATCH_UNIFIED_COLUMNS,JSON-safe)。

    走 process_one_fund(L2)+ ①`build_health_analysis_row` ②`build_dividend_summary_row`
    + σ/風險/MK `build_merged_extra_columns` → `build_unified_row`。
    §1 fail-loud:失敗回「狀態 != 成功」列(數值留 None,不填假值);整檔不外拋。
    """
    code = (code or "").strip().upper()

    def _blank(status, note, name=None):
        r = {c: None for c in BATCH_UNIFIED_COLUMNS}
        r["code"] = code
        r["基金名"] = name
        r["狀態"] = status
        r["備註"] = note
        return r

    if not code:
        return _blank("⚠️ 無效代號", "空白代號")

    from services.fund_row import process_one_fund
    try:
        base = process_one_fund(code, principal_twd)
    except Exception as e:  # noqa: BLE001 — 單檔炸掉收成失敗列
        return _blank("❌ 抓取失敗", f"{type(e).__name__}: {str(e)[:80]}")
    if not base.get("ok"):
        return _blank("❌ 抓取失敗", str(base.get("error", ""))[:100], name=base.get("基金名"))

    fd = base.get("_fund_raw") or {}
    from services.health.report import build_dividend_summary_row, build_health_analysis_row
    try:
        _health = build_health_analysis_row(fd, code)
    except Exception:  # noqa: BLE001
        _health = {}
    try:
        _div = {k: v for k, v in build_dividend_summary_row(
                    fd, code, principal_twd=principal_twd, fx=base.get("fx_spot")).items()
                if not str(k).startswith("_")}
    except Exception:  # noqa: BLE001
        _div = {}
    try:
        from ui.helpers.fund_grp_health._utils import _build_fund_dict
        _, _extra_map = build_merged_extra_columns(
            [_build_fund_dict(fd, code, principal_twd)], phase, score)
        _extra = _extra_map.get(code, {})
    except Exception:  # noqa: BLE001
        _extra = {}

    _row = build_unified_row(base, _health, _div, _extra)
    out = {c: _row.get(c) for c in BATCH_UNIFIED_COLUMNS}
    out["code"] = code
    out["狀態"] = "✅ 成功"
    out["備註"] = None
    return out
