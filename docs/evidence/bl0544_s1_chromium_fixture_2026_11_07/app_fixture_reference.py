# harness only: synthetic fixture data (tests/ui_v3/market_stubs), NOT market data
import sys
R = "/home/user/my-Fund-dashboard/.claude/worktrees/agent-ad7616d417aa37e1a"
sys.path.insert(0, R); sys.path.insert(0, R + "/tests/ui_v3")
import market_stubs as ms
from ui_v3.adapters import market_page as adapter
adapter.load = lambda sources: (ms.view(), ms.table())
from ui_v3 import app_preview
app_preview.main()
