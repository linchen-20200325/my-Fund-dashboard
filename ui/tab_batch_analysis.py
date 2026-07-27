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

from services.fund_batch import (
    COLUMN_LABELS_ZH,
    ROW_COLUMNS,
    STATUS_LABELS_ZH,
    analyze_fund_row,
)

# session_state 命名空間
_K_CODES = "batch_codes"      # list[str] 目標代號(依上傳順序)
_K_ROWS = "batch_rows"        # dict[str, row] 已完成結果(續跑用)
_K_RUN_AT = "batch_run_at"    # str 本次執行時間(台北)
_K_RUN_ID = "batch_run_id"    # str 目前清單的 checkpoint run_id(換清單即變 → 重置記憶體)
_K_DISK_OFF = "batch_disk_off"  # bool 磁碟續存失敗 → 降級只記憶體(只警告一次)

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


def _persist(run_id: str, codes: list[str], rows: dict) -> None:
    """磁碟續存;失敗 → 降級成只記憶體(警告一次,不中斷跑批)。§1:不靜默、不假裝。"""
    if st.session_state.get(_K_DISK_OFF):
        return
    from repositories import batch_checkpoint as bc
    try:
        bc.save(run_id, codes, rows)
    except Exception as e:  # noqa: BLE001 — 磁碟不可寫(如 Cloud 唯讀)→ 降級,不炸跑批
        st.session_state[_K_DISK_OFF] = True
        st.warning(f"⚠️ 磁碟續存失敗,本次改為只存記憶體(關分頁會消失):"
                   f"{type(e).__name__}: {str(e)[:80]}")


def _run_batch(codes: list[str], retry_failed: bool) -> None:
    """逐檔跑(進度條)。已完成的跳過(續跑);retry_failed=True 時失敗檔重抓。

    每完成一檔立刻寫進 session_state **+ 磁碟 checkpoint** → 關分頁 / 重啟後仍可續跑。
    """
    from repositories import batch_checkpoint as bc
    rows: dict = st.session_state.setdefault(_K_ROWS, {})
    st.session_state[_K_RUN_AT] = _dt.datetime.now(_TW_TZ).strftime("%Y-%m-%d %H:%M")
    run_id = bc.compute_run_id(codes)

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
        _persist(run_id, codes, rows)         # 每檔落地(續存後盾)
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
        "**每檔即時存磁碟** → 關分頁 / 伺服器重啟也不白費,重進上傳同一份清單自動接續。"
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
        _render_recent_checkpoints()  # 磁碟上的舊批次 → 可讀回看/下載
        _render_existing_results()    # 若本 session 已載入,仍可看/下載
        return

    # 換了清單(或剛開分頁 / 重啟後)→ 重置記憶體並嘗試從磁碟讀回該清單進度
    from repositories import batch_checkpoint as bc
    run_id = bc.compute_run_id(codes)
    if st.session_state.get(_K_RUN_ID) != run_id:
        st.session_state[_K_RUN_ID] = run_id
        st.session_state.pop(_K_DISK_OFF, None)
        ckpt = bc.load(run_id)
        if ckpt:
            st.session_state[_K_ROWS] = dict(ckpt.get("rows") or {})
            st.session_state[_K_RUN_AT] = ckpt.get("updated_at", "—")
            st.success(f"🔁 已從磁碟讀回上次進度:{len(st.session_state[_K_ROWS])} 檔"
                       f"(更新於 {ckpt.get('updated_at', '—')})")
        else:
            st.session_state[_K_ROWS] = {}

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
        bc.delete(run_id)                      # 連磁碟 checkpoint 一起清
        for _k in (_K_ROWS, _K_RUN_AT, _K_RUN_ID, _K_DISK_OFF):
            st.session_state.pop(_k, None)
        st.rerun()

    if go or retry:
        _run_batch(codes, retry_failed=bool(retry))

    _render_existing_results()


def _render_recent_checkpoints() -> None:
    """列磁碟上的舊批次存檔,讓使用者不必重上傳即可讀回看/下載(關分頁/重啟後救援)。"""
    from repositories import batch_checkpoint as bc
    recent = bc.list_recent()
    if not recent:
        return
    st.divider()
    st.markdown("### 💾 磁碟上的批次存檔(關分頁 / 重啟後可讀回)")
    st.caption("讀回後可直接下載;要**續跑**請重新上傳同一份清單(會自動接續)。")
    for r in recent:
        col1, col2 = st.columns([5, 1])
        col1.markdown(
            f"`{r['run_id']}`　·　**{r['n_done']}/{r['n_codes']}** 檔　·　"
            f"更新於 {r['updated_at'] or '—'}"
        )
        if col2.button("📂 讀回", key=f"batch_load_{r['run_id']}", use_container_width=True):
            ckpt = bc.load(r["run_id"])
            if ckpt:
                st.session_state[_K_ROWS] = dict(ckpt.get("rows") or {})
                st.session_state[_K_CODES] = (
                    ckpt.get("codes") or list((ckpt.get("rows") or {}).keys()))
                st.session_state[_K_RUN_AT] = ckpt.get("updated_at", "—")
                st.session_state[_K_RUN_ID] = r["run_id"]
                st.rerun()
            else:
                st.error("讀回失敗:存檔可能已損毀或被刪除。")


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

    # ── 中文標題 + 中文狀態(顯示 / 下載共用;內部 df 仍英文供邏輯)──────
    df_zh = df.copy()
    df_zh["status"] = df_zh["status"].map(lambda s: STATUS_LABELS_ZH.get(s, s))
    df_zh = df_zh.rename(columns=COLUMN_LABELS_ZH)

    # ── 表格 ───────────────────────────────────────────────
    st.dataframe(df_zh, use_container_width=True, height=420, hide_index=True)

    # ── 下載 CSV(utf-8-sig,Excel 直開中文標題正常)──────────────
    fname_ts = (run_at or "").replace("-", "").replace(":", "").replace(" ", "_") or "export"
    st.download_button(
        "⬇️ 下載分析結果 CSV",
        df_zh.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"fund_batch_{fname_ts}.csv",
        mime="text/csv",
        use_container_width=True,
        key="batch_download",
    )

    with st.expander("ℹ️ 欄位說明 / 這張表沒有什麼", expanded=False):
        st.markdown(
            "- **報酬欄**皆為百分比;「近1月/3月/6月/1年報酬%」為**純 NAV 報酬**,"
            "「近1年含息報酬%」含配息;「近3年/5年年化%」為年化。\n"
            "- **「年化波動%」** = 年化標準差;**「最大回撤%」**;"
            "**「最新淨值」** 為**原幣**(見「計價幣別」欄,未換算 TWD)。\n"
            "- **「配息年化率%」** = 配息率(≠ 含息報酬);**「經理費」**。\n"
            "- **「資料來源」** = 命中的來源;**「序列稀疏」** = True 時年化值已誠實砍掉。\n"
            "- ⚠️ **不含**:AI 跨檔評論、逐檔持股明細 —— 屬小 N 深看功能,"
            "請到「💊 組合健診」分頁對篩選出的一小撮基金做。"
        )
