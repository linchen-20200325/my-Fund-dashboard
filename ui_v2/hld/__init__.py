# -*- coding: utf-8 -*-
"""持倉體檢（HLD）。

三層，純邏輯與畫面嚴格分離（體例同 ui_v2/mkt/）：
  fixtures.py  假資料（示意值），純 dict/list
  logic.py     純函式，零 streamlit import
  theme.py     色票常數 ＋ WCAG 對比計算，零 streamlit import
  page.py      Streamlit 渲染，只呼叫上面三者，自己不做判定

⚠️ 本套件刻意**不 import** `ui_v2.mkt` 的任何東西，也不改它一個字。
   兩頁各自自足；要共用是下一輪的重構，本輪不做（派工單明令）。
   **因此本套件與 `ui_v2/mkt/` 有已知的重複**，逐筆寫在本輪回報裡。
"""
