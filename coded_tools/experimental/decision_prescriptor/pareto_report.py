# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT

import html
from collections.abc import Sequence

import numpy as np

from coded_tools.experimental.decision_prescriptor.svg_charts import SvgCharts


# The report has one public entry point; its parts are private steps of that one render.
# pylint: disable=too-few-public-methods
class ParetoReport:
    """
    Assembles the self-contained HTML report for one prescriptor run.

    Everything is emitted as inline SVG inside a single HTML file with no external
    stylesheet, script or font, which keeps a report readable straight from disk.
    The charts themselves come from SvgCharts; this class lays them out, adds the
    stat tiles and the data table, and defines the palette both themes use.

    Blue and orange were checked against colorblind-separation and contrast gates
    on both the light and dark surfaces before being used here.
    """

    # Palette roles. Light and dark are separately chosen steps, not an inversion.
    LIGHT_THEME: dict[str, str] = {
        "surface": "#fcfcfb",
        "plane": "#f9f9f7",
        "text-primary": "#0b0b0b",
        "text-secondary": "#52514e",
        "muted": "#898781",
        "grid": "#e1e0d9",
        "axis": "#c3c2b7",
        "series-1": "#2a78d6",
        "series-2": "#eb6834",
        "border": "rgba(11,11,11,0.10)",
    }
    DARK_THEME: dict[str, str] = {
        "surface": "#1a1a19",
        "plane": "#0d0d0d",
        "text-primary": "#ffffff",
        "text-secondary": "#c3c2b7",
        "muted": "#898781",
        "grid": "#2c2c2a",
        "axis": "#383835",
        "series-1": "#3987e5",
        "series-2": "#d95926",
        "border": "rgba(255,255,255,0.10)",
    }

    STYLE: str = """
:root { color-scheme: light dark; }
body { margin: 0; background: var(--plane); color: var(--text-primary);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
.wrap { max-width: 1080px; margin: 0 auto; padding: 32px 20px 64px; }
h1 { font-size: 1.5rem; margin: 0 0 4px; letter-spacing: -0.01em; }
h2 { font-size: 1rem; margin: 0 0 2px; }
p.sub { color: var(--text-secondary); margin: 0 0 28px; font-size: 0.875rem; line-height: 1.5; }
p.note { color: var(--text-secondary); margin: 0 0 12px; font-size: 0.8125rem; line-height: 1.5; }
section { background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
  padding: 20px; margin-bottom: 20px; }
.grid-2 { display: grid; gap: 24px; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); }
.chart { width: 100%; height: auto; overflow: visible; display: block; }
.chart-scroll { overflow-x: auto; }
line.grid { stroke: var(--grid); stroke-width: 1; }
line.axis { stroke: var(--axis); stroke-width: 1; }
text.tick { fill: var(--muted); font-size: 11px; }
text.axis-title { fill: var(--text-secondary); font-size: 12px; }
text.direct-label { fill: var(--text-primary); font-size: 12px; font-weight: 600; }
circle.dominated { fill: var(--muted); opacity: 0.42; }
circle.front { fill: var(--series-1); stroke: var(--surface); stroke-width: 2; }
circle.front:hover { r: 7; }
polyline.front-line { fill: none; stroke: var(--series-1); stroke-width: 2; opacity: 0.35; }
polyline.series-line { fill: none; stroke: var(--series-1); stroke-width: 2;
  stroke-linejoin: round; stroke-linecap: round; }
polyline.pc-line { fill: none; stroke: var(--series-1); stroke-width: 1.5; opacity: 0.3; }
polyline.pc-line:hover { opacity: 1; stroke-width: 2.5; }
polyline.pc-line-highlight { fill: none; stroke: var(--series-2); stroke-width: 3; }
.legend { display: flex; gap: 18px; flex-wrap: wrap; margin: 4px 0 14px;
  font-size: 0.8125rem; color: var(--text-secondary); }
.legend span { display: inline-flex; align-items: center; gap: 7px; }
.swatch { width: 11px; height: 11px; border-radius: 50%; display: inline-block; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 0.8125rem; }
caption { text-align: left; color: var(--text-secondary); font-size: 0.8125rem; padding-bottom: 10px; }
th, td { padding: 7px 12px; text-align: right; border-bottom: 1px solid var(--grid);
  font-variant-numeric: tabular-nums; }
thead th { color: var(--text-secondary); font-weight: 600; text-align: right; white-space: nowrap; }
tbody th { color: var(--text-secondary); font-weight: 500; text-align: left; }
dl.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 18px; margin: 0; }
dt { color: var(--text-secondary); font-size: 0.75rem; margin-bottom: 4px; }
dd { margin: 0; font-size: 1.375rem; font-variant-numeric: tabular-nums; letter-spacing: -0.01em; }
"""

    # The report needs every one of these inputs, and each is a distinct part of the page.
    # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    @staticmethod
    def render(
        title: str,
        front: np.ndarray,
        dominated: np.ndarray,
        actions: np.ndarray,
        objective_labels: Sequence[str],
        action_labels: Sequence[str],
        hypervolume_history: Sequence[float],
        summary: dict[str, str],
        balanced_index: int | None = None,
    ) -> str:
        """
        :param title: Page heading.
        :param front: Non-dominated objectives in display orientation, shape (n, num_objectives).
        :param dominated: Dominated objectives in display orientation.
        :param actions: Mean prescribed action per front solution, shape (n, num_actions).
        :param objective_labels: Objective display names.
        :param action_labels: Action display names.
        :param hypervolume_history: Hypervolume after each generation.
        :param summary: Named run facts shown as stat tiles.
        :param balanced_index: Row of `front` to highlight as a balanced compromise.
        :return: A complete, self-contained HTML document.
        """
        num_objectives: int = front.shape[1]

        # Pairwise projections: one chart for two objectives, small multiples beyond that.
        pairs: list[tuple[int, int]] = (
            [(0, 1)]
            if num_objectives == 2
            else [(i, j) for i in range(num_objectives) for j in range(i + 1, num_objectives)]
        )
        scatters: str = "".join(
            f"<div><h2>{html.escape(objective_labels[i])} vs {html.escape(objective_labels[j])}</h2>"
            f"{SvgCharts.pareto_scatter(front, dominated, i, j, objective_labels, connect=num_objectives == 2)}</div>"
            for i, j in pairs
        )

        stat_tiles: str = "".join(
            f"<div><dt>{html.escape(key)}</dt><dd>{html.escape(value)}</dd></div>" for key, value in summary.items()
        )

        legend: str = (
            "<div class='legend'>"
            "<span><i class='swatch' style='background:var(--series-1)'></i>Pareto front</span>"
            "<span><i class='swatch' style='background:var(--muted);opacity:.45'></i>dominated</span>"
            "</div>"
        )
        pc_legend: str = (
            "<div class='legend'>"
            "<span><i class='swatch' style='background:var(--series-1)'></i>front strategies</span>"
            "<span><i class='swatch' style='background:var(--series-2)'></i>balanced pick</span>"
            "</div>"
        )
        parallel: str = SvgCharts.parallel_coordinates(front, objective_labels, balanced_index)
        table: str = ParetoReport._front_table(front, actions, objective_labels, action_labels)

        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{ParetoReport._theme_variables()}{ParetoReport.STYLE}</style></head>
<body><div class="wrap">
<h1>{html.escape(title)}</h1>
<p class="sub">Each point is a distinct strategy that nothing else beats on every objective at once.
Moving along the front always means giving something up — that exchange is the decision.</p>
<section><dl class="stats">{stat_tiles}</dl></section>
<section><h2>Trade-off front</h2>
<p class="note">Grey points were reached during the search but are beaten outright on every objective,
so they are never worth choosing.</p>
{legend}<div class="grid-2">{scatters}</div></section>
<section><h2>Strategies across all objectives</h2>
<p class="note">One line per strategy. A line that rises on one axis and falls on the next is making
exactly that trade.</p>
{pc_legend}<div class="chart-scroll">{parallel}</div>
</section>
<section><h2>Search progress</h2>
<p class="note">Hypervolume of the archived front after each generation. It rises by construction, so a
flat tail means further generations added nothing.</p>
{SvgCharts.convergence(hypervolume_history)}</section>
<section><h2>The numbers</h2>{table}</section>
</div></body></html>"""

    @staticmethod
    def _front_table(
        front: np.ndarray, actions: np.ndarray, labels: Sequence[str], action_labels: Sequence[str]
    ) -> str:
        """
        Render the front as an HTML table.

        The table is the accessibility path for the charts and the practical way to
        read exact values, so it always ships rather than being an optional extra.

        :param front: Objective values per strategy.
        :param actions: Representative action values per strategy.
        :param labels: Objective display names.
        :param action_labels: Action display names.
        :return: HTML fragment.
        """
        header: str = "".join(f"<th>{html.escape(name)}</th>" for name in list(labels) + list(action_labels))
        rows: list[str] = []
        for index in range(front.shape[0]):
            values: list[float] = list(front[index]) + list(actions[index])
            cells: str = "".join(f"<td>{html.escape(SvgCharts.format_number(value))}</td>" for value in values)
            rows.append(f"<tr><th scope='row'>{index + 1}</th>{cells}</tr>")
        return (
            "<div class='table-wrap'><table><caption>Pareto front — objective values and mean prescribed action"
            f"</caption><thead><tr><th scope='col'>#</th>{header}</tr></thead><tbody>{''.join(rows)}</tbody>"
            "</table></div>"
        )

    @staticmethod
    def _theme_variables() -> str:
        """
        Emit the palette as CSS custom properties for both light and dark surfaces.

        Dark is a selected set of steps validated against the dark surface, not an
        automatic inversion of the light values.

        :return: A CSS fragment defining the theme variables under both scopes.
        """
        light: str = ParetoReport._theme_block(ParetoReport.LIGHT_THEME)
        dark: str = ParetoReport._theme_block(ParetoReport.DARK_THEME)
        return (
            f":root{{{light}}}"
            f"@media (prefers-color-scheme: dark){{:root:not([data-theme='light']){{{dark}}}}}"
            f":root[data-theme='dark']{{{dark}}}"
        )

    @staticmethod
    def _theme_block(theme: dict[str, str]) -> str:
        """
        :param theme: Palette role to color.
        :return: The roles as CSS custom property declarations.
        """
        return "".join(f"--{role}:{color};" for role, color in theme.items())
