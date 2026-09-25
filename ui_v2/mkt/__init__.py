# -*- coding: utf-8 -*-
"""市場總覽（MKT）。

三層，純邏輯與畫面嚴格分離：
  fixtures.py  假資料（示意值），純 dict/list
  logic.py     純函式，零 streamlit import
  theme.py     色票常數，零 streamlit import
  page.py      Streamlit 渲染，只呼叫上面三者，自己不做判定
"""
