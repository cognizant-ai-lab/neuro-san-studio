
Act as a senior Python developer, P&C insurance solution architect,
IBM i modernization specialist, and Neuro-SAN multi-agent developer.

Build a complete, runnable hackathon application named:

"Neuro-SAN Broker Submission Readiness Checker"

IMPORTANT TECHNOLOGY CONSTRAINTS

1. Use Python 3.12 or a Python version supported by the checked-out
   Neuro-SAN Studio repository.
2. Use Streamlit for the user interface.
3. Use Cognizant Neuro-SAN as the multi-agent orchestration framework.
4. Define the multi-agent network through a Neuro-SAN HOCON configuration.
5. Use Neuro-SAN CodedTools for deterministic Python operations and mock
   external-system integration.
6. Do not use React.
7. Do not use CrewAI.
8. Do not use LangGraph as the primary orchestrator.
9. Do not send any real email.
10. Do not connect to a live IBM i system.
11. Use synthetic P&C insurance data only.
12. Never allow an LLM to make the final READY or NEEDS INFORMATION decision.
13. The final status must come from deterministic Python business rules.
14. Require human review before a broker email can be copied or approved.
15. Do not include secrets or API keys in source code.

BUSINESS PROBLEM

P&C insurance underwriters receive broker submissions for new business
and renewals. These submissions may contain missing documents, incomplete
information, or values that are inconsistent with the existing policy.

The application must:

1. Accept a policy number.
2. Accept structured submission information.
3. Retrieve existing policy information from a mock IBM i REST API or
   deterministic local CodedTool.
4. Determine the required documents and fields.
5. Identify missing documents and fields.
6. compare submitted values with existing policy values.
7. identify material changes.
8. Generate a concise underwriting summary.
9. Draft a broker follow-up email.
10. Explain the deterministic business rules that were triggered.
11. Require human review before the email is approved.
12. Never perform underwriting, pricing, acceptance, rejection, or risk
    selection decisions.

- Underwriter review required: true
- No missing-document follow-up request

README REQUIREMENTS

Create a complete README containing:

1. Business problem.
2. Solution overview.
3. Neuro-SAN architecture.
4. Agent descriptions.
5. Why deterministic tools make the readiness decision.
6. Directory structure.
7. Prerequisites.
8. Environment setup.
9. Neuro-SAN Studio setup.
10. HOCON network registration.
11. Model-provider configuration.
12. How to start Neuro-SAN.
13. How to start Streamlit.
14. How to run tests.
15. Demo scenarios.
16. Troubleshooting.
17. Security and privacy considerations.
18. Current limitations.
19. Future IBM i integration approach.

DOCUMENTATION REQUIREMENTS

docs/architecture.md must contain a Mermaid diagram similar to:

flowchart LR
    UI[Streamlit UI] --> NS[Neuro-SAN Frontman]
    NS --> PC[Policy Context Agent]
    NS --> VA[Validation Agent]
    NS --> CA[Consistency Agent]
    NS --> DA[Readiness Decision Agent]
    NS --> SA[Summary Agent]
    NS --> EA[Email Agent]
    NS --> XA[Explainability Agent]

    PC --> PLT[Policy Lookup CodedTool]
    VA --> SVT[Submission Validation CodedTool]
    CA --> CCT[Consistency Check CodedTool]
    DA --> RDT[Readiness Decision CodedTool]

    PLT --> DATA[Synthetic IBM i Policy JSON]
    RDT --> UI

Also explain:

- Neuro layer: summary, communication, explanation.
- Symbolic/deterministic layer: validation, comparison, readiness rules.
- Human layer: result and email approval.
- Legacy integration layer: mock IBM i retrieval.


Phase 1:
Create data models, synthetic policies, deterministic functions, and tests.
 
Phase 2:
Run all deterministic tests and fix failures.
 
Phase 3:
Create Neuro-SAN CodedTool wrappers around tested deterministic functions.
 
Phase 4:
Inspect current Neuro-SAN examples and create valid HOCON.
 
Phase 5:
Register the network in the manifest.
 
Phase 6:
Create the Neuro-SAN client service.
 
Phase 7:
Create the Streamlit application.
 
Phase 8:
Add DEMO mode.
 
Phase 9:
Run tests, syntax checks, and import checks.
 
Phase 10:
Create README, architecture documentation, and demo script.
 
CODE QUALITY
 
- Use type hints.
- Use docstrings.
- Use pathlib for file paths.
- Use logging rather than print statements.
- Return new dictionaries instead of unexpectedly mutating shared values.
- Keep business rules separate from presentation logic.
- Keep LLM prompts separate from deterministic rules.
- Use stable JSON response contracts.
- Use Decimal where appropriate for financial values or explain why numeric
handling is safe for the demo.
- Make the code clear enough for an IBM i developer learning Python.
- Avoid unnecessary abstractions.
- Avoid large frameworks beyond Neuro-SAN and Streamlit.
 
DELIVERY FORMAT
 
Work file by file.
 
For every file:
 
1. Print the relative filename as a heading.
2. Provide the complete file content.
3. Do not use placeholders such as "add your code here".
4. Do not omit imports.
5. Do not truncate code.
6. Explain how the file connects to the solution.
7. After all files are generated, provide exact setup and run commands.
8. Provide a verification checklist.
9. Provide expected output for the three demo scenarios.
 
Before finalizing:
 
- verify imports;
- verify file paths;
- verify JSON field names;
- verify HOCON syntax against current repository examples;
- verify the manifest entry;
- verify tool class locations;
- verify Streamlit invokes the correct client;
- verify no LLM makes the readiness decision;
- verify no email is sent;
- verify all tests are internally consistent.
Important implementation note

Neuro-SAN is designed around data-driven agent networks configured in HOCON, with Python CodedTools for operations that LLMs should not perform, such as API calls, exact calculations, and private-data handling. That directly fits this use case: agents write summaries and communications, while coded tools retrieve policy data and make the deterministic readiness decision.

Your internal hackathon material says Neuro-SAN networks are defined through HOCON and registered in a manifest. The training also notes that the UI, database, and deployment are outside Neuro-SAN, so using Streamlit for the surrounding application is appropriate.

Recommended way to use the prompt

Because this prompt requests many files, give your coding assistant the master prompt first, then instruct it:

Plain Text
Start with Phase 1 only.
 
Generate:
 
1. data/policies.json
2. the four deterministic Python modules
3. pytest tests
 
Do not generate the Neuro-SAN HOCON or Streamlit UI yet.
After generating the files, verify the tests are internally consistent.

Next:

Plain Text
Proceed with Phase 3 and Phase 4.
 
Inspect the Neuro-SAN examples in the checked-out repository.
Create CodedTool wrappers and the HOCON agent network using the exact
current schemas. Do not invent any framework classes or HOCON properties.
Proceed with the Streamlit UI, Neuro-SAN client, DEMO mode,
documentation, and complete verification checklist.