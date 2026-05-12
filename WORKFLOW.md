# Workflow

This project currently works in 2 main steps:

1. Step 1: extract instrument
2. Step 2: classify instrument
3. Step 3: extract signal

The key idea is:

- Step 1 should answer: "what is the speaker talking about?"
- Step 2 should answer: "how should we tag it in our taxonomy?"
- Step 3 should answer: "what is the host's trading view on that tagged target?"

These 2 jobs should stay separate.

All 3 jobs should stay separate.

## Step 1

Entry:

- [main/extract_instrument.py](/home/ytee/test/GuruArena/main/extract_instrument.py)

Purpose:

- read transcript files
- extract financial instruments mentioned in the transcript
- normalize noisy mentions into a stable `instrument_normalized`

What Step 1 should do:

- identify the instrument from full transcript context
- normalize obvious ASR noise when confidence is high
- keep the normalized result close to what the speaker actually meant
- preserve a useful alias cluster from transcript raw values

What Step 1 should not do:

- should not over-resolve a generic concept into a very specific branded index
- should not invent a country, benchmark, or product wrapper unless transcript context really supports it
- should not turn a broad factor / sector / theme into a specific index just because such an index exists

Examples:

- `周期因子` should usually stay `周期因子`, not jump to `MSCI World Cyclical Sectors Index`
- `市值因子` should stay a generic factor concept, not a branded benchmark
- `四值因子` is likely ASR noise and should be corrected to `市值因子` if confidence is high
- `两年期的国债期货` should only become a US-specific treasury product if transcript context clearly supports that

Common failure mode in Step 1:

- over-normalization

This means the extractor takes a broad idea and converts it into a too-specific object.

Examples:

- generic factor -> specific MSCI index
- generic China equity mention -> specific benchmark
- generic bond mention -> specific US Treasury instrument

The downstream problem is that Step 2 then trusts that over-specific norm and tags it accordingly.

## Step 2

Entry:

- [main/extract_classification.py](/home/ytee/test/GuruArena/main/extract_classification.py)
- schema lives in [template/template_20260424_2026.py](/home/ytee/test/GuruArena/template/template_20260424_2026.py)

Purpose:

- take `instrument_normalized`
- use aliases as supporting evidence
- map the instrument into the internal tag taxonomy

Current input shape:

```json
{
  "instrument_normalized": "...",
  "aliases": ["...", "..."]
}
```

What Step 2 should do:

- trust `instrument_normalized` first
- use aliases only as support, disambiguation, or ASR sanity check
- map the input into stable internal tags like:
  - `equity_benchmark`
  - `equity_sector11Financials`
  - `equity_sector25Banks`
  - `equity_factorSize`
  - `gov_2Y`
  - `cmd_soybean`
  - `fx_basket`

What Step 2 should not do:

- should not re-extract the transcript
- should not casually override a good normalized instrument
- should not invent a more specific entity than the normalized input supports

Examples:

- `周期因子` -> `equity_factorCyclical`
- `市值因子` -> `equity_factorSize`
- `大豆期货` -> `cmd_soybean`
- `Asia Dollar Index` -> `fx_basket`, `ASIAPAC`

## Step 3

Purpose:

- take the full transcript
- take the helper generated after Step 1 and Step 2
- extract trading signals on the final target

Current helper shape:

```json
{
  "instrument": ["美国股市", "标普500", "道琼指数"],
  "instrument_normalized": "equity_benchmark_USA"
}
```

Important:

- in Step 3, `instrument_normalized` is the real target
- `instrument` is only helper text for locating that target in the transcript
- Step 3 should not re-extract or re-classify the target unless it is clearly invalid or a weaker duplicate

What Step 3 should do:

- read the full transcript
- use `instrument` to find where the target is discussed
- judge the host's trading view on `instrument_normalized`
- output:
  - `open_buy`
  - `open_sell`
  - `close_buy`
  - `close_sell`
  - `unclear`
  - `invalid`
  - `duplicate`

What Step 3 should not do:

- should not rewrite helper fields
- should not turn one helper row into a different target
- should not output `unclear` together with a stronger signal for the same helper row
- should not output `invalid` together with any directional signal for the same helper row

Multi-signal rule:

- one helper item may output multiple signals
- but only if the intents are different
- example:
  - same helper item can output one `open_buy` and one `open_sell`
- if multiple transcript spans support the same intent, they should be merged into one signal

Duplicate rule:

- `duplicate` only applies across different helper items
- it starts from overlapping raw `instrument` wording
- then Step 3 decides which `instrument_normalized` is the better fit for the transcript
- the weaker one becomes `duplicate`

Example:

- `['电力股', '特高压'] -> equity_sector11Utilities`
- `['电力股'] -> equity_sector11Utilities_CHN`

If the transcript is clearly discussing China/A-share utilities, then:

- `equity_sector11Utilities_CHN` should keep the real signal
- `equity_sector11Utilities` should become `duplicate`

ADR / local stock rule:

- if a local/origin-market row and an ADR row both exist for the same company
- default keep the local/origin-market row
- ADR should usually become `duplicate`
- only keep ADR when it is the only usable choice or the transcript clearly points to the ADR / US-listed line

## Why Aliases Matter

Classification works much better when the model sees aliases.

Bad pattern:

- classify only from one normalized string

Better pattern:

- classify from:
  - `instrument_normalized`
  - aliases from transcript raw values

Why this helps:

- aliases give extra evidence
- aliases help recover ASR noise
- aliases help detect whether the norm is too broad or too specific

But aliases should still be secondary.

They are supporting evidence, not the main anchor.

## Trust Hierarchy

The intended trust order is:

1. `instrument_normalized`
2. aliases
3. fallback financial common knowledge

This means:

- if Step 1 produced a good norm, Step 2 should mostly preserve it
- if Step 1 produced a weak or clearly wrong norm, aliases may help recover it
- if neither is enough, Step 2 may use common financial knowledge conservatively

## Typical Error Split

When something looks wrong, it is useful to decide whether it is a Step 1 problem or a Step 2 problem.

Usually it is a Step 1 problem if:

- a generic concept became a specific branded product
- a country was injected too early
- a benchmark identity was invented
- obvious ASR noise was preserved as a fake new concept

Usually it is a Step 2 problem if:

- the norm is fine, but the taxonomy tag is wrong
- the model falls back to `unclassified` even though a clear tag exists
- a specific existing label like `cmd_soybean` is missed and replaced with `cmd_other`
- a sector / factor / benchmark choice is inconsistent with the taxonomy rules

## Summary

Short version:

- Step 1 is semantic extraction and normalization
- Step 2 is taxonomy tagging
- Step 3 is transcript-grounded signal extraction on the tagged target

If Step 1 becomes too aggressive, Step 2 will look wrong even when the schema is fine.

If Step 1 stays conservative and clean, Step 2 becomes much easier and more stable.
If Step 3 stays anchored on `instrument_normalized` while using `instrument` only as locator text, signal extraction becomes more consistent and easier to audit.
