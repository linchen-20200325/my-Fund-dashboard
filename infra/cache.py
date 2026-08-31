"""infra/cache.py — TTL 快取裝飾器 + 集中註冊機制（v11.0 B-9a 從 fund_fetcher.py 抽出）

為什麼自己造輪子不用 @st.cache_data：
  (1) 本檔屬 L0 Infra（憲法主檔 §8.2 分層表），被全層 import：@st.cache_data 需要
      streamlit 在場，_ttl_cache 則是純標準庫實作、零 streamlit 依賴，
      CLI / pytest / 無 streamlit 的環境同樣可用
      （EX-CACHE-1 條文本身即註明「Fund 端 @_ttl_cache 為 custom 實作不依賴 streamlit」）。
      ⚠️ 憲法**沒有**禁用 st.cache_data —— EX-CACHE-1 明文**允許** L1 條件 import 使用；
      本檔不用它是分層／依賴考量，不是禁令。
      （2026-08-27 更正：原文誤寫「CLAUDE.md §4 全域禁用」，§4 是計算層，無此規定。）
  (2) functools.lru_cache 沒有 TTL，會永久存活 → 盤中 NAV 變動讀不到新值
  (3) 此實作跨 Streamlit rerun 共享（module 不重 import），
      同一 session 多次 rerun 重複呼叫即時 dedupe。

使用：
    from infra.cache import _ttl_cache, register_cache

    @register_cache
    @_ttl_cache(ttl_sec=300, maxsize=32)
    def fetch_something(...): ...

    # UI「🔄 清空快取」按鈕
    from infra.cache import clear_all_caches
    n = clear_all_caches()    # 一鍵清所有註冊的快取

v11.0 分層歸位：本檔屬於 Infrastructure Layer，跨切的快取機制。
向後相容：fund_fetcher.py 仍 re-export _ttl_cache / register_cache / clear_all_caches /
        get_all_cache_info / _CACHE_REGISTRY，既有 caller 零修改。

v19.74 K2：補充 _normalize_moneydj_url_for_cache() 正規化 URL key（防同基金不同 URL 重複抓）。
"""
from __future__ import annotations

import functools as _ft
import time as _time
import re as _re
from collections.abc import MutableMapping as _MutableMapping


def _normalize_moneydj_url_for_cache(url: str) -> str:
    """v19.74 K2：Cache key 正規化 — 不論 tcbbankfund 或 www，都變成 (code, page_type) 唯一識別。

    背景：同一基金代碼可能來自多個 URL（tcbbankfund、www、各家銀行冠名頁）。
    此函式將 URL 正規化為 (code, page_type) tuple key，避免「同基金不同 URL」重複 HTTP 抓取。

    範例：
      - https://...?a=ACDD01&yp=010000  → "fetch_fund|ACDD01|010000"
      - https://...?A=ACDD01&yp=010001  → "fetch_fund|ACDD01|010001"
      - 兩個 URL 共用同一 cache entry，第二次呼叫直接命中快取（K2 效能點）。
    """
    try:
        # 取代碼 &a=CODE 或 &A=CODE（MoneyDJ 大小寫混用）
        m = _re.search(r'[?&][aA]=([A-Z0-9\-]{3,30})', url)
        code = (m.group(1).upper() if m else "").strip()

        # 取頁面類型（yp=010000 = 基本資料；yp=010001 = 績效表等）
        m_pt = _re.search(r'[?&][yY][pP]=([0-9]{6})', url)
        page_type = (m_pt.group(1) if m_pt else "default").strip()

        # 最終 key = "fetch_fund|CODE|PAGE_TYPE"
        return f"fetch_fund|{code}|{page_type}"
    except Exception as e:
        # v19.187 F-MED:malformed URL → fallback 原 URL,留 stderr 軌跡
        import sys as _sys
        print(f'[cache] _normalize_moneydj_url_for_cache fail '
              f'(url={url[:80]!r}): {type(e).__name__}: {e}',
              file=_sys.stderr)
        return url


# ════════════════════════════════════════════════════════════
# v3 憲法 §02「只快取成功結果」— 失敗標記機制（2026-08-31）
# ════════════════════════════════════════════════════════════
# ## 這裡解的是什麼
#
# `_ttl_cache` 原本在 `fn()` 回傳後**無條件** `_cache[key] = (now, result)`。
# 而 L1 fetcher 的慣例是「失敗 → 回空 Series / 空 DataFrame」（§1 不回假資料），
# 於是**一次上游瞬斷會把空值鎖住整個 TTL** —— 使用者看到總經盤面空白，
# 而且**分不出「抓不到」與「真的沒有」**。
#
# ## ⚠️ 為什麼不是「空的就不要快取」（這是本機制存在的全部理由，必讀）
#
# 「空」有兩種，**回傳值本身分不出來**：
#
# | | 例 | 該不該快取 |
# |---|---|---|
# | **抓失敗** | proxy 掛掉 / 逾時 / 403 / 429 → `fetch_url` 回 `None` | ❌ 不該——下次要重試 |
# | **真的沒有** | FRED 回 200 且 `observations: []`；Yahoo 回 200 但該區間無觀測 | ✅ 該——那就是答案 |
#
# 兩者都是「空 DataFrame」。**若讓裝飾器去猜，猜錯哪一邊都是 §1 違憲**：
# 猜成失敗 → 把「真的沒有」變成每次呼叫都重打來源（轟炸）；
# 猜成成功 → 就是現在這個 bug。
#
# → **正解是讓 fetcher 自己講**：它知道自己走的是哪個分支。裝飾器**永遠不猜**，
#   只認 fetcher 明確掛上的標記。沒掛標記 = 照舊快取（既有 `_ttl_cache`
#   使用者行為**零改變**，這也是本機制刻意做成 opt-in 而非預設過濾的原因）。
#
# ## 判準：「HTTP 層有沒有把回應交到手上」
#
# 本次三個 fetcher 一律只標記 **`fetch_url` 回 `None`** 那一支，理由是
# **只有這一支重試才有意義**：
#
# - `r is None`（連不上 / 逾時 / 403 / 429 / 5xx）→ **暫時性**，下次可能就好 → 標記，不快取。
# - HTTP 200 但 JSON 壞掉 / 解析不出東西 → 來源活著而且**明確回答了**，
#   同一個回應再要一次還是同樣結果 → **不標記**（重抓不會變好，只會多打一次來源）。
# - HTTP 200 且解析成功但序列是空的 → **這就是答案**，照常快取。
#
# ## ⚠️ 「這不會造成連續轟炸來源」——**這句話只對四種失敗成立，不是六種**
#
# ~~本機制不會造成「連續轟炸來源」：退避早就有了且住在更下層，所以「失敗不快取
# → 下次再試」的那個再試，會先撞上來源冷卻而**根本不會出門**。~~
#
# ⚠️ **2026-08-31 更正（有意識的更正，不是漏刪 · 日期 2026-08-31 · 決策者：AI 總管）。**
#
# **舊表述對 `unreachable` / `server_error` / `blocked` / `rate_limited` 這四種
# 仍然完全成立**，而且那正是本機制設計時真正在想的情境 —— 它們都有冷卻期
# （60s / 300s / 900s / 1800s），失敗不快取之後的「再試」確實會被 `should_skip()`
# 擋在門口。**這四種的推理沒有一個字要改。**
#
# **錯的是它被寫成一句涵蓋全部六種的全稱句。** `not_found`(404) 與
# `proxy_auth`(407) 依 `shared/backoff_policy.NO_COOLDOWN_KINDS` **冷卻 0 秒**
# —— 對這兩種來說，`_ttl_cache` 是**唯一的節流器**。把它們也標記成「失敗、
# 不入快取」，等於同時拆掉兩層。**實測（5 次 Streamlit rerun，同窗量測）**：
#
# | 失敗 | 修復前 | 一律標記（錯） | 現行 |
# |---|---|---|---|
# | 404 `not_found` | 3 個請求 | **15** | **3** |
# | 407 `proxy_auth` | 1 個請求 | **5**  | **1** |
# | 500 `server_error`（有 300s 冷卻） | 3 | 3 | 3 |
#
# **處置**：`infra/proxy.py::mark_fetch_failed_if_retryable` 依失敗分類決定要不要
# 標記，`NO_COOLDOWN_KINDS` 那兩種**不標記、照舊入快取**。這**不是為它們破例** ——
# 判準一直都是「來源活著且明確回答了 → 那個回答就是答案」（HTTP 200 解析失敗刻意
# 不標記，用的就是這條），而 404 正是最純粹的那種情況。完整理由見該 helper 的
# docstring；六種 kind 逐一守衛見
# `tests/test_ttl_cache_positive_only.py::test_mark_decision_matches_backoff_policy_for_every_fail_kind`。
#
# 兩層仍然是串聯，只是第二層對其中兩種 kind **刻意留白**：
#
#     _ttl_cache（要不要記住這個答案）→ fetch_url → source_backoff（這一輪要不要碰這個來源）
#
# ## 與 `repositories/fund/fx_and_main.py` v18.275 的關係
#
# 同一個精神的兩種寫法。v18.275 的 `_FX_CACHE` 是**手動**快取，寫入點 `_store()`
# 只長在成功分支上，失敗路徑自然不會寫。本機制是把同一件事做進**裝飾器**，
# 讓走 `@_ttl_cache` 的 fetcher 不必各自手刻一份快取。
# **v18.275 一行都沒動，也不需要動。**
#
# ## ⚠️ `.attrs` 傳播：新增回傳 pandas 的 `@_ttl_cache` 函式前必讀
#
# ⚠️ **本段的第一版（2026-08-31 稍早）量錯了環境，已更正 —— 這件事本身值得記。**
# 當時的傳播矩陣（獨立稽核與本組各跑一次）都跑在**沙箱的 pandas 3.0.5** 上，
# 而 `requirements.txt` 宣告的是 **`pandas>=2.3.3,<3.0`** —— CI 與 production
# 用的是 **2.x**。兩組都做了對的動作（實測、不轉述），卻**量在一個不是
# production 的環境上**，於是把 3.x 的語意寫成了不帶版本限定的通則。
# 抓到它的是本節的守衛測試第一次上 CI 就紅 —— 守衛做對了事。
# **下列每一條都在兩個版本各跑一次**（`pandas 2.3.3` 與 `3.0.5`），逐條標明。
#
# ### 一、方法／單元運算 → **兩版都傳播**（這是真正要防的那一種）
#
# `marked.copy()` / `.dropna()` / `.to_frame()` / `.sort_index()` / `.iloc[:1]`
# / `.rename(...)` / `marked * 2` —— **pandas 2.3.3 與 3.0.5 實測皆保留標記**。
#
# ⛔ **所以「升級到 3.x 才有風險」是錯的讀法：風險在目前宣告的 2.x 就存在。**
#    一個 `return fetch_yf_close(t).dropna()` 或 `... / 100` 的衍生函式，
#    在**今天**的 production 上就會繼承標記。
#
# ### 二、二元運算 → **版本相關，這是唯一的差異點**
#
# | 寫法 | pandas 2.3.3 | pandas 3.0.5 |
# |---|---|---|
# | `marked + clean`（被標記的在**左**） | **傳播** | 傳播 |
# | `clean + marked`（被標記的在**右**） | **不傳播** | **傳播** |
#
# 2.x 只從**左運算元**繼承 `.attrs`；3.x 兩邊都繼承。
# **不要靠記憶挑邊** —— 要嘛用第三點的逃生門，要嘛實測。
#
# ### 三、⚠️ 合併類操作 → **看誰是 caller，不是看有沒有出現被標記的那一方**
#
# **本段第一版寫「`combine_first()` 會清掉標記」，那是錯的**，而且錯在
# **安全方向** —— 它會讓作者以為「用了 `combine_first` 就不必叫
# `clear_fetch_failed`」。第一版只量了 `乾淨.combine_first(標記)` 一個方向
# 就寫成通則。兩個方向都量之後，真正的規則是：
#
# **`self`（caller）那一側的 `.attrs` 勝出**，參數側的被丟掉。兩版皆然：
#
# | 寫法 | 2.3.3 | 3.0.5 |
# |---|---|---|
# | `marked.combine_first(clean)` | **保留標記** | **保留標記** |
# | `clean.combine_first(marked)` | 清掉 | 清掉 |
# | `marked.fillna(clean)` | **保留標記** | **保留標記** |
# | `clean.fillna(marked)` | 清掉 | 清掉 |
# | `marked.where(cond, clean)` | **保留標記** | **保留標記** |
# | `marked.update(clean)` 之後的 `marked` | **保留標記** | **保留標記** |
#
# ⛔ **這一條為什麼要命**：`primary.combine_first(fallback)` **正是本 repo
#    fallback chain 的標準寫法**（§2.1 多源備援）。實測那個真實形狀：
#
#      主源失敗（空 Series + 標記）.combine_first(備源成功（真資料）)
#        → 值 = 備源的真資料（**備援確實生效了，答案是對的**）
#        → 但**仍帶著失敗標記** → 這個正確的結果**永遠不會入快取**
#
#    這正是本段要防的那種「不會自己叫的病」的**最典型實例**，
#    而本段的第一版把它漏掉了。
#
# ### 三之二、真正會清掉標記的操作 → 兩版一致
#
# `pd.concat([...])`（兩種順序皆清）、`pd.DataFrame({...})`（兩種順序皆清）
# —— 它們**沒有一個享有特權的 `self`**，故一律不繼承。**2.3.3 與 3.0.5 一致。**
#
# **沒有一致規則可背，只能實測** —— 而「實測」必須**兩個方向都量**，
# 這正是第一版栽的地方。
#
# ### 四、落地往返 → 兩版一致
#
# **`to_parquet` / `read_parquet` 保留 `.attrs`；CSV 不保留**（兩版皆然）。
# 這點特別容易踩到，因為本 repo 的凍結快照走 parquet（§5 可重現性）。
#
# ## 目前為什麼還沒出事
#
# 本組實測全 repo **13 個 `@_ttl_cache` 函式**中，回傳 pandas 的**恰好只有
# 被標記的那 3 個**（`fetch_yf_close` / `fetch_fred` /
# `fetch_defillama_stablecoin_mcap`），其餘 10 個回 `dict` / `float | None`
# （`.attrs` 對它們不存在）。**所以目前沒有任何下游會繼承到標記。**
# （此事與 pandas 版本無關。）
#
# ⛔ **新增回傳 pandas Series / DataFrame 的 `@_ttl_cache` 函式時，
#    必須確認它的值不是從上述三個被標記的上游算出來的。**
#    若是，上游失敗時新函式會**繼承標記 → 永遠不入快取**。
#    ⚠️ 那是**效能病，不是正確性病** —— 它每次都重抓，答案仍然是對的，
#    所以**不會有任何測試變紅、也不會有畫面出錯**，只會安靜地變慢。
#    正因為它不會自己叫，才要寫在這裡。
#    **處理方式**：在新函式回傳前呼叫 `clear_fetch_failed(result)`，
#    明確表態「我這一層的成敗由我自己決定，不繼承上游的」。
#
# 守衛：`tests/test_ttl_cache_positive_only.py`。兩版都成立的部分**硬斷言**；
# 二元運算那一條**依 pandas 版本分支斷言**（2.x 斷言不傳播、3.x 斷言傳播）——
# 刻意**不**寫成「兩邊都過」，因為這組測試存在的價值就是
# **pandas 改語意時要紅**。另以 AST 靜態掃描釘住「回傳 pandas 的
# `@_ttl_cache` 函式只有那 3 個」，新增第 4 個就紅燈。

FETCH_FAILED_ATTR = "fetch_failed"


def mark_fetch_failed(obj, reason: str):
    """標記「這個回傳值來自**失敗的抓取**」→ `@_ttl_cache` 不會快取它。

    用在 fetcher 的失敗分支上，回傳值本身（型別、內容）**完全不變** ——
    標記掛在 pandas 的 `.attrs` 上，呼叫端讀 `.empty` / `len()` 的既有寫法零影響。
    （`.attrs` 已是本 repo 承載 provenance 的既有慣例，§2.2。）

    Args:
        obj: fetcher 的失敗回傳值（pandas Series / DataFrame）。
        reason: 失敗原因，人讀用。

    Returns:
        `obj` 本身（方便 `return mark_fetch_failed(pd.Series(...), "...")` 一行寫完）。

    ⚠️ **不要對「來自快取的物件」呼叫本函式**（2026-08-31 稽核 F6 補）。
    `_ttl_cache` 命中時回傳的是**同一個物件**（不是複本），而 `_cache` 是
    module-level 的 —— Streamlit 各 session 共用。對一個剛從快取拿到的
    Series 呼叫 `mark_fetch_failed()`，會就地改到**所有 session 都看得到的
    那一份**，且下一個 caller 拿到的仍是快取裡的舊值（它已經在快取裡了，
    標記阻止不了「已經入快取」這件事，只會讓它看起來像失敗）。
    本函式的唯一正確用法是**在 fetcher 的失敗分支上、對當場新建的空物件呼叫**。

    Raises:
        TypeError: `obj` 無法承載標記（例如 dict / list）。
            **刻意 fail loud，不做 silent no-op** —— 靜默失敗會讓作者以為自己
            擋住了失敗快取，實際上什麼都沒發生，那正是本次要修的那種假象
            （§-2「沒查證的宣稱比沒有宣稱更危險」）。
            回傳 dict 的 fetcher 請改用 `_daily_cache(cache_if=...)`，
            或在自己的分支裡明確處理。
        ValueError: `reason` 為空（`""` / `None` / 只有空白）。
            ⚠️ **2026-08-31 稽核 F5 補**：在此之前 `mark_fetch_failed(obj, "")`
            是一個**靜默 no-op** —— `.attrs` 確實被寫入 `""`，但 `is_fetch_failed`
            用 `bool()` 判斷，`""` 是 falsy → 回 False → 結果照樣入快取。
            上面那句「刻意 fail loud，不做 silent no-op」因此**對空 reason 為假**，
            而且假在最糟的方向：作者寫了標記、以為擋住了，什麼都沒發生。
            現在改成 raise，讓它與 TypeError 那一支的承諾一致。
    """
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError(
            "mark_fetch_failed: reason 不可為空 —— 空字串會讓 is_fetch_failed() "
            "回 False（bool('') 為 falsy），標記形同沒下，結果照樣入快取。"
            "請寫出是哪個來源、為什麼失敗（§1 fail loud 要求可回溯）。"
        )
    _attrs = getattr(obj, "attrs", None)
    if not isinstance(_attrs, _MutableMapping):
        raise TypeError(
            f"mark_fetch_failed: {type(obj).__name__} 無法承載失敗標記"
            f"（需要 dict-like 的 .attrs，pandas Series/DataFrame 才有）。"
            f"回傳此型別的 fetcher 請改用 _daily_cache(cache_if=...) 或自行處理。"
        )
    _attrs[FETCH_FAILED_ATTR] = str(reason)
    return obj


def clear_fetch_failed(obj):
    """清掉失敗標記 —— 給「值由被標記的上游算出來、但本層自有成敗判斷」的函式用。

    存在理由見本檔上方「`.attrs` 傳播」段：pandas 的算術運算會把上游的標記
    傳染給結果（`乾淨 + 被標記` → 帶標記），若新函式不表態就會**繼承一個
    不屬於自己的失敗**，導致它永遠不入快取（安靜的效能病，不會有測試變紅）。

    無 `.attrs` 的物件直接原樣回傳（no-op）—— 這裡**不** fail loud，
    因為「本來就沒有標記可清」與「清乾淨了」對呼叫端是同一件事；
    `mark_fetch_failed` 會 raise 是因為那裡靜默失敗會產生**假的安全感**，
    兩者不對稱是刻意的。

    Returns:
        `obj` 本身（方便 `return clear_fetch_failed(out)` 一行寫完）。
    """
    _attrs = getattr(obj, "attrs", None)
    if isinstance(_attrs, _MutableMapping):
        _attrs.pop(FETCH_FAILED_ATTR, None)
    return obj


def is_fetch_failed(obj) -> bool:
    """這個回傳值有沒有被 `mark_fetch_failed` 標記過？

    無 `.attrs` 的物件（dict / list / int / None …）一律回 False ——
    **未標記 = 視為成功**，既有 `_ttl_cache` 使用者行為不變。
    """
    try:
        _attrs = getattr(obj, "attrs", None)
        if not isinstance(_attrs, _MutableMapping):
            return False
        return bool(_attrs.get(FETCH_FAILED_ATTR))
    except Exception:
        # 標記機制自己壞掉不該把取數打死 → 從寬當成功（維持既有行為）
        return False


def _ttl_cache(ttl_sec: int, maxsize: int = 128, key_fn=None):
    """TTL + LRU 兩層快取裝飾器。

    cache key 由 (args, sorted kwargs) 組成；無法 hash 的引數（list/dict）跳過快取直走原 fn。
    v19.74 K2：新增 key_fn 參數，可自訂 key 生成邏輯（用於 URL normalize 等特殊場景）。

    2026-08-31（v3 §02「只快取成功結果」）：被 `mark_fetch_failed()` 標記過的結果
    **不入快取**，下次呼叫會真的重試（重試是否出門由 `infra.source_backoff` 決定，
    見上方 module 註解）。未標記者照舊快取 —— 既有使用者零行為改變。

    Wrapper 暴露：cache_clear() / cache_info()
        → {size, maxsize, ttl_sec, hits, misses, uncached_fail}
    """
    def decorator(fn):
        _cache: dict = {}
        _stats = {"hits": 0, "misses": 0, "uncached_fail": 0}

        @_ft.wraps(fn)
        def wrapper(*args, **kwargs):
            # v19.74 K2：若有 key_fn，用它生成 cache key（否則用預設 args/kwargs）
            if key_fn is not None and len(args) > 0:
                try:
                    key = key_fn(args[0])  # 通常 args[0] 是 URL 或主要參數
                except Exception as e:
                    # v19.187 F-MED:key_fn 失敗 → 放棄快取(不影響業務),留 stderr
                    import sys as _sys
                    print(f'[cache] key_fn fail in {fn.__name__} '
                          f'(arg0={str(args[0])[:60]!r}): '
                          f'{type(e).__name__}: {e}', file=_sys.stderr)
                    key = None
            else:
                # 防 unhashable args/kwargs（如 list/dict 引數）→ 跳過快取直走原 fn
                try:
                    key = (args, tuple(sorted(kwargs.items())))
                    hash(key)
                except TypeError:
                    return fn(*args, **kwargs)

            if key is None:
                return fn(*args, **kwargs)

            now = _time.time()
            hit = _cache.get(key)
            if hit and (now - hit[0]) < ttl_sec:
                _stats["hits"] += 1
                return hit[1]
            _stats["misses"] += 1
            result = fn(*args, **kwargs)
            # v3 §02「只快取成功結果」：fetcher 明說這次是抓失敗 → 不入快取，
            # 下次呼叫真的重試（是否出門由 infra.source_backoff 決定）。
            # ⚠️ 這裡**不判斷「空不空」** —— 空有兩種意思，裝飾器沒有資訊分辨，
            #    猜錯任一邊都違憲。理由見本檔上方 module 註解。
            if is_fetch_failed(result):
                _stats["uncached_fail"] += 1
                return result
            _cache[key] = (now, result)
            # LRU 防呆：超過 maxsize 砍最舊
            if len(_cache) > maxsize:
                oldest_key = min(_cache.items(), key=lambda kv: kv[1][0])[0]
                _cache.pop(oldest_key, None)
            return result

        def _clear():
            _cache.clear()
            _stats["hits"] = 0
            _stats["misses"] = 0
            _stats["uncached_fail"] = 0

        wrapper.cache_clear = _clear   # type: ignore[attr-defined]
        wrapper.cache_info = lambda: {   # type: ignore[attr-defined]
            # `name` 由生產者自己給(2026-08-31 欄位契約 CACHE_INFO_REQUIRED_KEYS)。
            # 過去只靠 get_all_cache_info() 事後注入 → 直接呼叫 fn.cache_info()
            # 的 caller 拿到的列是不完整的。
            "name": fn.__name__,
            "size": len(_cache), "maxsize": maxsize, "ttl_sec": ttl_sec,
            "hits": _stats["hits"], "misses": _stats["misses"],
            # 「這個 fetcher 因為抓失敗而沒被快取幾次」——§5 可觀測性。
            # ~~Tab5 快取狀態表走 get_all_cache_info() 泛型渲染，零 UI 改動。~~
            # ⚠️ **2026-08-31 更正（有意識的更正，不是漏刪 · 決策者：AI 總管）：
            #    這句兩處皆不實。** 實測：(a) `uncached_fail` 在 `ui/` 與 `app.py`
            #    **0 命中**；(b) 全站唯一消費 `get_all_cache_info()` 的畫面在
            #    `ui/helpers/portfolio/policy_admin_section.py`（**「📋 保單管理」，
            #    不是 Tab5**），而且它是寫死的 f-string，只加總 size/hits/misses ——
            #    **沒有泛型渲染，新欄位不會自己長出來。**
            #    **舊表述的用意仍然成立**（本欄確實是為了讓失敗次數可被看見），
            #    錯的是它宣稱這件事**已經做到了**。
            #    **現況：本欄目前在 UI 沒有任何消費者，production 尚無可觀測入口。**
            #    要接進「⑤ 參考 / 診斷」屬**欄位增減**，依客戶 2026-08-31 頒布的
            #    協作介面須**動工前先出 HTML 線框給客戶審** → **另立一批，不是本批省略**。
            #    在那之前，要看這個數字請用 `get_all_cache_info()` 直接讀（測試已釘）。
            "uncached_fail": _stats["uncached_fail"],
        }
        wrapper._cache_dict = _cache   # type: ignore[attr-defined]   # for tests
        return wrapper

    return decorator


# ════════════════════════════════════════════════════════════
# cache_info() 欄位契約(SSOT,2026-08-31)
# ════════════════════════════════════════════════════════════
# 為什麼要有這段:`cache_info()` 有 **4 個生產者** —— `_ttl_cache` /
# `_daily_cache`(本檔)、`infra.source_backoff._BackoffRegistryProxy`、
# `repositories.fund.fx_and_main._FxCacheProxy` —— 過去各寫各的欄位名,
# 光是「entry 數」就有兩個名字:`size`(_ttl_cache)與 `currsize`(其餘三個)。
# 後果是實測到的真缺陷:唯一的 production 消費者
# (`ui/helpers/portfolio/policy_admin_section.py` 的「🔋 快取狀態」caption)
# 寫 `sum(r["size"] for r in rows)`,一撞到 `currsize` 的列就 `KeyError: 'size'`,
# 再被外層 `except Exception: pass` 吞掉 → **那行 caption 從未在 production 印出來過**。
#
# 契約:
#   ① 必備欄位 `CACHE_INFO_REQUIRED_KEYS` —— **每一列都要有**,缺 = 違憲。
#   ② 統計欄位 `CACHE_INFO_STAT_KEYS` —— **全有或全無**。
#      ⚠️ **缺席代表「這個快取本質上沒有命中率」,不是「0 次命中」。**
#      proxy 型快取(`_FX_CACHE` / `_SOURCE_BACKOFF`)只是把一個 raw dict 包成
#      registry 介面,並沒有攔截呼叫,命中/未命中無從談起 —— 為了湊格式填 0
#      就是 §1 禁止的假數字。**消費端請用 `"hits" in row` 判斷,不要用
#      `row.get("hits", 0)`** —— 後者會把「不適用」偽裝成「0」。
#   ③ 其餘欄位(`maxsize` / `ttl_sec` / `ttl` / `backing_off`)由各生產者自訂。
#
# 為什麼 `ttl` **不列入必備**:它在四個生產者之間本來就不是同一種東西
# (`_ttl_cache` 給秒數 300;`_daily_cache` 給 `"daily-reset"`;
#  `_SOURCE_BACKOFF` 給 `"per-failure-kind"`;`_FX_CACHE` 給 float 秒數)。
# 硬塞進同一個 key 只是把「不同的東西」寫成「同一個欄位」,屬湊格式;
# 且 `_daily_cache` 的 `"daily-reset"` 與 `TTL_TODAY` marker 已有既存對齊測試。
# → **本批刻意不動 ttl**,只把「entry 數」這個真的同義的欄位收斂成一個名字。
CACHE_INFO_REQUIRED_KEYS: tuple[str, ...] = ("name", "size")
CACHE_INFO_STAT_KEYS: tuple[str, ...] = ("hits", "misses", "uncached_fail")


# 集中註冊：UI「🔄 清空快取」按鈕一鍵清所有快取
_CACHE_REGISTRY: list = []   # list of cached function wrappers


def register_cache(fn):
    """把 _ttl_cache 包過的函式註冊進去，clear_all_caches() 一次清。"""
    _CACHE_REGISTRY.append(fn)
    return fn


_ST_CACHE_REGISTRY: list = []   # @st.cache_data fetcher(EX-CACHE-1)供 global_refresh 清


def register_st_cache(fn):
    """把 `@st.cache_data` 包過的 L1 fetcher 註冊進來,`global_refresh_all()` 一併 `.clear()`。

    v19.374 B1(分層歸位):消除原本 infra(L0)→ repositories(L1)的**上行 import**
    (§8.2 硬規則 3 違憲)。改由 L1 fetcher 於自身 import 時向本 L0 registry **下行**註冊
    (repositories → infra,合規),infra.cache 不再反向 import repositories。
    `@st.cache_data` wrapper 具 `.clear()`;用法:`@register_st_cache` 疊在 `@st.cache_data` 之上。
    """
    _ST_CACHE_REGISTRY.append(fn)
    return fn


# ── v19.250 R20:日 TTL 快取(保存當日,隔日自動 miss 重抓)──────────
def _daily_cache(fn=None, *, today_fn=None, cache_if=None):
    """日 TTL 快取裝飾器:保存當日(TW UTC+8 timezone),隔日午夜自動 miss → 重抓。

    **設計理由**(v19.250 R20):30min TTL 對「月更新源頭」(MoneyDJ 持股 / wb07 風險 /
    wb05 配息等)過於激進,當日無謂重抓浪費 IO + MoneyDJ 流量。改成日 cache 後:
    - 同日多次呼叫:cache hit,0 HTTP
    - 隔日 00:00 TW(UTC+8):自動 miss → 重抓最新版本

    **v19.253 R23 失敗結果不入 cache**(防 cache 鎖死):
    R20 原版無條件 `_cache[key] = result`,若當日第一次呼叫遇上游 403 / 暫時網路錯誤
    回 empty / failure dict → 整天 caller 都拿到該 cached failure → user 看見「全域刷新」
    也救不回(因為 GC 規則只清「前一日」entry)。R23 加 `cache_if` 預設過濾:
    - dict 含 `"source": "...all_failed"` 或 empty `{}` → 不入 cache(下次重試)
    - Series / list 為空 → 不入 cache
    - 其他(包含有 sector_alloc / top_holdings 等真實資料的 dict)→ 入 cache

    **SSOT 對齊**:與 `_ttl_cache` 對稱 — 暴露 `cache_clear()` / `cache_info()`;
    透過 `@register_cache` 接入 `_CACHE_REGISTRY`,UI「全域刷新」一鍵清。

    Args:
        today_fn: 可選 date provider(test 用,預設 TW UTC+8 today ISO string)。
        cache_if: 可選 predicate(result) -> bool,True 才入 cache。預設過濾失敗結果。

    Memory hygiene:今日 key 變化(隔日 first call)會把所有舊日 entry GC 掉,
    無需手動清,記憶體用量 bounded(N=當日 cached call 數)。
    """
    import datetime as _dt

    def _default_today():
        _tw_tz = _dt.timezone(_dt.timedelta(hours=8))
        return _dt.datetime.now(_tw_tz).date().isoformat()

    def _default_cache_if(result):
        """預設過濾:失敗 / 空結果不入 cache,讓下次呼叫重試。"""
        if result is None:
            return False
        # dict 系列:empty 或含 all_failed marker 都不存
        if isinstance(result, dict):
            if not result:
                return False
            _src = result.get("source", "")
            if isinstance(_src, str) and "all_failed" in _src:
                return False
            return True
        # Series / list / tuple 空集合不存
        if hasattr(result, "__len__"):
            try:
                if len(result) == 0:
                    return False
            except Exception:
                pass
        return True

    _today_provider = today_fn or _default_today
    _cache_predicate = cache_if or _default_cache_if

    def decorator(_fn):
        _cache: dict = {}
        _stats = {"hits": 0, "misses": 0, "uncached_fail": 0}

        @_ft.wraps(_fn)
        def wrapper(*args, **kwargs):
            today = _today_provider()
            try:
                key = (today, args, tuple(sorted(kwargs.items())))
                hash(key)
            except TypeError:
                # 不可 hash 引數 → 跳過快取(對齊 _ttl_cache 行為)
                return _fn(*args, **kwargs)

            if key in _cache:
                _stats["hits"] += 1
                return _cache[key]

            # GC 舊日 entry — 隔日首次呼叫自動清前一日 cache
            _stale = [k for k in _cache if k[0] != today]
            for _k in _stale:
                del _cache[_k]

            _stats["misses"] += 1
            result = _fn(*args, **kwargs)
            # v19.253 R23:只 cache 成功結果,失敗下次重試(防 cache 鎖死)
            if _cache_predicate(result):
                _cache[key] = result
            else:
                _stats["uncached_fail"] += 1
            return result

        wrapper.cache_clear = lambda: _cache.clear()
        wrapper.cache_info = lambda: {
            "name": _fn.__name__,
            # 2026-08-31 欄位契約:entry 數的正式欄位名是 `size`(對齊 _ttl_cache)。
            "size": len(_cache),
            # ~~"currsize": len(_cache),~~ → 降為**向後相容別名**,保留不刪。
            # **有意識的更正,不是漏刪**(日期 2026-08-31;決策者:資料與計算組)。
            # **舊表述的理由仍然成立**:`currsize` 是照 `functools.lru_cache`
            # 的命名慣例取的,對熟悉 stdlib 的讀者最直覺。
            # **被權衡掉的原因**:這個介面的消費者是**我們自己的 UI**,不是
            # lru_cache 的使用者;而兩個名字並存已經實際造成 production 缺陷
            # (見上方欄位契約段)。同一件事只能有一個名字(§2.1 SSOT)。
            # **為什麼別名不當場刪**:`tests/test_daily_cache.py`、
            # `tests/test_daily_cache_skip_failure.py`、`tests/test_source_backoff.py`
            # 仍讀 `currsize`,而那三個檔**不在本批的檔案邊界內**。
            # **移除條件**:那三個檔遷到 `size` 之後即可刪本行(屆時屬收尾義務)。
            "currsize": len(_cache),
            "ttl": "daily-reset",
            **_stats,
        }
        return wrapper

    # Support both @_daily_cache and @_daily_cache(today_fn=...)
    if fn is not None and callable(fn):
        return decorator(fn)
    return decorator


def clear_all_caches() -> int:
    """清空所有註冊的 TTL cache。回傳清空的函式數量。"""
    for fn in _CACHE_REGISTRY:
        try:
            fn.cache_clear()
        except Exception as e:
            # v19.187 F-MED:單一 cache clear 失敗不該中斷其他,留 stderr
            import sys as _sys
            print(f'[cache] clear_all_caches: '
                  f'{getattr(fn, "__name__", "?")} cache_clear fail: '
                  f'{type(e).__name__}: {e}', file=_sys.stderr)
    return len(_CACHE_REGISTRY)


def clear_caches_by_names(names) -> int:
    """v19.57 C1：精準清指定函式名稱的 TTL cache（不影響其他 Tab）。

    參數 names: 可迭代的函式名稱集合 (e.g. {"fetch_fred", "fetch_yf_close"})。
    回傳實際命中並清掉的函式數量。
    """
    _wanted = set(names or [])
    if not _wanted:
        return 0
    _hit = 0
    for fn in _CACHE_REGISTRY:
        try:
            if getattr(fn, "__name__", "") in _wanted:
                fn.cache_clear()
                _hit += 1
        except Exception as e:
            # v19.187 F-MED:單一 cache clear 失敗不影響其他,留 stderr
            import sys as _sys
            print(f'[cache] clear_caches_by_names: '
                  f'{getattr(fn, "__name__", "?")} fail: '
                  f'{type(e).__name__}: {e}', file=_sys.stderr)
    return _hit


def get_all_cache_info() -> list[dict]:
    """回傳所有註冊快取的狀態，給 UI 顯示「cache hit 率」/「entries」用。

    每一列都遵守本檔上方的 **cache_info() 欄位契約**：
    - 必備 `CACHE_INFO_REQUIRED_KEYS`（`name` / `size`）—— 一定有；
    - 統計 `CACHE_INFO_STAT_KEYS`（`hits` / `misses` / `uncached_fail`）
      **全有或全無**，**缺席 = 「不適用」，不是 0 次命中**。
      消費端請用 `"hits" in row` 判斷，不要用 `row.get("hits", 0)`。
    契約由 `tests/test_cache_info_contract.py` 強制（新增第 5 個生產者卻不照
    契約 → CI 紅燈）。
    ⚠️ **上面這句在 2026-08-31 當天只對 `size` 成立，對 `name` 不成立**
    （**有意識的更正，不是漏刪**；決策者：**#746 回修組**，依獨立紅隊實測）。
    原因就在下面那行 `info["name"] = fn.__name__` —— **無條件事後回填**，
    於是守衛拿到的列必然有 `name`，看不到「生產者沒吐 `name`」這種違約。
    實測：拔掉 `_ttl_cache` 的 `"name"`、或註冊一個「有 `size` 沒 `name`」的
    生產者，當時 16 條守衛**全綠**。
    **舊表述保留不刪、也不劃線**：它描述的機制（契約由測試強制）本身是對的，
    錯的是它的**涵蓋範圍**；劃掉它反而會變成主張「契約沒有測試在守」，那是另一個
    假宣稱。已改為由 `TestRawProducerContract` 對**回填前的原始輸出**斷言，
    兩個必備欄位自此都真的被守住。
    """
    out = []
    for fn in _CACHE_REGISTRY:
        try:
            info = fn.cache_info()
            info["name"] = fn.__name__
            out.append(info)
        except Exception as e:
            # v19.187 F-MED:cache info 取不到不該擋整個 UI,留 stderr
            import sys as _sys
            print(f'[cache] get_all_cache_info: '
                  f'{getattr(fn, "__name__", "?")} fail: '
                  f'{type(e).__name__}: {e}', file=_sys.stderr)
    return out


# ════════════════════════════════════════════════════════════
# v19.59 C2：Sidebar 全域刷新總開關 — disk cache + 統一入口
# ════════════════════════════════════════════════════════════

# 跨 Tab session_state 殘留 keys（保留 OAuth/sheet 核心，避免用戶被踢出）
_GLOBAL_REFRESH_SESSION_KEYS = (
    # Tab1 總經
    "_radar_v1921_top", "_tp_v1948_top", "indicators",
    "phase_info", "news_items", "systemic_risk_data",
    "_fred_sources", "macro_done", "macro_last_update",
    # Tab2 / Tab3 基金 / 組合
    "_t3_cur_sheet_title", "_t3_groups_cache",
    # Tab5 健診
    "fund_grp_health_codes",
)

# 永遠保留的 session keys（OAuth/sheet 核心，砍了用戶要重登入）
_GLOBAL_REFRESH_KEEP_KEYS = frozenset({
    "gsheet_tokens", "policy_sheet_id", "active_policy_id",
})


def clear_disk_cache() -> dict:
    """v19.59 C2：清 /tmp/fund_cache 落地檔（NAV/DIV/META CSV+JSON）+ 記憶體 snapshot。

    嚴禁清 data_cache/ — 那是上游 cron 排程的歷史資料倉
    （SPX/TWII/VIX/FRED 8 series parquet），砍了要等下個 cron 才補。

    回傳 dict：files_removed / snapshot_cleared / dir_existed。
    """
    _stat = {"files_removed": 0, "snapshot_cleared": 0, "dir_existed": False}
    if _os.path.isdir(_CACHE_DIR):
        _stat["dir_existed"] = True
        try:
            for _fn in _os.listdir(_CACHE_DIR):
                if not (_fn.endswith(".csv") or _fn.endswith(".json")):
                    continue
                try:
                    _os.remove(_os.path.join(_CACHE_DIR, _fn))
                    _stat["files_removed"] += 1
                except Exception as e:
                    # v19.187 F-MED:單檔刪失敗(權限/併發)不擋全部
                    import sys as _sys
                    print(f'[cache] clear_disk_cache: rm {_fn} fail: '
                          f'{type(e).__name__}: {e}', file=_sys.stderr)
        except Exception as e:
            # v19.187 F-MED:listdir 失敗(權限)
            import sys as _sys
            print(f'[cache] clear_disk_cache: listdir({_CACHE_DIR}) fail: '
                  f'{type(e).__name__}: {e}', file=_sys.stderr)
    if _FUND_SNAPSHOT:
        _stat["snapshot_cleared"] = len(_FUND_SNAPSHOT)
        _FUND_SNAPSHOT.clear()
    return _stat


def global_refresh_all(session_state=None) -> dict:
    """v19.59 C2：Sidebar 全域刷新總開關統一入口。

    4 層清理：
      ① TTL caches（_CACHE_REGISTRY 全部）
      ② hot_money @st.cache_data（fetch_foreign_flow_series / fetch_usdtwd_series）
      ③ Disk cache（/tmp/fund_cache 落地 + _FUND_SNAPSHOT 記憶體最後防線）
      ④ Session state 跨 Tab 殘留（保留 OAuth/sheet 核心 keys）

    嚴禁清 data_cache/ — 上游 cron 歷史資料倉。

    回傳 dict：ttl_cleared / st_cache_cleared / disk_files_removed /
              snapshot_cleared / session_keys_popped。
    """
    _stat = {
        "ttl_cleared": 0, "st_cache_cleared": 0,
        "disk_files_removed": 0, "snapshot_cleared": 0,
        "session_keys_popped": 0,
    }
    import sys as _sys
    try:
        _stat["ttl_cleared"] = clear_all_caches()
    except Exception as e:
        # v19.187 F-MED:layer 1 失敗仍要嘗試 layer 2-4
        print(f'[cache] global_refresh_all L1 ttl fail: '
              f'{type(e).__name__}: {e}', file=_sys.stderr)
    # v19.374 B1:改走 _ST_CACHE_REGISTRY(L1 fetcher import 時下行註冊),消除原
    # infra(L0)→ repositories(L1)上行 import(§8.2 硬規則 3)。未被 import 的 fetcher
    # 其 cache 本就是空的,不在 registry = 無需清,語意等價。
    for _fn in list(_ST_CACHE_REGISTRY):
        try:
            _fn.clear()
            _stat["st_cache_cleared"] += 1
        except Exception as e:
            # v19.187 F-MED:單一 st.cache_data clear fail 不中斷其他
            print(f'[cache] global_refresh_all L2 '
                  f'{getattr(_fn, "__name__", "?")} clear fail: '
                  f'{type(e).__name__}: {e}', file=_sys.stderr)
    try:
        _disk = clear_disk_cache()
        _stat["disk_files_removed"] = _disk.get("files_removed", 0)
        _stat["snapshot_cleared"] = _disk.get("snapshot_cleared", 0)
    except Exception as e:
        # v19.187 F-MED:disk cache fail
        print(f'[cache] global_refresh_all L3 disk fail: '
              f'{type(e).__name__}: {e}', file=_sys.stderr)
    if session_state is not None:
        for _k in _GLOBAL_REFRESH_SESSION_KEYS:
            if _k in _GLOBAL_REFRESH_KEEP_KEYS:
                continue
            try:
                if _k in session_state:
                    session_state.pop(_k, None)
                    _stat["session_keys_popped"] += 1
            except Exception as e:
                # v19.187 F-MED:單一 session key pop fail
                print(f'[cache] global_refresh_all L4 pop {_k} fail: '
                      f'{type(e).__name__}: {e}', file=_sys.stderr)
    return _stat


# ════════════════════════════════════════════════════════════
# v11.0 B-9b-1：Disk cache helpers（從 fund_fetcher.py 抽出）
# 基金 NAV / 配息 / metadata 的本地 CSV+JSON 快取
# 環境自適應路徑（Colab → /content/fund_cache; 其他 → /tmp/fund_cache）
# pandas 採 lazy import（infra 層避免硬依賴 pandas）
# ════════════════════════════════════════════════════════════
import os as _os
import datetime as _datetime
import json as _json_mod

# ── 本地快取路徑（環境自適應：Colab → /content, Streamlit Cloud → /tmp）──
_CACHE_DIR = "/content/fund_cache" if _os.path.isdir("/content") else "/tmp/fund_cache"

# ── 記憶體快照：網路與檔案快取均失效時的最後一道防線（同 macro_engine._INDICATOR_SNAPSHOT）
_FUND_SNAPSHOT: dict = {}  # key=code.upper(), value=完整 result dict（不含 series）


def _cache_path(code: str, dtype: str) -> str:
    _os.makedirs(_CACHE_DIR, exist_ok=True)
    return f"{_CACHE_DIR}/{code.upper()}_{dtype}.csv"


def _cache_load_nav(code: str, max_age_hours: int = 20):
    """
    讀取本地 NAV 快取。
    若快取不存在或超過 max_age_hours，回傳 None（需重新抓取）。
    """
    fp = _cache_path(code, "nav")
    if not _os.path.exists(fp):
        return None
    try:
        import pandas as _pd  # lazy import: infra/ 避免硬依賴 pandas
        mtime = _os.path.getmtime(fp)
        age_h = (_datetime.datetime.now().timestamp() - mtime) / 3600
        if age_h > max_age_hours:
            return None
        df = _pd.read_csv(fp, index_col=0, parse_dates=True)
        if df.empty or len(df) < 5:
            return None
        s = df.iloc[:, 0].dropna()
        s.index = _pd.to_datetime(s.index)
        print(f"[cache] ✅ {code} NAV 快取命中 {len(s)} 筆（{age_h:.1f}小時前）")
        return s.sort_index()
    except Exception as e:
        print(f"[cache] load_nav 失敗: {e}")
        return None


def _cache_save_nav(code: str, s):
    """儲存 NAV 序列到本地快取（pandas.Series）"""
    if s is None or len(s) < 5:
        return
    try:
        fp = _cache_path(code, "nav")
        s.to_csv(fp, header=["nav"])
        print(f"[cache] 💾 {code} NAV {len(s)} 筆已快取")
    except Exception as e:
        print(f"[cache] save_nav 失敗: {e}")


def _cache_load_div(code: str, max_age_hours: int = 48):
    """讀取配息快取"""
    fp = _cache_path(code, "div")
    if not _os.path.exists(fp):
        return None
    try:
        age_h = (_datetime.datetime.now().timestamp() - _os.path.getmtime(fp)) / 3600
        if age_h > max_age_hours:
            return None
        with open(fp, "r", encoding="utf-8") as fh:
            data = _json_mod.load(fh)
        if data:
            print(f"[cache] ✅ {code} 配息快取命中 {len(data)} 筆")
            return data
    except Exception as e:
        print(f"[cache] load_div 失敗: {e}")
    return None


def _cache_save_div(code: str, divs: list):
    """儲存配息資料到本地快取"""
    if not divs:
        return
    try:
        fp = _cache_path(code, "div")
        with open(fp, "w", encoding="utf-8") as fh:
            _json_mod.dump(divs, fh, ensure_ascii=False, default=str)
        print(f"[cache] 💾 {code} 配息 {len(divs)} 筆已快取")
    except Exception as e:
        print(f"[cache] save_div 失敗: {e}")


def _cache_load_meta(code: str, max_age_hours: int = 48):
    """讀取基金基本資料快取"""
    fp = _cache_path(code, "meta")
    if not _os.path.exists(fp):
        return None
    try:
        age_h = (_datetime.datetime.now().timestamp() - _os.path.getmtime(fp)) / 3600
        if age_h > max_age_hours:
            return None
        with open(fp, "r", encoding="utf-8") as fh:
            data = _json_mod.load(fh)
        if data.get("fund_name"):
            print(f"[cache] ✅ {code} 基本資料快取命中: {data['fund_name'][:20]}")
            return data
    except Exception as e:
        print(f"[cache] load_meta 失敗: {e}")
    return None


def _cache_save_meta(code: str, meta: dict):
    """儲存基金基本資料到快取"""
    save_keys = ["fund_name", "currency", "risk_level", "dividend_freq",
                 "fund_scale", "category", "fund_region", "nav_latest",
                 "nav_date", "year_high_nav", "year_low_nav",
                 "moneydj_div_yield", "mgmt_fee"]
    try:
        fp = _cache_path(code, "meta")
        slim = {k: meta.get(k) for k in save_keys if meta.get(k) is not None}
        with open(fp, "w", encoding="utf-8") as fh:
            _json_mod.dump(slim, fh, ensure_ascii=False, default=str)
    except Exception as e:
        print(f"[cache] save_meta 失敗: {e}")
