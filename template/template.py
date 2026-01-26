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
    
class TopicChunk_deepseek(BaseModel):
    chunk_id: int = Field(..., ge=1, description="从1开始递增的分段编号")

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

    end_anchor: str = Field(
        ...,
        min_length=1,
        description=(
            "该段主题在原始逐字稿中的结束锚点。"
            "必须是逐字稿中出现过的连续原文片段（精确子串，区分全角/半角与标点），"
            "用于定位该段结束位置。"
            "尽量短且唯一（建议 8-30 个中文字符），避免过长句子。"
            "不得改写、翻译或总结。"
        ),
    )
    topic: str = Field(..., min_length=1, description="该段的主题标签（自由文本，尽量短）")
    summary: str = Field(..., min_length=1, description="该段的中文摘要（只总结原文明确表达的内容）")

class TopicChunks_deepseek(BaseModel):
    topic_chunks: List[TopicChunk_deepseek] = Field(default_factory=list)
    

# To extract trading signal
class AssetClass(str, Enum):
    STOCK = "stock"
    FX = "fx"
    COMMODITY = "commodity"
    CRYPTO = "crypto"
    INDEX = "index"
    RATE = "rate"
    ETF = "etf"
    BOND = "bond"
    OTHER = "other"

class Intent(str, Enum):
    OPEN_BUY = "open_buy"     # initiate/open/add exposure
    OPEN_SELL = "open_sell"   # initiate/open/add exposure
    CLOSE_BUY = "close_buy"     # close/reduce/exit exposure
    CLOSE_SELL = "close_sell"   # close/reduce/exit exposure
    NO_ACTION = "no_action"

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

class EvidenceSpan_deepseek(BaseModel):
    evidence_id: int = Field(..., ge=1, description="Integer starting from 1")
    sentence: str = Field(..., min_length=1, description="Evidence text span (can be fragment).")
    evidence_type: str = Field(..., min_length=1, description="Free-form label/tag in english.")

class TradingSignalBase_deepseek(BaseModel):
    signal_id: int = Field(..., ge=1, description="Integer starting from 1")
    instrument: str = Field(..., min_length=1, description="Raw instrument name from transcript")
    instrument_normalized: Optional[str] = Field(
        None,
        description="Canonical standardized name in english; null if cannot normalize."
    )
    intent: Intent = Field(..., description="open_buy/open_sell/close_buy/close_sell/no_action")
    confidence: Confidence = 0.7
    evidence_ids: List[int] = Field(default_factory=list, description="List of evidence_id integers")
    instrument_type: AssetClass = Field(..., description="Allowed asset class enum value")

class TradingSignal_deepseek(BaseModel):
    evidence: List[EvidenceSpan_deepseek] = Field(default_factory=list)
    signals: List[TradingSignalBase_deepseek] = Field(default_factory=list)