"""services/calibration 子套件 — v19.201 P2-3 5 個 calibration / optimization 模組收編。

從 services/ 平層搬入(**現存 1 檔**:macro_score;其餘 4 檔已逐次拔毒,逐條見下):
- `macro_score.py`(原 macro_score_calibration.py)— Walk-forward 月度 score replay
- ~~`risk.py`(原 risk_calibration.py)— Risk score z-score 標準化~~ 2026-08-28 Phase 1.4 拔毒(production 0 caller)
- ~~`cluster.py`(原 cluster_calibration.py)~~ v19.213 P0-3-#5 拔毒(production 0 caller)
- ~~`signal_threshold.py`(原 signal_threshold_optimization.py)— Threshold grid search~~ 2026-08-28 Phase 1.4 拔毒(production 0 caller)
- ~~`multi_factor.py`(原 multi_factor_optimization.py)— Modern Portfolio Theory allocator~~
  2026-08-31 拔毒(production 0 caller,auto_search 封閉死簇;客戶 2026-08-31 授權死碼清理)

ARCHITECTURE_AUDIT §2.B D3。原 5 個檔散在 services/,subpackage 收編後分類清楚。
既有 `from services.X import Y` 走原檔 shim re-export 不破。
"""
