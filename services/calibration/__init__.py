"""services/calibration 子套件 — v19.201 P2-3 5 個 calibration / optimization 模組收編。

從 services/ 平層搬入:
- `macro_score.py`(原 macro_score_calibration.py)— Walk-forward 月度 score replay
- `risk.py`(原 risk_calibration.py)— Risk score z-score 標準化
- `cluster.py`(原 cluster_calibration.py)— Portfolio k-means 群集校準
- `signal_threshold.py`(原 signal_threshold_optimization.py)— Threshold grid search
- `multi_factor.py`(原 multi_factor_optimization.py)— Modern Portfolio Theory allocator

ARCHITECTURE_AUDIT §2.B D3。原 5 個檔散在 services/,subpackage 收編後分類清楚。
既有 `from services.X import Y` 走原檔 shim re-export 不破。
"""
