# Neuro-SAN Broker Submission Readiness Checker

## 1. Business problem

Property and casualty underwriters receive new-business and renewal submissions with missing forms, incomplete values, or differences from the current policy record. Identifying intake gaps is time-consuming, and a changed value must not be mistaken for an underwriting decision.

## 2. Solution overview

This Streamlit demo accepts a policy number and structured submission details, retrieves synthetic policy data from a local mock IBM i repository, checks required fields and documents, compares submitted values with the policy, flags material differences, and prepares a concise summary and broker follow-up draft.

The final intake status is computed only by deterministic Python rules:

- **READY FOR UNDERWRITER REVIEW** means the required submission information is complete and valid for intake. It is not acceptance or approval.
- **NEEDS INFORMATION** means required fields or documents are missing, or an input is invalid.

Material changes are shown for a human underwriter; they do not change the completeness label by themselves. The tool never makes underwriting, pricing, acceptance, rejection, or risk-selection decisions. Broker messages are drafts only. A human must review and approve a draft before the UI presents its copyable version; no email is sent.

Revenue and requested-limit inputs are whole-dollar integers in this synthetic demo, so they are represented and compared without fractional currency. Materiality thresholds use integer cross-multiplication rather than floating-point rounding.

## 3. Neuro-SAN architecture

The Neuro-SAN network is declared in `registries/industry/broker_submission_readiness.hocon` and enabled in `registries/industry/manifest.hocon`. Streamlit calls the deterministic application service directly. Neuro-SAN may optionally generate supplemental narrative; that text cannot change or replace the Python readiness status.

## 4. Agent descriptions

| Agent | Responsibility |
| --- | --- |
| Broker Submission Readiness (frontman) | Coordinates specialist agents and returns a user-oriented narrative without making decisions. |
| Policy Context Agent | Retrieves synthetic policy context through `PolicyLookupTool`; it does not connect to IBM i. |
| Submission Validation Agent | Reports missing required fields/documents using `SubmissionValidationTool`. |
| Consistency Agent | Reports policy comparisons and material-change flags through `ConsistencyCheckTool`. |
| Readiness Decision Agent | Calls `ReadinessDecisionTool`; Python rules determine completeness status. |
| Summary Agent | Produces supplemental narrative using supplied facts only. |
| Email Agent | Drafts follow-up text only; never sends a message. |
| Explainability Agent | Explains the deterministic rule identifiers and descriptions supplied to it. |

## 5. Why deterministic tools make the readiness decision

Readiness affects operational routing and must be reproducible. Required information, validation errors, configured materiality thresholds, and the final status are calculated in regular Python functions and covered by tests. An LLM can help phrase a summary, but it does not decide whether a submission is ready. The UI renders the status returned by `analyze_submission`; it does not parse model-generated text for a status.

## 6. Directory structure

```text
apps/broker_submission_readiness/
  data/policies.json                 # synthetic mock policy records
  consistency.py                     # policy comparisons and materiality
  demo.py                            # deterministic command-line scenarios
  demo_scenarios.py                  # three synthetic submissions
  models.py                          # stable typed data contracts
  neuro_san_client.py                # optional direct narrative invocation
  policy_repository.py               # local mock IBM i retrieval
  readiness.py                       # deterministic completeness/status rules
  service.py                         # application service
  streamlit_app.py                   # human-facing UI
  validation.py                      # required-field/document checks
  requirements.txt                   # app-specific Streamlit dependency
coded_tools/industry/broker_submission_readiness/
  readiness_tools.py                 # Neuro-SAN CodedTool adapters
registries/industry/
  broker_submission_readiness.hocon  # multi-agent network
  manifest.hocon                     # network registration
tests/apps/broker_submission_readiness/
  test_readiness.py                  # business-rule, tool, and HOCON tests
docs/architecture.md                 # architecture and layer responsibilities
```

## 7. Prerequisites

- Python 3.12 is recommended. The checked-out Neuro-SAN Studio declares Python `>=3.10`; use a version supported by this checkout.
- Neuro-SAN Studio dependencies from the repository root.
- Streamlit, installed from the app-specific requirements file.
- A model-provider API key is optional for deterministic demo use and is needed only to run the optional Neuro-SAN narrative agents.

## 8. Environment setup

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r apps/broker_submission_readiness/requirements.txt
```

If the selected Python runtime differs, replace `python3.12` with a supported interpreter. Do not place credentials in source files.

## 9. Neuro-SAN Studio setup

Install Neuro-SAN with the repository dependencies above. Run commands from the repository root so relative HOCON includes resolve. The HOCON network and CodedTool implementation are already included in this checkout.

## 10. HOCON network registration

The network is registered as `"industry/broker_submission_readiness.hocon": true` in the industry manifest, which is included from `registries/manifest.hocon`. Its CodedTool classes are loaded from `coded_tools/industry/broker_submission_readiness/readiness_tools.py`.

## 11. Model-provider configuration

The network selects OpenAI's `openai/gpt-5.2` model through OpenRouter. Set `OPENROUTER_API_KEY` in the project-root `.env` (rename the existing `OPENAI_API_KEY` variable, keeping its value unchanged). Neuro-SAN loads the project `.env` when using `ns chat`. Keep the key in that ignored local file; never put the secret in HOCON or commit it. The deterministic Streamlit workflow does not require a provider key.

## 12. How to start Neuro-SAN

For a separately accessible Neuro-SAN server, set the root manifest and run:

```bash
AGENT_MANIFEST_FILE=registries/manifest.hocon python -m neuro_san_studio run
```

The Streamlit app's optional narrative button creates a Neuro-SAN direct session in-process and applies the repository's `ProjectEnvironment` so the manifest and CodedTool paths are available. The UI therefore does not require a separately running server for deterministic checks.

## 13. How to start Streamlit

In another terminal from the repository root, with the environment activated:

```bash
streamlit run apps/broker_submission_readiness/streamlit_app.py
```

Use one of the synthetic demo scenarios or enter synthetic submission details. The model-generated narrative button is optional.

## 14. How to run tests

```bash
pytest -q tests/apps/broker_submission_readiness
```

To print the deterministic outputs for all three demo cases:

```bash
python -m apps.broker_submission_readiness.demo
```

## 15. Demo scenarios

1. **Complete submission** — `POL-1001`; every required field and document matches the policy. Expected status: `READY FOR UNDERWRITER REVIEW`, with no missing information or material changes.
2. **Missing information** — `POL-1001`; business description is blank, annual revenue is zero, and three required documents are absent. Expected status: `NEEDS INFORMATION`, with those field/document gaps and an invalid revenue error.
3. **Material changes** — `POL-1001`; complete submission with changed business description, mailing address, revenue, and requested limit. Expected status: `READY FOR UNDERWRITER REVIEW` with four material changes flagged for human review. Completeness does not imply acceptance.

## 16. Troubleshooting

- **`ModuleNotFoundError: streamlit`** — activate the environment and install `apps/broker_submission_readiness/requirements.txt`.
- **Neuro-SAN model/provider error** — deterministic checks still work; configure the model provider before using the optional narrative button.
- **Network or coded-tool import error** — run from the repository root and verify the entry in `registries/industry/manifest.hocon`.
- **Policy not found** — use one of the exact synthetic identifiers in `apps/broker_submission_readiness/data/policies.json`.
- **Unexpected `NEEDS INFORMATION`** — inspect the missing field/document lists and the field-error messages; the status is deterministic.

## 17. Security and privacy considerations

- All bundled records and demo email addresses are synthetic (`example.test`).
- Do not enter real policyholder, applicant, broker, financial, or claims information.
- No live IBM i connection, outbound email integration, or persistence layer is configured.
- The optional Neuro-SAN narrative receives only the report facts selected by `neuro_san_client.py`; do not use it with production data without an approved privacy and provider review.
- Human review and explicit approval are required before the app presents a copyable email draft.
- No secrets or API keys are stored in this application.

## 18. Current limitations

- The policy repository is a local JSON mock; it does not call IBM i or an API.
- The required-field/document lists and materiality thresholds are synthetic examples, not approved underwriting guidelines.
- Broker email is a reviewable text draft only; the app does not send or store it.
- The optional LLM narrative is not guaranteed factual and is not part of readiness evaluation.
- The application does not assess risk or make any coverage, pricing, acceptance, or rejection decisions.

## 19. Future IBM i integration approach

Replace the local `get_policy` implementation behind the policy repository interface with an authenticated, read-only IBM i REST adapter. Preserve the `Policy` response contract, validate responses at the boundary, add timeouts and auditable error handling, and keep network credentials outside source control. Begin with synthetic or masked test data and verify field mappings with IBM i owners. Do not expose raw records to an LLM; continue to run validation, comparisons, thresholds, and readiness status in deterministic Python. Any production deployment would require security, privacy, access-control, retention, and underwriting-governance reviews.
