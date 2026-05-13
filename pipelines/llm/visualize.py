from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os
from collections import defaultdict, Counter
from typing import Optional
import plotly.graph_objects as go  # type: ignore[import-not-found]
import colorsys
import matplotlib.pyplot as plt  # type: ignore[import-not-found]
from matplotlib import font_manager, rcParams  # type: ignore[import-not-found]
from src.llm.mq_tag_summary import get_tag_summary


OUT_FOLDER = "outputs/viz"

class Visualizer:
    def __init__( self, out_folder: str = OUT_FOLDER,):
        self.out_folder = out_folder
        os.makedirs(self.out_folder, exist_ok=True)
        self._plotly_png_warning_shown = False

    def distinct_hex_colors(self, n: int):
        out = []
        for i in range(n):
            h = i / n
            r, g, b = colorsys.hsv_to_rgb(h, 0.65, 0.90)  # sat/value tune if you want
            out.append(f"rgb({int(r*255)},{int(g*255)},{int(b*255)})")
        return out


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

    def _write_plotly_png(self, fig: go.Figure, path: str) -> bool:
        """
        Best-effort static export for Plotly charts.
        Requires plotly image export support (typically kaleido).
        """
        try:
            fig.write_image(path, width=1600, height=900, scale=2)
            return True
        except Exception as e:
            if not self._plotly_png_warning_shown:
                print(
                    "plotly png export skipped: %s. "
                    "Install `kaleido` to enable Plotly PNG output." % e
                )
                self._plotly_png_warning_shown = True
            return False

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
            for inst in insts:
                month_counts[date_str[:6]][inst] += 1

        if not month_counts:
            return

        months = sorted(month_counts.keys(), key=lambda s: (int(s[:4]), int(s[4:6])))  # YYYY, MM
        years = sorted({mk[:4] for mk in months})

        colors = self.distinct_hex_colors(20)

        for year in years:
            months_year = [mk for mk in months if mk[:4] == year]
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
            base_path = os.path.join(
                self.out_folder, f"class_top_{top_per_month}_each_month_{year}"
            )
            fig.write_html(base_path + ".html")
            self._write_plotly_png(fig, base_path + ".png")

            if show:
                fig.show()
        return

    
    def _plot_ret2( self,
        ret2_local: dict[str, list[str]] | dict[str, set],
        show: bool,
        top_n: int,
    ) -> None:

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


    def main(
        self,
        prefix='2026_04_24_t0',
        model='deepseek-v4-flash',
        classification_prefix='class4',
        batches=range(3),
    ):
        ret =  get_tag_summary(
            prefix=prefix,
            model=model,
            classification_prefix=classification_prefix,
            batches=batches)
        ret_tags = ret['final_by_date']
        self._plot_ret2(ret_tags, show=1, top_n=10)
        self._plot_monthly_top_each_month(ret_tags, show=1, top_per_month=5)


if __name__ == "__main__":
    default_visualizer =Visualizer()

    default_visualizer.main()
