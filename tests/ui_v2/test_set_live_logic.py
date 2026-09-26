# -*- coding: utf-8 -*-
"""設定與診斷正式模式（`ui_v2/set/source.py` ＋ `ui_v2/set/live.py`）的邏輯測試（fast lane）。

走真的 L2（`services/v2_tables/settings_store`）與真的 L1（`repositories/settings_sheet_repository`），
只把 gspread 換成假試算表（tests/_fake_settings_sheet.py）、把 L1 取數換成替身、把 `st` 換成假物件。
遮蔽用真的 `masking.mask_message`；秘密值一律現場隨機產生（ACCEPTANCE 7.5 末段）。

草稿 = 客戶 2026-09-26 核准的「設定與診斷（SET）正式模式」線框草稿第二版；★n／✂n 為該稿的位置編號。
"""

from __future__ import annotations

import pathlib
import secrets as _rnd
import sys
import types

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "tests"))

from ui_v2.set import fixtures, live, logic  # noqa: E402

source = pytest.importorskip("ui_v2.set.source")  # 需要 L1 的相依（pandas、streamlit 等）

import pandas as pd  # noqa: E402

from _fake_settings_sheet import FakeClient, FakeSpreadsheet  # noqa: E402
from infra import gspread_retry as GR  # noqa: E402
from infra import source_backoff as SB  # noqa: E402
from repositories import settings_sheet_repository as R  # noqa: E402
from services.v2_tables import market_indicator as mi  # noqa: E402
from services.v2_tables import settings_store as S  # noqa: E402
from services.v2_tables.masking import MASK  # noqa: E402

KEY = "k" + _rnd.token_hex(12)                   # 假的 FRED 金鑰（遮蔽對象）
SHEET = "sheet" + _rnd.token_hex(8)              # 假的試算表 ID（遮蔽對象，ACCEPTANCE 7.2 甲）
EMAIL = "sa@example.iam.gserviceaccount.com"


class Book(FakeSpreadsheet):
    title = "客戶的設定本"


@pytest.fixture
def env(monkeypatch):
    book = Book()
    cfg = {"SETTINGS_SHEET_ID": SHEET, "FRED_API_KEY": KEY,
           "google_service_account": {"client_email": EMAIL}}
    monkeypatch.setattr(R, "get_secret", lambda key, default=None: cfg.get(key, default))
    monkeypatch.setattr(R, "_make_client", lambda creds: FakeClient(book))
    monkeypatch.setattr(R, "_TITLES", {})
    monkeypatch.setattr(GR.time, "sleep", lambda _s: None)
    monkeypatch.setattr(source, "st", types.SimpleNamespace(secrets=cfg, session_state={}))
    monkeypatch.setattr(source.market_indicator, "source_cooldowns", lambda: [])
    for name in ("FRED_API_KEY", "SETTINGS_SHEET_ID"):
        monkeypatch.delenv(name, raising=False)
    R.clear_cache()
    SB.reset_all()
    book.cfg = cfg
    yield book
    R.clear_cache()
    SB.reset_all()


def _vix(values=(17.0, 18.5), dates=("2026-09-22", "2026-09-23")):
    s = pd.Series(list(values), index=pd.to_datetime(list(dates)), dtype=float, name="^VIX")
    s.attrs["fetched_at"] = "2026-09-25T06:00:00+00:00"
    return s


def _stub_fetch(monkeypatch, series=None, error=None):
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", lambda ticker, *a, **k: (series, error))


def _page(save_results=None):
    """source.load_live → 與 page.render 正式路徑相同的組裝（不需要 streamlit 執行期）。"""
    data = source.load_live()
    dataset = live.dataset_with_save_results(data["dataset"], save_results)
    model = live.apply_live_notes(logic.build_page_model(dataset), dataset, data["notes"],
                                  save_results=save_results)
    return data, model


def _b(model, code):
    return logic.find_block(model, code)


def _strings(model):
    return "\n".join(logic.collect_ui_strings(model))


# ═══════════════════════ 狀態一：SETTINGS_SHEET_ID 未設（草稿 7.1） ═══════════════════════


def test_ID未設_燈照44外框_其餘位置統一一句_不重複印(env):
    env.cfg.pop("SETTINGS_SHEET_ID")
    data, model = _page()
    assert data["notes"]["gate"]["state"] == "not_configured"
    one = "⛔ 未設定試算表 ID，暫停寫入"
    assert _b(model, "SET-0")["text"] == "⛔ 取數失敗：未設定試算表 ID，暫停寫入"      # `44` 5.5 外框不動
    set1 = {r["_kind_label"]: r for r in _b(model, "SET-1")["_rows"]}
    assert set1["市場指標"]["at_text"] == one
    assert [n["text"] for n in _b(model, "SET-1")["fail_nodes"]] == [one]
    assert _b(model, "SET-2")["placeholder"]["text"] == one
    assert [n["text"] for n in _b(model, "SET-3")["head_lines"]] == [one]              # ★10
    assert _b(model, "SET-3")["placeholder"] is None                                   # 同一句不重複印
    set4 = _b(model, "SET-4")
    assert [n["text"] for n in set4["fail_nodes"]] == [one] and set4["top_lines"] == []
    assert set4["buttons"][0]["_enabled"] is False
    assert set4["buttons"][0]["disabled_reason"] == "未設定試算表 ID，暫停寫入"
    assert _b(model, "SET-6")["placeholder"]["text"] == one
    btn = live.refetch_button("市場指標", data["notes"])
    assert btn["_enabled"] is False and btn["disabled_reason"] == "未設定試算表 ID，暫停寫入"
    assert "取數失敗：未設定試算表 ID" not in _strings(model).replace(_b(model, "SET-0")["text"], "")
    assert SHEET not in _strings(model)


def test_ID未設_說法與L1是同一句():
    assert live.TEXT_NO_SHEET_ID == R.NOT_CONFIGURED_MESSAGE


def test_缺服務帳戶_存檔停用_同一件事只印一行_去重比對錯誤碼(env):
    env.cfg.pop("google_service_account")
    data, model = _page()
    set4 = _b(model, "SET-4")
    assert data["notes"]["table_errors"]["user_setting"]["code"] == "no_service_account"
    assert set4["top_lines"] == []                                  # 讀設定已因同一件事失敗：不再多印
    assert [n["text"] for n in set4["fail_nodes"]] == ["⛔ 取數失敗：未設定服務帳戶（google_service_account）"]
    assert set4["buttons"][0]["disabled_reason"] == "未設定服務帳戶"
    assert live.refetch_button("市場指標", data["notes"])["disabled_reason"] == "未設定服務帳戶"


# ═══════════════════════ 狀態二：讀取失敗且訊息被遮蔽 ═══════════════════════


def test_讀取失敗_訊息遮蔽_各處下一行加已遮蔽憑證(env):
    env.fail_next("open_by_key", ConnectionError(f"GET https://x/{SHEET}?api_key={KEY} refused"), times=4)
    data, model = _page()
    text = _strings(model)
    assert KEY not in text and SHEET not in text and MASK in text
    # 第一次讀（user_setting）失敗後同一本進入冷卻，另兩張表的讀取被冷卻擋下（`50` 第 8 節），訊息是冷卻那一句。
    assert data["notes"]["table_errors"]["fetch_log"]["code"] == "cooling"
    head = [n["text"] for n in _b(model, "SET-3")["head_lines"]]
    assert head[0].startswith("⛔ 讀不到試算表名稱：") and MASK in head[0]              # ★10
    assert head[1] == live.MASKED_NOTE                                                # ★5
    for node in (_b(model, "SET-3")["placeholder"], _b(model, "SET-1")["fail_nodes"][0]):
        assert MASK in node["text"] and [n["text"] for n in node["note_lines"]] == [live.MASKED_NOTE]
    assert [n["text"] for n in _b(model, "SET-2")["placeholder"]["note_lines"]] == []  # 沒遮東西就不出


def test_燈文含遮蔽記號_下一行加已遮蔽憑證_外框照44(env, monkeypatch):
    def broken(values):
        raise R.SettingsSheetError(f"ConnectionError: https://x/{MASK} refused", code="api")
    monkeypatch.setattr(source.settings_store, "load_fetch_log", broken)
    _data, model = _page()
    set0 = _b(model, "SET-0")
    assert set0["text"] == f"⛔ 取數失敗：ConnectionError: https://x/{MASK} refused"
    assert set0["note_lines"] == [live.MASKED_NOTE]


def test_設定試算表冷卻中_SET3與SET4改黃燈暫停_存檔停用(env):
    env.fail_next("open_by_key", Exception("APIError: [429]: Quota exceeded"), times=4)
    with pytest.raises(S.SettingsSheetError):
        S.load_user_settings([])
    data, model = _page()
    assert data["notes"]["gate"]["state"] == "cooling"
    for code in ("SET-3", "SET-4"):
        block = _b(model, code)
        node = block["placeholder"] if code == "SET-3" else block["fail_nodes"][0]
        assert node["_tone"] == "黃" and node["text"].startswith("⚠ 設定試算表暫停重試，約剩 ")
    head = _b(model, "SET-3")["head_lines"]                           # ★10 同一句黃色暫停（B4）
    assert [(n["text"], n["_tone"]) for n in head] == [(_b(model, "SET-3")["placeholder"]["text"], "黃")]
    reason = _b(model, "SET-4")["buttons"][0]["disabled_reason"]
    assert reason.startswith("設定試算表暫停重試，約剩 ") and reason.endswith(" 秒")
    assert live.refetch_button("市場指標", data["notes"])["disabled_reason"] == reason


def test_標頭不符_塊上寫出分頁與兩邊差異(env):
    from _fake_settings_sheet import FakeWorksheet
    env.tabs["fetch_log"] = FakeWorksheet(env, "fetch_log", [["log_id", "tier"]])
    _data, model = _page()
    node = _b(model, "SET-2")["placeholder"]
    assert node["text"] == "⛔ 標頭與規格不符：fetch_log"
    lines = [n["text"] for n in node["note_lines"]]
    assert lines[0].startswith("規格：log_id、source_tier") and lines[1] == "試算表：log_id、tier"


# ═══════════════════════ 狀態三：正常（ID 已設、從 set 頁取過一次） ═══════════════════════


def test_正常_新文案都在_示範字樣都拿掉(env, monkeypatch):
    _stub_fetch(monkeypatch, _vix())
    source.refetch("市場指標")
    S.save_setting_for_page("mkt_window_days", "90", "int", [])
    S.save_setting_for_page("set_max_age_days", "14", "int", [])
    data, model = _page()
    text = _strings(model)
    # ✂2～✂4
    for demo in (logic.HINT_NOTE, "本頁沒有後端"):
        assert demo not in text, demo
    # ★1、★3（三處）
    assert live.TEXT_PENDING_NAV_DIVIDEND in _b(model, "SET-0")["detail_lines"]
    for code in ("SET-0", "SET-2", "SET-6"):
        assert live.TEXT_LOG_SCOPE in _b(model, code)["detail_lines"], code
    # ★2、★4
    set1 = {r["_kind_label"]: r for r in _b(model, "SET-1")["_rows"]}
    for kind in ("淨值", "配息"):
        assert set1[kind]["badges"][0]["text"] == "資料未備" and set1[kind]["at_text"] == "⬜"
        assert set1[kind]["note_lines"] == [live.TEXT_REASON_KIND_PENDING]
    assert set1["市場指標"]["note_lines"] == [live.TEXT_MI_TIME_SCOPE]
    assert set1["市場指標"]["at_text"] == "2026-09-25 14:00"                          # fetched_at 轉 UTC+8
    set2 = {r["_tier"]: r for r in _b(model, "SET-2")["_rows"]}
    for tier in ("淨值", "配息", "其他"):
        assert set2[tier]["note_lines"] == [live.TEXT_REASON_TIER_PENDING], tier
    assert set2["市場指標"]["result_text"] == "ok" and set2["市場指標"]["note_lines"] == []
    # ★10
    assert [n["text"] for n in _b(model, "SET-3")["head_lines"]] == ["設定試算表：客戶的設定本"]
    assert SHEET not in text
    # ★7
    fields = {f["name"]: f for f in _b(model, "SET-4")["inputs"]}
    assert fields["mkt_window_days"]["used_by_text"] == "設定已存，MKT-4 接上後生效"
    assert fields["hld_window_start"]["used_by_text"] is None                          # 未設定：不出 ★7
    assert fields["hld_window_start"]["unset_lines"] == [logic.TEXT_UNSET]
    assert fields["set_max_age_days"]["used_by_text"] == "改這個鍵會影響：SET-1"          # set_ 鍵維持原行
    # ★8 說明行
    assert _b(model, "SET-5")["detail_lines"][-1] == live.TEXT_SET5_NOTE
    assert _b(model, "SET-0")["text"] == logic.TEXT_ALL_OK
    assert logic.scan_forbidden(logic.collect_ui_strings(model)) == {}


def test_星7_多塊以頓號串():
    blocks = dict(fixtures.SPEC_KEY_USED_BY)
    assert live.TEXT_SETTING_PENDING.format(codes="、".join(blocks["hld_window_start"])) == \
        "設定已存，HLD-2、HLD-3、HLD-4、HLD-8 接上後生效"
    assert live.TEXT_SETTING_PENDING.format(codes="、".join(blocks["alo_target_weights"])) == \
        "設定已存，ALO-1、ALO-7 接上後生效"


def test_結構檢查計數_大於0才出(env):
    from _fake_settings_sheet import FakeWorksheet
    head = [n for n, _k, _nl in R.USER_SETTING_SPEC]
    env.tabs["user_setting_log"] = FakeWorksheet(env, "user_setting_log", [
        head, ["set_max_age_days", "14", "int", "2026-09-20T00:00:00Z"],
        ["set_max_age_days", "x", "int", "壞時間"]])
    _data, model = _page()
    assert [n["text"] for n in _b(model, "SET-3")["live_lines"]] == ["⚠ 1 列格式不符，未採用"]
    row = [r for r in _b(model, "SET-3")["_rows"] if r["_key"] == "set_max_age_days"][0]
    assert row["value_text"] == "⚠ 1 列格式不符，未採用"                                 # 不是 ⬜ 未設定
    assert _b(model, "SET-6")["live_lines"] == [] and _b(model, "SET-1")["live_lines"] == []


# ═══════════════════════ 存檔（★6） ═══════════════════════


def _save(env, key, value, kind):
    return {**source.save_setting(key, value, kind), "attempted": value}


def test_存檔成功_已存檔_讀回新值(env):
    result = _save(env, "set_max_age_days", "21", "int")
    assert result["status"] == "saved"
    _d, model = _page({"set_max_age_days": result})
    field = {f["name"]: f for f in _b(model, "SET-4")["inputs"]}["set_max_age_days"]
    assert field["saved_lines"] == ["已存檔"] and field["value_text"] == "21" and field["fail_lines"] == []
    _d, again = _page()                                                              # 下一次互動後消失
    assert {f["name"]: f for f in _b(again, "SET-4")["inputs"]}["set_max_age_days"]["saved_lines"] == []


def test_存檔失敗_403_當下讀設定被冷卻擋下_失敗框掛在塊上_不印上面這一欄(env):
    S.save_setting_for_page("set_max_age_days", "14", "int", [])
    env.fail_next("append_rows", PermissionError(f"no permission on {SHEET}"), title="user_setting_log")
    result = _save(env, "set_max_age_days", "21", "int")
    _d, model = _page({"set_max_age_days": result})
    set4 = _b(model, "SET-4")
    assert set4["inputs"] == []
    assert set4["orphan_fail_lines"] == [[
        "⛔ 存檔寫入失敗：" + result["message"], live.MASKED_NOTE,
        "服務帳戶可能只有檢視權限，需要編輯者"]]                          # 403：根本沒寫，不印「可能其實已寫入」


def test_存檔失敗_403_冷卻過後_失敗框四行加遮蔽註記_輸入留著_SET3不變(env):
    S.save_setting_for_page("set_max_age_days", "14", "int", [])
    env.fail_next("append_rows", PermissionError(f"no permission on {SHEET}"), title="user_setting_log")
    result = _save(env, "set_max_age_days", "21", "int")
    assert result["status"] == "failed" and SHEET not in result["message"]
    SB.reset_all()                                                   # 冷卻結束（60 秒後）再開頁
    _d, model = _page({"set_max_age_days": result})
    field = {f["name"]: f for f in _b(model, "SET-4")["inputs"]}["set_max_age_days"]
    assert field["fail_lines"] == [
        "⛔ 存檔寫入失敗：" + result["message"], live.MASKED_NOTE, logic.TEXT_KEEP_INPUT,
        "服務帳戶可能只有檢視權限，需要編輯者"]
    assert field["value_text"] == "21" and field["saved_lines"] == []
    row = [r for r in _b(model, "SET-3")["_rows"] if r["_key"] == "set_max_age_days"][0]
    assert row["value_text"] == "14"


def test_存檔失敗_404_提示寫出服務帳戶信箱(env):
    class SpreadsheetNotFound(Exception):
        pass
    env.fail_next("open_by_key", SpreadsheetNotFound("not found"), times=4)
    result = _save(env, "set_max_age_days", "21", "int")
    lines = live._save_fail_lines(result, MASK)
    assert lines[-1] == f"請確認試算表 ID，以及已分享給服務帳戶 {EMAIL}"


def test_存檔_冷卻中_失敗框寫冷卻原文_不印可能已寫入(env):
    env.fail_next("open_by_key", Exception("APIError: [429]: Quota exceeded"), times=4)
    with pytest.raises(S.SettingsSheetError):
        S.load_user_settings([])
    result = _save(env, "set_max_age_days", "21", "int")
    assert result["status"] == "failed" and result["code"] == "cooling"
    lines = live._save_fail_lines(result, MASK)
    assert lines[0].startswith("⛔ 存檔寫入失敗：設定試算表暫停重試")
    assert live.TEXT_SAVE_MAYBE_WRITTEN not in lines


def test_存檔_一般失敗才印可能已寫入(env):
    S.save_setting_for_page("set_max_age_days", "14", "int", [])      # 先有標頭列
    env.fail_next("append_rows", ConnectionError("reset by peer"), title="user_setting_log", delivered=True)
    result = _save(env, "set_max_age_days", "21", "int")
    assert result["status"] == "failed" and result["code"] == "api" and result["http_status"] is None
    assert live._save_fail_lines(result, MASK) == [
        "⛔ 存檔寫入失敗：" + result["message"], logic.TEXT_KEEP_INPUT, live.TEXT_SAVE_MAYBE_WRITTEN]
    assert env.data("user_setting_log")[-1][:2] == ["set_max_age_days", "21"]      # 真的可能已寫入


@pytest.mark.parametrize("code, status, hint", [
    ("not_configured", None, None), ("no_service_account", None, None),
    ("header_mismatch", None, None), ("cooling", None, None),
    ("api", 404, None), ("api", 403, None),
    ("api", None, "服務帳戶可能只有檢視權限，需要編輯者"), ("api", None, "請確認試算表 ID，以及已分享給服務帳戶 `x`"),
])
def test_存檔_根本沒寫的失敗不印可能已寫入(code, status, hint):
    result = {"status": "failed", "message": "m", "code": code, "http_status": status, "hint": hint}
    assert live.TEXT_SAVE_MAYBE_WRITTEN not in live._save_fail_lines(result, MASK)


def test_存檔_型別不符_不存_欄位下方型別說明(env):
    S.save_setting_for_page("set_max_age_days", "14", "int", [])
    result = _save(env, "set_max_age_days", "ninety", "int")
    assert result["status"] == "kind_mismatch"
    _d, model = _page({"set_max_age_days": result})
    field = {f["name"]: f for f in _b(model, "SET-4")["inputs"]}["set_max_age_days"]
    assert field["hint_lines"] and field["hint_lines"][0].startswith("型別說明：") and field["fail_lines"] == []
    assert field["value_text"] == "ninety" and field["saved_lines"] == []
    row = [r for r in _b(model, "SET-3")["_rows"] if r["_key"] == "set_max_age_days"][0]
    assert row["value_text"] == "14"                                                  # SET-3 不變
    assert len(env.data("user_setting_log")) == 2                                     # 沒有多寫


def test_存檔_要寫的只有被改的那幾鍵_清空為None():
    inputs = [{"name": "a", "_value": "1", "_kind": "int"}, {"name": "b", "_value": None, "_kind": "int"},
              {"name": "c", "_value": "3", "_kind": "int"}]
    got = live.changed_settings(inputs, {"a": "1", "b": "  ", "c": ""})
    assert got == [("c", None, "int")]


# ═══════════════════════ 重新取數（★8） ═══════════════════════


def test_重新取數按鈕_各狀態停用原因(env, monkeypatch):
    notes = source.load_live()["notes"]
    assert live.refetch_button(None, notes)["disabled_reason"] == "尚未選定來源層級"
    for tier in ("淨值", "配息", "其他"):
        assert live.refetch_button(tier, notes)["disabled_reason"] == "這一層級的取數尚未接上"
    assert live.refetch_button("市場指標", notes)["_enabled"] is True
    cool = dict(notes, source_cooldowns=[{"source": "query1.finance.yahoo.com", "remaining_sec": 41.2},
                                         {"source": "b", "remaining_sec": 3}])
    assert live.refetch_button("市場指標", cool)["disabled_reason"] == \
        "來源冷卻中：query1.finance.yahoo.com，約剩 42 秒，另有 1 個來源冷卻中"
    running = live.refetch_button("市場指標", notes, running=True)
    assert running["_enabled"] is False and running["disabled_reason"] == "取數中：市場指標"


def test_來源冷卻文案與mkt已核准的逐字相同():
    from ui_v2.mkt import live as mkt_live
    for cds in ([], [{"source": "a", "remaining_sec": 5.1}],
                [{"source": "a", "remaining_sec": 5.1}, {"source": "b", "remaining_sec": 80}]):
        assert live.cooldown_reason(cds) == mkt_live.cooldown_reason(cds)


def _lines(result):
    return [n["text"] for n in live.refetch_result_lines(result, MASK)]


def test_取數成功_結果行(env, monkeypatch):
    _stub_fetch(monkeypatch, _vix())
    result = source.refetch("市場指標")
    assert _lines(result) == ["取數完成：市場指標，取回 2 列；結果記在取數紀錄（層 4）"]
    assert "error" not in str(result) or KEY not in str(result)


def test_取數回空_結果行(env, monkeypatch):
    _stub_fetch(monkeypatch, pd.Series([], dtype=float), None)
    result = source.refetch("市場指標")
    assert _lines(result) == ["取數完成：市場指標，回應為空"]
    log = S.load_fetch_log([])["rows"][-1]
    assert log["outcome"] == "ok" and log["row_count"] == 0


def test_取數失敗_遮蔽後與fetch_log_message逐字相同_畫面同一份(env, monkeypatch):
    _stub_fetch(monkeypatch, None, f"HTTPSConnectionPool: /chart?api_key={KEY} refused")
    result = source.refetch("市場指標")
    lines = _lines(result)
    stored = S.load_fetch_log([])["rows"][-1]["message"]
    assert lines == ["⛔ 取數失敗：" + stored, live.MASKED_NOTE]                      # `44` SET-5 判準
    assert KEY not in "".join(lines) and MASK in stored
    _d, model = _page()
    set2 = {r["_tier"]: r for r in _b(model, "SET-2")["_rows"]}["市場指標"]
    assert set2["message_text"] == stored and set2["message_note_lines"] == [live.MASKED_NOTE]
    row6 = _b(model, "SET-6")["_rows"][0]
    assert row6["cells"][6] == stored and row6["cell_notes"] == {6: [live.MASKED_NOTE]}
    assert _b(model, "SET-0")["text"] == "失敗的來源層級：市場指標"


def test_部分失敗_寫表主鍵矛盾_失敗行照fetch_log(env, monkeypatch):
    _stub_fetch(monkeypatch, _vix())
    source.refetch("市場指標")
    _stub_fetch(monkeypatch, _vix(values=(99.0, 18.5)))
    result = source.refetch("市場指標")
    stored = S.load_fetch_log([])["rows"][-1]["message"]
    assert result["log_message"] == stored and "主鍵矛盾 1 筆" in stored
    assert _lines(result) == ["⛔ 取數失敗：" + stored]


def test_寫表失敗_取數紀錄寫入失敗並列(env, monkeypatch):
    _stub_fetch(monkeypatch, _vix())
    env.fail_next("append_rows", ConnectionError(f"reset by peer {SHEET}"), title="market_indicator", times=4)
    result = source.refetch("市場指標")
    assert result["stage"] == "fetch_log"
    lines = _lines(result)
    assert lines[0].startswith("⛔ 取數失敗：market_indicator 寫入失敗：") and MASK in lines[0]
    assert lines[1] == live.MASKED_NOTE
    assert lines[2].startswith("⛔ 取數紀錄寫入失敗：") and SHEET not in lines[2]


@pytest.mark.parametrize("stage", ["fetch_log_open", "fetch_log"])
def test_取數紀錄寫不進去_成功行不說結果記在取數紀錄(stage):
    result = {"tier": "市場指標", "fetched": 3, "log_message": None, "masked_errors": {}, "empty": {},
              "stage": stage, "message": "boom", "ok": False}
    assert [n["text"] for n in live.refetch_result_lines(result, MASK)] == [
        "取數完成：市場指標，取回 3 列", "⛔ 取數紀錄寫入失敗：boom"]


def test_開始紀錄寫不進去_真的取數成功時_成功行只印前半(env, monkeypatch):
    _stub_fetch(monkeypatch, _vix())
    env.fail_next("append_rows", ConnectionError("boom"), title="fetch_log_open", times=4)
    result = source.refetch("市場指標")
    lines = _lines(result)
    assert lines[0] == "取數完成：市場指標，取回 2 列" and "取數紀錄（層 4）" not in "".join(lines)
    assert lines[1].startswith("⛔ 取數紀錄寫入失敗：")


def test_開始紀錄寫不進去_仍顯示取數結果並列寫入失敗(env, monkeypatch):
    _stub_fetch(monkeypatch, None, "HTTP 503 upstream")
    env.fail_next("append_rows", ConnectionError("boom"), title="fetch_log_open", times=4)
    result = source.refetch("市場指標")
    assert result["log_message"] is None and result["stage"] == "fetch_log_open"
    lines = _lines(result)
    assert lines[0] == "⛔ 取數失敗：vol_index: HTTP 503 upstream"
    assert lines[1].startswith("⛔ 取數紀錄寫入失敗：")


def test_未接上的層級_source直接拒絕():
    with pytest.raises(ValueError):
        source.refetch("淨值")


def test_source交出去的東西沒有未遮蔽的原文(env, monkeypatch):
    _stub_fetch(monkeypatch, None, f"api_key={KEY}")
    result = source.refetch("市場指標")
    assert KEY not in repr(result)
    assert set(result) == {"tier", "fetched", "log_message", "masked_errors", "empty", "stage", "message", "ok"}


# ═══════════════════════ 其他守衛 ═══════════════════════


def _full_word_list():
    """與既有原始碼禁詞守衛同一份完整字表（tests/ui_v2/test_set_logic.py::_source_forbidden_words，
    含「建議」「目標價」），另加客戶點名的八個詞。「一鍵」只在按鈕標籤禁（`44` 1.1），
    SET-4 的 `44` 逐字「一鍵一個輸入欄」不是禁詞 —— 故按鈕標籤另掃含「一鍵」的完整按鈕禁詞。"""
    import test_set_logic as guard
    return tuple(dict.fromkeys(guard._source_forbidden_words()
                               + ("最佳", "推薦", "最適", "買進", "賣出", "加碼", "減碼")))


def _live_models(env, monkeypatch):
    """正式模式各狀態的整頁模型（含存檔結果、取數結果行）。"""
    out = []
    _stub_fetch(monkeypatch, _vix())
    source.refetch("市場指標")
    S.save_setting_for_page("mkt_window_days", "90", "int", [])
    out.append(_page()[1])
    _stub_fetch(monkeypatch, None, f"api_key={KEY} refused")
    source.refetch("市場指標")
    results = {"set_max_age_days": {**source.save_setting("set_max_age_days", "x", "int"), "attempted": "x"},
               "alo_basis": {**source.save_setting("alo_basis", "cost", "list"), "attempted": "cost"}}
    out.append(_page(results)[1])
    env.cfg.pop("SETTINGS_SHEET_ID")
    R.clear_cache()
    out.append(_page()[1])
    return out


def test_正式模式整頁畫面字串零禁詞_完整字表(env, monkeypatch):
    words = _full_word_list()
    assert "建議" in words and "目標價" in words and len(words) >= 20
    models = _live_models(env, monkeypatch)
    strings = [s for m in models for s in logic.collect_ui_strings(m)]
    notes = source.load_live()["notes"]
    for tier in (None,) + logic.TIERS:
        strings += logic.collect_ui_strings(live.refetch_button(tier, notes))
    for result in ({"tier": "市場指標", "fetched": 2, "stage": "done"},
                   {"tier": "市場指標", "fetched": 0, "empty": {"vol_index": "x"}, "stage": "done"},
                   {"tier": "市場指標", "fetched": 2, "stage": "fetch_log", "message": "m"}):
        strings += [n["text"] for n in live.refetch_result_lines(result, MASK)]
    strings += [v for k, v in vars(live).items() if k.startswith("TEXT_") and isinstance(v, str)]
    assert len(strings) >= 500
    hits = [(w, s) for s in strings for w in words if w in s]
    assert hits == []
    for button in (b for m in models for b in logic.collect_buttons(m)):
        assert not any(w in button["label"] for w in logic.FORBIDDEN_BUTTON_WORDS), button


def test_禁詞掃描本身會咬_負控():
    words = _full_word_list()
    assert {w for w in words if w in "這裡有建議與目標價，最佳加碼"} == {"目標價", "建議", "最佳", "加碼"}


def test_不帶任何正式模式鍵的模型_logic照舊_fixture模式不受影響():
    for name in fixtures.ALL_SCENARIO_NAMES:
        model = logic.build_page_model(fixtures.scenario(name))
        for key in ("head_lines", "top_lines", "live_lines", "note_lines", "saved_lines", "cell_notes"):
            assert not any(key in node for node in logic._walk(model)), (name, key)


# ═══════════════════════ 2026-09-26 回修：同一秒平手（SET-GAP-同秒平手） ═══════════════════════

def _log(log_id, outcome, finished, started="2026-09-26T03:00:00Z", row_count=None, message=None):
    return {"log_id": log_id, "source_tier": "市場指標", "started_at": started, "finished_at": finished,
            "outcome": outcome, "row_count": row_count if outcome == "ok" else None,
            "message": message if outcome == "failed" else None}


@pytest.mark.parametrize("order", [0, 1])
def test_同一秒平手_失敗優先於成功_不論先後(order):
    ok = _log("a", "ok", "2026-09-26T03:00:05Z", row_count=2)
    bad = _log("b", "failed", "2026-09-26T03:00:01Z", message="boom")
    logs = [ok, bad] if order == 0 else [bad, ok]
    assert logic.latest_per_tier(logs)["市場指標"]["log_id"] == "b"


@pytest.mark.parametrize("order", [0, 1])
def test_同一秒平手_同狀態比結束時間_None視為最新(order):
    early = _log("a", "failed", "2026-09-26T03:00:01Z", message="x")
    late = _log("b", "failed", "2026-09-26T03:00:09Z", message="y")
    open_ = _log("c", "failed", None, message="取數沒有結束紀錄")
    pair = [early, late] if order == 0 else [late, early]
    assert logic.latest_per_tier(pair)["市場指標"]["log_id"] == "b"
    trio = pair + [open_] if order == 0 else [open_] + pair
    assert logic.latest_per_tier(trio)["市場指標"]["log_id"] == "c"


def test_不同秒照舊取較晚開始的():
    old_bad = _log("a", "failed", "2026-09-26T03:00:01Z", message="x")
    new_ok = _log("b", "ok", "2026-09-26T03:00:09Z", started="2026-09-26T03:00:02Z", row_count=1)
    assert logic.latest_per_tier([old_bad, new_ok])["市場指標"]["log_id"] == "b"


def test_同一秒平手_燈照失敗那一筆轉紅():
    dataset = fixtures.scenario("ok")
    dataset["fetch_log"] = [_log("a", "ok", "2026-09-22T03:00:05Z", started="2026-09-22T03:00:00Z", row_count=2),
                            _log("b", "failed", "2026-09-22T03:00:01Z", started="2026-09-22T03:00:00Z",
                                 message="boom")]
    model = logic.build_page_model(dataset)
    assert _b(model, "SET-0")["text"] == "失敗的來源層級：市場指標"


# ═══════════════════════ 2026-09-26 客戶裁示：alo_basis 定為 list（枚舉：成本／市值） ═══════════════════════


def _field(model, key):
    return {f["name"]: f for f in _b(model, "SET-4")["inputs"]}[key]


def test_alo_basis_正式模式型別為list_單行輸入欄(env):
    _d, model = _page()
    field = _field(model, "alo_basis")
    assert field["_kind"] == "list" and field["_multiline"] is False and field["label"] == "alo_basis（list）"
    row = [r for r in _b(model, "SET-3")["_rows"] if r["_key"] == "alo_basis"][0]
    assert row["kind_text"] == "list"


@pytest.mark.parametrize("value", ["成本", "市值"])
def test_alo_basis_兩個可選值照存_讀回照印(env, value):
    result = _save(env, "alo_basis", value, "list")
    assert result["status"] == "saved" and result["row"]["setting_value"] == value
    _d, model = _page({"alo_basis": result})
    assert _field(model, "alo_basis")["saved_lines"] == [live.TEXT_SAVED]
    row = [r for r in _b(model, "SET-3")["_rows"] if r["_key"] == "alo_basis"][0]
    assert row["value_text"] == value.strip() and row["raw_text"] == ""


@pytest.mark.parametrize("value", ["cost", "mv", '["成本"]', "成本、市值", "成 本", "市值 成本", " 市值", "成本\n"])
def test_alo_basis_其他值一律型別不符_不寫_畫可選值說明(env, value):
    result = _save(env, "alo_basis", value, "list")
    assert result["status"] == "kind_mismatch"
    assert "user_setting_log" not in env.tabs
    _d, model = _page({"alo_basis": result})
    assert _field(model, "alo_basis")["hint_lines"] == [
        "型別說明：這個鍵的 value_kind 是 list，可選值：成本、市值。" + logic.TEXT_NOT_SAVED]
    assert "要輸入其中之一" not in _strings(model)


def test_alo_basis_試算表上已存的舊值不在可選值內_SET3照印型別不符(env):
    from _fake_settings_sheet import FakeWorksheet
    head = [n for n, _k, _nl in R.USER_SETTING_SPEC]
    env.tabs["user_setting_log"] = FakeWorksheet(env, "user_setting_log", [
        head, ["alo_basis", "cost", "list", "2026-09-20T00:00:00Z"]])
    _d, model = _page()
    row = [r for r in _b(model, "SET-3")["_rows"] if r["_key"] == "alo_basis"][0]
    assert row["value_text"] == logic.TEXT_NA_BAD_KIND and row["raw_text"] == "原始字面值：cost"


def test_示範模式_alo_basis仍放空_畫面不變():
    model = logic.build_page_model(fixtures.scenario("ok"))
    row = [r for r in _b(model, "SET-3")["_rows"] if r["_key"] == "alo_basis"][0]
    assert row["kind_text"] == "⬜" and row["value_text"] == "cost"
    assert dict(fixtures.SPEC_SETTING_KEYS)["alo_basis"] is None


def test_正式模式不再有型別未定的鍵():
    from ui_v2.set import spec
    kinds = dict(spec.dataset_spec(live=True)["setting_keys"])
    assert None not in kinds.values() and kinds["alo_basis"] == "list"



def test_存檔_比對原值不strip_前後帶空白算改過_只有空白算清除():
    inputs = [{"name": "a", "_value": "1", "_kind": "int"}, {"name": "b", "_value": "2", "_kind": "int"},
              {"name": "c", "_value": "3", "_kind": "int"}, {"name": "d", "_value": "4", "_kind": "int"}]
    got = live.changed_settings(inputs, {"a": " 1 \n", "b": "\t3 ", "c": "   ", "d": "4"})
    assert got == [("a", " 1 \n", "int"), ("b", "\t3 ", "int"), ("c", None, "int")]


def test_存檔_前後帶空白_型別不符不存_型別說明照既有模板(env):
    S.save_setting_for_page("set_max_age_days", "14", "int", [])
    result = _save(env, "set_max_age_days", " 30 ", "int")
    assert result["status"] == "kind_mismatch"
    assert env.data("user_setting_log")[-1][:2] == ["set_max_age_days", "14"]      # 沒有多寫
    _d, model = _page({"set_max_age_days": result})
    field = _field(model, "set_max_age_days")
    assert field["value_text"] == " 30 "                                          # 輸入欄內容逐字留著
    assert field["hint_lines"] == [
        f"型別說明：這個鍵的 value_kind 是 int，{logic.KIND_HINTS['int']}。{logic.TEXT_NOT_SAVED}"]
