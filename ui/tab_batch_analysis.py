"""ui/tab_batch_analysis.py — 批次基金分析分頁(上傳 400 檔 → 逐檔跑 → 下載 CSV)。

L3 delivery surface。單一職責:收一份代號清單(上傳 CSV / 貼上)→ 每檔跑
`build_batch_unified_row`(= 與「組合健診」同一張 40 欄大表)→ 進度條逐檔累積到
session_state(可中斷續跑、磁碟續存)→ 成功/失敗摘要 → 下載 CSV(utf-8-sig)。

v19.413:批次表**完全等同組合健診大表**(①健康分析 + ②配息相關 + ③實際購買結果 +
σ/風險/MK),共用 `process_one_fund`(L2)+ 同一組 SSOT builder。每檔以 100 萬 TWD 為基準。

§1 誠實:400 檔必有失敗(停售/403/無 NAV),失敗檔完整留在表裡帶「狀態 + 備註」,
數值留白(絕不填 0),下載檔可追溯。AI 跨檔評論 / 持股明細不在批次表(小 N,見組合健診)。
"""
from __future__ import annotations

import datetime as _dt
import re

import pandas as pd
import streamlit as st

from ui.helpers.fund_grp_health.unified import (
    BATCH_NUMERIC_COLUMNS,
    BATCH_UNIFIED_COLUMNS,
    build_batch_unified_row,
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

def _is_fail(row: dict) -> bool:
    """該檔是否失敗 / 無效(可重試)。狀態欄含「失敗」或「無效」。"""
    _s = str((row or {}).get("狀態", ""))
    return ("失敗" in _s) or ("無效" in _s)


def _rows_compatible(rows: dict) -> bool:
    """新 schema 檢查:每列須有「狀態」欄。v19.413 批次表升級為組合健診大表後,
    舊版 flat-schema 存檔(status/note/nav…)不相容 → 讀回時忽略,避免欄位錯位。"""
    vals = list((rows or {}).values())
    return bool(vals) and all(isinstance(r, dict) and "狀態" in r for r in vals)


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
        if c not in rows or (retry_failed and _is_fail(rows[c]))
    ]
    if not todo:
        st.info("沒有待處理的代號(全部已完成)。如要全部重來,請按「🗑️ 清除重來」。")
        return

    # v19.413:讀景氣位階(同組合健診)→ 讓「資產屬性 / 操作訊號」欄能算真值,而非永遠「—」
    _pi = st.session_state.get("phase_info") if hasattr(st, "session_state") else None
    _phase = (_pi or {}).get("phase") or ""
    _score = (_pi or {}).get("score")

    bar = st.progress(0.0)
    live = st.empty()
    total = len(todo)
    for i, code in enumerate(todo, start=1):
        live.markdown(f"⏳ 處理中 **{i}/{total}**:`{code}` …")
        # 組合健診大表單檔列;失敗也回一列不外拋。phase/score 對齊健診 tab
        rows[code] = build_batch_unified_row(code, phase=_phase, score=_score)
        _persist(run_id, codes, rows)         # 每檔落地(續存後盾)
        bar.progress(i / total)
    bar.empty()
    live.markdown(f"✅ 本輪完成 **{total}** 檔。")


def _build_df(codes: list[str], rows: dict) -> pd.DataFrame:
    """依上傳順序組 DataFrame(= 組合健診大表 40 欄)。只納入已完成的檔;數值欄轉 numeric。"""
    data = [rows[c] for c in codes if c in rows]
    df = pd.DataFrame(data, columns=BATCH_UNIFIED_COLUMNS)
    for _c in BATCH_NUMERIC_COLUMNS:
        if _c in df.columns:
            df[_c] = pd.to_numeric(df[_c], errors="coerce")
    return df


def render_batch_analysis_tab() -> None:
    st.markdown("## 📦 批次基金分析")
    st.caption(
        "上傳或貼上基金代號清單 → 每檔跑**與「組合健診」同一張大表**(評分/報酬/風險/配息/"
        "σ位階/MK 買賣點,以 100 萬 TWD 為基準)→ 下載 CSV。每檔抓 NAV/配息/績效"
        "(T+1~T+3、含 fallback chain)+ 完整健診計算,**400 檔約 30~40 分鐘**;**每檔即時存磁碟** → "
        "關分頁 / 伺服器重啟也不白費,重進上傳同一份清單自動接續。"
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
        _ck_rows = dict(ckpt.get("rows") or {}) if ckpt else {}
        if _ck_rows and not _rows_compatible(_ck_rows):
            # 舊版 flat-schema 存檔 → 忽略,提示重跑(表格已升級為組合健診大表)
            st.session_state[_K_ROWS] = {}
            st.info("偵測到**舊版格式**的批次存檔,已忽略 —— 批次表已升級為「組合健診大表」,"
                    "請重新分析(舊存檔可按「🗑️ 清除重來」刪除)。")
        elif _ck_rows:
            st.session_state[_K_ROWS] = _ck_rows
            st.session_state[_K_RUN_AT] = ckpt.get("updated_at", "—")
            st.success(f"🔁 已從磁碟讀回上次進度:{len(_ck_rows)} 檔"
                       f"(更新於 {ckpt.get('updated_at', '—')})")
        else:
            st.session_state[_K_ROWS] = {}

    st.session_state[_K_CODES] = codes
    rows: dict = st.session_state.get(_K_ROWS, {})
    done = sum(1 for c in codes if c in rows)
    est_min = max(1, round(len(codes) * 5 / 60))   # 粗估 ~5s/檔(含完整健診計算)
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
            _ck_rows = dict(ckpt.get("rows") or {}) if ckpt else {}
            if not ckpt:
                st.error("讀回失敗:存檔可能已損毀或被刪除。")
            elif _ck_rows and not _rows_compatible(_ck_rows):
                st.warning("此存檔為**舊版格式**(批次表已升級為組合健診大表),無法讀回;"
                           "請重新上傳清單分析。")
            else:
                st.session_state[_K_ROWS] = _ck_rows
                st.session_state[_K_CODES] = (
                    ckpt.get("codes") or list(_ck_rows.keys()))
                st.session_state[_K_RUN_AT] = ckpt.get("updated_at", "—")
                st.session_state[_K_RUN_ID] = r["run_id"]
                st.rerun()


def _render_existing_results() -> None:
    """有結果就渲染摘要 + 表 + 下載鈕(§1:失敗檔誠實入表)。"""
    codes = st.session_state.get(_K_CODES, [])
    rows = st.session_state.get(_K_ROWS, {})
    if not codes or not rows:
        return

    df = _build_df(codes, rows)
    if df.empty:
        return

    # ── 摘要(§1:成功 / 失敗 一目了然)────────────────
    n = len(df)
    _status = df["狀態"].astype(str)
    n_ok = int(_status.str.contains("成功").sum())
    n_fail = n - n_ok
    run_at = st.session_state.get(_K_RUN_AT, "—")

    st.divider()
    st.markdown(f"### 📊 分析結果(組合健診大表)　·　執行時間(台北):{run_at}")
    m1, m2, m3 = st.columns(3)
    m1.metric("檔數", n)
    m2.metric("✅ 成功", n_ok)
    m3.metric("❌ 失敗 / 無效", n_fail)
    if n_fail:
        st.caption("失敗的檔仍完整列在表裡(狀態 + 備註標明原因、數值留白),"
                   "**不會靜默丟棄或填假值**(§1)。可按「🔁 重試失敗檔」重抓。")

    # ── 表格(欄位已是中文,與組合健診大表同款;橫向可滾動)──────────
    st.dataframe(df, use_container_width=True, height=460, hide_index=True)

    # ── 下載 CSV(utf-8-sig,Excel 直開中文標題正常)──────────────
    fname_ts = (run_at or "").replace("-", "").replace(":", "").replace(" ", "_") or "export"
    st.download_button(
        "⬇️ 下載分析結果 CSV",
        df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"fund_batch_{fname_ts}.csv",
        mime="text/csv",
        use_container_width=True,
        key="batch_download",
    )

    # ── 🔄 輪動配對建議(跨類別;讀上表 σ/操盤評分/類別,不重抓)+ 獨立 CSV 下載 ──
    from ui.helpers.fund_grp_health.rotation import render_rotation_section_from_df
    render_rotation_section_from_df(df)

    # ── 🔀 換標決策(策略燈號已在上表;此區 regime banner + 紅燈檔一對一替換)── v19.423 ──
    try:
        from ui.helpers.fund_grp_health.switch_section import render_switch_section
        render_switch_section(df.to_dict("records"))
    except Exception as _e_sw:  # noqa: BLE001
        st.caption(f"⬜ 換標決策區塊失敗:[{type(_e_sw).__name__}] {str(_e_sw)[:80]}")

    # ── 🧭 景氣位階適配摘要 ── v19.425 ──
    try:
        from ui.helpers.fund_grp_health.regime_section import render_regime_fit_section
        render_regime_fit_section(df.to_dict("records"))
    except Exception as _e_rf:  # noqa: BLE001
        st.caption(f"⬜ 景氣適配區塊失敗:[{type(_e_rf).__name__}] {str(_e_rf)[:80]}")

    with st.expander("ℹ️ 欄位說明 / 這張表沒有什麼", expanded=False):
        st.markdown(
            "- 本表 = **組合健診大表**(①健康分析 + ②配息相關 + ③實際購買結果 + σ/風險/MK)。\n"
            "- **評分**:4D Grade / 4D Score;**每月配息 / 累積 TWD 配息 / 原幣本金 / 單位** 皆以"
            "**100 萬 TWD 為基準**(FX 換算,見「換匯資訊 🧮」欄)。\n"
            "- **報酬**:1Y 含息(wb01 官方)/ 3Y·5Y 年化 / 全期實際·年化;**風險**:Sharpe /"
            "Sortino / Calmar / Max DD / σ 位階(HWM);**買賣點**:MK 買 3~賣 3 + 現價位階。\n"
            "- **吃本金燈號 / 換標的建議 / MK 3-3-3** 判定與組合健診同源(SSOT)。\n"
            "- **上/下檔捕捉% + 操盤評分**:vs 大盤(TWD→台股 / 其餘→S&P500)分漲跌月算;"
            "需**漲、跌月各 ≥ 3**(貼近高點/短歷史的基金跌月太少 → 留白,不假造);"
            "**3–5 月為參考值**(下檔樣本少較噪)。\n"
            "- **vs 大盤%**:近 1 年**純價格**報酬 − 大盤(正 = 跑贏);純淨值對純指數(公平不含息),"
            "歷史不足 1 年 → 用全期。\n"
            "- **基期**:🔴 高基期(σ≥−0.5 貼近高點)/ ⚪ 中性 / 🟢 低基期(σ≤−1.5 跌深)——"
            "可篩選一次挑出所有高/低基期標的(門檻同輪動配對)。\n"
            "- **策略燈號 / 換標策略分**:換標決策(獨立於 4D)—— 🔴 賣出/平轉、🟡 觀望、"
            "🟢 續抱加碼、⬜ 資料不足;分 = 1Y含息35+Sharpe30+MaxDD20+vs大盤15。下方「🔀 換標決策」"
            "區給紅燈檔的同類一對一替換建議 + 大盤 regime 提醒。\n"
            "- **景氣適配 / 適配傾向**:依資產屬性 + 抗跌/追漲對照**當前景氣位階**——"
            "✅順風 / ⚠️逆風 / ⚪全景氣 / ⬜無法判定(參考傾向,非買賣建議、非%配置)。"
            "⚠️ 批次表的景氣適配**以各檔跑批當下的景氣位階為準**;若景氣位階變動請重跑。\n"
            "- ⚠️ **不含**:AI 跨檔評論、逐檔持股明細 —— 小 N 深看功能,請到「💊 組合健診」做。"
        )
