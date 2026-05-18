"""ui/ — Presentation Layer (Streamlit only).

v11.0 分層架構：UI 元件 + Tab 渲染 + session helper。
本層可呼叫 services/ 與 models/，不可呼叫 repositories/（必須走 service）。
"""
