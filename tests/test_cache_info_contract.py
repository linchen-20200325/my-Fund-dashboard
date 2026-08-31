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

本檔要擋的兩件事
----------------
1. **契約守衛**：`get_all_cache_info()` 的**每一列**都要有 `name` + `size`；
   統計欄位 `hits`/`misses`/`uncached_fail` **全有或全無**。
   → 日後有人新增第 5 種生產者卻不照契約，這裡會紅。
2. **回歸守衛**：直接釘住本次的 bug —— 對**真實 registry** 做消費端那個加總，
   不得拋例外。

⚠️ **刻意用真實 `_CACHE_REGISTRY`，不自己造假 dict** —— 造假 dict 只會測到
「我寫的假資料符合我寫的契約」，測不到真的生產者。
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
