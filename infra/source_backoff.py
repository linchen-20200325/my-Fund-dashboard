"""infra/source_backoff.py — 外部來源「失敗後退避」狀態機（L0 Infra）。

v3 憲法 §02：「只快取成功結果；**失敗時退避，不連續轟炸來源**」。
**冷卻秒數與失敗分類的理由全部寫在 `shared/backoff_policy.py`（SSOT），本檔只讀不定義。**

## 一句話

某個 host 剛失敗過 → 冷卻期內 `should_skip()` 回 True，`infra.proxy.fetch_url`
**直接回 `None` 不發請求**，呼叫端的 fallback chain 自然走下一個來源。

## ⚠️ 這**不是** `fx_and_main.py` v18.275 positive-only 快取的反轉

v18.275 刻意「**None 不入 cache → 下次仍會 retry**」，防的是 **None-poisoning**
（一次失敗讓 caller 在整個 TTL 內**拿到錯的答案**）。本模組**不存任何值** ——
狀態只有 `until / kind / cooldown / fails / last_fail` 五個欄位，
結構上沒有地方可以放「上次的失敗值」。兩者是串聯不是競爭，
完整對照表寫在 `shared/backoff_policy.py` docstring，**不在此重述（§2 SSOT）**。

## ⚠️ 這也**不是**既有「單次呼叫內重試」的替代品

既有的 `infra/proxy.py::_RATE_LIMIT_BACKOFF_SEC (2/4/8s)`、
`repositories/policy/_helpers.py`、`snapshot_repository.py`、`fundclear_offshore.py`
的 5xx/429 重試問的是「**再試一下**會不會就好」（秒級，一次呼叫內），
**本次一行都沒動**。本模組問的是「**這一輪還要不要碰**這個來源」（分鐘級，跨呼叫）。
前者額度耗盡 = 後者的輸入訊號。分工表同樣在 `shared/backoff_policy.py`。

## §1 Fail Loud 相容性（這是最容易讀錯的一點）

退避期內回傳的 `None` 與「真的打了但失敗」回傳的 `None` **完全相同** ——
本模組**不儲存任何回傳值**，不存成功值也不存失敗值，只存
「這個 host 何時可以再試」。因此：

- 呼叫端拿不到假資料、拿不到過期值、拿不到 dummy；
- 整條 fallback chain 都在冷卻期時，chain 尾端**照樣 fail loud**
  （回 None / raise / `source: "...all_failed"`，視各 chain 既有行為而定，本模組零介入）。

## §5 可觀測性

三種狀態轉換都有 stdout log（`[source_backoff] ...`）：進入退避 / 跳過一次請求 /
來源恢復。另有 `get_backoff_state()` 回傳結構化快照，供未來的資料診斷頁揭露
（本輪**刻意不接 UI** —— 那會動到畫面，依 §-1.5.4「UI 草稿先行」須先出線框）。

## 逃生門（§1 對偶：退避不可讓資料長期消失）

本模組以 `_BackoffRegistryProxy` 註冊進 `infra.cache._CACHE_REGISTRY`：
- sidebar「全域刷新」→ `global_refresh_all()` → `clear_all_caches()` → **退避全清**；
- ~~Tab5 的快取狀態表走 `get_all_cache_info()` → 會多出一列 `_SOURCE_BACKOFF`
  顯示目前有幾個 host 在冷卻（既有 UI 泛型渲染，**零 UI 改動**）。~~
  ⚠️ **2026-08-31 更正（有意識的更正，不是漏刪 · 決策者：資料與計算組）：
  這句話三處皆不實**，逐一實測：
  (a) **不在 Tab5** —— 全站唯一消費 `get_all_cache_info()` 的畫面在
      `ui/helpers/portfolio/policy_admin_section.py`，屬「📋 保單管理」
      expander 下的「🛠️ 進階工具」（AST 窮舉：production 端僅此 1 個呼叫點，
      且它是 `from fund_fetcher import get_all_cache_info as _gci` 的**別名**）。
  (b) **不是泛型渲染** —— 它是寫死的 f-string，只印「函式數 / entries /
      hit-rate」三個數字。新欄位（含本模組的 `backing_off`）**不會自己長出來**。
  (c) **它根本沒在渲染** —— 那行 caption 寫 `sum(r["size"] …)`，而本模組這一列
      當時只給 `currsize`，於是 `KeyError: 'size'` 被外層 `except Exception: pass`
      吞掉，**production 一次都沒印出來過**。
  **舊表述的用意仍然成立**（把退避狀態掛進 registry 確實讓它「可被觀測」，
  且逃生門那半句是真的、未受影響）；錯的是它宣稱**這件事已經做到了**。
  **現況（2026-08-31 本批之後）**：`_SOURCE_BACKOFF` 這一列已符合
  `infra.cache` 的欄位契約（補上 `size`），該 caption 已能正常渲染並把本列
  計入「函式數 / entries」；但 **`backing_off` 仍然沒有 UI 消費者** ——
  要把「哪些 host 在冷卻」顯示出來屬**欄位增減**，依客戶 2026-08-31 頒布的
  協作介面須**動工前先出線框給客戶審** → **另立一批，不是本批省略**。
  在那之前要看這個清單，請用 `get_all_cache_info()` 直接讀（測試已釘）。

## 執行緒安全

TW PMI 9 源賽跑用 `ThreadPoolExecutor` 並行呼叫 `fetch_url`，故全部狀態存取
都在 `_LOCK` 內。單一 dict + 短臨界區，競爭成本可忽略。
"""
from __future__ import annotations

import threading
import time as _time
from urllib.parse import urlsplit

from shared.backoff_policy import (
    BACKOFF_COOLDOWN_SEC,
    BACKOFF_DEFAULT_KIND,
    BACKOFF_MAX_TRACKED_HOSTS,
    NO_COOLDOWN_KINDS,
)
from infra.cache import register_cache

# ⚠️ 刻意用 monotonic 而非 wall clock：退避是「距離上次失敗過了多久」的**間隔**問題，
# NTP 校時 / 夏令時 / 手動改系統時間都不該讓一個 host 提早解封或永遠鎖死。
# 模組層變數（不是直接呼叫 `_time.monotonic()`）是為了讓測試能注入 fake clock —— 見
# `tests/test_source_backoff.py`；突變測試的「假時鐘 + 呼叫計數器」設計依賴這一點。
_clock = _time.monotonic

# host -> {"until": float, "kind": str, "cooldown": int, "fails": int, "last_fail": float}
_STATE: dict[str, dict] = {}
_LOCK = threading.RLock()


def source_key(url: str) -> str:
    """URL → 退避鍵（host，小寫，不含 port 以外的東西）。

    粒度為 host 的理由見 `shared/backoff_policy.py` docstring 末段。
    無法解析時退回原字串前 80 字 —— **絕不 raise**：退避是輔助機制，
    它自己壞掉不該把取數整條打死（但仍會留下可辨識的 key 供 log 追蹤）。
    """
    try:
        _netloc = urlsplit(str(url)).netloc
        return _netloc.lower() or str(url)[:80]
    except Exception:
        return str(url)[:80]


def cooldown_for(kind: str) -> int:
    """失敗類型 → 冷卻秒數（0 = 不退避）。未知 kind 從寬，退回最短冷卻。"""
    if kind in NO_COOLDOWN_KINDS:
        return 0
    return BACKOFF_COOLDOWN_SEC.get(
        kind, BACKOFF_COOLDOWN_SEC[BACKOFF_DEFAULT_KIND]
    )


def kind_for_status(status: "int | None") -> str:
    """HTTP 狀態碼 → 失敗分類。

    給**不走 `infra.proxy.fetch_url`** 的裸 `requests.get` 路徑共用
    （例：`repositories/fund/fx_and_main.get_latest_fx` 的 open.er-api / Frankfurter
    兩段，v18.273 起刻意直打 proxy 不走 fetch_url）。分類邏輯只有這一份，
    避免同一套規則在兩處各寫一遍後漂移（§2 SSOT）。

    `status is None` = 連線層例外（逾時 / DNS / ConnectionError）→ unreachable。
    """
    if status is None:
        return "unreachable"
    if status == 404:
        return "not_found"
    if status == 407:
        return "proxy_auth"
    if status == 403:
        return "blocked"
    if status == 429:
        return "rate_limited"
    if status >= 400:
        return "server_error"
    return ""          # 2xx/3xx 不是失敗


def should_skip(key: str) -> "tuple[bool, float, str]":
    """這個來源現在該不該跳過？

    Returns:
        (skip, remaining_sec, kind) — skip=False 時 remaining=0.0、kind=""。
    """
    now = _clock()
    with _LOCK:
        ent = _STATE.get(key)
        if not ent:
            return (False, 0.0, "")
        _left = ent["until"] - now
        if _left <= 0:
            # 冷卻期已過 → 立刻移除，讓下一次是乾淨的完整重試
            # （**不保留失敗計數**：不做指數放大，理由見 backoff_policy docstring）
            _STATE.pop(key, None)
            return (False, 0.0, "")
        return (True, _left, ent["kind"])


def record_failure(key: str, kind: str) -> int:
    """記一次來源失敗，回傳實際套用的冷卻秒數（0 = 依分類**刻意不退避**）。

    ⚠️ 回傳 0 有兩種可能，兩種都是**正常**：`not_found` / `proxy_auth`
    （見 `NO_COOLDOWN_KINDS`）。這是分類的結果，不是「查表失敗」。
    """
    _cd = cooldown_for(kind)
    if _cd <= 0:
        print(f"[source_backoff] {key} 失敗（kind={kind}）→ 依分類**不退避**，下次照常嘗試")
        return 0
    now = _clock()
    with _LOCK:
        _prune_locked(now)
        ent = _STATE.get(key) or {"fails": 0}
        _fails = int(ent.get("fails", 0)) + 1
        _STATE[key] = {
            "until": now + _cd,
            "kind": kind,
            "cooldown": _cd,
            "fails": _fails,
            "last_fail": now,
        }
    print(f"[source_backoff] {key} 進入退避 {_cd}s（kind={kind}，連續第 {_fails} 次失敗）")
    return _cd


def record_success(key: str) -> bool:
    """來源成功 → 立刻解除退避。回傳是否真的清掉了一筆（供 log / 測試判讀）。"""
    with _LOCK:
        _had = _STATE.pop(key, None)
    if _had:
        print(f"[source_backoff] {key} 恢復（前次 kind={_had['kind']}）→ 清除退避")
        return True
    return False


def get_backoff_state() -> "list[dict]":
    """目前仍在冷卻中的來源快照（§5 可觀測性；給診斷頁 / 測試用）。

    只回傳**尚未到期**的項目，欄位：source / kind / remaining_sec / cooldown_sec / fails。
    """
    now = _clock()
    out: list[dict] = []
    with _LOCK:
        for _k, _v in _STATE.items():
            _left = _v["until"] - now
            if _left <= 0:
                continue
            out.append({
                "source": _k,
                "kind": _v["kind"],
                "remaining_sec": round(_left, 1),
                "cooldown_sec": _v["cooldown"],
                "fails": _v["fails"],
            })
    out.sort(key=lambda d: -d["remaining_sec"])
    return out


def reset_all() -> int:
    """清空全部退避狀態，回傳清掉幾筆（逃生門 + 測試隔離用）。"""
    with _LOCK:
        _n = len(_STATE)
        _STATE.clear()
    return _n


def _prune_locked(now: float) -> None:
    """記憶體上限維護（必須已持有 `_LOCK`）。

    先清已到期的；仍超過上限就清「最久沒失敗過的」那筆 —— 它最接近到期，
    誤清的代價只是多打那個來源一次（安全方向）。
    """
    _expired = [k for k, v in _STATE.items() if v["until"] <= now]
    for _k in _expired:
        _STATE.pop(_k, None)
    while len(_STATE) >= BACKOFF_MAX_TRACKED_HOSTS:
        _oldest = min(_STATE.items(), key=lambda kv: kv[1]["last_fail"])[0]
        _STATE.pop(_oldest, None)


class _BackoffRegistryProxy:
    """把退避狀態掛進 `_CACHE_REGISTRY`（同 `repositories.fund.fx_and_main._FxCacheProxy` 手法）。

    效果：sidebar「全域刷新」一鍵解除全部退避（逃生門）。

    ~~且 Tab5 快取狀態表自動多一列可觀測 —— **兩者都零 UI 改動**。~~
    ⚠️ **2026-08-31 更正（有意識的更正，不是漏刪 · 決策者：資料與計算組）**：
    這是同一句不實宣稱在本檔的**第二份副本**（另一份在 module docstring
    「逃生門」段，已就地更正 —— 完整三點實測理由寫在那裡，此處不重複）。
    一句話版本：那個畫面**不在 Tab5**、**不是泛型渲染**，而且在本批修好之前
    **根本沒渲染**（`KeyError: 'size'` 被 `except Exception: pass` 吞掉）。
    **逃生門那半句仍然為真、未受影響。**
    📌 **方法教訓**：同一句話當時被寫進**三個載體**（本檔 module docstring、
    本檔這個 class docstring、`infra/cache.py` 的 `uncached_fail` 註解），
    而先前那一輪只更正了 `infra/cache.py` 那一份 —— **更正措辭時只修被點名的
    那個載體，剩下的副本會繼續說謊**。往後更正任何一句宣稱，請對
    「程式註解 / docstring / 測試 docstring / PR 描述 / commit message」
    各掃一遍。
    ⚠️ **本批已知仍未更正的副本**：`tests/test_source_backoff.py` 該測試的
    docstring 仍寫「Tab5 泛型渲染，零 UI 改動」—— 該檔**不在本批的檔案邊界內**，
    故**登記不動**（已寫進本批 PR 描述）。
    """
    __name__ = "_SOURCE_BACKOFF"

    @staticmethod
    def cache_clear() -> None:
        reset_all()

    @staticmethod
    def cache_info() -> dict:
        _live = get_backoff_state()
        return {
            "name": "_SOURCE_BACKOFF",
            # 2026-08-31 欄位契約(infra.cache.CACHE_INFO_REQUIRED_KEYS):
            # entry 數的正式欄位名是 `size`;`currsize` 降為向後相容別名,
            # 保留不刪(**有意識的更正,不是漏刪**;決策者:資料與計算組)。
            # 理由見 infra/cache.py 的「cache_info() 欄位契約」段。
            "size": len(_live),
            "currsize": len(_live),
            "ttl": "per-failure-kind",
            # ⚠️ 本列**刻意不給** hits/misses/uncached_fail —— 退避狀態表不是
            # 「快取命中」的概念,命中率**不適用**;填 0 會是假數字(§1)。
            "backing_off": [d["source"] for d in _live],
        }


register_cache(_BackoffRegistryProxy())
