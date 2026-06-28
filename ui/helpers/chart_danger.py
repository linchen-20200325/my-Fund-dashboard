"""v19.204 P2-7 shim — ui/helpers/chart_danger.py 已搬 ui/helpers/chart/danger.py。"""
from __future__ import annotations

from ui.helpers.chart.danger import *  # noqa: F401, F403

# Re-export 含 _* 私函(dir+globals pattern,跟 P1-5/P2-3 一致)
from ui.helpers import chart as _pkg
_mod = getattr(_pkg, 'danger')
for _name in dir(_mod):
    if not _name.startswith('__'):
        globals()[_name] = getattr(_mod, _name)
del _pkg, _mod, _name
