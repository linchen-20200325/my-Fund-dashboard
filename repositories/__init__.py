"""repositories/ — Data Access Layer.

v11.0 分層架構：純 I/O / 持久化層（FRED / yfinance / MoneyDJ / gspread）。
本層只做資料抓取與快取；嚴禁業務規則或 Streamlit 呼叫。
"""
