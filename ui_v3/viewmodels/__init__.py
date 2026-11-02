# -*- coding: utf-8 -*-
"""View Model Contract（80 第 6 節）：純 Python、無 streamlit、無 I/O、無 services import。

只重新匯出契約需要的名稱；import 時零副作用。
"""
from ui_v3.viewmodels.action_slot import (  # noqa: F401
    ACTION_SLOT_SOURCES_ENABLED,
    ACTION_VOCABULARY,
    ActionSlot,
)
from ui_v3.viewmodels.common import (  # noqa: F401
    MISSING_TEXT,
    STATUSES,
    FactMeta,
    ValueFacts,
)
from ui_v3.viewmodels.components import (  # noqa: F401
    CHART_PERIODS,
    CHIP_KINDS,
    ChartCard,
    ChartPoint,
    ChartSeries,
    EvidenceItem,
    MetricCard,
    MissingItem,
    ProvenanceTag,
    StatusChip,
)
