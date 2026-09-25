# -*- coding: utf-8 -*-
"""設定與診斷（SET）。

三層，純邏輯與畫面嚴格分離（體例同 ui_v2/alo/）：
  fixtures.py  假資料（示意值）與一份 `44` 第三、四節的規格快照，純 dict/tuple
  logic.py     純函式，零 streamlit import
  theme.py     色票常數 ＋ WCAG 對比計算，零 streamlit import
  page.py      Streamlit 渲染，只呼叫上面三者，自己不做判定

⚠️ 本套件刻意**不 import** `ui_v2.mkt`／`ui_v2.hld`／`ui_v2.exp`／`ui_v2.alo` 的任何東西，也不改它們一個字。
   各頁各自自足；因此本套件與姊妹頁有已知的重複（斷點、文案模板、對比函式），
   要共用是另一輪的重構，本輪不做（派工單只准新增本套件的檔）。
"""
