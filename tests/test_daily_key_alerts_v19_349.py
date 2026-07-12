# -*- coding: utf-8 -*-
"""v19.349 — ⚡ 今日關鍵橫幅(第 4 步,股票 v19.108 同構移植)回歸鎖。

三個最容易出錯的輸入(§6):
1. 全空/None(未載入)→ items=[],掛載端不渲染(不誤導)
2. indicator block 的 score 是字串垃圾 → 跳過該項不炸,其他項不受影響
3. 拐點 source_ok=False(抓取失敗)→ 不進橫幅(⬜ 不是事件)
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _src(rel: str) -> str:
    return (REPO / rel).read_text(encoding='utf-8')


def _ind(score, weight=1.0, name='測試指標', value=1.23, unit='%'):
    return {'name': name, 'value': value, 'unit': unit,
            'score': score, 'weight': weight}


def _tp(icon, signal='訊號', label='拐點', note='白話說明', source_ok=True):
    return {'icon': icon, 'signal': signal, 'label': label,
            'note': note, 'source_ok': source_ok}


# ═════════════════════════════════════════════════════════════════
# L2 collect_key_alerts
# ═════════════════════════════════════════════════════════════════
class TestCollectKeyAlerts:
    def test_all_empty_no_crash(self):
        from services.macro.daily_key_alerts import collect_key_alerts
        assert collect_key_alerts(None, None) == {
            'items': [], 'n_red': 0, 'n_yellow': 0}

    def test_signal_layer_severity_by_sigma_cutoffs(self):
        from shared.signal_thresholds import (
            SIGMA_HIGH_CUTOFF, SIGMA_LOW_CUTOFF,
        )
        from services.macro.daily_key_alerts import collect_key_alerts
        ind = {
            'CALM':  _ind(SIGMA_LOW_CUTOFF - 0.1),    # 未達黃 → 排除
            'WARN':  _ind(SIGMA_LOW_CUTOFF + 0.1),    # 黃級
            'DANGER': _ind(SIGMA_HIGH_CUTOFF + 0.1),  # 紅級
        }
        out = collect_key_alerts(ind, None)
        assert len(out['items']) == 2
        assert out['n_red'] == 1 and out['n_yellow'] == 1
        assert out['items'][0]['severity'] == 0      # 紅先
        assert out['items'][0]['detail'], '白話 detail 沿用 _interpret_indicator(SSOT)'

    def test_signal_layer_ranked_by_calibrated_weight(self):
        from shared.signal_thresholds import SIGMA_HIGH_CUTOFF
        from services.macro.daily_key_alerts import collect_key_alerts
        _s = SIGMA_HIGH_CUTOFF + 0.2
        ind = {
            'LIGHT': _ind(_s, weight=0.5, name='輕權重'),
            'HEAVY': _ind(_s, weight=3.0, name='重權重'),
        }
        out = collect_key_alerts(ind, None)
        assert out['items'][0]['text'].startswith('重權重'), (
            '同級內依 |score×weight| 降冪 — active.json 校準權重決定順序')

    def test_signal_layer_garbage_score_skipped(self):
        from shared.signal_thresholds import SIGMA_HIGH_CUTOFF
        from services.macro.daily_key_alerts import collect_key_alerts
        ind = {
            'BAD': _ind('N/A'),
            'OK': _ind(SIGMA_HIGH_CUTOFF + 0.1, name='正常'),
        }
        out = collect_key_alerts(ind, None)
        assert len(out['items']) == 1 and '正常' in out['items'][0]['text']

    def test_turning_point_layer_icon_mapping(self):
        from services.macro.daily_key_alerts import collect_key_alerts
        tp = {
            'a': _tp('🔻', label='收縮'),       # 紅級
            'b': _tp('🚀', label='利多拐點'),   # 黃級(利多也該看)
            'c': _tp('🟢', label='擴張延續'),   # 非事件
            'd': _tp('🔻', label='壞源', source_ok=False),   # 抓取失敗不進
        }
        out = collect_key_alerts(None, tp)
        assert len(out['items']) == 2
        assert out['items'][0]['emoji'] == '🔻' and out['items'][0]['severity'] == 0
        assert out['items'][1]['emoji'] == '🚀' and out['items'][1]['severity'] == 1
        assert '收縮' in out['items'][0]['text']
        assert out['items'][0]['detail'] == '白話說明'   # note 作 hover

    def test_merged_red_first_across_layers(self):
        from shared.signal_thresholds import SIGMA_LOW_CUTOFF
        from services.macro.daily_key_alerts import collect_key_alerts
        out = collect_key_alerts(
            {'W': _ind(SIGMA_LOW_CUTOFF + 0.1)},   # 黃(訊號層)
            {'t': _tp('⚠️')})                        # 紅(拐點層)
        assert out['items'][0]['layer'] == 'turning_point'
        assert out['items'][0]['severity'] == 0

    def test_l2_purity(self):
        text = _src('services/macro/daily_key_alerts.py')
        for banned in ('import streamlit', 'import requests', 'fetch_url'):
            assert banned not in text, f'L2 純函式不得 {banned}(§8.2)'


# ═════════════════════════════════════════════════════════════════
# 橫幅渲染 + 掛載
# ═════════════════════════════════════════════════════════════════
class TestBannerAndMount:
    def test_empty_honest_all_clear(self):
        from ui.helpers.macro.key_alerts import key_alerts_banner
        assert '無異常' in key_alerts_banner(
            {'items': [], 'n_red': 0, 'n_yellow': 0})

    def test_red_banner_with_tooltip(self):
        from shared.colors import TRAFFIC_RED
        from services.macro.daily_key_alerts import collect_key_alerts
        from ui.helpers.macro.key_alerts import key_alerts_banner
        html = key_alerts_banner(collect_key_alerts(None, {'t': _tp('🔻')}))
        assert '今日關鍵（1 項）' in html and TRAFFIC_RED in html
        assert 'title="白話說明"' in html

    def test_tab1_mounts_after_caption_with_loaded_guard(self):
        text = _src('ui/tab1_macro.py')
        assert 'collect_key_alerts' in text and 'key_alerts_banner' in text
        # 未載入(兩源皆空)不渲染 — 防誤導性「無異常」
        assert '_ka_ind or _ka_tp' in text
        # 掛在頁首(載入按鈕之前)
        assert text.index('key_alerts_banner') < text.index('btn_macro_load')
