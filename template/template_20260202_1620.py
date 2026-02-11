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


field_instrument_from_helper_deepseek = Field( ..., description=("来自helper.instruments.instrument，直接沿用") )
field_instrument_normalized_from_helper_deepseek = Field( ..., description=("来自helper.instruments.instrument_normalized，直接沿用"))
field_instrument_type_from_helper_deepseek = Field( ..., description=("来自helper.instruments.instrument_type，直接沿用"))

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
    BOND = "bond"
    INVALID = "invalid"

class TradingSignalBase_deepseek4(BaseModel):
    signal_id: int = field_id_deepseek
    instrument: str = field_instrument_from_helper_deepseek
    instrument_normalized: str = field_instrument_normalized_from_helper_deepseek
    intent: Intent = field_intent_deepseek
    trading_window: TradingWindow = field_trading_window
    evidence_ids: List[int] = Field(default_factory=list, description="evidence_id列表")
    instrument_type: AssetClass = field_instrument_type_from_helper_deepseek

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


SCHEMA_INSTRUMENT_RULES_EXTRACT = r"""
SCHEMA_VERSION=2026-02-06T00:00:00
你是一个会中文（普通话）且经验丰富的财经分析师。

目标:
从 Transcript 中抽取所有「可交易的金融标的」名称。金融交易标的是指可以在金融市场上直接买卖的具体金融工具。

=== 核心判断规则 ===

一、抽取条件（满足以下任一）：
1. 具体公司实体：对应已上市公司股票
2. 具体金融产品：对应交易所交易的具体产品（包括商品、货币、债券等）
3. 具体指数：对应可交易或广泛引用的金融指数
4. 行业/因子类：有对应广泛可交易指数产品的行业或投资因子术语

二、排除条件（满足以下任一）：
1. 宽泛资产类别术语（如"股票"类泛指）
2. 不可交易的物理实体或非金融资产
3. 未上市或已退市实体
4. 无对应可交易指数产品的行业/因子术语

=== 执行规则 ===
1. 完全匹配原文子串，保持原格式
2. 去重
3. 拆分相邻标的为独立标的
4. 纠正明显拼写错误
5. 仅在金融上下文中抽取行业/因子术语

注：所有判断基于金融常识和市场惯例。
"""

SCHEMA_INSTRUMENT_RULES_EXTRACT2 = r"""
SCHEMA_VERSION=2026-02-08T00:00:00
你是一个会中文（普通话）且经验丰富的财经分析师。

目标：从 Transcript 中抽取所有「可交易的金融标的」名称。

核心定义：
可交易的金融标的 = 可在金融市场直接买卖的具体金融工具。

具体包括：
- 具体公司股票（上市公司）
- 具体商品（黄金、石油等）
- 具体货币（美元、欧元等）  
- 具体债券（美国10年期公债等）
- 具体指数（标普500等）
- 行业/因子类：有对应MSCI或其他主流指数提供商发布的广泛可交易指数产品的术语

判断流程：
1. 排除不可交易实体：未上市/已退市、物理实体、纯地理名称、投资概念术语
2. 排除宽泛资产类别："股票"、"债券"、"ETF"等泛指术语
3. 行业/因子判断：有MSCI等广泛可交易指数产品对应则抽，否则不抽
4. 输出完全匹配原文的子串

执行规则：
1. 完全匹配，保持原格式
2. 去重
3. 相邻标的拆分
"""

SCHEMA_INSTRUMENT_RULES_EXTRACT_STOCK_ONLY = r"""
SCHEMA_VERSION=2026-02-10T00:00:00
你是一个会中文（普通话）且经验丰富的财经分析师。

目标：
从 Transcript 中**只**抽取「股票（个股）」名称（具体上市公司股票/ADR/H股/A股/台股等）。
不抽取任何非股票标的（指数、ETF、基金、期货、期权、外汇、商品、债券、加密货币等）。

核心定义：
“股票（个股）”= 语境中明确指向某家上市公司的**可交易股票**（而不是公司/机构本身、报告来源、或泛指概念）。

=== 强制排除（宁可错杀）===
1) 非个股：
   - 指数/大盘：如“标普500/纳指/恒生指数/上证指数”等
   - ETF/基金：如“ETF/指数基金/某某基金/某某ETF”等
   - 期货/期权/合约、外汇、商品、债券、加密货币
2) 宽泛板块/概念/群体（不算具体个股）：
   - 如“科技股/金融股/AI概念股/内需股/周期股/成长股”等
3) 非金融语境的同形词：
   - 如“苹果(水果)/特斯拉(人物或其它)/小米(食物)”等；若语境不明确指向股票则排除
4) **“机构/研报/报告来源”语境下的机构名（避免误抽）**：
   - 当某名称在句子里扮演“发布报告/研报/指出/认为/预测/上调下调评级/给出目标价/策略会/电话会/路演”等
     **信息来源或研究机构**角色时，不要把该机构名当成股票抽取。
   - 典型触发词： “报告/研报/券商/投行/分析师/策略/观点/表示/指出/认为/预计/预测/上调/下调/评级/目标价”
   - 例： “摩根士丹利报告指出……” → **不要**抽取“摩根士丹利”（除非明确在谈“摩根士丹利股价/股票/MS这支股票”等）
   - 注意：同一句里如果还提到其他公司的股票（如“上调苹果目标价”），**可以**抽取“苹果”，但仍然**不要**抽取“摩根士丹利”

=== 股票语境确认（满足任一即可抽取该名称为股票）===
1) 明确股票词汇邻近或指代：
   - “股/股票/股价/该股/股份/上市/挂牌/市值/本益比(PE)/EPS/财报/营收/配息/股利/回购/增发”
2) 明确交易/持仓动作：
   - “买/卖/做多/做空/加码/减码/建仓/出清/止损/目标价位/进场/离场”
3) 明确市场标签或代码：
   - “美股/港股/A股/台股/ADR/NYSE/Nasdaq/港交所/上交所/深交所/台交所”
   - 或出现股票代码样式（如“TSLA/2330/600519/0700”等）

=== 执行规则（输出格式与质量）===
1) 输出必须为 Transcript 中的**连续子串**，保持原格式；不得改写/翻译/补全；不得包含前后空格
2) 去重：同一股票名称多次出现只输出一次
3) 相邻多个股票名称要拆分为独立条目
4) 纠正明显错别字/谐音导致的股票名笔误（仅限非常明显且不改变指代）
5) 如果无法确定某名称是否在谈“股票”，一律不抽取
"""

SCHEMA_INSTRUMENT_RULES_EXTRACT_COMMODITY_ONLY = r"""
SCHEMA_VERSION=2026-02-10T00:00:00
你是一个会中文（普通话）且经验丰富的财经分析师。

目标：
从 Transcript 中**只**抽取「商品（大宗商品）」标的名称。
不抽取任何非商品标的（个股/指数/ETF/基金/期货期权以外的金融名词/外汇/债券/加密货币等）。

核心定义：
“商品（commodity）”= 在主流交易所/场外市场中被广泛交易的**标准化大宗商品**本体或其常见交易基准（如 WTI/布伦特、COMEX黄金等）。

=== 允许抽取的典型类别（举例，不限于）===
1) 贵金属：黄金、白银、铂金、钯金（及“COMEX黄金/伦敦金/现货黄金”等）
2) 能源：原油、WTI、布伦特、天然气（及“纽约原油/布油/美油”等常见基准写法）
3) 工业金属：铜、铝、镍、锌、铅、锡（及“LME铜”等）
4) 农产品：大豆、豆粕、豆油、玉米、小麦、棉花、糖、咖啡、可可等
5) 其他常见大宗：铁矿石等（仅当语境明确指向可交易商品本体/基准）

=== 强制排除（宁可错杀）===
1) 非商品资产类别/泛指：
   - “大宗商品/商品/原材料/金属/能源/农产品”等**泛称**，不够具体 → 不抽
2) 股票与公司/产业链名词（避免把产业链当商品）：
   - “黄金股/石油股/煤炭股/钢铁股/矿业股”等是板块或股票 → 不抽
   - 公司名/机构名（如“中石油/台积电/特斯拉”等）不是商品 → 不抽
3) 地名/产地/事件本身：
   - “中东/俄乌/欧佩克/沙特/伊朗/红海”等不是商品 → 不抽
4) 合约泛称但无标的：
   - “期货/合约/期权/多单/空单”等若未指向具体商品名 → 不抽

=== 商品语境确认（满足任一即可抽取该名称为商品）===
1) 明确交易/标的语境：
   - “做多/做空/买/卖/布局/建仓/加码/减码/止损/目标价位”
2) 明确市场/合约语境（可帮助确认，但仍需出现商品名）：
   - “期货/现货/升贴水/库存/交割/主力合约/近月远月/contango/backwardation”
   - 交易所/基准提示：COMEX、NYMEX、ICE、LME、CBOT 等（仅作为确认线索）
3) 语言形式明确指向商品本体：
   - 直接出现商品名称（如“黄金/原油/铜/大豆”等）或常见基准简称（如“WTI/布伦特”）

=== 执行规则（输出格式与质量）===
1) 输出必须为 Transcript 中的**连续子串**，保持原格式；不得改写/翻译/补全；不得包含前后空格
2) 去重：同一商品名称多次出现只输出一次
3) 相邻多个商品名称要拆分为独立条目
4) 纠正明显错别字/谐音导致的商品名笔误（仅限非常明显且不改变指代）
5) 如果无法确定某名称是否为“具体可交易商品标的”，一律不抽取
"""

SCHEMA_INSTRUMENT_RULES_EXTRACT_INDEX_ONLY = r"""
SCHEMA_VERSION=2026-02-10T00:00:00
你是一个会中文（普通话）且经验丰富的财经分析师。

目标：
从 Transcript 中**只**抽取「指数（index）」标的名称（宽基指数、国家/地区代表指数、行业指数、因子指数等）。
不抽取任何非指数标的（个股/公司名、ETF/基金、期货期权合约名、外汇、商品、债券、加密货币等）。

核心定义：
“指数（index）”= 市场广泛引用、通常有可跟踪交易产品/衍生品的**标准化指数名称**。

=== 强制排除（宁可错杀）===
1) ETF/基金不是指数：
   - 如原文只出现“SPY/QQQ/某某ETF/指数基金”等 ETF/基金名称而未出现指数名称 → 不抽取指数
2) 个股/公司名/机构名不是指数：
   - 如“摩根士丹利/高盛/苹果/台积电”等默认不抽
3) 板块/概念泛称不是指数：
   - “科技股/金融股/AI概念/内需/景气循环”等若无法落到具体指数名 → 不抽
4) 泛指“指数/大盘/市场/股市”但无法定位具体指数 → 不抽

=== 允许抽取的指数类型 ===
1) 宽基/大盘指数：如“标普500/纳斯达克100/道琼斯/恒生指数/沪深300/上证50/日经225/DAX”等
2) 行业指数：在行业配置/行业前景语境下，可对应“MSCI 行业指数”（规则A）
3) 因子指数：在因子投资/风格因子语境下，可对应“MSCI 因子指数”（规则B）
4) 国家/地区代表指数：在谈某国/地区股市整体时，可落到代表性指数（规则C）

=== 关键允许推断规则（将“展望/观点”落到可交易指数）===
注意：只有在 Transcript 明确表达“在谈市场整体/指数/配置某地区或某风格”时，才允许使用以下推断；
且推断输出必须是**明确指数名**（优先 MSCI 行业/因子指数，或常见国家/地区代表宽基指数）。

A) 行业展望/行业配置 → MSCI 行业指数（允许）
触发条件（满足任一）：
- 出现“行业前景/行业展望/行业配置/看好某行业/行业轮动”等，并且讨论对象是**行业**而非具体公司
输出要求：
- 输出“MSCI+行业+指数”或“MSCI 行业指数（行业=…）”
- 行业必须明确（如“金融/科技/半导体/能源/医疗保健/消费”等），否则不抽
说明例：
- “我看好半导体行业未来两季” → 可抽取 “MSCI 半导体指数”（或“MSCI 行业指数（半导体）”）

B) 因子投资/风格因子 → MSCI 因子指数（允许）
触发条件（满足任一）：
- 明确提到“因子投资/风格/Smart Beta/价值/成长/动量/质量/低波/高股息/小盘”等，并且语境为配置/偏好/轮动
输出要求：
- 输出“MSCI+因子+指数”或“MSCI 因子指数（因子=…）”
- 因子必须清晰（价值/成长/动量/质量/低波/高股息/小盘等），否则不抽

C) 国家/地区股市整体观点 → 该国/地区代表性指数（允许）
触发条件：
- 出现“某国家/地区股市整体/大盘/整体看法/整体配置”，但未给出具体指数名
输出要求：
- 输出该国家/地区最具代表性、最常被引用的宽基指数名
- 仅当国家/地区明确时允许；若只说“海外/新兴/全球”且无法落点 → 不抽
说明例：
- “整体来说我看好美股大盘” → 可抽取 “标普500”
- “香港整体会转强” → 可抽取 “恒生指数”（若原文明示“恒生100/恒生科技指数”等则按原文抽取）

=== 执行规则（输出格式与质量）===
1) 输出必须为 Transcript 中的**连续子串**，保持原格式；不得改写/翻译/补全；不得包含前后空格
2) 去重：同一指数名称多次出现只输出一次
3) 相邻多个指数名称要拆分为独立条目
4) 允许做非常保守的专业归一化（仅限明显错别字/常见简称，如“恆生/恒生”、“纳指/纳斯达克”）
5) 若无法把观点可靠落到“具体指数名”，一律不抽取
"""

SCHEMA_INSTRUMENT_RULES_EXTRACT_CURRENCY_ONLY = r"""
SCHEMA_VERSION=2026-02-10T00:00:00
你是一个会中文（普通话）且经验丰富的财经分析师。

目标：
从 Transcript 中**只**抽取「货币/外汇（FX currency）」标的名称（单一货币或货币对/汇率）。
不抽取任何非货币标的（个股/指数/ETF/基金/商品/债券/加密货币等）。

核心定义：
“货币（currency）”= 市场广泛交易的**法定货币**（如美元、欧元等），以及其**货币对/汇率写法**（如 EUR/USD、美元兑日元等）。

=== 允许抽取的形式（举例，不限于）===
1) 单一货币名称/简称：
   - “美元/美金/USD”
   - “欧元/EUR”
   - “日元/JPY”
   - “英镑/GBP”
   - “人民币/CNY/CNH”
   - “港币/HKD”
   - “澳元/AUD、加元/CAD、瑞郎/CHF、新台币/TWD、韩元/KRW、新元/SGD”等
2) 货币对/汇率：
   - “EUR/USD、USDJPY、GBPUSD”等代码写法
   - “欧元兑美元/美元兑日元/人民币兑美元/美元对台币”等中文写法
   - “美日/欧美/镑美/澳美”等交易简称（仅当语境明确为外汇交易/汇率讨论）

=== 强制排除（宁可错杀）===
1) 加密货币/稳定币不是法币外汇：
   - “比特币/以太坊/USDT/USDC”等 → 不抽
2) 指数不是货币：
   - “美元指数/DXY”等属于指数 → 不抽（currency-only 一律排除）
3) 宏观/政策/区域概念不是货币标的：
   - “欧元区/美元体系/货币政策/强美元/弱美元/外汇市场/汇率制度”等概念词本身 → 不抽
4) 债券或计价属性不等于外汇标的：
   - “美元债/欧元债/美元计价资产/出口收美元”等若原文未在讨论该货币本身或其汇率交易 → 不抽
5) 仅泛称“外汇/汇率”但没有具体货币或货币对 → 不抽

=== 货币语境确认（满足任一即可抽取）===
1) 明确汇率/兑换/升值贬值语境：
   - “兑/对/兑换/汇率/升值/贬值/破7/回到…/升到…/跌到…/报价”
2) 明确外汇交易/持仓动作：
   - “做多/做空/买/卖/布局/建仓/加码/减码/止损/目标位”
3) 明确以货币对或代码形式出现：
   - “EUR/USD、USDJPY、CNY、CNH、USD”等

=== 执行规则（输出格式与质量）===
1) 输出必须为 Transcript 中的**连续子串**，保持原格式；不得改写/翻译/补全；不得包含前后空格
2) 去重：同一货币/货币对多次出现只输出一次
3) 相邻多个货币/货币对要拆分为独立条目
4) 纠正明显错别字/谐音导致的货币名笔误（仅限非常明显且不改变指代）
5) 若无法确定是否在谈“货币/汇率标的”，一律不抽取
"""

field_instrument_normalized_deepseek = Field( ...,
    description=(
        "标准化后的可交易资产标识，用于对齐与检索（优先：ticker/合约代码/交易所符号；"
        "其次：官方全称；再次：常用英文名/缩写）。"
        "当原文疑似笔误/谐音/错别字时，可给出你认为最可能的标准名称，但不得凭空引入原文之外的新标的。"
        "本字段不得为空：若无法可靠标准化，则 instrument_normalized 必须等于原文 instrument（原样拷贝）。"
        "目标：输出最具代表性的、可交易的标准化资产。"
    ))


# to standardize signal instrument for future comparison purpose
class TradingInstrumentBase(BaseModel):
    instrument_id: int = field_id_deepseek
    instrument: str = Field(..., min_length=1,
        description="必须来自 Transcript 的连续子串（精确抄写），不得改写/翻译/补全；不得包含前后空格；只包含标的名称本身，必要时可从更长黏连片段中裁剪出标的名称（仍需连续子串）。",
    )
    instrument_normalized: str = field_instrument_normalized_deepseek

class TradingInstrument(BaseModel):
    instruments: List[TradingInstrumentBase] = Field(default_factory=list)


SCHEMA_INSTRUMENT_RULES_VALIDATE = r"""
SCHEMA_VERSION=2026-02-03T13:01:00
你是一个会中文(普通话)而且经验丰富的财经分析师。

输入:
- Transcript：内涵instruments

目标:
对已抽取的 instruments 逐条进行验证，判断其是否符合可交易资产标准。

【强制验证与决策流程】
在决定输出一个资产前，你必须进行以下逻辑验证：
市场联想测试： 提到这个工具时，你是否能立刻想到一个具体的交易所名称或一个具体的交易产品代码？如果不能，它很可能不可交易。
类别否决检查： 对照各类别的否决条款，检查该工具是否属于被明确排除的类型。
最终判断： 只有通过以上测试的工具才符合输出条件。如果存疑，优先排除。

验证标准与范围（必须严格遵循，宁可错杀不要漏放）：
1) 具有明确、公开、中心化的交易市场（如交易所、受监管的交易平台）。
2) 有足够流动性（非极冷门品种）。
3) 标准化程度高（期货、主要股票、主流债券等）。
4) 核心修订原则：当识别一个工具时，你必须能联想到其至少一个具体的、活跃的交易市场或标准化产品。否则，判为不合格。

分类标准与否决条款（严格执行）：
【stock】个股/公司名/股票简称。必须是在主要证券交易所上市的公司股票。私有企业、仅场外交易的股票不予录取。
【fx】外汇货币/汇率。非公开可交易的内部报价或非标准写法不予录取。
【commodity】仅限传统大宗商品；非传统大宗商品不予录取。
【crypto】仅限主流加密货币；非主流加密货币不予录取。
【index】金融市场指数。必须拥有场内衍生品的指数。若仅为泛指市场概念，且无法对应到主流基准指数，则不予录取。
【bond】债券。必须为公开交易、具有高信用评级和流动性的债券；私募债、非标资产、流动性极差的债券不予录取。

验证要求:
1) 覆盖性：所有在 instruments.instrument 中出现过的，都必须被覆盖；如因智能去重合并为同一 instrument_normalized，则需通过 instrument_id_reference 显式包含被合并的 instrument_id。
2) 可追溯：instrument 必须来自 instruments.instrument 的原文写法（精确抄写，不要改写/翻译/补全）。
3) 专业修正：instrument_normalized 字段必须对明显的笔误/谐音/错别字进行专业修正。
4) 智能去重：同一 instrument_normalized 在 Transcript 多次出现时，只输出一次（合并为同一个条目）。
"""




class TradingInstrumentValidatedBase(BaseModel):
    instrument_id: int = field_id_deepseek
    instrument: str =  Field(..., min_length=1, 
        description=(
        "该资产于transcript的原文。"))
    instrument_normalized: str = field_instrument_normalized_deepseek
    appearance_count: int = Field( ..., ge=1,description="应为同一 instrument_normalized 的 appearance_count 之和。",)
    instrument_id_reference: List[int] = Field(
        default_factory=list,
        description="该条目合并/覆盖的 instrument_id 列表；用于满足覆盖性要求，需包含被合并的全部 instrument_id。",
    )
    instrument_type: AssetClass = Field(
        ...,
        description=(
            "当 is_valid=false 时，instrument_type 必须为 invalid；"
            "当 is_valid=true 时，必须为有效资产类别之一（stock/fx/commodity/crypto/index/bond）。"
        ),
    )
    is_valid: bool
    reasons: List[str] = Field(
        default_factory=list,
        description="失败原因列表（若 is_valid=true，则可为空列表）。",
    )


class TradingInstrumentValidated(BaseModel):
    instruments: List[TradingInstrumentValidatedBase] = Field(default_factory=list)
