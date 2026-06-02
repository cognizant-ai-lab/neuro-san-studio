# Semantic Density — FedEx Day Summary

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
User Question → qa_manager → [answerer + confidence_checker]
                                          ↓
                               semantic_density (CodedTool)
                                          ↓
                               0-1 confidence score
```

- **qa_manager**: Front Man — orchestrates answerer and confidence_checker
- **answerer**: Provides a direct answer to the question
- **confidence_checker**: Calls the semantic_density CodedTool, reports score
- Score mapping: >= 0.7 high, 0.4-0.7 moderate, < 0.4 low

### Demo Scripts

| File | Purpose |
|------|---------|
| `demo_runner.py` | Colored terminal output (green/yellow/red confidence bars) |
| `demo_visualize.py` | t-SNE heatmap PNG showing answer clustering |
| `demo_audio_server.py` | FastAPI WebSocket server with OpenAI TTS narration |
| `demo_results_backup.json` | Pre-computed results for 3 curated questions |

### Tests (`tests/tools/semantic_density/`)

9 unit tests covering:
- Density computation (identical, distant, zero, single, asymmetric)
- Confidence interpretation thresholds
- Evaluate result structure
- CodedTool wrapper (missing input, mocked invocation)

## Curated Demo Questions

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
# Terminal demo (live)
export PYTHONPATH=$(pwd)
export AGENT_TOOL_PATH=coded_tools/
python coded_tools/tools/semantic_density/demo_runner.py

# Terminal demo (pre-computed fallback)
python coded_tools/tools/semantic_density/demo_runner.py \
    coded_tools/tools/semantic_density/demo_results_backup.json

# Via agent_cli
python -m neuro_san.client.agent_cli --agent semantic_density

# Visualization
python coded_tools/tools/semantic_density/demo_visualize.py \
    demo_results_backup.json

# Audio server
python coded_tools/tools/semantic_density/demo_audio_server.py
```
