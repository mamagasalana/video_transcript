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

Intent = Literal["open_buy", "open_sell", "close_buy", "close_sell", "unclear", "invalid"]

class TradingSignalBase(BaseModel):
    instrument: List[str] = Field(..., min_length=1,
        description=(
            "必须精确复制 Helper 中对应项的 instrument 列表，用于和 helper 建立一一对应关系。"
            "列表中的每一项都是同一标的在 Transcript 中可能出现的别名或写法。"
            "不得新增、删减、改写、翻译或重新排序；输出时应直接沿用 Helper 原始列表。"
        ),
    )
    instrument_normalized: str = Field(..., min_length=1,
        description=(
            "必须精确复制 Helper 中对应项的 instrument_normalized 字段；"
            "该字段是该标的的唯一标准化标识，例如 cmd_gold / fx_usd。"
            "若 Helper 提供的是标准化名称，则直接沿用，不得自行重写。"
        ),
    )
    intent: Intent = Field(...,
        description=(
            "交易意图枚举，仅可填写：open_buy / open_sell / close_buy / close_sell / unclear / invalid。\n\n"
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
            "**invalid**：Helper 给出的对象并非可交易标的，或在当前语境下属于错误/无效标的，例如 CPI、GDP、经济数据等。\n\n"
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
SCHEMA_VERSION=2026-04-24T00:00:00
你是一个中文(普通话)经验丰富的财经分析师，专门分析《金钱报》主持人(杨世光) 的交易信号。

输入:
- Transcript：完整逐字稿
- Helper：instruments JSON（已抽取好的 instrument 列表，至少包含 instrument / instrument_normalized）

目标:
基于 Transcript，对 Helper 中列出的每一个 instrument 逐一判断其交易意图（intent）并输出交易信号。
必须覆盖 Helper 的所有 instrument：每个 helper item 都要输出且只输出一条 signal。

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

核心约束（必须遵守）：
1) 覆盖性：signals 中必须覆盖 Helper 的全部 helper item；每个 helper item 必须且只能对应一条 signal。
2) 不新增标的：不得在 signals 中输出 Helper 之外的任何 instrument；不得自行补充未出现于 Helper 的标的。
3) Helper 优先：signal 中的 instrument / instrument_normalized 必须直接沿用 Helper 对应字段，不得改写。
4) 别名匹配：Helper.instrument 是同一标的的别名列表；只要 Transcript 明确提到其中任一别名，都视为命中该 helper item。
5) 以 Transcript 为准：所有 intent、evidence、summary 判断只能来自 Transcript 明确表达的内容；不得引入 Transcript 之外的新信息。
6) 证据原文：evidence 的每一项都必须是 Transcript 中真实存在的连续原文子串，必须逐字复制，不得改写、拼接或凭空生成。
7) 解释约束：summary 的每一项都要解释对应 evidence 为什么支持 intent；summary 可以概括，但不得引入 Transcript 之外的事实。
8) 配对关系：summary 与 evidence 一一对应；若有 2 条 evidence，则必须有 2 条 summary。若 evidence 为空，则 summary 也应为空。
9) 合并原则：同一个 helper item 只输出一条 signal；如果 Transcript 多处提及该 item 的多个别名，把相关证据合并到同一条 signal 中。

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

**重要区分（补充说明）：**
- **单一理由即可**：只要主持人给出单一但清晰、可执行、带方向的支持理由，就可以判为 open_buy 或 open_sell，不要求必须有多个理由。
- **证据的强度**：证据不必是绝对确定，只要主持人表达出倾向性（如“可能”、“恐怕”、“要小心”），也应结合上下文判断。
- **上下文优先**：若某段话表面中性，但结合前后文明显指向操作方向，应以整体意图为准。

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
SCHEMA_VERSION=2026-03-02T00:00:00
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
       - If the raw includes an exchange/ticker suffix, you MUST use the suffix mapping below and MUST NOT override it using context.
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
- EQUITY TICKER SUFFIX -> COUNTRY (HARD RULES):
  - If raw ends with ".T" => country="JPN" (Tokyo Stock Exchange). NOT Taiwan.
  - If raw ends with ".TW" => country="TWN".
  - If raw ends with ".HK" => country="HKG".
  - If raw ends with ".SS" or ".SH" or ".SZ" => country="CHN".
  - If raw ends with ".KS" or ".KQ" => country="KOR".
  - If raw ends with ".AS" => country="NLD".
  - If raw ends with ".L" => country="GBR".
  - If raw ends with ".PA" => country="FRA".
  - If raw ends with ".DE" => country="DEU".
  - If raw ends with ".SW" => country="CHE".

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
