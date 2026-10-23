"""services/fund_screening.py — 基金品質篩選（L2 純計算）

職責（單一）：提供基金篩選純函式（ 3-3-3 原則 + 低基期進場點）；
無 I/O、無 Streamlit。

§8.2 分層：L2 Service — 禁止 import requests / httpx / streamlit。
資料由 L3 UI 從 session_state 取出後傳入。

老師「3-3-3 原則」：
  C1: 成立 > 3 年（以最早 NAV 日期推算，老標的歷經牛熊考驗）
  C2: 過去 3 年平均年化報酬率 > 7%（定存替代品，含息總報酬）
  C3: 晨星評級 3 顆星以上 / 同儕排名前 1/3（中前段班，有上升潛力）

⚠️ 2026-10-23 客戶裁示 3A（有意識的政策變更，不是漏刪；決策者：客戶）：
  - 3-3-3 **只保留一個判斷 SSOT**：`services.health.dividend.check_333_principle`
    （成立 ≥ 3 年、3 年年化 > 7%），報酬口徑與 1Y 一致 = 配息還原淨值法
    `metrics.ret_3y_ann_tr`（輸入推導 `derive_years_for_333` / `derive_ann_3y_for_333`）。
  - 上列 C3「晨星 / 同儕前 1/3」**不屬正式規格**：不新增同儕資料來源、不參與任何判定。
    上面三行保留為老師原話的紀錄，不是本模組的現行規格。`batch_333_funds` 的 ③ 欄
    依客戶 UI/Layout Decision Gate（`DEC-2026-10-23-04`）**保留欄位**、欄名加註「參考，
    不計入 3-3-3 判定」，內容不判定（見 `COL_333_PEER_RANK` 註）。
  - `check_333_fund` **停止作為判斷 SSOT**（production 0 caller；本體保留、不實體刪除，
    待 BL-0422 / BL-0292 legacy deletion gate 處置），`batch_333_funds` 不得再呼叫它。
  舊設計的理由仍然成立（三條件是老師原話）；被權衡掉的是「本模組自己再算一套」——
  它用純淨值（`ret_3y_ann` / NAV 時間切法）判 C2、與健診表 / Tab2 的 verdict 不同源，
  同一檔在不同分頁會得到不同燈號（§2.1 SSOT）。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    pass


def fund_inception_years(inception_date, series=None) -> "float | None":
    """v19.308 SSOT — 基金「成立至今」年數（ 3-3-3 ① / 健診 / 戰情室共用）。

    優先用 MoneyDJ 頁面現成的「成立日期」（inception_date，ISO 或 YYYY/MM/DD）——
    這是 user 要的「抓 MoneyDJ 已算好的」，不需本地長 NAV 歷史。缺成立日才以 NAV
    序列最早日推算；序列在 Streamlit Cloud 上可能因長歷史源被擋而過短
    （< 90 筆且推算 < 0.5 年 → 不可信 → None，§1 Fail Loud 不硬報 0.1 年）。

    回傳 float 年數，或 None（無成立日且序列不足以可信推算）。
    """
    import datetime as _dt
    # 1) MoneyDJ 現成成立日優先（免依賴本地長歷史）
    if inception_date:
        try:
            _inc = _dt.date.fromisoformat(str(inception_date)[:10])
            return (_dt.date.today() - _inc).days / 365.25
        except Exception:
            pass  # 成立日格式異常 → 落到序列 fallback
    # 2) fallback：NAV 序列最早日
    if series is None:
        return None
    try:
        s = series.dropna().sort_index() if hasattr(series, "dropna") else series
        if len(s) == 0:
            return None
        first = pd.Timestamp(s.index[0])
        if first.tzinfo is not None:
            first = first.tz_localize(None)
        _today = pd.Timestamp.now('UTC').tz_localize(None).normalize()
        years = (_today - first).days / 365.25
        if len(s) < 90 and years < 0.5:
            return None  # 序列太短，無法可信估算成立日（Cloud 長歷史被擋時常見）
        return years
    except Exception:
        return None


def check_333_fund(
    nav_series: "pd.Series | None",
    metrics: "dict | None" = None,
    peer_series_map: "dict[str, pd.Series] | None" = None,
    *,
    min_years: float = 3.0,
    target_annualized: float = 0.07,
    peer_top_pct: float = 1 / 3,
) -> dict:
    """ 3-3-3 原則評估（基金版）。

    ⛔ **RETIRED — 2026-10-23 客戶裁示 3A：停止作為 3-3-3 判斷 SSOT。**
    production 0 caller（`batch_333_funds` / Tab2 `_render_333_fund_expander` 已改走
    `services.health.dividend.check_333_principle` + `derive_years_for_333` /
    `derive_ann_3y_for_333`；僅 `scripts/diagnose_ret_3y_fallback.py` 的離線診斷仍 import）。
    本體**保留、不實體刪除**，待 BL-0422 / BL-0292 legacy deletion gate 處置；
    **不得**再被接回任何燈號 / 篩選判定。
    退役理由：C2 用純淨值（`ret_3y_ann` / NAV 時間切法）判「> 7%」，與 SSOT 的
    配息還原淨值法口徑不同；C3 同儕排名不屬正式規格。

    Parameters
    ----------
    nav_series       : pd.Series  NAV 序列，index=DatetimeIndex（升序），values=float
    metrics          : dict       fund_service.calc_metrics 回傳的 metrics dict
                                  （用 ret_3y_ann 作 C2 最優先來源；單位為 %）
    peer_series_map  : dict       {fund_code → pd.Series}，用來計算同儕排名（C3）
    min_years        : float      C1/C2 年限（預設 3.0）
    target_annualized: float      C2 目標年化報酬（預設 0.07 = 7%，與 metrics % 轉換）
    peer_top_pct     : float      C3 通過門檻（預設 1/3）

    Returns
    -------
    dict 含：
        c1_age_years     : float | None   成立年數（以最早 NAV 日推算）
        c1_pass          : bool  | None
        c2_return_3y     : float | None   3 年年化報酬率（小數，非 %）
        c2_source        : str            "metrics"（MoneyDJ）or "nav_series"（本地計算）
        c2_pass          : bool  | None
        c3_peer_rank_pct : float | None   排名百分位（0=最好 ~ 1=最差）
        c3_pass          : bool  | None
        overall_pass     : bool  | None   三項全過；有任一明確 Fail → False
        criteria_count   : int            可計算項目數（最多 3）
    """
    result: dict = {
        'c1_age_years': None, 'c1_pass': None,
        'c2_return_3y': None, 'c2_source': '', 'c2_pass': None,
        'c3_peer_rank_pct': None, 'c3_pass': None,
        'overall_pass': None,
        'criteria_count': 0,
    }

    if nav_series is None or (hasattr(nav_series, 'empty') and nav_series.empty):
        return result

    # 統一 Series
    if isinstance(nav_series, pd.DataFrame):
        nav_series = nav_series.squeeze()
    s = nav_series.dropna().sort_index()
    if len(s) < 10:
        return result

    # 確保 tz-naive
    if hasattr(s.index, 'tz') and s.index.tz is not None:
        s.index = s.index.tz_localize(None)

    today = pd.Timestamp.now('UTC').tz_localize(None).normalize()

    # ── C1：成立年數（v19.308：優先 MoneyDJ 現成成立日，缺則 NAV 最早日推算）──
    _inception = (metrics or {}).get("inception_date")
    age_years = fund_inception_years(_inception, s)
    if age_years is not None:
        c1_pass = age_years >= min_years
        result.update({'c1_age_years': round(age_years, 2), 'c1_pass': c1_pass})
        result['criteria_count'] += 1
    else:
        # 無成立日且序列過短 → 資料不足（c1_age_years/c1_pass 保持 None，
        # 顯示「—」/❓ 而非誤導的「0.1 年 ❌」）
        result['c1_age_years'] = None

    # ── C2：3 年年化報酬率 ──────────────────────────────────────────────────
    _m = metrics or {}

    # ⚠️ 2026-08-11 更正：這裡原本的註解寫「優先用 MoneyDJ 的 ret_3y_ann
    #    （含息總報酬，**已由 MoneyDJ 算好**）」—— **兩點都不對**，查證如下：
    #    (1) `ret_3y_ann` 是 `services/fund_service.py` 從 **NAV 序列自算**的
    #        （`_ret(3 * TRADING_DAYS_PER_YEAR)` → 需要 756 個資料點），不是 MoneyDJ 給的；
    #    (2) 它是**純 NAV**，不含息 —— 而 3-3-3 的 C2 定義要的正是含息。
    #    真正的含息 3Y 來自 MoneyDJ wb01（`perf["3Y"]`），只有**境外**基金頁有。
    #    境內基金（ACCP138 等）沒有 wb01 → C2 無來源，已於 2026-08-11 拍板凍結，
    #    見 `repositories/fund/nav_metrics.py::_fetch_domestic_perf` docstring。
    #    下方 `c2_source` 標的 'metrics(MoneyDJ)' 字串同樣是舊誤解的殘留，
    #    但它已被健診表「②來源」欄與 Tab② 消費，改字串會動到畫面 → 另案處理。
    _ret_3y_pct = _m.get("ret_3y_ann")
    if _ret_3y_pct is not None:
        try:
            ann_ret = float(_ret_3y_pct) / 100.0
            c2_pass = ann_ret >= target_annualized
            result.update({
                'c2_return_3y': round(ann_ret, 4),
                'c2_source': 'metrics(MoneyDJ)',
                'c2_pass': c2_pass,
            })
            result['criteria_count'] += 1
        except (TypeError, ValueError):
            pass

    # 若 metrics 沒有 ret_3y_ann，從 NAV 序列自算（不含息，保守估計）
    if result['c2_return_3y'] is None:
        three_yr_ago = today - pd.Timedelta(days=int(min_years * 365.25))
        try:
            idx_loc = min(s.index.searchsorted(three_yr_ago, side='left'), len(s) - 1)
            start_ts = pd.Timestamp(s.index[idx_loc])
            if start_ts.tzinfo is not None:
                start_ts = start_ts.tz_localize(None)
            actual_years = (today - start_ts).days / 365.25
            sp = float(s.iloc[idx_loc])
            ep = float(s.iloc[-1])
            if actual_years >= 2.5 and sp > 0 and ep > 0:
                ann_ret = (ep / sp) ** (1.0 / actual_years) - 1.0
                c2_pass = ann_ret >= target_annualized
                result.update({
                    'c2_return_3y': round(ann_ret, 4),
                    'c2_source': 'nav_series（NAV，不含息）',
                    'c2_pass': c2_pass,
                })
                result['criteria_count'] += 1
        except Exception:
            pass

    # ── C3：同儕排名 ────────────────────────────────────────────────────────
    if peer_series_map:
        try:
            _ref_ago = today - pd.Timedelta(days=int(min_years * 365.25))
            peer_ann_rets: dict[str, float] = {}
            for code, ps in peer_series_map.items():
                if ps is None or len(ps) < 50:
                    continue
                ps2 = ps.dropna().sort_index()
                if hasattr(ps2.index, 'tz') and ps2.index.tz is not None:
                    ps2.index = ps2.index.tz_localize(None)
                li = min(ps2.index.searchsorted(_ref_ago, side='left'), len(ps2) - 1)
                sp_p = float(ps2.iloc[li])
                ep_p = float(ps2.iloc[-1])
                st_ts = pd.Timestamp(ps2.index[li])
                if st_ts.tzinfo is not None:
                    st_ts = st_ts.tz_localize(None)
                ay = (today - st_ts).days / 365.25
                if ay >= 2.5 and sp_p > 0 and ep_p > 0:
                    peer_ann_rets[code] = (ep_p / sp_p) ** (1.0 / ay) - 1.0

            if peer_ann_rets:
                # 用 NAV 報酬也加入自己（若有 C2 from nav_series）
                _my_ret = result.get('c2_return_3y')
                if _my_ret is not None:
                    _me_key = '__self__'
                    peer_ann_rets[_me_key] = _my_ret
                    sorted_rets = sorted(peer_ann_rets.values(), reverse=True)
                    rank_0 = sorted_rets.index(peer_ann_rets[_me_key])
                    rank_pct = rank_0 / len(sorted_rets)
                    c3_pass = rank_pct <= peer_top_pct
                    result.update({'c3_peer_rank_pct': round(rank_pct, 3), 'c3_pass': c3_pass})
                    result['criteria_count'] += 1
        except Exception:
            pass

    # ── Overall ─────────────────────────────────────────────────────────────
    passes = [result['c1_pass'], result['c2_pass'], result['c3_pass']]
    if all(p is not None for p in passes):
        result['overall_pass'] = all(passes)
    elif any(p is False for p in passes):
        result['overall_pass'] = False

    return result


def _nav_first_iso(series) -> "str | None":
    """NAV 序列最早一筆日期（ISO 字串）；無序列 / 空序列 / 解析失敗 → None（不猜）。"""
    if series is None:
        return None
    try:
        s = series.dropna().sort_index() if hasattr(series, "dropna") else series
        if len(s) == 0:
            return None
        return str(pd.Timestamp(s.index[0]).date())
    except Exception:
        return None


def evaluate_333_for_fund(f: dict) -> dict:
    """單檔 3-3-3（2026-10-23 客戶裁示 3A）—— **唯一** SSOT 判定的單檔入口，本模組不自己算門檻。

    `batch_333_funds`（Tab3 批次表）與 `ui/components/mk_dashboard`（Tab3 戰情室「3-3-3 篩選器」）
    共用本函式，保證同一檔在兩處得到同一個結果（§2.1 SSOT）。

    輸入：Tab3 `portfolio_funds` 的單檔 dict（或其子集）：code / series / metrics，
    選填 dividends / moneydj_raw / inception_date / perf_source（皆為既有欄位，不新增資料來源）。

    步驟：
      ① `derive_years_for_333`：成立日 meta 優先（metrics → 頂層 → moneydj_raw，與 fund_row /
         report 同順序），缺則 NAV 首日 proxy（proxy < 3 年 → None，不反證）；
      ② `derive_ann_3y_for_333`：配息還原淨值法 `metrics.ret_3y_ann_tr` ＋ 配息閘門；
      判定 `check_333_principle(years, ann)` → passed 三態（True / False / None=⬜）。

    Returns
    -------
    {"years": float|None, "ann_pct": float|None, "basis": str,
     "years_ok": bool|None, "return_ok": bool|None, "passed": bool|None, "message": str}
    """
    from services.health.dividend import (
        check_333_principle,
        derive_ann_3y_for_333,
        derive_years_for_333,
    )

    f = f if isinstance(f, dict) else {}
    series  = f.get('series')
    metrics = f.get('metrics') or {}
    _mj     = f.get('moneydj_raw') or {}
    # 成立日來源順序與 fund_row / Tab2 一致：metrics（fetcher 已複製）→ 頂層 → moneydj_raw
    _inception = (metrics.get('inception_date') or f.get('inception_date')
                  or _mj.get('inception_date') or '')
    years, _ = derive_years_for_333(_inception, _nav_first_iso(series))
    # fd 形狀對齊 SSOT（nested）；dividends / moneydj_div_yield 供配息閘門辨識配息型
    _fd = {
        'moneydj_raw': _mj,
        'metrics': metrics,
        'series': series,
        'dividends': f.get('dividends') if f.get('dividends') is not None else _mj.get('dividends'),
        'perf_source': f.get('perf_source') or _mj.get('perf_source'),
    }
    ann, basis = derive_ann_3y_for_333(_fd, metrics)
    r = check_333_principle(years, ann)
    return {"years": years, "ann_pct": ann, "basis": basis,
            "years_ok": r.get("years_ok"), "return_ok": r.get("return_ok"),
            "passed": r.get("passed"), "message": r.get("message", "")}


# ③ 欄（同儕排名）—— 2026-10-23 客戶 UI/Layout Decision Gate（`DEC-2026-10-23-04`）：
# 欄位**不得移除**（欄位增減屬版面變更，留到新版 UI/UX Blueprint），但它**不屬**正式 3-3-3
# （裁示 3A：正式規則只有 ① 成立 ≥ 3 年、② 3 年年化 > 7%），故只改欄名加註、內容不判定。
# 欄名住這裡（L2 產出欄名的同一處），Tab3 caption / 測試一律 import，不各自手抄。
COL_333_PEER_RANK = "③同儕排名（參考，不計入 3-3-3 判定）"
COL_333_PEER_PASS = "③通過（參考，不計入 3-3-3 判定）"


def batch_333_funds(fund_list: list[dict]) -> "pd.DataFrame":
    """批次評估多檔基金的 3-3-3 通過狀況（用於 Tab3 組合）—— 走唯一 SSOT。

    2026-10-23 客戶裁示 3A：每檔一律以 `services.health.dividend` 的
    `derive_years_for_333`（成立日 meta 優先、缺則 NAV 首日 proxy 下界）＋
    `derive_ann_3y_for_333`（配息還原淨值法 `metrics.ret_3y_ann_tr`，與 1Y 同口徑）＋
    `check_333_principle`（成立 ≥ 3 年、3 年年化 > 7%，三態）算出結果；
    **不再**呼叫 `check_333_fund`。
    舊簽名的 `min_years` / `target_annualized` 旋鈕一併移除：門檻只住在 SSOT 常數
    （`THREE_THREE_THREE_MIN_YEARS` / `THREE_THREE_THREE_MIN_ANN_RETURN_PCT`），
    留一個會被靜默忽略的參數等於留一個假開關（全 repo 實測無呼叫端傳這兩個 kwargs）。

    Parameters
    ----------
    fund_list : list of dict，每個 dict 需含：
                  code (str), name (str), series (pd.Series), metrics (dict)；
                選填（配息閘門用，缺 → 無法證明是配息基金 → 不擋）：
                  dividends (list), moneydj_raw (dict), inception_date (str)

    Returns
    -------
    pd.DataFrame  欄位（**欄數與欄序與 3A 之前相同**，客戶 UI/Layout Gate `DEC-2026-10-23-04`）：
      代碼 / 名稱 / ①成立年 / ①通過 / ②3年年化 / ②通過 /
      `COL_333_PEER_RANK` / `COL_333_PEER_PASS` / 整體
      - ①通過 / ②通過 / 整體：`check_333_principle` 的 years_ok / return_ok / passed
        → ✅ 通過 / ❌ 未通過（有明確反證）/ ⬜ 資料不足（**不是** ❌）
      - ②3年年化：有值 → 「x.x%」（含息，配息還原淨值法）；缺 → `derive_ann_3y_for_333`
        的 basis 字串原樣（⬜ 配息資料未備 / ⬜ 歷史不足 3 年 / ⬜ 3 年含息年化不可得 / —）
      - ③ 兩欄：**不參與任何判定**，不出現 ✅ / ❌。值維持 3A 之前的同一個來源 ——
        舊版取自 `check_333_fund(...)["c3_peer_rank_pct"]`，而本函式**從未**傳
        `peer_series_map`，該值恆為 None、畫面恆為「—」（2026-10-23 以 main 版實跑確認）。
        不新增同儕資料來源（裁示 3A），故兩欄一律「—」。

    v19.306：以 code 去重（一檔一列，保留首次出現順序）。3-3-3 評估的是基金
    內在屬性（成立年 / 3 年年化），同一基金若跨多張保單在
    portfolio_funds 重複，會產生完全相同的重複列 + 灌水「共 N 檔」統計。此處
    收斂為 SSOT 一檔一列。注意：僅基金內在分析去重；組合層投入金額 / 配置需保留
    跨保單重複，故不在 portfolio_funds 源頭去重。
    """
    def _icon(b) -> str:
        if b is True:   return '✅'
        if b is False:  return '❌'
        return '⬜'

    rows = []
    _seen_codes: set = set()  # v19.306 SSOT 去重（見 docstring）：同 code 只評一次
    for f in fund_list:
        code    = f.get('code', '')
        if code and code in _seen_codes:
            continue  # 同基金已評過，跳過重複列
        if code:
            _seen_codes.add(code)
        name    = f.get('name', '') or ''
        # 單檔判定一律走 `evaluate_333_for_fund`（= derive_years / derive_ann_3y / check_333_principle）
        r = evaluate_333_for_fund(f)
        years, ann, basis = r["years"], r["ann_pct"], r["basis"]

        rows.append({
            '代碼':     code,
            '名稱':     name[:18],
            '①成立年': f'{years:.1f}年' if years is not None else '—',
            '①通過':   _icon(r.get('years_ok')),
            # 缺值時印 basis 原因（⬜ 配息資料未備 / ⬜ 歷史不足 3 年 …），不以純淨值或官方值頂替
            '②3年年化': f'{ann:.1f}%' if ann is not None else basis,
            '②通過':   _icon(r.get('return_ok')),
            # ③ 不參與判定、不出 ✅/❌；來源同 3A 之前（恆無值 → 「—」），見 docstring
            COL_333_PEER_RANK: '—',
            COL_333_PEER_PASS: '—',
            '整體':     _icon(r.get('passed')),
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ════════════════════════════════════════════════════════════════════════
# 低基期進場點篩選（「🎯 選基金」清單）
# ════════════════════════════════════════════════════════════════════════
# 2026-08-07 user 拍板：**低基期全站統一用 HWM σ rank**（健診大表「基期」欄那把尺）。
#
# 原本這裡是另一套演算法（`高點 − N×NAV 標準差`，深度取**正數**、倍數由使用者選
# 1 或 2σ、回看期可選 1/2/3 年），與大表的 σ rank（**負數**、報酬率標準差換算、
# 門檻固定 `ROTATION_BUY_SIGMA`）互相獨立 —— 同一檔可能在這裡標「✅ 低基期」、
# 在大表標「⚪ 中性」，使用者照這裡買進，回頭卻看到系統自己說不是低基期。
#
# 統一後的口徑（§4.1 σ sign convention：**一律負數，愈負愈低基期**）：
#   σ rank = (現價 − 期間 HWM) / σ_abs      ← services/fund_position.compute_fund_position
#            （2026-10-23 裁示 2C：配息還原序列、fail closed；數學核心仍是
#             services/precision_service.calc_hwm_sigma_levels）
#   低基期 ⇔ σ rank ≤ ROTATION_BUY_SIGMA    ← services/rotation.classify_base
# 兩邊呼叫同一組函式 + 同一組 shared/signal_thresholds 常數，**不可能再分歧**。
# ⚠️ 「低基期／進場點」是 legacy 行動語意（規則、門檻、用字未改），待 BL-0428 重新裁示。
LOW_BASE_LOOKBACK_DEFAULT = 252   # 回看窗（交易日，1Y ≈ 252，非 365 日曆日）
# ⚠️ 必須等於 `calc_hwm_sigma_levels` 的 lookback 預設值 —— 大表走預設、本模組顯式
# 傳入，兩者不同就會讓同一檔在兩處算出不同的 σ rank（σ_abs 隨 √n 縮放）。
# 漂移由 tests/test_fund_screener_low_base.py 的 inspect 漂移鎖守住。
LOW_BASE_MIN_POINTS = 60          # 可信度門檻：低於此樣本數 → reliable=False

# 基期狀態 → 給 UI 的說明字串（label 本身由 L3 決定，這裡只給中性描述）
_BASE_NOTE = {
    "low": "低基期（σ rank ≤ 買點門檻）",
    "mid": "中性（介於買賣門檻之間）",
    "high": "高基期（貼近期間高點）",
    "unknown": "資料不足，無法定位階",
}


def compute_base_state(
    fund: dict,
    *,
    lookback: int = LOW_BASE_LOOKBACK_DEFAULT,
    min_points: int = LOW_BASE_MIN_POINTS,
    buy_sigma: "float | None" = None,
    sell_sigma: "float | None" = None,
) -> dict:
    """基期定位（純計算）—— **與健診大表「基期」欄同一把尺**。

    ⚠️ 2026-10-23 裁示 2C ＋ Stop Gate「選項 1」（BL-0426）：σ rank 一律取自唯一 SSOT
    `services.fund_position.compute_fund_position`（**配息還原序列**、fail closed）。
    本函式的低基期 / 高基期規則、門檻、`buy_threshold_nav` 語意與用字**一字未改**
    —— legacy 行動語意，待 BL-0428 重新裁示。

    輸入：**一律 fund dict**（`series` / `dividends` / `moneydj_raw`（category、moneydj_div_yield）；
    與 `compute_fund_position` 同一套讀法）。~~也接受裸 NAV 序列~~（2026-10-23 稽核必修 A 移除：
    裸序列等於沒有任何配息資訊，配息基金會被當非配息基金拿原始 NAV 去判 —— 那是一條
    繞過 2C 的 raw 入口）。傳非 dict → `TypeError`（§1 Fail Loud）。

    數學式（σ sign convention 見 §4.1：**負值愈深愈低基期**）:
        σ rank   = compute_fund_position(...)["sigma_rank"]   ≤ 0
        低基期  ⇔ σ rank ≤ buy_sigma（預設 ROTATION_BUY_SIGMA = −1.5）
        高基期  ⇔ σ rank ≥ sell_sigma（預設 ROTATION_SELL_SIGMA = −0.5）
    分類走 `services.rotation.classify_base` + `shared.signal_thresholds` 常數（§3.3）。

    `buy_threshold_nav`（σ rank 剛好等於 buy_sigma 的 NAV 價位）：還原基準的 HWM / σ_abs
    已由 SSOT 以「最新原始淨值」為錨換回原幣淨值單位（`current_nav_tr == current_nav`），
    所以 `hwm + buy_sigma × σ_abs` 仍是**可以和原始現價直接比較**的價位，語意不變。

    §1 Fail Closed 邊界（**停售 / 清算 / 無法判定的基金絕不可被推薦**）:
      - SSOT 回 unavailable（歷史不足 / 報酬不足 / σ≈0 / 配息資料未備 / 貨幣市場型 /
        還原失敗）→ `base="unknown"` / `is_low_base=None` / `sigma_rank=None`，
        ⬜ 白話原因原字轉載到 `note`。`screen_funds(only_low_base=True)` 一定濾掉它。
      - 窗口樣本數 < min_points → reliable=False（仍給值但標「可信度低」）

    Returns
    -------
    dict:
        sigma_rank        : float | None  現價在 HWM 下方第幾個 σ（**負數**；配息還原基準）
        base              : "low" / "mid" / "high" / "unknown"
        is_low_base       : bool | None   (None = 無法定位階)
        hwm / current / dist_to_hwm_pct : float | None
                            （hwm = 還原基準、以最新原始淨值為錨；current = 原始最新淨值）
        buy_threshold_nav : float | None  σ rank 剛好等於 buy_sigma 的 NAV 價位
        hwm_label         : str           SSOT 的中性位置標籤（或 ⬜ 原因）
        n_points          : int           實際採用的樣本數
        reliable          : bool          n_points ≥ min_points
        note              : str           狀態說明（供 UI 顯示）
        buy_sigma / sell_sigma : float    本次實際採用的門檻（揭露，不讓 UI 自己猜）
    """
    from shared.signal_thresholds import ROTATION_BUY_SIGMA, ROTATION_SELL_SIGMA
    _buy = float(ROTATION_BUY_SIGMA if buy_sigma is None else buy_sigma)
    _sell = float(ROTATION_SELL_SIGMA if sell_sigma is None else sell_sigma)

    out: dict = {
        "sigma_rank": None, "base": "unknown", "is_low_base": None,
        "hwm": None, "current": None, "dist_to_hwm_pct": None,
        "buy_threshold_nav": None, "hwm_label": "—",
        "n_points": 0, "reliable": False, "note": "",
        "buy_sigma": _buy, "sell_sigma": _sell,
    }

    if not isinstance(fund, dict):
        raise TypeError(
            f"compute_base_state 需要 fund dict(series + dividends + moneydj_raw),"
            f"收到 {type(fund).__name__} —— 裸 NAV 序列沒有配息資訊,不得繞過 2C SSOT")
    nav_series = fund.get("series")
    if nav_series is None:
        nav_series = (fund.get("moneydj_raw") or {}).get("series") \
            if isinstance(fund.get("moneydj_raw"), dict) else None

    if nav_series is None:
        out["note"] = "無 NAV"
        return out
    s = nav_series
    if isinstance(s, pd.DataFrame):
        s = s.squeeze()
    if not hasattr(s, "dropna"):
        out["note"] = "NAV 型別非序列"
        return out
    s = s.dropna().sort_index()
    # tz-naive（與檔內其他函式一致）
    if hasattr(s.index, "tz") and s.index.tz is not None:
        s.index = s.index.tz_localize(None)
    if len(s) == 0:
        out["note"] = "NAV 全空"
        return out

    s = s.tail(int(lookback))
    n = len(s)
    out["n_points"] = n
    out["reliable"] = n >= int(min_points)

    from services.fund_position import compute_fund_position
    from services.rotation import classify_base

    _r = compute_fund_position(fund, lookback=int(lookback))
    if _r.get("status") != "ok":
        # 停售 / 剛成立 / NAV 不動 / 配息資料未備 / 貨幣市場型 → 誠實不判定（§1）
        out["hwm_label"] = _r.get("label") or "—"
        out["note"] = str(_r.get("label") or _r.get("error") or "")
        return out

    _hwm = _r.get("hwm_tr")
    _sigma_abs = _r.get("sigma_abs")
    out["sigma_rank"] = _r.get("sigma_rank")
    out["hwm"] = _hwm
    out["current"] = _r.get("current_nav")
    out["dist_to_hwm_pct"] = _r.get("dist_to_hwm_pct")
    out["hwm_label"] = _r.get("label") or "—"
    if _hwm is not None and _sigma_abs:
        # buy_sigma 是**負數**：用加法保持符號一致，不寫 `hwm − |buy|×σ`，
        # 否則有人把常數改成正數時整條線會靜默反向（§4.1）。
        out["buy_threshold_nav"] = round(_hwm + _buy * _sigma_abs, 4)

    _base = classify_base(out["sigma_rank"], _sell, _buy)
    out["base"] = _base
    out["is_low_base"] = None if _base == "unknown" else (_base == "low")
    if not out["reliable"]:
        out["note"] = f"樣本僅 {n} 筆（<{min_points}），可信度低"
    else:
        out["note"] = _BASE_NOTE.get(_base, "")
    return out


def screen_funds(
    items: list[dict],
    *,
    lookback: int = LOW_BASE_LOOKBACK_DEFAULT,
    min_points: int = LOW_BASE_MIN_POINTS,
    only_low_base: bool = True,
    only_no_eat: bool = True,
    currencies: "set[str] | None" = None,
    categories: "set[str] | None" = None,
    buy_sigma: "float | None" = None,
    sell_sigma: "float | None" = None,
) -> list[dict]:
    """「選基金清單」：對已載入基金套低基期 + 不吃本金 + 幣別/類別濾鏡（純函式）。

    Parameters
    ----------
    items : list of dict，每檔需含（缺欄位以 None/"" 容錯）:
        code (str), name (str), series (pd.Series NAV),
        currency (str), category (str),
        eats_principal (bool | None)   # True=吃本金 / False=不吃 / None=未知
        dividends (list) / moneydj_raw (dict)   # 2C:σ 位置 SSOT 配息還原與配息閘門用
    lookback / min_points / buy_sigma / sell_sigma : 傳入 compute_base_state
    only_low_base : True → 僅保留 `base == "low"`（**無法定位階者一併排除** ——
                    停售 / NAV 不動的基金 σ rank 為 None，不得混進進場候選，§1）
    only_no_eat   : True → 僅保留 eats_principal 明確為 False（不吃本金）
    currencies    : None=全部；否則僅保留 currency ∈ 此集合
    categories    : None=全部；否則僅保留 category ∈ 此集合

    Returns
    -------
    list[dict]（依 **σ rank 由負至正**排序 = 跌最深的在最前，無法定位階者排最後）：
    每列含 code / name / currency / category / eats_principal +
    compute_base_state 全欄位。**去重同 code**（一檔一列）。
    """
    rows: list[dict] = []
    seen: set = set()
    for it in items:
        code = str(it.get("code", "") or "").strip()
        if code and code in seen:
            continue
        if code:
            seen.add(code)

        ccy = str(it.get("currency", "") or "").strip()
        cat = str(it.get("category", "") or "").strip()
        eats = it.get("eats_principal", None)

        # 濾鏡（基期以外的先擋，省 compute）
        if currencies is not None and ccy not in currencies:
            continue
        if categories is not None and cat not in categories:
            continue
        if only_no_eat and eats is not False:  # 僅保留「明確不吃本金」
            continue

        # 2C:整個 item 原樣傳入(series + dividends + moneydj_raw)→ SSOT 配息還原
        lb = compute_base_state(
            it, lookback=lookback, min_points=min_points,
            buy_sigma=buy_sigma, sell_sigma=sell_sigma,
        )
        if only_low_base and lb.get("base") != "low":
            continue

        rows.append({
            "code": code, "name": str(it.get("name", "") or ""),
            "currency": ccy, "category": cat, "eats_principal": eats,
            **lb,
        })

    # σ rank 遞增（愈負 = 跌愈深 = 排愈前）；None（無法定位階）一律排最後
    rows.sort(key=lambda r: (r.get("sigma_rank") is None,
                             r.get("sigma_rank") if r.get("sigma_rank") is not None else 0.0))
    return rows
