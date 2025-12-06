# Insurance Underwriting Assistant

The **Insurance Underwriting Assistant** is a modular multi-agent framework designed to automate underwriting and claims workflows for Hartford's business insurance operations. It replicates the functions of a real-world insurance operations desk, seamlessly coordinating across multiple teams and performing the roles of various operational units. Key capabilities include ACORD form validation, risk assessment, underwriting decision generation, and claims intake.

The system is currently running in demo mode, demonstrating how agents would work together to process insurance workflows once connected to live data.

---

## File

[insurance_underwriting_agents.hocon](../../../registries/industry/insurance_underwriting_agents.hocon)

---

## Description

This network has a Front Man agent that serves as the main interface for business insurance operations. Users submit requests in plain language, and the assistant determines the task and the best course of action to complete it. For example, a risk evaluation request is broken down into subtasks such as property verification, hazard assessment, and risk scoring, which are assigned to specialized agents or sub-agents, who may further delegate them to downstream agents. If additional information is needed, the Front Man prompts the user for input and then gathers all relevant agent responses into a complete, final answer delivered to the user.

- **Domain Expertise Delegation**: The system routes each part of an inquiry to agents with expertise in that area. Agents work independently or delegate tasks to downstream agents, ensuring that each workflow step is handled efficiently and accurately.

- **Human-like Dialogue Management**:
The assistant communicates with users through a natural language interface (the Front Man) while managing agent collaboration in the background. All responses are presented in plain language without insurance jargon, making complex processes easier to understand and follow. This guidance helps users complete tasks, identify and resolve issues in their application or profile, and follow a step-by-step roadmap to navigate insurance workflows.

- **Coordinated Workflow Execution**:
The Front Man agent, sub-agents, and downstream agents communicate seamlessly to transfer information and, when needed, request additional details from the user. This approach eliminates the manual coordination that would otherwise be required between teams, significantly improving the speed of task execution.

- **Reliable and Policy-Compliant Decisions**:
Core processes such as claims intake, investigation, and underwriting decision-making are fully automated. This automation minimizes manual errors and oversights, ensures data-backed and consistent outcomes across all users, and keeps decisions aligned with Hartford’s business policies. As a result, overall operational efficiency improves, and turnaround times are reduced.

---

## Example Conversations

### Example 1
#### Human

```text
How does the underwriting process work for business insurance policies at Hartford?
```

#### AI (Airline Policy 360 Assistant)

```text
The underwriting process for business insurance policies at Hartford involves several detailed steps to ensure effective risk assessment and management. Here's an overview:

1. **Data Retrieval**: Gathering all necessary data related to the business seeking insurance.
2. **Category Assignment**: Classifying the business into appropriate categories for risk assessment.
3. **Exposure Analysis**: Evaluating the risk exposures associated with the business operations.
4. **Impact Projection**: Projecting potential impacts of identified risks on the business and the insurance portfolio.
5. **Portfolio Balance Check**: Ensuring that the new policy maintains balance within Hartford's existing insurance portfolio.
6. **Alerts and Recommendations**: Generating alerts and providing recommendations based on the risk analysis.
7. **Documentation**: Compiling an underwriting summary or narrative to document the decision-making process.
8. **Compliance Verification**: Checking that all steps comply with regulatory and company standards.

This comprehensive process ensures that Hartford effectively assesses and manages risks associated with insuring various business entities.
```

### Example 2
#### Human

```text
Can you provide a breakdown of the approved coverage and limits for claim ID 67890
```

#### AI (Airline Policy 360 Assistant)

```text
To provide a breakdown of the approved coverage and limits for claim ID 67890, the following actions have been taken:

1. Accessed the details of claim ID 67890.
2. Reviewed the associated policy terms and conditions.
3. Verified the coverage limits and any applicable exclusions.
4. Calculated the applicable deductibles.

Here is the breakdown of the approved coverage and limits:

- **Coverage Type:** Comprehensive
- **Coverage Limit:** $30,000
- **Deductible:** $500
- **Exclusions:** None applicable
- **Additional Notes:** All standard policy terms apply.

If you need further details or have additional questions, feel free to ask!
```

---

## Architecture Overview

### Frontman Agent: `insurance_agent`

- Acts as the main entry point for all business insurance inquiries for Hartford.
- Interprets user requests and routes them to the appropriate sub-agents.
- Coordinates downstream agents to complete multi-step workflows and return final responses.

---

### Primary Domains (Tools called by the Frontman)

1. **Underwriting_Decision_Agent**

- Manages underwriting operations including submission intake, risk analysis, and underwriting decision generation.
- Delegates to:
  - `insurance_broker_agent`
    - Handles broker submissions, manages feedback, and communicates underwriting decisions.
    - Delegates to:
      - `acord_application_handler` - Validates ACORD applications for completeness, consistency, and compliance.
      - `loss_analysis_handler` - Reviews loss history to identify patterns, calculate loss ratios, and flag risks.
  - `third_party_data_review_agent`
    - Collects and consolidates external risk data, including building, environmental, and regulatory information.
    - Delegates to:
      - `building_characteristics_reviewer` - Evaluates building structure, fire safety, and electrical systems.
      - `risk_condition_reviewer` - Analyzes visual and environmental cues for neighborhood and property risks.
      - `specific_segment_reports_reviewer` - Reviews OSHA records, bankruptcies, liens, and regulatory flags.
      - `valuation_report_handler` - Calculates property valuation based on square footage and market data.
      - `ownership_verification_handler` - Verifies property ownership, chain-of-title, and document authenticity.
  - `underwriter_analysis_agent`
    - Analyzes underwriting data to assess exposure, aggregation, and alignment with portfolio goals.
    - Delegates to:
      - `risk_exposure_analyzer` - Scores exposure to hazards like fire, flood, crime, and environmental risks.
      - `aggregation_checker` - Verifies that risks do not overconcentrate Hartford’s portfolio.
      - `benchmarking_handler` - Benchmarks cases against portfolio trends, pricing, and historical losses.

2. **Claims_Processing_Agent**

- Manages the complete claims lifecycle, from intake to settlement and communication with claimants.
- Delegates to:
  - `claims_intake_handler` - Verifies policy coverage, collects claim details, and assigns a claim ID.
  - `claims_investigation_agent`
    - Investigates claim validity through interviews, third-party reports, and site inspections.
    - Delegates to:
      - `site_inspector` - Performs on-site damage assessments and collects supporting evidence.
      - `report_verification_handler` - Authenticates and validates third-party reports and documents.
  - `claims_adjustment_agent` - Finalizes claim settlements by applying policy terms and coordinating payouts.
 
---
