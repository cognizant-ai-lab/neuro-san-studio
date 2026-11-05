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

from coded_tools.experimental.decision_prescriptor.linear_scale import LinearScale


class SvgCharts:
    """
    Self-contained SVG charts for a Pareto front.

    A trade-off front is one of the few results that genuinely cannot be read as a
    table. The shape of the curve is the finding: where it is steep, a small
    concession on one objective buys a large gain on another, and where it is flat,
    it does not. So the charts here are the output, not decoration on it.

    Each chart is a complete <svg> element styled by CSS classes that ParetoReport
    defines, so the charts carry no colors of their own.
    """

    PLOT_WIDTH: int = 460
    PLOT_HEIGHT: int = 320
    # Full-bleed charts use their own width so they render near 1:1 rather than being
    # scaled up from a narrow viewBox, which would enlarge the text along with the plot.
    WIDE_WIDTH: int = 940
    MARGIN_TOP: int = 24
    MARGIN_RIGHT: int = 24
    MARGIN_BOTTOM: int = 52
    MARGIN_LEFT: int = 72

    @staticmethod
    def format_number(value: float) -> str:
        """
        Format a number compactly for an axis label, tooltip or table cell.

        :param value: Number to format.
        :return: Short human-readable string.
        """
        if value == 0:
            return "0"
        magnitude: float = abs(value)
        if magnitude >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        if magnitude >= 1_000:
            return f"{value / 1_000:.1f}k"
        if magnitude >= 10:
            return f"{value:.1f}"
        if magnitude >= 0.01:
            return f"{value:.3g}"
        return f"{value:.2e}"

    # Chart builders name every axis, label and series they draw; bundling them into a
    # config object would hide the signature without simplifying the drawing.
    # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    @staticmethod
    def pareto_scatter(
        front: np.ndarray,
        dominated: np.ndarray,
        x_index: int,
        y_index: int,
        labels: Sequence[str],
        connect: bool = False,
    ) -> str:
        """
        Scatter one pair of objectives, front against dominated solutions.

        Dominated points stay in a neutral ink rather than a second series color:
        they are context, not a category worth competing for attention. Front points
        carry a surface-colored ring so overlapping markers remain countable.

        The connecting line is opt-in and correct only for a genuinely two-objective
        problem, where the front really is a monotone curve. With three or more
        objectives this chart is a projection: two strategies adjacent here can be far
        apart on the objective that is not shown, so joining them would draw a
        relationship that does not exist.

        :param front: Non-dominated objectives, shape (num_front, num_objectives).
        :param dominated: Dominated objectives, shape (num_dominated, num_objectives).
        :param x_index: Objective plotted horizontally.
        :param y_index: Objective plotted vertically.
        :param labels: Display name per objective.
        :param connect: Whether to join front points into a curve.
        :return: A complete <svg> element.
        """
        width: int = SvgCharts.PLOT_WIDTH
        height: int = SvgCharts.PLOT_HEIGHT
        everything: np.ndarray = np.vstack([front, dominated]) if dominated.size else front

        x_values: np.ndarray = everything[:, x_index]
        y_values: np.ndarray = everything[:, y_index]
        x_pad: float = (x_values.max() - x_values.min()) * 0.08 or 0.5
        y_pad: float = (y_values.max() - y_values.min()) * 0.08 or 0.5

        x_scale = LinearScale(
            x_values.min() - x_pad, x_values.max() + x_pad, SvgCharts.MARGIN_LEFT, width - SvgCharts.MARGIN_RIGHT
        )
        y_scale = LinearScale(
            y_values.min() - y_pad, y_values.max() + y_pad, height - SvgCharts.MARGIN_BOTTOM, SvgCharts.MARGIN_TOP
        )

        parts: list[str] = [SvgCharts._axes(x_scale, y_scale, labels[x_index], labels[y_index], width, height)]
        x_label: str = html.escape(labels[x_index])
        y_label: str = html.escape(labels[y_index])

        for row in dominated:
            parts.append(
                f'<circle cx="{x_scale.place(row[x_index]):.1f}" cy="{y_scale.place(row[y_index]):.1f}" r="3.5" '
                f'class="dominated"><title>dominated — {x_label} '
                f"{SvgCharts.format_number(row[x_index])}, {y_label} "
                f"{SvgCharts.format_number(row[y_index])}</title></circle>"
            )

        # Draw the front last so it is never buried under the cloud of dominated points.
        order: np.ndarray = np.argsort(front[:, x_index])
        if connect:
            trace: str = " ".join(
                f"{x_scale.place(front[i, x_index]):.1f},{y_scale.place(front[i, y_index]):.1f}" for i in order
            )
            parts.append(f'<polyline points="{trace}" class="front-line"/>')

        for position, index in enumerate(order):
            row: np.ndarray = front[index]
            parts.append(
                f'<circle cx="{x_scale.place(row[x_index]):.1f}" cy="{y_scale.place(row[y_index]):.1f}" r="5" '
                f'class="front"><title>strategy {position + 1} — {x_label} '
                f"{SvgCharts.format_number(row[x_index])}, {y_label} "
                f"{SvgCharts.format_number(row[y_index])}</title></circle>"
            )

        return SvgCharts._svg(width, height, parts)

    # pylint: disable=too-many-locals
    @staticmethod
    def parallel_coordinates(front: np.ndarray, labels: Sequence[str], highlight: int | None = None) -> str:
        """
        Show every front solution as a line across all objectives at once.

        Where the scatter shows one pair, this shows the whole trade-off: a line that
        sits high on one axis and low on the next is a strategy making exactly that
        exchange. Each axis is normalized to its own range because the objectives are
        in different units.

        :param front: Non-dominated objectives, shape (num_front, num_objectives).
        :param labels: Display name per objective.
        :param highlight: Optional row index drawn in the second series color and labelled.
        :return: A complete <svg> element.
        """
        num_objectives: int = front.shape[1]
        # Sized close to its rendered width. An SVG scaled up from a small viewBox
        # scales its type with it, which is what turns 12px axis labels into headlines.
        width: int = max(SvgCharts.WIDE_WIDTH, 220 * num_objectives)
        height: int = 360

        plot_top: int = SvgCharts.MARGIN_TOP
        plot_bottom: int = height - SvgCharts.MARGIN_BOTTOM
        axis_x: np.ndarray = np.linspace(SvgCharts.MARGIN_LEFT, width - SvgCharts.MARGIN_RIGHT, num_objectives)

        low: np.ndarray = front.min(axis=0)
        high: np.ndarray = front.max(axis=0)
        span: np.ndarray = np.where((high - low) < 1e-12, 1.0, high - low)

        parts: list[str] = []
        for index, position in enumerate(axis_x):
            # The outermost axes sit on the plot edges, so centred labels would run off
            # the canvas and be clipped. Anchor those two inward instead.
            if index == 0:
                anchor: str = "start"
            elif index == num_objectives - 1:
                anchor = "end"
            else:
                anchor = "middle"

            parts.append(
                f'<line x1="{position:.1f}" y1="{plot_top}" x2="{position:.1f}" y2="{plot_bottom}" class="axis"/>'
            )
            parts.append(
                f'<text x="{position:.1f}" y="{plot_bottom + 22}" class="axis-title" text-anchor="{anchor}">'
                f"{html.escape(labels[index])}</text>"
            )
            parts.append(
                f'<text x="{position:.1f}" y="{plot_top - 8}" class="tick" text-anchor="{anchor}">'
                f"{html.escape(SvgCharts.format_number(high[index]))}</text>"
            )
            parts.append(
                f'<text x="{position:.1f}" y="{plot_bottom + 38}" class="tick" text-anchor="{anchor}">'
                f"{html.escape(SvgCharts.format_number(low[index]))}</text>"
            )

        for index, row in enumerate(front):
            if index == highlight:
                continue
            points: str = SvgCharts._line_points((row - low) / span, axis_x, plot_top, plot_bottom)
            parts.append(
                f'<polyline points="{points}" class="pc-line">'
                f"<title>strategy {index + 1} — {html.escape(SvgCharts._row_summary(row, labels))}</title></polyline>"
            )

        if highlight is not None and 0 <= highlight < front.shape[0]:
            row = front[highlight]
            normalized: np.ndarray = (row - low) / span
            points = SvgCharts._line_points(normalized, axis_x, plot_top, plot_bottom)
            parts.append(
                f'<polyline points="{points}" class="pc-line-highlight">'
                f"<title>balanced pick — {html.escape(SvgCharts._row_summary(row, labels))}</title></polyline>"
            )
            # Anchored to the line's own right-hand end, clear of the axis maxima
            # printed along the top edge.
            end_y: float = plot_bottom - normalized[-1] * (plot_bottom - plot_top)
            parts.append(
                f'<text x="{axis_x[-1] - 8:.1f}" y="{end_y - 10:.1f}" class="direct-label" text-anchor="end">'
                f"balanced pick</text>"
            )

        return SvgCharts._svg(width, height, parts)

    @staticmethod
    def convergence(history: Sequence[float]) -> str:
        """
        Plot archived hypervolume against generation.

        This is the run's own evidence that the search made progress. Because the
        archive only ever grows, the curve can only rise; a curve that flattens early
        says the extra generations bought nothing.

        :param history: Hypervolume after each generation.
        :return: A complete <svg> element.
        """
        values: np.ndarray = np.asarray(list(history), dtype=float)
        width: int = SvgCharts.WIDE_WIDTH
        height: int = 260
        if values.size == 0:
            return SvgCharts._svg(width, height, [])

        generations: np.ndarray = np.arange(1, values.size + 1)
        y_pad: float = (values.max() - values.min()) * 0.1 or 0.5

        x_scale = LinearScale(1, max(values.size, 2), SvgCharts.MARGIN_LEFT, width - SvgCharts.MARGIN_RIGHT)
        y_scale = LinearScale(
            values.min() - y_pad, values.max() + y_pad, height - SvgCharts.MARGIN_BOTTOM, SvgCharts.MARGIN_TOP
        )

        parts: list[str] = [SvgCharts._axes(x_scale, y_scale, "generation", "hypervolume", width, height)]
        trace: str = " ".join(
            f"{x_scale.place(generations[i]):.1f},{y_scale.place(values[i]):.1f}" for i in range(values.size)
        )
        parts.append(f'<polyline points="{trace}" class="series-line"/>')

        # Direct-label the end point only; a number on every point would be noise.
        end_x: float = x_scale.place(generations[-1])
        end_y: float = y_scale.place(values[-1])
        parts.append(f'<circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="5" class="front"/>')
        parts.append(
            f'<text x="{end_x - 8:.1f}" y="{end_y - 12:.1f}" class="direct-label" text-anchor="end">'
            f"{html.escape(SvgCharts.format_number(values[-1]))}</text>"
        )
        return SvgCharts._svg(width, height, parts)

    @staticmethod
    def nice_ticks(low: float, high: float, target_count: int = 5) -> list[float]:
        """
        Choose readable axis tick values covering a range.

        Steps are snapped to 1, 2 or 5 times a power of ten, which is what makes
        axis labels land on round numbers a reader can hold in their head.

        :param low: Lowest value that must be covered.
        :param high: Highest value that must be covered.
        :param target_count: Rough number of ticks wanted.
        :return: Ascending tick values spanning at least [low, high].
        """
        if not np.isfinite(low) or not np.isfinite(high) or high <= low:
            return [low, low + 1.0] if np.isfinite(low) else [0.0, 1.0]

        raw_step: float = (high - low) / max(target_count, 1)
        magnitude: float = 10.0 ** np.floor(np.log10(raw_step))
        step: float = 10.0 * magnitude
        for multiple in (1.0, 2.0, 5.0):
            if raw_step <= multiple * magnitude:
                step = multiple * magnitude
                break

        ticks: list[float] = []
        value: float = np.floor(low / step) * step
        while value < high + step * 0.5:
            # Snap away floating point dust so labels read as round numbers.
            ticks.append(float(round(value, 10)))
            value += step
        return ticks

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    @staticmethod
    def _axes(
        x_scale: LinearScale,
        y_scale: LinearScale,
        x_label: str,
        y_label: str,
        width: int,
        height: int,
    ) -> str:
        """
        Render recessive gridlines, ticks and axis titles.

        :param x_scale: Horizontal scale.
        :param y_scale: Vertical scale.
        :param x_label: Title under the horizontal axis.
        :param y_label: Title beside the vertical axis.
        :param width: Full SVG width.
        :param height: Full SVG height.
        :return: SVG fragment.
        """
        parts: list[str] = []
        plot_left: int = SvgCharts.MARGIN_LEFT
        plot_right: int = width - SvgCharts.MARGIN_RIGHT
        plot_top: int = SvgCharts.MARGIN_TOP
        plot_bottom: int = height - SvgCharts.MARGIN_BOTTOM

        for tick in SvgCharts.nice_ticks(*y_scale.get_domain()):
            position: float = y_scale.place(tick)
            if not plot_top - 1 <= position <= plot_bottom + 1:
                continue
            parts.append(
                f'<line x1="{plot_left}" y1="{position:.1f}" x2="{plot_right}" y2="{position:.1f}" class="grid"/>'
            )
            parts.append(
                f'<text x="{plot_left - 10}" y="{position + 4:.1f}" class="tick" text-anchor="end">'
                f"{html.escape(SvgCharts.format_number(tick))}</text>"
            )

        for tick in SvgCharts.nice_ticks(*x_scale.get_domain()):
            position = x_scale.place(tick)
            if not plot_left - 1 <= position <= plot_right + 1:
                continue
            parts.append(
                f'<line x1="{position:.1f}" y1="{plot_top}" x2="{position:.1f}" y2="{plot_bottom}" class="grid"/>'
            )
            parts.append(
                f'<text x="{position:.1f}" y="{plot_bottom + 20}" class="tick" text-anchor="middle">'
                f"{html.escape(SvgCharts.format_number(tick))}</text>"
            )

        parts.append(f'<line x1="{plot_left}" y1="{plot_bottom}" x2="{plot_right}" y2="{plot_bottom}" class="axis"/>')
        parts.append(f'<line x1="{plot_left}" y1="{plot_top}" x2="{plot_left}" y2="{plot_bottom}" class="axis"/>')

        middle_y: float = (plot_top + plot_bottom) / 2
        parts.append(
            f'<text x="{(plot_left + plot_right) / 2:.1f}" y="{height - 8}" class="axis-title" '
            f'text-anchor="middle">{html.escape(x_label)}</text>'
        )
        parts.append(
            f'<text x="16" y="{middle_y:.1f}" class="axis-title" text-anchor="middle" '
            f'transform="rotate(-90 16 {middle_y:.1f})">{html.escape(y_label)}</text>'
        )
        return "".join(parts)

    @staticmethod
    def _line_points(normalized: np.ndarray, axis_x: np.ndarray, plot_top: int, plot_bottom: int) -> str:
        """
        Place one normalized row on the parallel-coordinate axes.

        :param normalized: Row values scaled to [0, 1] per objective.
        :param axis_x: Horizontal position of each objective's axis.
        :param plot_top: Pixel position of a normalized 1.
        :param plot_bottom: Pixel position of a normalized 0.
        :return: SVG polyline points.
        """
        return " ".join(
            f"{axis_x[i]:.1f},{plot_bottom - normalized[i] * (plot_bottom - plot_top):.1f}"
            for i in range(normalized.shape[0])
        )

    @staticmethod
    def _row_summary(row: np.ndarray, labels: Sequence[str]) -> str:
        """
        :param row: Objective values of one strategy.
        :param labels: Display name per objective.
        :return: "name value" pairs for a tooltip, unescaped.
        """
        return ", ".join(f"{labels[i]} {SvgCharts.format_number(row[i])}" for i in range(row.shape[0]))

    @staticmethod
    def _svg(width: int, height: int, parts: list[str]) -> str:
        """
        :param width: viewBox width.
        :param height: viewBox height.
        :param parts: SVG fragments to wrap.
        :return: A complete <svg> element.
        """
        return f'<svg viewBox="0 0 {width} {height}" role="img" class="chart">{"".join(parts)}</svg>'
