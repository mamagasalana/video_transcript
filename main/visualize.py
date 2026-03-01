import json
import re
import os
from collections import defaultdict
import glob
from typing import Optional
import datetime as dtmod
import plotly.graph_objects as go  # type: ignore[import-not-found]
import colorsys

try:
    import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    from matplotlib import font_manager, rcParams  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    plt = None
    font_manager = None
    rcParams = None
from collections import Counter

OUT_FOLDER = "outputs/viz"

class Visualizer:
    def __init__(self, out_folder: str = OUT_FOLDER) -> None:
        self.out_folder = out_folder
        self.raw_norm_counts = defaultdict(lambda: defaultdict(int))  # raw -> normalized -> count
        self.classification_map = {}

    def distinct_hex_colors(self, n: int):
        out = []
        for i in range(n):
            h = i / n
            r, g, b = colorsys.hsv_to_rgb(h, 0.65, 0.90)  # sat/value tune if you want
            out.append(f"rgb({int(r*255)},{int(g*255)},{int(b*255)})")
        return out

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
        if font_manager is None or rcParams is None:
            return None
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

        classification_map = {}
        classifications = []
        for f in glob.glob('outputs/model_output/class1_deepseek-reasoner/*'):
            js = json.load(open(f, 'r'))
            classifications.extend(js['instruments'])
        for x in classifications:
            norm_inst =  x['raw']
            tmp = []
            country = '_%s' % x['country']
            if country == '_GLOBAL':
                country = ''
            ticker = x['ticker']
            if ticker:
                ticker  = '_%s' % ticker
            
            for ua in x['underlying_assets']:
                if len(x['underlying_assets']) ==2:
                    if ua == 'fx_usd':
                        continue
                tmp.append('%s%s%s' % (ua, country, ticker))
            classification_map[norm_inst] = tmp.copy()
            
        self.classification_map = classification_map


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
                     'classification_map': classification_map,
                     }

    def load_outputs_tags(
        self,
        glob_template: str = "outputs/model_output/2026_02_14_t2_{batch}_deepseek-reasoner/*",
        *,
        include_unmapped: bool = False,
        unmapped_label: str = "Unmapped",
    ) -> dict[str, set[str]]:
        """
        Build date -> set of classification tags using `classification_map` keyed by norm_inst.

        If a norm_inst maps to multiple tags, each tag is added.
        Using a set means a tag counts at most once per date (presence), even if multiple
        instruments on that date map to the same tag.
        """
        if not self.classification_map:
            # Also builds self.classification_map.
            self.load_outputs(glob_template=glob_template, debug=True)

        ret_tags: defaultdict[str, set[str]] = defaultdict(set)
        for batch in range(3):
            pattern = glob_template.format(batch=batch)
            for f in sorted(glob.glob(pattern)):
                f2 = os.path.basename(f)
                date_str = self._extract_date_str(f2)
                with open(f, "r", encoding="utf-8-sig") as fp:
                    js = json.load(fp)["instruments"]
                for itm in js:
                    raw_inst = self._strip_bom(itm["instrument"])
                    norm_inst = self._strip_bom(itm["instrument_normalized"])
                    if raw_inst == norm_inst:
                        continue

                    tags = self.classification_map.get(norm_inst)
                    if isinstance(tags, list) and tags:
                        # de-dupe within a single instrument mapping (avoid accidental double-count)
                        tags = list(dict.fromkeys([str(t) for t in tags if str(t).strip()]))
                        ret_tags[date_str].update(tags)
                    elif include_unmapped:
                        ret_tags[date_str].add(unmapped_label)

        return dict(ret_tags)

    def _month_key_from_date_str(self, date_str: str) -> Optional[str]:
        d = self._parse_yyyymmdd(date_str)
        if d is None:
            return None
        return d.strftime("%m%Y")  # mmyyyy


    def _plot_monthly_top_each_month(
        self,
        ret2_local: dict[str, list[str]] | dict[str, set],
        show: bool,
        top_per_month: int,
    ) -> None:
        """
        Plot the top-N instruments *within each month* (not global top across months).
        Produces a single figure aligned like _plot_monthly_top_stacked.
        """
        if plt is None:
            raise RuntimeError("Matplotlib is required for plotting. Install it with: pip install -r requirements-viz.txt")
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

        colors = self.distinct_hex_colors(17)

        for year in years:
            months_year = [mk for mk in months if mk[2:6] == year]
            fig = go.Figure()
            color_map = {}
            for mk in months_year:
                top = month_counts[mk].most_common(max(0, top_per_month))
                for inst, inst_count in top:
                    if not inst in color_map:
                        color_map[inst] = colors[len(color_map)]
                    color = color_map[inst]
                    fig.add_trace(
                        go.Bar(
                            name=inst,
                            x=[mk],
                            y=[inst_count],
                            marker_color=color,
                            hovertemplate="%{x}<br>%{fullData.name}: %{y}<extra></extra>",
                        )
                    )

            fig.update_layout(
                barmode="stack",
                title=f"classification: top {top_per_month} tags within each month (stacked) — {year}",
                xaxis_title="Month (mmyyyy)",
                yaxis_title="# dates where tag present",
                legend_title_text="Tag",
                margin=dict(l=60, r=260, t=80, b=80),
            )
            fig.update_xaxes(tickangle=-60)
            fig.write_html(
                os.path.join(self.out_folder, f"class_top_{top_per_month}_each_month_{year}.html")
            )

            if show:
                fig.show()
        return

    


    def _plot_ret2(
        self,
        ret2_local: dict[str, list[str]] | dict[str, set],
        show: bool,
        top_n: int,
    ) -> None:
        if plt is None:
            raise RuntimeError("Matplotlib is required for plotting. Install it with: pip install -r requirements-viz.txt")
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
        ax.set_title(f"classification: top {top_n} tags")
        fig.tight_layout()
        fig.savefig(os.path.join(self.out_folder, "class_top_items.png"), dpi=150)

        if show:
            plt.show(block=True)
        else:
            plt.close("all")


    def main(self) -> int:
        # Use classification tags (including multi-tag instruments) instead of normalized instrument strings.
        ret_tags = self.load_outputs_tags()
        os.makedirs(self.out_folder, exist_ok=True)
        self._plot_ret2(ret_tags, show=1, top_n=10)
        self._plot_monthly_top_each_month(ret_tags, show=1, top_per_month=5)

        return 0




if __name__ == "__main__":
    default_visualizer =Visualizer()

    default_visualizer.main()
