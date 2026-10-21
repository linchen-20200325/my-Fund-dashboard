# -*- coding: utf-8 -*-
"""BL-0250 實機驗收回修 批次 3 第一段（3-A）（客戶 2026-10-19 批次 3 裁示，`docs/DECISIONS.md` `DEC-2026-10-19-05`；
44 第七節第三小節之十二）的畫面守衛。

情境腳本與抽字器重用 `tests/ui_v2/_plain_scan.py`（五頁正式模式全部情境；只用各頁 fixtures／替身，不打網路）。
每一項一條正面（正式模式畫面改了）＋一條反面（不該改的情境照舊；示範模式照舊）。
邏輯層與突變見 `tests/ui_v2/test_bl0250_batch3a_logic.py` 與本批回報。
"""

from __future__ import annotations

import functools
import pathlib
import sys

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
for _p in (_HERE, _HERE.parent, _HERE.parents[1]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

pytestmark = pytest.mark.slow

import _plain_scan as SCAN  # noqa: E402

_ROOT = _HERE.parents[1]
# BL-0250 批次 3-B 總管裁定（2026-10-19；有意識的更正，不是漏刪）：括號由「沒有單一的來源與新鮮度」改為線框第六版待裁示 (1) 推薦原文；
# 舊值在寫下當時為真（列展開還不存在）。44 第七節第三小節之十三其六。
_NA = "⬜ 不適用（這張卡由多檔基金組成，各檔來源見每列展開）"
_CASES = [(page, name) for page, scripts in SCAN.SCRIPTS.items() for name in scripts]


@functools.lru_cache(maxsize=None)
def _at(page, name):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(SCAN.SCRIPTS[page][name], default_timeout=90)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


@functools.lru_cache(maxsize=None)
def _demo(page, scenario):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(_ROOT / "ui_v2" / f"app_{page}.py"), default_timeout=90)
    at.query_params["scenario"] = scenario
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _texts(at):
    return [" ".join(t.split()) for t in SCAN.screen_texts(at)]


def _joined(page, name):
    return "\n".join(_texts(_at(page, name)))


# ═══════════════════════ 待裁示 (2)：尚未設定 vs 取數失敗（批次 1 四處遺留） ═══════════════════════


def test_EXP_未設定_燈與結果清單標題寫尚未設定():
    joined = _joined("exp", "未設定")
    assert "⛔ 狀態：尚未設定 讀到的那兩塊有一塊尚未設定：設定試算表、選股池的雲端來源" in joined
    assert "結果清單 — ⛔ 尚未設定：選股池的雲端來源、設定試算表" in joined
    assert "結果清單 — ⛔ 取數失敗" not in joined and "⛔ 狀態：取數失敗" not in joined


def test_EXP_真的取數失敗_燈與結果清單標題照寫取數失敗():
    joined = _joined("exp", "取數失敗")
    assert "⛔ 狀態：取數失敗 讀到的那兩塊有一塊取數失敗" in joined
    assert "結果清單 — ⛔ 取數失敗" in joined and "尚未設定" not in joined


def test_SET_未設定_參數編輯與取數紀錄標題_不寫表名():
    joined = _joined("set", "未設定")
    assert "參數編輯 — ⛔ 尚未設定：試算表 ID" in joined
    assert "取數紀錄 — ⛔ 尚未設定：試算表 ID" in joined
    assert "取數失敗：user_setting" not in joined and "取數失敗：fetch_log" not in joined   # 欄位對照內容照舊會有表名


def test_SET_stale_取數紀錄全屬尚未設定_燈與來源健康卡與兩表結果寫尚未設定():
    joined = _joined("set", "stale")
    assert "⛔ 狀態：尚未設定 尚未設定：資料來源的金鑰（市場指標）" in joined
    assert "來源健康卡 — ⛔ 尚未設定：資料來源的金鑰（市場指標）" in joined
    assert "市場指標 ⛔ 尚未設定：資料來源的金鑰" in joined
    assert "失敗的來源層級：市場指標" not in joined and "最近一次取數失敗" not in joined


def test_SET_stale_有金鑰但FRED回400_燈寫來源失敗_不寫尚未設定():
    """PR #1012 CI 回修的反面：金鑰有值但無效、FRED 回 400（替身模擬，不打網路）→ 那一筆是真的取數失敗，
    燈照規則寫來源失敗，取數紀錄與來源健康卡寫取數失敗；不得降級成尚未設定。"""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(SCAN.SET_STALE_FRED_INVALID, default_timeout=90)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    texts = _texts(at)
    joined = "\n".join(texts)
    assert "⛔ 狀態：來源失敗 失敗的來源層級：市場指標" in joined
    assert "來源健康卡 — ⛔ 最近一次取數失敗：市場指標" in joined
    assert "api_key is not registered" in joined                     # 訊息原文照印
    assert "尚未設定：資料來源的金鑰" not in joined


def test_SET_取數紀錄混有真的失敗_照寫取數失敗_燈判定照舊():
    joined = _joined("set", "取數紀錄")
    assert "⛔ 狀態：來源失敗 失敗的來源層級：市場指標" in joined
    assert "來源健康卡 — ⛔ 最近一次取數失敗：市場指標" in joined
    assert "⛔ 尚未設定：資料來源的金鑰" not in joined


@functools.lru_cache(maxsize=None)
def _at_off(page, name):
    """BL-0250 批次 3-D：同情境把卡片安靜收起關掉（＝3-C 的畫法），驗 3-A 那幾處值位置的寫法照舊。"""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(SCAN.quiet_off(SCAN.SCRIPTS[page][name]), default_timeout=90)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _joined_off(page, name):
    return "\n".join(_texts(_at_off(page, name)))


def test_HLD_未設定_偏離提示卡主值寫尚未設定_真的取數失敗情境照舊():
    # ~~"偏離提示卡 ⛔ 尚未設定 ⛔ 此區塊暫時無法判定"~~ → 同批總管裁定（適用 `DEC-2026-10-19-05` 第 2 點；有意識的更正，不是漏刪）：補上哪一項。
    # → BL-0250 批次 3-D（新設計 B；44 第七節第三小節之十五；有意識的政策變更，不是漏刪；決策者：客戶 `DEC-2026-10-21-03`）：
    # ~~現況畫面直接驗~~ —— 這張卡主值全部讀不到 → 收起，畫面上改寫原因行；3-A 那一句值位置寫法改在「關掉收起」的畫面驗（照舊），
    # 收起後的那一行另驗（兩項都寫出來、不寫成取數失敗）。
    assert "偏離提示卡 ⛔ 尚未設定：保單試算表 ⛔ 此區塊暫時無法判定" in _joined_off("hld", "未設定")
    assert "偏離提示卡 （暫時收起） ⛔ 尚未設定：保單試算表、設定試算表 " in _joined("hld", "未設定")
    failed = _joined("hld", "取數失敗")
    assert "⛔ AAAA 取數失敗" in failed and "偏離提示卡 ⛔ 尚未設定" not in failed


def test_MKT_未設定_尚未設定的主值旁不掛取數失敗_真的取數失敗那一個照掛():
    # BL-0250 批次 3-D（同上一條）：「未設定」情境三張卡主值全部讀不到 → 收起；3-A 這幾句值位置寫法改在「關掉收起」的畫面驗（照舊）。
    joined = _joined_off("mkt", "未設定")
    # 同批稽核回修 C1：風險情緒卡是混合成因（波動度指數真的取數失敗），自己全屬尚未設定的那個值寫哪一項（不留光禿禿的狀態族）。
    assert "高收益信用利差 ⛔ 尚未設定：資料來源的金鑰 ⬜ 不適用" in joined
    assert "政策利率 ⛔ 此區塊暫時無法判定 新臺幣對美元匯率" in joined
    assert "高收益信用利差 ⛔ 尚未設定 取數失敗" not in joined
    assert "波動度指數 ⛔ 此區塊暫時無法判定 取數失敗" in joined          # 反面：同一張卡真的取數失敗那一個照掛
    assert "波動度指數 ⛔ 此區塊暫時無法判定 取數失敗" in _joined("mkt", "取數失敗")   # 部分讀不到：不收起，照舊
    # 收起之後：兩種成因各一行，尚未設定那一行寫哪一項、不掛「取數失敗」
    quiet = _joined("mkt", "未設定")
    assert "風險情緒卡 （暫時收起） ⛔ 取數失敗：波動度指數 ⛔ 尚未設定：資料來源的金鑰 ⬜ 不適用（尚未設定：設定試算表）" in quiet
    assert "資金與匯率卡 （暫時收起） ⛔ 尚未設定：資料來源的金鑰 ◇ 資料未備：新臺幣對美元匯率" in quiet
    assert "取數失敗：高收益信用利差" not in quiet and "取數失敗：資料來源的金鑰" not in quiet


def test_MKT_未設定_缺金鑰的指標_清單與明細表與新鮮度清單寫尚未設定_真的失敗照寫():
    """同批總管裁定（適用 `DEC-2026-10-19-05` 第 2 點；44 第七節第三小節之十二其九第 1 條）。"""
    texts = _texts(_at("mkt", "未設定"))
    assert texts.count("⛔ 尚未設定：資料來源的金鑰（高收益信用利差、政策利率、期限利差）") == 2      # MKT-5 清單下方、MKT-6 表尾
    assert texts.count("⛔ 取數失敗：波動度指數") == 2
    table = [t for t in texts if t.startswith("指標 最近觀測日 ")]
    assert len(table) == 1
    assert "高收益信用利差 ⛔ 尚未設定：資料來源的金鑰 ⛔ ⛔ ⛔ 政策利率" in table[0]
    assert "波動度指數 取數失敗 ⛔ ⛔ ⛔ ⛔" in table[0] and "高收益信用利差 取數失敗" not in table[0]
    assert "⛔ 取數失敗：高收益信用利差" not in "\n".join(texts)


# ═══════════════════════ 待裁示 (3)：缺 Google 服務帳戶 ═══════════════════════


def test_SET_缺服務帳戶_燈以外各處統一一句_燈照C1_照印原文照舊():
    """~~同批總管裁定：燈也改、照印原文那一格改統一句~~ → 同批稽核後撤回（有意識的更正，不是漏刪；決策者 AI 總管；
    理由：超出 `DEC-2026-10-19-05` 核准推薦 (3)「燈以外各處」「除來源健康卡與取數紀錄（照印原文）外」的射程，且會改寫
    `DEC-2026-10-18-01` C1）。本條鎖住撤回後的現況。"""
    texts = _texts(_at("set", "取數失敗"))
    joined = "\n".join(texts)
    assert "⛔ 狀態：取數失敗 ⛔ 取數失敗：未設定 Google 服務帳戶" in joined         # C1（DEC-2026-10-18-01）照舊
    assert texts.count("⛔ 取數失敗：未設定服務帳戶（google_service_account）") == 2   # SET-2、SET-6 照印原文（客戶核准的例外）
    assert "讀取失敗的原文" not in joined
    for title in ("規則參數卡", "參數編輯", "來源健康卡", "取數紀錄"):
        assert f"{title} — ⛔ 尚未設定：Google 服務帳戶" in joined, title
    assert "⛔ 讀不到試算表名稱：未設定 Google 服務帳戶" not in joined
    assert "尚未設定 Google 服務帳戶，暫停寫入" in joined
    assert "未設定服務帳戶" not in texts                             # 舊的停用原因那一行


def test_SET_有服務帳戶_沒有這一句():
    assert "Google 服務帳戶" not in _joined("set", "正常")


# ═══════════════════════ U7：設定與診斷頁 ═══════════════════════


def test_SET3_表頭與列上中文_沒有英文型別():
    joined = _joined("set", "正常")
    assert "設定項目 目前值 資料型態 最後修改時間（UTC+8） 計算基礎 ⬜ 未設定 清單" in joined
    assert "型別（value_kind）" not in joined and "鍵名 目前值" not in joined
    assert "每個設定的輸入方式依它的資料型態決定。" in joined


def test_SET2與SET6_結果不寫英文原值_紀錄編號只在進階診斷():
    texts = _texts(_at("set", "取數紀錄"))
    joined = "\n".join(texts)
    log_table = [t for t in texts if t.startswith("來源層級 開始（UTC+8） 耗時（秒） 結果 取回列數 訊息")]
    assert len(log_table) == 1 and " failed " not in log_table[0] and "⛔ 取數失敗" in log_table[0]
    assert not log_table[0].startswith("log_id") and "依 started_at" not in joined and "由新到舊排列。" in joined
    raw = [t for t in texts if t.startswith("紀錄編號 開始（UTC+8） 結果原值 ")]
    assert len(raw) == 1 and raw[0].endswith(" failed")
    log_id = raw[0].split()[3]
    assert sum(log_id in t for t in texts) == 1                       # 紀錄編號只出現在進階診斷那一張
    assert "取數紀錄的紀錄編號與結果原值" in joined


def test_SET7_留在原位_改標題():
    joined = _joined("set", "正常")
    assert "欄位對照（進階） — 每一欄資料用在哪一塊" in joined and "欄位對照表 — 第四節" not in joined


# ═══════════════════════ U4：持倉體檢「套用」 ═══════════════════════


@pytest.mark.parametrize("name", list(SCAN.SCRIPTS["hld"]))
def test_HLD_正式模式不畫套用_說明一句恰一次(name):
    at = _at("hld", name)
    texts = _texts(at)
    assert "套用" not in [b.label for b in at.button]
    if "存檔" in [b.label for b in at.button]:
        assert texts.count("畫面上的結果只讀已存的設定；存檔後，下一次重新載入時生效。") == 1
    assert "正式結果只讀已存設定：請按「存檔」" not in "\n".join(texts)


def test_HLD_示範模式照舊畫套用():
    assert "套用" in [b.label for b in _demo("hld", "full").button]


# ═══════════════════════ 待裁示 (1)：EXP 三張核心卡 ⬜ 不適用 ═══════════════════════


@pytest.mark.parametrize("name", list(SCAN.SCRIPTS["exp"]))
def test_EXP_三張核心卡來源與新鮮度寫不適用(name):
    # ~~在 ④「核心卡的來源與新鮮度」裡寫「‹卡名› ⬜ 不適用（…）」~~ → BL-0250 批次 3-C（G2 第 11 列；`DEC-2026-10-21-01`；
    # 有意識的政策變更，不是漏刪）：那一枚不再畫，那一句在設定與診斷頁總表明細的狀態欄。該卡另有塊層 ⛔ 時，總表依既有合併規則
    # 以 ⛔ 那一句為狀態（之十三其八第 7 條，不改；總管派工判定）。
    from ui_v2 import page_health

    at = _at("exp", name)
    joined = "\n".join(_texts(at))
    assert _NA not in joined and "〔來源層級〕" not in joined and "〔新鮮度〕" not in joined
    rows = page_health.detail_rows(at.session_state[page_health.STATE_KEY]["exp"])
    for card in ("條件輸入卡", "候選清單卡", "並排對照卡"):
        mine = [r for r in rows if r[1] == card]
        assert mine and all(r[2] == _NA or r[2].startswith("⛔ ") for r in mine), (card, mine)
    if name in ("正常", "局部失敗", "stale"):
        assert all(next(r for r in rows if r[1] == card)[2] == _NA for card in ("條件輸入卡", "候選清單卡", "並排對照卡"))


@pytest.mark.parametrize("page,name", _CASES, ids=[f"{p}-{n}" for p, n in _CASES])
def test_不適用那一句只在標的探索三張卡_其他缺資料情境不用(page, name):
    texts = _texts(_at(page, name))
    hits = sum(t.count(_NA) for t in texts)
    # ~~`hits == (3 if page == "exp" else 0)`~~ → 3-C：標的探索那三句改在總表明細（上一條），一般畫面四頁都是 0（有意識的政策變更，不是漏刪）
    assert hits == 0
    assert "多檔基金組成" not in "\n".join(t.replace(_NA, "") for t in texts)


def test_EXP_示範模式照舊佔位():
    joined = "\n".join(_texts(_demo("exp", "full")))
    assert "〔來源層級〕" in joined and _NA not in joined


# ═══════════════════════ 示範模式正控（設定與診斷） ═══════════════════════


def test_SET_示範模式照舊英文表頭與舊標題():
    joined = "\n".join(_texts(_demo("set", "ok")))
    assert "型別（value_kind）" in joined and "欄位對照表" in joined and "欄位對照（進階）" not in joined
