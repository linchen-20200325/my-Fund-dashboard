"""ui/tab_batch_analysis.py — 批次基金分析分頁(上傳 400 檔 → 逐檔跑 → 下載 CSV)。

L3 delivery surface。單一職責:收一份代號清單(上傳 CSV / 貼上)→ 每檔跑
`build_batch_unified_row`(= 與「組合健診」同一張 40 欄大表)→ 進度條逐檔累積到
session_state(可中斷續跑、磁碟續存)→ 成功/失敗摘要 → 下載 CSV(utf-8-sig)。

v19.413:批次表**完全等同組合健診大表**(①健康分析 + ②配息相關 + ③實際購買結果 +
σ/風險/),共用 `process_one_fund`(L2)+ 同一組 SSOT builder。每檔以 100 萬 TWD 為基準。

§1 誠實:400 檔必有失敗(停售/403/無 NAV),失敗檔完整留在表裡帶「狀態 + 備註」,
數值留白(絕不填 0),下載檔可追溯。AI 跨檔評論 / 持股明細不在批次表(小 N,見組合健診)。
"""
from __future__ import annotations

import datetime as _dt
import re

import pandas as pd
import streamlit as st

from ui.helpers.render_state import system_error
# ③ 基金研究合併頁（線框 §03）共用頂部的所有權旗標。預設全空 → 本檔行為與合併前完全相同。
from ui.helpers.fund_research.merge_context import (
    PAGE_HEADER as _MERGED_PAGE_HEADER,
    owned_by_merged_page as _merged_page_owns,
)
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
    """該檔是否失敗 / 無效。狀態欄含「失敗」或「無效」。

    ⚠️ 「⚠️ 部分成功」**不算**失敗 —— 它有抓到淨值、大部分欄位算得出來,
    只是某一組欄留白。計數與統計要把它獨立成一態(見 `split_status_counts`)。
    要判「該不該重跑」請用 `_is_retryable`,不要用這支(稽核 A1 / 🟠-7)。
    """
    _s = str((row or {}).get("狀態", ""))
    return ("失敗" in _s) or ("無效" in _s)


def _is_retryable(row: dict) -> bool:
    """該檔值不值得重跑 = 抓取失敗 / 代號無效 / **部分成功**。稽核 🟠-7。"""
    _s = str((row or {}).get("狀態", ""))
    return _is_fail(row) or ("部分成功" in _s)


def split_status_counts(statuses) -> tuple:
    """狀態欄 → (完全成功, 部分成功, 失敗/無效) 三態計數。稽核 A1(2026-08-14)。

    抽成具名純函式的理由:原本是摘要區裡的三行 inline 運算,而
    `"部分成功"` **字面含有「成功」** —— 任何人日後回頭用最直覺的
    `str.contains("成功")` 改回去,都會把「13~22 欄沒算出來」的檔靜靜混進
    全綠計數,而且不會有任何測試會紅。抽出來就守得住(PROCESS §4)。

    Args:
        statuses: 可迭代的狀態字串(pandas Series / list 皆可)。

    Returns:
        (n_ok, n_partial, n_fail) —— 三者相加必等於輸入長度。
    """
    n_ok = n_partial = n_fail = 0
    for _s in statuses:
        _t = str(_s or "")
        if "部分成功" in _t:
            n_partial += 1
        elif "成功" in _t:
            n_ok += 1
        else:
            n_fail += 1
    return n_ok, n_partial, n_fail


def _rows_compatible(rows: dict) -> bool:
    """新 schema 檢查:每列須有「狀態」欄。v19.413 批次表升級為組合健診大表後,
    舊版 flat-schema 存檔(status/note/nav…)不相容 → 讀回時忽略,避免欄位錯位。

    ⚠️ 本檢查刻意**只**守「狀態」這個 schema 世代旗標,不隨每次加欄跟著收緊 ——
    加欄(如「淨值日期 / 淨值新鮮度」)屬**向後相容的擴充**:`_build_df` 以
    `BATCH_UNIFIED_COLUMNS` 為欄骨架建表,舊列缺鍵只會變空格,不會欄位錯位。
    若這裡跟著擋,使用者會為了兩個新欄被迫重跑 30~40 分鐘的 400 檔批次。
    缺欄的事實改由 `_render_stale_schema_notice` 明講(§1 不靜默)。"""
    vals = list((rows or {}).values())
    return bool(vals) and all(isinstance(r, dict) and "狀態" in r for r in vals)


# 每次為批次大表加新欄,都必須在這裡登記(欄名 → 該欄是哪一版加的說明)。
# 理由:舊 checkpoint 讀得回來(`_rows_compatible` 只驗「狀態」這個世代旗標),
# `_build_df` 以固定欄骨架建表 → 舊列缺鍵補成空白。空白與「這檔真的沒有」
# 在畫面上長得一模一樣,而新欄的 help 又教使用者把空白讀成後者(§1)。
# ⚠️ 只登記在 `_render_stale_schema_notice` 掃得到的地方沒有用 —— 加欄時
#    請同時更新這個 tuple,否則新欄會靜靜地留白(2026-08-14 稽核 🟠-8 的成因)。
_LATE_ADDED_COLUMNS: tuple = ("淨值新鮮度", "淨值樣本")


def _rows_missing_late_columns(rows: dict) -> dict:
    """{欄名: 缺該欄的成功列數} —— 只算成功列(失敗列本來就整列留白)。"""
    out: dict = {}
    for _col in _LATE_ADDED_COLUMNS:
        _n = sum(1 for r in (rows or {}).values()
                 if isinstance(r, dict) and not _is_fail(r) and _col not in r)
        if _n:
            out[_col] = _n
    return out


def _rows_missing_freshness(rows: dict) -> int:
    """回傳「成功但沒有淨值新鮮度欄」的列數(= 加欄前存的舊 checkpoint)。

    保留供既有測試與 caller 使用;新的多欄版走 `_rows_missing_late_columns`。
    """
    return sum(1 for r in (rows or {}).values()
               if isinstance(r, dict) and not _is_fail(r) and "淨值新鮮度" not in r)


def _render_stale_schema_notice(rows: dict) -> None:
    """§1:讀回的舊 checkpoint 缺新欄 → 當場講清楚,不讓空白冒充「這檔沒資料」。"""
    _missing = _rows_missing_late_columns(rows)
    if not _missing:
        return
    _parts = "、".join(f"「{_c}」({_n} 檔)" for _c, _n in _missing.items())
    st.caption(
        f"ℹ️ 部分存檔是在新增下列欄位**之前**跑的,因此這些欄留白:{_parts}。"
        "這是**存檔較舊**,不是這些基金查不到該項資料 —— 尤其「淨值樣本」欄留白時,"
        "請**不要**照該欄 help 讀成「連淨值序列都沒拿到」。"
        "要補齊請按「🗑️ 清除重來」重跑(或忽略,其餘欄位不受影響)。"
    )


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
        # 與 nav_history 寫入失敗同一族：**畫面數字全對,壞掉的是持久化**。
        # 兩處顏色必須一致,否則同一種失敗又會變成「看你在哪個分頁」。
        # ⚠️ 判斷（非事實）：紅框指的是「這批結果留不住」,不是「這批數字算錯」。
        system_error("磁碟續存失敗", e,
                     hint="本次跑批結果**全部有效**,但改為只存記憶體 —— "
                          "關掉分頁或重啟就會消失,無法續跑。")


def _run_batch(codes: list[str], retry_failed: bool) -> None:
    """逐檔跑(進度條)。已完成的跳過(續跑);retry_failed=True 時失敗檔重抓。

    每完成一檔立刻寫進 session_state **+ 磁碟 checkpoint** → 關分頁 / 重啟後仍可續跑。
    """
    from repositories import batch_checkpoint as bc
    rows: dict = st.session_state.setdefault(_K_ROWS, {})
    st.session_state[_K_RUN_AT] = _dt.datetime.now(_TW_TZ).strftime("%Y-%m-%d %H:%M")
    run_id = bc.compute_run_id(codes)

    # 決定本輪要處理哪些(未做的 + 選擇性重試失敗的)
    # 稽核 🟠-7:「⚠️ 部分成功」也納入重試範圍。它不含「失敗」「無效」故 `_is_fail`
    # 判 False —— 分類本身是對的(淨值抓到了),但如果重試放不進來,使用者就會看到
    # 一個**自己無法處理**的狀態:唯一出路是整批清除重跑(400 檔要 2~5 小時)。
    # 部分成功多半是暫時性的(大盤基準抓失敗 / 匯率逾時),重跑單檔通常就好了。
    todo = [
        c for c in codes
        if c not in rows or (retry_failed and _is_retryable(rows[c]))
    ]
    if not todo:
        st.info("沒有待處理的代號(全部已完成)。如要全部重來,請按「🗑️ 清除重來」。")
        return

    # v19.413:讀景氣位階(同組合健診)→ 讓「資產屬性 / 操作訊號」欄能算真值,而非永遠「—」
    _pi = st.session_state.get("phase_info") if hasattr(st, "session_state") else None
    _phase = (_pi or {}).get("phase") or ""
    _score = (_pi or {}).get("score")

    # v19.497:選股池自填名 → name_hint。批次含池成員(如 ALZF9,線上抓不到真名)時
    # 顯示池名而非代號。§1:池讀失敗不擋批次(guard → 空 map)。EX-CRUD-1 允許 L3 直呼。
    _name_map: dict = {}
    try:
        from repositories.pool_repository import list_pool
        _name_map = {str(e.code).upper(): (e.name or "") for e in (list_pool() or []) if e.name}
    except Exception as _e_pool:  # noqa: BLE001
        print(f"[batch] 選股池名稱查詢略過:{type(_e_pool).__name__}: {_e_pool}")

    # v19.509:SA 缺(手機無 SA)時,主執行緒捕獲登入者 OAuth client 傳入每列 build →
    # 讓批次大表也讀得到 OAuth 寫進雲端的補回歷史(拿不到 → None → 退 SA/空)。
    _oauth = None
    try:
        from ui.helpers.io.oauth_state import _get_oauth_client
        _oauth = _get_oauth_client()
    except Exception:  # noqa: BLE001
        _oauth = None
    bar = st.progress(0.0)
    live = st.empty()
    total = len(todo)
    for i, code in enumerate(todo, start=1):
        live.markdown(f"⏳ 處理中 **{i}/{total}**:`{code}` …")
        # 組合健診大表單檔列;失敗也回一列不外拋。phase/score 對齊健診 tab
        rows[code] = build_batch_unified_row(
            code, phase=_phase, score=_score,
            name_hint=_name_map.get(str(code).upper(), ""), oauth_client=_oauth)
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
    # 稽核 H1：H1 原寫死「批次基金分析」，分頁列是「📦 批次分析」—— 同頁兩個名字。
    from ui.helpers.story_nav import render_flow_nav, tab_label as _tab_label_tb
    # 合併頁（③ 基金研究）已在共用頂部畫過頁面大標時，這裡不再畫第二個 `##`。
    # 只讓掉標題那一行 —— flow_nav 與下方那段 caption（含「400 檔約 30~40 分鐘」
    # 這個使用者據以決定要不要按下去的預期說明）一律照舊，不得跟著消失。
    if not _merged_page_owns(_MERGED_PAGE_HEADER):
        st.markdown(f"## {_tab_label_tb('batch')}")
    render_flow_nav("batch")   # 巨觀:第 ② 層 基金核心分析
    st.caption(
        "上傳或貼上基金代號清單 → 每檔跑**與「組合健診」同一張大表**(評分/報酬/風險/配息/"
        "σ位階/買賣點,以 100 萬 TWD 為基準)→ 下載 CSV。每檔抓 NAV/配息/績效"
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
    # ── 稽核 D5：估算改吃實測值 ─────────────────────────────────────────────
    # 原本是 `len(codes) * 5 / 60`（~5s/檔），實機實測 **~45s/檔**
    # （2026-08-14：組合健診 2 檔耗時約 90 秒，且健診是 4-worker 並行、
    #  批次是**序列**跑，所以批次只會更慢不會更快）。
    # 400 檔原本顯示「約 33 分鐘」，實際約 **5 小時** —— 差 9 倍。
    # 使用者照這個數字決定要不要按下去，低報等於騙他。
    # 給區間而不是單點：MoneyDJ 每檔要走多頁 + fallback chain，
    # 境外基金常態要跑兩輪 page_type，離散度本來就大。
    _SEC_PER_FUND_FAST = 20   # 快取命中 / 境內單輪
    _SEC_PER_FUND_SLOW = 45   # 實測值：境外走完 fallback chain
    _todo_n = max(len(codes) - done, 0)
    _est_lo = max(1, round(_todo_n * _SEC_PER_FUND_FAST / 60))
    _est_hi = max(1, round(_todo_n * _SEC_PER_FUND_SLOW / 60))
    _est_txt = (f"約 {_est_lo}~{_est_hi} 分鐘" if _est_hi > _est_lo
                else f"約 {_est_hi} 分鐘")
    st.markdown(
        f"**解析到 {len(codes)} 檔**(去重後)　·　已完成 {done} 檔　·　"
        f"剩餘 {_todo_n} 檔，預估 {_est_txt}"
    )
    if _todo_n >= 100:
        st.warning(
            f"⚠️ 這批要跑 {_todo_n} 檔，預估 **{_est_txt}**（依實測 20~45 秒/檔推算）。"
            "本頁是**序列**執行以避免對 MoneyDJ 造成過高請求速率，"
            "跑的過程中請不要關閉分頁；已完成的檔會即時落地，中斷後重上傳同一份"
            "清單可接續。"
        )

    b1, b2, b3 = st.columns([2, 2, 1])
    with b1:
        go = st.button("▶️ 開始 / 繼續分析", type="primary", use_container_width=True,
                       key="batch_go")
    with b2:
        retry = st.button("🔁 重試失敗 / 部分成功檔", use_container_width=True,
                          key="batch_retry", disabled=(done == 0),
                          help="重抓「❌ 抓取失敗」「⚠️ 代號無效」與「⚠️ 部分成功」的檔;"
                               "已完全成功的不會重跑,所以通常很快。")
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

    # ── 摘要(§1:成功 / 部分成功 / 失敗 一目了然)────────────────
    # 稽核 A1(2026-08-14):原本 `str.contains("成功")` 是**兩態**切法,而
    # `unified.py` 現在會回「⚠️ 部分成功」(①/②/③/④ 其中一組算爆 → 該組欄留白)。
    # 「部分成功」字面含「成功」,若沿用舊切法會被算進 `✅ 成功` —— 等於
    # 把「13~22 欄沒算出來」的檔混進全綠計數,使用者永遠不會去看它的備註。
    n = len(df)
    n_ok, n_partial, n_fail = split_status_counts(df["狀態"].astype(str))
    run_at = st.session_state.get(_K_RUN_AT, "—")

    st.divider()
    st.markdown(f"### 📊 分析結果(組合健診大表)　·　執行時間(台北):{run_at}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("檔數", n)
    m2.metric("✅ 完全成功", n_ok)
    m3.metric("⚠️ 部分成功", n_partial,
              help="有抓到淨值、但某一組欄位(健康分析 / 配息 / σ 風險 / 策略燈號)"
                   "計算過程出錯而留白。留白**不代表這檔沒有這項資料**,原因寫在「備註」。")
    m4.metric("❌ 失敗 / 無效", n_fail)
    if n_fail or n_partial:
        st.caption("失敗的檔仍完整列在表裡(狀態 + 備註會標明原因、數值欄留白),"
                   "**不會偷偷丟掉、也不會填假數字**。可按「🔁 重試失敗 / 部分成功檔」重抓;"
                   "「備註」是唯一寫出失敗原因的地方,把滑鼠移到欄名上可看哪些原因值得重試。")
    if n_partial:
        st.caption(f"⚠️ 其中 **{n_partial} 檔為「部分成功」** —— 淨值有抓到,但部分欄組"
                   "計算失敗而留白。**做換標決策前請先讀該列的「備註」**,"
                   "不要把留白讀成「這檔沒有這個特性」。"
                   "這類失敗多半是暫時的(大盤基準抓不到 / 匯率逾時),"
                   "按「🔁 重試失敗 / 部分成功檔」通常就會補齊。")
    _render_stale_schema_notice(rows)

    # ── 表格(欄位已是中文,與組合健診大表同款;橫向可滾動)──────────
    # 必修 4:原本裸 `st.dataframe(df, ...)` —— 48 個中文欄名零 tooltip,且「備註」
    # (100 字失敗原因,§1 唯一揭露)被截成看不出是網路問題還是基金停售。
    # 改吃與健診大表**同一份** column_config(欄寬 + 逐欄 help)。
    from ui.helpers.fund_grp_health.columns import unified_column_config
    _cfg = unified_column_config(batch=True)
    st.dataframe(
        df, use_container_width=True, height=460, hide_index=True,
        column_config={k: v for k, v in _cfg.items() if k in df.columns},
    )

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

    # ── 🧩 候選標的互補探索(元件 B)── 2026-08-31 客戶拍板 Q3:原「攤開照抄 ②
    # 的輪動配對整段」改型為**預設收合的 Expander**(卡片 + 完整表 + CSV,資訊零損失),
    # 不再把第二張大表攤在結果區把頁尾撐爆。讀上表 σ/操盤評分/類別,不重抓。
    from ui.helpers.fund_grp_health.rotation import render_complementary_explorer_from_df
    render_complementary_explorer_from_df(df)

    # ── 🔀 換標決策(策略燈號已在上表;此區 regime banner + 紅燈檔一對一替換)── v19.423 ──
    try:
        from ui.helpers.fund_grp_health.switch_section import render_switch_section
        render_switch_section(df.to_dict("records"))
    except Exception as _e_sw:  # noqa: BLE001 — 換標區塊失敗不擋大表
        # 2026-08-28 顏色批次二之一：與 `tab_fund_grp_health.py` 呼叫的是
        # **同一個 render_switch_section**，那邊已走 system_error、這邊還是灰字。
        system_error("換標決策區塊失敗", _e_sw)

    # ── 🧭 景氣位階適配摘要 ── v19.425 ──
    try:
        from ui.helpers.fund_grp_health.regime_section import render_regime_fit_section
        render_regime_fit_section(df.to_dict("records"))
    except Exception as _e_rf:  # noqa: BLE001
        # 同上：與健診頁的 render_regime_fit_section 是同一個函式，顏色必須一致。
        system_error("景氣適配區塊失敗", _e_rf)

    # 說明文裡的門檻數字一律從 shared/signal_thresholds SSOT 讀(§3.3):
    # 捕捉率最少月數、輪動高/低基期 σ 切點,改常數時這段文案自動跟著改。
    from shared.signal_thresholds import (
        CAPTURE_MIN_MONTHS as _CAP_MIN,
        ROTATION_BUY_SIGMA as _ROT_BUY,
        ROTATION_SELL_SIGMA as _ROT_SELL,
    )
    with st.expander("ℹ️ 欄位說明 / 這張表沒有什麼", expanded=False):
        st.markdown(
            "- 本表 = **和「💊 組合健診」完全同一張大表**(健康分析 + 配息相關 + 實際購買結果 "
            "+ 基期 / 風險 / 買賣點)。\n"
            "- **每一欄的欄名都可以把滑鼠移上去看說明**(怎麼算的、單位是什麼、留白代表什麼、"
            "能不能拿去跨檔比大小)。\n"
            "- **狀態**:✅ 完全成功 / **⚠️ 部分成功** / ❌ 抓取失敗 / ⚠️ 代號無效。"
            "「部分成功」= 淨值抓到了,但某一組欄位算到一半出錯而留白 —— "
            "**留白不代表這檔沒有那個特性**,缺哪一組寫在「備註」。"
            "多半是暫時性的,按「🔁 重試失敗 / 部分成功檔」通常會補齊。\n"
            "- **淨值日期 / 淨值新鮮度**:這檔最新一筆淨值是哪一天的、距今幾天。基金淨值本來就"
            "慢 1~3 天才公布、週末假日不更新,所以 🟢/🟠 都算正常;**🔴 = 很可能已停售或清算** —— "
            "此時同一列的基期 / 操盤評分 / 策略燈號都是用已經不動的舊淨值算的,別當成現況。"
            "點欄名排序可一次挑出所有 🔴。\n"
            "- **淨值樣本**:這一列的數字是拿**幾筆淨值、橫跨幾天**算出來的。"
            "帶 ⚠️ 表示我們只抓到很短一段歷史(常見於保單專屬網頁被擋、只讀到首頁的"
            "「近 30 日淨值表」)—— 此時 Sharpe / 波動 / 最大回檔 / 3Y 5Y 年化**會整批留白**,"
            "那是樣本不夠,**不是這檔沒有風險**;同列的 4D 分數仍會用剩下幾個面向給分,"
            "別把它當完整體檢。\n"
            "- **評分**:4D 等第與分數;**每月配息 / 累積台幣配息 / 原幣本金 / 單位** 全都假設"
            "**投入 100 萬台幣**來比較(換匯過程見「換匯資訊 🧮」欄)。\n"
            "- **報酬**:近一年含息(優先抄 MoneyDJ 官方績效表)/ 3 年·5 年平均每年 / "
            "全期實際與年化;**風險**:Sharpe / Sortino / Calmar / 最大跌幅 / 離高點多遠;"
            "**買賣點**:分批買 3 段~賣 3 段 + 現價落在哪一段。\n"
            "- **吃本金燈號 / 換標的建議 /  3-3-3** 的判定與組合健診用同一套算法,不會兩處打架。\n"
            "- **上/下檔捕捉% + 操盤評分**:和大盤比(台幣計價比台股、**美元計價比 S&P 500**),"
            "把月份拆成大盤漲的月和跌的月分開算;"
            f"需要漲的月、跌的月**各**至少 {_CAP_MIN} 個月(貼近高點或成立太短的基金跌月太少 → "
            "留白,不硬湊)。旁邊「**捕捉樣本**」欄會逐列標實際月數:✅ 夠穩 / ⚠️ 樣本少(只能參考)"
            "/ ⬜ 不足 —— 3 個跌月算出的 92 分不等於 40 個跌月的 92 分,排序比大小前先看這欄。\n"
            "- **vs 大盤%**:近一年比大盤多賺(正)或少賺(負)幾個百分點;兩邊都只看價格、"
            "都不算配息,所以比法公平。「**vs 大盤期間**」欄會標明實際量了多長(近 1 年 / ⚠️ 全期)。"
            "⚠️ **不是台幣也不是美元計價的(歐元/澳幣/南非幣/人民幣/日圓…)一律留白** —— "
            "基金淨值是原幣,直接去減美股指數等於把匯率漲跌算成經理人的功勞,寧可不給也不給錯的。\n"
            f"- **基期**:🔴 高基期(σ ≥ {_ROT_SELL:+.1f},貼近高點、現在買偏貴)/ ⚪ 中性 / "
            f"🟢 低基期(σ ≤ {_ROT_BUY:+.1f},跌得夠深)/ ⬜ 資料不足(含淨值完全不動的停售檔)"
            "—— 可篩選一次挑出所有高 / 低基期標的(門檻與下方「輪動配對」同一組)。\n"
            "- **策略燈號 / 換標策略分**:專為「該不該換掉」設計,與 4D 健康度是兩套 —— "
            "🔴 賣出 / 轉換、🟡 觀望、🟢 續抱可加碼、⬜ 資料不足;"
            "分數 = 近一年含息 35 + Sharpe 30 + 最大跌幅 20 + vs 大盤 15。"
            "下方「🔀 換標決策」區會給紅燈檔的同類替換建議 + 大盤整體氣氛提醒。\n"
            "- **景氣適配 / 適配傾向**:拿資產屬性 + 抗跌 / 追漲能力對照**現在的景氣位階** —— "
            "✅ 順風 / ⚠️ 逆風 / ⚪ 全景氣 / ⬜ 無法判定(只是傾向參考,不是買賣建議,"
            "也不是叫你配幾 %)。⚠️ 批次表用的是**各檔跑批當下**的景氣位階;景氣變了請重跑。\n"
            "- **匯率位階 / 淨值×匯率**(只有外幣基金有):美元兌台幣相對近一年的位置"
            "(台幣強 / 中性 / 台幣弱)× 淨值基期 → 🟢 兩邊都便宜(進場時機好)/ "
            "🔴 兩邊都貴(出場時機好)/ ⚪ 觀望。台幣計價顯示 ➖;匯率比淨值更難預測,"
            "只是傾向參考、不保證買低賣高。⚠️ **用的是跑批當下的匯率**,匯率變動請重跑。\n"
            "- ⚠️ **這張表沒有**:AI 跨檔評論、逐檔持股明細 —— 那是少量基金深看用的,"
            "請到「💊 組合健診」做。"
        )
