"""v19.483 稽核 PR-4a:235 加碼 §3.3 SSOT(M2)+ 加碼水位欄 help(A1/A2)。

M2:驅動燈號的布林 z 切點(+3/+2/−1/−2/−3)+ 落底回升 lookback 原 inline 於
    ladder235._classify/_defense_note → 收進 shared/signal_thresholds SSOT。
A1/A2:加碼水位欄補 column help,說明它與「基期」錨點不同、可能不一致(交叉提醒)。
"""
import re
from pathlib import Path

from shared import signal_thresholds as ST
from ui.helpers.fund_grp_health.columns import extra_column_config

_ROOT = Path(__file__).resolve().parent.parent
_LADDER_SRC = (_ROOT / "services" / "ladder235.py").read_text(encoding="utf-8")
_COLUMNS_SRC = (_ROOT / "ui" / "helpers" / "fund_grp_health" / "columns.py").read_text(encoding="utf-8")


# ── M2:SSOT 常數存在且值正確(§3.3)──────────────────────────────────────
def test_bb_cutoff_constants_exist_with_expected_values():
    assert ST.LADDER235_BB_STOPGAIN_FORCE == 3.0
    assert ST.LADDER235_BB_STOPGAIN_BATCH == 2.0
    assert ST.LADDER235_BB_L1 == -1.0
    assert ST.LADDER235_BB_L2 == -2.0
    assert ST.LADDER235_BB_L3 == -3.0
    assert ST.LADDER235_DEFENSE_LOOKBACK_W == 8


def test_ladder_classify_uses_ssot_not_inline_literals():
    _clsf = _LADDER_SRC.split("def _classify")[1].split("def _defense_note")[0]
    # 決策 if 條件必須走常數,不得再 inline `z_bb > 3` / `z_bb < -3` 等
    assert "LADDER235_BB_STOPGAIN_FORCE" in _clsf and "LADDER235_BB_L3" in _clsf
    assert not re.search(r"if\s+z_bb\s*>\s*3\b", _clsf), "z_bb>3 應走 SSOT"
    assert not re.search(r"if\s+z_bb\s*<\s*-3\b", _clsf), "z_bb<-3 應走 SSOT"
    assert not re.search(r"z_bb\s*<\s*-1\b", _clsf), "z_bb<-1 應走 SSOT"


def test_defense_note_lookback_uses_ssot():
    assert "iloc[-LADDER235_DEFENSE_LOOKBACK_W:]" in _LADDER_SRC
    assert "iloc[-8:]" not in _LADDER_SRC


# ── A1/A2:加碼水位欄 help 存在且點出「與基期錨點不同、可能不一致」───────────
def test_deploy_ladder_column_registered():
    # A2:加碼水位欄已進 column_config(不再是裸欄無 tooltip)
    assert "加碼水位" in extra_column_config()


def test_deploy_ladder_help_points_out_anchor_difference():
    # A1/A2:help 文字須點出與「基期 / 一年 HWM」不同錨點、可能不一致(source-level 守門,
    # Streamlit ColumnConfig 物件不外露 help 屬性,改驗原始碼的 help 片語)
    assert "近 20 週均值" in _COLUMNS_SRC
    assert "一年 HWM" in _COLUMNS_SRC
    assert "可能不一致" in _COLUMNS_SRC and "都對" in _COLUMNS_SRC


# ── 行為不變佐證:SSOT 化不改燈號值 ─────────────────────────────────────
def test_deploy_pct_unchanged():
    assert ST.LADDER235_DEPLOY_PCT == {"燈一": 0.20, "燈二": 0.30, "燈三": 0.50, "巡航": 0.0}
