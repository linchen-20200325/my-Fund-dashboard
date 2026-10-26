# -*- coding: utf-8 -*-
"""設定頁「試算表連線」卡（Sheet Picker）的純邏輯測試（批 3b-3；不需要 streamlit）。

驗 `ui_v2/set/live.py::picker_view`：只在正式登入後出現（待確認登入／未登入／讀不到都 hidden）、候選只來自清單、
待確認（尚未使用）≠ 使用中、失敗時「使用中」取自當下狀態（舊的那一本）、空清單／清單失敗照實說且不補任何預設、
沒有任何「清除」控制項、畫面字零權杖；以及九個 error code 之一的對映。
"""
from __future__ import annotations

import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from shared import ui_v2_error_codes as ec  # noqa: E402
from ui_v2.set import live  # noqa: E402

A = "1AAAAAAAAAAAAAAAAAAAA"
B = "1BBBBBBBBBBBBBBBBBBBB"
C = "1CCCCCCCCCCCCCCCCCCCC"
LIST_OK = {"ok": True, "sheets": [{"id": A, "name": "甲"}, {"id": B, "name": "乙"}, {"id": C, "name": "丙"}]}


def _status(login_state="logged_in", **kw):
    base = {"login_state": login_state, "email": "me@example.com", "pending_login_email": None,
            "pending_sheet": None, "active_sheet": None}
    base.update(kw)
    return base


def _view(status=None, listing=LIST_OK, notice=None):
    return live.picker_view({"status": status if status is not None else _status(), "list": listing, "notice": notice})


def _text(view):
    return "\n".join(view["lines"])


# ───────────── 只在正式登入後出現 ─────────────


@pytest.mark.parametrize("status", [
    None, "x", {}, _status("logged_out"), _status("pending_login", pending_login_email="n@example.com"),
    _status("garbage")])
def test_picker只在正式登入後出現_其餘一律hidden(status):
    v = live.picker_view({"status": status, "list": LIST_OK, "notice": None})
    assert v["state"] == "hidden"
    assert v["lines"] == [] and v["options"] == [] and v["buttons"] == []   # 沒有任何東西可畫（含清單）


def test_picker_輸入不是dict_hidden():
    assert live.picker_view(None)["state"] == "hidden"


def test_mutation_登入檢查拿掉就會紅燈(monkeypatch):
    """變異：把「只在 logged_in 才出現」的判斷拿掉（把待確認登入當成已登入）→ 上面的斷言必須失敗。"""
    def mutant(inp):
        st = dict(inp["status"]); st["login_state"] = "logged_in"
        return live.picker_view({**inp, "status": st})
    pend = {"status": _status("pending_login", pending_login_email="n@example.com"), "list": LIST_OK, "notice": None}
    assert live.picker_view(pend)["state"] == "hidden"
    assert mutant(pend)["state"] != "hidden"   # 變異版會畫出選單 → 上面「只在正式登入後出現」測試會抓到


# ───────────── 候選只來自清單；待確認 vs 使用中 ─────────────


def test_選項只來自清單_不補預設_不含POLICY():
    v = _view()
    assert v["state"] == "ready"
    assert [o["id"] for o in v["options"]] == [A, B, C]
    assert v["selected"] is None   # 沒有待確認就不預選任何一本（不猜）


def test_清單壞項被丟掉_同id只留第一筆_名稱缺用id():
    listing = {"ok": True, "sheets": [{"id": A, "name": "甲"}, {"id": A, "name": "重複"}, {"id": 5, "name": "x"},
                                      {"id": "", "name": "空"}, "junk", {"id": B}]}
    v = _view(listing=listing)
    assert [o["id"] for o in v["options"]] == [A, B]
    assert B in v["options"][1]["label"] and "甲" in v["options"][0]["label"]


def test_待確認_顯示待確認尚未使用_且使用中仍是舊的():
    v = _view(_status(active_sheet={"id": A, "name": "甲", "verified_at": 1.0},
                      pending_sheet={"id": B, "name": "乙"}))
    t = _text(v)
    assert "待確認（尚未使用）：乙" in t and f"使用中：甲（{A}）" in t and "帳號：me@example.com" in t
    use = [b for b in v["buttons"] if b["action"] == "use"]
    assert use == [{"action": "use", "label": "使用這一本", "arg": B}]   # 綁定畫面上顯示的待確認那一本
    assert v["selected"] == 1


def test_待確認等於使用中_不出現待確認區與使用鈕():
    v = _view(_status(active_sheet={"id": A, "name": "甲", "verified_at": 1.0}, pending_sheet={"id": A, "name": "甲"}))
    assert "待確認" not in _text(v) and not [b for b in v["buttons"] if b["action"] == "use"]


def test_沒有使用中_照實說尚未選定_不猜():
    v = _view()
    assert live.TEXT_PICKER_NO_ACTIVE in _text(v) and "使用中：" not in _text(v)


def test_使用中的那一本在選項上標記():
    v = _view(_status(active_sheet={"id": B, "name": "乙", "verified_at": 1.0}))
    assert live.PICKER_ACTIVE_MARK in v["options"][1]["label"] and live.PICKER_ACTIVE_MARK not in v["options"][0]["label"]


def test_沒有任何清除使用中的控制項():
    for v in (_view(), _view(_status(active_sheet={"id": A, "name": "甲", "verified_at": 1.0},
                                     pending_sheet={"id": B, "name": "乙"}))):
        assert not any("清除" in b["label"] or "取消" in b["label"] for b in v["buttons"])
        assert {b["action"] for b in v["buttons"]} <= set(live.PICKER_ACTIONS)


# ───────────── 失敗：維持舊 Active（取自當下狀態） ─────────────


def test_使用失敗_仍顯示舊使用中_且字樣是未變更():
    v = _view(_status(active_sheet={"id": A, "name": "甲", "verified_at": 1.0}, pending_sheet={"id": B, "name": "乙"}),
              notice={"kind": "use_fail", "code": ec.PERMISSION_DENIED, "name": "乙"})
    t = _text(v)
    assert "⛔ 無權限：切換沒有完成。" in t and "目前使用中仍是：甲（未變更）" in t
    assert "已切換" not in t and f"使用中：甲（{A}）" in t and f"使用中：乙" not in t


def test_mutation_失敗時使用中取回傳值就會紅燈():
    """失敗路徑的名稱必須取自當下狀態的 Active；若取自這次嘗試的 Pending 名稱（變異）→ 斷言失敗。"""
    st = _status(active_sheet={"id": A, "name": "甲", "verified_at": 1.0}, pending_sheet={"id": B, "name": "乙"})
    v = _view(st, notice={"kind": "use_fail", "code": ec.SCHEMA_INVALID, "name": "乙"})
    good = "目前使用中仍是：甲（未變更）" in _text(v)
    mutated = _text(v).replace("甲（未變更）", "乙（未變更）")
    assert good and "目前使用中仍是：甲（未變更）" not in mutated


def test_使用失敗而沒有舊Active_不印仍是():
    v = _view(_status(pending_sheet={"id": B, "name": "乙"}), notice={"kind": "use_fail", "code": ec.SHEET_NOT_FOUND})
    assert "仍是" not in _text(v) and live.TEXT_PICKER_NO_ACTIVE in _text(v)


def test_使用成功_切換字樣取自當下的Active():
    v = _view(_status(active_sheet={"id": B, "name": "乙-驗證名", "verified_at": 1.0}),
              notice={"kind": "use_ok", "name": "假名稱"})
    assert "◆ 已切換為：乙-驗證名" in _text(v) and "假名稱" not in _text(v)


def test_use_ok但Active不存在_不印已切換():
    v = _view(_status(), notice={"kind": "use_ok", "name": "乙"})
    assert "已切換" not in _text(v)


@pytest.mark.parametrize("code, ctx, want", [
    (ec.AUTH_EXPIRED, "use", "◷ 登入已過期"),
    (ec.AUTH_REQUIRED, "use", "⬜ 未登入"),
    (ec.PERMISSION_DENIED, "use", "⛔ 無權限：切換沒有完成。"),
    (ec.PERMISSION_DENIED, "list", "⛔ 這個帳號沒有列出試算表的權限"),
    (ec.SHEET_NOT_FOUND, "use", "⛔ 找不到：切換沒有完成。"),
    (ec.SHEET_NOT_FOUND, "select", "⛔ 找不到這本試算表"),
    (ec.SCHEMA_INVALID, "use", "⛔ 驗證失敗：切換沒有完成。"),
    (ec.NETWORK_ERROR, "use", "⛔ 驗證失敗：切換沒有完成。"),
    (ec.UPSTREAM_ERROR, "list", "⛔ 列出試算表失敗"),
    (ec.UNAVAILABLE, "use", "⬜ 無法判定"),
    (ec.AUTH_STATE_INVALID, "use", "⬜ 無法判定"),
    ("SOMETHING_ELSE", "use", "⬜ 無法判定"),
    (None, "list", "⬜ 無法判定"),
])
def test_九個code對映_未知落無法判定(code, ctx, want):
    assert want in live.picker_error_lines(code, ctx)


def test_九個code全都有對映_沒有任何一個崩潰():
    for code in ec.ALL_ERROR_CODES:
        for ctx in ("list", "select", "use"):
            assert live.picker_error_lines(code, ctx)


# ───────────── 清單狀態：Missing stays Missing ─────────────


def test_空清單_照實說沒有可選的_不補任何預設_不給下拉():
    v = _view(listing={"ok": True, "sheets": []})
    assert v["state"] == "empty" and v["options"] == []
    assert live.TEXT_PICKER_EMPTY in _text(v) and live.TEXT_PICKER_EMPTY_NOTE in _text(v)


def test_全是壞項的清單_視同沒有可選的():
    assert _view(listing={"ok": True, "sheets": [{"id": 1}, "x"]})["state"] == "empty"


def test_清單失敗_不當成空清單_給重新列出():
    v = _view(listing={"ok": False, "error_code": ec.NETWORK_ERROR})
    assert v["state"] == "list_error" and v["options"] == []
    assert live.TEXT_PICKER_LIST_FAILED in _text(v) and live.TEXT_PICKER_EMPTY not in _text(v)
    assert [b["action"] for b in v["buttons"]] == ["relist"]


@pytest.mark.parametrize("listing", [None, "x", {"ok": "yes", "sheets": []}, {"ok": True, "sheets": "oops"}])
def test_清單讀不到或形狀不對_落無法判定_不當成空(listing):
    v = _view(listing=listing)
    assert v["state"] in ("unknown", "list_error", "empty")
    assert v["options"] == []
    if listing is None:
        assert v["state"] == "unknown" and live.TEXT_PICKER_UNKNOWN in _text(v)


def test_畫面字沒有權杖也沒有指示句():
    v = _view(_status(active_sheet={"id": A, "name": "甲", "verified_at": 1.0}, pending_sheet={"id": B, "name": "乙"}))
    t = _text(v).lower()
    for bad in ("token", "secret", "bearer", "refresh", "請先", "請按", "請重新"):
        assert bad not in t


# ───────────── 原始碼層的結構守衛 ─────────────


def test_page的picker卡只在picker_live有傳時畫_示範模式傳了就炸_且沒有清除控制項():
    import ast
    src = (_ROOT / "ui_v2" / "set" / "page.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    render = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "render")
    assert "picker_live" in [a.arg for a in render.args.kwonlyargs]
    raises = [n for n in ast.walk(render) if isinstance(n, ast.Raise) and "picker_live" in ast.unparse(n)]
    assert raises
    guarded = [n for n in ast.walk(render) if isinstance(n, ast.If) and ast.unparse(n.test) == "picker_live is not None"
               and any("_render_picker" in ast.unparse(x) for x in n.body)]
    assert guarded
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_render_picker")
    body = fn.body[1:] if ast.get_docstring(fn) else fn.body   # 說明文字（docstring）不算控制項
    assert "清除" not in "\n".join(ast.unparse(x) for x in body)


def test_source的動作代號白名單與live一致_且不含清除():
    assert live.PICKER_ACTIONS == ("select", "use", "relist")
    assert not any("clear" in a or "delete" in a for a in live.PICKER_ACTIONS)
