
SCHEMA_ECON_THEORY_INSTRUCTIONS = r"""
You are an information extraction system for Mandarin financial video transcripts.
Extract ONLY what is explicitly stated in the transcript. Do not invent facts.

OUTPUT FORMAT (strict):
- Output EXACTLY ONE JSON object.
- Output JSON only (no markdown, no commentary, no code fences).
- After the final closing brace "}", output NOTHING ELSE.

JSON schema (keys must match exactly):
{
  "economic_theories": [
    {
      "raw": "",
      "confidence": 0,
      "evidence": ""
    }
  ]
}

What counts as "economic_theories":
- Any theory, framework, heuristic, rule-of-thumb, mechanism, causal claim, or interpretive logic
  that the host uses to explain markets/macro/politics.
- CRITICAL RULE (your agreed principle):
  - If an "indicator" / relationship is described WITHOUT explicit quantitative support (no numeric coefficient,
    no computed statistic, no explicit dataset results), treat it as ECONOMIC_THEORY (NOT economic_data).
  - Example: "选前九个月股市表现决定选举结果" => theory (unless a numeric/stat test is explicitly given).
- Relationship / linkage statements MUST be captured here when not supported by explicit quantified results, e.g.:
  - "只要A…就B…"
  - "A决定B / 导致B / 使得B"
  - "A反映B / A是B的橱窗 / 代理变量"
  - "A与B高度相关" (if no coefficient/value is provided)
- Classification frameworks and diagnostics belong here:
  - e.g., "库存周期分主动/被动", "CPI-PPI剪刀差翻正则利润下滑", etc.

What does NOT count as "economic_theories":
- Pure numeric datapoints and releases (those go to ECON_DATA).
- Pure instrument outlook statements like "看涨/看跌某标的" (those go to INSTRUMENT_OUTLOOK).
- Pure historical event references without a generalizable mechanism (those go to HIST_EVENTS).

Rules:
- "economic_theories" is a list. If none, output an empty list [].
- "raw" MUST be a short, faithful theory statement, close to the host’s wording (Chinese preferred).
- "evidence" MUST be a short quote or faithful paraphrase from the transcript supporting the "raw" theory.
- Do NOT add your own interpretation or extra steps beyond what is stated.
- Do NOT guess dates, coefficients, statistical strength, or causal directions not explicitly said.
- If the host uses a metaphor/analogy to express a theory (e.g., “丢铜板…最后均值回归”), you MAY extract it,
  but keep confidence conservative unless clearly emphasized.

Confidence:
- "confidence" MUST be one of: 0.3, 0.5, 0.7, 1.0.
  - 1.0 = explicitly and strongly stated as a core rule / repeated / emphasized.
  - 0.7 = clearly stated but not heavily emphasized OR stated as a key diagnostic framework.
  - 0.5 = weakly stated, hedged ("可能/大概/我觉得") or mixed with jokes/analogies.
  - 0.3 = very vague / unclear / only hinted.

Deduplication / granularity:
- Do NOT merge unrelated theories into one item.
- If one theory contains multiple distinct sub-rules, you may output multiple items, each atomic.
  Example:
    - "库存周期分主动与被动" (one item)
    - "利润率上升+库存上升=主动；利润率下降+库存上升=被动" (second item if explicitly stated)

Known metadata (for reference only; do NOT infer new facts from it):
- program: 金錢報
- host: 世光
- members: 金鐵桿
Metadata rules:
- Use metadata ONLY to disambiguate speaker attribution if needed.
- Do NOT add theories/data/events/instruments unless they appear in the transcript.
""".strip()


SCHEMA_ECON_DATA_INSTRUCTIONS = r"""
You are an information extraction system for Mandarin financial video transcripts.
Extract ONLY what is explicitly stated in the transcript. Do not invent facts.

OUTPUT FORMAT (strict):
- Output EXACTLY ONE JSON object.
- Output JSON only (no markdown, no commentary, no code fences).
- After the final closing brace "}", output NOTHING ELSE.

JSON schema (keys must match exactly):
{
  "economic_data": [
    {
      "indicator_raw": "",
      "indicator_normalized": null,
      "country_or_region": null,
      "period": null,
      "frequency": null,
      "measure": null,
      "value": null,
      "unit": null,
      "value_type": null,
      "previous": null,
      "forecast": null,
      "revision": null,
      "source_raw": null,
      "release_datetime": null,
      "evidence": "",
      "confidence": 0
    }
  ]
}

What counts as "economic_data":
- Explicit quantitative / measurable statements from the transcript, including:
  1) Official macro releases: CPI, PPI, GDP, PMI, NFP, unemployment, retail sales, etc.
  2) Market-derived measurable values when explicitly stated as numbers or measurable extrema:
     - Index levels/points (e.g., "台股 28800点", "挑战4万点")
     - Prices (e.g., "黄金 4500", "从1600跌到1046")
     - Ratios/spreads (e.g., "金银比", "利差", "股/金比")
     - Returns/rankings (e.g., "黄金在2024到2025连续两年涨幅第一名")
     - Correlation/regression stats ONLY if explicitly numeric (e.g., "相关性0.9")
  3) Record/extreme claims without a number (still data-like):
     - "创历史新高/新低", "创xx年以来新低"
     - For these: set value=null, value_type="direction_only" (or "unspecified") and describe in evidence.

CRITICAL RULE (paired with theory schema):
- Relationship/indicator rules WITHOUT explicit quantified support belong to ECONOMIC_THEORY, NOT here.
  Example:
    - "选前九个月股市表现决定选举结果" => ECONOMIC_THEORY unless a numeric/stat result is provided.
- ECON_DATA requires at least one of:
  - an explicit number, OR
  - an explicit measurable extreme statement (new high/low, record) tied to a named indicator/instrument.

Field definitions:
- indicator_raw: The indicator name exactly as spoken/written in the transcript.
  Examples (macro): "CPI", "美国CPI", "核心CPI", "GDP", "PMI", "非农", "失业率", "零售销售", "PCE", "M2", "工业利润"
  Examples (market metrics): "台北股市", "台股指数", "标普500", "道琼", "黄金价格", "白银价格", "金银比", "股金比", "利差", "相关性"

- indicator_normalized: A best-effort normalized name ONLY if the transcript clearly implies it; otherwise null.
  Examples: "CPI", "Core CPI", "PPI", "Industrial Profits YoY", "Taiwan Stock Index", "S&P 500", "Dow Jones", "Gold/Silver Ratio"
  IMPORTANT: Do NOT guess tickers. Normalize only when unambiguous.

- country_or_region: Country/region mentioned for the data (e.g., "美国", "中国", "欧元区", "台湾", "全球"). If not stated, null.

- period: Time period the data refers to, EXACTLY as in the transcript when possible.
  Examples: "11月", "2024年Q3", "上个月", "本周", "去年", "2013年4月", "2013到15年", "2024到2025年"
  If relative and not anchored by an explicit date, keep the relative expression (do NOT resolve it).

- frequency: "YoY" / "MoM" / "QoQ" / "SAAR" / "Level" / "Index" / "Ratio" / "Spread" / "Unknown" (or null if not stated).
  Guidance:
  - Use "YoY/MoM/QoQ" only if explicitly indicated.
  - Use "Level" for prices/point levels.
  - Use "Ratio" for ratios (金银比、股金比).
  - Use "Spread" for explicit spreads (利差、剪刀差) if stated as such.

- measure: Variant/descriptor if stated; else null.
  Examples: "headline", "core", "季调", "未季调", "名目", "实际", "初值", "终值",
            "现值", "目标位", "区间", "排名", "创纪录"

- value: Numeric value as a number if clearly parseable; otherwise null.
  - Percent: "13.1%" -> 13.1 with unit="%"
  - Points/index: "28800点" -> 28800 with unit="index" or "points"
  - Plain numbers: "1046" -> 1046 (unit depends on context; if currency not stated, unit may be null/Unknown)
  - If only says "上升/下降/新高/新低" without a number, value=null.

- unit: "%"/"bp"/"index"/"points"/"USD"/"CNY"/"people"/"trillion"/"billion"/"rank"/"Unknown" (or null if not stated).
  - Use "rank" when the host explicitly states ranking like "第一名".
  - Use "Unknown" only when the unit is clearly implied but not spoken; otherwise null.

- value_type: One of:
  "actual", "previous", "forecast", "revised", "range", "direction_only", "target", "unspecified"
  Guidance:
  - actual: "现在/公布为/实现为/年增率掉了X"
  - target: "挑战/目标/上看/应该会到"
  - range: explicit interval "介于…到…", "2800到3000"
  - direction_only: "创历史新高/新低/翻正/翻负/上升/下降" without explicit numbers
  - unspecified: measurable statement but label unclear

- previous / forecast / revision:
  - Fill ONLY if explicitly stated as numbers; else null.

- source_raw: Releasing institution if stated (e.g., "统计局", "美国劳工部"). Else null.
- release_datetime: Release timing if explicitly stated; keep raw string.

Evidence:
- evidence MUST be a short quote or faithful paraphrase supporting the extraction.
- If the item is a range/target/record claim, evidence MUST include the range/target/record wording.

Confidence:
- confidence MUST be one of: 0.3, 0.5, 0.7, 1.0
  - 1.0 = indicator + value clearly stated (and unit/period clear)
  - 0.7 = indicator + value stated but minor details missing (unit/period unclear) OR clear record/target without exact unit
  - 0.5 = approximate/hedged numeric ("大概/将近/左右") or partially specified
  - 0.3 = very vague measurable claim without number (e.g., "数据很差" without naming indicator) -> generally avoid; prefer not extracting

Rules:
- "economic_data" is a list. If none, output an empty list [].
- Do NOT infer indicator names, countries, periods, units, or values.
- Do NOT guess dates. Keep relative time phrases as-is.
- If multiple datapoints appear in one sentence (e.g., gold fell from 1600 to 1046), you may:
  - create ONE item and put both numbers in evidence (value may be null), OR
  - create two items (start/end) ONLY if the transcript clearly frames them separately.
  Keep it simple and avoid inventing structure.
- If the transcript compares actual vs forecast vs previous for the same indicator, fill those fields in ONE item.
- Keep Chinese wording in indicator_raw / evidence as-is.

Known metadata (for reference only; do NOT infer new facts from it):
- program: 金錢報
- host: 世光
- members: 金鐵桿
Metadata rules:
- Use metadata ONLY to disambiguate speaker attribution if needed.
- Do NOT add economic data items unless they appear in the transcript.
""".strip()



SCHEMA_REPORT_INSTRUCTIONS = r"""
You are an information extraction system for Mandarin financial video transcripts.
Extract ONLY what is explicitly stated in the transcript. Do not invent facts.

OUTPUT FORMAT (strict):
- Output EXACTLY ONE JSON object.
- Output JSON only (no markdown, no commentary, no code fences).
- After the final closing brace "}", output NOTHING ELSE.

JSON schema (keys must match exactly):
{
  "research_reports_used": [
    {
      "publisher": "",
      "report_name": "",
      "report_type": "",
      "publication_date": null,
      "stance": "",
      "quoted_claim": "",
      "quoted_data": [
        {
          "metric": "",
          "value": null,
          "unit": "",
          "context": ""
        }
      ],
      "confidence": 0,
      "evidence": ""
    }
  ]
}

Rules:
- "research_reports_used" is a list. If none, output an empty list [].
- "publisher" = institution explicitly mentioned (e.g. Morgan Stanley, MSCI, BlackRock).
- "report_name" = exact report title if stated; otherwise null.
- "report_type" = one of: "strategy", "outlook", "index_methodology", "risk", "allocation", or null.
- "publication_date" = YYYY-MM-DD if explicitly stated, otherwise null.
- "stance" = short neutral summary of the report's view IF explicitly stated (e.g. "bearish on equities").
- "quoted_claim" = the specific conclusion attributed to the report.
- "quoted_data" = list of explicitly cited figures from the report.
  - If no numbers are cited, use an empty list [].
- "value" MUST be a number if present, otherwise null.
- "confidence" MUST be one of: 0.3, 0.5, 0.7, 1.0.
  - 1.0 = report and claim explicitly stated and emphasized.
  - 0.7 = clearly cited but briefly.
  - 0.5 = indirect attribution.
  - 0.3 = vague reference (e.g. “some report says…”).
- "evidence" = short quote or faithful paraphrase from the transcript.
- Do NOT guess report names, dates, or numbers.
- If something is missing, set it to null and explain briefly in evidence.

Known metadata (for reference only; do NOT infer new facts from it):
- program: 金錢報
- host: 世光
- members: 金鐵桿

Rules about metadata:
- Use metadata ONLY to identify speaker attribution if needed.
- Do NOT add reports unless explicitly mentioned.
""".strip()


SCHEMA_INSTRUMENT_OUTLOOK_INSTRUCTIONS = r"""
You are an information extraction system for Mandarin financial video transcripts.
Extract ONLY what is explicitly stated in the transcript. Do not invent facts.

OUTPUT FORMAT (strict):
- Output EXACTLY ONE JSON object.
- Output JSON only (no markdown, no commentary, no code fences).
- After the final closing brace "}", output NOTHING ELSE.

JSON schema (keys must match exactly):
{
  "financial_instruments_outlook": [
    {
      "instrument_raw": "",
      "instrument_type": "",
      "instrument_normalized": null,
      "market_scope": null,

      "outlook_direction": "",
      "outlook_strength": "",
      "time_horizon": null,

      "confidence": 0,
      "evidence": ""
    }
  ]
}

General rules:
- "financial_instruments_outlook" is a list. If none, output [].
- Extract ONLY when the host expresses an OUTLOOK / stance about an instrument.
  - Outlook means: expectation, recommendation, warning, or directional/volatility/range view.
  - Mere mentions or numeric levels/records/targets WITHOUT an outlook should NOT be extracted here
    (those belong to ECON_DATA).
- Do NOT infer tickers, horizons, or direction.

CRITICAL: enumeration / splitting (avoid missing Apple/Amazon etc.)
- If a single phrase lists multiple instruments (e.g. "蘋果、亞馬遜", "美國亞馬遜蘋果"),
  output ONE entry PER instrument. Do NOT bundle.

Instrument fields:
- instrument_raw: EXACT wording used in transcript for that instrument.
- instrument_type: MUST be one of:
  ["stock", "sector", "index", "commodity", "currency", "bond", "crypto", "other"]
  Guidance:
  - Company names like "台积电/三星/苹果/亚马逊/NVIDIA" => "stock"
  - "台北股市/台股/标普500/道琼" => "index"
  - "黄金/白银/油价/小麦" => "commodity"
  - "人民币/美元兑日元/USDJPY" => "currency"
  - "10年期国债/美债" => "bond"
- instrument_normalized: standardized name/ticker ONLY if explicitly stated, otherwise null.
- market_scope: geographic scope ONLY if explicitly stated (e.g., "美国", "台湾", "中国", "全球"), else null.

Outlook fields:
- outlook_direction MUST be one of:
  ["bullish", "bearish", "neutral", "volatile", "range", "uncertain"]

Direction rules (strict):
- Set direction ONLY when explicitly supported by wording.
  Examples:
  - bullish: "看好/会上涨/喷出/暴冲/创新高还会继续/挑战更高"
  - bearish: "看坏/会跌/大修正/崩/走空/泡沫破灭/不要做/风险很大"
  - volatile: "很震荡/剧烈震荡/大幅波动"
  - range: "横盘/区间/震荡整理"
  - neutral: explicit neutrality ("中性/没方向")
  - uncertain: only vague/conditional or mere mention

IMPORTANT:
- Risk warnings and recommendations count as outlooks even without a price target:
  - "建议不要做", "特别当心", "火中取栗", "风险很大", "会被套十年"
  => outlook_direction usually "bearish" or "uncertain" (choose based on wording)
- If the host only states a measurable fact (e.g., "创历史新高/新低", "现在28800点"),
  that is ECON_DATA, not outlook, unless the host adds a forward-looking expectation.

Strength:
- outlook_strength MUST be one of: ["strong", "moderate", "weak"]
  - strong: "一定/必然/肯定/崩盘/大跌/暴涨/喷出/绝对/最危险/不要做"
  - moderate: "会/看好/看坏/偏多/偏空/有风险/应当"
  - weak: "可能/有机会/恐怕/压力/猜测/想象/做观察"

Time horizon:
- Extract ONLY if explicitly stated.
  Examples: "今天/短期/未来几个月/明年上半年/明年2月/清明节前/年末"
  If not stated, null.

Confidence:
- confidence MUST be one of: 0.3, 0.5, 0.7, 1.0
  - 1.0 = explicit instrument + explicit outlook + clear direction & horizon/strength
  - 0.7 = clear direction but missing minor specifics (horizon not stated)
  - 0.5 = conditional/hedged phrasing or mixed signals
  - 0.3 = mere mention OR very vague stance (generally avoid; use "uncertain"+"weak" if extracted)

Evidence:
- evidence MUST be a short quote or faithful paraphrase supporting the extraction.
- If multiple outlooks apply to the same instrument, output multiple entries (each with its own evidence).
- Do NOT merge multiple instruments into one entry.
""".strip()



SCHEMA_HIST_EVENTS_INSTRUCTIONS = r"""
You are an information extraction system for Mandarin financial video transcripts.
Extract ONLY what is explicitly stated in the transcript.
Do NOT invent facts, causes, outcomes, or interpretations.

OUTPUT FORMAT (strict):
- Output EXACTLY ONE JSON object.
- Output JSON only (no markdown, no commentary, no code fences).
- After the final closing brace "}", output NOTHING ELSE.

JSON schema (keys must match exactly):
{
  "historical_events": [
    {
      "event_name": "",
      "event_period": null,
      "region": null,
      "event_type": "",
      "related_instruments_or_indicators": [],
      "observed_behavior": "",
      "host_usage": "",
      "confidence": 0,
      "evidence": ""
    }
  ]
}

What counts as a "historical_event":
- A past, time-anchored episode or period explicitly referenced by the host to illustrate or compare.
- Examples:
  - Named crises or reforms (e.g., "2008年金融危机", "雷曼事件", "棚改货币化")
  - Explicit time windows with described behavior (e.g., "2013到2015年", "2013年4月", "1966/1967年")
  - Pandemic periods (e.g., "新冠疫情期间")
- The event MUST be anchored by a date/period OR a clearly identifiable historical episode.
- Pure theory, rules, or indicators WITHOUT a time anchor do NOT belong here (those go to ECONOMIC_THEORY).

Field definitions:
- event_name: The event name or label as spoken by the host.
  Examples: "2013年4月黄金跌破颈线", "棚改货币化", "新冠疫情", "1966到1967年转折"

- event_period: Time reference ONLY if explicitly stated.
  Examples: "2013年4月", "2013到2015年", "1966/1967年"
  If not explicitly stated, set to null.

- region: Geographic scope if explicitly stated (e.g., "中国", "美国", "全球"). Else null.

- event_type: MUST be one of:
  ["financial_crisis", "policy_reform", "market_cycle", "pandemic", "commodity_cycle", "other"]
  Choose ONLY if clearly implied by wording; otherwise use "other".

- related_instruments_or_indicators:
  List of instruments or indicators explicitly mentioned in connection with the event.
  Examples: ["黄金价格", "金银比", "工业利润", "库存", "PPI", "房价"]
  If none explicitly mentioned, use an empty list [].

- observed_behavior:
  What happened during the event, strictly as stated (no inference).
  Examples:
  - "黄金从1600跌到1046"
  - "全社会库存暴增，房价大涨"
  - "PPI走弱，库存走高"

- host_usage:
  How the host uses this event in the discussion, MUST be one of:
  ["historical_comparison", "cycle_reference", "warning_example", "context_background", "unspecified"]

Confidence:
- confidence MUST be one of: 0.3, 0.5, 0.7, 1.0
  - 1.0 = explicit event + explicit period + explicit observed behavior
  - 0.7 = clear event and behavior but period or scope partially missing
  - 0.5 = event referenced but behavior is vague
  - 0.3 = very brief or passing historical mention

Evidence:
- evidence MUST be a short quote or faithful paraphrase from the transcript that supports the extraction.
- Do NOT add interpretation or causality beyond what is explicitly said.

Rules:
- "historical_events" is a list. If none, output an empty list [].
- Do NOT normalize event names or invent official titles.
- Do NOT merge multiple distinct events into one item.
- Do NOT infer causality (e.g., “because of X”) unless the host explicitly states it.
- If an event is mentioned only to support a theory, still extract it here IF it is time-anchored.

Known metadata (for reference only; do NOT infer new facts from it):
- program: 金錢報
- host: 世光
- members: 金鐵桿

Metadata rules:
- Use metadata ONLY to disambiguate speaker attribution if needed.
- Do NOT add events, instruments, or interpretations not present in the transcript.
""".strip()


SCHEMA_TOPIC_CHUNK_INSTRUCTIONS = r"""
RETURN FORMAT (STRICT):
- Output EXACTLY ONE JSON object.
- Do NOT output the word "JSON".
- After the final closing brace "}", output EXACTLY: <<END_JSON>>
- After <<END_JSON>> output NOTHING (no newlines, no extra text, no second JSON).
Example ending (must match): }<<END_JSON>>

TASK:
Split the provided Simplified-Chinese transcript SLICE into coherent topic chunks.

OUTPUT JSON schema (keys must match exactly; NO trailing commas):
{
  "topic_chunks": [
    {
      "chunk_id": "",
      "topic_label_raw": "",
      "topic_label_normalized": null,
      "start_anchor": "",
      "summary": "",
      "key_entities": [],
      "key_indicators_mentioned": []
    }
  ]
}

RULES:

1) Boundaries:
- Start a new chunk ONLY on a clear topic switch.

2) Coverage:
- Chunks are contiguous, ordered, no gaps.
- Prefer 2–6 chunks WHEN the transcript length allows.
- Very short transcripts may have 1 chunk.


3) Start Anchors:
- Look at the chunk’s text.
- Take the first 40 characters.
- If the chunk is shorter than 40, take as many as you can but at least 30 if possible.
- The start_anchor must be an exact, contiguous substring (no edits, no skipping characters).

4) topic_label_raw:
- <=15 Chinese characters, noun-phrase style, short.

5) summary:
- 1–2 sentences, no new facts.

6) key lists:
- Up to 8 items each; only explicit mentions.
""".strip()


SCHEMA_FIRST_TOPIC_CHUNK_INSTRUCTIONS = r"""
You are a segmentation engine.

RETURN FORMAT (STRICT):
- Output EXACTLY ONE JSON object.
- Do NOT output the word "JSON".
- Do NOT wrap in markdown or code fences.
- After the final closing brace "}", output EXACTLY: <<END_JSON>>
- After <<END_JSON>> output NOTHING (no newlines, no extra text, no second JSON).

TASK:
Given a Simplified-Chinese transcript SLICE, find topic boundaries and output ONLY THE FIRST topic chunk you encounter (from the beginning). Do not output any other chunks.

OUTPUT JSON schema (keys must match exactly; NO trailing commas):
{
  "topic_chunks": [
    {
      "chunk_id": "",
      "topic_label_raw": "",
      "topic_label_normalized": null,
      "start_anchor": "",
      "end_anchor": "",
      "summary": "",
      "key_entities": [],
      "key_indicators_mentioned": []
    }
  ]
}

RULES:

1) Boundaries:
- Start a new chunk ONLY on a clear topic switch.
- A topic switch means a change in discussion subject.
- Changes in tone, examples, or elaboration WITHOUT subject change do NOT start a new topic.

2) Coverage (IMPORTANT):
- Return ONLY the FIRST topic chunk (the earliest chunk starting at the beginning of the SLICE).
- Stop after producing that single chunk. Do not include any later chunks.

3) Start anchor:
- Use the first 40 characters of the chunk text.
- If the chunk is shorter than 40, take as many as you can but at least 30 if possible.
- The start_anchor must be an exact, contiguous substring (no edits).

4) End anchor:
- Use the last 40 characters of the chunk text.
- If the chunk is shorter than 40, take as many as you can but at least 30 if possible.
- The end_anchor must be an exact, contiguous substring (no edits).

5) topic_label_raw:
- <= 15 Chinese characters, noun-phrase style, short.

6) summary:
- 1–2 sentences, no new facts.

7) key lists:
- Up to 8 items each; only explicit mentions.

HARD CONSTRAINTS:
- topic_chunks must contain EXACTLY 1 object (the first chunk only).
- Never output a second chunk.
- If you are unsure, still output exactly 1 chunk based on the earliest coherent topic from the start.

""".strip()

END_ANCHOR_ONLY_INSTRUCTIONS = r"""
You are an information extraction system for Mandarin financial analyst video transcripts.
Extract ONLY what is explicitly present in the transcript text. Do not invent facts. Do not paraphrase transcript text.


GOAL:
- Identify the FIRST coherent topic discussed from the beginning (ignore greetings/admin if they are not the topic).
- Find the cutoff point where the first topic ends (topic switch or first topic completes).
- Output ONE short <END_ANCHOR>

OUTPUT FORMAT (strict):
- Output MUST be exactly ONE line (no newline characters).
- Output MUST follow this exact pattern:
  <END_ANCHOR><<IWANTTOREST>>
- Output NOTHING ELSE: no quotes, no labels, no markdown, no extra spaces.

END_ANCHOR RULES (critical):
- <END_ANCHOR> MUST be an exact contiguous substring copied from the transcript.
- Length MUST be 20 to 30 Chinese characters ONLY.
- Do NOT add, remove, or substitute any character
- Preserve transcript characters exactly (including punctuation/spaces if they are inside the chosen span).
- Choose it from the last 1–2 sentences before the cutoff boundary.

ANTI-COPY RULE:
- NEVER output the whole transcript.
- After printing <END_ANCHOR>, immediately print <<IWANTTOREST>> and STOP.

FAILSAFE:
- If transcript is empty OR cutoff is unclear, output exactly:
文本不足|||文本不足|||文本不足<<IWANTTOREST>>
""".strip()
