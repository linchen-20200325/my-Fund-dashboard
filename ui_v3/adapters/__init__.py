# -*- coding: utf-8 -*-
"""adapters 層 —— **唯一**允許 import `services.v2_tables`／`services.v2_domain` 的位置（80 第 2、4.2 節）。

本批只有這份說明（stub）：**零 import、零函式、不接任何真資料**。

日後（逐頁 wireframe 核准後的批次）的契約：
- adapters 呼叫下層（`services.v2_tables.*`、`services/v2_domain`），注入 session state，遮蔽失敗原文；
  把下層結果交給 `ui_v3/viewmodels` 組成元件。
- adapters **不**計算領域值、**不**決定狀態語意、**不**自己打網路（要取數經下層才可）。
- 下層的中文 reason／狀態字面不得外洩成 presentation：一律以 `reason_code`／`status` 鍵映射（80 R10）。
- 每個 adapter 一檔 `<page>_source.py`；新增檔會自動被 `tests/ui_v3/test_ui_v3_import_guard.py` 納入掃描。
- 守衛現況：本層除 `services.v2_tables`／`services.v2_domain` 外，仍不得 import 其他舊樹模組
  （`repositories`／`shared`／`infra`／`ui`…）；若某 adapter 確實需要 `shared/` 常數，須走 Gate 並明列白名單。
"""
