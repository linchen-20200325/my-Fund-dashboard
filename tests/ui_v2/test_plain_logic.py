# -*- coding: utf-8 -*-
"""一般畫面去工程化（Phase 3 P0-①）`ui_v2/plain.py` 的純函式測試（fast lane；不需要 streamlit）。

依據 `docs/v2/44_fund_ui_ssot.md` 第七節第三小節之七其二（`DEC-2026-10-17-03`）與護欄 2（只改呈現，不改判定）：

1. 鏡像常數逐字等於舊樹真身（AST 讀檔，不 import 舊樹）；ui_v2 內的失敗字首逐字等於各頁真身。
2. 對照表沒有缺、沒有多、沒有死條目。
3. **不變式**：五頁全部 fixtures 情境（示範模型＋可在本機組出的正式模型），`plain_model` 前後
   `_` 開頭鍵的純量值、`code`、`name`、所有數值與布林、塊數、每一張串列的長度**深度相等**；輸入模型不被改動。
   唯一的例外是持倉體檢的 `PRINT_AS_IS_LINE`（原文移出一般畫面後那句話成了假話），比對前兩邊都先拿掉。
4. 不是最新／預存序列那一類句子原樣保留。
5. `record_raw` 整格覆寫、清空；`RAW_STATE` 不在預覽入口換頁要清的清單裡。
"""

from __future__ import annotations

import ast
import copy
import datetime
import json
import pathlib
import re
import sys

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE))

from ui_v2 import plain  # noqa: E402
from ui_v2.set import spec  # noqa: E402

# ───────────────────────── 1. 鏡像常數 ─────────────────────────


def _module_constant(relpath: str, name: str):
    """以 AST 讀出模組層 `NAME = <字面值>`（不 import 舊樹，免得把 gspread／pandas 拉進 fast lane）。"""
    tree = ast.parse((_ROOT / relpath).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{relpath} 找不到 {name}")


@pytest.mark.parametrize(
    "mirror, relpath, name",
    [
        ("MSG_SETTINGS_NOT_CONFIGURED", "repositories/settings_sheet_repository.py", "NOT_CONFIGURED_MESSAGE"),
        ("MSG_NO_SERVICE_ACCOUNT", "repositories/settings_sheet_repository.py", "NO_SERVICE_ACCOUNT_MESSAGE"),
        ("MSG_NO_SERVICE_ACCOUNT", "repositories/policy_supplement_repository.py", "NO_SERVICE_ACCOUNT_MESSAGE"),
        ("MSG_POLICY_NOT_CONFIGURED", "repositories/policy_supplement_repository.py", "NOT_CONFIGURED_MESSAGE"),
        ("MSG_FRED_MISSING", "services/v2_tables/market_indicator.py", "MISSING_FRED_API_KEY"),
        ("MSG_POOL_NOT_CLOUD", "services/v2_tables/exp_universe.py", "TEXT_NOT_CLOUD"),
    ],
)
def test_鏡像常數逐字等於舊樹真身(mirror, relpath, name):
    assert getattr(plain, mirror) == _module_constant(relpath, name)


def test_失敗字首逐字等於五頁真身():
    from ui_v2.alo import logic as alo
    from ui_v2.exp import logic as exp
    from ui_v2.hld import live as hld_live
    from ui_v2.hld import logic as hld
    from ui_v2.mkt import live as mkt_live
    from ui_v2.mkt import logic as mkt
    from ui_v2.set import logic as set_logic

    for module in (mkt, hld, alo):
        assert module.fetch_failed_text("") == plain.FETCH_FAIL_PREFIX, module.__name__
    assert exp.fetch_failed_text("") == plain.FETCH_FAIL_PREFIX
    assert set_logic.fetch_failed_text("") == plain.FETCH_FAIL_PREFIX
    assert mkt.TEXT_SETTINGS_UNREADABLE_PREFIX == plain.SETTINGS_UNREADABLE_PREFIX
    assert mkt_live.TEXT_SAVE_FAILED == hld_live.TEXT_SAVE_FAILED == plain.SAVE_FAIL_PREFIX
    assert hld.PRINT_AS_IS_LINE == plain.PRINT_AS_IS_LINE


# ───────────────────────── 2. 對照表 ─────────────────────────


def _demo_models():
    """五頁全部示範情境的模型：{(頁, 情境): 模型}。"""
    from ui_v2.alo import fixtures as AF
    from ui_v2.alo import logic as A
    from ui_v2.exp import fixtures as EF
    from ui_v2.exp import logic as E
    from ui_v2.hld import fixtures as HF
    from ui_v2.hld import logic as H
    from ui_v2.mkt import fixtures as MF
    from ui_v2.mkt import logic as M
    from ui_v2.set import fixtures as SF
    from ui_v2.set import logic as S

    out = {}
    for name, dataset in MF.all_datasets().items():
        out[("mkt", name)] = M.build_page_model(dataset)
    for name in HF.ALL_SCENARIO_NAMES:
        out[("hld", name)] = H.build_page_model(**HF.scenario(name))
    for name in EF.ALL_SCENARIO_NAMES:
        for failed in (False, True):
            params = EF.scenario_with(name, save_failed=failed)
            out[("exp", f"{name}/{failed}")] = E.build_page_model(
                params["dataset"], draft_rules=params.get("draft_rules"),
                compare_checked=params.get("compare_checked", ()), watch_checked=params.get("watch_checked", ()),
                save_failed=failed,
            )
    for name in AF.ALL_SCENARIO_NAMES:
        for failed in (False, True):
            out[("alo", f"{name}/{failed}")] = A.build_page_model(AF.scenario_with(name, save_failed=failed))
    for name in SF.ALL_SCENARIO_NAMES:
        for failed in (False, True):
            out[("set", f"{name}/{failed}")] = S.build_page_model(SF.scenario_with(name, save_failed=failed))
    return out


_PAGE_OF = {"MKT": "mkt", "HLD": "hld", "EXP": "exp", "ALO": "alo", "SET": "set"}


def test_塊名逐字等於五頁logic的標題_沒有缺也沒有多():
    seen = {}
    for (_page, _name), model in _demo_models().items():
        for block in model["blocks"]:
            seen.setdefault(block["code"], set()).add(block["title"])
    assert {code: {title} for code, title in plain.BLOCK_NAMES.items()} == seen


def test_表名欄名設定鍵_與規格快照一一對應():
    assert set(plain.TABLE_NAMES) == {table for table, _ in spec.SPEC_TABLES}
    assert set(plain.COLUMN_NAMES) == {column for _, columns in spec.SPEC_TABLES for column in columns}
    assert set(plain.SETTING_NAMES) == {key for key, _ in spec.SPEC_SETTING_KEYS}


def test_指標中文名逐字等於市場總覽核心卡():
    from ui_v2.mkt import logic as M

    card = {key: label for specs in M._CARD_SPECS.values() for key, label, *_ in specs}
    assert {k: plain.INDICATOR_NAMES[k] for k in card} == card
    assert set(plain.INDICATOR_NAMES) - set(card) == {"term_spread_pct"}


def _ui_v2_source() -> str:
    paths = sorted(p for p in (_ROOT / "ui_v2").rglob("*.py") if p.name != "plain.py")
    return "\n".join(p.read_text(encoding="utf-8") for p in paths)


def test_對照表沒有死條目_每一條都在ui_v2原始碼裡逐字出現():
    source = _ui_v2_source()
    dead = [k for k in list(plain.EXACT_LABELS) + list(plain.EXTRA_KEY_NAMES) + list(plain.INDICATOR_NAMES)
            if k not in source]
    assert dead == []


def test_中文名沒有一個還帶英文鍵名():
    token = re.compile(r"[A-Za-z_]{3,}")
    for table in (plain.KEY_NAMES, plain.EXACT_LABELS, plain.BLOCK_NAMES):
        assert [v for v in table.values() if token.search(v)] == []


def test_key_name給下拉選單用_欄位鍵都有中文名_未知值原樣():
    from ui_v2.exp import logic as E

    for field in E.FUND_PROFILE_FIELDS:
        assert plain.key_name(field) != field
    assert plain.key_name("最近淨值（nav_orig_ccy，原幣）") == "最近淨值（原幣）"
    assert plain.key_name("基金名") == "基金名"
    assert plain.key_name("not_a_known_key") == "not_a_known_key"
    assert plain.key_name(None) == ""
    assert plain.key_name("fx_twd_per_eur") == "新臺幣對EUR匯率"


# ───────────────────────── 3. 不變式 ─────────────────────────


def _live_models():
    """可以不經 streamlit、不打網路組出的正式模型：{(頁, 情境): 模型}。"""
    from ui_v2.alo import fixtures as AF
    from ui_v2.alo import live as AL
    from ui_v2.alo import logic as A
    from ui_v2.hld import fixtures as HF
    from ui_v2.hld import live as HL
    from ui_v2.mkt import fixtures as MF
    from ui_v2.mkt import live as ML

    out = {}
    notes = {
        "pending": {"leading_index": "ndc_no_release_date", "coincident_index": "ndc_no_release_date",
                    "fx_twd_per_usd": "fx_obs_date_rule"},
        "masked_keys": [], "cooldowns": [],
        "available_keys": ["vol_index", "credit_spread_pct", "term_spread_pct", "policy_rate_pct"],
        "settings": {"window_days": 30, "baseline_date": "2026-08-01",
                     "indicator_keys": ["vol_index", "credit_spread_pct"], "pair_consistent": True},
        "settings_error": None,
    }
    datasets = dict(MF.all_datasets())
    datasets["unconf"] = {"rows": [], "errors": {"vol_index": "fetch_url returned None: ^VIX (kind=unreachable)",
                                                  "credit_spread_pct": plain.MSG_FRED_MISSING}}
    for name, dataset in datasets.items():
        out[("mkt", name)] = ML.build_live_model({"dataset": dataset, "notes": notes}, save_wired=True)
        broken = dict(notes, settings_error=plain.MSG_SETTINGS_NOT_CONFIGURED,
                      settings={"window_days": None, "baseline_date": None, "indicator_keys": None,
                                "pair_consistent": None})
        out[("mkt", name + "/settingfail")] = ML.build_live_model(
            {"dataset": dataset, "notes": broken}, save_wired=True,
            save_results={"mkt_window_days": "連線逾時（示意）", "mkt_indicator_keys": None})
    for name in HF.ALL_SCENARIO_NAMES:
        args = copy.deepcopy(HF.scenario(name))
        for holding in args["dataset"]["holding"]:
            if holding["policy_id"] == "DIRECT":
                holding["policy_id"] = "P-001"
        codes = {row["fund_code"] for row in args["dataset"]["nav"]}
        for days in (10, 21):
            prov = {code: {"cache_fallback": code == "AAAA", "stale": None} for code in codes}
            try:
                out[("hld", f"{name}/{days}")] = HL.build_live_model(
                    **args, today=datetime.date(2026, 9, 18) + datetime.timedelta(days=days),
                    direct_policy_id="DIRECT", nav_provenance=prov)
            except (ValueError, TypeError):
                continue   # 這一組情境在正式路徑本來就畫整頁錯誤畫面（不經 plain_model）
    for name in AF.ALL_SCENARIO_NAMES:
        out[("alo", name)] = AL.apply_live_notes(A.build_page_model(AF.scenario(name)))
    import _exp_live_stub as STUB
    from ui_v2.exp import live as EL

    for wired in (False, True):
        for read_error in (None, plain.MSG_SETTINGS_NOT_CONFIGURED):
            STUB.reset()
            if wired:
                STUB.WIRED.append(True)
            STUB.STORE["exp_filter_rules"] = json.dumps(
                [{"field": "fund_code", "op": "不等於", "value": "ZZZ"}], ensure_ascii=False)
            if read_error:
                STUB.READ_ERROR.append(read_error)
            out[("exp", f"{wired}/{read_error}")] = EL.build_live_model(STUB.load_live(), save_wired=True)
    STUB.reset()
    return out


_ALL = None


def _all_models():
    global _ALL
    if _ALL is None:
        _ALL = {**{("demo",) + k: v for k, v in _demo_models().items()},
                **{("live",) + k: v for k, v in _live_models().items()}}
    return _ALL


# 值會被程式拿去比對、查表、寫出的鍵：字串也要逐字相同（本檔獨立列一份，不引用 plain 自己的清單）。
_VERBATIM_KEYS = frozenset({"code", "name", "options", "sort_options", "tier_options", "basis_option_labels",
                            "file_name", "sort_shown"})


def _projection(node, page, private=False):
    """判定與結構的投影：字串只留位置（`<s>`），其餘照原值；`_` 開頭鍵、`code`、`name`、選項清單、
    `*_keys` 鍵名清單、輸入欄的當下值（`value_text`）的字串照原字。"""
    if isinstance(node, dict):
        out = {}
        is_input = "name" in node and "label" in node
        for key, value in node.items():
            keep = isinstance(key, str) and (key.startswith("_") or key in _VERBATIM_KEYS or key.endswith("_keys")
                                             or (key == "value_text" and is_input))
            out[key] = _projection(value, page, keep)   # dict 的一般鍵重新起算（同 plain._walk）
        return out
    if isinstance(node, (list, tuple)):
        items = [item for item in node if not (page == "hld" and item == plain.PRINT_AS_IS_LINE)]
        return [type(node).__name__] + [_projection(item, page, private) for item in items]
    if isinstance(node, str):
        return node if private else "<s>"
    return node


def test_不變式_判定與結構深度相等_輸入不被改動():
    count = {}
    for key, model in _all_models().items():
        page = key[1]
        before = copy.deepcopy(model)
        display, raw, status = plain.plain_model(model, page=page)
        assert model == before, key                         # 深拷貝：輸入一個字都沒動
        assert _projection(display, page) == _projection(model, page), key
        assert len(display["blocks"]) == len(model["blocks"]), key
        assert isinstance(raw, list) and status["raw_count"] == len(raw)
        count[(key[0], page)] = count.get((key[0], page), 0) + 1
    # 覆蓋面：每一頁兩種模式都真的跑到（正式模式只有 set 在本機組不出來，那一頁由畫面測試蓋）
    for mode, page in (("demo", p) for p in plain.PAGE_NAMES):
        assert count.get((mode, page), 0) >= 5, (mode, page, count)
    for page in ("mkt", "hld", "exp", "alo"):
        assert count.get(("live", page), 0) >= 4, (page, count)


# `reason_text` 是 logic 內部拿來組失敗行的中間值（畫面層不讀它：見 `test_畫面層不讀reason_text`），
# 掃「畫面上會出現的字」時不算它。
_NOT_RENDERED = frozenset({"reason_text"})


def _strings(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key not in _NOT_RENDERED:
                yield from _strings(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _strings(item)
    elif isinstance(node, str):
        yield node


def test_畫面層不讀reason_text():
    for page in plain.PAGE_NAMES:
        assert "reason_text" not in (_ROOT / "ui_v2" / page / "page.py").read_text(encoding="utf-8"), page


_STALE_WORDS = ("已超過", "預存序列", "最後有效", "延遲")


def test_不是最新與預存序列那一類句子原樣保留():
    checked = 0
    for key, model in _all_models().items():
        if key[0] != "live":
            continue
        display, _raw, _status = plain.plain_model(model, page=key[1])
        after = set(_strings(display))
        for text in _strings(model):
            if any(word in text for word in _STALE_WORDS):
                # 原句照留；句中若帶塊代號或層字樣，只換那幾個記號（`plain.section_text`），其餘逐字相同
                assert text in after or plain.section_text(text) in after, (key, text)
                checked += 1
    assert checked >= 20, checked


def test_失敗原文移出一般畫面_收進原始訊息清單():
    hits = 0
    for key, model in _all_models().items():
        if key[0] != "live" or key[1] == "set":
            continue
        display, raw, status = plain.plain_model(model, page=key[1])
        after = list(_strings(display))
        for text in _strings(model):
            if plain.FETCH_FAIL_PREFIX in text:
                hits += 1
                assert text not in after, (key, text)
                assert any(entry["text"] == text for entry in raw), (key, text)
        for text in after:
            assert "returned None" not in text and "kind=" not in text, (key, text)
            assert not re.search(r"\w+(Error|Exception)", text), (key, text)
            for secret in ("POLICY_SHEET_ID", "SETTINGS_SHEET_ID", "FRED_API_KEY", "google_service_account"):
                assert secret not in text, (key, text)
        if any(plain.FETCH_FAIL_PREFIX in t for t in _strings(model)):
            assert status["fetch_failed"], key
    assert hits >= 10, hits


def test_失敗行照舊以停止符號起頭_紅色與狀態不動():
    display, raw, status = plain.plain_model(
        {"title": "t", "blocks": [{"code": "MKT-1", "title": "風險情緒卡", "_tone": "紅", "state": "系統錯誤",
                                   "main_values": [{"label": "波動度指數", "_tone": "紅",
                                                    "value_text": "⛔ 取數失敗：fetch_url returned None (kind=x)"}]}]},
        page="mkt")
    block = display["blocks"][0]
    assert block["_tone"] == "紅" and block["state"] == "系統錯誤"
    # 原文認不出是哪一張表 → 資料類一律寫「資料」（獨立稽核必修：不依塊的來源欄推）
    assert block["main_values"][0]["value_text"] == "⛔ 資料 取數失敗：相關數字暫時無法判定"
    assert raw == [{"where": "MKT-1 風險情緒卡", "text": "⛔ 取數失敗：fetch_url returned None (kind=x)"}]
    assert status["fetch_failed"] == ["資料"]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("⛔ 取數失敗：" + plain.MSG_POLICY_NOT_CONFIGURED, "⛔ 保單與持倉 取數失敗：保單試算表尚未設定"),
        ("user_setting：⛔ 取數失敗：" + plain.MSG_SETTINGS_NOT_CONFIGURED, "⛔ 使用者設定 取數失敗：設定試算表尚未設定"),
        ("EXP-1　fund_profile：⛔ 取數失敗：HTTP 503", "條件輸入卡　⛔ 基金基本資料 取數失敗：相關數字暫時無法判定"),
        ("⛔ 取數失敗：AAAA：ConnectionError: 逾時", "⛔ 資料 取數失敗：AAAA 的相關數字暫時無法判定"),
        ("⛔ 設定讀不到：" + plain.MSG_SETTINGS_NOT_CONFIGURED, "⛔ 設定讀不到：設定試算表尚未設定"),
        ("存檔寫入失敗：mkt_window_days：HTTP 500", "存檔寫入失敗：觀察窗長度：這一次沒有存進去"),
        ("觀察窗長度（days_calendar）", "觀察窗長度（日曆日）"),
        ("依 fund_code 字面值排列", "依 基金代碼 字面值排列"),
        ("第三個值移到層 4 的 HLD-8", "第三個值移到④詳細資料「證據／來源」 的 最大回撤與本金類配息佔比"),
        ("FundClear:GetFundNAV", "FundClear"),
        ("nav_orig_ccy 與 ccy", "原幣淨值 與 計價幣別"),
    ],
)
def test_逐條改寫(text, expected):
    block = {"code": "HLD-2" if "AAAA" in text else ("EXP-0" if "EXP-1" in text else "HLD-1"), "title": "x"}
    display, _raw, _status = plain.plain_model({"blocks": [dict(block, line=text)]}, page="hld")
    assert display["blocks"][0]["line"] == expected


_CLASS = re.compile(r"⛔ (\S+) 取數失敗：")


def _expected_class(raw: str) -> str:
    """原文可判定的所屬資料類（本檔獨立寫一份）：字首表鍵 → 已知訊息 → 否則「資料」。"""
    head = raw.split(plain.FETCH_FAIL_PREFIX, 1)[0]
    for table, name in plain.TABLE_NAMES.items():
        if re.search(rf"(?<![A-Za-z0-9_]){table}：\s*$", head):
            return name
    known = {plain.MSG_SETTINGS_NOT_CONFIGURED: "使用者設定", plain.MSG_POLICY_NOT_CONFIGURED: "保單與持倉",
             plain.MSG_FRED_MISSING: "市場指標", plain.MSG_POOL_NOT_CLOUD: "選股池"}
    for message, name in known.items():
        if message in raw:
            return name
    # 客戶 2026-10-18 裁示 BL-0375（`DEC-2026-10-18-02`）：本頁自己組的「改用 <日期> 的預存淨值」那一句 → 淨值（本檔獨立寫）。
    if re.search(r"改用 \d{4}-\d{2}-\d{2} 的預存淨值$", raw):
        return "淨值"
    return "資料"


def test_改寫後寫的資料類_必須與原文可判定的所屬表一致_判定不了就是資料():
    checked = 0
    for key, model in _all_models().items():
        if key[0] != "live" or key[1] == "set":
            continue
        display, raw, _status = plain.plain_model(model, page=key[1])
        for block, shown in zip(model["blocks"], display["blocks"]):
            where = f"{block['code']} {block['title']}"
            allowed = {_expected_class(e["text"]) for e in raw
                       if e["where"] == where and plain.FETCH_FAIL_PREFIX in e["text"]}
            for text in _strings(shown):
                for found in _CLASS.findall(text):
                    assert found in allowed, (key, block["code"], found, allowed, text)
                    checked += 1
    assert checked >= 30, checked


@pytest.mark.parametrize("scenario", ["holdfail", "fxfail"])
def test_ALO3照抄別塊的失敗字串時_不得標成使用者設定(scenario):
    from ui_v2.alo import fixtures as AF
    from ui_v2.alo import live as AL
    from ui_v2.alo import logic as A

    display = plain.plain_model(AL.apply_live_notes(A.build_page_model(AF.scenario(scenario))), page="alo")[0]
    alo3 = next(b for b in display["blocks"] if b["code"] == "ALO-3")
    texts = list(_strings(alo3))
    assert any("取數失敗" in t for t in texts), texts      # 前提：這一塊真的有失敗字串
    assert not [t for t in texts if "使用者設定" in t], texts


def test_使用者的資料不換字_小寫詞照原樣():
    model = {"blocks": [
        {"code": "ALO-7", "title": "目標修改紀錄",
         "_rows": [{"key_text": "alo_bucket_names", "value_text": "nav status policy", "time_text": "t"}]},
        {"code": "ALO-6", "title": "歸屬明細", "_rows": [{"fund_text": "global nav fund", "policy_text": "policy x",
                                                        "bucket_text": "status"}]},
        {"code": "HLD-8", "title": "最大回撤與本金類配息佔比", "_rows": [{"fund_name": "nav growth"}]},
    ]}
    blocks = plain.plain_model(model, page="alo")[0]["blocks"]
    assert blocks[0]["_rows"][0] == {"key_text": "類別名稱", "value_text": "nav status policy", "time_text": "t"}
    assert blocks[1]["_rows"][0] == {"fund_text": "global nav fund", "policy_text": "policy x", "bucket_text": "status"}
    assert blocks[2]["_rows"][0] == {"fund_name": "nav growth"}


def test_受保護的鍵不換字():
    model = {"blocks": [{"code": "EXP-2", "title": "候選清單卡", "column_keys": ["ccy", "fund_name"],
                         "sort_options": ["ccy"], "sort_shown": "ccy", "_columns": ["ccy"], "name": "ccy",
                         "inputs": [{"name": "f", "label": "ccy", "value_text": "ccy"}],
                         "_rows": [{"_fund_code": "ccy", "label": "ccy"}]}]}
    block = plain.plain_model(model, page="exp")[0]["blocks"][0]
    assert block["column_keys"] == ["ccy", "fund_name"] and block["sort_options"] == ["ccy"]
    assert block["sort_shown"] == "ccy" and block["_columns"] == ["ccy"] and block["name"] == "ccy"
    assert block["inputs"][0] == {"name": "f", "label": "計價幣別", "value_text": "ccy"}
    assert block["_rows"][0] == {"_fund_code": "ccy", "label": "計價幣別"}


def test_設定與診斷頁_原文與鍵名照舊_只換塊代號與層字樣():
    model = {"blocks": [
        {"code": "SET-0", "title": "可信度結論燈", "line": "本燈只讀 SET-1，⛔ 取數失敗：" + plain.MSG_NO_SERVICE_ACCOUNT},
        {"code": "SET-1", "title": "資料新鮮度卡", "label": "距今日數（days_calendar）"},
        {"code": "SET-2", "title": "來源健康卡", "line": "⛔ 取數失敗：fetch_url returned None，見 SET-1"},
        {"code": "SET-4", "title": "參數編輯", "line": "alo_basis 改這個鍵會影響：ALO-1、ALO-7（層 3）"},
        {"code": "SET-7", "title": "欄位對照表", "_rows": [{"blocks_text": "HLD-1、HLD-5"}]},
    ]}
    display, raw, _status = plain.plain_model(model, page="set")
    blocks = display["blocks"]
    assert blocks[0]["line"] == "本燈只讀 資料新鮮度卡，⛔ 取數失敗：" + plain.MSG_NO_SERVICE_ACCOUNT
    assert blocks[1]["label"] == "距今日數（日曆日）"
    assert blocks[2]["line"] == model["blocks"][2]["line"]           # SET-2 照印原文
    assert blocks[3]["line"] == "alo_basis 改這個鍵會影響：目標輸入卡、目標修改紀錄（④詳細資料「操作」）"
    assert blocks[4]["_rows"][0]["blocks_text"] == "HLD-1、HLD-5"   # SET-7 照列塊代號
    assert raw == []


def test_整頁錯誤那一行():
    line, raw = plain.plain_error_line("⛔ 取數失敗：RuntimeError：fetch_url returned None", page="hld")
    assert line == "⛔ 資料 取數失敗：本頁暫時無法判定"
    assert raw == [{"where": "持倉體檢", "text": "⛔ 取數失敗：RuntimeError：fetch_url returned None"}]
    line, _raw = plain.plain_error_line("⛔ 取數失敗：ValueError：" + plain.MSG_POLICY_NOT_CONFIGURED, page="alo")
    assert line == "⛔ 保單與持倉 取數失敗：保單試算表尚未設定"


def test_持倉體檢的照印句拿掉_其他頁不動():
    model = {"blocks": [{"code": "HLD-2", "title": "績效與風險卡", "detail_lines": ["a", plain.PRINT_AS_IS_LINE]}]}
    assert plain.plain_model(model, page="hld")[0]["blocks"][0]["detail_lines"] == ["a"]
    model["blocks"][0]["code"] = "SET-2"
    assert plain.plain_model(model, page="set")[0]["blocks"][0]["detail_lines"] == ["a", plain.PRINT_AS_IS_LINE]


def test_鍵不是字串的dict照樣走得過():
    """設定與診斷頁 `SET-6` 的 `cell_notes` 以欄位序號（int）當鍵（2026-10-17 畫面測試抓到：曾在這裡拋 AttributeError）。"""
    model = {"blocks": [{"code": "SET-6", "title": "取數紀錄", "_rows": [{"cells": ["a"], "cell_notes": {0: ["x"]}}]},
                        {"code": "SET-1", "title": "資料新鮮度卡", "cell_notes": {1: ["days_calendar"]}}]}
    display = plain.plain_model(model, page="set")[0]
    assert display["blocks"][0]["_rows"][0]["cell_notes"] == {0: ["x"]}
    assert display["blocks"][1]["cell_notes"] == {1: ["日曆日"]}


def test_不認得的頁當場炸():
    with pytest.raises(ValueError):
        plain.plain_model({"blocks": []}, page="xxx")


# ───────────────────────── 5. 跨頁的原始訊息 ─────────────────────────


def test_record_raw_每次整格覆寫_沒有就寫空():
    state = {}
    plain.record_raw(state, "mkt", [{"where": "MKT-1 風險情緒卡", "text": "原文一"}],
                     datetime.datetime(2026, 10, 17, 1, 2, 3, tzinfo=datetime.timezone.utc))
    plain.record_raw(state, "hld", [{"where": "持倉體檢", "text": "原文二"}], "2026-10-17T02:00:00+00:00")
    assert plain.raw_entries(state) == [
        ("市場總覽", "2026-10-17T01:02:03+00:00", "MKT-1 風險情緒卡", "原文一"),
        ("持倉體檢", "2026-10-17T02:00:00+00:00", "持倉體檢", "原文二"),
    ]
    plain.record_raw(state, "mkt", [{"where": "MKT-3 資金與匯率卡", "text": "原文三"}], "t2")
    assert [e[3] for e in plain.raw_entries(state)] == ["原文三", "原文二"]   # 整格覆寫，不累加
    plain.record_raw(state, "mkt", [], "t3")
    assert [e[3] for e in plain.raw_entries(state)] == ["原文二"]            # 沒有就寫空
    assert plain.recorded_pages(state) == [("市場總覽", "t3"), ("持倉體檢", "2026-10-17T02:00:00+00:00")]
    assert plain.raw_entries({}) == [] and plain.recorded_pages({}) == []


def test_RAW_STATE不在預覽入口換頁要清的清單裡():
    source = (_ROOT / "ui_v2" / "app_preview.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    segment = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "_PAGE_STATE_TO_DROP"
                                                for t in node.targets):
            segment = ast.get_source_segment(source, node.value)
    assert segment is not None
    code_only = "\n".join(line.split("#", 1)[0] for line in segment.splitlines())
    assert "RAW_STATE" not in code_only and plain.RAW_STATE not in code_only
    assert "plain" not in code_only
