
SCHEMA_DEVELOPER_OPENAI = r"""You are an information extraction system for Mandarin financial video transcripts.
Split the transcript into coherent TOPIC CHUNKS.
Prefer FEWER, LARGER chunks.
Create a new chunk ONLY when the main topic changes in a sustained way.
Do NOT split due to examples, repetition, or elaboration of the same idea.
start_anchor MUST be an exact substring from the transcript and 30 to 40 Chinese characters.
Extract only what is explicitly stated. Do not invent facts.
"""


SCHEMA_SIGNAL_RULES = r"""
Extract TRADING SIGNALS (forward-looking bets) from a Mandarin Chinese financial transcript.

OUTPUT:
- Output must match the provided template exactly.

COVERAGE (IMPORTANT):
- Do not only return the most prominent instrument.
- Extract signals for ALL explicitly mentioned instruments that have any forward-looking bias or positioning implication supported by evidence.
- If an instrument is mentioned but has no forward-looking bias and no positioning implication, set no action.
- Ambigious/weak/implied signals are welcome with low confidence value.

SIGNAL:
- A signal (open_*/close_* intents) is a statement that implies either 
(a) a trading action/positioning, OR 
(b) a forward-looking directional bias
- Observation OR recap = "no_action"

INSTRUMENT:
- Only extract instruments explicitly mentioned.
- instrument.name_raw must be exact transcript wording.
- symbol null unless explicitly stated.
- asset_class best-effort; if unclear use "other".

INTENT:
- open_buy/open_sell: statements that express a bullish/bearish directional bias, or encourage initiating/adding exposure in that direction.
- close_buy/close_sell: statements that imply reducing/exiting exposure for risk control or profit-taking (defensive / de-risk).
- no_action: observation/recap only; NOT a tradable bias.

EVIDENCE (STRICT + LINKING, WITH IMPLICIT REFERENCE):
- evidence.sentence MUST be copied EXACTLY as a contiguous substring (keep whitespace/line breaks).
- A signal may reference multiple evidence snippets.

- Evidence snippets can be:
  (A) explicit: contains instrument.name_raw exactly, OR
  (B) implicit: does NOT contain instrument.name_raw, but is clearly part of the same local passage where the instrument is being discussed (coreference/ellipsis), with no topic switch to another instrument in-between.

- To emit a signal, across referenced evidence snippets you must have:
  (i) at least one snippet that anchors the instrument (explicit mention), AND
  (ii) at least one snippet that provides the forward-looking bias or positioning implication (explicit or implicit).
- If you cannot provide an explicit instrument anchor snippet, omit the signal.

NO_ACTION HANDLING:
- For intent = "no_action", only an explicit instrument anchor snippet (contains instrument.name_raw) is required.
- Do NOT output "no_action" for an instrument that already has any open_*/close_* signal.

INTEGRITY:
- evidence_id and signal_id: unique increasing integers starting at 1.
- Each signal must have >=1 evidence_id; all evidence_ids must exist; no unused evidence.

CONFIDENCE:
- confidence must be between 0.0 and 1.0.
- Explicit action/positioning => >=0.7
- Direction/bias only => <=0.5
- Ambigious evidence => <=0.3
- no_action => == 0.0
"""