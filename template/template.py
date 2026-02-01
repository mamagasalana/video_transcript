from __future__ import annotations
from pydantic import BaseModel, Field
from enum import Enum
from typing import List, Optional, Literal, Annotated

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]

# To extract topic
class TopicChunk(BaseModel):
    chunk_id: int
    topic_label_raw: str
    start_anchor: str
    summary: str
    key_entities: List[str] = Field(default_factory=list)
    key_indicators_mentioned: List[str] = Field(default_factory=list)

class TopicChunks(BaseModel): 
    topic_chunks: List[TopicChunk]    

# To extract trading signal
class AssetClass(str, Enum):
    STOCK = "stock"
    FX = "fx"
    COMMODITY = "commodity"
    CRYPTO = "crypto"
    INDEX = "index"
    ETF = "etf"
    BOND = "bond"

class Intent(str, Enum):
    OPEN_BUY_IMPLICIT = "open_buy_implicit"     
    OPEN_BUY_EXPLICIT = "open_buy_explicit"  
    OPEN_SELL_IMPLICIT = "open_sell_implicit"   
    OPEN_SELL_EXPLICIT = "open_sell_explicit"    
    CLOSE_BUY = "close_buy"     
    CLOSE_SELL = "close_sell"   
    UNCLEAR = "unclear"

class TradingWindow(str, Enum):
    short_term   = "short_term"
    medium_term  = "medium_term"
    long_term    = "long_term"
    event_window = "event_window"
    unknown      = "unknown"

class InstrumentRef(BaseModel):
    asset_class: AssetClass
    name_raw: str = Field(..., description="Exact wording from transcript, e.g. '美股', '黄金', '比特币'.")
    name_normalized: Optional[str] = Field(
        None,
        description="Optional normalization, e.g. 'S&P 500', 'XAUUSD', 'BTC'."
    )
    symbol: Optional[str] = Field(None, description="Ticker/symbol if explicitly stated.")

# --- the trading signal itself ---
class TradingSignalBase(BaseModel):
    signal_id: int
    instrument: InstrumentRef
    intent: Intent                 # active vs passive
    confidence:  Confidence = 0.7
    evidence_ids: List[int] = Field(default_factory=list)

class EvidenceType(str, Enum):
    ANCHOR = "anchor"   # explicitly names the instrument
    DRIVER = "driver"   # explains what moves price
    STANCE = "stance"   # expresses implied/explicit trade stance
    SYNTHESIS = "synthesis"  # model-generated reasoning glue
    OTHER  = "other"    # glue/context

class EvidenceSpan(BaseModel):
    evidence_id: int = Field(..., description="Unique evidence ID, e.g. 1")
    sentence: str = Field(..., description="Exact sentence/line from transcript.")
    evidence_type: EvidenceType = Field(..., description="anchor/driver/stance/other")

class TradingSignal(BaseModel):
    evidence: List[EvidenceSpan] = Field(default_factory=list)
    signals: List[TradingSignalBase] = Field(default_factory=list)

##########################################################################
# Deepseek section
##########################################################################


field_id_deepseek = Field(..., ge=1, description="从1开始递增的分段编号")
field_instrument_deepseek =  Field(..., min_length=1, 
    description=(
        "该资产于transcript的原文。"
        "必须是明确是可交易资产。"
    ))
field_instrument_normalized_deepseek = Field( ...,
    description=(
        "标准化后的可交易资产标识，用于对齐与检索（优先：ticker/合约代码/交易所符号；"
        "其次：官方全称；再次：常用英文名/缩写）。"
        "当原文疑似笔误/谐音/错别字时，可给出你认为最可能的标准名称，但不得凭空引入原文之外的新标的。"
        "本字段不得为空：若无法可靠标准化，则 instrument_normalized 必须等于原文 instrument（原样拷贝）。"
        "目标：输出最具代表性的、可交易的标准化资产。"
    ))
field_trading_window = Field(
    ...,
    description=(
        "交易窗口：从原始文本中抽象出的“时间有效区间”枚举标签，"
        "表示该观点、判断或交易信号在何种时间尺度或事件窗口下成立；"
        "用于刻画信号的时效性，而非具体的下单时间点。\n"
        "可选枚举值及含义：\n"
        "- short_term：短期有效（通常为几天到数周）。\n"
        "- medium_term：中期有效（通常为数周到数月）。\n"
        "- long_term：长期有效（通常为半年到数年）。\n"
        "- event_window：事件窗口有效（围绕特定事件/节点的一段时间，例如财报、议息、政策落地、重要数据发布前后）。\n"
        "- unknown：无法从文本中判断交易窗口或信息不足。"
    )
)
field_intent_deepseek = Field(..., 
    description=(
    "open_buy_explicit: 明确、直接建议做多/买入/加仓。"
    "open_buy_implicit: 暗示,通过多项判断依据（观点/指标/条件/情景）共同指向偏多: 例如趋势判断、关键价位、基本面利多、资金/情绪/仓位变化、时间窗口、胜率/概率、风险回报更优等。"
    "open_sell_explicit: 明确、直接建议做空/卖出/减仓。"
    "open_sell_implicit: 暗示,通过多项判断依据（观点/指标/条件/情景）共同指向偏空: 例如趋势转弱、关键价位、基本面利空、资金/情绪/仓位变化、估值/风险溢价不利、事件风险、概率倾向下跌等。"
    "close_buy: 对多头方向提示风险/止盈止损/离场/不再做多。"
    "close_sell: 对空头方向提示风险/止盈止损/离场/不再做空。"
    "unclear: 仅提及/举例/对比/解释机制，或没有可落地的方向性建议。")
    )
field_instrument_type_deepseek = Field(..., 
    description=("instrument 的范围:"
        "stock: 个股/公司名/股票简称（如“台积电”“英伟达”“苹果”）。"
        "fx: 外汇货币对与汇率写法（如“美元/日元”“USDJPY”“人民币汇率”）。"
        "commodity: 大宗商品与其基准（如“黄金”“原油”“WTI”“布伦特”）"
        "crypto: 加密资产（如“比特币/BTC”“以太坊/ETH”）。"
        "index: 指数与指数简称（如“标普500”“纳指”“道指”“沪深300”“美元指数”）,仅指“金融市场指数/可交易指数（或其衍生品所跟踪的指数。"
        "etf: ETF/基金名称（如“SPY”“QQQ”“某某ETF”）。"
        "bond: 债券/国债（如“美债”“国债”“公司债”）。"
    ))

class TopicChunk_deepseek(BaseModel):
    chunk_id: int = field_id_deepseek

    start_anchor: str = Field(
        ...,
        min_length=1,
        description=(
            "该段主题在原始逐字稿中的起始锚点。"
            "必须是逐字稿中出现过的连续原文片段（精确子串，区分全角/半角与标点），"
            "用于定位该段开始位置。"
            "尽量短且唯一（建议 8-30 个中文字符），避免过长句子。"
            "不得改写、翻译或总结。"
        ),
    )
    topic: str = Field(..., min_length=1, description="该段的主题标签（自由文本，尽量短）")
    summary: str = Field(..., min_length=1, description="该段的中文摘要（只总结原文明确表达的内容）")

class TopicChunks_deepseek(BaseModel):
    topic_chunks: List[TopicChunk_deepseek] = Field(default_factory=list)

class EvidenceSpan_deepseek(BaseModel):
    evidence_id: int = field_id_deepseek
    evidence_explanation: str = Field(..., min_length=1,     
        description=(
        "证据摘要：用中文概括该 transcript 中与该信号直接相关的内容，"
        "说明为什么支持该 intent。"
        "不得引入 transcript 之外的新信息；"
        "尽量具体到‘观点/条件/风险/操作倾向’，而不是泛泛而谈。"
    ))

class TradingSignalBase_deepseek(BaseModel):
    signal_id: int = field_id_deepseek
    instrument: str = field_instrument_deepseek
    instrument_normalized: str = field_instrument_normalized_deepseek
    intent: Intent = field_intent_deepseek
    evidence_ids: List[int] = Field(default_factory=list, description="evidence_id列表")
    instrument_type: AssetClass = field_instrument_type_deepseek

class TradingSignal_deepseek(BaseModel):
    evidence: List[EvidenceSpan_deepseek] = Field(default_factory=list)
    signals: List[TradingSignalBase_deepseek] = Field(default_factory=list)


class EvidenceSpan_deepseek2(BaseModel):
    evidence_id: int = field_id_deepseek
    chunk_id: int = Field(..., ge=1, description="来自topic_chunk的chunk_id")
    chunk_topic: str = Field(..., min_length=1, description="对应 topic_chunk.topic(可复制)")
    remark: str = Field(
    ...,
    min_length=1,
    description=(
        "证据摘要：用中文概括该 chunk 中与该信号直接相关的内容，"
        "说明为什么支持该 intent。"
        "不得引入 chunk 之外的新信息；"
        "尽量具体到‘观点/条件/风险/操作倾向’，而不是泛泛而谈。"
    ))

class TradingSignalBase_deepseek2(BaseModel):
    signal_id: int = field_id_deepseek
    instrument: str = field_instrument_deepseek
    instrument_normalized: str = field_instrument_normalized_deepseek
    intent: Intent = field_intent_deepseek
    evidence_ids: List[int] = Field(default_factory=list, description="evidence_id列表")
    instrument_type: AssetClass = field_instrument_type_deepseek

class TradingSignal_deepseek2(BaseModel):
    evidence: List[EvidenceSpan_deepseek2] = Field(default_factory=list)
    signals: List[TradingSignalBase_deepseek2] = Field(default_factory=list)


# 2026-01-30T23:10:00
class EvidenceSpan_deepseek3(BaseModel):
    evidence_id: int = field_id_deepseek
    chunk_id: int = Field(..., ge=1, description="来自topic_chunk的chunk_id")
    remark: str = Field(
    ...,
    min_length=1,
    description=(
        "证据摘要：用中文概括该 chunk 中与该信号直接相关的内容，"
        "说明为什么支持该 intent。"
        "不得引入 chunk 之外的新信息；"
        "尽量具体到‘观点/条件/风险/操作倾向’，而不是泛泛而谈。"
    ))

class TradingSignalBase_deepseek3(BaseModel):
    signal_id: int = field_id_deepseek
    instrument: str = field_instrument_deepseek
    instrument_normalized: str = field_instrument_normalized_deepseek
    intent: Intent = field_intent_deepseek
    evidence_ids: List[int] = Field(default_factory=list, description="evidence_id列表")
    instrument_type: AssetClass = field_instrument_type_deepseek

class TradingSignal_deepseek3(BaseModel):
    evidence: List[EvidenceSpan_deepseek3] = Field(default_factory=list)
    signals: List[TradingSignalBase_deepseek3] = Field(default_factory=list)



field_instrument_from_helper_deepseek =  Field(..., min_length=1, 
    description=("来自helper.instruments.instrument"))
field_instrument_normalized_from_helper_deepseek = Field( ...,
    description=("来自helper.instruments.instrument_normalized"))

class EvidenceSpan_deepseek4(BaseModel):
    evidence_id: int = field_id_deepseek
    evidence_intent: str = Field(..., min_length=1,     
        description=(
        "证据摘要：用中文概括该 transcript 中与该信号直接相关的内容，"
        "说明为什么支持该 intent。"
        "不得引入 transcript 之外的新信息；"
        "尽量具体尽量具体仔细。"
    ))
    evidence_trading_window: str = Field(..., min_length=1,     
        description=(
        "证据摘要：用中文概括该 transcript 中与该信号直接相关的内容，"
        "说明为什么选择该 trading_window。"
        "不得引入 transcript 之外的新信息；"
        "尽量具体尽量具体仔细。"
    ))


class TradingSignalBase_deepseek4(BaseModel):
    signal_id: int = field_id_deepseek
    instrument: str = field_instrument_from_helper_deepseek
    instrument_normalized: str = field_instrument_normalized_from_helper_deepseek
    intent: Intent = field_intent_deepseek
    trading_window : TradingWindow = field_trading_window
    evidence_ids: List[int] = Field(default_factory=list, description="evidence_id列表")
    instrument_type: AssetClass = field_instrument_type_deepseek

class TradingSignal_deepseek4(BaseModel):
    evidence: List[EvidenceSpan_deepseek4] = Field(default_factory=list)
    signals: List[TradingSignalBase_deepseek4] = Field(default_factory=list)


# to standardize signal instrument for future comparison purpose
class TradingInstrumentBase_deepseek(BaseModel):
    instrument_id: int = field_id_deepseek
    instrument: str = field_instrument_deepseek
    instrument_normalized: str = field_instrument_normalized_deepseek
    instrument_type: AssetClass = field_instrument_type_deepseek

class TradingInstrument_deepseek(BaseModel):
    instruments: List[TradingInstrumentBase_deepseek] = Field(default_factory=list)
