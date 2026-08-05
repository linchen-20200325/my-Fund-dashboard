"""test_midcycle_card_labels — Z-Score 矩陣卡片標籤誠實化 + 指標數去寫死。

2026-08-05 稽核:
- 🔴 必修 1(§1 造假違憲):服務層已把代理 / 升級來源的 `name` 改對了
  (PMI→「ISM 製造業 PMI（Phil Fed 替代）」、FED_BS→「淨流動性 (YoY)」),
  但 `ui/tab1_macro_midcycle.py` 的卡片 `title=_r["指標"]` 完全不讀 `name`
  → 畫面把 Phil Fed 擴散指數轉換值(63.8)標成「ISM PMI」(官方 2026-07 是 55.6),
  把淨流動性 YoY 標成「Fed 資產負債表」並寫死白話「QT 縮表」。
  這是 `PROCESS.md §4` 的典型形狀:**服務層算對了、UI 沒接出去**。
- 🟡 必修 3(§3.3 反捏造):指標數三處寫死(18 / 23 / 23),實際 18。

**修正前全部必紅**:`_ZS_INDICATORS` / `_card_title` / `_card_note` 三個 symbol
在修正前不存在 → import 直接 ImportError。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ui.tab1_macro_midcycle import _ZS_INDICATORS, _card_note, _card_title

_SRC = (Path(__file__).resolve().parents[1] / "ui" / "tab1_macro_midcycle.py"
        ).read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════
# 1) 卡片標題吃服務層 name(§1 代理值不可偽裝成本尊)
# ══════════════════════════════════════════════════════════════
class TestCardTitle:
    def test_pmi_proxy_shows_service_name_and_warning(self):
        """Phil Fed 代理:標題必須帶服務層改好的名字 + 可見的 ⚠️ 標記。"""
        _t = _card_title("ISM PMI", {
            "name": "ISM 製造業 PMI（Phil Fed 替代）",
            "is_proxy": True,
            "proxy_note": "Phil Fed 擴散指數轉換",
        })
        assert "Phil Fed 替代" in _t, "代理值仍被標成本尊 = §1 造假"
        assert "⚠️" in _t, "is_proxy 為真時卡片必須有可見標記"
        assert _t != "ISM PMI"

    def test_pmi_official_has_no_warning(self):
        """非代理(官方 ISM)不得亂加 ⚠️ —— 旗標決定,不是每張卡都掛警示。"""
        _t = _card_title("ISM PMI", {"name": "ISM 製造業 PMI", "is_proxy": False})
        assert _t == "ISM 製造業 PMI"

    def test_fed_bs_shows_net_liquidity_name(self):
        """FED_BS 這格自 v19.193 起是淨流動性,標題必須跟著服務層走。"""
        _t = _card_title("Fed 資產負債表 YoY", {"name": "淨流動性 (YoY)"})
        assert _t == "淨流動性 (YoY)"

    def test_fed_bs_gross_fallback_keeps_service_name(self):
        """§1 降級路徑(淨流動性序列不足 → 回毛額 WALCL)時標題也吃服務層 name。"""
        _t = _card_title("Fed 資產負債表 YoY", {"name": "Fed 資產負債表 (YoY)"})
        assert _t == "Fed 資產負債表 (YoY)"

    def test_star_marker_preserved(self):
        """⭐(v16.1 高頻替代源)是本表自有語意,服務層 name 不帶 → 不可被吃掉。"""
        _t = _card_title("⭐ CFNAI 領先指標", {"name": "CFNAI 領先指標"})
        assert _t.startswith("⭐ ") and "CFNAI 領先指標" in _t

    def test_missing_name_falls_back_to_spec(self):
        """服務層沒給 name(指標整格缺)→ 退回 spec 顯示名,不炸、不空白。"""
        assert _card_title("失業率", {}) == "失業率"
        assert _card_title("⭐ 建照核發", None) == "⭐ 建照核發"


# ══════════════════════════════════════════════════════════════
# 2) 卡片註腳吃服務層 desc(原本 desc 全站 0 consumer)
# ══════════════════════════════════════════════════════════════
class TestCardNote:
    def test_desc_is_rendered(self):
        """FED_BS 的『誰在抽水』分解必須出現在卡片上,否則使用者仍讀成 Fed 縮表。"""
        _n = _card_note("🟠 警示（流動性轉緊，Z=-1.72）", {
            "desc": "Fed資產−RRP−TGA=真正進股市的錢｜Fed資產 +1.44%(+956 億) / "
                    "TGA +5,403 億(抽水) / RRP -1,529 億(釋水)",
        })
        assert "TGA +5,403 億(抽水)" in _n
        assert "🟠 警示" in _n

    def test_proxy_note_appended_when_proxy(self):
        _n = _card_note("🟢 正常", {"is_proxy": True, "proxy_note": "Phil Fed 擴散指數轉換",
                                    "desc": "50 為榮枯線"})
        assert "Phil Fed 擴散指數轉換" in _n and "⚠️" in _n

    def test_proxy_note_skipped_when_not_proxy(self):
        _n = _card_note("🟢 正常", {"is_proxy": False, "proxy_note": "不該出現"})
        assert "不該出現" not in _n

    def test_angle_brackets_escaped(self):
        """desc 常含 `>50 擴張，<45 收縮`;卡片是 unsafe_allow_html,不 escape 會被吃掉。"""
        _n = _card_note("🟢 正常", {"desc": "50 為榮枯線，>50 擴張，<45 收縮"})
        assert "&gt;50" in _n and "&lt;45" in _n
        assert "<45" not in _n

    def test_empty_desc_leaves_verdict_only(self):
        assert _card_note("🟢 正常", {}) == "🟢 正常"


# ══════════════════════════════════════════════════════════════
# 3) 指標盤 SSOT + 接線
# ══════════════════════════════════════════════════════════════
class TestIndicatorSpec:
    def test_fed_bs_phrase_no_longer_says_qt(self):
        """**修正前必紅**:FED_BS 白話原寫死「QE 擴表 / QT 縮表」,但這格已非毛額。"""
        _row = next(r for r in _ZS_INDICATORS if r[0] == "FED_BS")
        _pos, _neg = _row[5], _row[6]
        assert "QT" not in _neg and "縮表" not in _neg, f"FED_BS 負向白話仍寫 {_neg}"
        assert "QE" not in _pos and "擴表" not in _pos, f"FED_BS 正向白話仍寫 {_pos}"
        assert "流動性" in _pos and "流動性" in _neg

    def test_spec_shape_is_7_tuple(self):
        for _row in _ZS_INDICATORS:
            assert len(_row) == 7, f"spec 欄數改了會讓 render 的 unpack 炸掉:{_row}"

    def test_counts_derived_not_hardcoded(self):
        """**修正前必紅**:caption 寫 18、標題與 expander 寫 23,實際 18(§3.3)。"""
        assert "23 指標" not in _SRC, "仍有寫死的『23 指標』字串"
        assert "(18 指標)" not in _SRC, "仍有寫死的『(18 指標)』字串"
        assert _SRC.count("_n_zs = len(_ZS_INDICATORS)") == 1
        assert _SRC.count("{_n_zs} 指標") >= 3, "三處指標數文案都要吃同一個 len()"

    def test_card_is_wired_to_title_and_note_builders(self):
        """**修正前必紅** —— builder 寫好但沒接出去就等於沒修(PROCESS.md §4)。"""
        assert "_ztitle = _card_title(_zname, _zd)" in _SRC
        assert 'note=_r["_note"]' in _SRC, "卡片仍傳純白話判讀,服務層 desc 沒接出去"
        assert 'title=_r["指標"]' in _SRC     # 「指標」欄本身已改成 _ztitle
        assert '"指標": _zname' not in _SRC, "仍有 row 直接用 spec 名當標題"


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
