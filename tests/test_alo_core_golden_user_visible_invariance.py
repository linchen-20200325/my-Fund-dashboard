# -*- coding: utf-8 -*-
"""BL-0342／BL-0453：ALO 黃金矩陣的「使用者可見內容跨 CPython 版本不變」守衛（**額外**的一條，不取代、也不放寬嚴格 Golden）。

背景：`tests/test_alo_core_golden.py` 以**逐位元組**比對黃金檔，預期值錄於 CPython 3.11；CPython≥3.12 起內建 float `sum()`
改為補償加總，`alo2_family/cost:near_tied_leaders_within_1e9` 情境的內部浮點欄差 1 ulp，所以嚴格比對在非 3.11 直譯器上
會被 `@baseline_python_only` 擋下（本機 skip、CI fail）。那留下一個問題：**這 1 ulp 會不會外溢成使用者看得到的差異？**

本檔回答它，且**在任何 CPython 版本都執行**（不 skip）：把工作樹的整份矩陣與黃金檔（唯讀）逐葉比對 ——
  * **所有非浮點葉**（文字、布林、整數、None、鍵順序、清單長度、型別）：任何位置都必須**逐一相同**；
  * **浮點葉**：在「內部欄」（路徑上任一層的鍵以單底線 `_` 開頭，例如 `_current_pct`／`_diff`／`_in_total`）之外必須**逐位元相同**（repr）；
    內部欄之內只容許 `math.isclose(rel_tol=1e-9, abs_tol=1e-12)` 的尾差；
  * 唯一整個略過的鍵是 `page_model_sha256`（整頁模型的摘要；內部浮點欄差 1 ulp 它必然不同，而其內容已由上面逐葉比對覆蓋）。

⚠️ 這**不是**放寬 Golden：黃金檔一個位元組都沒動，嚴格逐位元組比對仍在 `tests/test_alo_core_golden.py`（基準版本 3.11 照跑）。
   本檔只是補一條「就算嚴格比對在 3.12+ 不能用，使用者可見輸出仍與黃金檔相同」的證據，且對自己做負向對照（見最後一節）。
⚠️ 若本檔在某個版本變紅，代表差異已不只是內部浮點尾差（例如文字欄變了）—— 那是真的行為變化，不得放寬本檔。
"""

from __future__ import annotations

import copy
import json
import math
import pathlib

import _alo_core_golden as G

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_GOLDEN = _ROOT / "tests" / "fixtures" / "alo_core_golden_before.json"

#: 整個略過的鍵（整頁模型摘要；內部浮點欄尾差必然改變它）。
DIGEST_KEY = "page_model_sha256"
#: 內部浮點欄的容許尾差（1 ulp 約 1e-14 量級；`_diff` 為相減結果，故另給絕對容許）。
REL_TOL = 1e-9
ABS_TOL = 1e-12


def _is_float_leaf(node) -> bool:
    return isinstance(node, dict) and set(node) == {"__float__"}


def _is_internal_key(key) -> bool:
    return isinstance(key, str) and key.startswith("_") and not key.startswith("__")


def compare_user_visible(live, gold) -> tuple[list[str], dict]:
    """逐葉比對（`G.canon` 的 JSON 原生形式）。回傳 (違規清單, 統計)。"""
    violations: list[str] = []
    stats = {"str": 0, "other_exact": 0, "float_exact": 0, "float_internal_equal": 0,
             "float_internal_tolerated": 0, "digest_skipped": 0}

    def where(path):
        return "/".join(str(p) for p in path)

    def walk(a, b, path, internal):
        if _is_float_leaf(a) or _is_float_leaf(b):
            if not (_is_float_leaf(a) and _is_float_leaf(b)):
                violations.append(f"{where(path)}: float leaf vs non-float ({a!r} vs {b!r})")
                return
            ra, rb = a["__float__"], b["__float__"]
            if ra == rb:
                stats["float_internal_equal" if internal else "float_exact"] += 1
                return
            if internal and math.isclose(float(ra), float(rb), rel_tol=REL_TOL, abs_tol=ABS_TOL):
                stats["float_internal_tolerated"] += 1
                return
            violations.append(f"{where(path)}: float {ra} vs {rb} ({'internal, beyond tolerance' if internal else 'user-visible path, must be bit-identical'})")
            return
        if isinstance(a, dict) and isinstance(b, dict):
            if list(a) != list(b):
                violations.append(f"{where(path)}: dict keys/order differ ({list(a)[:6]} vs {list(b)[:6]})")
                return
            for k in a:
                if k == DIGEST_KEY:
                    stats["digest_skipped"] += 1
                    continue
                walk(a[k], b[k], path + [k], internal or _is_internal_key(k))
            return
        if isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                violations.append(f"{where(path)}: list length {len(a)} vs {len(b)}")
                return
            for i, (x, y) in enumerate(zip(a, b)):
                walk(x, y, path + [i], internal)
            return
        if type(a) is not type(b) or a != b:
            violations.append(f"{where(path)}: {a!r} vs {b!r}")
            return
        stats["str" if isinstance(a, str) else "other_exact"] += 1

    walk(live, gold, [], False)
    return violations, stats


def _golden_decoded() -> dict:
    return G.decode_matrix(json.loads(_GOLDEN.read_text(encoding="utf-8")))


# ═══════════════════════ 主驗收：使用者可見內容與黃金檔相同（任何 CPython 版本都跑） ═══════════════════════


def test_使用者可見內容_工作樹與黃金檔相同_內部浮點欄只容許尾差():
    violations, stats = compare_user_visible(G.run_matrix(G.live_namespace()), _golden_decoded())
    assert violations == [], violations[:10]
    # 防空掃：比對的葉子要夠多（黃金檔凍結為 212 情境）；摘要鍵逐情境略過 107 個（只有 alo2_family 有）。
    assert stats["str"] >= 5000, stats
    assert stats["other_exact"] >= 1000, stats
    assert stats["float_exact"] >= 50, stats
    assert stats["float_internal_equal"] + stats["float_internal_tolerated"] >= 500, stats
    assert stats["digest_skipped"] == 107, stats


# ═══════════════════════ 負向對照：比對器真的會抓到使用者可見的差異 ═══════════════════════


def _synthetic():
    return {"ok": {
        "title": "目標對照卡",
        "_tone": "中性",
        "weight": {"__float__": "0.5"},
        "_rows": [{"bucket_text": "核心", "current_text": "55.0%", "_current_pct": {"__float__": "55.000000003"}}],
        DIGEST_KEY: "a" * 64,
    }}


def _bumped(text: str) -> dict:
    """比 `text` 大 1 ulp 的浮點葉。"""
    return {"__float__": repr(math.nextafter(float(text), math.inf))}


def test_比對器_完全相同_無違規():
    v, stats = compare_user_visible(_synthetic(), _synthetic())
    assert v == []
    assert stats["digest_skipped"] == 1


def test_比對器_內部浮點欄差1ulp_容許():
    live = _synthetic()
    live["ok"]["_rows"][0]["_current_pct"] = _bumped("55.000000003")
    v, stats = compare_user_visible(live, _synthetic())
    assert v == []
    assert stats["float_internal_tolerated"] == 1


def test_比對器_內部浮點欄差超過容許_抓到():
    live = _synthetic()
    live["ok"]["_rows"][0]["_current_pct"] = {"__float__": "55.00001"}
    v, _ = compare_user_visible(live, _synthetic())
    assert v and "beyond tolerance" in v[0]


def test_比對器_非內部浮點欄差1ulp_抓到_必須逐位元相同():
    live = _synthetic()
    live["ok"]["weight"] = _bumped("0.5")
    v, _ = compare_user_visible(live, _synthetic())
    assert v and "bit-identical" in v[0]


def test_比對器_文字欄不同_抓到():
    live = _synthetic()
    live["ok"]["_rows"][0]["current_text"] = "55.1%"
    v, _ = compare_user_visible(live, _synthetic())
    assert len(v) == 1 and "current_text" in v[0]


def test_比對器_內部欄底下的非浮點值不同_也抓到():
    live = _synthetic()
    live["ok"]["_tone"] = "警示"
    v, _ = compare_user_visible(live, _synthetic())
    assert len(v) == 1 and "_tone" in v[0]


def test_比對器_鍵順序或清單長度或型別不同_抓到():
    live = _synthetic()
    live["ok"] = dict(reversed(list(live["ok"].items())))
    assert compare_user_visible(live, _synthetic())[0]
    live2 = _synthetic()
    live2["ok"]["_rows"].append({})
    assert compare_user_visible(live2, _synthetic())[0]
    live3 = _synthetic()
    live3["ok"]["title"] = 1
    assert compare_user_visible(live3, _synthetic())[0]


def test_比對器_摘要鍵不同_只略過這一個鍵():
    live = _synthetic()
    live["ok"][DIGEST_KEY] = "b" * 64
    assert compare_user_visible(live, _synthetic())[0] == []
    live["ok"]["other_sha256"] = "x"
    gold = _synthetic()
    gold["ok"]["other_sha256"] = "y"
    assert compare_user_visible(live, gold)[0]


def test_比對器_作用在真正的黃金矩陣上_改一個文字欄會被抓到():
    gold = _golden_decoded()
    live = copy.deepcopy(gold)
    rows = live["alo2_family"]["cost:near_tied_leaders_within_1e9"]["alo2"]["ok"]["_rows"]
    assert rows[0]["current_text"] == "55.0%"
    rows[0]["current_text"] = "55.1%"
    v, _ = compare_user_visible(live, gold)
    assert len(v) == 1 and "current_text" in v[0], v
