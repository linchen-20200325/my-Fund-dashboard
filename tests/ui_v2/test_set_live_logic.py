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


def test_缺服務帳戶_存檔停用_頂端一行(env):
    env.cfg.pop("google_service_account")
    data, model = _page()
    set4 = _b(model, "SET-4")
    assert [n["text"] for n in set4["top_lines"]] == ["⛔ 未設定服務帳戶"]
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
        "未存檔。這次可能其實已寫入，請先重新整理本頁確認，再決定要不要重存",
        "服務帳戶可能只有檢視權限，需要編輯者"]]


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
        "未存檔。這次可能其實已寫入，請先重新整理本頁確認，再決定要不要重存",
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


def test_存檔_冷卻中_失敗框寫冷卻原文(env):
    env.fail_next("open_by_key", Exception("APIError: [429]: Quota exceeded"), times=4)
    with pytest.raises(S.SettingsSheetError):
        S.load_user_settings([])
    result = _save(env, "set_max_age_days", "21", "int")
    assert result["status"] == "failed" and result["code"] == "cooling"
    assert live._save_fail_lines(result, MASK)[0].startswith("⛔ 存檔寫入失敗：設定試算表暫停重試")


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


def test_正式模式文案零禁詞():
    words = ("一鍵", "最佳", "推薦", "最適", "買進", "賣出", "加碼", "減碼") + logic.FORBIDDEN_DIRECTION_WORDS \
        + logic.FORBIDDEN_ADVICE_WORDS + logic.FORBIDDEN_ARROWS
    texts = [v for k, v in vars(live).items() if k.startswith("TEXT_") or k == "MASKED_NOTE"]
    assert len(texts) >= 25
    for text in texts:
        for word in words:
            assert word not in text, (text, word)


def test_不帶任何正式模式鍵的模型_logic照舊_fixture模式不受影響():
    for name in fixtures.ALL_SCENARIO_NAMES:
        model = logic.build_page_model(fixtures.scenario(name))
        for key in ("head_lines", "top_lines", "live_lines", "note_lines", "saved_lines", "cell_notes"):
            assert not any(key in node for node in logic._walk(model)), (name, key)
