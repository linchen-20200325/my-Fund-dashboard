"""ui/helpers/holdings.py — 持股英文 → 中文對照（v18.136 從 app.py 搬入）

來自 app.py:111-447。包含：
- _HOLDING_ZH         (~410 keys 英文 → 中文 dict)
- _HOLDING_ZH_SUFFIXES (公司型態後綴 tuple)
- _zh_holding(name)   (核心查詢函式，含後綴剝除)
"""
from __future__ import annotations

_HOLDING_ZH = {
    "MICROSOFT": "微軟", "MICROSOFT CORP": "微軟", "MICROSOFT CORPORATION": "微軟",
    "APPLE": "蘋果", "APPLE INC": "蘋果",
    "NVIDIA": "輝達", "NVIDIA CORP": "輝達", "NVIDIA CORPORATION": "輝達",
    "ALPHABET": "字母控股(Google)", "ALPHABET INC": "字母控股(Google)",
    "ALPHABET INC CLASS A": "字母控股(Google)", "ALPHABET INC CLASS C": "字母控股(Google)",
    "ALPHABET INC-CL A": "字母控股(Google)", "ALPHABET INC-CL C": "字母控股(Google)",
    "GOOGLE": "字母控股(Google)", "GOOGL": "字母控股(Google)", "GOOG": "字母控股(Google)",
    "AMAZON": "亞馬遜", "AMAZON.COM": "亞馬遜", "AMAZON.COM INC": "亞馬遜",
    "META": "Meta(臉書)", "META PLATFORMS": "Meta(臉書)", "META PLATFORMS INC": "Meta(臉書)",
    "FACEBOOK": "Meta(臉書)",
    "TESLA": "特斯拉", "TESLA INC": "特斯拉",
    "BERKSHIRE HATHAWAY": "波克夏", "BERKSHIRE HATHAWAY INC": "波克夏",
    "BERKSHIRE HATHAWAY INC CLASS B": "波克夏",
    "JPMORGAN CHASE": "摩根大通", "JPMORGAN CHASE & CO": "摩根大通", "JPMORGAN": "摩根大通",
    "JOHNSON & JOHNSON": "嬌生",
    "VISA": "Visa", "VISA INC": "Visa", "VISA INC CLASS A": "Visa",
    "MASTERCARD": "萬事達卡", "MASTERCARD INC": "萬事達卡",
    "ELI LILLY": "禮來", "ELI LILLY AND CO": "禮來", "ELI LILLY & CO": "禮來",
    "UNITEDHEALTH": "聯合健康", "UNITEDHEALTH GROUP": "聯合健康",
    "WALMART": "沃爾瑪", "WALMART INC": "沃爾瑪",
    "PROCTER & GAMBLE": "寶僑(P&G)", "PROCTER AND GAMBLE": "寶僑(P&G)",
    "EXXON MOBIL": "艾克森美孚", "EXXON MOBIL CORP": "艾克森美孚",
    "CHEVRON": "雪佛龍", "CHEVRON CORP": "雪佛龍",
    "HOME DEPOT": "家得寶", "HOME DEPOT INC": "家得寶", "THE HOME DEPOT": "家得寶",
    "BANK OF AMERICA": "美國銀行", "BANK OF AMERICA CORP": "美國銀行",
    "MERCK": "默克", "MERCK & CO": "默克", "MERCK & CO INC": "默克",
    "ABBVIE": "艾伯維", "ABBVIE INC": "艾伯維",
    "COSTCO": "好市多", "COSTCO WHOLESALE": "好市多",
    "PEPSICO": "百事", "PEPSICO INC": "百事",
    "COCA-COLA": "可口可樂", "COCA COLA": "可口可樂", "THE COCA-COLA COMPANY": "可口可樂",
    "MCDONALD'S": "麥當勞", "MCDONALDS": "麥當勞", "MCDONALD'S CORP": "麥當勞",
    "DISNEY": "迪士尼", "WALT DISNEY": "迪士尼", "THE WALT DISNEY COMPANY": "迪士尼",
    "NETFLIX": "網飛", "NETFLIX INC": "網飛",
    "ADOBE": "Adobe", "ADOBE INC": "Adobe",
    "SALESFORCE": "賽富時", "SALESFORCE INC": "賽富時", "SALESFORCE.COM": "賽富時",
    "ORACLE": "甲骨文", "ORACLE CORP": "甲骨文", "ORACLE CORPORATION": "甲骨文",
    "INTEL": "英特爾", "INTEL CORP": "英特爾", "INTEL CORPORATION": "英特爾",
    "ADVANCED MICRO DEVICES": "超微(AMD)", "AMD": "超微(AMD)",
    "QUALCOMM": "高通", "QUALCOMM INC": "高通",
    "BROADCOM": "博通", "BROADCOM INC": "博通",
    "CISCO": "思科", "CISCO SYSTEMS": "思科",
    "IBM": "IBM", "INTERNATIONAL BUSINESS MACHINES": "IBM",
    "PFIZER": "輝瑞", "PFIZER INC": "輝瑞",
    "GOLDMAN SACHS": "高盛", "GOLDMAN SACHS GROUP": "高盛", "THE GOLDMAN SACHS GROUP": "高盛",
    "MORGAN STANLEY": "摩根士丹利",
    "WELLS FARGO": "富國銀行", "WELLS FARGO & CO": "富國銀行",
    "CITIGROUP": "花旗", "CITIGROUP INC": "花旗",
    "BLACKROCK": "貝萊德", "BLACKROCK INC": "貝萊德",
    "TAIWAN SEMICONDUCTOR": "台積電",
    "TAIWAN SEMICONDUCTOR MANUFACTURING": "台積電",
    "TAIWAN SEMICONDUCTOR MFG": "台積電",
    "TSMC": "台積電", "TSM": "台積電",
    "ASML": "艾司摩爾", "ASML HOLDING": "艾司摩爾", "ASML HOLDING NV": "艾司摩爾",
    "SAMSUNG ELECTRONICS": "三星電子", "SAMSUNG": "三星",
    "ALIBABA": "阿里巴巴", "ALIBABA GROUP": "阿里巴巴", "ALIBABA GROUP HOLDING": "阿里巴巴",
    "TENCENT": "騰訊", "TENCENT HOLDINGS": "騰訊",
    "TOYOTA": "豐田", "TOYOTA MOTOR": "豐田", "TOYOTA MOTOR CORP": "豐田",
    "SONY": "索尼", "SONY GROUP": "索尼", "SONY GROUP CORP": "索尼",
    "NESTLE": "雀巢", "NESTLÉ": "雀巢", "NESTLE SA": "雀巢",
    "LVMH": "路威酩軒", "LVMH MOET HENNESSY": "路威酩軒",
    "NOVO NORDISK": "諾和諾德",
    "ROCHE": "羅氏", "ROCHE HOLDING": "羅氏", "ROCHE HOLDING AG": "羅氏",
    "ASTRAZENECA": "阿斯特捷利康", "ASTRAZENECA PLC": "阿斯特捷利康",
    "NOVARTIS": "諾華", "NOVARTIS AG": "諾華",
    "SHELL": "殼牌", "SHELL PLC": "殼牌",
    "HSBC": "匯豐", "HSBC HOLDINGS": "匯豐", "HSBC HOLDINGS PLC": "匯豐",
    "TENCENT MUSIC": "騰訊音樂",
    "RELIANCE INDUSTRIES": "信實工業",
    "INFOSYS": "印孚瑟斯",
    "HDFC BANK": "HDFC 銀行",
    "ICICI BANK": "ICICI 銀行",
    "BAIDU": "百度", "JD.COM": "京東",
    "MEITUAN": "美團", "PINDUODUO": "拼多多", "PDD HOLDINGS": "拼多多",
    "NIO": "蔚來", "XPENG": "小鵬", "LI AUTO": "理想汽車",
    "BYD": "比亞迪", "BYD COMPANY": "比亞迪",
    "SOFTBANK": "軟銀", "SOFTBANK GROUP": "軟銀",
    "KEYENCE": "基恩斯", "TOKYO ELECTRON": "東京威力科創",
    "FAST RETAILING": "迅銷集團(Uniqlo)",
    "MITSUBISHI": "三菱", "SUMITOMO MITSUI": "三井住友",
    "AIRBUS": "空中巴士", "AIRBUS SE": "空中巴士",
    "SAP": "SAP", "SAP SE": "SAP",
    "SIEMENS": "西門子", "SIEMENS AG": "西門子",
    "BANCO SANTANDER": "桑坦德銀行",
    "TOTALENERGIES": "道達爾能源", "TOTAL": "道達爾能源",
    # 台股
    "HON HAI PRECISION": "鴻海", "HON HAI PRECISION INDUSTRY": "鴻海",
    "HON HAI PRECISION INDUSTRY CO": "鴻海", "FOXCONN": "鴻海",
    "MEDIATEK": "聯發科", "MEDIATEK INC": "聯發科",
    "UNITED MICROELECTRONICS": "聯電", "UMC": "聯電",
    "DELTA ELECTRONICS": "台達電",
    "FUBON FINANCIAL": "富邦金", "FUBON FINANCIAL HOLDING": "富邦金",
    "CATHAY FINANCIAL": "國泰金", "CATHAY FINANCIAL HOLDING": "國泰金",
    "CHUNGHWA TELECOM": "中華電",
    "CTBC FINANCIAL": "中信金", "CTBC FINANCIAL HOLDING": "中信金",
    "MEGA FINANCIAL": "兆豐金", "MEGA FINANCIAL HOLDING": "兆豐金",
    "FIRST FINANCIAL": "第一金", "FIRST FINANCIAL HOLDING": "第一金",
    "HUA NAN FINANCIAL": "華南金", "HUA NAN FINANCIAL HOLDINGS": "華南金",
    "HOTAI MOTOR": "和泰車",
    "LARGAN PRECISION": "大立光",
    "FORMOSA PLASTICS": "台塑",
    "NAN YA PLASTICS": "南亞", "NAN YA": "南亞",
    "UNI-PRESIDENT": "統一企業", "UNI PRESIDENT": "統一企業",
    "CHINA STEEL": "中鋼",
    "EVERGREEN MARINE": "長榮海運",
    "YANG MING MARINE": "陽明海運", "YANG MING MARINE TRANSPORT": "陽明海運",
    "ASE TECHNOLOGY": "日月光投控", "ASE TECHNOLOGY HOLDING": "日月光投控",
    # 日股
    "MITSUBISHI UFJ FINANCIAL": "三菱UFJ金融", "MITSUBISHI UFJ FINANCIAL GROUP": "三菱UFJ金融",
    "SUMITOMO MITSUI FINANCIAL": "三井住友金融", "SUMITOMO MITSUI FINANCIAL GROUP": "三井住友金融",
    "HITACHI": "日立", "HONDA": "本田", "HONDA MOTOR": "本田",
    "NINTENDO": "任天堂", "KDDI": "KDDI", "RECRUIT": "瑞可利", "RECRUIT HOLDINGS": "瑞可利",
    "MURATA MANUFACTURING": "村田製作所",
    "SHIN-ETSU CHEMICAL": "信越化學", "SHIN ETSU CHEMICAL": "信越化學",
    "DAIICHI SANKYO": "第一三共",
    "ASTELLAS PHARMA": "安斯泰來",
    "TAKEDA PHARMACEUTICAL": "武田藥品",
    "DENSO": "電裝", "PANASONIC": "松下", "CANON": "佳能",
    "NIPPON STEEL": "日本製鐵", "SUBARU": "速霸陸",
    "NISSAN": "日產", "NISSAN MOTOR": "日產",
    # 韓股
    "SK HYNIX": "SK海力士",
    "HYUNDAI MOTOR": "現代汽車", "HYUNDAI MOBIS": "現代摩比斯",
    "LG ENERGY SOLUTION": "LG新能源", "LG CHEM": "LG化學",
    "NAVER": "NAVER", "KAKAO": "Kakao",
    "POSCO": "浦項製鐵", "POSCO HOLDINGS": "浦項製鐵",
    "SAMSUNG BIOLOGICS": "三星生物",
    "KIA": "起亞", "KIA CORP": "起亞",
    # 陸港股
    "PING AN": "中國平安", "PING AN INSURANCE": "中國平安",
    "ICBC": "工商銀行", "INDUSTRIAL AND COMMERCIAL BANK OF CHINA": "工商銀行",
    "BANK OF CHINA": "中國銀行",
    "CHINA CONSTRUCTION BANK": "建設銀行",
    "AGRICULTURAL BANK OF CHINA": "農業銀行",
    "BANK OF COMMUNICATIONS": "交通銀行",
    "AIA": "友邦保險", "AIA GROUP": "友邦保險",
    "SINOPEC": "中石化",
    "PETROCHINA": "中石油",
    "CHINA MOBILE": "中國移動",
    "GEELY": "吉利汽車", "GEELY AUTOMOBILE": "吉利汽車",
    "XIAOMI": "小米", "LENOVO": "聯想", "LENOVO GROUP": "聯想",
    "KUAISHOU": "快手", "BILIBILI": "嗶哩嗶哩",
    "CNOOC": "中海油",
    # 印度 / 東南亞
    "TATA CONSULTANCY SERVICES": "塔塔顧問", "TCS": "塔塔顧問",
    "BHARTI AIRTEL": "印度電信",
    "SEA LIMITED": "Sea", "SEA": "Sea",
    "GRAB HOLDINGS": "Grab",
    # 澳洲 / 紐西蘭（v18.97 補強）
    "BHP GROUP": "必和必拓", "BHP GROUP LIMITED": "必和必拓", "BHP": "必和必拓",
    "RIO TINTO": "力拓", "RIO TINTO LIMITED": "力拓", "RIO TINTO PLC": "力拓",
    "FORTESCUE": "福斯特", "FORTESCUE METALS GROUP": "福斯特", "FORTESCUE LIMITED": "福斯特",
    "CSL": "CSL生技", "CSL LIMITED": "CSL生技",
    "COMMONWEALTH BANK": "澳洲聯邦銀行", "COMMONWEALTH BANK OF AUSTRALIA": "澳洲聯邦銀行",
    "WESTPAC": "西太平洋銀行", "WESTPAC BANKING": "西太平洋銀行",
    "WESTPAC BANKING CORPORATION": "西太平洋銀行",
    "NATIONAL AUSTRALIA BANK": "澳洲國民銀行", "NAB": "澳洲國民銀行",
    "ANZ": "澳新銀行", "AUSTRALIA AND NEW ZEALAND BANKING GROUP": "澳新銀行",
    "ANZ GROUP HOLDINGS": "澳新銀行",
    "MACQUARIE GROUP": "麥格理集團", "MACQUARIE": "麥格理集團",
    "WOOLWORTHS GROUP": "Woolworths超市", "WOOLWORTHS": "Woolworths超市",
    "WESFARMERS": "西農集團", "WESFARMERS LIMITED": "西農集團",
    "TELSTRA": "澳洲電信", "TELSTRA GROUP": "澳洲電信",
    "GOODMAN GROUP": "Goodman 物流地產",
    "TRANSURBAN": "Transurban收費道路", "TRANSURBAN GROUP": "Transurban收費道路",
    "NEWCREST MINING": "紐克雷斯礦業",
    "AMP": "AMP金融",
    "FISHER & PAYKEL HEALTHCARE": "費雪派克醫療",
    "AUCKLAND INTERNATIONAL AIRPORT": "奧克蘭機場",
    # 拉美（v18.97 補強）
    "PETROLEO BRASILEIRO": "巴西石油", "PETROBRAS": "巴西石油",
    "PETROLEO BRASILEIRO PETROBRAS": "巴西石油",
    "VALE": "淡水河谷", "VALE SA": "淡水河谷", "VALE S.A.": "淡水河谷",
    "ITAU UNIBANCO": "伊塔烏聯合銀行", "ITAU UNIBANCO HOLDING": "伊塔烏聯合銀行",
    "BANCO BRADESCO": "巴西布拉德斯科銀行", "BRADESCO": "巴西布拉德斯科銀行",
    "BANCO SANTANDER BRASIL": "桑坦德巴西銀行",
    "AMBEV": "百威安貝夫", "AMBEV SA": "百威安貝夫",
    "MERCADOLIBRE": "Mercado Libre", "MERCADO LIBRE": "Mercado Libre",
    "AMERICA MOVIL": "美洲電信", "AMÉRICA MÓVIL": "美洲電信",
    "FEMSA": "FEMSA可口可樂", "FOMENTO ECONOMICO MEXICANO": "FEMSA可口可樂",
    "WALMART DE MEXICO": "墨西哥沃爾瑪", "WALMEX": "墨西哥沃爾瑪",
    "GRUPO MEXICO": "墨西哥集團",
    "CEMEX": "西麥斯水泥", "CEMEX SAB DE CV": "西麥斯水泥",
    "GRUPO FINANCIERO BANORTE": "巴諾爾特金融", "BANORTE": "巴諾爾特金融",
    "SUZANO": "蘇札諾紙漿", "SUZANO SA": "蘇札諾紙漿",
    "BANCO DO BRASIL": "巴西銀行",
    "B3": "B3巴西交易所", "B3 SA - BRASIL BOLSA BALCAO": "B3巴西交易所",
    "JBS": "JBS肉品", "JBS SA": "JBS肉品",
    "ECOPETROL": "哥倫比亞國家石油",
    "BANCOLOMBIA": "哥倫比亞銀行",
    "SQM": "智利化工礦業", "SOCIEDAD QUIMICA Y MINERA DE CHILE": "智利化工礦業",
    "FALABELLA": "Falabella零售",
    # 歐洲核心（v18.102 補強：DAX / CAC40 / FTSE100 / SMI / 北歐）
    "SAP": "SAP軟體", "SAP SE": "SAP軟體",
    "SIEMENS": "西門子", "SIEMENS AG": "西門子",
    "SIEMENS HEALTHINEERS": "西門子醫療",
    "ALLIANZ": "安聯保險", "ALLIANZ SE": "安聯保險",
    "DEUTSCHE TELEKOM": "德國電信",
    "DEUTSCHE BANK": "德意志銀行",
    "MERCEDES-BENZ GROUP": "賓士集團", "MERCEDES BENZ GROUP": "賓士集團",
    "BMW": "BMW", "BAYERISCHE MOTOREN WERKE": "BMW",
    "VOLKSWAGEN": "福斯汽車", "VOLKSWAGEN AG": "福斯汽車",
    "BASF": "BASF化學",
    "ADIDAS": "愛迪達",
    "MUNICH RE": "慕尼黑再保", "MUENCHENER RUECKVERSICHERUNGS": "慕尼黑再保",
    "INFINEON TECHNOLOGIES": "英飛凌半導體", "INFINEON": "英飛凌半導體",
    "AIRBUS": "空中巴士", "AIRBUS SE": "空中巴士",
    "LVMH": "LVMH精品", "LVMH MOET HENNESSY LOUIS VUITTON": "LVMH精品",
    "L'OREAL": "萊雅", "LOREAL": "萊雅",
    "HERMES": "愛馬仕", "HERMES INTERNATIONAL": "愛馬仕",
    "KERING": "開雲集團",
    "TOTALENERGIES": "道達爾能源", "TOTAL ENERGIES": "道達爾能源",
    "SANOFI": "賽諾菲藥業",
    "BNP PARIBAS": "法國巴黎銀行",
    "AXA": "安盛保險",
    "SCHNEIDER ELECTRIC": "施耐德電機",
    "AIR LIQUIDE": "液空集團",
    "DANONE": "達能食品",
    "SAINT-GOBAIN": "聖戈班建材", "COMPAGNIE DE SAINT GOBAIN": "聖戈班建材",
    "PERNOD RICARD": "保樂力加",
    "VINCI": "Vinci 工程",
    "STELLANTIS": "Stellantis汽車",
    "ASTRAZENECA": "阿斯特捷利康",
    "GLAXOSMITHKLINE": "葛蘭素史克", "GSK": "葛蘭素史克", "GSK PLC": "葛蘭素史克",
    "HSBC": "匯豐控股", "HSBC HOLDINGS": "匯豐控股",
    "BARCLAYS": "巴克萊銀行", "BARCLAYS PLC": "巴克萊銀行",
    "LLOYDS BANKING GROUP": "勞埃德銀行", "LLOYDS": "勞埃德銀行",
    "BP": "BP石油", "BP PLC": "BP石油",
    "SHELL": "殼牌能源", "SHELL PLC": "殼牌能源",
    "DIAGEO": "帝亞吉歐酒業", "DIAGEO PLC": "帝亞吉歐酒業",
    "UNILEVER": "聯合利華", "UNILEVER PLC": "聯合利華",
    "RECKITT BENCKISER": "利潔時", "RECKITT": "利潔時",
    "VODAFONE": "沃達豐電信", "VODAFONE GROUP": "沃達豐電信",
    "PRUDENTIAL": "保誠保險", "PRUDENTIAL PLC": "保誠保險",
    "BRITISH AMERICAN TOBACCO": "英美煙草", "BAT": "英美煙草",
    "ROCHE": "羅氏藥業", "ROCHE HOLDING": "羅氏藥業",
    "NESTLE": "雀巢", "NESTLE SA": "雀巢", "NESTLÉ": "雀巢",
    "NOVARTIS": "諾華製藥", "NOVARTIS AG": "諾華製藥",
    "UBS": "瑞銀集團", "UBS GROUP": "瑞銀集團",
    "ZURICH INSURANCE": "蘇黎世保險", "ZURICH INSURANCE GROUP": "蘇黎世保險",
    "ABB": "ABB機電", "ABB LTD": "ABB機電",
    "RICHEMONT": "歷峰集團", "COMPAGNIE FINANCIERE RICHEMONT": "歷峰集團",
    "NOVO NORDISK": "諾和諾德",
    "MAERSK": "馬士基航運", "AP MOLLER MAERSK": "馬士基航運",
    "ORSTED": "沃旭能源", "ØRSTED": "沃旭能源",
    "VOLVO": "Volvo卡車",
    "ATLAS COPCO": "阿特拉斯科普柯",
    "ERICSSON": "易利信通訊", "TELEFONAKTIEBOLAGET LM ERICSSON": "易利信通訊",
    "H&M": "H&M服飾", "HENNES & MAURITZ": "H&M服飾",
    "EQUINOR": "Equinor能源", "EQUINOR ASA": "Equinor能源",
    "DSV": "DSV物流", "DSV AS": "DSV物流",
    "INGKA": "宜家集團",
    "ENI": "Eni石油", "ENI SPA": "Eni石油",
    "FERRARI": "法拉利", "FERRARI NV": "法拉利",
    "INTESA SANPAOLO": "聯合聖保羅銀行",
    "UNICREDIT": "義大利聯合信貸銀行",
    "IBERDROLA": "伊比德羅拉電力",
    "BANCO SANTANDER": "桑坦德銀行", "SANTANDER": "桑坦德銀行",
    "INDITEX": "Inditex(Zara母公司)",
    "REPSOL": "Repsol能源",
    "ASML HOLDING": "ASML半導體", "ASML": "ASML半導體",
    "PROSUS": "Prosus科技", "PROSUS NV": "Prosus科技",
    "HEINEKEN": "海尼根啤酒", "HEINEKEN NV": "海尼根啤酒",
    "ING GROEP": "ING金融", "ING": "ING金融",
    "AHOLD DELHAIZE": "皇家阿霍德", "KONINKLIJKE AHOLD DELHAIZE": "皇家阿霍德",
    # 新興市場（v18.102 補強：土耳其 / 印尼 / 越南 / 南非 / 菲律賓 / 馬來西亞）
    "TURKIYE GARANTI BANKASI": "土耳其擔保銀行", "GARANTI BBVA": "土耳其擔保銀行",
    "TURKIYE IS BANKASI": "土耳其實業銀行",
    "AKBANK": "土耳其Akbank",
    "BIM BIRLESIK MAGAZALAR": "BIM超市",
    "KOC HOLDING": "Koç控股",
    "SABANCI HOLDING": "Sabanci控股",
    "TURK HAVA YOLLARI": "土耳其航空", "TURKISH AIRLINES": "土耳其航空",
    "ASTRA INTERNATIONAL": "阿斯特拉國際",
    "BANK CENTRAL ASIA": "印尼中亞銀行", "BCA": "印尼中亞銀行",
    "BANK MANDIRI": "印尼曼底里銀行",
    "BANK RAKYAT INDONESIA": "印尼人民銀行", "BRI": "印尼人民銀行",
    "TELKOM INDONESIA": "印尼電信", "TELEKOMUNIKASI INDONESIA": "印尼電信",
    "UNILEVER INDONESIA": "印尼聯合利華",
    "GUDANG GARAM": "印尼Gudang Garam煙草",
    "VINGROUP": "Vingroup越南", "VINGROUP JSC": "Vingroup越南",
    "VINHOMES": "Vinhomes不動產",
    "VIETCOMBANK": "越南外貿銀行", "BANK FOR FOREIGN TRADE OF VIETNAM": "越南外貿銀行",
    "MASAN GROUP": "Masan集團",
    "HOA PHAT GROUP": "和發鋼鐵",
    "NASPERS": "Naspers南非", "NASPERS LIMITED": "Naspers南非",
    "FIRSTRAND": "FirstRand銀行",
    "STANDARD BANK GROUP": "南非標準銀行",
    "ANGLO AMERICAN": "英美資源", "ANGLO AMERICAN PLC": "英美資源",
    "MTN GROUP": "MTN電信",
    "SASOL": "Sasol能源",
    "SHOPRITE HOLDINGS": "Shoprite零售",
    "SM INVESTMENTS": "SM投資",
    "AYALA": "Ayala菲律賓", "AYALA CORPORATION": "Ayala菲律賓",
    "BDO UNIBANK": "BDO菲律賓",
    "JOLLIBEE FOODS": "Jollibee快餐",
    "PETRONAS CHEMICALS": "馬國石油化學", "PETRONAS CHEMICALS GROUP": "馬國石油化學",
    "MAYBANK": "馬來亞銀行", "MALAYAN BANKING": "馬來亞銀行",
    "PUBLIC BANK BERHAD": "馬國大眾銀行",
    "CIMB GROUP": "馨豐銀行",
    "TENAGA NASIONAL": "馬國國家能源",
    "EMAAR PROPERTIES": "Emaar地產",
    "QATAR NATIONAL BANK": "卡達國家銀行", "QNB": "卡達國家銀行",
    "SAUDI ARAMCO": "沙烏地阿美", "SAUDI ARABIAN OIL": "沙烏地阿美",
    "AL RAJHI BANK": "Al Rajhi銀行",
}
_HOLDING_ZH_SUFFIXES = (" INC", " CORP", " CORPORATION", " CO", " CO.",
                        " LTD", " LIMITED", " PLC", " LLC", " AG", " SA",
                        " SE", " NV", " GROUP", " HOLDINGS", " HOLDING",
                        " COMPANY", " THE")

# v18.125 B-C.3: _parse_indicator_date 已搬至 ui/helpers/session.py
from ui.helpers.session import parse_indicator_date as _parse_indicator_date  # noqa: F401


def _zh_holding(name: str) -> str:
    """傳入英文持股名稱，回傳中文對照；查不到回空字串。

    v18.15: 改為迭代式後綴剝除，可處理雙層後綴（如 "CTBC FINANCIAL HOLDING CO LTD"）。
    """
    if not name: return ""
    key = str(name).upper().strip().rstrip(".,;").strip()
    if key in _HOLDING_ZH: return _HOLDING_ZH[key]
    # 反覆剝除常見公司型態後綴，每剝一層就查表（最多 5 層保護無窮迴圈）
    for _ in range(5):
        stripped = False
        for suffix in _HOLDING_ZH_SUFFIXES:
            if key.endswith(suffix):
                key = key[: -len(suffix)].strip().rstrip(",.").strip()
                stripped = True
                if key in _HOLDING_ZH: return _HOLDING_ZH[key]
                break
        if not stripped: break
    # 首詞回退
    first = key.split()[0] if key.split() else ""
    if first and first in _HOLDING_ZH: return _HOLDING_ZH[first]
    return ""


# ══════════════════════════════════════════════════════════════════════
# v19.282 持股明細共用渲染器(SSOT)
# ──────────────────────────────────────────────────────────────────────
# 背景:Tab2 單一基金(tab2_single_fund L1100-1138)與 組合健檢
# (fund_grp_health/investment.py L156-211)各有一份 byte-identical 的
# 「產業配置 + 前10大持股」渲染 → 重複邏輯違反 SSOT。抽此共用 render,兩處共用。
# 純 L3 UI 渲染:僅依 streamlit + shared.colors(L0)+ 同模組 _zh_holding,無 IO。
# ══════════════════════════════════════════════════════════════════════
def render_holdings_detail(holdings: dict) -> bool:
    """渲染持股明細(🏭 產業配置 + 🏆 前10大持股,兩欄)。

    holdings:fetch_holdings 契約 dict(sector_alloc / top_holdings)。
    回傳 True 若渲染了任何持股/產業;False 若全空(caller 自行決定空訊息)。
    """
    import streamlit as st
    from shared.colors import (
        GH_BG_CARD, GRAY_55, GRAY_CC, INFO_BLUE,
        MD_BLUE_500, MD_ORANGE_300, TRAFFIC_NEUTRAL,
    )
    _sectors = (holdings or {}).get("sector_alloc") or []
    _tops = (holdings or {}).get("top_holdings") or []
    if not (_sectors or _tops):
        return False

    _hc1, _hc2 = st.columns(2)
    with _hc1:
        if _sectors:
            st.markdown("**🏭 產業配置**")
            for _sec in _sectors[:10]:
                _sn = str(_sec.get("name", ""))[:18]
                _sp = float(_sec.get("pct", 0) or 0)
                st.markdown(
                    f"<div style='display:flex;align-items:center;gap:8px;margin:3px 0'>"
                    f"<div style='color:{GRAY_CC};font-size:11px;width:95px;flex-shrink:0'>{_sn}</div>"
                    f"<div style='flex:1;background:#1a1a2a;border-radius:3px;height:10px'>"
                    f"<div style='background:{MD_BLUE_500};width:{min(_sp*3,100):.0f}%;"
                    f"height:100%;border-radius:3px'></div></div>"
                    f"<div style='color:{MD_BLUE_500};font-size:11px;width:40px;text-align:right'>"
                    f"{_sp:.1f}%</div></div>",
                    unsafe_allow_html=True)
    with _hc2:
        if _tops:
            st.markdown("**🏆 前10大持股**")
            for _i, _top in enumerate(_tops[:10], 1):
                _tn_raw = str(_top.get("name", ""))
                _zh = _zh_holding(_tn_raw)
                _tn = _tn_raw[:22]
                _zh_html = (f"<span style='color:{MD_ORANGE_300};font-size:10px;margin-left:6px'>"
                            f"({_zh})</span>" if _zh else "")
                _tp = float(_top.get("pct", 0) or 0)
                _ts = str(_top.get("sector", ""))[:12]
                st.markdown(
                    f"<div style='display:flex;gap:6px;padding:3px 8px;"
                    f"background:{GH_BG_CARD};border-radius:6px;margin:2px 0'>"
                    f"<span style='color:{GRAY_55};font-size:11px;width:16px'>#{_i}</span>"
                    f"<span style='font-size:11px;flex:1'>{_tn}{_zh_html}</span>"
                    f"<span style='color:{TRAFFIC_NEUTRAL};font-size:10px'>{_ts}</span>"
                    f"<span style='color:{INFO_BLUE};font-weight:700;font-size:11px;"
                    f"width:36px;text-align:right'>{_tp:.1f}%</span>"
                    f"</div>", unsafe_allow_html=True)
    return True


def render_holdings_diag(holdings: dict) -> None:
    """空持股時顯示逐源抓取診斷(SSOT:Tab2 + 組合健檢共用)。

    holdings 內若帶 `diag`(v19.280 三源逐一結果)→ 攤 st.code;否則提示舊版。
    """
    import streamlit as st
    st.caption("⬜ 三源持股全抓不到(MoneyDJ → cnyes → Morningstar)")
    _diag = (holdings or {}).get("diag") or []
    if _diag:
        st.caption("🔍 **抓取診斷**(逐源結果):")
        st.code("\n".join(str(_x) for _x in _diag), language=None)
    else:
        st.caption(
            f"🔍 來源={(holdings or {}).get('source', '—')}"
            "(若無 diag 表示線上仍為舊版,請 Manage app → Reboot + 強制刷新)"
        )
