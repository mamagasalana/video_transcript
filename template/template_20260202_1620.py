from __future__ import annotations
from pydantic import BaseModel, Field
from enum import Enum
from typing import Dict, List, Optional, Literal, Annotated

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
   - 【剔除到期/交割日期，但保留期限】若原文标的包含任何“到期/交割”等日历日期信息（年月日/具体时间等）或期货合约的月份/年份/代码（例如“黄金2406”“CLZ4”“WTI 2024年12月合约”“美债10年期 2024年12月到期”），instrument_normalized 必须剔除这些“到期/交割日期”信息，只保留“标的本体/基准标的”。
     - 例：instrument="黄金2406" → instrument_normalized="Gold"；instrument="WTI 2024年12月合约" → instrument_normalized="WTI Crude Oil"。
     - 【期限保留规则】若原文包含“期限/久期/年期/tenor”（如“2年期/10年期/30年期/10Y/10yr”），该期限信息属于“标的本体”，必须保留；需要剔除的是“到期/交割日期”。例如 instrument="美债10年期 2024年12月到期" 时，instrument_normalized 应为 "US 10Y Treasury"（而不是 "US Treasury"）。
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
        "【剔除到期/交割日期，但保留期限】若 instrument 原文包含任何“到期/交割”等日历日期信息（年月日/具体时间等）或期货合约的月份/年份/代码（如“黄金2406”“CLZ4”“WTI 2024年12月合约”“美债10年期 2024年12月到期”），"
        "instrument_normalized 必须剔除这些“到期/交割日期”信息，只保留“标的本体/基准标的”（如“Gold”“WTI Crude Oil”）。"
        "【期限保留规则】若原文包含“期限/久期/年期/tenor”（如“2年期/10年期/30年期/10Y/10yr”），该期限信息属于“标的本体”，必须保留；需要剔除的是“到期/交割日期”。例如 instrument='美债10年期 2024年12月到期' 时，instrument_normalized 应为 'US 10Y Treasury'（而不是 'US Treasury'）。"
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



UnderlyingAsset = Literal[
  # ----------------
  # EQUITY (index-like exposures; country ignored)
  # ----------------
  'equity_benchmark' ,
  'equity_vix' ,

  # equity_factor{Factor}'
  'equity_factorValue' ,
  'equity_factorMomentum' ,
  'equity_factorQuality' ,
  'equity_factorLowVolatility' ,
  'equity_factorDividend' ,
  'equity_factorSize' ,
  'equity_factorGrowth' ,

  # equity_cap{Bucket}'
  'equity_caplarge' ,
  'equity_capmid' ,
  'equity_capsmall' ,

  # equity_sector{GICS 11}'
  'equity_sectorCommunicationServices' ,
  'equity_sectorConsumerDiscretionary' ,
  'equity_sectorConsumerStaples' ,
  'equity_sectorEnergy' ,
  'equity_sectorFinancials' ,
  'equity_sectorHealthCare' ,
  'equity_sectorIndustrials' ,
  'equity_sectorInformationTechnology' ,
  'equity_sectorMaterials' ,
  'equity_sectorRealEstate' ,
  'equity_sectorUtilities' ,

  'equity_stock',
  # ----------------'
  # FX (single-currency groups; baskets map to main currency, e.g. DXY -> fx_usd)'
  # Starter set (expand freely)'
  # ----------------'
  'fx_usd',
  'fx_eur',
  'fx_jpy',
  'fx_gbp',
  'fx_chf',
  'fx_cad',
  'fx_aud',
  'fx_nzd',
  'fx_cny',
  'fx_hkd',
  'fx_sgd',
  'fx_myr',
  'fx_inr',
  'fx_krw',
  'fx_thb',
  'fx_twd',
  'fx_try',
  'fx_idr',
  'fx_pln',
  'fx_sek',
  'fx_dkk',
  'fx_nok',
  'fx_zar',
  'fx_brl',
  'fx_rub',
  'fx_mxn',
  'fx_php',
  'fx_vnd',
  'fx_egp',
  'fx_ils',
  'fx_sar',
  'fx_czk',
  'fx_ars',
  'fx_clp',
  'fx_cop',
  'fx_ron',
  'fx_huf',
  'fx_other',


  # ----------------'
  # COMMODITY (buckets; ignore spot/future/expiry; brent+wti -> cmd_oil)'
  # Starter set (expand freely)'
  # ----------------'
  'cmd_oil',
  'cmd_natgas',
  'cmd_gold',
  'cmd_silver',
  'cmd_copper',
  'cmd_aluminum',
  'cmd_ironore',
  'cmd_coal',
  'cmd_corn',
  'cmd_wheat',
  'cmd_soybean',
  'cmd_other',


  # ----------------'
  # GOV (treasury by term buckets; country handled in `country`)'
  # Starter set (expand freely)'
  # ----------------'
  'gov_1M', 
  'gov_3M', 
  'gov_6M', 
  'gov_1Y', 
  'gov_2Y', 
  'gov_3Y', 
  'gov_5Y', 
  'gov_7Y', 
  'gov_10Y', 
  'gov_20Y', 
  'gov_30Y', 
  'gov_other',
  'gov_tips5Y',
  'gov_tips10Y',
  'gov_tips30Y',
  'gov_tipsother',

  # ----------------
  # CREDIT (non-sovereign / spread products; country handled in `country`)
  # Starter set (expand freely)
  # ----------------
  'credit_ig',
  'credit_hy',
  'credit_em',
  'credit_cds',
  'credit_mbs',
  'credit_abs',
  'credit_cp',
  'credit_other',

  # ----------------
  # CRYPTO (major coins/stables; country ALWAYS GLOBAL)
  # Starter set (expand freely)
  # ----------------
  'crypto_btc',
  'crypto_eth',
  'crypto_usdt',
  'crypto_other',

  # ----------------
  # RATES (non-government rate products; country handled in `country`)
  # Starter set (expand freely)
  # ----------------
  'rates_inflationswap',
  'rates_other',
  'unclassified', 
  ]

class InstrumentTagBase(BaseModel):
    raw: str = Field(..., min_length=1, description="输入原文（ask 列表中的字符串），用于可追溯。")

    underlying_assets: List[UnderlyingAsset] = Field(
        ...,
        min_length=1, 
        description=(
            "分组标签列表（Group Tags），用于把原文标的映射到你预定义的暴露组。"
            "每个标签都采用固定字符串形式：{asset_class}_{description}"
            "允许一个 raw 命中多个标签（如多因子/多行业/利率曲线价差等），但列表内不得重复。"
            "注意：这里的标签不是自然语言名称，也不是合约类型（忽略 spot/future/expiry 等外壳），"
            "而是你用于确定性分组与统计的“暴露类别 ID”。"
        ),
    )

    country: str = Field(
        ...,
        description="国家/地区代码 (ISO3) 或GLOBAL。",
    )

    ticker: str = Field(
        ...,
        description="股票代码（仅当underlying_assets为equity_stock时填写）。",
    )

class InstrumentTag(BaseModel):
    instruments: List[InstrumentTagBase] = Field(default_factory=list)


SCHEMA_INSTRUMENT_TAG_CLASSIFICATION = r"""
SCHEMA_VERSION=2026-03-01T02:00:00
You are a strict classification system. Your job is to map each input instrument string into one or more predefined exposure tags.

INPUT:
- The user provides a LIST of strings (it may look like JSON: ["...","..."] or like a Python list).
- Treat EACH element as one item to classify.
- Do NOT deduplicate.
- Preserve order.

OUTPUT (STRICT):
- Output ONLY valid JSON. No markdown. No commentary.
- The output MUST validate against the provided Pydantic/JSON Schema (the caller enforces it).
- Populate `InstrumentTag.instruments` with EXACTLY N items where N == number of input strings.

FOR EACH item (InstrumentTagBase):
1) raw
   - Must equal the original input string EXACTLY (no rewriting, no trimming, no normalization).
2) underlying_assets
   - Must be a NON-EMPTY list of allowed tags (UnderlyingAsset).
   - No duplicates in the list.
   - If unsure, output exactly ["unclassified"] (and NOTHING ELSE). Never mix "unclassified" with other tags.
3) country
   - For COMMODITY, FX, and CRYPTO exposures: ALWAYS "GLOBAL".
     - If any `cmd_*` tag is present in underlying_assets -> country="GLOBAL".
     - If any `fx_*` tag is present in underlying_assets -> country="GLOBAL".
     - If any `crypto_*` tag is present in underlying_assets -> country="GLOBAL".
   - Otherwise (non-FX, non-commodity): return an ISO3 country code if you can infer it from the raw string; else "GLOBAL".
     - When GOV/RATES is present (any `gov_*` tag):
       - If the raw string clearly indicates the sovereign/issuer, map to ISO3, else "GLOBAL".
     - When CREDIT is present (any `credit_*` tag):
       - If the raw string clearly indicates a country/region issuer (e.g., "US High Yield Bonds", "China HY bonds"), map to ISO3; else "GLOBAL".
     - When EQUITY index / benchmark / sector / factor exposure (not single-stock) is present:
       - If it clearly refers to a single-country index/market, map to ISO3; if global/regional, use "GLOBAL".
     - When `equity_stock` is present:
       - You SHOULD infer the country from common financial knowledge (issuer domicile / primary listing) even if the raw string is just a company name.
       - If the raw includes an exchange/ticker suffix (e.g., ".HK", ".TW", ".T", ".SS", ".SZ"), use that to infer country.
       - Only use "GLOBAL" if the company is genuinely ambiguous or you cannot make a reasonable best-effort inference.
4) ticker
   - If `equity_stock` is NOT present in underlying_assets: MUST be "" (empty string).
   - If `equity_stock` IS present:
     - If an explicit ticker is present in raw (e.g., "AAPL", "0700.HK", "600519.SS"), copy it.
     - Otherwise, you SHOULD infer the most representative ticker from common financial knowledge.
       - Prefer the primary / most-liquid listing ticker (not an ADR) unless the raw explicitly indicates the ADR or US listing.
       - If multiple tickers are plausible, choose the most common primary listing used in news/quotes; do not output multiple tickers.
       - If you truly cannot infer a ticker, output "".

CLASSIFICATION RULES (DECISION TREE):
- FX:
  - Currency names/codes/synonyms -> fx_* (e.g., "USD", "US Dollar", "US Dollar (USD)", "USD (US Dollar)" -> fx_usd).
  - US Dollar Index / DXY -> fx_usd.
  - Currency pair like "USD/JPY" or "USDJPY" -> include BOTH fx_usd and fx_jpy.
  - IMPORTANT: only map to a specific fx_* tag if the currency is unambiguous (exact code like "THB" or a clear name like "Thai Baht").
    - If the raw is a short all-caps token that is NOT a known currency code, do NOT guess; prefer equity_stock (ticker) or unclassified.
  - Unknown / ambiguous currency -> fx_other.
- COMMODITY:
  - Gold/Silver/Oil/Natural gas/etc -> corresponding cmd_* tag; otherwise cmd_other.
  - Ignore spot/future/expiry wrappers.
- GOV / RATES:
  - If tenor is mentioned, map to gov_1M/3M/6M/1Y/2Y/3Y/5Y/7Y/10Y/20Y/30Y.
  - If it is gov/rates but tenor is unclear -> gov_other.
  - TIPS / inflation-protected Treasuries:
    - If tenor is mentioned, map to gov_tips5Y/10Y/30Y.
    - If TIPS is mentioned but tenor is unclear -> gov_tipsother.
- RATES (non-government):
  - Inflation swap / breakeven style strings (e.g., "USD 5Y5Y Inflation Swap", "EUR 5Y5Y Inflation Swap") -> rates_inflation_swap.
  - Other rate derivatives/benchmarks (if clearly tradable but not a sovereign bond) -> rates_other.
- CREDIT / SPREAD:
  - "Investment grade" / "IG" -> credit_ig.
  - "High yield" / "HY" -> credit_hy.
  - "Emerging markets" / "EM" credit -> credit_em.
  - CDS indices like "CDX" / "iTraxx" -> credit_cds.
  - MBS / CMBS -> credit_mbs.
  - ABS -> credit_abs.
  - Commercial paper -> credit_cp.
  - Otherwise any corporate bond / bond basket / bond index that is NOT clearly sovereign -> credit_other.
- EQUITY:
  - Broad equity market / index beta exposure -> equity_benchmark.
  - VIX / volatility index exposure (e.g., "VIX", "CBOE VIX") -> equity_vix.
  - Factor/style keywords -> equity_factorValue/Momentum/Quality/LowVolatility/Dividend/Size/Growth.
  - Cap bucket keywords -> equity_caplarge/mid/small.
  - Clear GICS 11 sector -> corresponding equity_sector*.
  - Single company name or explicit ticker -> equity_stock.
- CRYPTO:
  - "Bitcoin" / "BTC" -> crypto_btc.
  - "Ethereum" / "ETH" -> crypto_eth.
  - "USDT" / "Tether" -> crypto_usdt.
  - Generic "cryptocurrency/crypto" or other coins -> crypto_other.

"""
