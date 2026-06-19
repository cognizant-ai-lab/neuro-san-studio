# Underwriting Analytics URE System

## Overview
The `underwriting_analytics_ure_system` network is a grounded analytics system for URE-focused underwriting operations. It routes analytical tasks to specialist agents and produces evidence-based insights from packaged local datasets.

URE here is treated as an underwriting rule and decision effectiveness context, including KPI tracking, rule diagnostics, experimentation, monitoring, and governance.

## Primary Goal
Generate grounded underwriting analytics without external data dependencies, using only packaged artifacts and tool outputs.

## Architecture
The network includes one orchestrator, one controlled file reader, and five specialist agents:

1. `underwriting_analytics_orchestrator`
2. `underwriting_analytics_grounding_reader`
3. `ingestion_agent`
4. `kpi_analytics_agent`
5. `rules_diagnostics_agent`
6. `experiment_design_agent`
7. `monitoring_agent`
8. `governance_agent`

## Orchestration Model
`underwriting_analytics_orchestrator` is responsible for:

1. Reading required artifacts first
2. Routing work to the appropriate specialist
3. Synthesizing only grounded findings
4. Returning evidence-based conclusions

## Grounding and Data Access Rules
The only file access path for local analytics evidence is:

- `coded_tools/generated/underwriting_analytics_ure_system`

The `underwriting_analytics_grounding_reader` enforces extension and path constraints for controlled data access.

Supported file types:

- `.json`
- `.md`
- `.txt`
- `.py`

Blocked file type:

- `.env`

## Core Packaged Artifacts
Primary files used by the network include:

- `coded_tools/generated/underwriting_analytics_ure_system/README.md`
- `coded_tools/generated/underwriting_analytics_ure_system/GROUNDING_SUMMARY.txt`
- `coded_tools/generated/underwriting_analytics_ure_system/underwriting_ure_uplift_dataset.json`
- `coded_tools/generated/underwriting_analytics_ure_system/dataset_1_underwriting_decision_logs.json`
- `coded_tools/generated/underwriting_analytics_ure_system/dataset_2_ure_rule_definitions.json`
- `coded_tools/generated/underwriting_analytics_ure_system/dataset_3_case_attributes.json`
- `coded_tools/generated/underwriting_analytics_ure_system/dataset_4_divergence_scenarios.json`
- `coded_tools/generated/underwriting_analytics_ure_system/dataset_5_rule_impact_feedback_data.json`

## Specialist Agent Responsibilities

### Ingestion Agent
- Describes dataset availability, schema, lineage, and gaps

### KPI Analytics Agent
- Computes and summarizes KPI patterns from packaged data
- Reports bounded qualitative insights when exact metrics are unavailable

### Rules Diagnostics Agent
- Evaluates rule behavior, impact, drift, conflicts, and redundancy
- Anchors recommendations to rule definitions and feedback datasets

### Experiment Design Agent
- Proposes experiments grounded in observed KPI/rule evidence
- Requests missing baselines rather than inventing assumptions

### Monitoring Agent
- Proposes monitoring strategy, alerts, and dashboard dimensions
- Uses conservative defaults when baseline statistics are incomplete

### Governance Agent
- Evaluates privacy, lineage, and compliance implications
- Flags unsupported joins and sensitive-field misuse

## Output Characteristics
Expected outputs are:

- Grounded in packaged artifacts
- Explicit about missing evidence
- Suitable for analytics planning and operational governance

## Runtime Notes
This network includes shared model config via:

- `config/llm_config.hocon`

It is intended to run in environments where local packaged data is the source of truth.

## Suggested Use Cases
- Underwriting KPI and trend reviews
- URE rule optimization analysis
- Controlled A/B and policy experiment planning
- Monitoring and governance readiness assessments
