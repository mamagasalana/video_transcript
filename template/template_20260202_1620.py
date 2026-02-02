from __future__ import annotations
from pydantic import BaseModel, Field
from enum import Enum
from typing import List, Optional, Literal, Annotated

# its good to have an introduction that explain the background of this template
"""
1. 基于deepseek-reasoner无法输出稳定结果,咨询了deepseek-deepthink所得建议
2. 添加了主持人风格
"""
field_id_deepseek = Field(..., ge=1, description="从1开始递增的分段编号")
field_trading_window = Field(
    ...,
    description=(
        "交易窗口判断规则（严格按优先级）：\n"
        "1. 明确时间词：'明天/下周/这几天'→short_term，'本月/本季/年底/几个月'→medium_term，'今年/长期/未来几年'→long_term\n"
        "2. 技术分析提及'关键价位突破'：通常为medium_term\n"
        "3. 无时间信息但有多维度分析：默认为medium_term（主持人布局周期）\n"
        "4. 事件驱动：'财报/选举/会议'→event_window\n"
        "5. 仅现象描述或无分析：unknown\n"
        "注意：已发生的具体历史时间点（如'昨晚10点半'）不能作为未来交易窗口依据"
    )
)


field_intent_deepseek = Field(
    ...,
    description=(
        "**注意：以下判断规则必须严格遵守**\n\n"
        "基于布局型主持人风格判断（严格决策树）：\n"
        "Step1: 检查是否为举例说明\n"
        "  - 关键词检测：'比如说'、'就像'、'连...都...'、'你看'、'举个例子'\n"
        "  - 上下文检测：是否用于说明其他概念而非分析该标的\n"
        "  → 是，则必须设为unclear\n\n"
        "Step2: 统计分析维度（必须≥2个同向维度）\n"
        "  - 有效维度：技术面、基本面、资金面、宏观面、情绪面、事件面\n"
        "  - 仅价格描述（如'暴涨'、'暴跌'）不算分析维度\n"
        "  - ≥2个同向维度 → implicit\n"
        "  - 1个维度或矛盾维度 → unclear\n\n"
        "Step3: 检查可执行参考点（必须面向未来）\n"
        "  - 有效：具体价位、具体条件、具体时间框架\n"
        "  - 无效：已发生的具体历史时间点\n\n"
        "Step4: 检查否定表述\n"
        "  - 明确'不建议'、'不是叫你去玩' → unclear\n"
        "  - 讽刺性表述（表面看涨实则看空）→ 识别真实意图\n\n"
        "explicit: 明确使用'买/卖/做多/做空'等动词且无否定\n"
        "implicit: 无交易动词但满足上述Step1-4所有条件\n"
        "unclear: 不符合上述任何条件"
    )
)



field_instrument_type_deepseek = Field(
    ...,
    description=(
        "instrument的范围:\n"
        "stock: 个股/公司名/股票简称（如'台积电''英伟达''苹果'）。\n"
        "fx: 外汇货币对与汇率写法（如'美元/日元''USDJPY''人民币汇率'）。\n"
        "commodity: 大宗商品与其基准（如'黄金''原油''WTI''布伦特'）。\n"
        "crypto: 加密资产（如'比特币/BTC''以太坊/ETH'）。\n"
        "index: 指数与指数简称（如'标普500''纳指''道指''沪深300''美元指数'）。\n"
        "etf: ETF/基金名称（如'SPY''QQQ''某某ETF'）。\n"
        "bond: 债券/国债（如'美债''国债''公司债'）。\n"
    )
)

field_instrument_from_helper_deepseek = Field(
    ...,
    min_length=1,
    description=("来自helper.instruments.instrument，精确拷贝")
)

field_instrument_normalized_from_helper_deepseek = Field(
    ...,
    description=("来自helper.instruments.instrument_normalized，直接沿用")
)


class EvidenceSpan_deepseek4(BaseModel):
    evidence_id: int = field_id_deepseek
    evidence_intent: str = Field(
        ...,
        min_length=1,
        description=(
            "**注意：必须严格按照以下格式，否则验证失败**\n\n"
            "结构化证据摘要（必须按以下格式）：\n"
            "格式：'原文：\"...\"；分析维度：【技术面/基本面/资金面/宏观面/情绪面/事件面】；"
            "方向：【偏多/偏空/中性】；主持人意图：【分析/举例/警示/推荐】；"
            "举例检测：【是/否，如是为辅助说明什么概念】'\n\n"
            "示例：'原文：\"黄金白银为什么喷出，到为什么急速的修正拉回，甚至要泡沫破灭\"；"
            "分析维度：【技术面】；方向：【偏空】；主持人意图：【分析】；举例检测：【否】'"
        )
    )
    evidence_trading_window: str = Field(
        ...,
        min_length=1,
        description=(
            "**注意：必须严格按照以下格式，否则验证失败**\n\n"
            "结构化时间窗口摘要（必须按以下格式）：\n"
            "格式：'时间依据：\"...\"；判断：short_term/medium_term/long_term/event_window/unknown；理由：...'\n\n"
            "示例：'时间依据：\"年底可能有一波变化\"；判断：medium_term；理由：主持人提及年底变化窗口'"
        )
    )


class Intent(str, Enum):
    OPEN_BUY_IMPLICIT = "open_buy_implicit"
    OPEN_BUY_EXPLICIT = "open_buy_explicit"
    OPEN_SELL_IMPLICIT = "open_sell_implicit"
    OPEN_SELL_EXPLICIT = "open_sell_explicit"
    CLOSE_BUY = "close_buy"
    CLOSE_SELL = "close_sell"
    UNCLEAR = "unclear"


class TradingWindow(str, Enum):
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"
    EVENT_WINDOW = "event_window"
    UNKNOWN = "unknown"


class AssetClass(str, Enum):
    STOCK = "stock"
    FX = "fx"
    COMMODITY = "commodity"
    CRYPTO = "crypto"
    INDEX = "index"
    ETF = "etf"
    BOND = "bond"

class TradingSignalBase_deepseek4(BaseModel):
    signal_id: int = field_id_deepseek
    instrument: str = field_instrument_from_helper_deepseek
    instrument_normalized: str = field_instrument_normalized_from_helper_deepseek
    intent: Intent = field_intent_deepseek
    trading_window: TradingWindow = field_trading_window
    evidence_ids: List[int] = Field(default_factory=list, description="evidence_id列表")
    instrument_type: AssetClass = field_instrument_type_deepseek

class TRADING_SIGNAL(BaseModel):
    evidence: List[EvidenceSpan_deepseek4] = Field(default_factory=list)
    signals: List[TradingSignalBase_deepseek4] = Field(default_factory=list)


SCHEMA = r"""
SCHEMA_VERSION=2026-02-01T10:00:00
你是一个中文(普通话)经验丰富的财经分析师，专门分析《金钱报》主持人(杨世光) 的交易信号。

输入:
- Transcript：完整逐字稿
- Helper：instruments JSON（已抽取好的 instrument 列表，包含 instrument_id / instrument / instrument_normalized / instrument_type）

目标:
基于 Transcript，对 Helper 中列出的每一个 instrument 逐一判断其交易意图（intent）并输出交易信号。
必须覆盖 Helper 的所有 instrument：每个 instrument 都要输出一条 signal（至少 intent=unclear）。

**关键提示（必须遵守）：**
1. **主持人风格**：杨世光主持人是"布局型"风格，不是"观察型"。提及标的通常带有交易意图，不是单纯描述现象。
2. **举例检测**：如果标的仅用于举例说明其他概念（关键词："比如说"、"就像"、"连...都..."、"你看"），则 intent 必须为 unclear。
3. **分析维度**：只有至少2个同向分析维度（技术面、基本面、资金面、宏观面、情绪面、事件面）才能形成 implicit 信号。
4. **时间窗口**：已发生的具体历史时间点（如"昨晚10点半"）不能作为未来交易窗口依据。
5. **讽刺语气**：注意识别讽刺性表述（表面看涨实则看空）的真实意图。

核心约束（必须遵守）：
1) 覆盖性：signals 中必须包含 Helper 的全部 instrument_id；不允许遗漏。
2) 不新增标的：不得在 signals 中输出 Helper 之外的任何 instrument；不得自行补充未出现于 Helper 的标的。
3) 以 Transcript 为准：所有 intent 判断只能来自 Transcript 明确表达的内容；不得引入 Transcript 之外的新信息或常识推断。
4) 先 evidence 后 signals：必须先生成 evidence 列表，再生成 signals 列表；signals 引用的 evidence_id 必须在 evidence 中真实存在。
5) 去重合并：同一 instrument_id 只输出一条 signal；如 Transcript 多处提及，合并证据到同一条 signal 中。
6) Helper 优先：instrument 的写法必须与 Helper 的 instrument 字段一致（精确拷贝），用于可追溯；instrument_normalized / instrument_type 也以 Helper 为准（直接沿用）。
"""