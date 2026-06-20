"""
Comprehensive README documenting the grounded underwriting analytics agentic network.
"""

README = """
# Underwriting Analytics Agentic Network - Grounded Implementation

## Overview

This directory contains a grounded, data-backed implementation of the underwriting analytics agentic network 
defined in `underwriting_analytics_ure_system.hocon`. The network consists of 7 specialized agents that work 
together to analyze URE (Underwriting Rules Engine) performance and generate actionable recommendations.

## Network Architecture

### 7 Specialized Agents (All Kept, Grounded in Data):

1. **Ingestion Agent** (`ingestion_agent.py`)
   - Purpose: Load, validate, normalize, and curate raw datasets
   - Grounding: Loads from actual JSON datasets with schema validation and quality checks
   - Methods:
     - `ingest_and_curate_decision_logs()` - Process underwriting decisions
     - `ingest_and_curate_ure_rules()` - Process rule definitions
     - `ingest_and_curate_case_attributes()` - Process applicant attributes
     - `ingest_and_curate_divergences()` - Process human vs URE divergences
     - `ingest_and_curate_rule_impact()` - Process rule impact feedback
     - `publish_quality_report()` - Generate data quality report

2. **KPI Analytics Agent** (`kpi_analytics_agent.py`)
   - Purpose: Compute and segment underwriting KPIs
   - Grounding: Uses curated decision logs to calculate metrics
   - Methods:
     - `compute_approval_rate()` - Compute approval rate with optional segmentation
     - `compute_decline_rate()` - Compute decline rate
     - `compute_referral_rate()` - Compute manual review referral rate
     - `compute_human_ure_alignment()` - Compute decision alignment
     - `generate_kpi_pack()` - Generate comprehensive KPI pack
     - `analyze_age_segments()` - Segment by age groups
     - `analyze_condition_segments()` - Segment by medical condition

3. **Rules Diagnostics Agent** (`rules_diagnostics_agent.py`)
   - Purpose: Analyze rule firing patterns and propose optimizations
   - Grounding: Uses rule definitions and impact feedback data
   - Methods:
     - `analyze_rule_impact_on_decisions()` - Quantify rule impact
     - `detect_rule_conflicts_and_redundancies()` - Find problematic patterns
     - `identify_divergence_patterns()` - Analyze human-URE divergences
     - `rank_rules_for_optimization()` - Prioritize rules for improvement
     - `propose_rule_optimizations()` - Generate specific candidates
     - `generate_diagnostics_report()` - Comprehensive rule analysis

4. **Experiment Design Agent** (`experiment_design_agent.py`)
   - Purpose: Design safe, statistically sound experiments
   - Grounding: Uses KPI and diagnostics outputs for experiment parameters
   - Methods:
     - `design_rule_change_experiment()` - Design A/B test for rule changes
     - `design_shadow_mode_experiment()` - Design shadow mode observation
     - `design_canary_rollout()` - Design staged rollout
     - `estimate_sample_size()` - Calculate statistical power requirements
     - `generate_experiment_brief()` - Create experiment specification

5. **Monitoring Agent** (`monitoring_agent.py`)
   - Purpose: Define monitoring, alerting, and dashboard specifications
   - Grounding: Uses dataset manifests and established metrics
   - Methods:
     - `create_kpi_monitors()` - Create KPI monitoring specs
     - `create_data_quality_monitors()` - Create data quality checks
     - `create_rule_drift_monitors()` - Create rule stability monitoring
     - `create_experiment_monitoring_plan()` - Setup experiment observability
     - `create_dashboard_spec()` - Generate dashboard specifications
     - `create_alerting_rules()` - Define alerting thresholds

6. **Governance Agent** (`governance_agent.py`)
   - Purpose: Ensure privacy, security, and regulatory compliance
   - Grounding: Validates against allowed fields and aggregation policies
   - Methods:
     - `review_analysis_for_compliance()` - Compliance review
     - `validate_lineage()` - Data lineage validation
     - `review_experiment_for_fairness()` - Fairness impact analysis
     - `approve_data_export()` - Data export approval with controls
     - `generate_compliance_checklist()` - Production readiness checklist
     - `get_allowed_fields_policy()` - Get governance policy

7. **Orchestrator Agent** (`orchestrator_agent.py`)
   - Purpose: Coordinate all agents, manage dependencies, synthesize results
   - Grounding: Integrates all other agents and curated data
   - Methods:
     - `ingest_and_prepare_data()` - Execute Phase 1 (ingestion)
     - `compute_kpi_analytics()` - Execute Phase 2 (KPI analysis)
     - `diagnose_rules_and_identify_optimizations()` - Execute Phase 3 (diagnostics)
     - `design_experiments()` - Execute Phase 4 (experiment design)
     - `setup_monitoring_and_alerts()` - Execute Phase 5 (monitoring)
     - `execute_governance_review()` - Execute Phase 6 (governance)
     - `execute_full_workflow()` - Execute all 6 phases in sequence
     - `synthesize_results()` - Generate synthesis with citations

## Data Grounding

### Available Datasets (Automatically Loaded)

1. **dataset_1_underwriting_decision_logs.json**
   - Case-level underwriting decisions (human vs URE)
   - Fields: case_id, applicant_age, occupation, condition, severity, decisions, reasons, decision_date

2. **dataset_2_ure_rule_definitions.json**
   - URE rule specifications
   - Fields: rule_id, rule_name, condition, criteria, decision, load_percentage

3. **dataset_3_case_attributes.json**
   - Detailed case/applicant attributes
   - Fields: case_id, age, gender, occupation, condition, severity, income_band, policy_type

4. **dataset_4_divergence_scenarios.json**
   - Cases where human and URE decisions diverged
   - Fields: case_id, human_decision, ure_decision, divergence_reason, explanation

5. **dataset_5_rule_impact_feedback_data.json**
   - Rule impact analysis and feedback
   - Fields: rule_id, cases_affected, accuracy, projected_accuracy, manual_review_reduction, uplift, confidence

6. **underwriting_ure_uplift_dataset.json**
   - Potential uplift scenarios and improvements

### Data Models (`data_models.py`)

All data is represented through strongly-typed Python dataclasses:
- `UnderwritingDecisionLog` - Decision records
- `URERule` - Rule definitions
- `CaseAttribute` - Case attributes
- `DivergenceScenario` - Divergence cases
- `RuleImpactAnalysis` - Rule impact data
- `KPIResult` - KPI calculation results
- `ExperimentBrief` - Experiment specifications
- `MonitoringSpec` - Monitoring specifications
- `GovernanceApproval` - Compliance approvals

### Data Loading (`data_loader.py`)

The `DataLoader` class:
- Loads from JSON files with validation
- Performs schema normalization
- Runs data quality checks (completeness, duplicates, type consistency)
- Generates versioned ingestion manifests with lineage

## Usage

### Quick Start

```python
from orchestrator_agent import OrchestratorAgent

# Initialize orchestrator
orchestrator = OrchestratorAgent()

# Execute complete workflow
results = orchestrator.execute_full_workflow()

# Access results
kpi_pack = results['kpi_analytics']
diagnostics = results['rule_diagnostics']
experiments = results['experiments']
monitoring = results['monitoring']
governance = results['governance']
synthesis = results['synthesis']
```

### Individual Agent Usage

```python
# Use ingestion agent
ingestion = IngestionAgent()
decision_logs, manifest = ingestion.ingest_and_curate_decision_logs()

# Use KPI agent
kpi_agent = KPIAnalyticsAgent()
approval_rate = kpi_agent.compute_approval_rate(decision_logs)
kpi_pack = kpi_agent.generate_kpi_pack(decision_logs)

# Use rules agent
rules_agent = RulesDiagnosticsAgent()
diagnostics = rules_agent.generate_diagnostics_report(decision_logs, rules, rule_impacts)

# Use experiment agent
experiment_agent = ExperimentDesignAgent()
brief = experiment_agent.design_rule_change_experiment(rule_id="R-001", ...)

# Use monitoring agent
monitoring_agent = MonitoringAgent()
kpi_monitors = monitoring_agent.create_kpi_monitors()
dashboard = monitoring_agent.create_dashboard_spec()

# Use governance agent
governance_agent = GovernanceAgent()
approval = governance_agent.review_analysis_for_compliance(...)
checklist = governance_agent.generate_compliance_checklist()
```

## Workflow Phases

### Phase 1: Data Ingestion & Curation
- Load all 6 datasets
- Validate schemas and types
- Run quality checks
- Generate ingestion manifests with lineage
- Output: Curated datasets + quality reports

### Phase 2: KPI Analytics
- Compute approval/decline/referral/load rates
- Calculate human-URE alignment
- Segment by age, condition, income
- Analyze trends and distributions
- Output: KPI pack with segmentations

### Phase 3: Rule Diagnostics & Optimization
- Analyze rule firing patterns
- Detect conflicts and redundancies
- Identify divergence patterns
- Rank rules for optimization
- Propose specific change candidates
- Output: Diagnostics report with ranked rules

### Phase 4: Experiment Design
- For top optimization candidates:
  - Design A/B test specifications
  - Calculate sample sizes
  - Define guardrails and stop conditions
  - Specify analysis plans
- Output: Experiment briefs with rollout schedules

### Phase 5: Monitoring & Alerting
- Define KPI monitoring specs with thresholds
- Create data quality monitors
- Design rule drift detection
- Specify dashboard requirements
- Define alerting rules with escalation
- Output: Monitoring specification package

### Phase 6: Governance & Compliance
- Review analysis for PII and aggregation
- Validate data lineage and purpose limitation
- Evaluate fairness and non-discrimination
- Generate compliance checklist
- Output: Approvals and policy documents

## Key Features

✓ **All 7 Agents Retained** - No agents removed; all grounded in available data
✓ **Grounded in Real Data** - Uses actual JSON datasets, not mock/demo data
✓ **Schema Validation** - Strong typing with dataclasses for all data models
✓ **Quality Checks** - Completeness, duplicates, type consistency validation
✓ **Data Lineage** - Tracks sources and transformations through manifests
✓ **Privacy by Design** - Governance agent enforces PII minimization and aggregation thresholds
✓ **End-to-End Orchestration** - Single entry point executes all 6 phases with dependencies
✓ **Results Synthesis** - Final synthesis includes citations to source agents

## File Structure

```
underwriting_analytics_ure_system/
├── __init__.py                    # Package exports
├── data_models.py                 # Dataclass definitions for all domain objects
├── data_loader.py                 # DataLoader for JSON ingestion and validation
├── ingestion_agent.py             # Ingestion agent implementation
├── kpi_analytics_agent.py         # KPI analytics agent implementation
├── rules_diagnostics_agent.py     # Rules diagnostics agent implementation
├── experiment_design_agent.py     # Experiment design agent implementation
├── monitoring_agent.py            # Monitoring agent implementation
├── governance_agent.py            # Governance agent implementation
├── orchestrator_agent.py          # Orchestrator agent implementation
├── example_usage.py               # Example script showing full workflow
└── [JSON datasets from parent folder]
    ├── dataset_1_underwriting_decision_logs.json
    ├── dataset_2_ure_rule_definitions.json
    ├── dataset_3_case_attributes.json
    ├── dataset_4_divergence_scenarios.json
    ├── dataset_5_rule_impact_feedback_data.json
    └── underwriting_ure_uplift_dataset.json
```

## Configuration

The governance agent defines default policies for:
- **Allowed Fields**: Predefined list of fields for analytics (PII minimization)
- **Minimum Aggregation Threshold**: K-anonymity of 10 (cell suppression below threshold)
- **Retention Days**: 365 days for curated datasets
- **Approved Purposes**: URE improvement, rule optimization, QA, compliance monitoring

Policies are enforced in the governance review phase.

## Examples

See `example_usage.py` for a complete example showing:
1. Initializing the orchestrator
2. Executing the full workflow
3. Accessing and printing results from each phase
4. Exporting results to JSON

Run with:
```bash
python example_usage.py
```

## Extensibility

To add new functionality:
1. Add data models to `data_models.py`
2. Create new agent class with methods implementing specific responsibilities
3. Update `OrchestratorAgent` to coordinate new agent in workflow
4. Add new methods to `DataLoader` if new data sources are needed

## Performance Considerations

- Data is loaded into memory once during ingestion phase
- All agents operate on curated, in-memory datasets
- No direct database queries; all grounded in loaded data
- Suitable for typical underwriting volumes (10K-100K cases)

## Limitations

- Datasets must be available as JSON files in the specified directory
- Outcome lag data (bind, loss, claims) not included in current datasets
- Historical trend analysis limited to single snapshot of data
- Customer feedback data not available in current datasets

## Next Steps

After using this grounded network:
1. Load experiment results from A/B tests
2. Feed experiment results back to agents for iterative optimization
3. Integrate with production monitoring dashboards
4. Establish feedback loops for continuous improvement

---

Created: 2026-06-19
Version: 1.0
All agents grounded in attached data | No agents removed | Full workflow implemented
"""

if __name__ == "__main__":
    print(README)
