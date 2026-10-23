# Automotive Model-Based Development Workflow

This Neuro SAN agent network demonstrates a generic automotive software requirement-to-model workflow. It coordinates
specialists for requirement interpretation, model planning, MATLAB/Simulink implementation, verification, and a
traceable engineering report. Model operations use the existing Simulink Agentic Toolkit MCP bridge.

## File

[simulink_mbd_verifier.hocon](../../../registries/simulink_mbd_verifier.hocon)

## Agent workflow

1. **Requirements analyst** converts natural language into a testable contract, maps clauses to observable behavior,
   and identifies missing or ambiguous details.
2. **Model planner** proposes interfaces, Simulink blocks and connections, traceability, and positive, negative, and
   boundary scenarios.
3. **Simulink model builder** implements the approved plan in the requested model via MATLAB MCP.
4. **Model verification agent** inspects and checks the live model, runs applicable tests when available, and records
   diagnostics and evidence.
5. **Engineering reporter** combines the results, clearly distinguishing completed checks from planned or unavailable
   checks.

The front-man coordinates these agents in sequence. A behavior-changing ambiguity pauses the workflow for user input.
Requests limited to analysis, planning, or an architecture explanation do not need to connect to MATLAB.

## Generic example

Use a simple driver-door warning requirement:

> When vehicle speed is at least 10 km/h and the driver door is open, assert a warning output; otherwise clear it.

This example implies a speed input in km/h, a Boolean door input, a Boolean warning output, an inclusive speed
threshold, and combinational behavior. A request to build the model should also provide a model name, or allow the
planner to propose one. The workflow reports actual MATLAB/MCP results and does not represent a mock dry run as model
creation or verification.

Try it in Neuro SAN:

```text
ns chat simulink_mbd_verifier
```

Then provide the requirement and request analysis, planning, model creation, verification, and a report. To explore
agent routing without MATLAB, ask:

```text
Explain the roles in the automotive model-based development workflow without connecting to MATLAB.
```

## Setup and limitations

The model-creation and verification phases require Neuro SAN Studio, MATLAB/Simulink, the MathWorks Simulink Agentic
Toolkit and its MATLAB MCP server, plus a configured MATLAB session. The bridge can locate the MCP executable and
tool schema using `MATLAB_MCP_BIN` and `SATK_TOOLS_JSON`; see the
[Simulink bridge](../../../coded_tools/simulink_mbd_verifier/simulink_bridge.py) for defaults.
For a new model, the workflow first creates and opens the planned model in MATLAB, then uses `model_edit` to add
blocks. MATLAB errors returned in MCP text responses are surfaced as errors rather than successful edits.

The network tries `gemini-3-flash` first and falls back to local Ollama `qwen2.5:7b` if Gemini is unavailable or
fails. Set `GOOGLE_API_KEY` in the project `.env` file (copy `.env.example` if needed) to use Gemini. The Qwen
fallback requires Ollama running at `http://127.0.0.1:11434` with `qwen2.5:7b` available. Fallbacks handle model
failures such as provider errors or rate limits; they do not switch models just because a response is low quality.

Without live MATLAB/MCP, the bridge may return `mock_dry_run`; that is not model creation, simulation, or verification.
This generic example demonstrates agent orchestration and does not claim functional safety, production readiness, or
compliance with automotive standards.
