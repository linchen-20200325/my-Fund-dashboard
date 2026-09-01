"""scripts/weekly_nav_backfill.py — 每週 NAV 自動補齊(GitHub Actions 美國 IP / NAS)v19.479。

不靠 user 開 App:**每天**(v19.495,原每週)對「**持倉 ∪ 選股池**」跑一次 `backfill_to_gs`,把最新可得淨值
append 進雲端 `nav_history`(永久、重開不丟)。與 App「🔄 一鍵補抓全部缺淨值」**同一條 L2**
(`services.nav_history_store.backfill_to_gs`),`(code, date)` 冪等去重;含 LU 檔的
**ISIN → Yahoo secId 自動解析**(v19.478),故雲端跑一次就把 LU 檔的最新淨值也補上。

── 為何建議 GitHub Actions(美國 IP)────────────────────────────
Yahoo / 晨星從**美國 IP** 可達(台灣 IP 被擋)。LU 檔要靠 `ISIN→secId→Yahoo chart` 抓,
只有在美國 IP 環境(GitHub Actions / Streamlit Cloud)才成功;NAS(台灣 IP)可跑但 LU 檔
只拿得到 MoneyDJ 短窗。TW000 台灣註冊檔兩邊都靠 MoneyDJ(增量抓最新一筆即可)。

── 前置(env / GitHub repo secrets;infra.config env fallback)────
    google_service_account = Service Account 完整 JSON 字串(須為 nav / pool Sheet 編輯者)
    NAV_SHEET_ID           = (選填)nav_history 目標 Sheet;未設走 baked 預設
    POLICY_SHEET_ID        = 持倉 Sheet ID(讀持倉代碼;未設 → 退 macro_weights_sheet_id)
    macro_weights_sheet_id = (fallback)持倉 / 內部表 Sheet ID
cron:.github/workflows/weekly_nav_backfill.yml(**每天** 20:00 台灣;NAV 多 T+1 傍晚已確定;
    (code,date) 冪等 → 週末/假日無新值時 no-op)。檔名沿用 weekly_*(legacy,避免動 references)。
先手動驗證(不寫入,只列將補的代號):
    python scripts/weekly_nav_backfill.py --dry-run

── 行為(§1 Fail Loud)──────────────────────────────────────────
缺 SA / 讀不到任何代號 → exit 2;backfill 全數抓不到 → exit 1;部分抓不到 → 顯式列出 + exit 0
(增量場景單檔暫時抓不到非致命);雲端未啟用(is_enabled=False)→ exit 2(只存本機無意義)。
**任一檔被 Gate 0 擋下 → exit 1**(2026-08-28 稽核修正:被擋 ≠ 抓不到,且是**持續性**
故障 —— 舊版 n_ok>0 就回 0,一檔被擋會綠燈零通知、每天重演,fail-closed 退化成
silent data loss;理由與「天天紅」的權衡完整寫在 `main` 末段)。
另寫 `$GITHUB_STEP_SUMMARY`(有設才寫)讓 run 頁面一眼看懂,見 `_step_summary`。

**幣別不一致 → 拒絕換源(2026-09-01)**:長歷史候選與本檔預期幣別對不上時,`backfill_to_gs`
會拒絕整條替換(§1 不換算、不混寫)。**單就「拒絕」這個決定本身而言沒有資料遺失**
——**但那不等於這一檔今天有補到**:同一檔可以「拒絕換源」再疊上「MoneyDJ 也抓不到」
或「被 Gate 0 擋下」而**完全沒有寫入**(兩支都以實跑 probe 複驗過)。
⛔ **逐檔結局一律走 `_ccy_outcome`,禁止在任何地方(含註解與 docstring)再寫成
「有寫入 / 照常寫入」這種無條件斷言** —— 2026-09-01 稽核抓到這句話在改完之後
還在同一批模組裡活了 4 處,其中一處正是 exit code 決策的書面理由。

它**刻意不影響 exit code**:與 Gate 0 的「被擋下」不同 —— 後者是**每一檔都確定沒寫入**
的持續性資料遺失,而且有 `NAV_GATE0_MODE=observe` 這個刻意的止血開關;
**幣別拒絕沒有任何開關**,選股池 currency 填錯的檔會每天拒絕、永遠不會自己好 →
真讓它 exit 1,這條 cron 會**永久紅**,把 `blocked` 賴以生效的訊號一起燒掉。
它照樣要**被看見**:逐檔 🟠 一行(帶結局)+ 完成行的聚合計數(含「其中幾檔完全沒寫入」)
+ Step Summary 專屬表格(見 `_step_summary`),否則就是 §1／§5 要防的無聲降級。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _log(msg: str) -> None:
    print(f"[weekly_nav_backfill] {msg}", file=sys.stderr)


def _gather_codes(client, sheet_id) -> list:
    """持倉(政策 Sheet)∪ 選股池 → 去重(§2.1 upper)代號清單。純函式(client/sheet 注入,可測)。"""
    _codes: list = []
    # 持倉(重用已驗證的 headless 讀取)
    try:
        from scripts.weekly_switch_notify import _read_holdings
        _codes.extend(_read_holdings(client, sheet_id) if (client and sheet_id) else [])
    except Exception as _e:  # noqa: BLE001 — 讀持倉失敗不擋(還有選股池);§1 記 log 不靜默
        _log(f"讀持倉失敗(略過持倉):{type(_e).__name__}: {_e}")
    # 選股池(self-contained,SA 內部解析)
    try:
        from repositories.pool_repository import list_pool
        _codes.extend(str(e.code or "").strip().upper() for e in list_pool())
    except Exception as _e:  # noqa: BLE001
        _log(f"讀選股池失敗(略過選股池):{type(_e).__name__}: {_e}")
    _seen: set = set()
    out: list = []
    for _c in _codes:
        _c = str(_c or "").strip().upper()
        if _c and _c not in _seen:
            _seen.add(_c)
            out.append(_c)
    return out


def _load_client_and_holdings_sheet():
    """(gspread client, 持倉 sheet_id)。缺 SA → (None, None)。持倉 sheet 優先 POLICY_SHEET_ID。"""
    try:
        from infra.config import get_secret
        from repositories.policy_repository import get_gspread_client
    except Exception as _e:  # noqa: BLE001
        _log(f"import 失敗:{type(_e).__name__}: {_e}")
        return None, None
    _sa = get_secret("google_service_account")
    if not _sa:
        _log("缺 google_service_account secret")
        return None, None
    try:
        client = get_gspread_client(_sa)
    except Exception as _e:  # noqa: BLE001
        _log(f"建 gspread client 失敗:{type(_e).__name__}: {_e}")
        return None, None
    _sid = get_secret("POLICY_SHEET_ID") or get_secret("macro_weights_sheet_id")
    return client, (str(_sid) if _sid else None)


def _ccy_outcome(r: dict) -> str:
    """一檔「幣別拒絕換源」的**實際結局**一句話。

    2026-09-01 稽核 🔴:上一版在四個地方無條件寫「原幣別序列照常寫入」——
    那是**斷言**,而它在兩個可達狀態下是**假的**(兩支都以實跑 probe 複驗過,不是推論):
      - **MoneyDJ 也抓不到**:`ccy_refused` 設在 `if s.empty` **之前** → 拒絕成立、
        序列是空的 → cron 會同時印「⬜ 抓不到淨值」與「🟠 原幣別序列…寫入」,
        **同一次 run 的兩行自相矛盾,而且根本不存在那條「原幣別序列」**。
      - **同一檔又被 Gate 0 擋下**:`ccy_refused` 也設在 Gate 0 **之前** → 會同時印
        🔴「已擋下未寫入」與 🟠「照常寫入」。⚠️ 而且這兩件事**正相關** ——
        幣別混亂的基金,正是歷史值對不上 Gate 0 的那一檔。

    §1:訊息說謊比沒有訊息更危險。**資料行為本身是對的**(空序列時拒絕美元候選仍然正確
    —— 寧可沒有,不可寫錯幣別);錯的純粹是敘述,所以這裡只改敘述。
    """
    if r.get("blocked"):
        return "本檔另被 Gate 0 擋下,今天沒有寫入任何淨值"
    if not r.get("fetched"):
        return "本檔沒有其他可寫入的序列,今天等於沒補到"
    # ⚠️ 用「保留、照常送出寫入」而不是「照常寫入」:本腳本的逐檔行是 **fetch 語意**
    # （檔內既有註解自陳「抓取成功 vs 雲端寫入失敗是兩件事」）。雲端 `append_points`
    # 若整批爆掉,這一檔一樣一筆都沒進去 —— 那是**全域**失敗,由完成行的
    # 「⚠️ 雲端寫入失敗」+ exit 1 大聲負責,但逐檔行不該先替它宣稱「已寫入」。
    return "原幣別序列保留,照常送出寫入"


def _ccy_nothing_written(ccy_refused: list) -> int:
    """被拒絕的檔裡,**今天完全沒有寫入**的檔數(blocked 或根本沒抓到)。"""
    return sum(1 for r in ccy_refused if r.get("blocked") or not r.get("fetched"))


def _step_summary(res: dict, blocked: list, ccy_refused: "list | None" = None) -> None:
    """把結果寫進 `$GITHUB_STEP_SUMMARY`（有設才寫;本機/NAS 無此 env → no-op）。

    exit code 負責**叫人來看**（見 `main` 末段的理由）,本函式負責**讓他一眼看懂** ——
    run 頁面直接看到哪一檔被擋、差在哪一天,不必翻 log。§5 可觀測。
    失敗只 log 不擋（寫 summary 壞掉不該讓一次成功的補淨值變成失敗）。

    2026-09-01 新增 `ccy_refused`（幣別不一致 → 拒絕換源）。**與 `blocked` 同規格渲染,
    但語意完全不同,渲染上必須分得開**:`blocked` 是「抓到了但**整檔沒寫入**」;
    `ccy_refused` 只表示「**沒有換成更長的候選**」——**這一檔今天到底有沒有寫入,
    要看 `_ccy_outcome(r)` 逐檔判**（可能有寫、可能疊上抓不到、可能疊上被 Gate 0 擋下）。
    ⛔ 本 docstring 上一版寫「`ccy_refused` 是『有寫入…』」,那正是 `_ccy_outcome`
    這個函式存在的理由所要消滅的那句無條件斷言 —— 產生條件式結局的函式旁邊
    留著一句無條件斷言,是 2026-09-01 稽核當場點名的諷刺。
    ⚠️ 為什麼非渲染不可:這道守門的「誠實揭露」原本只存在 stderr 數百行 log 裡,
    沒有任何聚合、沒有任何 UI —— 那就是 §1／§5 要防的**無聲降級**。
    """
    import os
    _path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not _path:
        return
    _ccy = list(ccy_refused or [])
    _ccy_none = _ccy_nothing_written(_ccy)
    _nb = int(res.get("n_blocked") or 0)
    _nf = int(res.get("n_fail") or 0) - _nb
    _lines = [
        "## NAV 回填結果",
        "",
        f"- ✅ 抓到並寫入:**{res.get('n_ok', 0)}** 檔（雲端去重後新增 "
        f"**{res.get('gs_written', 0)}** 筆）",
        f"- ⬜ 抓不到:**{_nf}** 檔",
        f"- 🔴 被 Gate 0 擋下（**抓到了但沒寫入**）:**{_nb}** 檔",
        f"- 🟠 幣別不一致 → 拒絕換源:**{len(_ccy)}** 檔"
        + (f"（其中 **{_ccy_none}** 檔今天**完全沒有寫入**）" if _ccy_none else ""),
        f"- Gate 0 模式:`{res.get('gate_mode', '?')}`",
    ]
    if res.get("gs_error"):
        _lines += ["", f"> 🔴 雲端寫入:{res['gs_error']}"]
    if blocked:
        _lines += [
            "",
            "### 🔴 被 Gate 0 擋下的檔（資料完整性偵測,不是抓不到）",
            "",
            "| 代號 | 原因 |", "|---|---|",
        ]
        _lines += [f"| `{r['code']}` | {str(r.get('error') or '').replace('|', '/')} |"
                   for r in blocked]
        _lines += [
            "",
            "這幾檔今天**沒有寫入任何淨值**,不處理就會每天重演。",
            "確認是誤擋 → 設 `NAV_GATE0_MODE=observe` 先止血,再修來源。",
        ]
    if _ccy:
        _lines += [
            "",
            "### 🟠 幣別不一致,已拒絕換源",
            "",
            "| 代號 | 這一檔今天的結局 | 理由 |", "|---|---|---|",
        ]
        _lines += [f"| `{r['code']}` | {_ccy_outcome(r)} | "
                   f"{str(r.get('ccy_refused') or '').replace('|', '/')} |"
                   for r in _ccy]
        _lines += [
            "",
            "長歷史候選與本檔預期幣別對不上 → **拒絕整條換掉**（§1 不換算、不混寫）。",
            "**這個決定本身一定是對的**（寧可沒有,不可寫錯幣別）——",
            "但「今天有沒有補到」要看上表**逐檔**的結局欄,**不是每一檔都有寫入**。",
            "要補到 5 年請去選股池把 `currency` 填對。",
        ]
        if _ccy_none:
            _lines += [
                "",
                f"⚠️ 上表有 **{_ccy_none}** 檔**今天完全沒有寫入任何淨值** ——",
                "拒絕換源之外還疊了「MoneyDJ 也抓不到」或「被 Gate 0 擋下」。",
                "這幾檔不處理就會每天重演。",
            ]
    try:
        with open(_path, "a", encoding="utf-8") as _f:
            _f.write("\n".join(_lines) + "\n")
    except Exception as _e:  # noqa: BLE001 — 寫 summary 失敗不該擋補淨值;§1 記 log 不靜默
        _log(f"寫 GITHUB_STEP_SUMMARY 失敗(非致命):{type(_e).__name__}: {_e}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="每週 NAV 自動補齊(持倉 ∪ 選股池 → 雲端 nav_history)")
    ap.add_argument("--dry-run", action="store_true", help="只列將補的代號,不抓取/不寫入")
    args = ap.parse_args(argv)

    client, sheet_id = _load_client_and_holdings_sheet()
    if client is None:
        _log("缺 Service Account → 無法讀持倉/選股池(§1 exit 2)")
        return 2

    codes = _gather_codes(client, sheet_id)
    if not codes:
        _log("持倉與選股池都讀不到任何代號(§1 exit 2)")
        return 2
    _log(f"將補抓 {len(codes)} 檔:{', '.join(codes)}")

    if args.dry_run:
        _log("--dry-run:不抓取/不寫入,結束。")
        return 0

    from services.nav_history_gs import is_enabled
    if not is_enabled():
        _log("雲端 nav_history 未啟用(缺 SA / NAV_SHEET_ID)→ 只存本機無意義(§1 exit 2)")
        return 2

    from services.nav_history_store import backfill_to_gs
    res = backfill_to_gs(codes)
    _blocked = [r for r in res["results"] if r.get("blocked")]
    # 2026-09-01:因幣別不一致而拒絕換源的檔。**不進 exit code**（理由見檔頭）——
    # ⚠️ 理由**不是**「這些檔都有寫入」（那句已被 STATE 1/2 證偽:同一檔可以再疊上
    # 「抓不到」或「被 Gate 0 擋下」而完全沒寫入,見 `_ccy_outcome`）,而是:
    #   (a) 幣別拒絕**沒有** `NAV_GATE0_MODE` 那種止血開關 → 讓它 exit 1 會永久紅,
    #       把 `blocked` 賴以生效的訊號一起燒掉;
    #   (b) 真正「確定沒寫入」的那兩種情形**本來就各自有自己的 exit code 途徑**
    #       （`blocked` → exit 1;全數抓不到 → exit 1）,不需要本旗標再叫一次。
    # 但它一定要被看見,否則這道守門等於沒揭露 —— 逐檔結局走 `_ccy_outcome`。
    _ccy_refused = [r for r in res["results"] if r.get("ccy_refused")]
    for r in res["results"]:
        if r["error"] is None and r["fetched"]:
            _log(f"  ✅ {r['code']}: {r['fetched']} 筆 ({r['date_min']}~{r['date_max']}) "
                 f"src={r.get('source')}")
        elif r.get("blocked"):
            # 🔴 不是「抓不到」—— 抓得好好的,是**資料完整性偵測**把它擋下來的。
            _log(f"  🔴 {r['code']}: 【Gate 0 擋下,未寫入】{r['error']}")
        else:
            _log(f"  ⬜ {r['code']}: {r['error']}")
        # 幣別拒絕與上面三態**正交**（一檔可以同時「抓到並寫入」＋「拒絕過換源」）,
        # 故獨立一行,不塞進 if/elif 鏈裡。🟠 而不是 🔴:它沒有造成任何資料遺失。
        if r.get("ccy_refused"):
            _log(f"  🟠 {r['code']}: 【幣別不一致,已拒絕換源;{_ccy_outcome(r)}】"
                 f"{r['ccy_refused']}")
    # 2026-08-28 稽核修正:被擋下的檔**抓得好好的**,舊版把它併進「N 檔抓不到」是說謊。
    _n_blocked = int(res.get("n_blocked") or 0)
    _n_nofetch = int(res["n_fail"]) - _n_blocked
    # 與三行外的 `_n_blocked` 對稱:計數讀 L2 的聚合欄,不在這裡自己數
    # (稽核 minor:上一版加了 `n_ccy_refused` 卻沒有任何生產端讀者,
    #  同一個 commit 寫的唯一呼叫端還是去掃 `results` —— 那個欄位當場變成裝飾品)。
    _n_ccy = int(res.get("n_ccy_refused") or 0)
    _n_ccy_none = _ccy_nothing_written(_ccy_refused)
    _log(f"完成:{res['n_ok']} 檔抓到 → 雲端去重後新增 {res['gs_written']} 筆;"
         f"{_n_nofetch} 檔抓不到;{_n_blocked} 檔被 Gate 0 擋下(抓到了但沒寫入);"
         f"{_n_ccy} 檔幣別不一致拒絕換源"
         f"{f'(其中 {_n_ccy_none} 檔今天完全沒寫入)' if _n_ccy_none else ''}。"
         f" gate_mode={res.get('gate_mode', '?')}")
    _step_summary(res, _blocked, _ccy_refused)
    if res.get("gs_error"):
        _log(f"⚠️ 雲端寫入失敗:{res['gs_error']}(§1 exit 1)")
        return 1
    if res["n_ok"] == 0:
        _log("全數抓不到(§1 exit 1)")
        return 1
    if _blocked:
        # ── 為什麼**被擋也要 exit 1**（2026-08-28 稽核修正）────────────────
        # 舊版只在 `gs_error` 或 `n_ok == 0` 時回 1。一檔被擋、其他正常 → n_ok > 0
        # → exit 0 → **綠燈、零通知**,那檔基金從此每天被擋、每天沒人知道 ——
        # fail-closed 於是退化成 **silent data loss**（本 repo 剛修完它的鏡像:
        # 「假紅讓真錯誤沒人看見」;這裡是「假綠讓真失敗沒人看見」）。
        # 這是**持續性**故障:不處理就每天重演,而 exit code 是這條排程上唯一
        # 會主動通知人的管道（沒有人會去點開綠色 run 的 summary）。
        # ⚠️ 「天天紅會麻痺」的疑慮成立,但答案不是靜音,是:
        #   (a) 訊息直接指名哪一檔、差在哪一天（上面已列）;
        #   (b) `NAV_GATE0_MODE=observe` 是**刻意的**止血開關,改 env 即可,不必改 code;
        #   (c) C1（把「1 天對不上就整檔擋」改成比例/型態門檻）要靠**真實觸發頻率**
        #       才能校準 —— 看得見是校準的前提,所以現在不能靜音。
        _log(f"🔴 {len(_blocked)} 檔被 Gate 0 擋下(資料完整性偵測,**不是抓不到**):"
             f"{'、'.join(r['code'] for r in _blocked)} —— 這幾檔今天沒有寫入任何淨值,"
             f"不處理就會每天重演(§1 exit 1)。"
             f"確認是誤擋 → 設 NAV_GATE0_MODE=observe 先止血,再修來源。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
