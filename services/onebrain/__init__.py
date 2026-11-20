"""services/onebrain/ -- OneBrain OB-B 最小離線切片（僅型別、介面、離線 Fake）。

授權依據：`DEC-2026-11-20-01`（客戶本人 2026-11-20 逐字確認；範圍以該逐字原文為準）。

本套件只含：Provider-neutral 型別、抽象介面、離線 `FakeProvider`、結構化錯誤／降級狀態。

本套件**不得**：
- 被任何 production 路徑、頁面或 UI import（由 `tests/test_onebrain_offline_guard.py` 守）；
- 使用真實 Provider、SDK、金鑰、環境變數、網路、檔案系統、prompt、Digest、Risk Cap 或投資行動。

本檔刻意只有這段說明：沒有 import、沒有 re-export、沒有執行期副作用。
"""
