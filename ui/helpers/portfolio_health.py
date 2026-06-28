"""v19.204 P2-7 shim — ui/helpers/portfolio_health.py 已搬 ui/helpers/portfolio/health.py。"""
from __future__ import annotations

from ui.helpers.portfolio.health import *  # noqa: F401, F403

# Re-export 含 _* 私函(dir+globals pattern,跟 P1-5/P2-3 一致)
from ui.helpers import portfolio as _pkg
_mod = getattr(_pkg, 'health')
for _name in dir(_mod):
    if not _name.startswith('__'):
        globals()[_name] = getattr(_mod, _name)
del _pkg, _mod, _name
