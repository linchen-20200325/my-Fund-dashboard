# -*- coding: utf-8 -*-
"""BL-0542 G1-①「黃金基準」：💼 ALO 配置核心（`basis_value_with_key`／`_category_values`／`_build_alo2` 與下游）
搬遷前的行為，逐位元組不變（fast lane；不打網路、不需要 git 歷史）。

證明方式：`tests/fixtures/alo_core_golden_before.json` 是**基準版本**（commit `e6ff19025f7e2c56c6c398de7c59188194aa96ab`、
tree `abebfa59e4112e970c4bccb2ddda9253ed4b3675`）在**乾淨解開的目錄**（`git archive | tar -x`，不是工作樹）上，
以 `tests/_alo_core_golden.py` 的情境矩陣跑出來的結果。本檔對**工作樹**再跑一次同一份矩陣，序列化結果必須與檔案相同。

⚠️ 黃金檔**不得**以改動後的程式重錄（那會把要證明的東西變成循環論證）；它的 sha256 釘在本檔（`_PINNED_SHA256`），
   任何人改了檔案內容，`test_黃金檔本身的sha256釘死` 先紅。
⚠️ 黃金檔凍結的是**現況**，含已知差異：市值基準下「某類別缺匯率、另一類別有值」時，有值類別的分母只含自己 ⇒ 顯示 100.0%
   （與客戶核可的方案 A 不同；見 `docs/BACKLOG.md` BL-0542）。G1-②（搬遷）必須**逐位元組相同**；方案 A 的行為變更是之後
   另一個批次、另一份黃金檔。
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import types

import pytest

import _alo_core_golden as G

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_GOLDEN = _ROOT / "tests" / "fixtures" / "alo_core_golden_before.json"

_BASE_COMMIT = "e6ff19025f7e2c56c6c398de7c59188194aa96ab"
_BASE_TREE = "abebfa59e4112e970c4bccb2ddda9253ed4b3675"
_PINNED_SHA256 = "c65875cdf4c3fbe8929379b52733a89d47359c5947772b1f82c88a66733ee4a5"
_EXPECTED_COUNTS = {"basis_value": 67, "category_values": 38, "alo2_family": 107}


def _doc() -> dict:
    return json.loads(_GOLDEN.read_text(encoding="utf-8"))


def _golden_decoded() -> dict:
    return G.decode_matrix(_doc())


_LIVE_CACHE = {}


def _live_decoded() -> dict:
    if "v" not in _LIVE_CACHE:
        _LIVE_CACHE["v"] = G.run_matrix(G.live_namespace())
    return _LIVE_CACHE["v"]


# ═══════════════════════ 黃金檔本身 ═══════════════════════


def test_黃金檔存在且不是空的():
    assert _GOLDEN.is_file()
    assert _GOLDEN.stat().st_size > 100_000


def test_黃金檔本身的sha256釘死():
    assert hashlib.sha256(_GOLDEN.read_bytes()).hexdigest() == _PINNED_SHA256


def test_黃金檔檔頭_基準commit_tree_錄製腳本_直譯器():
    header = _doc()["header"]
    assert header["baseline_commit"] == _BASE_COMMIT
    assert header["baseline_tree"] == _BASE_TREE
    assert header["recorder"] == G.RECORDER_NAME
    assert header["python"].count(".") == 2
    assert set(header["blob_hashes"]) == set(G.FEEDING_FILES)
    assert all(len(v) == 40 and set(v) <= set("0123456789abcdef") for v in header["blob_hashes"].values())
    assert header["counts"] == _EXPECTED_COUNTS


def test_黃金檔位元組可由其內容重新序列化出來_沒有被手改():
    text = _GOLDEN.read_text(encoding="utf-8")
    doc = json.loads(text)
    assert G.dumps(doc) == text


# ═══════════════════════ 主驗收：工作樹 == 黃金檔（不 skip） ═══════════════════════


def test_整份矩陣_工作樹與黃金檔逐位元組相同():
    now = G.dumps(G.encode_matrix(_live_decoded()))
    doc = _doc()
    want = G.dumps({"strings": doc["strings"], "matrix": doc["matrix"]})
    assert now == want


@pytest.mark.parametrize("group,label", [(g, k) for g, labels in (
    ("basis_value", [c[0] for c in G._basis_cases()]),
    ("category_values", [c[0] for c in G._cat_cases()]),
    ("alo2_family", list(G._alo2_cases())),
) for k in labels])
def test_逐情境相同(group, label):
    """整份比對失敗時，逐情境指出是哪一個變了。"""
    got = _live_decoded()[group][label]
    want = _golden_decoded()[group][label]
    assert G.dumps(got) == G.dumps(want)


# ═══════════════════════ 防空掃 ═══════════════════════


def test_情境數量與黃金檔一致_防空掃():
    assert G.counts() == _EXPECTED_COUNTS
    golden = _golden_decoded()
    assert {g: len(v) for g, v in golden.items()} == _EXPECTED_COUNTS
    assert sum(_EXPECTED_COUNTS.values()) == 212
    assert list(golden["basis_value"]) == [c[0] for c in G._basis_cases()]
    assert list(golden["category_values"]) == [c[0] for c in G._cat_cases()]
    assert list(golden["alo2_family"]) == list(G._alo2_cases())


def test_每個目標函式真的被矩陣呼叫到():
    wrapped, hits = G.instrumented_namespace(G.live_namespace())
    G.run_matrix(wrapped)
    assert set(hits) == set(G.TARGET_FUNCTIONS)
    empty = [name for name, n in hits.items() if n == 0]
    assert empty == []
    assert hits["basis_value_with_key"] >= len(G._basis_cases())
    assert hits["basis_value"] >= len(G._basis_cases())
    assert hits["_category_values"] >= 2 * len(G._cat_cases())
    assert hits["_build_alo2"] >= len(G._alo2_cases())
    assert hits["build_page_model"] >= len(G._alo2_cases())


def _iter_results(node):
    """走過黃金檔，收集所有 {"ok":…}／{"raise":…} 結果節點。"""
    if isinstance(node, dict):
        if set(node) in ({"ok"}, {"raise"}):
            yield node
        for v in node.values():
            yield from _iter_results(v)
    elif isinstance(node, list):
        for v in node:
            yield from _iter_results(v)


def test_正常與例外兩支都走到():
    golden = _golden_decoded()
    for group, cases in golden.items():
        kinds = {next(iter(r)) for r in _iter_results(cases)}
        assert kinds == {"ok", "raise"}, group


def test_黃金檔裡有的例外型別_是本頁自己丟的中文訊息與內建型別都有():
    golden = _golden_decoded()
    excs = [r["raise"]["__exc__"] for g in golden.values() for r in _iter_results(g) if "raise" in r]
    types_seen = {e[0] for e in excs}
    assert {"ValueError", "TypeError", "KeyError"} <= types_seen
    assert any(e[1] for e in excs)        # 中文訊息有留
    assert any(e[1] is None for e in excs)  # 內建英文訊息只留型別


# ═══════════════════════ 缺值不是 0 ═══════════════════════


def _basis(label, which="with_key"):
    return _live_decoded()["basis_value"][label][which]["ok"]["__tuple__"]


def test_缺值不是零_缺匯率缺淨值回None與原因_匯率零是真值():
    missing_fx = _basis("mv:fx_missing_usd")
    missing_nav = _basis("mv:nav_missing")
    zero_fx = _basis("mv:fx_zero_is_value_not_missing")
    assert missing_fx[0] is None and missing_fx[1] and missing_fx[2]
    assert missing_nav[0] is None and missing_nav[1] and missing_nav[2]
    assert zero_fx[0] == {"__float__": "0.0"} and zero_fx[1] is None and zero_fx[2] is None
    assert missing_fx[0] != zero_fx[0] and missing_nav[0] != zero_fx[0]


def test_缺值不是零_類別層缺值為None_分母不含缺的類別_已知差異照錄():
    block = _live_decoded()["alo2_family"]["known_diff:usd_missing_twd_valued_twd_100pct"]["alo2"]["ok"]
    rows = {r["_bucket"]: r for r in block["_rows"]}
    assert rows["核心"]["_value"] is None and rows["核心"]["_current_pct"] is None
    assert rows["核心"]["current_text"] != "0.0%"
    # 已知差異（現況，非理想行為）：新臺幣類別分母只含自己 ⇒ 100.0%
    assert rows["衛星"]["_current_pct"] == {"__float__": "100.0"}
    assert block["tail_lines"] == ["合計未涵蓋 核心"]
    assert block["_missing_reasons"] == [rows["核心"]["current_text"]]


def test_缺值不是零_全缺時沒有分母_每一類各寫自己的理由():
    block = _live_decoded()["alo2_family"]["mv:all_missing_mixed_reasons"]["alo2"]["ok"]
    assert block["_no_denominator"] is True
    assert all(r["_value"] is None for r in block["_rows"])
    assert len(block["_missing_reasons"]) == 2
    assert block["placeholder"] is None


# ═══════════════════════ 可選：對照 git 歷史（拿不到就 skip；主驗收不靠它） ═══════════════════════


def _git_show(rel):
    try:
        out = subprocess.run(["git", "show", f"{_BASE_COMMIT}:{rel}"], cwd=_ROOT, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.decode("utf-8") if out.returncode == 0 else None


def test_額外對照_從git歷史的基準原始碼重算_等於黃金檔():
    logic_src = _git_show("ui_v2/alo/logic.py")
    hold_src = _git_show("services/v2_domain/holdings.py")
    if logic_src is None or hold_src is None:
        pytest.skip(f"拿不到 {_BASE_COMMIT}（淺層 clone）；主驗收（整份矩陣逐位元組）不依賴它")
    G.setup_path()
    hold_ns = {"__name__": "_alo_core_golden_orig.holdings", "__package__": "services.v2_domain"}
    exec(compile(hold_src, "<base:holdings>", "exec"), hold_ns)   # noqa: S102 — 只執行 repo 自己的歷史版本
    ns = {"__name__": "_alo_core_golden_orig.logic", "__package__": "ui_v2.alo"}
    exec(compile(logic_src, "<base:logic>", "exec"), ns)          # noqa: S102
    holdings = types.SimpleNamespace(**{k: v for k, v in hold_ns.items() if not k.startswith("__")})
    ns["_v2d"] = types.SimpleNamespace(holdings=holdings)
    ns["exceeds"] = holdings.exceeds
    doc = _doc()
    assert G.dumps(G.encode_matrix(G.run_matrix(ns))) == G.dumps({"strings": doc["strings"], "matrix": doc["matrix"]})
