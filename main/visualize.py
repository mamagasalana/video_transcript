import json
import re
import os
from collections import defaultdict
import glob
from typing import Optional
import datetime as dtmod

import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams
from collections import Counter

OUT_FOLDER = "outputs/viz"

class Visualizer:
    def __init__(self, out_folder: str = OUT_FOLDER) -> None:
        self.out_folder = out_folder
        self.raw_norm_counts = defaultdict(lambda: defaultdict(int))  # raw -> normalized -> count

    def _extract_date_str(self, s: str) -> str:
        """
        Try to extract a YYYYMMDD date from a filename/path string.
        Falls back to the first digit group (legacy behavior).
        """
        m = re.search(r"(20\d{2})[_-](\d{2})[_-](\d{2})", s)
        if m:
            return f"{m.group(1)}{m.group(2)}{m.group(3)}"
        m = re.search(r"(20\d{2})(\d{2})(\d{2})", s)
        if m:
            return m.group(0)
        groups = re.findall(r"\d+", s)
        if not groups:
            return s
        return groups[0]


    def _parse_yyyymmdd(self, s: str) -> Optional[dtmod.date]:
        if re.fullmatch(r"20\d{6}", s) is None:
            return None
        try:
            return dtmod.datetime.strptime(s, "%Y%m%d").date()
        except ValueError:
            return None


    def _configure_plot_font(self, preferred_font: Optional[str]) -> Optional[str]:
        """
        Fix "broken" Chinese/CJK characters in PNGs by selecting a CJK-capable font.
        Note: utf-8 / utf-8-sig affects decoding; font selection affects rendering.
        """
        available = {f.name for f in font_manager.fontManager.ttflist}
        candidates = [
            preferred_font,
            "Noto Sans CJK SC",
            "WenQuanYi Zen Hei",
            "Noto Serif CJK SC",
            "Noto Sans CJK TC",
            "Noto Sans CJK JP",
            "Noto Sans CJK KR",
            "SimHei",
            "Microsoft YaHei",
        ]

        chosen: Optional[str] = None
        for name in candidates:
            if name and name in available:
                chosen = name
                break

        if chosen is None:
            for name in sorted(available):
                if "CJK" in name or "WenQuanYi" in name or "文泉" in name:
                    chosen = name
                    break

        if chosen:
            current = list(rcParams.get("font.sans-serif", []))
            rcParams["font.family"] = "sans-serif"
            rcParams["font.sans-serif"] = [chosen] + [f for f in current if f != chosen]
            rcParams["axes.unicode_minus"] = False
            return chosen

        return None

    def _strip_bom(self, s: str) -> str:
        # Some upstream files/fields may carry a UTF-8 BOM; strip it so labels render cleanly.
        return s.lstrip("\ufeff") if isinstance(s, str) else s

    def _pick_best_norm_for_raw(self, raw: str) -> Optional[str]:
        counts = self.raw_norm_counts.get(raw)
        if not counts:
            return None
        # Highest count wins; stable tiebreak by normalized string.
        candidates = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        return candidates[0][0]


    def load_outputs(self, glob_template: str="outputs/model_output/2026_02_14_t2_{batch}_deepseek-reasoner/*",
                     debug=False
                     ) :
        ret = defaultdict(set)  # date_str -> {raw_instrument}
        norm_map = defaultdict(set)  # normalized -> {raw}
        raw_map = defaultdict(set)  # raw -> {normalized} (set size <= 1)

        # Keep the original multi-to-multi view for debugging.
        norm_map_multi = defaultdict(set)  # normalized -> {raw}
        raw_map_multi = defaultdict(set)  # raw -> {normalized}
        norm_count = defaultdict(int)  # normalized -> {raw}
        raw_count = defaultdict(int)  # raw -> {normalized}
        raw_norm_counts = defaultdict(lambda: defaultdict(int))  # raw -> normalized -> count
        self.raw_norm_counts = raw_norm_counts

        for batch in range(3):
            pattern = glob_template.format(batch=batch)
            for f in sorted(glob.glob(pattern)):
                f2 = os.path.basename(f)
                date_str = self._extract_date_str(f2)
                # Use utf-8-sig to tolerate UTF-8 BOM in upstream files.
                with open(f, "r", encoding="utf-8-sig") as fp:
                    js = json.load(fp)["instruments"]
                for itm in js:
                    raw_inst = self._strip_bom(itm["instrument"])
                    norm_inst = self._strip_bom(itm["instrument_normalized"])

                    
                    if raw_inst != norm_inst:
                        ret[date_str].add(raw_inst)
                        norm_map_multi[norm_inst].add(raw_inst)
                        raw_map_multi[raw_inst].add(norm_inst)
                        raw_norm_counts[raw_inst][norm_inst] += 1
                        raw_count[raw_inst] +=1
                        norm_count[norm_inst] +=1
                        
        # Build one-to-multi maps by choosing a single "best" normalized value per raw.
        for raw in raw_map_multi.keys():
            best_norm = self._pick_best_norm_for_raw(raw)
            if best_norm is None:
                continue
            raw_map[raw].add(best_norm)
            norm_map[best_norm].add(raw)

        ret2_local: defaultdict[str, set] = defaultdict(set)  # date_str -> {normalized}
        for date_str, itms in ret.items():
            for itm in itms:
                tmp = raw_map[itm]
                assert len(tmp) == 1, "why not 1"
                ret2_local[date_str].add(next(iter(tmp)))
        if not debug:
            return ret2_local
        else:
            return {'norm_map_multi': norm_map_multi,
                    'raw_map_multi':  raw_map_multi,
                    'raw_norm_counts':  raw_norm_counts,
                    'raw_map':  raw_map,
                     'norm_map': norm_map,
                     'raw_count': raw_count,
                     'norm_count': norm_count,
                     }


    def _sort_dates(self, date_keys: list[str]) -> list[str]:
        parsed = {k: self._parse_yyyymmdd(k) for k in date_keys}
        if all(v is not None for v in parsed.values()):
            return sorted(date_keys, key=lambda k: parsed[k])
        return sorted(date_keys)

    def _month_key_from_date_str(self, date_str: str) -> Optional[str]:
        d = self._parse_yyyymmdd(date_str)
        if d is None:
            return None
        return d.strftime("%m%Y")  # mmyyyy


    def _plot_monthly_top_stacked(
        self,
        ret2_local: dict[str, set],
        show: bool,
        top_n: int,
    ) -> None:
        self._configure_plot_font(None)

        month_counts: dict[str, Counter] = defaultdict(Counter)  # mmyyyy -> Counter(inst -> count)
        for date_str, insts in ret2_local.items():
            mk = self._month_key_from_date_str(date_str)
            if mk is None:
                continue
            for inst in insts:
                month_counts[mk][inst] += 1

        if not month_counts:
            return

        months = sorted(month_counts.keys(), key=lambda s: (int(s[2:6]), int(s[0:2])))  # YYYY, MM

        totals = Counter()
        for mk in months:
            totals.update(month_counts[mk])
        top_insts = [k for k, _ in totals.most_common(top_n)]

        x = list(range(len(months)))
        bottoms = [0] * len(months)
        fig, ax = plt.subplots(figsize=(max(10, 0.5 * len(months)), 6))

        for inst in top_insts:
            ys = [month_counts[mk].get(inst, 0) for mk in months]
            ax.bar(x, ys, bottom=bottoms, label=inst)
            bottoms = [b + y for b, y in zip(bottoms, ys)]

        other = []
        for i, mk in enumerate(months):
            total = sum(month_counts[mk].values())
            other.append(max(0, total - bottoms[i]))
        if any(other):
            ax.bar(x, other, bottom=bottoms, label="Other", color="#CCCCCC")

        ax.set_xticks(x)
        ax.set_xticklabels(months, rotation=60, ha="right")
        ax.set_ylabel("# (date, instrument) occurrences")
        ax.set_title(f"ret2: top {top_n} instruments by month (stacked)")
        ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), borderaxespad=0)
        fig.tight_layout()
        fig.savefig(os.path.join(self.out_folder, f"ret2_top_{top_n}_by_month_stacked.png"), dpi=150)

        if show:
            plt.show(block=True)
        else:
            plt.close(fig)


    def _plot_monthly_top_each_month(
        self,
        ret2_local: dict[str, set],
        show: bool,
        top_per_month: int,
    ) -> None:
        """
        Plot the top-N instruments *within each month* (not global top across months).
        Produces a single figure aligned like _plot_monthly_top_stacked.
        """
        self._configure_plot_font(None)

        month_counts: dict[str, Counter] = defaultdict(Counter)  # mmyyyy -> Counter(inst -> count)
        for date_str, insts in ret2_local.items():
            mk = self._month_key_from_date_str(date_str)
            if mk is None:
                continue
            for inst in insts:
                month_counts[mk][inst] += 1

        if not month_counts:
            return

        months = sorted(month_counts.keys(), key=lambda s: (int(s[2:6]), int(s[0:2])))  # YYYY, MM
        years = sorted({mk[2:6] for mk in months})

        if 1:
            try:
                import plotly.graph_objects as go  # type: ignore[import-not-found]
                from plotly.colors import qualitative  # type: ignore[import-not-found]
            except Exception as e:  # pragma: no cover
                raise RuntimeError(
                    "Plotly is required for interactive charts. Install it with: pip install plotly"
                ) from e

            colors = list(getattr(qualitative, "Plotly", [])) or [
                "#1f77b4",
                "#ff7f0e",
                "#2ca02c",
                "#d62728",
                "#9467bd",
                "#8c564b",
                "#e377c2",
                "#7f7f7f",
                "#bcbd22",
                "#17becf",
            ]

            for year in years:
                months_year = [mk for mk in months if mk[2:6] == year]
                per_month_top: dict[str, Counter] = {}
                other_counts: list[int] = []
                totals_of_top = Counter()
                for mk in months_year:
                    top = month_counts[mk].most_common(max(0, top_per_month))
                    top_counter = Counter({inst: v for inst, v in top})
                    per_month_top[mk] = top_counter
                    totals_of_top.update(top_counter)

                    total = sum(month_counts[mk].values())
                    other_counts.append(max(0, total - sum(top_counter.values())))

                top_insts = [k for k, _ in totals_of_top.most_common()]  # union of each-month tops, ordered

                fig = go.Figure()
                for i, inst in enumerate(top_insts):
                    ys = [per_month_top[mk].get(inst, 0) for mk in months_year]
                    if not any(ys):
                        continue
                    fig.add_trace(
                        go.Bar(
                            name=inst,
                            x=months_year,
                            y=ys,
                            marker_color=colors[i % len(colors)],
                            hovertemplate="%{x}<br>%{fullData.name}: %{y}<extra></extra>",
                        )
                    )

                # if any(other_counts):
                #     fig.add_trace(
                #         go.Bar(
                #             name="Other",
                #             x=months_year,
                #             y=other_counts,
                #             marker_color="#CCCCCC",
                #             hovertemplate="%{x}<br>%{fullData.name}: %{y}<extra></extra>",
                #         )
                #     )

                fig.update_layout(
                    barmode="stack",
                    title=f"ret2: top {top_per_month} instruments within each month (stacked) — {year}",
                    xaxis_title="Month (mmyyyy)",
                    yaxis_title="# (date, instrument) occurrences",
                    legend_title_text="Instrument",
                    margin=dict(l=60, r=260, t=80, b=80),
                )
                fig.update_xaxes(tickangle=-60)
                fig.write_html(
                    os.path.join(self.out_folder, f"ret2_top_{top_per_month}_each_month_{year}.html")
                )

                if show:
                    fig.show()
            return

        for year in years:
            months_year = [mk for mk in months if mk[2:6] == year]
            per_month_top = {}
            other_counts = []
            totals_of_top = Counter()
            for mk in months_year:
                top = month_counts[mk].most_common(max(0, top_per_month))
                top_counter = Counter({inst: v for inst, v in top})
                per_month_top[mk] = top_counter
                totals_of_top.update(top_counter)

                total = sum(month_counts[mk].values())
                other_counts.append(max(0, total - sum(top_counter.values())))

            top_insts = [k for k, _ in totals_of_top.most_common()]  # union of each-month tops, ordered

            # Stable colors within the year chart.
            cmap = plt.get_cmap("tab20")
            inst_to_color = {inst: cmap(i % cmap.N) for i, inst in enumerate(top_insts)}

            x = list(range(len(months_year)))
            bottoms = [0] * len(months_year)
            fig, ax = plt.subplots(figsize=(max(10, 0.5 * len(months_year)), 6))

            for inst in top_insts:
                ys = [per_month_top[mk].get(inst, 0) for mk in months_year]
                if not any(ys):
                    continue
                ax.bar(x, ys, bottom=bottoms, label=inst, color=inst_to_color.get(inst))
                bottoms = [b + y for b, y in zip(bottoms, ys)]

            if any(other_counts):
                ax.bar(x, other_counts, bottom=bottoms, label="Other", color="#CCCCCC")

            ax.set_xticks(x)
            ax.set_xticklabels(months_year, rotation=60, ha="right")
            ax.set_ylabel("# (date, instrument) occurrences")
            ax.set_title(f"ret2: top {top_per_month} instruments within each month (stacked) — {year}")
            ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), borderaxespad=0)
            fig.tight_layout()
            fig.savefig(
                os.path.join(self.out_folder, f"ret2_top_{top_per_month}_each_month_{year}.png"), dpi=150
            )

            if show:
                plt.show(block=True)
            else:
                plt.close(fig)


    def _plot_ret2(
        self,
        ret2_local: dict[str, set],
        show: bool,
        top_n: int,
    ) -> None:
        self._configure_plot_font(None)
        # Top instruments overall (how many dates each appears on).
        freq = Counter()
        for insts in ret2_local.values():
            freq.update(insts)
        top = freq.most_common(top_n)
        labels = [k for k, _ in top][::-1]
        values = [v for _, v in top][::-1]

        fig, ax = plt.subplots(figsize=(10, max(4, 0.25 * len(labels))))
        ax.barh(labels, values)
        ax.set_xlabel("# dates where present")
        ax.set_title(f"ret2: top {top_n} normalized instruments")
        fig.tight_layout()
        fig.savefig(os.path.join(self.out_folder, "ret2_top_instruments.png"), dpi=150)

        if show:
            plt.show(block=True)
        else:
            plt.close("all")


    def main(self) -> int:
        ret2_local = self.load_outputs()
        os.makedirs(self.out_folder, exist_ok=True)
        self._plot_ret2(ret2_local,show=1,top_n=10,)
        self._plot_monthly_top_stacked(ret2_local,show=1,top_n=5,)
        self._plot_monthly_top_each_month(ret2_local,show=1,top_per_month=5,)

        return 0




if __name__ == "__main__":
    default_visualizer =Visualizer()

    default_visualizer.main()
