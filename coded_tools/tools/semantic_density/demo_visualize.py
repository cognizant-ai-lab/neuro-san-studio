#!/usr/bin/env python3
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

"""
Generate t-SNE heatmap visualization for the semantic density demo.

Produces a PNG showing how answers cluster in semantic space,
with confidence scores as a color overlay.
"""

import json
import sys

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from sklearn.manifold import TSNE


# pylint: disable=too-many-locals
def plot_tsne_heatmap(
    answers: list[str],
    distance_matrix: np.ndarray,
    densities: list[float],
    question: str,
    output_path: str = "semantic_density_tsne.png",
):
    """
    Create a t-SNE visualization of answer clusters with density heatmap.

    :param answers: List of answer strings.
    :param distance_matrix: Symmetric distance matrix from NLI.
    :param densities: Per-answer density scores.
    :param question: The original question (for the title).
    :param output_path: File path for the output PNG.
    """
    num_answers = len(answers)

    if num_answers < 2:
        # t-SNE needs at least 2 points
        _, ax = plt.subplots(figsize=(10, 8))
        ax.text(
            0.5,
            0.5,
            f"Only {num_answers} answer — no clustering to visualize",
            ha="center",
            va="center",
            fontsize=14,
        )
        ax.set_title(f"Semantic Density: {question[:60]}", fontsize=12)
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()
        return

    # t-SNE embedding from distance matrix
    perplexity = min(num_answers - 1, 5)
    tsne = TSNE(
        n_components=2,
        metric="precomputed",
        perplexity=perplexity,
        random_state=42,
        init="random",
    )
    embedding = tsne.fit_transform(distance_matrix)

    # Custom colormap: red (low) → yellow (mid) → green (high)
    colors_list = ["#d32f2f", "#ff9800", "#4caf50"]
    cmap = LinearSegmentedColormap.from_list("confidence", colors_list, N=256)

    _, ax = plt.subplots(figsize=(12, 9))

    # Scatter plot with density-based coloring
    scatter = ax.scatter(
        embedding[:, 0],
        embedding[:, 1],
        c=densities,
        cmap=cmap,
        s=300,
        edgecolors="black",
        linewidths=1.5,
        vmin=0,
        vmax=1,
        zorder=5,
    )

    # Annotate each point with truncated answer text
    for i, answer in enumerate(answers):
        truncated = answer[:50] + "..." if len(answer) > 50 else answer
        ax.annotate(
            f"{i + 1}. {truncated}",
            (embedding[i, 0], embedding[i, 1]),
            textcoords="offset points",
            xytext=(10, 10),
            fontsize=8,
            bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "alpha": 0.8},
        )

        # Add density label near the point
        ax.annotate(
            f"d={densities[i]:.3f}",
            (embedding[i, 0], embedding[i, 1]),
            textcoords="offset points",
            xytext=(10, -15),
            fontsize=7,
            color="gray",
        )

    # Draw distance lines between points
    for i in range(num_answers):
        for j in range(i + 1, num_answers):
            dist = distance_matrix[i, j]
            alpha = max(0.1, 1.0 - dist)
            ax.plot(
                [embedding[i, 0], embedding[j, 0]],
                [embedding[i, 1], embedding[j, 1]],
                color="gray",
                alpha=alpha,
                linewidth=0.5,
                zorder=1,
            )

    cbar = plt.colorbar(scatter, ax=ax, shrink=0.8)
    cbar.set_label("Semantic Density Score", fontsize=11)

    ax.set_title(f'Semantic Density Visualization\n"{question[:80]}"', fontsize=13, pad=20)
    ax.set_xlabel("t-SNE Dimension 1", fontsize=10)
    ax.set_ylabel("t-SNE Dimension 2", fontsize=10)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved t-SNE heatmap to {output_path}")


def main():
    """Generate visualization from pre-computed results or live."""
    if len(sys.argv) > 1:
        # Load from pre-computed JSON
        results_path = sys.argv[1]
        with open(results_path, encoding="utf-8") as f:
            all_results = json.load(f)

        for question, result in all_results.items():
            safe_name = question[:30].replace(" ", "_").replace("?", "")
            output_path = f"tsne_{safe_name}.png"
            answers = [entry["answer"] for entry in result["answers_with_scores"]]
            densities = [entry["density"] for entry in result["answers_with_scores"]]
            distance_matrix = np.array(result["distance_matrix"])
            plot_tsne_heatmap(answers, distance_matrix, densities, question, output_path)
    else:
        # Live mode
        from coded_tools.tools.semantic_density.semantic_density_engine import get_engine

        engine = get_engine()
        question = "What is the capital of France?"
        result = engine.evaluate(question)

        answers = [entry["answer"] for entry in result["answers_with_scores"]]
        densities = [entry["density"] for entry in result["answers_with_scores"]]
        distance_matrix = np.array(result["distance_matrix"])
        plot_tsne_heatmap(answers, distance_matrix, densities, question)


if __name__ == "__main__":
    main()
