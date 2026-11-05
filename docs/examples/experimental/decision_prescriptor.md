# Decision Prescriptor

The **Decision Prescriptor** does not answer "what will happen?" It answers "what should we do, and
what does each option cost us?"

It is an agent-network implementation of **Evolutionary Surrogate-assisted Prescription (ESP)**
([Francon et al., 2020](https://doi.org/10.1145/3377930.3389842)): fit a predictor from historical
data, evolve decision policies against that predictor, and return a set of strategies where no option
beats every other on everything at once. The user picks from the set, because that choice encodes what
the objectives are worth to them — and nothing in the mathematics knows that.

---

## File

[decision_prescriptor.hocon](../../../registries/experimental/decision_prescriptor.hocon)

---

## Description

Most agent networks retrieve, summarize or route. This one optimizes. The split of responsibility is
the point:

* **Deterministic Python does everything numeric** — fitting, searching, ranking and drawing.
* **LLM agents frame the problem and explain the result** — they are never asked to produce a number.

That division is not stylistic. A language model asked for "the optimal staffing ratio" will produce a
plausible number, and a plausible number is indistinguishable from a correct one once it is in a
chart. Every figure this network reports came out of a solver.

The network runs in four stages:

| Stage | Agent | What it does |
|---|---|---|
| 1 | `problem_loader` | Records which fields are context, which are decisions, which are outcomes |
| 2 | `surrogate_modeler` | Fits the predictor and reports how well it fits |
| 3 | `strategy_evolver` | Evolves policies and returns the Pareto front |
| 4 | `report_writer` | Renders the charts to a self-contained HTML file |

`tradeoff_explainer` reads the front and puts the trade-off into plain language. `decision_advisor` is
the front man and the only agent the user talks to.

State moves between stages through **`sly_data`**, neuro-san's channel for values that must never enter
an LLM prompt. A fitted model and a thousand candidate strategies belong there: they are large, they
are exact, and passing them as chat text would both blow the context window and risk mangling them.

---

## The method

### Why a surrogate

Evolution needs to score hundreds of thousands of candidate strategies. You cannot try them on a real
business, so you try them on a model fitted from what already happened. That model is the
**surrogate**, and it is the reason the search is affordable at all.

The surrogate here is **ridge regression**, solved in closed form:

```text
coefficients = (XᵀX + αI)⁻¹ XᵀY
```

Chosen deliberately over anything fancier: the solution is exact, reproducible, has no learning rate or
random seed to explain away, and stays finite when features are collinear — which they usually are in
small decision datasets. The intercept is left unpenalized, since shrinking it would bias every
prediction.

The R² per outcome is reported back to the user rather than hidden. **A prescriptor evolved against a
weak surrogate has optimized a bad map of the world**, and the front will look exactly as precise
either way. If any outcome scores below 0.5, the front man is instructed to say so plainly.

### Why evolve the policy

A prescriptor is a small neural network mapping context to action. Its weights are never trained by
gradient descent, because **there are no labels to descend against** — nobody knows the optimal action
for a given context, which is precisely why the problem exists. So the entire weight vector is evolved,
and a candidate is judged by the outcomes the surrogate predicts when its actions are applied across
every historical context.

Evolving a *policy* rather than a fixed action matters: the result responds to circumstances, so a new
situation gets its own action instead of whatever suited the average case.

Actions are squashed through a logistic into the range the historical data actually covers. Outside
that range the surrogate is extrapolating, and its predictions there describe the model rather than the
world.

### Pareto dominance

Strategy A **dominates** B when A is no worse on every objective and strictly better on at least one.
If neither dominates the other, they are incomparable — and that incomparability is the whole finding.
The **Pareto front** is the set nothing dominates.

There is no "best" strategy on a front. Improving any objective requires giving up another. Which trade
is acceptable is a judgement, not a calculation, and the network is instructed never to present one
option as the answer.

### NSGA-II

The search is NSGA-II ([Deb et al., 2002](https://doi.org/10.1109/4235.996017)), implemented directly
in numpy rather than pulled from a library, so the mechanism is inspectable:

* **Fast non-dominated sort** — peel the population into layers. Count how many solutions dominate each
  one, take the zero-count layer as front 0, then decrement and repeat.
* **Crowding distance** — within a front, score each solution by the gap between its neighbours,
  summed across objectives. Extremes score infinity so the honest edges of what is achievable are never
  discarded. This is the diversity pressure that stops the front collapsing onto one corner.
* **Crowded-comparison tournament** — lower front wins; on a tie, the less crowded wins. Selection
  pressure on convergence and diversity at once.
* **SBX crossover and polynomial mutation** — real-valued operators whose spread is controlled by a
  distribution index, so children usually land near their parents.
* **Elitism** — parents and children compete together for the next generation, so a good solution is
  never lost to chance.

### The archive, and why the convergence curve is trustworthy

Progress is measured by **hypervolume**: the volume of objective space the front dominates, bounded by
a fixed reference point. It rewards convergence and spread in one number.

Measuring it on the *population* produces a curve that dips. That is not noise — once front 0 outgrows
the population, NSGA-II's crowding truncation has to discard genuinely non-dominated solutions, and the
measure falls with them.

So the run keeps an **unbounded archive** of every non-dominated solution found. Anything dropped from
the archive was dominated by something that remains, so the region it dominates can only grow, and the
reported curve is **non-decreasing by construction**. A flat tail therefore means the extra generations
genuinely bought nothing.

Hypervolume is computed exactly by a sweep for two objectives. Above that it is estimated by Monte
Carlo against a **fixed** sample set reused for the whole run — re-drawing samples each generation
would make successive estimates differ by sampling noise as well as by real progress, which is enough
to put visible dips in a curve that is supposed to be monotone.

The archive is kept whole for the measurement but **subsampled by crowding distance for display**. A
thousand strategies is not a choice, it is a haystack; the chart shows roughly two dozen that span the
same extent.

---

## The charts

A trade-off front is one of the few results that genuinely cannot be read as a table — the *shape* of
the curve is the finding. Where it is steep, a small concession on one objective buys a large gain on
another. Where it is flat, it does not.

The report is a single self-contained HTML file with no external stylesheet, script or font, so it
reads correctly straight from disk. It contains:

* **Trade-off scatter** — front against dominated solutions, one chart per pair of objectives.
  Dominated points are drawn in a neutral ink because they are context, not a category competing for
  attention. The connecting line appears **only** for a genuinely two-objective problem: with three or
  more, each chart is a projection, and two points adjacent on screen can be far apart on the objective
  that is not shown, so joining them would draw a relationship that does not exist.
* **Parallel coordinates** — every strategy across all objectives at once. A line rising on one axis
  and falling on the next is making exactly that trade.
* **Convergence** — archived hypervolume per generation.
* **A data table** — the accessibility path for the charts, and the way to read exact values.

The two series colors, blue and orange, were checked for colorblind separation and contrast on both
the light and dark surfaces. Dark mode is a selected set of steps, not an inversion, and follows both the
OS setting and an explicit theme toggle.

### Guard rails

The search and the report writer take their arguments from an LLM, so both are bounded:

* `population_size` and `generations` are capped at 500 each, and `hidden_dim` at 32, so one request
  cannot hold the server indefinitely.
* The report is only written inside the server's working directory, and only to a path ending in
  `.html`.

---

## Prerequisites

The only numeric dependency is numpy, which is already part of the repo's core requirements.

No API keys are needed beyond the LLM provider key your `config/llm_config.hocon` already points at. The solver
itself makes no network calls.

---

## Run

Start the Neuro SAN server and the nsflow UI:

```bash
ns run
```

Then select **experimental/decision_prescriptor** from the agent list.

### Try it with no data at all

```text
Run the built-in delivery staffing example and show me the trade-offs.
```

The bundled example is **synthetic on purpose**. The point of the example is the method, and inventing
figures about real companies to dress it up would make the output look like evidence when it is not.

It models delivery staffing across a portfolio of engagements, with two conflicts built in deliberately:

* senior staffing lowers delivery risk but costs margin;
* automation lifts margin but pushes out time to value while it is being set up.

An optimizer that returned a single answer here would be hiding one of those exchanges.

A typical run with the default settings fits the surrogate at R² ≈ 0.97 on all three outcomes and finds
around 1,200 non-dominated strategies in about ten seconds, spanning roughly:

| Outcome | Range across the front |
|---|---|
| margin_pct | 11.0 → 29.7 |
| delivery_risk | 0.21 → 0.63 |
| time_to_value_weeks | 11.1 → 22.5 |

### Use your own data

Supply records plus which fields play which role:

```text
Here are 200 past campaigns. Context is audience_size and season, the decisions are
budget and channel_mix, and I want to maximize conversions while minimizing cost_per_acquisition.
```

Every record must be a flat object of field name to number, and `maximize` needs one entry per outcome.

---

## Sample queries

```text
Run the built-in delivery staffing example and show me the trade-offs.
What are my options if I want margin above 25% without pushing delivery risk past 0.4?
Which strategy gives the best balance between margin, delivery risk and time to value?
Fit the surrogate with alpha 0.1 and evolve for 80 generations, then write the report.
```

---

## Tests

```bash
pytest tests/coded_tools/experimental/decision_prescriptor/ -v
```

The suite avoids asserting on any particular solution, since the search is stochastic. It pins down
what is exactly determined instead: the dominance relation, the front partition, hypervolume on shapes
whose area can be worked out by hand, ridge regression against an independently written closed form,
and convergence against **ZDT1**, a benchmark whose true front is known analytically to be
`f2 = 1 - √f1`. The four coded tools are also run end to end through `sly_data`, the way the front man
drives them.

An integration fixture runs the whole network against a live LLM:

```bash
python -m pytest -s -m "integration_experimental" -k decision_prescriptor
```

---

## Code layout

Everything lives in
[coded_tools/experimental/decision_prescriptor](../../../coded_tools/experimental/decision_prescriptor),
one class per file:

| File | Role |
|---|---|
| `load_decision_problem.py`, `fit_surrogate.py`, `evolve_prescriptors.py`, `render_pareto_report.py` | The four coded tools |
| `decision_keys.py` | The `sly_data` keys the tools share |
| `ridge_surrogate.py`, `training_arrays.py` | The predictor and the records it is fitted from |
| `prescriptor_network.py`, `standardizer.py`, `prescriptor_evaluator.py` | The evolved policy and its objective function |
| `nsga2.py`, `pareto_ranking.py`, `genetic_operators.py`, `hypervolume.py` | The search |
| `svg_charts.py`, `linear_scale.py`, `pareto_report.py` | The HTML report |
| `sample_data.py` | The synthetic example |
