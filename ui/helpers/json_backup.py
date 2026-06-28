"""v19.204 P2-7 shim — ui/helpers/json_backup.py 已搬 ui/helpers/io/json_backup.py。"""
from __future__ import annotations

from ui.helpers.io.json_backup import *  # noqa: F401, F403

# Re-export 含 _* 私函(dir+globals pattern,跟 P1-5/P2-3 一致)
from ui.helpers import io as _pkg
_mod = getattr(_pkg, 'json_backup')
for _name in dir(_mod):
    if not _name.startswith('__'):
        globals()[_name] = getattr(_mod, _name)
del _pkg, _mod, _name
