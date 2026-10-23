"""services/fund_grp_health/unified.py — 健診總表的**逐檔額外欄合併器**(L2,零 streamlit、零 `ui.*`)。

2026-10-13 客戶裁示(LINE 推播與舊 UI 解耦):`build_merged_extra_columns` 與它直接用到的
`sharpe_provenance_by_code` / `reconcile_by_code`(含 `SHARPE_SRC_*` 顯示值 SSOT 與
`_RECONCILE_KEYS`)由 `ui/helpers/fund_grp_health/unified.py` **原封搬來** —— 每週換檔推播
`scripts/weekly_switch_notify.py` 依賴它。唯一的介面差異見 `build_merged_extra_columns` docstring。
寬表組裝(`build_unified_health_df` / `build_batch_unified_row` / `_UNIFIED_FRONT` …)
只有舊 UI 用,留在原檔;原檔改從這裡 import 同一份物件(SSOT,不複製)。

資料來源仍是各表的單一 data 函式(`risk.hwm_sigma_by_code` / `risk.risk_compare_by_code` /
`signals.mk_signal_by_code`)—— 不重算、不偽造(§1);缺值由來源填 '—'。

⚠️ **legacy 行動語意,待 BL-0428 重新裁示**(2026-10-23 裁示 2C ＋ Stop Gate「選項 1」,BL-0426):
本模組讀到的 σ rank 一律來自唯一 SSOT `services/fund_position.compute_fund_position`
(配息還原序列、fail closed —— 無法判定時 σ rank 缺值,走既有的「資料不足 / unknown」分支,
不補 0、不當中性)。「基期」欄 / 「淨值×匯率」欄以 `rotation.classify_base(σ rank 字串)` 分類,σ rank 字串由 `risk.hwm_sigma_by_code` 經 SSOT 產生。本模組的買賣 / 加碼 / 換股規則、門檻、決策結構與文字**一字未改**;
σ 位置本身只是「相對自身近一年高點的位置證據」,不是交易建議。
"""
from __future__ import annotations

# ── 「Sharpe 來源」欄的顯示值(SSOT;測試與呼叫端一律 import,不得抄字面值)──────
# 2026-08-10 user 拍板:這一欄印給使用者看,值本身必須是白話。原本印的是
# MoneyDJ 的網頁代號 + 英文期間縮寫,使用者無從得知那是「官方公布值」還是
# 「本站自己算的」—— 而這正是本欄存在的**唯一**理由(§2.2 血緣可辨識)。
#
# 三條規則:
#   1. 官方值一律以「MoneyDJ 官方」開頭,自算值一律以「自算」開頭 → 掃一眼就分得出來。
#   2. 期間資訊不可省(1 年 / 6 個月 / N 天),因為同一欄會混不同期間。
#   3. 六個月那條的重點是「**期間不是一年**」,警告記號與括號註明都不可拿掉 ——
#      拿掉就等於把跨檔比大小的陷阱藏起來。
SHARPE_SRC_OFFICIAL_1Y = "MoneyDJ 官方　1 年"
SHARPE_SRC_OFFICIAL_6M = "⚠️ MoneyDJ 官方　6 個月（非 1 年）"
SHARPE_SRC_SELF_CALC = "自算"          # 有樣本天數時 → f"{SHARPE_SRC_SELF_CALC}　{N} 天"
SHARPE_SRC_UNKNOWN = "⬜ —"


def sharpe_provenance_by_code(funds: list) -> dict:
    """{code: {"Sharpe 來源": 標籤}} —— 大表 `Sharpe 1Y` 欄的**實際**來源與期間(§2.2)。

    大表原本的欄位 help 硬寫「自計算(NAV序列);非MoneyDJ公布值」,但 `m["sharpe"]` 的
    優先序是 **wb07 一年 > wb07 六個月 > 本地自算**(`services/fund_service.py`
    `_sharpe_out`)—— 只要 MoneyDJ wb07 有值(境外基金常態),顯示的就是官方值,斷言與事實
    完全相反;wb07 **六個月**命中時欄名還寫死「1Y」。

    值取自 `calc_metrics` 已經算好的 `metrics.risk_metric_meta.sharpe`(不重算、不推測),
    fund dict 由 `_build_fund_dict` 包裝 → `metrics` 即 calc_metrics 產物。
    缺 meta(舊 cache / 抓取失敗)→ `⬜ —`,**不猜**(§1)。

    顯示值走本模組頂部四個常數(SSOT)——「官方」與「自算」以開頭字樣區分,期間寫在後面。

    ⚠️ 同一欄可能混三種期間(官方一年 / 官方六個月 / 本地 N 天),跨檔比大小前必須看本欄;
    換標策略分的 Sharpe tier 目前**未**依期間分層(§4.1 期間錯配殘留風險,見報告提案)。
    """
    out: dict = {}
    for _f in (funds or []):
        _code = str((_f or {}).get("code") or "").strip()
        if not _code:
            continue
        _mt = (((_f.get("metrics") or {}).get("risk_metric_meta") or {}).get("sharpe") or {})
        _src = _mt.get("source")
        if _src == "wb07_1y":
            _lbl = SHARPE_SRC_OFFICIAL_1Y
        elif _src == "wb07_6m":
            _lbl = SHARPE_SRC_OFFICIAL_6M
        elif _src == "self_calc":
            _d = _mt.get("period_days")
            _lbl = (f"{SHARPE_SRC_SELF_CALC}　{_d} 天" if isinstance(_d, int)
                    else SHARPE_SRC_SELF_CALC)
        else:
            _lbl = SHARPE_SRC_UNKNOWN
        out[_code] = {"Sharpe 來源": _lbl}
    return out


_RECONCILE_KEYS = ("sharpe_reconcile", "ret_1y_reconcile", "div_yield_reconcile")


def reconcile_by_code(funds: list) -> dict:
    """{code: {"對帳": worst-of-3 標籤}} —— Sharpe / 1Y報酬 / 配息率 三組雙演算法對帳的最差態。

    §4.3:個基深掘頁(單一基金)有逐項 agree/disagree chip,但批次 / 健檢 / 帳本大表原本沒有 →
    400 檔換標決策拿的是**未經「自算 vs MoneyDJ 官方值」交叉驗證**的單一數字。本欄接出
    `calc_metrics` / `finalize_fund_metrics` **已算好**的三組 reconcile(`metrics.sharpe_reconcile`
    / `ret_1y_reconcile` / `div_yield_reconcile`,§1 不重算、不新抓),取最差態當決策面旗標:
      - 任一組 `disagree` → **⚠️ 有矛盾**(自算與官方差距大;跳個基深掘頁看逐項)
      - 無矛盾且至少一組 `agree` → **✅ 一致**(全部可對且相符)/ **✅ 部分**(其餘單源無對照)
      - 三組皆無法對帳(單源 / 缺值:a_missing / b_missing / both_missing)→ **⬜ 單源**
      - 完全無 metrics(舊 cache / 抓取失敗)→ **⬜ —**(不猜,§1)
    """
    out: dict = {}
    for _f in (funds or []):
        _code = str((_f or {}).get("code") or "").strip()
        if not _code:
            continue
        _m = (_f.get("metrics") or {})
        _states = [(_m.get(_k) or {}).get("status")
                   for _k in _RECONCILE_KEYS if isinstance(_m.get(_k), dict)]
        _states = [s for s in _states if s]
        if not _states:
            _lbl = "⬜ —"
        elif "disagree" in _states:
            _lbl = "⚠️ 有矛盾"
        elif "agree" in _states:
            _lbl = "✅ 一致" if all(s == "agree" for s in _states) else "✅ 部分"
        else:
            _lbl = "⬜ 單源"
        out[_code] = {"對帳": _lbl}
    return out


def build_merged_extra_columns(funds: list, phase: str = "", score=None, *,
                               signal_by_code=None) -> tuple:
    """回傳 (col_order, combined)。

    - col_order:list[str],新欄依 HWM σ → 風險 → 出現順序、去重後的欄名。
    - combined:dict[code -> {欄名: 值}],同名欄「先到先得」(如「現價」HWM 版優先,版略過)。

    phase/score 給 訊號用(由呼叫端從 session_state.phase_info 取);缺則 訊號欄 '—'。

    2026-10-13(LINE 推播與舊 UI 解耦)—— 由 `ui/helpers/fund_grp_health/unified.py` 原封搬來,
    **只多一個 keyword `signal_by_code`**:`(funds, phase, score) -> {code: {欄: 值}}`。
    舊 UI 的同名函式會注入 `ui/helpers/fund_grp_health/signals.py::mk_signal_by_code`
    (它負責解析讀 `st.session_state` 的 `mk_fund_signal`,L2 不得 import);
    不注入(每週換檔推播排程)→ 用 L2 `services.fund_grp_health.signals.mk_signal_by_code`。
    其餘欄位、欄序、先到先得規則一字未改。
    """
    from services.fund_grp_health.capture import capture_by_code
    from services.fund_grp_health.quality import quality_score_by_code
    from services.fund_grp_health.risk import hwm_sigma_by_code, risk_compare_by_code
    from services.fund_grp_health.signals import mk_signal_by_code as _svc_mk_signal_by_code

    # 2026-10-13:舊 UI 注入它自己那版(會解析讀 session_state 的 `mk_fund_signal`);
    # 未注入(排程)→ L2 版,phase="" 時兩版輸出逐字相同(見 signals.mk_signal_by_code)。
    mk_signal_by_code = signal_by_code if signal_by_code is not None else _svc_mk_signal_by_code

    # v19.496:capture 算一次,同時餵「捕捉率欄」與「相對品質分」的操盤因子(不重算、不重抓基準)
    _capture = capture_by_code(funds)
    maps = [
        hwm_sigma_by_code(funds),
        risk_compare_by_code(funds),
        mk_signal_by_code(funds, phase, score),
        _capture,                    # v19.414 上/下檔捕捉率 + 操盤評分;v19.420 + vs 大盤%(同一基準)
        sharpe_provenance_by_code(funds),   # Sharpe 實際來源/期間(§2.2;大表原本硬說「非官方值」)
        reconcile_by_code(funds),    # v19.492 §4.3 雙演算法對帳旗標(worst-of-3;決策面缺口補上)
        quality_score_by_code(funds, capture_map=_capture),  # v19.496 A1 同類相對品質分(6因子+MoneyDJ大母體錨定)
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

    # v19.421 —「基期」標籤欄:由 σ rank 分高/中/低(reuse rotation.classify_base),
    # 讓 user 一眼看出高基期(貼近高點)/ 低基期(跌深)標的,不必自己讀 σ 數字。
    from services.rotation import classify_base
    from shared.signal_thresholds import ROTATION_BUY_SIGMA, ROTATION_SELL_SIGMA
    # 2026-09-02 T29:用字走 `_utils.BASE_LABELS` SSOT(原為本函式內的區域變數,
    # 全 repo 三份手抄、彼此 import 不到)。
    from services.fund_grp_health._utils import BASE_LABELS as _BASE_LBL
    for _slot in combined.values():
        _slot["基期"] = _BASE_LBL[
            classify_base(_slot.get("σ rank"), ROTATION_SELL_SIGMA, ROTATION_BUY_SIGMA)]
    if "基期" not in col_order:
        col_order.append("基期")
    return col_order, combined
