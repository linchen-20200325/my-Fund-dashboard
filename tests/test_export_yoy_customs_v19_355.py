# -*- coding: utf-8 -*-
"""v19.355 — TW 出口 YoY 改走海關 opendata 6053(取代不存在的 FinMind dataset)。

背景:`fetch_tw_export_yoy` 原掛 FinMind `TaiwanMacroEconomics`(FinMind 不存在此
dataset,v19.342 診斷)→ 出口卡片恆無資料。改走海關 opendata 6053 CSV(股票 repo
已驗證穩定源),同月對齊算 YoY。

三個最容易出錯的輸入(§6):
1. CSV 降序(民國年、新月在前)→ 同月對齊須抗亂序,YoY 不可算反
2. 去年同月缺 base → 該月跳過(不偽造)
3. CSV 列數不足(<13)或欄位不符 → 回 [](fail loud,不腦補)
"""
from __future__ import annotations

import repositories.macro_tw_local_repository as mod
from repositories.macro_tw_local_repository import (
    _customs_export_yoy_points,
    fetch_tw_export_yoy,
)


def _make_csv() -> str:
    """18 列真實格式樣本:115 年(2026)1-6 月 + 114 年(2025)1-12 月,**降序**。

    值:2025 全年 1000;2026 各月 1100(6 月 1200)。
      → 2026/M YoY = (1100/1000-1)*100 = 10%,惟 2026/6 = (1200/1000-1)*100 = 20%
      → 2025/M 無 2024 同月 base → 跳過。
    """
    lines = ['"年度","月份","出口總值(新臺幣千元)"']
    for m in range(6, 0, -1):                       # 2026 6→1 降序
        lines.append(f'"115","{m}","{1200 if m == 6 else 1100}"')
    for m in range(12, 0, -1):                      # 2025 12→1 降序
        lines.append(f'"114","{m}","1000"')
    return '\n'.join(lines) + '\n'


# ══════════════════════════════════════════════════════════════
# 純函式 _customs_export_yoy_points
# ══════════════════════════════════════════════════════════════
def test_points_same_month_alignment_and_sort():
    """降序輸入 → 6 個 YoY 點,依 (年,月) 升冪,同月對齊(非 iloc)。"""
    pts = _customs_export_yoy_points(_make_csv())
    assert len(pts) == 6, f'應 6 個 YoY 點(僅 2026 各月有 2025 同月 base),實得 {len(pts)}'
    # 升冪
    keys = [k for k, _ in pts]
    assert keys == sorted(keys), '須依 (年,月) 升冪'
    assert keys[0] == (2026, 1) and keys[-1] == (2026, 6)
    # YoY 值:前 5 月 10%,6 月 20%
    assert all(abs(v - 10.0) < 1e-9 for _, v in pts[:5])
    assert abs(pts[-1][1] - 20.0) < 1e-9, '2026/6 YoY 應 20%'


def test_points_skip_missing_base():
    """去年同月缺 base → 跳過(不偽造)。只有 13 月時僅最新月可算。"""
    lines = ['"年度","月份","出口總值(新臺幣千元)"']
    # 2025/1 + 2024/1..12 → 只有 2025/1 有 2024/1 同月 base
    lines.append('"114","1","1100"')
    for m in range(12, 0, -1):
        lines.append(f'"113","{m}","1000"')
    pts = _customs_export_yoy_points('\n'.join(lines) + '\n')
    assert len(pts) == 1
    assert pts[0][0] == (2025, 1) and abs(pts[0][1] - 10.0) < 1e-9


def test_points_insufficient_rows():
    """<13 列 → [](資料不足不腦補)。"""
    csv = '"年度","月份","出口總值(新臺幣千元)"\n"115","6","1200"\n'
    assert _customs_export_yoy_points(csv) == []


def test_points_missing_columns():
    """欄位不符 → [](不猜欄位)。"""
    csv = '"foo","bar"\n' + '\n'.join(['"1","2"'] * 20) + '\n'
    assert _customs_export_yoy_points(csv) == []


def test_points_base_zero_skipped():
    """base <= 0 → 該月 YoY 跳過(避免除零/爆表)。"""
    lines = ['"年度","月份","出口總值(新臺幣千元)"']
    lines.append('"115","1","1100"')
    lines.append('"114","1","0"')                   # base=0 → skip
    for m in range(12, 1, -1):
        lines.append(f'"113","{m}","1000"')
    pts = _customs_export_yoy_points('\n'.join(lines) + '\n')
    assert all(k != (2025, 1) for k, _ in pts), 'base=0 的月份不可入列'


# ══════════════════════════════════════════════════════════════
# 整合 fetch_tw_export_yoy(monkeypatch fetch_url)
# ══════════════════════════════════════════════════════════════
class _Resp:
    def __init__(self, text: str, status: int = 200):
        self.status_code = status
        self.content = text.encode('utf-8-sig')
        self.text = text


def test_fetch_export_yoy_success(monkeypatch):
    """mock 海關 CSV → dict value/prev/trend/source/inflection 正確。"""
    monkeypatch.setattr(mod, 'fetch_url', lambda *a, **k: _Resp(_make_csv()))
    fetch_tw_export_yoy.cache_clear()
    out = fetch_tw_export_yoy()
    assert out['error'] is None
    assert abs(out['value'] - 20.0) < 1e-9, f"最新月 YoY 應 20%,實得 {out['value']}"
    assert abs(out['prev'] - 10.0) < 1e-9
    assert out['trend'][-1] == 20.0 and len(out['trend']) == 6
    assert out['date_latest'] == '2026-06'
    assert 'Customs:Export6053' in out['source'], out['source']
    assert out['inflection'] == '🟢 正成長加速', out['inflection']   # cur>prev, cur>=0


def test_fetch_export_yoy_source_down(monkeypatch):
    """海關無回應 → error 明確,不偽造(§1 Fail Loud)。"""
    monkeypatch.setattr(mod, 'fetch_url', lambda *a, **k: None)
    fetch_tw_export_yoy.cache_clear()
    out = fetch_tw_export_yoy()
    assert out['value'] is None and out['source'] is None
    assert out['error'] and '海關' in out['error']
