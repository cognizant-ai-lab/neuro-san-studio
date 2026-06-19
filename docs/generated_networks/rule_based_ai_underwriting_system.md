# Rule-Based AI Underwriting System

## Overview
The `rule_based_ai_underwriting_system` network is a grounded, deterministic underwriting pipeline. It reads underwriting guidance, maps rules to explicit case attributes, computes a decision, and generates an audit-ready explanation.

This network is designed for traceability-first underwriting workflows where every outcome must be reproducible from the provided case data and cited manual rules.

## Primary Goal
Produce a final underwriting decision from structured case data and underwriting manual content, with full explainability and strict rule citation.

## Architecture
The network is composed of five tools/agents:

1. `uw_pipeline_orchestrator`
2. `underwriting_grounding_reader`
3. `uw_manual_reader_agent`
4. `condition_matcher_agent`
5. `decision_engine_agent`
6. `explanation_generator_agent`

## End-to-End Flow
The orchestrator enforces this execution sequence:

1. Manual extraction (`uw_manual_reader_agent`)
2. Rule-to-case matching (`condition_matcher_agent`)
3. Decision computation (`decision_engine_agent`)
4. Explanation packaging (`explanation_generator_agent`)

A final decision is not returned unless all stages pass validation gates.

## Data Grounding Model
Only these data sources are allowed:

- User-provided underwriting manual content
- User-provided structured case data
- Packaged local artifacts via `underwriting_grounding_reader`

Preferred packaged files:

- `coded_tools/generated/rule_based_ai_underwriting_system/dataset_1_underwriting_manual_rule_base.json`
- `coded_tools/generated/rule_based_ai_underwriting_system/dataset_2_structured_case_data.json`
- `coded_tools/generated/rule_based_ai_underwriting_system/dataset_3_historical_underwriting_decisions.json`
- `coded_tools/generated/rule_based_ai_underwriting_system/dataset_4_rule_to_case_mapping.json`
- `coded_tools/generated/rule_based_ai_underwriting_system/dataset_5_ai_decision_output_expected.json`
- `coded_tools/generated/rule_based_ai_underwriting_system/dataset_6_explainability_audit_trail.json`

No external web or unstated policy knowledge should be used.

## Determinism and Validation
The network requires deterministic behavior:

- Same input should produce the same output.
- Rule IDs and ordering should be stable.
- Decision logic should use fixed precedence.

Mandatory checks include:

- At least one cited underwriting manual rule in matched set
- Rule traceability from extraction to decision
- Decision references only matched rules and explicit case attributes

If citation coverage is missing, the system should return:

- `NO_MANUAL_RULE_REFERENCED`

## Outputs
Expected structured output from the full pipeline includes:

- `final_decision`
- `decision_details`
- `reasoning_chain`
- `rules_used`
- `supporting_case_attributes`
- `historical_comparison` (if input provided)
- `confidence_level`
- `audit_log`

## Error Handling
The network is designed to fail explicitly (not infer) when required data is missing or contradictory.

Representative error codes:

- `NO_MANUAL`
- `NO_MANUAL_RULES`
- `NO_MATCHED_RULES`
- `UNTRACEABLE_RULE`
- `MISSING_CASE_FIELDS`
- `UNRESOLVABLE_CONFLICT`

## Runtime Notes
This network depends on substitutions from:

- `registries/aaosa.hocon`

And shared model configuration from:

- `config/llm_config.hocon`

## Suggested Use Cases
- Rule-driven life/health underwriting decisions
- Underwriting audit and compliance reviews
- Historical decision delta analysis
- Explainable underwriting demonstrations
