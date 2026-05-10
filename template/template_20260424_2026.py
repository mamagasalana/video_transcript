from __future__ import annotations
from pydantic import BaseModel, Field
from enum import Enum
from typing import Dict, List, Optional, Literal, Annotated

# its good to have an introduction that explain the background of this template
"""
1. 基于deepseek-reasoner无法输出稳定结果,咨询了deepseek-deepthink所得建议
2. 添加了主持人风格
2026-03-14: outputs/model_output/2026_03_08_signal_0_deepseek-reasoner/20251118.json fail to recognize equity_benchmark_USA as open_sell
"""
field_id_deepseek = Field(..., ge=1, description="从1开始递增的分段编号")

Intent = Literal["open_buy", "open_sell", "close_buy", "close_sell", "unclear", "invalid", "duplicate"]

class TradingSignalBase(BaseModel):
    instrument: List[str] = Field(..., min_length=1,
        description=(
            "必须精确复制 Helper 中对应项的 instrument 列表，用于和 helper 建立一一对应关系。"
            "列表中的每一项可以是该 helper item 在 Transcript 中可能出现的别名、写法、相关提法，"
            "或同一聚合观察对象下的代表性说法。"
            "该字段的作用是帮助模型在 Transcript 中定位当前 instrument_normalized，"
            "而不是要求模型对列表中的每个元素分别单独输出 signal。"
            "不得新增、删减、改写、翻译或重新排序；输出时应直接沿用 Helper 原始列表。"
        ),
    )
    instrument_normalized: str = Field(..., min_length=1,
        description=(
            "必须精确复制 Helper 中对应项的 instrument_normalized 字段；"
            "该字段是当前 helper item 的目标标识：既可以是单一标的的标准化名称，也可以是聚合后的分类目标/观察目标，"
            "例如 cmd_gold / fx_usd / equity_benchmark_CHN。"
            "第三步的核心判断对象是 instrument_normalized；instrument 列表只是帮助在 Transcript 中定位该目标。"
            "若 Helper 提供了该目标标识，则直接沿用，不得自行重写。"
        ),
    )
    intent: Intent = Field(...,
        description=(
            "交易意图枚举，仅可填写：open_buy / open_sell / close_buy / close_sell / unclear / invalid / duplicate。\n\n"
            "**open_buy**：主持人对该标的给出偏多、偏买入、偏布局的建议，或给出能支撑做多的理由与判断。\n"
            "  常见偏多证据包括：价格被低估、基本面改善、技术面买入信号、资金流入、政策支持等，并暗示或建议买入/布局。\n\n"
            "**open_sell**：与 open_buy 相反；主持人对该标的给出偏空、偏卖出、偏做空的建议，或给出能支撑做空的理由与判断。\n"
            "  常见偏空证据包括：估值过高（如市销率、市盈率远超历史均值）、技术面破位（如跌破关键支撑）、大户/主力出货、\n"
            "  利多出尽、资金流出、风险积聚（如债务问题、政策风险）等。\n"
            "  注意：即使主持人没有直接说“卖出”，但通过上述证据暗示市场将下跌、应离场或避免买入，也应判为 open_sell。\n\n"
            "**close_buy**：主持人对多头方向提示风险，提醒不要追、不要继续加码、应减仓/止盈/先观望，或明确否定继续做多。\n"
            "  示例：“虽然长期看好，但短期涨幅过大，不建议追高”、“估值已高，应考虑减仓”。\n\n"
            "**close_sell**：与 close_buy 相反；主持人对空头方向提示风险，提醒回补、离场、不要继续做空。\n"
            "  示例：“虽然趋势向下，但短期反弹可能强劲，空单应回补”、“下跌空间有限，不宜继续做空”。\n\n"
            "**unclear**：主持人只是提到该标的、解释背景、陈述价格变化、做类比、做举例，或证据不足以形成可执行建议。\n"
            "  常见误判：单纯说“今天油价大跌”而没有给出看空理由，应判为 unclear；若接着说“因为库存增加、需求疲软，后市仍看跌”，则应判为 open_sell。\n\n"
            "**invalid**：Helper 给出的对象并非可交易标的，或在当前语境下属于错误/无效标的，例如 CPI、GDP、经济数据等。"
            "另外，若某个 helper item 虽然本身可交易，但其 instrument_normalized 与当前 Transcript 语境明显不匹配，"
            "且又不存在另一条更合适、可与之形成 duplicate 关系的 helper item，则也可判为 invalid。\n\n"
            "**duplicate**：当前 helper item 的 instrument 与另一个 helper item 的 instrument 在本段 Transcript 中明显重叠，"
            "或显然是在指向同一讨论目标；而当前 item 只是重复、较弱、较不贴切或较次要的解释路径。"
            "此时应保留更贴切的那一项给出真实交易信号，当前 item 标为 duplicate，而不是勉强给 open/close/unclear。\n\n"
            "**重要区分**：\n"
            "- 陈述事实 vs 交易建议：如果主持人只是描述价格涨跌、列举数据，但没有对这些数据赋予方向性判断或操作导向，则判为 unclear。\n"
            "- 证据的强度：单一但明确的偏空/偏多理由即可支撑 open_sell 或 open_buy，无需多个理由。\n"
            "- 讽刺语气：注意识别反话，例如表面说“太好了，可以抄底了”，但上下文显示市场崩溃，实际是讽刺看多，应结合整体语气判断真实意图。\n\n"
            "**主持人风格提示**：\n"
            "- 主持人杨世光偏好“买低卖高”的逆向布局，常通过宏观数据、资金流向、技术形态等分析来暗示方向，而不是直接喊单。\n"
            "- 当主持人反复强调风险、泡沫、大户离场时，即使没有明确说“卖出”，也往往意味着看空（open_sell），因为他认为当前不适合持有或应该做空。\n"
            "- 当主持人提示“反弹很艰辛”、“做空很难抱”时，通常是在提醒风险，可能更接近 close_sell（对空头提示风险）或 unclear（如果没有进一步建议），需结合上下文判断。"
        ),
    )
    evidence: List[str] = Field(
        default_factory=list,
        description=(
            "支持 intent 的原文证据列表。每一项都必须是 Transcript 中真实出现过的连续原文子串，"
            "必须逐字复制，不得改写、翻译、润色、合并自多处内容，也不得凭空生成。"
            "优先提取完整句子；若句子过长，可提取足以表达含义的连续分句。"
        ),
    )
    summary: List[str] = Field(
        default_factory=list,
        description=(
            "对 evidence 的解释列表。summary[i] 必须说明 evidence[i] 为什么支持当前 intent，"
            "只能基于对应证据和 Transcript 已明确表达的内容进行说明，不得引入 Transcript 之外的新事实、常识或推断。"
            "当 evidence 为空时，summary 也应为空。"
        ),
    )

class TradingSignal(BaseModel):
    signals: List[TradingSignalBase] = Field(default_factory=list)


SCHEMA_SIGNAL_EXTRACT = r"""
SCHEMA_VERSION=2026-05-10T00:00:00
你是一个中文(普通话)经验丰富的财经分析师，专门分析《金钱报》主持人(杨世光) 的交易信号。

背景：
上游系统在第三步之前，已经先完成前两步处理：
- 第一步：从完整 Transcript 中抽取原始标的提法，并得到原始的 instrument / instrument_normalized
- 第二步：基于第一步结果做分类，把原始提法进一步归并到最终的分类目标

因此，第三步收到的 Helper 并不是“第一步原样输出”，而是前两步处理后的 helper item。每个 helper item 提供：
- instrument：来自 Transcript 的原始提法、别名、写法或相关触发词；这些词是为了帮助你回到原文定位讨论对象
- instrument_normalized：经过前两步处理后，最终归并出来的目标标识；它代表第三步真正要判断交易信号的目标

换句话说：
- instrument 更接近“原文里怎么说”
- instrument_normalized 更接近“前两步最后认为它应归到哪个目标”

因此，在第三步里：
- instrument_normalized 是当前交易信号判断的核心目标，具有最高信任度
- instrument 列表只是帮助你回到 Transcript 中定位这个 instrument_normalized 在原文里的对应说法
- instrument 列表可能包含 ASR 瑕疵、相关提法、或同一聚合观察对象下的代表性触发词

你的任务不是重新抽取 instrument，也不是重写 helper，而是基于 Transcript 判断：
- 这个 helper item 对应的 instrument_normalized 在当前语境下是否有交易信号
- 若对同一个 helper item 的同一个 instrument_normalized 出现多个彼此不同的 intent，允许输出多条 signal
- 若不同 helper item 的 instrument 实际上在说同一件事，则可把较弱者判为 duplicate

输入:
- Transcript：完整逐字稿
- Helper：instruments JSON（已抽取好的 instrument 列表，至少包含 instrument / instrument_normalized）

目标:
基于 Transcript，对 Helper 中列出的每一个 helper item 所对应的 instrument_normalized 逐一判断其交易意图（intent）并输出交易信号。
必须覆盖 Helper 的所有 instrument：每个 helper item 至少要输出一条 signal。
第三步的核心对象是 Helper.item.instrument_normalized；Helper.instrument 列表只是帮助你在 Transcript 中定位这个目标。
允许同一个 helper item 输出多条 signal，但仅限于 Transcript 对同一个 instrument_normalized 给出了彼此不同的 intent（例如一条 open_buy，另一条 open_sell）。
  - 示例：若 helper item 为 `{'instrument': ['美国股市', '标普500', '道琼指数'], 'instrument_normalized': 'equity_benchmark_USA'}`，
    Transcript 同时表达“标普500要小心/可考虑卖出”以及“道琼指数相对抗跌/可留意布局”，
    则允许对同一个 helper item 输出两条 signal；两条 signal 的 instrument 与 instrument_normalized 完全相同，
    但 intent / evidence / summary 不同。
  - 若只是同一 helper item 在 Transcript 多处重复支持同一个 intent（例如都是 open_buy），则应合并为一条 signal，而不是重复输出多条同方向 signal。

**关键提示（必须遵守）：**
1. **主持人风格**：杨世光主持人偏向“布局型”、“买低卖高”、“不要追价”的风格。他常通过宏观数据、估值、资金流向、技术形态等分析来暗示方向，而不是直接喊单。因此，即使没有明确说“买入”或“卖出”，只要给出支撑做多/做空的理由，也应判为 open_buy/open_sell。
2. **陈述 vs 建议**：单纯描述事实、涨跌、现象，不等于交易建议。只有当主持人进一步给出支撑理由、风险判断、布局倾向或操作导向时，才可判为 open/close 信号。例如：
   - “今天油价大跌” → 通常判为 unclear。
   - “今天油价大跌，因为库存增加、需求疲软，后市仍看跌” → 判为 open_sell。
3. **举例检测**：如果标的仅用于举例说明其他概念（如解释宏观经济），则 intent 应优先判为 unclear。
4. **讽刺语气**：注意识别反话，例如表面说“太好了，可以抄底了”，但上下文显示市场崩溃，实际是讽刺看多，应结合整体语气判断真实意图。
5. **风险提示与交易否定（关键区分）**：
   主持人常在给出方向后提及风险。必须严格区分“常规谨慎提醒”与“对当前操作的明确否定”：
   - **常规谨慎提醒**：若主持人仅说“注意风险”、“要观察”、“位阶不低”，但未直接否定立刻买入，且前文已给出方向性理由（如“有机会”、“可能转强”），这属于其表达习惯，**不能**抵消方向。此时应依据方向性理由判为 open_buy 或 open_sell。
     - *示例*：“大豆短线右转强，从历史的经验做观察，是有机会的，注意风险。” → **open_buy**（方向理由成立，风险提示仅是一般提醒）。
   - **对当前操作的明确否定**：若主持人明确表达“不要追”、“现在不适合”、“建议观望”、“等拉回再买”、“应维持高现金水位”、“寻找放空机会”等，这是对**当前介入动作**的直接叫停。此时应判为 close_buy（否定当前做多）或 close_sell（否定当前做空），即使主持人同时声称“长期看好”。
     - *示例*：“我们对陆股仍然是长期看好，但尽量要保持高现金水位，寻找一些放空的机会跟标的” → **close_buy**（长期看好但被当前防御/做空部署覆盖，明确否定当下做多）。
6. **含蓄表达**：当主持人反复强调风险、泡沫、大户离场、估值过高，且没有给出相反的方向性理由时，即使没有直接说“卖出”，也往往意味着看空（open_sell），因为他认为当前不适合持有或应该做空。反之亦然。但要结合第5条区分是“否定当前操作”还是“仅作提醒”。
7. **重复 Helper 处理**：duplicate 只用于不同 helper item 之间。若多个 helper item 在当前 Transcript 中明显对应同一讨论目标，而其中某一项只是重复、较弱、较不贴切、过度细化、或只是另一项的替代解释路径，则应把较次要者判为 duplicate。不要为了“每个 helper 都要有结果”而给重复项硬判 open/close/unclear。判为 duplicate 时，仍应尽量提供最少量但足够的 evidence，并在 summary 中简要说明为什么另一条 helper item 更贴切。
8. **ADR / 本地股票重复优先规则**：若同一公司同时出现本地上市版本与 ADR / 美股版本的 helper item，duplicate 默认优先保留本地上市/原属市场项，ADR / 美股项判 duplicate。若 Transcript 又明确指向某个更具体的 ADR / 美股版本，则可反转该默认优先级。
9. **同一 Helper 多信号规则**：若同一个 helper item 在 Transcript 中被赋予多个彼此不同的 intent，则允许为同一个 helper item 输出多条 signal。此时多条 signal 的 instrument 与 instrument_normalized 都保持完全相同，差异只体现在 intent、evidence、summary 上；不要为了区分不同证据来源而改写 instrument 或拆分出新的 instrument。若只是同一 intent 被多处重复支持，则应合并为一条 signal。
10. **unclear / invalid 互斥规则**：对同一个 helper item 而言：
   - 若已经形成任何更明确的判断（open_buy / open_sell / close_buy / close_sell / duplicate / invalid），则不应再额外输出 unclear。
   - 若已经判为 invalid，则不应再同时输出 open_buy / open_sell / close_buy / close_sell / unclear；invalid 只能作为该 helper item 的错误/失效兜底结果。
   - unclear 只用于“没有形成任何更明确判断”的兜底场景。

核心约束（必须遵守）：
1) 覆盖性：signals 中必须覆盖 Helper 的全部 helper item；每个 helper item 至少对应一条 signal。
2) 不新增标的：不得在 signals 中输出 Helper 之外的任何 instrument；不得自行补充未出现于 Helper 的标的。
3) Helper 优先：signal 中的 instrument / instrument_normalized 必须直接沿用 Helper 对应字段，不得改写。
4) 定位规则：Helper.instrument 是该 helper item 的触发词列表；可以是别名、写法、相关提法或同一聚合观察对象下的代表性说法。它的作用是帮助你在 Transcript 中定位该 instrument_normalized；只要 Transcript 明确提到其中任一项，都可视为命中该 helper item。
5) 以 Transcript 为准：所有 intent、evidence、summary 判断只能来自 Transcript 明确表达的内容；不得引入 Transcript 之外的新信息。
6) 证据原文：evidence 的每一项都必须是 Transcript 中真实存在的连续原文子串，必须逐字复制，不得改写、拼接或凭空生成。
7) 解释约束：summary 的每一项都要解释对应 evidence 为什么支持 intent；summary 可以概括，但不得引入 Transcript 之外的事实。
8) 配对关系：summary 与 evidence 一一对应；若有 2 条 evidence，则必须有 2 条 summary。若 evidence 为空，则 summary 也应为空。
9) 单条 signal 的聚焦原则：每一条 signal 必须只表达一个清晰的交易意图；如果同一个 helper item 对同一个 instrument_normalized 出现不同 intent，则应拆成多条 signal，而不是混在同一条里。
10) 合并原则：若同一个 helper item 在 Transcript 多处重复支持同一方向，可把相关证据合并到同一条 signal 中。
11) duplicate 判定重心：当多个 helper item 的 instrument 列表有重叠、近似或明显指向同一讨论对象时，首先应判断这些 instrument 是否在说同一件事；若是，再比较哪个 instrument_normalized 更贴切当前 Transcript 语境。较弱、较泛、较偏、或较不贴切的 item 判为 duplicate。也就是说，duplicate 先看 instrument 是否重叠，再看 instrument_normalized 哪个更贴切。
   - 示例：若同时存在 `{'instrument': ['电力股', '特高压'], 'instrument_normalized': 'equity_sector11Utilities'}`
     与 `{'instrument': ['电力股'], 'instrument_normalized': 'equity_sector11Utilities_CHN'}`，
     两条 helper item 的 instrument 明显重叠，因为都命中“电力股”。
     此时先判断它们是不是在说同一件事；若 Transcript 语境明显是在讲大陆/A股/中国市场中的电力股，
     则 `equity_sector11Utilities_CHN` 更贴切，应保留该项给出真实 signal，
     而较泛的 `equity_sector11Utilities` 判为 duplicate。

**intent 判定规则（详细版）：**
- **open_buy**：主持人对该标的给出偏多、偏买入、偏布局的建议，或给出能支撑做多的理由与判断。
  - 常见偏多证据：价格被低估、基本面改善、技术面买入信号（如突破关键阻力、短线转强、有望走第二波）、资金流入、政策支持、行业景气回升等。
  - 若方向性理由后仅跟随常规谨慎提醒（如“注意风险”），仍判为 open_buy。
  - 示例：“股价已跌至历史低位，但公司现金流稳健，可逢低布局。”
  - 示例：“大豆短线右转强，从历史的经验做观察，是有机会的，注意风险。” → **open_buy**。

- **open_sell**：与 open_buy 相反；主持人对该标的给出偏空、偏卖出、偏做空的建议，或给出能支撑做空的理由与判断。
  - 常见偏空证据：
    - **估值过高**：市销率、市盈率远超历史均值，或与GDP比率处于极端高位。
    - **技术面破位**：跌破关键支撑位、均线空头排列、反弹无力。
    - **资金面**：大户/主力出货、平均买单挂单萎缩、资金持续流出。
    - **基本面**：利多出尽、债务风险、政策打压、行业衰退。
    - **市场情绪**：泡沫迹象、投机过度、散户追高。
  - 注意：即使主持人没有直接说“卖出”，但通过上述证据暗示市场将下跌、应离场或避免买入，也应判为 open_sell。
  - 示例：“美股总市值与GDP比率已高于均值两个标准差，泡沫巨大，风险很高。”（暗示看空）

- **close_buy**：主持人对多头方向提示风险，并明确否定当前做多行为。包括提醒不要追、不要继续加码、应减仓/止盈/先观望、保持高现金水位、转而寻找放空机会等。
  - 关键特征：存在对当前介入的战术叫停，即使仍称“长期看好”。
  - 示例：“虽然长期看好，但短期涨幅过大，不建议追高”、“估值已高，应考虑减仓”。
  - 示例：“我们对陆股仍然是长期看好，但尽量要保持高现金水位，寻找一些放空的机会跟标的。” → **close_buy**。

- **close_sell**：与 close_buy 相反；主持人对空头方向提示风险，并明确否定当前做空行为，提醒回补、离场、不要继续做空。
  - 示例：“虽然趋势向下，但短期反弹可能强劲，空单应回补”、“下跌空间有限，不宜继续做空”。

- **unclear**：主持人只是提到该标的、解释背景、陈述价格变化、做类比、做举例，或证据不足以形成可执行建议。
  - 常见情况：仅提及价格、无方向性判断；用于举例说明其他事物；陈述现象后未给出操作导向。
  - 注意：如果主持人给出了方向性倾向（如“有机会”），即使加了“要观察”，但只要没有明确否定当前操作，就不应归为 unclear，而应按其倾向判为 open_buy/open_sell。

- **invalid**：Helper 给出的对象并非可交易标的，或在当前语境下属于错误/无效标的，例如 CPI、GDP、经济数据、宏观指标等。
  - 也可用于：该 helper item 一般而言可交易，但它在当前 Transcript 中明显是错误映射/错误目标，且又不存在另一条更合适的 helper item 可供它判为 duplicate。
  - invalid 是兜底结果：同一个 helper item 一旦判为 invalid，就不应再同时输出 open_buy / open_sell / close_buy / close_sell / unclear。

- **duplicate**：只用于不同 helper item 之间。当前 helper item 的 instrument 与别的 helper item 的 instrument 在本段 Transcript 中明显重叠、近似，或显然是在说同一件事、同一家公司、同一聚合市场观点，而当前 item 只是重复、较弱、较不贴切、或较次要版本。
  - 常见情况：
    - 同一公司同时出现本地上市版本与 ADR / 美股版本，默认优先保留本地上市/原属市场版本；
    - 同一主题同时出现泛化标签与更贴切的国家/市场定向标签；
    - 同一讨论目标被上游重复抽成两条 helper，而其中一条只是较弱解释。
  - duplicate 的判断顺序是：先看 instrument 是否明显重叠或在说同一件事，再看哪个 instrument_normalized 明显更贴切当前语境；若属于同公司的 ADR / 本地股票重复，默认优先保留本地上市/原属市场版本，把 ADR / 美股版本判为 duplicate；较弱者判 duplicate。
  - duplicate 最好仍保留最少量但足够的 evidence，以显示它为什么与另一条 helper item 重叠，以及为什么它是较弱解释。
  - duplicate 不是 invalid：它不表示该 helper 天然不可交易，而是表示在当前 Transcript 语境下，它应被另一条 helper 覆盖。

**重要区分（补充说明）：**
- **单一理由即可**：只要主持人给出单一但清晰、可执行、带方向的支持理由，就可以判为 open_buy 或 open_sell，不要求必须有多个理由。
- **证据的强度**：证据不必是绝对确定，只要主持人表达出倾向性（如“可能”、“恐怕”、“要小心”），也应结合上下文判断。
- **上下文优先**：若某段话表面中性，但结合前后文明显指向操作方向，应以整体意图为准。
- **聚合 helper 的多信号**：若 helper.instrument 包含多个触发词，而 Transcript 对应到同一个 instrument_normalized 给出了不同 intent，则应拆成多条 signal，但每条 signal 仍沿用同一个 helper 的 instrument 与 instrument_normalized；不要因为证据来自不同触发词就改写输出结构。若最终 intent 相同，则应合并成一条 signal。
- **unclear 的地位**：unclear 是兜底，不是并列补充项。只要同一个 helper item 已经能形成更明确的 open/close/duplicate/invalid 判断，就不应再额外输出 unclear。
- **invalid 的地位**：invalid 也是兜底，不是并列补充项。只要同一个 helper item 已经判为 invalid，就不应再并列输出任何方向性 signal 或 unclear。

注意：所有判断必须严格基于 Transcript，不得添加个人猜测。
"""

SCHEMA_INSTRUMENT_RULES_EXTRACT = r"""
SCHEMA_VERSION=2026-04-24T00:00:00
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

=== 重要补充：不得以“示例/非投资建议”等理由排除 ===
- 即使某个标的在 Transcript 中仅作为例子、比喻、反问、否定性陈述出现，只要它满足上述抽取条件（显式或隐含），就必须抽取，不得自行排除。
- 分析过程中严禁输出类似“只是举例，不抽取”的判断；必须把所有符合条件的 instrument 全部输出。

=== 执行规则 ===
1) 完全匹配原文：instrument 必须是 Transcript 连续子串，保持原格式（不改写）。
2) 去重规则（修改后）：
   - 仅当 instrument 原文完全相同（字符串完全一致）时，才视为重复并只输出一次。
   - 若 instrument 原文不同（即使 instrument_normalized 相同，例如“S&P500”和“美国股市”），必须分别保留为独立条目，不可合并丢弃。
   - 示例：“美国股市”和“S&P500”原文不同，各输出一条记录。
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
  # EQUITY
  # ----------------
  'equity_benchmark' ,
  'equity_volatility' ,

  # equity_factor{Factor}
  'equity_factorValue' ,
  'equity_factorMomentum' ,
  'equity_factorQuality' ,
  'equity_factorLowVolatility' ,
  'equity_factorDividend' ,
  'equity_factorBeta' ,
  'equity_factorCyclical' ,
  'equity_factorLiquidity' ,
  'equity_factorSize' ,
  'equity_factorGrowth' ,
  'equity_factorDefensive' ,    # 新增：防御型风格（低风险、稳定、高股息等）
  'equity_factorUndefined' ,    # 新增：明确是风格因子但不在上述列表中的标的

  # equity_cap{Bucket}
  'equity_capmega' ,
  'equity_caplarge' ,
  'equity_capmid' ,
  'equity_capsmall' ,

  # ============================================================
  # equity_sector{GICS 一级 / 二级行业组}
  # 规则：能明确落到二级行业组时优先用二级；否则回退到一级行业
  # ============================================================
  # 10 — 能源
  'equity_sector11Energy',                    # GICS 11: Energy 能源

  # 15 — 材料
  'equity_sector11Materials',                 # GICS 11: Materials 材料

  # 20 — 工业
  'equity_sector11Industrials',               # GICS 11: Industrials 工业
  # 二级 (3个)
  'equity_sector25CapitalGoods',              # GICS 25: 2010 Capital Goods 资本品
  'equity_sector25CommercialProfessionalServices', # GICS 25: 2020 Commercial & Professional Services 商业和专业服务
  'equity_sector25Transportation',            # GICS 25: 2030 Transportation 运输

  # 25 — 非必需消费品
  'equity_sector11ConsumerDiscretionary',     # GICS 11: Consumer Discretionary 非必需消费品
  # 二级 (4个)
  'equity_sector25AutomobilesComponents',     # GICS 25: 2510 Automobiles & Components 汽车与零部件
  'equity_sector25ConsumerDurablesApparel',   # GICS 25: 2520 Consumer Durables & Apparel 耐用消费品与服装
  'equity_sector25ConsumerServices',          # GICS 25: 2530 Consumer Services 消费者服务
  'equity_sector25ConsumerDiscretionaryDistributionRetail', # GICS 25: 2550 Consumer Discretionary Distribution & Retail 非必需消费品分销与零售

  # 30 — 必需消费品
  'equity_sector11ConsumerStaples',           # GICS 11: Consumer Staples 必需消费品
  # 二级 (3个)
  'equity_sector25ConsumerStaplesDistributionRetail', # GICS 25: 3010 Consumer Staples Distribution & Retail 必需消费品分销与零售
  'equity_sector25FoodBeverageTobacco',       # GICS 25: 3020 Food, Beverage & Tobacco 食品、饮料与烟草
  'equity_sector25HouseholdPersonalProducts', # GICS 25: 3030 Household & Personal Products 家庭与个人用品

  # 35 — 医疗保健
  'equity_sector11HealthCare',                # GICS 11: Health Care 医疗保健
  # 二级 (2个)
  'equity_sector25HealthCareEquipmentServices', # GICS 25: 3510 Health Care Equipment & Services 医疗保健设备与服务
  'equity_sector25PharmaceuticalsBiotechnologyLifeSciences', # GICS 25: 3520 Pharmaceuticals, Biotechnology & Life Sciences 制药、生物科技与生命科学

  # 40 — 金融
  'equity_sector11Financials',                # GICS 11: Financials 金融
  # 二级 (3个)
  'equity_sector25Banks',                     # GICS 25: 4010 Banks 银行
  'equity_sector25FinancialServices',         # GICS 25: 4020 Financial Services 金融服务（含资本市场、消费金融等）
  'equity_sector25Insurance',                 # GICS 25: 4030 Insurance 保险

  # 45 — 信息技术
  'equity_sector11InformationTechnology',     # GICS 11: Information Technology 信息技术
  # 二级 (3个)
  'equity_sector25SoftwareServices',          # GICS 25: 4510 Software & Services 软件与服务
  'equity_sector25TechnologyHardwareEquipment', # GICS 25: 4520 Technology Hardware & Equipment 技术硬件与设备
  'equity_sector25SemiconductorsSemiconductorEquipment', # GICS 25: 4530 Semiconductors & Semiconductor Equipment 半导体与半导体设备

  # 50 — 通信服务
  'equity_sector11CommunicationServices',     # GICS 11: Communication Services 通信服务
  # 二级 (2个)
  'equity_sector25TelecommunicationServices', # GICS 25: 5010 Telecommunication Services 电信服务
  'equity_sector25MediaEntertainment',        # GICS 25: 5020 Media & Entertainment 媒体与娱乐

  # 55 — 公用事业
  'equity_sector11Utilities',                 # GICS 11: Utilities 公用事业

  # 60 — 房地产
  'equity_sector11RealEstate',                # GICS 11: Real Estate 房地产
  # 二级 (2个)
  'equity_sector25EquityREITs',               # GICS 25: 6010 Equity Real Estate Investment Trusts (REITs) 权益型房地产投资信托
  'equity_sector25RealEstateManagementDevelopment', # GICS 25: 6020 Real Estate Management & Development 房地产管理与开发

  # 兜底
  'equity_sectorUndefined',                   # 明确属于行业/概念板块，但连一级行业都无法自信映射时使用
  'equity_stock',
  # ----------------'
  # FX (single-currency groups plus basket/index exposures)'
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
  'fx_basket',
  'fx_other',


  # ----------------'
  # COMMODITY (buckets; ignore spot/future/expiry; brent+wti -> cmd_oil)'
  # Starter set (expand freely)'
  # ----------------'
  'cmd_oil',
  'cmd_natgas',
  'cmd_gold',
  'cmd_silver',
  'cmd_platinum',
  'cmd_palladium',
  'cmd_copper',
  'cmd_lead',
  'cmd_zinc',
  'cmd_nickel',
  'cmd_aluminum',
  'cmd_ironore',
  'cmd_coal',
  'cmd_carbon',
  'cmd_corn',
  'cmd_wheat',
  'cmd_oat',
  'cmd_rice',
  'cmd_soybean',
  'cmd_soymeal',
  'cmd_soyoil',
  'cmd_cotton',
  'cmd_sugar',
  'cmd_coffee',
  'cmd_cocoa',
  'cmd_orangejuice',
  'cmd_cattle',
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
    raw: str = Field(..., min_length=1, description="输入的 instrument_normalized，作为当前分类对象的可追溯主键。")

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
        description="国家代码 (ISO3) 或区域代码（如 GLOBAL / ASIAPAC / EUROPE / LATAM / EMERGING 等）。",
    )

    ticker: str = Field(
        ...,
        description="股票代码（仅当underlying_assets为equity_stock时填写）。",
    )

class InstrumentTag(BaseModel):
    instruments: List[InstrumentTagBase] = Field(default_factory=list)

SCHEMA_INSTRUMENT_TAG_CLASSIFICATION = r"""
SCHEMA_VERSION=2026-05-09T00:00:00
你是一个严格的分类系统。将每个输入资产映射到预定义敞口标签。

背景：
上游系统从完整的对话转录中抽取了 instrument_normalized，并附带了 aliases（转录中真实出现的词汇）。
第一步（提取）拥有完整的语境，因此 instrument_normalized 是结合语境标准化后的结果，具有最高信任度。
aliases 是原始转录片段，可能包含 ASR 瑕疵。第二步（分类）必须首先信任 instrument_normalized，仅在高门槛条件下才用 aliases 修正。

输入：JSON 对象列表，每个包含 instrument_normalized 和 aliases。
输出：仅输出合法 JSON。instruments 数组与输入等长，每项含 raw, underlying_assets, country, ticker。

=== 字段规则 ===
1) raw — 严格等于 instrument_normalized。
2) underlying_assets — 非空列表，仅含允许的标签。不确定时输出 ["unclassified"]，绝不混用。
3) country —
   - 底层含 cmd_* / crypto_* → 强制 "GLOBAL"。
   - 底层含单一货币 fx_*（不含 fx_basket）→ 强制 "GLOBAL"。
   - 底层含 fx_basket：country 表示该货币篮子/货币指数的地域范围；单一区域用区域代码，跨区域且无明确主区域时用 "GLOBAL"。
   - 底层含 gov_*：原始字符串明确主权/发行方 → ISO3，否则 "GLOBAL"。
   - 底层含 credit_*：原始字符串明确国家/区域发行人 → ISO3，否则 "GLOBAL"。
   - 底层含非个股权益标签（benchmark/sector/factor/cap/volatility）：
      · 若 norm 或 aliases 含明确单一国家限定词 → ISO3（如 USA, CHN, JPN）。
      · 若含区域限定词 → 对应区域代码（见下文区域代码表及映射提示）。
      · 若底层为 equity_volatility，country 表示其所对应股票市场的暴露地域，而非产品上市地；例如 VIX / VXX / UVXY → USA，VHSI / VHSCEI → HKG。
      · 若属于成熟且广泛认知的国家级市场基准、市场基准简称，或其直接 ETF 代理（如 S&P 500, NASDAQ 100, Dow Jones, Nikkei 225, Hang Seng, 沪深300, SPY, IVV, VOO, QQQ），即使字符串未显式写出国家，也允许基于金融常识推断其对应 country。
      · 若属于成熟且广泛认知的单一国家超大市值龙头篮子/巨头组合（如 Magnificent 7 / 美股七巨头 / 美国科技七巨头 / FAANG），即使字符串未显式写出国家，也允许基于金融常识推断其对应 country（通常为 USA）。
      · 以上皆无 → "GLOBAL"。不得仅因 instrument_normalized / aliases 使用中文、普通话或其他本地语言，就把泛行业词、泛市场词或泛资产词默认推断为该语言对应国家；例如“电力”“半导体”“消费”“银行”不能仅因是中文就默认判为 CHN。
   - 底层含 equity_stock：优先按后缀硬规则映射；若明确为 ADR / DR 等跨境存托凭证，country 填发行主体原属国家/主要业务归属，而非存托凭证上市地；其余无后缀则按金融常识推断主要上市地 ISO3；推断不出则 "GLOBAL"。
4) ticker —
   - 无 equity_stock → ""。
   - 有 equity_stock：
       * raw 中显式 ticker 且后缀属合法列表(.T/.TW/.HK/.SS/.SZ/.KS/.KQ/.AS/.L/.PA/.DE/.SW/.TO) → 直接复制。
       * 若 raw 或 aliases 出现上海股票后缀 ".SH"，应规范修正为 ".SS"；深圳维持 ".SZ"。
       * 若 norm 中显式包含无后缀股票代码，且该代码是清晰可识别的美国上市股票/ADR 代码，可直接保留该 ticker；若是美国本土股票则 country="USA"，若是 ADR / DR 则 country 仍填发行主体原属国家；不要求强行补后缀。
       * 后缀非法（如 ".JP"）但 aliases / 金融常识足以强烈指明市场 → 修正为标准后缀（如 "8301.JP" + 日本银行 → "8301.T", country="JPN"；加拿大主板股票可修正为 .TO）。
       * 若后缀不在已知列表但仍可从 aliases / 公司身份 / 上市地常识明确推断主要市场，则允许直接规范成你体系中的标准本地后缀；不要机械保留错误后缀。
       * 若后缀不在已知列表且无法从别名/上下文明确推断 → 保留原始字符串，country="GLOBAL"。
       * 无显式 ticker → 推断最主流本地上市代码（见下文 ticker 推断优先规则）；推断不出则 ""。

=== 核心信任层级 ===
1. instrument_normalized 优先信任。
2. aliases 用于辅助。推翻 norm 需满足：aliases 极高置信、一致、无歧义，且 norm 明显不合理。
3. MSCI 代理还原：若 norm 含 "Index" 而 aliases 全部是非指数词汇（板块/行业/因子/区域/具体公司名），则可忽略 Index 外壳，按 aliases 实质类型分类；但该规则主要用于在 benchmark / sector / factor / cap 之间调整，不应轻易把指数 norm 降格为单一股票。若 aliases 本身含指数含义则保留 benchmark。
   示例：
   - norm="MSCI China Consumer Staples Index", aliases=["白酒","白酒消费类股"] → 行业 → equity_sector25FoodBeverageTobacco, country="CHN"
   - norm="MSCI China Value Index", aliases=["价值因子","价值股"] → 因子 → equity_factorValue, country="CHN"
   - norm="MSCI AC Asia Pacific Index", aliases=["亚洲股市","亚太股市"] → 区域基准 → equity_benchmark, country="ASIAPAC"
   - norm="MSCI China Consumer Staples Index", aliases=["贵州茅台","五粮液"] → 仍优先视为中国消费必需品相关的板块/基准敞口，不应仅凭成分股别名直接改判为 equity_stock
   - norm="BSE 50 Index", aliases=["北创50"] → BSE=Beijing Stock Exchange，norm 自身即指数，aliases 为 ASR 偏差 → equity_benchmark, country="CHN"
4. 泛行业词默认中性：对于“电力、银行、地产、半导体、消费、科技、能源”等泛行业/板块词，若 norm 与 aliases 都不含明确国家或区域限定词，不得仅因语言是中文而输出 CHN，默认 country="GLOBAL"。
   示例：
   - norm="电力", aliases=["电力"] → equity_sector11Utilities, country="GLOBAL"
   - norm="银行", aliases=["银行"] → equity_sector25Banks, country="GLOBAL"
   - norm="半导体", aliases=["半导体"] → 若仅能确定为行业词，则优先行业标签，country="GLOBAL"

=== 区域代码表及映射提示 ===
单一国家：使用 ISO 3166-1 alpha-3（如 USA, CHN, JPN, GBR 等）。
区域代码及对应的常见中文/英文关键词：
  GLOBAL      全球/全世界/全球市场/多区域/all-country
  DEVELOPED   发达市场/已发展市场
  EMERGING    新兴市场
  FRONTIER    前沿市场
  AMERICAS    美洲
  NORTHAM     北美
  LATAM       拉丁美洲/拉美/南美
  EUROPE      欧洲/欧股/泛欧
  MENA        中东与北非/中东
  AFRICA      非洲
  ASIAPAC     亚太/亚洲/亚洲市场/亚太地区/亚洲股市（默认）
  ASIAPACEXJP 亚太（除日本）/亚洲（除日本）
  ASIAPACDEV  亚太发达市场
  ASIAPACEM   亚太新兴市场
若 aliases 仅模糊提及“亚洲”或“亚太”，默认使用 ASIAPAC；明确提到“除日本”时才使用 ASIAPACEXJP；其余区域代码按需匹配。

=== 分类决策树 ===

【EQUITY TICKER SUFFIX → COUNTRY 硬规则】
.T→JPN  .TW→TWN  .HK→HKG  .SS/.SZ→CHN  .KS/.KQ→KOR
.AS→NLD  .L→GBR  .PA→FRA  .DE→DEU  .SW→CHE  .TO→CAN

【TICKER 推断优先规则】
- 下列 ticker 后缀、交易所示例与股票样例仅用于说明规范化方式，不构成穷举列表。
- 不得因为某个国家、交易所或后缀没有在示例中出现，就机械地认为该市场“不支持”或一律输出空 ticker。
- 只要能够基于 instrument_normalized、aliases 与金融常识，高置信识别公司身份及其主要本地上市地，就应主动输出其最常用、最标准的本地上市代码格式。
- 对于明显错误、缺失或非标准的 ticker 后缀，应根据主要上市市场主动修正为标准格式，而不是机械保留原样。
- 只有在公司身份、主要上市地或标准 ticker 格式无法高置信判断时，才输出 ticker=""。
- 优先选择主要本地上市代码（非 ADR），除非 norm 或 aliases 明确提到“ADR”“美股”“纳斯达克”“纽交所上市”等。
- 若同一公司同时存在 ADR / 美股代码与本地主要上市代码，默认优先选择本地主要上市代码（非 ADR）；若 aliases 明确提到“港股”则选 .HK，若明确提到“美股”或 “ADR” 才选对应美国代码。
- 若最终选择的是 ADR / DR 代码，ticker 可保留该美国存托凭证代码，但 country 仍填写发行主体原属国家/主要业务归属，不填 USA。
- 若公司为跨国企业，选择其注册地或总部所在地的主要交易所。
- 若有多个本地上市地，选择日均交易量最大的代码。
- 若 aliases / 金融常识已足以明确主要上市地，但给定 ticker 缺少标准后缀、后缀属于错误市场、或只给了本地 share class 形式，允许你主动补齐并修正为本体系标准 ticker。
- 若 norm 已显式给出无后缀美国 ticker，且公司身份清晰，可直接保留该美国代码；美国本土股票填 country="USA"，美国上市 ADR / DR 则按发行主体原属国家填写 country；例如 China Mobile (CHL) → ticker="CHL", country="CHN"。
- 中国 A 股规范：上海证券交易所统一输出 .SS，深圳证券交易所统一输出 .SZ；即使输入出现 .SH，也应修正为 .SS。
- 加拿大股票若能明确为多伦多证券交易所主上市地，优先使用 .TO 作为标准后缀；例如 Bombardier 应优先规范为相应 TSX 代码并赋 country="CAN"。

【FX 外汇】
- 货币名称/代码/同义词 → fx_*（如 USD / US Dollar / DXY → fx_usd）。
- 货币对如 USD/JPY → 同时包含 fx_usd 和 fx_jpy。
- 多货币篮子 / 货币指数 / 区域货币组合（如 Asia Dollar Index / 亚元指数 / EM FX basket）→ fx_basket，country 填其对应区域；例如 Asia Dollar Index → fx_basket, country="ASIAPAC"。
- **CNY/CNH 一体规则**：无论代码是 CNY 还是 CNH，无论 aliases 提到“在岸”“离岸”“人民币”等任何形式，统一映射为 fx_cny。
- 仅无歧义时映射具体标签；全大写短字符（≤5 个字母）非已知货币代码时，不得默认视为 equity_stock。必须先结合 norm 与 aliases 判断它是否更像商品代码、指数简称、利率/债券符号或股票 ticker；只有在存在明确公司/ticker 证据时才判为 equity_stock，否则输出更合适的资产类别，仍无法判断则 unclassified。
- 模糊货币 → fx_other。

【COMMODITY 大宗商品】
- 商品类应先在允许的 `cmd_*` 标签中寻找最具体、最直接对应的底层品种标签；只有当无法高置信匹配到任何现有具体商品标签时，才使用 cmd_other。
- 忽略现货/期货/到期日包裹层。

【GOV / RATES 政府债与利率】
- 提及期限 → gov_1M/3M/6M/1Y/2Y/3Y/5Y/7Y/10Y/20Y/30Y。
- 政府/利率但期限不清晰 → gov_other。
- TIPS + 期限 → gov_tips5Y/10Y/30Y；TIPS 期限不清晰 → gov_tipsother。

【RATES 非政府利率】
- 通胀互换/盈亏平衡风格 → rates_inflationswap。
- 其他非主权利率衍生品/基准 → rates_other。

【CREDIT & SPREAD 信用与利差】
- IG → credit_ig  /  HY → credit_hy  /  EM credit → credit_em
- CDS 指数(CDX/iTraxx) → credit_cds
- MBS/CMBS → credit_mbs  /  ABS → credit_abs
- 商业票据 → credit_cp
- 其余公司债/债券篮/债券指数 → credit_other
- country 同样适用区域代码表：如“欧洲高收益债”→ credit_hy, EUROPE；“亚洲投资级债”→ credit_ig, ASIAPAC；不明确则 GLOBAL。

【EQUITY 权益类】
- 多标签优先级：当 aliases 同时包含市值/因子词和行业词时，优先输出行业标签；仅在完全没有行业词时使用市值分档或因子标签。
1) equity_benchmark 的定义：
   - 仅用于国家、地区或广义市场整体表现的代表性股票基准。
   - 它应当是该国家/地区“整体股市”或“主要市场 beta”的代理。
   - 不要把主题指数、行业指数、因子指数、概念篮子、龙头股组合误判为 equity_benchmark。
   - 若对象主要表达的是行业、风格、市值层级或主题篮子，应改用 equity_sector11* / equity_sector25* / equity_factor* / equity_cap*。
   - 符合以上定义的宽基/主流市场指数 → equity_benchmark（如 S&P 500、NASDAQ 100、Dow Jones、沪深300、MSCI China Index 等）。
2) VIX 等波动率指数 / 股票波动率指数 → equity_volatility。
3) 因子/风格（先执行 MSCI 代理还原）：
   - 价值/动量/质量/低波/红利/成长 → 对应 equity_factor*
   - 高β / 低β / beta / beta trade → equity_factorBeta
   - 周期因子 / 顺周期 / 周期风格 / 景气循环因子 → equity_factorCyclical
   - 但若 norm 或 aliases 已明确指向具体行业（如钢铁、煤炭、有色、航运、化工等），优先使用对应行业标签，不要强行归为 equity_factorCyclical
   - 流动性因子 / liquidity factor / 高流动性股票 / 低流动性溢价 → equity_factorLiquidity
   - 但若“流动性”仅指宏观流动性、货币条件、市场资金面、央行投放等，不要映射为 equity_factorLiquidity
   - 防御型/防守型 → equity_factorDefensive
   - 其他明确因子 → equity_factorUndefined
   - 规模/大小盘风格 → 优先 equity_cap*；若明确为因子而非市值分段可用 equity_factorSize
4) 市值分档 → equity_capmega / large / mid / small。
   - “mega cap / 超大市值 / 巨头 / 七巨头 / Magnificent 7 / FAANG / Big Tech leaders” 这类以超大市值龙头股票集合为核心语义的命名篮子，优先映射为 equity_capmega。
   - 若该巨头篮子在金融常识上明显对应单一国家市场（如 Magnificent 7 / FAANG 通常对应 USA），即使 norm 未显式写出国家，也可推断对应 country。
   - 若名称明确是宽基主流市场基准（如 S&P 500、沪深300、MSCI China Index），仍使用 equity_benchmark，不要改为 equity_capmega。
5) 行业/概念板块（优先 GICS 25，其次 GICS 11）：
    - 规则：若 norm 或 aliases 能明确落到某个 GICS 二级行业组，则优先使用对应的 `equity_sector25*` 标签；若只能明确到一级行业，则使用对应的 `equity_sector11*` 标签；只有连一级行业都无法自信判断时，才用 equity_sectorUndefined。
    - Energy / Materials / Utilities：当前仅保留一级标签，直接使用 equity_sector11Energy / equity_sector11Materials / equity_sector11Utilities。
    - 工业一级：equity_sector11Industrials
      · 二级：equity_sector25CapitalGoods / equity_sector25CommercialProfessionalServices / equity_sector25Transportation
    - 非必需消费一级：equity_sector11ConsumerDiscretionary
      · 二级：equity_sector25AutomobilesComponents / equity_sector25ConsumerDurablesApparel / equity_sector25ConsumerServices / equity_sector25ConsumerDiscretionaryDistributionRetail
    - 必需消费一级：equity_sector11ConsumerStaples
      · 二级：equity_sector25ConsumerStaplesDistributionRetail / equity_sector25FoodBeverageTobacco / equity_sector25HouseholdPersonalProducts
    - 医疗一级：equity_sector11HealthCare
      · 二级：equity_sector25HealthCareEquipmentServices / equity_sector25PharmaceuticalsBiotechnologyLifeSciences
    - 金融一级：equity_sector11Financials
      · 二级：equity_sector25Banks / equity_sector25FinancialServices / equity_sector25Insurance
      · 中文语境下："金融" / "金融股" / "金融板块" → equity_sector11Financials
      · "银行" / "银行股" / "银行板块" → equity_sector25Banks
      · "保险" / "保险股" / "保险板块" → equity_sector25Insurance
      · "券商" / "券商股" / "证券" / "证券股" / "大金融" → equity_sector25FinancialServices
    - 信息技术一级：equity_sector11InformationTechnology
      · 二级：equity_sector25SoftwareServices / equity_sector25TechnologyHardwareEquipment / equity_sector25SemiconductorsSemiconductorEquipment
      · 中文语境下："科技" / "高科技" / "高新板块" / "高效能运算" 若不足以细化到二级，则使用 equity_sector11InformationTechnology
    - 通信服务一级：equity_sector11CommunicationServices
      · 二级：equity_sector25TelecommunicationServices / equity_sector25MediaEntertainment
    - 房地产一级：equity_sector11RealEstate
      · 二级：equity_sector25EquityREITs / equity_sector25RealEstateManagementDevelopment
    - 无法自信映射→ equity_sectorUndefined。
6) 单一公司名或 ticker → equity_stock。

【特殊标的的豁免与直接分类】
- 衍生品（期货/期权/互换/远期）：若 norm 或 aliases 明确指代衍生品合约本身，且底层资产明确，直接映射底层资产标签；不额外创建衍生品标签。
- 波动率指数 / VIX 相关产品（如 VIX 期货、VXX ETN）：映射为 equity_volatility；country 按其所对应股票市场的暴露地域填写，而非产品上市地；例如 VIX / VXX / UVXY → country="USA"，VHSI / VHSCEI → country="HKG"；ticker=""。
- 基金 / ETF / ETN（若上游未过滤）：优先按其所追踪的底层敞口分类，而不是一律视为 equity_stock。
  - 例如：SPY / IVV / VOO → equity_benchmark, country="USA"
  - 例如：QQQ → equity_benchmark, country="USA"
  - 行业 ETF → 对应 equity_sector11* 或 equity_sector25*
  - 因子 ETF → 对应 equity_factor*
  - 市值风格 ETF / 巨头篮子 ETF → 对应 equity_cap*
  - 只有在无法可靠判断其底层敞口时，才退回为 equity_stock + 对应 ticker + 上市地 country。

=== 标签输出严格约束 ===
- 所有标签必须从 UnderlyingAsset 列表中逐字复制，严禁修改、缩短、拼写错误或自创标签。
- 除货币对等少数强制多标签场景外，优先输出单一最精确标签。

【CRYPTO 加密资产】
- Bitcoin/BTC → crypto_btc  /  Ethereum/ETH → crypto_eth
- USDT/Tether → crypto_usdt
- 泛称或其他币种 → crypto_other

=== 兜底 ===
无法自信映射 → ["unclassified"]
"""
