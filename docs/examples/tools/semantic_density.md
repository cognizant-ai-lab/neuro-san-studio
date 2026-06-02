# Semantic Density (Confidence Assessment)

Evaluates the trustworthiness of LLM-generated answers by scoring how consistently a model responds to the same question across multiple diverse beam search outputs.

---

## File

[semantic_density.hocon](../../../registries/tools/semantic_density.hocon)

---

## Description

The Semantic Density agent network answers user questions and provides a 0-1 confidence score indicating how trustworthy the answer is. It uses a three-agent architecture:

1. **Soothsayer** (frontman) receives the question and delegates to two sub-agents
2. **Answerer** provides a direct answer
3. **Confidence Checker** invokes the `SemanticDensityTool` coded tool on GPU to score confidence

The coded tool runs a four-step pipeline: diverse beam search generation, token probability extraction, NLI-based semantic distance, and weighted semantic density calculation.

---

## Prerequisites

This agent network requires GPU hardware and several Python packages not included in the base `requirements.txt`.

### Hardware

- GPU with ~32 GB VRAM (tested on A100-80GB and L40S-48GB)
- float32 precision required (group beam search has dtype issues with float16)

### Python Dependencies

```bash
pip install torch transformers scipy scikit-learn numpy
```

Pin `transformers==4.45.0` to avoid a group beam search regression in newer versions.

### Environment Variables

```bash
export OPENAI_API_KEY="your_openai_api_key_here"
```

The soothsayer and answerer agents use OpenAI for LLM calls. The coded tool itself runs local models on GPU.

---

## Example Conversation

### Human

```text
What is the capital of France?
```

### AI (Soothsayer)

```text
The capital of France is Paris. I am highly confident in this answer
with a confidence score of 0.9987.
```

### Human

```text
What is 19879 times 4390?
```

### AI (Soothsayer)

```text
The product of 19879 and 4390 is reported as 87,230,810. However, the
confidence score for this calculation is 0.2259, which is low. There
appears to be some discrepancy across evaluations. Please verify this
calculation using a reliable calculator or authoritative source.
```

---

## Architecture Overview

### Frontman Agent: soothsayer

- Receives user questions and delegates to answerer and confidence_checker.
- Interprets the confidence score to decide how to present the answer:
  - Score >= 0.7 (high): present directly
  - Score 0.4-0.7 (moderate): present with a caveat
  - Score < 0.4 (low): flag as potentially unreliable

### Sub-Agent: answerer

- Provides a direct, concise answer to the user's question.

### Sub-Agent: confidence_checker

- Invokes the `semantic_density` coded tool and reports the score.

### Coded Tool: semantic_density

- `SemanticDensityTool` wraps `SemanticDensityEngine` via `asyncio.to_thread()`.
- Runs the four-step pipeline on GPU: beam search (Qwen2.5-7B-Instruct), token probabilities, NLI distances (DeBERTa-large-MNLI), semantic density.

---

## Debugging Hints

- **Model loading**: First invocation takes 30-60 seconds to load models. Subsequent calls reuse the singleton instance.
- **VRAM**: Monitor with `nvidia-smi`. Peak usage is ~31 GB during beam search.
- **transformers version**: Version 4.45.0 is required. Newer versions moved group beam search to a community module with garbled output.
- **do_sample conflict**: The engine sets `do_sample=False` explicitly because Qwen2.5-7B's `generation_config.json` defaults to `do_sample=True`, which conflicts with group beam search.
