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
SCHEMA_VERSION=2026-02-13T00:00:00
你是一个会中文（普通话）且经验丰富的财经分析师。

目标：
从 Transcript 中抽取所有「可交易的金融标的」名称，既包括【显式提及】也包括【隐含提及】。

核心定义：
可交易的金融标的 = 可在金融市场上直接买卖的具体金融工具（股票/指数/外汇/商品/期货合约/具体债券/主流加密货币）。
范围声明：本任务不包含 ETF/基金类产品（即使可交易也不抽取）。

=== 字段约束（必须严格遵守）===
1) instrument（原文标的）：
   - 必须来自 Transcript 的连续子串（精确抄写），不得改写/翻译/补全。
   - 不得包含前后空格；只写标的名称本身（必要时可从更长黏连片段中裁剪出标的名称，但仍需连续子串）。
   - 目标：最大化保留 Transcript 原文表述，用于可追溯。
2) instrument_normalized（标准化标的）：
   - 用于检索/对齐：优先 ticker/交易所符号；其次官方全称；再次常用英文名/缩写。
   - 【日期信息一律剔除】若原文标的带有任何“日历日期/时间/交割月/年份/到期日/合约代码”等日期信息（例如“黄金2406”“CLZ4”“WTI 2024年12月”“美债2033年到期”），instrument_normalized 必须剔除这些日期信息，只保留“标的本体/基准标的”（如“Gold”“WTI Crude Oil”“US Treasury”）。
     - 注意：不要误删本身就是 ticker/交易所符号的一部分的数字（例如股票代码/指数代码/外汇符号中的数字或点号等）。
   - 当原文疑似笔误/谐音/错别字时，可给出最可能的标准名称，但不得凭空引入原文之外的新标的。
   - 若无法可靠标准化，则 instrument_normalized 必须等于 instrument（原样拷贝）。
   - 重要：原文只放在 instrument；标准化只放在 instrument_normalized。

=== 显式标的（明确提到具体可交易对象）===
满足以下任一则应抽取（instrument 保留原文；instrument_normalized 尽量标准化）：
1 股票：具体公司名/股票简称/代码（如“苹果”“AAPL”）。
2 指数：具体指数名称（如“标普500”“纳指”“恒生指数”等；可在 instrument_normalized 做标准化归一）。
3 外汇：具体货币或货币对（如“美元”“欧元”“美元兑日元”等）。
4 商品：具体商品名称或具体合约符号（如“黄金”“原油”“WTI”等）。
5 债券：必须地域具体化，例如“美债”。
  - 注意：单独出现“债券/国债”若无任何地域限定，一律视为泛指，不抽取。
6 加密货币：仅限主流加密货币或其常用写法/符号（如“比特币”“BTC”“以太坊”“ETH”）。
  - 非主流/山寨币/不确定的币种：不抽取。

=== 隐含标的（多为指数）===
仅当 Transcript 在明确金融语境中提及以下内容时，才将其视为隐含标的候选：
1 行业/板块/主题：如“半导体板块”“银行股”“新能源”“AI主题”“Large Cap”等。
2 因子：如“价值因子”“成长风格”“高股息”“低波动”“质量因子”等。
MSCI 代理规则（用于行业/因子“可交易代理”标准化）：
- 原则：对 行业/因子 相关的隐含标的，优先假设存在可交易的 MSCI 指数作为代理（如果你确定该 MSCI 指数确实存在/常见）。
- 若你【高置信】存在对应 MSCI 指数可作为代理：
  - instrument = Transcript 原文提法（连续子串，原样保留）
  - instrument_normalized = 对应 MSCI 英文官方指数名称（例如“MSCI USA Value Index”等；必须是英文）
- 若你【不确定】是否存在对应 MSCI 指数，或无法高置信映射：
  - 仍可抽取 instrument（原文）
  - 但 instrument_normalized 必须 = instrument（不得输出猜测的 MSCI 名称；不得凭空造指数名）

3 地区/国家暴露：如“美国股市”隐示“标普500”，“A股”隐示“上证指数”
- 注意：单独出现“股市”若无任何地域限定，一律视为泛指，不抽取。

  
=== 排除规则（必须严格执行）===
以下情况一律不抽取为 instrument：
1) 宽泛资产类别/泛称：如仅出现“股票/债券/ETF/基金/期货/外汇/商品/指数/板块”等且无任何具体限定。
2) ETF（无论是否给出代码/名称）一律不抽取：例如“SPY”“QQQ”“沪深300ETF”“510300”等也不要输出为 instrument。
3) 不可交易实体：物理实体/纯地理名称/人物机构（非可交易证券）/未上市或已退市实体。

=== 执行规则 ===
1) 完全匹配原文：instrument 必须是 Transcript 连续子串，保持原格式（不改写）。
2) 去重：同一标的多次出现只输出一次；优先按 instrument_normalized 判定同一，否则按 instrument 原文。
3) 拆分：相邻多个标的必须拆成独立条目。
4) 标准化：instrument_normalized 用于对齐与检索；不确定就原样拷贝 instrument。
"""


field_instrument_normalized_deepseek = Field( ...,
    description=(
        "标准化后的可交易资产标识，用于对齐与检索（一般优先：ticker/交易所符号；"
        "其次：官方全称；再次：常用英文名/缩写）。"
        "【日期信息一律剔除】若 instrument 原文包含任何“日历日期/时间/交割月/年份/到期日/合约代码”等日期信息（如“黄金2406”“CLZ4”“WTI 2024年12月合约”“美债2033年到期”），"
        "instrument_normalized 必须剔除这些日期信息，只保留“标的本体/基准标的”（如“Gold”“WTI Crude Oil”“US Treasury”）。"
        "注意：不要误删本身就是 ticker/交易所符号的一部分的数字（例如股票代码/指数代码/外汇符号中的数字或点号等）。"
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
