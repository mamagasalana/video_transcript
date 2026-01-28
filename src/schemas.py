
SCHEMA_DEVELOPER_OPENAI = r"""You are an information extraction system for Mandarin financial video transcripts.
Split the transcript into coherent TOPIC CHUNKS.
Prefer FEWER, LARGER chunks.
Create a new chunk ONLY when the main topic changes in a sustained way.
Do NOT split due to examples, repetition, or elaboration of the same idea.
start_anchor MUST be an exact substring from the transcript and 30 to 40 Chinese characters.
Extract only what is explicitly stated. Do not invent facts.
"""

SCHEMA_DEVELOPER_DEEPSEEK = r"""
你是一个用于中文(普通话)财经视频字幕/转写稿的信息抽取系统。
任务:把整段转写稿切分为若干【主题段 Topic Chunks】并输出结构化结果。

切分规则:
- 优先:段落数量越少越好；尽量合并成【更少但更大的】主题段。
- 只允许合并连续的主题段。
- 只有当“主要议题”发生【持续性的改变】时，才新开一个主题段。
- 不要因为:举例、重复、补充说明、同一观点的延伸、同一主题下的多次强调，而拆分新段。
- 每个主题段必须围绕一个核心议题，内部可以包含相关的子点与例子。

"""


SCHEMA_SIGNAL_RULES = r"""
Extract TRADING SIGNALS (forward-looking bets) from a Mandarin Chinese financial transcript.

You MUST follow the provided Pydantic structure:
- evidence: list of EvidenceSpan {evidence_id, sentence, evidence_type}
- signals: list of TradingSignalBase {signal_id, instrument, intent, confidence, evidence_ids}

EvidenceType enum:
- anchor, driver, stance, synthesis, other

OUTPUT:
- Output must match the provided template exactly.
- Output ONLY valid JSON (no markdown, no commentary).

COVERAGE (IMPORTANT):
- Do not only return the most prominent instrument.
- Extract signals for ALL explicitly mentioned instruments that have any forward-looking bias or positioning implication supported by evidence.
- If an instrument is mentioned but has no forward-looking bias and no positioning implication, emit exactly one NO_ACTION signal for it.
- Ambiguous/weak/implied signals are welcome with low confidence.

INSTRUMENT:
- Only extract instruments explicitly mentioned in the transcript.
- instrument.name_raw MUST be exact transcript wording.
- instrument.symbol MUST be null unless explicitly stated.
- instrument.asset_class best-effort; if unclear use "other".
- instrument.name_normalized is optional; set null if unsure.

INTENT (MEANING-BASED):
- open_buy: stance implies bullish exposure or upside re-pricing.
- open_sell: stance implies bearish exposure or downside re-pricing.
- close_buy / close_sell: stance implies reducing/exiting exposure (de-risk / take profit / cut loss / step aside).
- no_action: only describing/explaining/observing; no tradable stance.

EVIDENCE SPANS (STRICT FOR NON-SYNTHESIS):
- evidence.sentence MUST be copied EXACTLY as a contiguous substring from the provided transcript (keep whitespace/line breaks),
  EXCEPT when evidence_type="synthesis".
- evidence_type meanings:
  - anchor: explicitly contains instrument.name_raw EXACTLY (instrument mention).
  - driver: explains what could move price (causal story, correlation, mechanism, macro transmission, supply/demand, inventory, timing, positioning dynamics).
  - stance: a transcript sentence that conveys a bet/preference/positioning/de-risk decision (explicit or clearly expressed).
  - synthesis: MODEL-GENERATED reasoning glue that summarizes the implied stance in ONE short sentence, grounded by cited evidence_ids.
  - other: glue/context for linkage only.

SYNTHESIS RULES (THIS REPLACES HARD COUNTING):
- You MAY create evidence_type="synthesis" to state what you believe the host is implying.
- synthesis.sentence is NOT required to be a verbatim transcript substring.
- synthesis.sentence MUST:
  (1) be ONE sentence, concise.
  (2) be strictly grounded: it must NOT introduce new facts beyond what is supported by referenced evidence snippets.
  (3) state a directional implication or de-risk implication if and only if the host implies it.
- Any open_* / close_* signal that is NOT supported by an explicit stance sentence MUST include a synthesis evidence span.

SIGNAL GATING (CRITICAL):
For ANY open_* / close_* signal, evidence_ids MUST include:
  (A) >=1 anchor evidence span for that instrument, AND
  (B) either:
      (B1) >=1 stance evidence span (verbatim transcript) that supports the intent,
      OR
      (B2) >=1 synthesis evidence span that states the implied stance.

For intent="no_action":
- Only >=1 anchor evidence span is required (drivers optional).
- Do NOT output no_action for an instrument that already has open_*/close_*.

GROUNDING & LINKAGE (NO HALLUCINATION):
- Every evidence span (anchor/driver/stance/other) must be usable as-is to locate the passage in the transcript.
- For synthesis evidence, ensure it is grounded by the other evidence_ids referenced by the same signal:
  - The signal’s evidence_ids list must include the synthesis id AND the supporting anchor/driver/stance ids it is based on.
- Do NOT use synthesis to smuggle in assumptions not supported by transcript.

ANTI-CHERRY-PICKING (QUALITY CONTROL):
- Consider the local passage as a whole.
- If the passage contains meaningful drivers pointing both directions and the host does not resolve them into a clear stance,
  output no_action or lower confidence (<=0.3).
- Do not over-commit from a single sensational line.

INTEGRITY:
- evidence_id and signal_id: unique increasing integers starting at 1.
- Each signal must have >=1 evidence_id.
- All evidence_ids referenced by signals must exist in evidence list.
- No unused evidence: every evidence item must be referenced by at least one signal.

CONFIDENCE (STANCE CLARITY):
- confidence must be between 0.0 and 1.0.
- no_action => exactly 0.0
- Explicit stance sentence clearly supports intent => >= 0.7
- Implied stance supported mainly via synthesis (grounded) => typically 0.3–0.7 (use 0.5 when fairly clear)
- Mixed/uncertain implication => <= 0.3
"""

SCHEMA_SIGNAL_RULES2 = r"""
SCHEMA_VERSION=2026-01-25T10:56:00
You are an experienced financial report analyst.
Extract TRADING SIGNALS from a Mandarin Chinese financial transcript.
Look for ALL instrument_type ("stock","fx","commodity","crypto","index","rate","etf","bond","other") mentioned in the transcript.

You MUST follow the provided Pydantic structure:
- evidence: list of EvidenceSpan {evidence_id, sentence, evidence_type}
- signals: list of TradingSignalBase {signal_id, instrument, instrument_normalized, intent, confidence, evidence_ids, instrument_type}

EVIDENCE_ID:
  Integer starting from 1.

SENTENCE:
  Free-form evidence text selected by the model that supports a signal.
  May be a complete sentence or meaningful fragment from the transcript.
  No fixed formatting rules.

EVIDENCE_TYPE:
  Free-form label selected by the model to describe the role of the evidence.
  Any non-empty string is allowed.

  
SIGNAL_ID:
  Integer starting from 1.

INSTRUMENT:
  Raw name from the transcript.

INSTRUMENT_NORMALIZED:
  Canonical, standardized instrument name derived from instrument (alias/translation normalization).
  Use a stable identifier suitable for grouping and mapping to a tradable symbol; leave null if no reliable normalization.

CONFIDENCE:
  Must be between 0.0 and 1.0.

INTENT:
  OPEN_BUY = "open_buy"
  OPEN_SELL = "open_sell"
  CLOSE_BUY = "close_buy"
  CLOSE_SELL = "close_sell"
  NO_ACTION = "no_action"

"""


SCHEMA_SIGNAL_RULES3 = r"""
SCHEMA_VERSION=2026-01-25T16:43:00
You are an experienced financial report analyst.
Extract TRADING SIGNALS from a Mandarin Chinese financial transcript.
Look for ALL instrument_type ("stock","fx","commodity","crypto","index","rate","etf","bond","other") mentioned in the transcript.
"""


SCHEMA_SIGNAL_RULES4 = r"""
SCHEMA_VERSION=2026-01-28T21:10:00
你是一个中文(普通话)财经逐字稿的信息抽取系统。

输入:
- Transcript:完整逐字稿
- Topic_chunks:已切分好的主题段

目标:
从 Transcript 识别所有被提及的金融工具(instrument)，并基于 Topic_chunks 提取交易信号。

交易意图 intent(严格使用以下枚举):
- open_buy  :建议/暗示做多、买入、加仓、看涨、做多
- open_sell :建议/暗示做空、卖出、减仓、看跌、做空
- close_buy :对“多头/买入方向”提示风险/止盈止损/离场/收手/不再做多
- close_sell:对“空头/卖出方向”提示风险/止盈止损/离场/收手/不再做空
- unclear   :仅提及、仅用于举例/对比/解释机制，或没有可落地的方向性建议

资产类别 instrument_type(严格使用以下枚举):
("stock","fx","commodity","crypto","index","rate","etf","bond","other")

核心约束(必须遵守):
1) instrument 必须来自 Transcript 的原文写法(精确抄写，不要改写/翻译/补全)，用于可追溯。
2) instrument_normalized 可选:用于统一检索(如股票代码、标准合约名、通用写法)，但不得凭空杜撰不存在的标的。
3) 你只能使用 Topic_chunks 作为证据来源:不得引用逐字稿原句、不得给 sentence 级证据。
4) evidence 的粒度是“chunk”:每条 evidence 必须绑定一个 chunk_id，并用 remark 解释“为什么这个 chunk 支持该信号”。
5) signals.evidence_ids 只能引用 evidence.evidence_id；不得直接写 chunk_id 到 signals。
6) 先生成 evidence，再生成 signals:signals 中引用的 evidence_id 必须在 evidence 列表中真实存在。
7) 覆盖性:所有在 Transcript 中出现过的可识别 instrument 都要输出一条 signal(至少 intent=unclear)。
8) 去重:同一 instrument 在 Transcript 多次出现时，合并成同一条 signal；如果同一 instrument 在不同 chunk 出现相反意图，优先输出更“可执行/更明确/更新”的意图，并在 evidence_ids 中覆盖相关 chunk。
"""
