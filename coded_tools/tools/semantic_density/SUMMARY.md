# Semantic Density — Summary

## What It Does

Semantic Density is a confidence scoring system for LLM-generated answers.
Given a question, it:

1. **Generates 5 diverse answers** via group beam search (Qwen2.5-7B-Instruct)
2. **Extracts token probabilities** as geometric mean per answer
3. **Computes pairwise NLI distances** via DeBERTa-large-MNLI (contradiction + 0.5 * neutral)
4. **Calculates semantic density** — a 0-1 score combining distance and probability

High-agreement factual questions score ~0.9. Subjective or incorrect-premise
questions score lower, enabling agents to hedge or flag unreliable answers.

## Deliverables

### CodedTool (`coded_tools/tools/semantic_density/`)

| File | Purpose |
|------|---------|
| `semantic_density_engine.py` | Core algorithm class with 4 pipeline steps |
| `semantic_density_tool.py` | Async `CodedTool` wrapper using `asyncio.to_thread()` |
| `__init__.py` | Package marker |

### Agent Network (`registries/tools/semantic_density.hocon`)

```
User Question → soothsayer → [answerer + confidence_checker]
                                          ↓
                               semantic_density (CodedTool)
                                          ↓
                               0-1 confidence score
```

- **soothsayer**: Front Man — orchestrates answerer and confidence_checker
- **answerer**: Provides a direct answer to the question
- **confidence_checker**: Calls the semantic_density CodedTool, reports score
- Score mapping: >= 0.7 high, 0.4-0.7 moderate, < 0.4 low

### MCP Server (`servers/mcp/confidence_server.py`)

A thin MCP wrapper (~40 lines) that exposes `SemanticDensityEngine` as a
remote tool via streamable HTTP. Any agent network on any machine can call
`assess_confidence(question)` over MCP — no local GPU required.

### MCP Consumer (`coded_tools/tools/mcp_confidence/`)

| File | Purpose |
|------|---------|
| `confidence_checker.py` | Coded tool that connects to the MCP server via `langchain-mcp-adapters` |
| `mcp_confidence.hocon` | Agent network using the MCP-based confidence checker |

### Tests (`tests/tools/semantic_density/`)

9 unit tests covering:
- Density computation (identical, distant, zero, single, asymmetric)
- Confidence interpretation thresholds
- Evaluate result structure
- CodedTool wrapper (missing input, mocked invocation)

## Example Questions

| Question | Expected Confidence |
|----------|-------------------|
| "What is the capital of France?" | High (~0.9) |
| "What is the best programming language?" | Moderate (~0.5) |
| "What year did humans land on Mars?" | Low (~0.3) |

## Hardware Requirements

- GPU: ~31 GB VRAM peak (float32 required for group beam search)
- Tested on: g6e.2xlarge (L40S, 48 GB)
- Models: Qwen/Qwen2.5-7B-Instruct + microsoft/deberta-large-mnli

## Running

```bash
# Via agent_cli
export PYTHONPATH=$(pwd)
export AGENT_TOOL_PATH=coded_tools/
python -m neuro_san.client.agent_cli --agent semantic_density

# Via MCP (start server, then use mcp_confidence network)
CUDA_VISIBLE_DEVICES=7 python servers/mcp/confidence_server.py
python -m neuro_san.client.agent_cli --agent mcp_confidence
```
