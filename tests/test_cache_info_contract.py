"""cache_info() 欄位契約守衛 + 「🔋 快取狀態」caption 回歸守衛（2026-08-31）。

修的是什麼
----------
`cache_info()` 有 **4 個生產者**，過去各寫各的欄位名：entry 數在
`infra.cache._ttl_cache` 叫 `size`，在 `_daily_cache` /
`infra.source_backoff._BackoffRegistryProxy` /
`repositories.fund.fx_and_main._FxCacheProxy` 叫 `currsize`。

實測後果（2026-08-31，`origin/main` = 3aceccb）：`get_all_cache_info()` 回 14 列
共 **4 種形狀**，其中 7 列沒有 `size`。全站唯一的 production 消費者
——`ui/helpers/portfolio/policy_admin_section.py` 的「🔋 快取狀態」caption——
寫 `sum(r["size"] for r in rows)`，於是 `KeyError: 'size'`，再被外層
`except Exception: pass  # smoke-allow-pass` 吞掉 →
**那行 caption 從上線以來一次都沒印出來過，而測試一路長綠。**

~~本檔要擋的兩件事~~ → **三件事**
--------------------------------
⚠️ **有意識的更正，不是漏刪**（日期 **2026-08-31**；決策者：**#746 回修組**，
依獨立紅隊實測）。**舊表述在寫下的當天不是「寫錯」，是「不完整」**：第 1 條的
「每一列都要有 `name` + `size`」讀起來像兩個欄位都被守住了，
**實測只有 `size` 是真的**（理由見下方第 3 條與 `TestRawProducerContract`）。
舊表述的理由仍然成立（它確實描述了第 1、2 條在做的事），被權衡掉的是它的
**涵蓋範圍宣稱**。

1. **契約守衛（回填後）**：`get_all_cache_info()` 的**每一列**都要有
   `name` + `size`；統計欄位 `hits`/`misses`/`uncached_fail` **全有或全無**。
2. **回歸守衛**：直接釘住本次的 bug —— 對**真實 registry** 做消費端那個加總，
   不得拋例外。
3. 🆕 **契約守衛（回填前）**：直接向每個生產者要 `cache_info()`，斷言必備欄位齊全。
   **第 1 條驗不到 `name`** —— `get_all_cache_info()` 內是
   `info["name"] = fn.__name__`（**無條件事後回填**），回填後的列必然有 `name`。
   → ~~日後有人新增第 5 種生產者卻不照契約，**要靠第 3 條才會紅**。~~

⚠️ **刻意用真實 `_CACHE_REGISTRY`，不自己造假 dict** —— 造假 dict 只會測到
「我寫的假資料符合我寫的契約」，測不到真的生產者。

⚠️ **涵蓋範圍限定（必讀；上面那句被實測推翻）**
------------------------------------------------
**有意識的更正，不是漏刪**；日期 **2026-08-31**；決策者：**#746 回修組**，
依**第二輪獨立稽核**實測。

**舊表述的理由仍然成立**：第 3 條確實是「第 5 生產者不照契約」的**唯一**紅燈來源
（第 1 條因回填而結構上看不見它），這句話描述的機制沒有錯。
**被權衡掉的是它省略掉的前提** —— 它讀起來像「新增任何第 5 生產者都會被抓到」，
**而那要看那個生產者住在哪個模組**。

**根因**：`_CACHE_REGISTRY` 由 `register_cache(fn)` 在 **module import 時**填充
→ registry 的內容**取決於誰被 import**。本檔守衛（含第 3 條）的涵蓋範圍
＝ 下方 `rows` fixture 那 6 個 import 的**可達集合**，**不是 production 全集**。

**三個數字都對，但不可互換（2026-08-31 AST 別名不敏感窮舉 + 實測）**：

===================================  ====  ==========================================
量的是什麼                           數量  來源
===================================  ====  ==========================================
`cache_info()` **生產者種類**           4  `infra/cache.py` ×2（`_ttl_cache` /
                                          `_daily_cache`）+ `infra/source_backoff.py`
                                          + `repositories/fund/fx_and_main.py`
production **註冊點**                  20  18 個 `@register_cache`
                                          + 2 處 `register_cache(<proxy>())`
本檔 fixture **可達的註冊條目**        18  實測（本檔守衛的真實涵蓋範圍）
===================================  ====  ==========================================

**差額的 2 個生產者不在本檔視野內**：
  - `services/liquidity_engine.py::fetch_liquidity_factors`
  - `services/us_liquidity_engine.py::fetch_us_liquidity_snapshot`

兩者都是 UI 端**函式內 lazy import**（`ui/tab1_macro.py` /
`ui/tab1_macro_longterm.py` / `ui/tab1_macro_radar.py` /
`services/macro/us_indicators.py`）—— 也就是說它們在 production **真的會**進
registry（使用者開過總經分頁後即為 20），只是本檔**永遠量不到**。

**決定性實測（2026-08-31，本組獨立複跑）**：把一個「有 `size`、沒有 `name`」的
違約生產者種進 `services/us_liquidity_engine.py`（fixture 永遠不會 import 的模組），
先證明該突變**確實生效**（registry 內出現該違約者），再跑本檔 —— **18 條全綠、
零紅燈**。

⚠️ **這是結構性限制，不是本批的缺陷**：守衛只能檢查**已註冊**的東西，而註冊是
import 的副作用。且上述 2 個構外生產者**目前皆符合契約**（實測）→ 這是**未來的
偵測缺口，不是現行的違約**。**要修的是「有沒有據實揭露」，不是程式碼。**

⚠️ **想擴大涵蓋範圍的人請注意**：在 fixture 補 import 只會把 18 變成 20，
**不會**改變「涵蓋範圍＝import 可達集合」這個結構 —— 下一個新增在別處的生產者
一樣看不到。真正的解是改成**掃描註冊點**（AST）而非**掃描 registry**（runtime），
那是另一個題目，**本批沒有做**（§-1：無 user 指派、無實際 bug 觸發）。
"""
import ast
import pathlib

import pytest

import infra.cache as ic
from infra.cache import (
    CACHE_INFO_REQUIRED_KEYS,
    CACHE_INFO_STAT_KEYS,
    get_all_cache_info,
)

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_CONSUMER = _ROOT / "ui" / "helpers" / "portfolio" / "policy_admin_section.py"


@pytest.fixture(scope="module")
def rows():
    """真實 registry。先 import 所有會註冊快取的模組，重現 production 的組成。

    這幾個 import 就是消費端那段程式做的事（它 import repositories.macro_repository
    來「觸發 macro 快取註冊」），此處對齊，否則只會測到 registry 的一部分。
    """
    import repositories.macro_repository  # noqa: F401
    import repositories.macro_tw_local_repository  # noqa: F401
    import repositories.fund.fx_and_main  # noqa: F401
    import repositories.fund.nav_metrics  # noqa: F401
    import infra.proxy  # noqa: F401
    import infra.source_backoff  # noqa: F401
    out = get_all_cache_info()
    assert out, "registry 是空的 —— 這批測試就失去意義了（import 沒觸發註冊？）"
    return out


@pytest.fixture(scope="module")
def producers(rows):
    """registry 本身（不是 get_all_cache_info() 的輸出）。

    依賴 `rows` 只為借它的 import 副作用 —— 那些 import 才會觸發快取註冊。
    """
    assert ic._CACHE_REGISTRY, "registry 是空的 —— 這批測試就失去意義了"
    return list(ic._CACHE_REGISTRY)


class TestCacheInfoContract:
    def test_every_row_has_required_keys(self, rows):
        """必備欄位：每一列都要有 name + size。

        這是本次 KeyError 的根因守衛：只要有任何一個生產者不吐 `size`，這裡就紅。
        """
        offenders = [
            (r.get("name", "?"), sorted(set(CACHE_INFO_REQUIRED_KEYS) - set(r)))
            for r in rows
            if not set(CACHE_INFO_REQUIRED_KEYS).issubset(r)
        ]
        assert not offenders, (
            f"下列 cache_info() 生產者違反欄位契約（缺必備欄位）：{offenders}\n"
            f"  → 必備欄位 = {CACHE_INFO_REQUIRED_KEYS}\n"
            f"  → 見 infra/cache.py 的「cache_info() 欄位契約」段"
        )

    def test_size_is_a_non_negative_int(self, rows):
        """`size` 必須是能被加總的數 —— 不能是字串或 None。"""
        bad = [(r.get("name", "?"), repr(r.get("size")))
               for r in rows
               if not isinstance(r.get("size"), int) or isinstance(r.get("size"), bool)
               or r.get("size") < 0]
        assert not bad, f"size 必須是非負 int（可加總），違規列：{bad}"

    def test_stat_keys_are_all_or_nothing(self, rows):
        """統計欄位全有或全無 —— 不得只給一半，讓消費端算出半真的命中率。"""
        partial = []
        for r in rows:
            present = [k for k in CACHE_INFO_STAT_KEYS if k in r]
            if present and len(present) != len(CACHE_INFO_STAT_KEYS):
                partial.append((r.get("name", "?"), present))
        assert not partial, (
            f"統計欄位必須全有或全無（{CACHE_INFO_STAT_KEYS}），半套的列：{partial}"
        )

    def test_proxy_rows_omit_stats_rather_than_faking_zero(self, rows):
        """§1：本質上沒有命中率的列要**缺席**，不是填 0。

        `_FX_CACHE` / `_SOURCE_BACKOFF` 只是把 raw dict 包成 registry 介面，
        沒有攔截呼叫 —— 命中率不適用。填 0 會讓消費端把「不適用」讀成
        「0 次命中」，那是 §1 禁止的假數字。
        """
        by_name = {r.get("name"): r for r in rows}
        for _n in ("_FX_CACHE", "_SOURCE_BACKOFF"):
            assert _n in by_name, f"{_n} 應在 registry 內（逃生門 + 可觀測）"
            for _k in CACHE_INFO_STAT_KEYS:
                assert _k not in by_name[_n], (
                    f"{_n} 不該有 {_k} —— 它沒有攔截呼叫，命中率不適用；"
                    f"缺席才是誠實的表達方式（§1）"
                )

    def test_at_least_one_row_does_carry_stats(self, rows):
        """反向：不能全部都「不適用」，否則上一條會空轉成假綠燈。"""
        with_stats = [r for r in rows if set(CACHE_INFO_STAT_KEYS).issubset(r)]
        assert with_stats, "沒有任何一列帶統計欄位 —— hit-rate 永遠算不出來"


class TestRawProducerContract:
    """契約守衛（**回填前**）：直接向每個生產者要 `cache_info()`，不看回填後的列。

    ⚠️ **為什麼非得多這一組不可 —— 這是 2026-08-31 紅隊實測抓到的守衛缺口**：
    `get_all_cache_info()` 內部寫的是 `info["name"] = fn.__name__` ——
    **無條件事後回填**。於是 `rows` fixture 拿到的每一列都一定有 `name`，
    上面 `TestCacheInfoContract` 那組**在結構上不可能**看到「生產者沒吐 name」。
    實測兩筆：
      (a) 拔掉 `infra/cache.py::_ttl_cache` 新增的 `"name": fn.__name__`
          → 生產者原始輸出真的少了 `name`（行為確實變了），16 條守衛**全綠**；
      (b) 註冊一個「有 `size`、沒有 `name`」的第 5 生產者
          → 回填後那列有 `name`，16 條守衛**全綠**。
    也就是說：契約的兩個必備欄位裡，先前**只有 `size` 真的被守住**。

    本組把尺換成**回填前的原始輸出**，同一個尺同時擋住 (a) 與 (b)。
    ⚠️ 這一條是**行為守衛**，不是形式守衛：它斷言的是生產者實際吐出來的東西，
    不是原始碼長什麼樣。
    """

    def test_producer_output_carries_required_keys_before_backfill(self, producers):
        """每個生產者**自己**就要吐齊必備欄位，不准靠 get_all_cache_info() 補。

        `name` 之所以要生產者自己給：`fn.cache_info()` 是 public 介面，
        直接呼叫它的 caller（不經 `get_all_cache_info()`）拿到的必須也是完整的列。
        """
        offenders = []
        for fn in producers:
            label = getattr(fn, "__name__", repr(fn))
            try:
                raw = fn.cache_info()
            except Exception as e:  # 生產者連 cache_info() 都叫不動 = 違約
                offenders.append((label, f"cache_info() 拋 {type(e).__name__}: {e}"))
                continue
            # ⚠️ 型別先驗，不能只靠下一行的 `set(raw)`（2026-08-31 稽核 M-D2）：
            # `set(REQUIRED) - set(raw)` 對**任何可迭代物**都成立 —— 生產者回一個
            # `["name", "size"]`（list）會完全過關，而消費端 `r["size"]` 會當場
            # TypeError。實務上牽強（真的 `lru_cache` 回 namedtuple，`set()` 迭代出
            # 的是數值 → 反而會被抓到），但關掉它只要一行。
            if not isinstance(raw, dict):
                offenders.append(
                    (label, f"cache_info() 回傳 {type(raw).__name__} 而非 dict")
                )
                continue
            missing = sorted(set(CACHE_INFO_REQUIRED_KEYS) - set(raw))
            if missing:
                offenders.append((label, f"缺 {missing}"))
        assert not offenders, (
            f"下列生產者的 **cache_info() 原始輸出**違反欄位契約：{offenders}\n"
            f"  → 必備欄位 = {CACHE_INFO_REQUIRED_KEYS}\n"
            f"  → 注意：get_all_cache_info() 會事後回填 `name`，所以看回填後的列"
            f"    **驗不出這個問題**；本條刻意在回填前量。\n"
            f"  → 見 infra/cache.py 的「cache_info() 欄位契約」段"
        )

    def test_backfill_is_not_load_bearing(self, producers):
        """反向：確認上一條沒有空轉。

        若哪天 `get_all_cache_info()` 的回填被拿掉，回填前後的 `name` 必須一致
        —— 也就是**回填目前不承載任何東西**，它只是防禦性的重複。
        這條同時釘住「回填不得被用來『補齊』一個違約的生產者」。

        ⚠️ **刪本條之前必讀 —— 它同時是 `name` 唯一的型別檢查**（2026-08-31 稽核）：
        `size` 有 `test_size_is_a_non_negative_int` 守型別，**`name` 沒有對應的
        型別測試**。實測兩筆突變 —— 生產者回 `name=None`、回 `name=12345` ——
        **只有本條抓到**（`raw_name != label` 兩種都成立）。

        ⚠️ **它「看起來恆真」是個陷阱**：對走 `_ttl_cache` / `_daily_cache` 的生產者
        而言（**本檔可見的 18 條裡佔 16 條**，2026-08-31 實測；⚠️ 這是**fixture 可達**
        的計數，不是 production 全集，見本檔開頭「涵蓋範圍限定」），
        `@functools.wraps` 讓 `info["name"]` 與 `fn.__name__` 本來就是
        同一個字串，本條近乎恆真 —— 但**對 2 個 proxy 生產者它是真的在檢查**
        （`_FX_CACHE` / `_SOURCE_BACKOFF` 兩邊都是**手寫**的：一邊手寫
        `__name__`，一邊手寫 `"name"` 字面值，兩者可以各自漂移）。
        → **日後若有人覺得它「恆真、沒在測東西」而刪掉，會同時失去 `name` 的
        型別防線。要刪請先補一條 `name` 的型別測試。**
        """
        mismatched = []
        for fn in producers:
            label = getattr(fn, "__name__", repr(fn))
            try:
                raw_name = fn.cache_info().get("name")
            except Exception:
                continue  # 上一條會紅，這裡不重複報
            if raw_name != label:
                mismatched.append((label, raw_name))
        assert not mismatched, (
            f"生產者自報的 name 與 registry 的 __name__ 不一致：{mismatched}\n"
            f"  → 兩者不一致時，UI 顯示的名字會隨『有沒有走 get_all_cache_info()』而變"
        )


class TestCaptionRegression:
    """直接釘住本次 bug：消費端那段加總，對真實 registry 不得拋例外。"""

    def test_total_entries_sum_does_not_raise(self, rows):
        """`sum(r["size"] …)` —— 這一行在修好前會 KeyError: 'size'。"""
        total = sum(r["size"] for r in rows)
        assert isinstance(total, int) and total >= 0

    def test_full_caption_aggregation_reproduces(self, rows):
        """完整重跑消費端的三個數字，確認整段能算完。"""
        n_funcs = len(rows)
        total_entries = sum(r["size"] for r in rows)
        stat_rows = [r for r in rows if "hits" in r and "misses" in r]
        hits = sum(r["hits"] for r in stat_rows)
        misses = sum(r["misses"] for r in stat_rows)
        calls = hits + misses
        rate = f"{(hits / calls * 100):.1f}%" if calls > 0 else "—"
        caption = (f"🔋 快取狀態：{n_funcs} 個函式 / {total_entries} entries / "
                   f"hit-rate {rate}（hits={hits} / misses={misses}）")
        assert "快取狀態" in caption and n_funcs > 0

    def test_get_uses_would_have_hidden_the_bug(self, rows):
        """說明性守衛：證明 `.get("size", 0)` 是**不可接受**的修法。

        若當初改用 `.get("size", 0)`，caption 不會炸，但會**靜默少算** entries
        —— 那是 §1 的假數字。本測試確認每一列都真的有 `size`，
        因此 `r["size"]` 與 `r.get("size", 0)` 結果一致；一旦有人違約，
        兩者會分岐，`test_every_row_has_required_keys` 會先紅。
        """
        strict = sum(r["size"] for r in rows)
        lenient = sum(r.get("size", 0) for r in rows)
        assert strict == lenient, (
            "有列缺 size —— 寬鬆版會少算，等於用假數字掩蓋違約"
        )


class TestConsumerLeavesATrace:
    """§1：顯示性失敗可以不影響主流程，但**不得沒有痕跡**。

    對照既有前例 `tests/test_review_fixes_v19_346.py::
    test_smoke_allow_pass_not_used_with_broad_except` —— 那條規則在
    2026-08-14 就立好了，但**只套用在 `ui/tab2_single_fund.py` 一個檔**。
    本檔把同一把尺套到 `policy_admin_section.py`。
    （⚠️ repo 內其餘 12 檔 29 處同型寫法仍未套用，已登記於本批 PR 描述，
      **不在本批檔案邊界內**。）
    """

    def _src(self):
        return _CONSUMER.read_text(encoding="utf-8")

    def test_no_new_broad_except_pass(self):
        """廣義 `except: pass` 不得再新增；本次修好的兩處不得回退。

        ⚠️ **已登記的既有基準（本批刻意不動，非漏改）**：本檔另有 **3 處**
        廣義 `except Exception: pass`，全部是 v19.296 的「🔐 用 Google 登入」
        快捷按鈕（`st.link_button`）—— OAuth 設定解析失敗時整顆按鈕靜默消失。
        **同型的病**，但屬**另一個功能（OAuth 登入）**、本批沒有任務碰它、
        也沒有實際 bug 觸發 → 依 §-1 **登記不動**，已寫進本批 PR 描述。

        故本守衛用**語意基準**而非行號（行號會隨編輯漂移）：
        允許的例外**只有** try 區塊內含 `st.link_button` 的那一種；
        其餘任何廣義 `except: pass`（含本次修好的兩處若被改回去）一律紅燈。
        """
        tree = ast.parse(self._src())
        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            body_src = ast.dump(ast.Module(body=node.body, type_ignores=[]))
            is_known_login_baseline = "link_button" in body_src
            for h in node.handlers:
                if len(h.body) != 1 or not isinstance(h.body[0], ast.Pass):
                    continue
                t = h.type
                broad = t is None or (isinstance(t, ast.Name)
                                      and t.id in ("Exception", "BaseException"))
                if broad and not is_known_login_baseline:
                    offenders.append(h.body[0].lineno)
        assert not offenders, (
            f"policy_admin_section.py 出現**未登記**的廣義 except: pass"
            f"（行號 {offenders}）。請收窄例外型別，或補 stderr log ——"
            f"2026-08-31 實證：這種寫法整整吞掉了一個 production"
            f"從未渲染成功的 caption，而測試一路長綠。"
        )

    @pytest.mark.parametrize("tag", ["[policy_admin/cache_info]",
                                     "[policy_admin/sheet_stats]"])
    def test_log_tags_present(self, tag):
        assert tag in self._src(), (
            f"缺 {tag} stderr log —— 失敗時使用者與稽核都無從分辨"
            f"「本來就沒東西」與「算爆了」"
        )

    def test_consumer_excludes_not_applicable_rows_from_hit_rate(self):
        """消費端必須用 `"hits" in r` 判斷，不得用 `.get("hits", 0)`。

        後者把「不適用」偽裝成「0 次命中」（§1 假數字）。
        """
        tree = ast.parse(self._src())

        # ⚠️ 走 AST 而非字串比對 —— 這個檔的**註解裡**就寫著
        # 「不要用 `r.get("hits", 0)`」，字串比對會被自己的警告句誤判。
        bad = []
        for n in ast.walk(tree):
            if (isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "get"
                    and n.args
                    and isinstance(n.args[0], ast.Constant)
                    and n.args[0].value in ("hits", "misses")):
                bad.append(n.lineno)
        assert not bad, (
            f'消費端在行 {bad} 用了 `.get("hits"/"misses", …)` —— 那會把'
            f'「不適用」寫成「0 次命中」，是 §1 禁止的假數字。'
            f'請改用 `"hits" in r` 明確排除。'
        )

        has_membership = any(
            isinstance(n, ast.Compare)
            and isinstance(n.left, ast.Constant)
            and n.left.value == "hits"
            and any(isinstance(o, ast.In) for o in n.ops)
            for n in ast.walk(tree)
        )
        assert has_membership, (
            '消費端應以 `"hits" in r` 明確排除本質上沒有命中率的列'
        )


class TestStaleClaimNotReasserted:
    """擋住那句被更正過的不實宣稱重新長回來。

    「Tab5 快取狀態表 … 既有 UI 泛型渲染，零 UI 改動」三處皆不實：
    (a) 畫面不在 Tab5（在「📋 保單管理」）；(b) 不是泛型渲染，是寫死 f-string；
    (c) 在本批修好前根本沒渲染。同一句話當時被寫進 3 個載體，
    先前那一輪只更正了 1 個。
    """

    # 三個載體各自的**原句片段**（逐字取自更正前的原始碼）。
    # 規則：這些片段若還在檔案裡，所在行必須帶刪除線 `~~`（舊表述保留不刪）。
    _ORIGINAL_CLAIMS = [
        ("infra/source_backoff.py", "（既有 UI 泛型渲染，**零 UI 改動**）"),
        ("infra/source_backoff.py", "**兩者都零 UI 改動**"),
        ("infra/cache.py", "Tab5 快取狀態表走 get_all_cache_info() 泛型渲染"),
    ]

    @pytest.mark.parametrize("path,claim", _ORIGINAL_CLAIMS)
    def test_original_claim_is_struck_through(self, path, claim):
        """原句必須**保留但劃線**，不得刪除、也不得回到未劃線的肯定句。"""
        lines = (_ROOT / path).read_text(encoding="utf-8").splitlines()
        hits = [l for l in lines if claim in l]
        assert hits, (
            f"{path} 找不到原句「{claim}」—— 舊表述應**保留不刪**"
            f"（加刪除線 + 註明理由），不是整句刪掉"
        )
        unstruck = [l for l in hits if "~~" not in l]
        assert not unstruck, (
            f"{path} 的原句未加刪除線（等於仍在主張一件不實的事）：\n"
            + "\n".join("  " + l.strip() for l in unstruck)
        )

    def test_correction_is_recorded_in_source_backoff(self):
        text = (_ROOT / "infra" / "source_backoff.py").read_text(encoding="utf-8")
        assert "有意識的更正，不是漏刪" in text, "更正須留痕（舊表述保留 + 理由）"
        assert "policy_admin_section.py" in text, (
            "更正須指出畫面實際在哪，否則下一個人還是會去 Tab5 找"
        )
