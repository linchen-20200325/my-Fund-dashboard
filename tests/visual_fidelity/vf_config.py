# -*- coding: utf-8 -*-
"""Visual Fidelity 工具鏈的設定單一位置（BL-0525 Batch A；`DEC-2026-10-29-07`；`docs/v2/71_presentation_contract_migration.md` 第七節）。

兩層驗收，**不得互相冒充**（客戶 2026-10-29 逐字：「CI fixture screenshot ≠ production-like Cloud screenshot」）：

- A. CI deterministic screenshot（`test_ci_fixture_screenshots.py`）：Playwright／Chromium、固定 fixtures、不打外部網路；
  desktop 與 390px；基本 layout 檢查；artifact upload。**automated safety net**，不是正式確認。
- B. Streamlit Cloud screenshot（`cloud_capture.py`）：從下方 `CLOUD_PREVIEW_URL` 取 desktop 與 390px。
  **production-like Visual Fidelity confirmation**。目前執行環境連不到該網域時，只記錄
  `CLOUD_BLOCKED_NOTE`，不停批、不重複向客戶要 URL；環境放行後補正式 Cloud confirmation。

這個檔只放常數與標示字串；不 import 任何專案模組、不含 credential、token、secret（URL 是公開網址）。
"""

from __future__ import annotations

# B 線預覽站（客戶 2026-10-29 提供；公開網址，不是 secret）。
CLOUD_PREVIEW_URL = "https://my-fund-dashboard-3atbdymetmxyi2fbkxujtv.streamlit.app/"

# 兩個視窗：desktop 與 390px mobile（高度取常見手機高度；與 `tests/ui_v2/test_live_390_page.py` 的 390x844 一致）。
VIEWPORTS = {
    "desktop": {"width": 1280, "height": 800},
    "mobile390": {"width": 390, "height": 844},
}

# 標示字串：截圖檔名、artifact 名、報告開頭一律帶這兩個之一，兩層不得混用。
CI_FIXTURE_LABEL = "CI fixture screenshot ≠ production-like Cloud screenshot"
CI_FILE_PREFIX = "ci-fixture"                      # 檔名前綴（ASCII，避免 artifact 檔名編碼問題）
CI_ARTIFACT_NAME = "ci-fixture-screenshots-NOT-production-cloud"
CLOUD_FILE_PREFIX = "cloud-preview"
CLOUD_BLOCKED_NOTE = "production-like Cloud capture blocked by current environment network policy"

# 環境變數：CI job 設定輸出目錄後，截圖測試才會執行（沒設就 skip —— slow lane 的 `-m slow` 會收到本檔，但不產生截圖）。
ENV_OUT_DIR = "VISUAL_FIDELITY_OUT"

# 基本 layout 檢查的門檻（VFG 12 項中可自動量測者；數字是安全網下限，不是設計目標）。
MAX_CHIPS_PER_CARD = 5            # 之十九其一之一：每張卡 chips 至多 5
MIN_CHART_HEIGHT_PX = 120         # 圖表至少這麼高才算「圖表外露」而非一條線
MIN_CHART_WIDTH_RATIO = 0.6       # 圖表寬度至少佔內容區寬度的這個比例
