"""ui/tab_batch_analysis.py — 批次基金分析分頁(上傳 400 檔 → 逐檔跑 → 下載 CSV)。

L3 delivery surface。單一職責:收一份代號清單(上傳 CSV / 貼上)→ 對每檔呼
L2 `services.fund_batch.analyze_fund_row` → 進度條逐檔累積到 session_state
(可中斷續跑)→ 成功/失敗摘要 → 下載 CSV(utf-8-sig,Excel 直開)。

架構(§8.2):L3 → L2 `services.fund_batch`(→ `services.moneydj_fetcher` → L1)。
不直呼 L1、無上行 import。

§1 誠實:400 檔必有失敗(停售/403/無 NAV),失敗檔完整留在表裡帶 `status`+`note`,
數值留白(絕不填 0),下載檔可追溯。AI 跨檔評論 / 持股明細**刻意不在批次表**
(小 N by design + §EX-AI-1 AI 回散文非資料)—— 篩出想深看的一小撮後,到
「組合健診」分頁做 AI 比較。
"""
from __future__ import annotations

import datetime as _dt
import re

import pandas as pd
import streamlit as st

from services.fund_batch import ROW_COLUMNS, analyze_fund_row

# session_state 命名空間
_K_CODES = "batch_codes"      # list[str] 目標代號(依上傳順序)
_K_ROWS = "batch_rows"        # dict[str, row] 已完成結果(續跑用)
_K_RUN_AT = "batch_run_at"    # str 本次執行時間(台北)

# 解析用:代號寬鬆樣式 + 常見表頭字(過濾掉,避免當成基金碼硬抓)
_CODE_RE = re.compile(r"^[A-Z0-9]{3,20}$")
_HEADER_TOKENS = {"CODE", "SYMBOL", "TICKER", "代號", "基金代號", "基金代碼", "標的", "標的代號"}
_TW_TZ = _dt.timezone(_dt.timedelta(hours=8))

# 失敗類(可「重試失敗檔」的 status)
_FAIL_STATUSES = {"fetch_fail", "no_nav"}


def _parse_codes(raw: str) -> list[str]:
    """把一坨文字(貼上或 CSV 內容)解析成去重、大寫的代號清單。

    規則:逗號/分號/tab/換行皆為分隔;每行取第一個 token(容忍「ACCP138,美元基金」);
    只留符合 `[A-Z0-9]{3,20}` 的 token;過濾常見表頭;保留首次出現順序去重。
    """
    if not raw:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for line in raw.replace("\r", "\n").split("\n"):
        line = line.strip()
        if not line:
            continue
        # 每行取第一欄(CSV/多欄容忍)
        token = re.split(r"[,\t;]", line, maxsplit=1)[0].strip().upper()
        if not token or token in _HEADER_TOKENS:
            continue
        if not _CODE_RE.match(token):
            continue
        if token not in seen:
            seen.add(token)
            out.append(token)
    return out


def _run_batch(codes: list[str], retry_failed: bool) -> None:
    """逐檔跑(進度條)。已完成的跳過(續跑);retry_failed=True 時失敗檔重抓。

    每完成一檔立刻寫進 session_state → 中斷後再按可續跑。
    """
    rows: dict = st.session_state.setdefault(_K_ROWS, {})
    st.session_state[_K_RUN_AT] = _dt.datetime.now(_TW_TZ).strftime("%Y-%m-%d %H:%M")

    # 決定本輪要處理哪些(未做的 + 選擇性重試失敗的)
    todo = [
        c for c in codes
        if c not in rows or (retry_failed and rows[c].get("status") in _FAIL_STATUSES)
    ]
    if not todo:
        st.info("沒有待處理的代號(全部已完成)。如要全部重來,請按「🗑️ 清除重來」。")
        return

    bar = st.progress(0.0)
    live = st.empty()
    total = len(todo)
    for i, code in enumerate(todo, start=1):
        live.markdown(f"⏳ 處理中 **{i}/{total}**:`{code}` …")
        rows[code] = analyze_fund_row(code)   # L2:失敗也回一列,不外拋
        bar.progress(i / total)
    bar.empty()
    live.markdown(f"✅ 本輪完成 **{total}** 檔。")


def _build_df(codes: list[str], rows: dict) -> pd.DataFrame:
    """依上傳順序組 DataFrame,欄位固定 ROW_COLUMNS。只納入已完成的檔。"""
    data = [rows[c] for c in codes if c in rows]
    df = pd.DataFrame(data, columns=ROW_COLUMNS)
    return df


def render_batch_analysis_tab() -> None:
    st.markdown("## 📦 批次基金分析")
    st.caption(
        "上傳或貼上基金代號清單 → 逐檔跑報酬/風險/配息分析 → 下載 CSV。"
        "每檔要抓 NAV/配息/績效(T+1~T+3、含 fallback chain),**400 檔約 15~25 分鐘**;"
        "可中斷後再按「繼續」續跑(已完成的會快取跳過)。"
    )

    # ── 輸入:上傳 CSV/TXT 或貼上 ──────────────────────────────
    c1, c2 = st.columns(2)
    with c1:
        up = st.file_uploader("① 上傳清單(CSV / TXT,每行一檔或第一欄為代號)",
                              type=["csv", "txt"], key="batch_uploader")
    with c2:
        pasted = st.text_area("② 或直接貼上(每行一檔,逗號/換行皆可)",
                              height=150, key="batch_paste",
                              placeholder="ACCP138\nB07\n0050\n...")

    raw = ""
    if up is not None:
        try:
            raw = up.getvalue().decode("utf-8-sig", errors="replace")
        except Exception as e:  # noqa: BLE001 — 解碼失敗誠實告知,不吞
            st.error(f"檔案讀取失敗:{type(e).__name__}: {e}")
            raw = ""
    if pasted.strip():
        raw = (raw + "\n" + pasted) if raw else pasted

    codes = _parse_codes(raw)

    if not codes:
        st.info("👆 請上傳或貼上基金代號清單。範例代號:`ACCP138`(保單連結)、`0050`(境內)。")
        _render_existing_results()   # 若上次跑過,仍可看/下載
        return

    st.session_state[_K_CODES] = codes
    rows: dict = st.session_state.get(_K_ROWS, {})
    done = sum(1 for c in codes if c in rows)
    est_min = max(1, round(len(codes) * 4 / 60))   # 粗估 ~4s/檔
    st.markdown(
        f"**解析到 {len(codes)} 檔**(去重後)　·　已完成 {done} 檔　·　"
        f"預估首次全跑約 {est_min} 分鐘"
    )

    b1, b2, b3 = st.columns([2, 2, 1])
    with b1:
        go = st.button("▶️ 開始 / 繼續分析", type="primary", use_container_width=True,
                       key="batch_go")
    with b2:
        retry = st.button("🔁 重試失敗檔", use_container_width=True, key="batch_retry",
                          disabled=(done == 0))
    with b3:
        clear = st.button("🗑️ 清除重來", use_container_width=True, key="batch_clear")

    if clear:
        st.session_state.pop(_K_ROWS, None)
        st.session_state.pop(_K_RUN_AT, None)
        st.rerun()

    if go or retry:
        _run_batch(codes, retry_failed=bool(retry))

    _render_existing_results()


def _render_existing_results() -> None:
    """有結果就渲染摘要 + 表 + 下載鈕(§1:失敗檔誠實入表)。"""
    codes = st.session_state.get(_K_CODES, [])
    rows = st.session_state.get(_K_ROWS, {})
    if not codes or not rows:
        return

    df = _build_df(codes, rows)
    if df.empty:
        return

    # ── 摘要(§1:成功 / 部分 / 失敗 一目了然)────────────────
    n = len(df)
    n_ok = int((df["status"] == "ok").sum())
    n_partial = int((df["status"] == "partial").sum())
    n_nonav = int((df["status"] == "no_nav").sum())
    n_fail = int((df["status"] == "fetch_fail").sum())
    run_at = st.session_state.get(_K_RUN_AT, "—")

    st.divider()
    st.markdown(f"### 📊 分析結果　·　執行時間(台北):{run_at}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("✅ 成功", n_ok)
    m2.metric("🟡 部分(序列短/稀疏)", n_partial)
    m3.metric("⬜ 無 NAV(停售/403)", n_nonav)
    m4.metric("❌ 抓取失敗", n_fail)
    if n_fail or n_nonav:
        st.caption("失敗/無資料的檔仍完整列在表裡(status + note 標明原因、數值留白),"
                   "**不會靜默丟棄或填假值**(§1)。可按「🔁 重試失敗檔」重抓。")

    # ── 表格 ───────────────────────────────────────────────
    st.dataframe(df, use_container_width=True, height=420, hide_index=True)

    # ── 下載 CSV(utf-8-sig,Excel 直開中文正常)──────────────
    fname_ts = (run_at or "").replace("-", "").replace(":", "").replace(" ", "_") or "export"
    st.download_button(
        "⬇️ 下載分析結果 CSV",
        df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"fund_batch_{fname_ts}.csv",
        mime="text/csv",
        use_container_width=True,
        key="batch_download",
    )

    with st.expander("ℹ️ 欄位說明 / 這張表沒有什麼", expanded=False):
        st.markdown(
            "- **報酬欄 `*_pct`** 為百分比;`ret_*_pct` 為**純 NAV 報酬**,"
            "`ret_1y_total_pct` 為**含息**;`ret_3y/5y_ann_pct` 為年化。\n"
            "- **`vol_1y_pct`** = 年化標準差;**`max_drawdown_pct`** = 最大回撤;"
            "**`nav`** 為**原幣**淨值(見 `currency` 欄,未換算 TWD)。\n"
            "- **`div_yield_pct`** = 配息年化率(≠ 含息報酬);**`mgmt_fee`** = 經理費。\n"
            "- **`data_source`** = 命中的來源;**`is_sparse`** = 序列稀疏(年化值已誠實砍掉)。\n"
            "- ⚠️ **不含**:AI 跨檔評論、逐檔持股明細 —— 屬小 N 深看功能,"
            "請到「💊 組合健診」分頁對篩選出的一小撮基金做。"
        )
