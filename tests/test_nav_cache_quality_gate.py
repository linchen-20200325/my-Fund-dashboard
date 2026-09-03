"""cache/nav 讀取端品質閘 — 2026-08-27。

## 修的是什麼

`repositories/fund/sources._src_cache_files` 是 `fetch_nav` 的最後一道 fallback
(Streamlit Cloud 美國 IP 被上游封鎖時,唯一還吐得出 NAV 的來源),但它原本
**只檢查檔案存在 + `history` 非空**就回傳 —— 不看筆數、不看密度、不看年齡、
也不跑 `validate_fund_nav`。

而同一條 chain 的其他路徑都有閘:
  - live(`fetch_nav` 迴圈內)      → `len >= 10` **且** `validate_fund_nav()`
  - 長歷史(`nav_metrics` 多處)    → `len >= 50` / `>= 100`
  - 下游(`fx_and_main.fetch_fund_by_key`)→ `len >= 20` 才收

實測 `cache/nav/TLZF9.json`(該目錄唯一的檔):**10 點橫跨 14.43 年**、最大空窗
**2,029 天**、密度 0.69 點/年、`source="cache_only"`。這種序列被下游拿去算
Sharpe / σ / 最大回撤(年化一律 ×√252、假設「每點 = 1 交易日」)= 假精確。

## 閘的形狀(刻意不對稱)

- **Tier A 擋**:筆數 < `NAV_CACHE_MIN_POINTS` 或 schema 違反 → 回空。
  這**不是新標準**,是補回 live 分支同一把尺;且下游本來就會丟掉 <10 點的序列,
  可用性零損失。
- **Tier B 不擋,標註疑義**:密度 / 空窗 / 新鮮度 → 序列照回,掛
  `attrs["supports_annualized"]=False`。⚠️ 刻意不擋 —— 擋掉會把「數字可疑」
  變成「完全沒資料」,對這條最後的 fallback 是更糟的失效模式(§1 是讓它誠實,
  不是讓它消失)。
"""
from __future__ import annotations

import ast
import datetime as dt
import json
import re
from pathlib import Path

import pandas as pd
import pytest

from repositories.fund.sources import _src_cache_files
from shared.data_quality import (
    NAV_CACHE_MIN_POINTS,
    QUALITY_NAV_SPARSE,
    QUALITY_NAV_TOO_FEW,
    QUALITY_OK,
    assess_nav_cache_quality,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CACHE_DIR = _REPO_ROOT / "cache" / "nav"
_NOW = dt.datetime(2026, 8, 27, tzinfo=dt.timezone.utc)


def _mk(dates: list[str], navs: list[float] | None = None) -> pd.Series:
    navs = navs or [10.0 + i * 0.01 for i in range(len(dates))]
    s = pd.Series(navs, index=pd.to_datetime(dates), dtype=float).sort_index()
    s.attrs["source"] = "GitHubActions:cache/nav/TEST.json"
    s.attrs["fetched_at"] = _NOW.isoformat()
    return s


def _dense(n: int, end: str = "2026-08-26") -> pd.Series:
    """n 個連續日曆日(密度足夠、不過期)。

    ⚠️ 預設 `end` 寫死是**刻意的**,而且**只對注入時鐘的測試安全**:本檔 L0 區段
    每一條都傳 `now=_NOW`(=2026-08-27),`end` 與 `_NOW` 是**成對凍結**的參考時點
    (§5 可重現性)。**走真實時鐘的 `test_wired_*` 一律不得用它當「健康」種子** ——
    那會隨時間自然腐爛,見 `_healthy_history` 與本檔末的兩道守衛。
    """
    end_d = dt.date.fromisoformat(end)
    return _mk([str(end_d - dt.timedelta(days=n - 1 - i)) for i in range(n)])


def _utc_today() -> dt.date:
    """production 判定器用 `datetime.now(timezone.utc)` 當基準,故種子也對 UTC 日期。"""
    return dt.datetime.now(dt.timezone.utc).date()


def _healthy_history(today: dt.date, n: int = 60) -> list[dict]:
    """n 個連續日曆日、**結束於 `today`** 的 cache history payload。

    ⚠️ **這裡不可以寫死日期**,理由不是風格而是一顆已經引爆過的定時炸彈:
    `_src_cache_files` 沒有 `now=` 注入點(它是 production 路徑,吃真實時鐘),
    而「健康」的定義本身就含 `MJ_FRESH_DAYS_YELLOW`(7 天)新鮮度。任何寫死的
    `end` 只要撐過 7 天就會從 `QUALITY_OK` 翻成 `QUALITY_NAV_STALE` ——
    **不是 production 壞了,是種子過期了**。故種子必須相對於 `today` 產生。

    以 `today` 參數化(而非直接讀時鐘)是為了讓守衛能把時鐘往前撥、
    驗證本函式真的跟著走 —— 見 `test_healthy_wired_seed_survives_time_travel`。
    """
    return [
        {"date": str(today - dt.timedelta(days=n - 1 - i)), "nav": 10.0 + i * 0.01}
        for i in range(n)
    ]


@pytest.fixture
def _seed():
    """在 repo 根 cache/nav/ 寫測試檔,測完刪(不污染 production 的 TLZF9.json)。"""
    written: list[Path] = []

    def _w(code: str, history: list[dict], updated_at: str) -> str:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        p = _CACHE_DIR / f"{code}.json"
        p.write_text(
            json.dumps({"code": code, "updated_at": updated_at,
                        "count": len(history), "history": history}) + "\n",
            encoding="utf-8",
        )
        written.append(p)
        return code

    yield _w
    for p in written:
        p.unlink(missing_ok=True)


# ════════════════════════════════════════════════════════════════
# L0 判定器本身
# ════════════════════════════════════════════════════════════════

def test_dense_recent_series_is_clean():
    """密集 + 新鮮 → 無疑義,年化指標可用。"""
    q = assess_nav_cache_quality(_dense(60), cache_updated_at=_NOW.isoformat(), now=_NOW)
    assert q["code"] == QUALITY_OK
    assert q["usable"] is True
    assert q["supports_annualized"] is True
    assert q["sparse"] is False and q["stale"] is False
    assert q["reason"] is None


def test_too_few_points_is_blocked():
    """筆數 < 下限 → usable=False(Tier A,唯一會擋的情形)。"""
    q = assess_nav_cache_quality(_dense(NAV_CACHE_MIN_POINTS - 1), now=_NOW)
    assert q["usable"] is False
    assert q["code"] == QUALITY_NAV_TOO_FEW
    assert q["supports_annualized"] is False


def test_min_points_boundary_is_inclusive():
    """邊界:剛好等於下限 → 放行(>=,不是 >)。"""
    assert assess_nav_cache_quality(_dense(NAV_CACHE_MIN_POINTS), now=_NOW)["usable"] is True


def test_tlzf9_shaped_series_passes_but_is_flagged():
    """本次事故的真實形狀:10 點 / 14 年 / 空窗 2029 天。

    **放行**(usable=True — 這是最後的 fallback,不能關掉),
    但 **supports_annualized=False**(下游不得拿去算 Sharpe/σ/回撤)。
    """
    q = assess_nav_cache_quality(
        _mk(["2011-11-18", "2012-10-15", "2012-10-16", "2013-03-01", "2013-05-02",
             "2015-03-18", "2020-02-03", "2020-10-01", "2026-04-22", "2026-04-23"]),
        cache_updated_at="2026-07-22T04:31:29.432936+00:00", now=_NOW,
    )
    assert q["usable"] is True, "最後的 fallback 不可被關掉"
    assert q["supports_annualized"] is False, "稀疏序列不得支撐年化指標"
    assert q["code"] == QUALITY_NAV_SPARSE
    assert q["sparse"] is True and q["stale"] is True
    assert q["n_points"] == 10 and q["span_days"] == 5270
    assert q["max_gap_days"] == 2029
    # 以注入的 _NOW(2026-08-27T00:00Z)為基準 → 35;用真實當下跑會是 36。
    # 差 1 天純粹是參考時點不同,故本測試注入固定 now(§5 可重現性)。
    assert q["newest_age_days"] == 126 and q["file_age_days"] == 35
    assert "Sharpe" in q["reason"]


def test_empty_and_none_are_not_usable():
    for s in (None, pd.Series(dtype=float)):
        q = assess_nav_cache_quality(s, now=_NOW)
        assert q["usable"] is False and q["supports_annualized"] is False


def test_stale_but_dense_is_flagged_not_blocked():
    """夠密但過期 → 仍放行;stale=True。"""
    q = assess_nav_cache_quality(_dense(60, end="2026-01-31"), now=_NOW)
    assert q["usable"] is True
    assert q["stale"] is True
    assert q["reason"] is not None


def test_thresholds_come_from_ssot_not_inline():
    """§3.3:三個判定門檻必須是既有 SSOT 常數,不是本模組發明的數字。"""
    from shared import signal_thresholds as st
    assert st.NAV_HIST_COVERAGE_MIN == 0.6
    assert st.NAV_HIST_MAX_GAP_DAYS == 14
    assert st.MJ_FRESH_DAYS_YELLOW == 7
    # 下限本身也不是憑空來的:它等於 live 分支的 inline `>= 10`
    assert NAV_CACHE_MIN_POINTS == 10


def test_coverage_matches_l2_assess_series_coverage():
    """漂移鎖:L0 的覆蓋率算式必須與 L2 `fund_service.assess_series_coverage` 逐欄相同。

    L1 不得 import L2(§8.2,EX-L1ORCH-1 退役前例),所以算式在 L0 又有一份。
    兩份一旦漂移,全站「年化指標可不可信」就會有兩個答案 → 本測試把它們釘死。
    """
    from services.fund_service import assess_series_coverage
    cases = [
        _dense(60),
        _dense(300),
        _mk(["2011-11-18", "2012-10-15", "2012-10-16", "2013-03-01", "2013-05-02",
             "2015-03-18", "2020-02-03", "2020-10-01", "2026-04-22", "2026-04-23"]),
        _mk(["2026-01-01", "2026-06-01"]),
    ]
    for s in cases:
        l2 = assess_series_coverage(s)
        l0 = assess_nav_cache_quality(s, now=_NOW)
        assert l0["coverage"] == l2["coverage"], f"coverage 漂移 @ {len(s)} 點"
        assert l0["max_gap_days"] == l2["max_gap_days"], f"max_gap 漂移 @ {len(s)} 點"
        assert l0["sparse"] == l2["sparse"], f"sparse 漂移 @ {len(s)} 點"


# ════════════════════════════════════════════════════════════════
# 接線:_src_cache_files 真的有用到判定器(防死接線)
# ════════════════════════════════════════════════════════════════

def test_wired_sparse_cache_returns_series_with_flags(_seed):
    """稀疏快取 → 序列照回(fallback 沒被關掉)+ attrs 帶疑義旗標。"""
    code = _seed("ZZSPARSE1", [
        {"date": d, "nav": 10.0 + i}
        for i, d in enumerate(
            ["2011-11-18", "2012-10-15", "2013-03-01", "2013-05-02", "2015-03-18",
             "2020-02-03", "2020-10-01", "2022-01-05", "2026-04-22", "2026-04-23"])
    ], "2026-07-22T04:31:29+00:00")

    s = _src_cache_files(code)
    assert not s.empty and len(s) == 10, "最後的 fallback 不可被閘關掉"
    assert s.attrs["supports_annualized"] is False
    assert s.attrs["nav_quality_code"] == QUALITY_NAV_SPARSE
    assert s.attrs["nav_quality"]["max_gap_days"] > 14


def test_wired_too_few_points_returns_empty(_seed):
    """筆數不足 → 回空(Tier A)。"""
    code = _seed("ZZFEW1", [
        {"date": f"2026-08-{d:02d}", "nav": 10.0} for d in range(1, 5)
    ], "2026-08-26T00:00:00+00:00")
    assert _src_cache_files(code).empty


def test_wired_schema_violation_returns_empty(_seed):
    """NAV <= 0(停售/清算應為 NaN 而非 0)→ schema 擋掉,不再靜默流進 chain。"""
    code = _seed("ZZBAD1", [
        {"date": f"2026-08-{d:02d}", "nav": (0.0 if d == 3 else 10.0)}
        for d in range(1, 15)
    ], "2026-08-26T00:00:00+00:00")
    assert _src_cache_files(code).empty, "NAV=0 的快取必須被 validate_fund_nav 擋下"


def test_wired_healthy_cache_is_untouched(_seed):
    """健康快取 → 完全不受影響(閘不是拿來擋好資料的)。

    ⚠️ 種子**相對於 UTC 當日**產生,不是寫死日期。原本寫死 `2026-08-26`,
    在寫入當天(2026-08-27)age=1 天、綠燈,但 age 每天 +1,撐到 2026-09-03
    就跨過 `MJ_FRESH_DAYS_YELLOW`(7 天)→ `nav_stale_series`,CI 無故轉紅。
    這條測的是「**健康**快取不受影響」,而「健康」的定義本來就包含「夠新」——
    寫死日期等於讓種子隨時間自己變成不健康,那是測試的缺陷,不是 production 的。
    """
    today = _utc_today()
    code = _seed(
        "ZZGOOD1",
        _healthy_history(today),
        dt.datetime.combine(today, dt.time(), tzinfo=dt.timezone.utc).isoformat(),
    )
    s = _src_cache_files(code)
    assert len(s) == 60
    assert s.attrs["supports_annualized"] is True
    assert s.attrs["nav_quality_code"] == QUALITY_OK


# ════════════════════════════════════════════════════════════════
# 防定時炸彈:走真實時鐘的種子不得寫死日期
# ════════════════════════════════════════════════════════════════
# 2026-09-03 事故:`test_wired_healthy_cache_is_untouched` 的種子寫死
# `end = dt.date(2026, 8, 26)`,寫入當天(2026-08-27)age=1 天、綠燈,
# 之後 age 每天 +1;走到 age=8 就跨過 `MJ_FRESH_DAYS_YELLOW`(7)→
# `QUALITY_NAV_STALE`,main 在沒有任何人碰過該檔的情況下自己轉紅。
#
# 下面兩道守衛**互補,缺一不可**:
#   1. 行為守衛(把時鐘往前撥)→ 抓「種子產生器自己被改回寫死」。
#   2. 靜態守衛(掃自己的 AST)→ 抓「有人**新寫**一條走真實時鐘、卻期待
#      健康結果、又寫死日期的測試」。
#
# ⚠️ 兩道都**只管走真實時鐘的 `test_wired_*`**。本檔 L0 區段(`assess_*` 直呼)
# 一律注入 `now=_NOW`,其寫死日期與 `_NOW` 是成對凍結的參考時點,**是正確寫法、
# 不在射程內**,請不要「順手」把守衛擴大到它們 —— 那會逼掉 §5 可重現性。


def test_healthy_wired_seed_survives_time_travel():
    """把時鐘往前撥,`_healthy_history` 產出的種子必須永遠是「健康」。

    這條抓的是:有人把 `_healthy_history` 改回寫死日期(或讓它忽略 `today`)。
    只要它真的跟著 `today` 走,不論在哪一天跑,判定都該是 `QUALITY_OK`。

    ⚠️ **本條不走 `_src_cache_files`**(那條 production 路徑沒有 `now=` 注入點,
    時鐘撥不動),而是直接呼叫 L0 `assess_nav_cache_quality(..., now=...)`。
    函式名裡的 "wired" 指的是「**wired 測試用的那份種子**」,**不是**「跑過
    wired 路徑」—— 2026-09-03 獨立稽核指出這個名字會被誤讀,故就地講明。
    """
    base = _utc_today()
    horizons = [0, 90, 365 * 2, 365 * 10]
    verdicts = {}
    for d in horizons:
        t = base + dt.timedelta(days=d)
        t_dt = dt.datetime.combine(t, dt.time(), tzinfo=dt.timezone.utc)
        s = pd.Series(
            {pd.Timestamp(r["date"]): float(r["nav"]) for r in _healthy_history(t)}
        ).sort_index()
        q = assess_nav_cache_quality(s, cache_updated_at=t_dt.isoformat(), now=t_dt)
        verdicts[d] = (q["code"], q["usable"], q["supports_annualized"], q["stale"])

    expected = (QUALITY_OK, True, True, False)
    bad = {d: v for d, v in verdicts.items() if v != expected}
    assert bad == {}, (
        "種子沒有跟著『現在』走 —— 這正是 2026-09-03 那顆定時炸彈的形狀。\n"
        f"期待每個時點都是 {expected},實際偏離:{bad}"
    )
    # 反向自證:守衛本身沒有空轉(真的算了 4 個時點,而不是一個都沒跑)。
    assert len(verdicts) == len(horizons), "守衛空轉:時間旅行迴圈沒有跑滿"


# ── 靜態守衛用的偵測器(測試與正控共用同一份實作)────────────────────────
# ⚠️ 只寫 `\d{4}-\d{2}-\d{2}` 會漏掉 f-string:`f"2026-08-{d:02d}"` 的 AST
#    Constant 是 `'2026-08-'`(`{...}` 是獨立的 FormattedValue,不在字串裡)。
#    故比對到「年-月-」為止即可,寧可寬也不要漏 —— 漏抓才是本守衛的失效模式。
_DATE_LITERAL_RE = re.compile(r"\d{4}-\d{2}-")


def _wired_tests_with_hardcoded_dates(tree: ast.AST) -> "tuple[dict, set]":
    """回傳 ({有問題的 test 名: 寫死的字面值}, 掃到的所有 test_wired_* 名)。

    「有問題」= 同時滿足:(a) 名字 `test_wired_*`(走 `_src_cache_files`,即真實時鐘)
    (b) 期待**健康**結果(引用 `QUALITY_OK`,或斷言 `supports_annualized ... is True`)
    (c) 函式體內出現寫死的日曆日字面值。
    只有三者同時成立才會腐爛:期待不健康的測試(sparse / 回空)時間再走也不會翻盤。
    """
    offenders, seen = {}, set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_wired_"):
            continue
        seen.add(node.name)

        expects_healthy = False
        literals = []
        # ⚠️ 跳過 docstring:它是**說明文字**,本來就會引用事故日期
        #    (「原本寫死 2026-08-26…」)。把它算成種子會讓守衛誤報,
        #    而誤報的守衛最後一定會被人加豁免關掉。註解不進 AST,天然不受影響。
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body = body[1:]
        for sub in [n for stmt in body for n in ast.walk(stmt)]:
            if isinstance(sub, ast.Name) and sub.id == "QUALITY_OK":
                expects_healthy = True
            if isinstance(sub, ast.Compare) and any(
                isinstance(c, ast.Is) for c in sub.ops
            ):
                txt = ast.dump(sub)
                if "supports_annualized" in txt and "value=True" in txt:
                    expects_healthy = True
            # 寫死日期字面值:字串 / f-string 片段 / dt.date(Y, M, D)
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                if _DATE_LITERAL_RE.search(sub.value):
                    literals.append(sub.value)
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                if sub.func.attr == "date" and len(sub.args) == 3 and all(
                    isinstance(a, ast.Constant) for a in sub.args
                ):
                    literals.append(
                        "date(" + ", ".join(str(a.value) for a in sub.args) + ")"
                    )
        if expects_healthy and literals:
            offenders[node.name] = literals
    return offenders, seen


def test_guard_no_hardcoded_date_in_healthy_wired_test():
    """走真實時鐘 + 期待健康結果的測試,不得含寫死日曆日字面值。

    這條抓的是**下一顆**炸彈:有人新寫一條 `test_wired_*`、斷言 `QUALITY_OK`
    或 `supports_annualized is True`,卻用寫死日期當種子 —— 那條會在
    `MJ_FRESH_DAYS_YELLOW` 天後無聲引爆。

    ⚠️ **射程只有一個語法形狀,不要當成「這一類已經擋住了」**
    (2026-09-03 獨立稽核實測,每一條都附 `_TODAY`/`_OLD` 對照組,**不是推論**)
    擋得住的**只有**:日期字面值**直接寫在 `test_wired_*` 函式體內**,
    且該函式引用 `QUALITY_OK` 或斷言 `supports_annualized ... is True`。
    下列六種寫法**實測全部穿過**(今天全綠,`MJ_FRESH_DAYS_YELLOW` 天後照爆):
      1. `assert ...["nav_quality"]["stale"] is False` — 不碰上面那兩個名字
      2. `assert not ...["nav_quality"]["stale"]`
      3. `assert ...["nav_quality_code"] == "ok"` — 不 import 常數
      4. **把日期搬到 module-level 常數** ← 最危險:本檔的 `_NOW` 就是這個先例,
         只要往上搬一行就完全隱形(實測 14 passed,兩道守衛都沒反應)
      5. 測試不叫 `test_wired_*`、卻照樣呼叫 `_src_cache_files` — 本守衛只認前綴
      6. 日期由 `@pytest.mark.parametrize` 供給 — decorator 不在 `node.body` 裡
    → **要真正封住的方向**(稽核給的,本輪刻意不做):(a) 掃函式外的節點;
      (b) 判定條件由「名字前綴」改成「**有沒有呼叫 `_src_cache_files`**」;
      (c) 「健康」的認定由 `QUALITY_OK` / `supports_annualized` 擴到 `stale`。
      本輪不做的理由是 §-1:稽核已判本次 diff 零必改,擴大守衛是另一件事,須另行派工。

    ⚠️ **已知誤報(一併記名,因為誤報才是守衛被關掉的真正原因)**:一條**時間安全的
    合法**測試 —— 種子用相對日期、但**故意**給一個很舊的 `updated_at`,用來測
    「檔案很舊但資料很新 → 仍應 OK」—— 會被本守衛誤報成違規。本檔上面自己就寫了
    「誤報的守衛最後一定會被人加豁免關掉」,所以這個具體案例先寫在這裡。
    """
    source = Path(__file__).read_text(encoding="utf-8")
    offenders, seen = _wired_tests_with_hardcoded_dates(ast.parse(source))

    # ── 錨點:偵測器必須真的看到東西,否則整條規則空轉(靜默放行)──────────
    assert seen, (
        "錨點失效:本檔已找不到任何 `test_wired_*` 函式。"
        "接線測試若改名或搬走,請同步更新本守衛,不要讓它空轉。"
    )
    assert "test_wired_healthy_cache_is_untouched" in seen, (
        "錨點失效:找不到 `test_wired_healthy_cache_is_untouched`(它是本守衛"
        "唯一已知的『期待健康 + 走真實時鐘』案例)。改名了就請更新本守衛。"
    )

    # ── 正控 / 負控:拿**已知答案**的程式碼餵給同一個偵測器。────────────────
    # 沒有這一步,偵測器一旦壞掉 offenders 就恆空,守衛變成永遠會過的空操作
    # (assert {} == {})。正控證明「抓得到」,負控證明「豁免沒有把它整個關掉」。
    controls = [
        # (名稱, 程式碼, 應否被抓)
        ("寫死 dt.date(...) + QUALITY_OK", (
            "def test_wired_c1(_seed):\n"
            "    end = dt.date(2026, 8, 26)\n"
            "    assert s.attrs['nav_quality_code'] == QUALITY_OK\n"
        ), True),
        ("寫死日期字串 + supports_annualized is True", (
            "def test_wired_c2(_seed):\n"
            "    code = _seed('X', [{'date': '2026-08-26', 'nav': 1.0}], 'u')\n"
            "    assert s.attrs['supports_annualized'] is True\n"
        ), True),
        ("f-string 日期 + QUALITY_OK", (
            "def test_wired_c3(_seed):\n"
            "    h = [{'date': f'2026-08-{d:02d}', 'nav': 1.0} for d in range(1, 15)]\n"
            "    assert s.attrs['nav_quality_code'] == QUALITY_OK\n"
        ), True),
        ("日期只在 docstring(說明文字)", (
            "def test_wired_c4(_seed):\n"
            "    \"\"\"原本寫死 2026-08-26,已改成相對日期。\"\"\"\n"
            "    assert s.attrs['nav_quality_code'] == QUALITY_OK\n"
        ), False),
        ("寫死日期但期待**不健康**結果(sparse / 回空)", (
            "def test_wired_c5(_seed):\n"
            "    code = _seed('X', [{'date': '2026-08-26', 'nav': 1.0}], 'u')\n"
            "    assert _src_cache_files(code).empty\n"
        ), False),
    ]
    ctl_bad = []
    for label, snippet, should_flag in controls:
        off, seen_c = _wired_tests_with_hardcoded_dates(ast.parse(snippet))
        if not seen_c:
            ctl_bad.append(f"{label}:偵測器連函式都掃不到")
        elif bool(off) is not should_flag:
            ctl_bad.append(
                f"{label}:應{'抓到' if should_flag else '放行'},實際{'抓到' if off else '放行'}"
            )
    assert ctl_bad == [], (
        "偵測器自我驗證失敗 —— 本守衛此刻等同空操作,必須先修偵測器再看下面的結果:\n"
        + "\n".join(ctl_bad)
    )

    # ── 本體 ────────────────────────────────────────────────────────────
    assert offenders == {}, (
        "下列測試走真實時鐘(`_src_cache_files` 沒有 now= 注入點)、期待健康結果,"
        "卻用寫死日期當種子 —— 它會在 `MJ_FRESH_DAYS_YELLOW` 天後自己轉紅。\n"
        f"{offenders}\n"
        "修法:種子改成相對於 `_utc_today()` 產生(見 `_healthy_history`)。"
    )
