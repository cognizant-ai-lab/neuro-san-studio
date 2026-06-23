# rule_based_ai_underwriting_system (Experiment 2 — grounded)

This agent network runs the AI Underwriter pipeline **grounded on three real local
files** (no demo mode, nothing fabricated):

| File | Role |
| --- | --- |
| `all_flowcharts.json` | Rule base — 9 flowcharts; nodes = conditions, edges = branch logic, terminal nodes = decisions (`STANDARD`/`REFER`/`DECLINE` → `DECISION_*`). |
| `desicion_question.json` | 500 cases; each has `questions[]` and historical `decisions[]` (ground truth). |
| `question_wording.json` | `tag → question_line_name → definition → [{question_text, question_help_text}]` for explanations. |

The grounded coded tool [`underwriting_data_tool.py`](underwriting_data_tool.py)
exposes `UnderwritingDataTool` with these read-only operations: `load_rules`,
`list_cases`, `get_case`, `get_wording`, `unmatched_line_names`. It never writes files.

## How to run

From the repository root:

```bash
python -m neuro_san_studio run
```

Then select `rule_based_ai_underwriting_system` and try an example query against a
real `enquiry_id` from `desicion_question.json`:

> Run an end-to-end underwriting decision for enquiry_id
> `001dfd11d26b4a1da164fa322f6e562d`: read its questions, match answers to the
> matching flowchart's nodes/edges, walk to a terminal decision
> (STANDARD/REFER/DECLINE → DECISION_*), and return the final decision with
> reasoning chain, rules used (flowchart + node ids), confidence, audit log, and a
> comparison against the case's recorded `decisions[]`.

Standalone sanity check of the data tool (prints rule/case counts; writes nothing):

```bash
PYTHONPATH=coded_tools python -m generated.rule_based_ai_underwriting_system.underwriting_data_tool
```

## Pipeline

`uw_pipeline_orchestrator` → `uw_manual_reader_agent` (extract flowchart rules) →
`condition_matcher_agent` (match case answers to node/edge conditions) →
`decision_engine_agent` (walk to a terminal decision, compare to historical
`decisions[]`) → `explanation_generator_agent` (render explanation using
`question_wording.json`).

## Unmapped question_line_names

Four case `question_line_name` values have **no** flowchart and are reported as
unmapped (never guessed): `Occupation_Casual`, `Occupation_HoursWorked`,
`Retail_Initial_Inputs`, `Revive_Occ_Income`. The other five map to flowcharts
(`Occupation_Contractor`, `Occupation_ContractorExpire`, `Occupation_Employee`,
`Occupation_IntendSelfEmp`, and `Occupation_WorkingContinuous` →
`Occupation_WorkingConti` via fuzzy stem matching).
