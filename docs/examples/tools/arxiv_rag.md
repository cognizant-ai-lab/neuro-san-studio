# ArXiv RAG Assistant

The **ArXiv RAG Assistant** answers user queries using Retrieval-Augmented Generation (RAG) over academic papers from [arXiv.org](https://arxiv.org).

---

## File

[arxiv_rag.hocon](../../../registries/tools/arxiv_rag.hocon)

---

## Prerequisites for RAG:

This agent is **disabled by default**. To use it:

1. Enable hocon file:
   
    ```hocon
    "arxiv_rag.hocon": true
    ```
   
2. Installing the required packages:

    ```bash
    pip install arxiv
    ```

    If `get_full_documents` is set to True. See [Optional](#optional)
    
    ```bash
    pip install pymupdf
    ```

---

## Example Conversation

### Human

```text
Please give me a list of research papers on LORA.
```

### AI (ArXiv RAG Assistant)

```text
Here is a list of research papers on Low-Rank Adaptation (LoRA):

1. **Multi-LoRA Composition for Image Generation:** 
   - Authors: Ming Zhong, Yelong Shen, Shuohang Wang, Yadong Lu, Yizhu Jiao, Siru Ouyang,
   Donghan Yu, Jiawei Han, Weizhu Chen
   - Published in: Transactions on Machine Learning Research (11/2024)
   - Focus: The paper studies multi-LoRA composition for text-to-image models and presents
   two training-free methods, LoRA Switch and LoRA Composite.

2. **Mixture of LoRA Experts:**
   - Authors: Xun Wu, Shaohan Huang, Furu Wei
   - Published at: ICLR 2024
   - Focus: Proposes Mixture of LoRA Experts (MOLE) to enhance LoRA composition by treating
   each layer as a distinct expert with hierarchical weight control.

3. **Not All LoRA Parameters Are Essential: Insights on Inference Necessity:**
   - Authors: Guanhua Chen, Yutong Yao, Ci-Jun Gao, Lidia S. Chao, Feng Wan, Derek F. Wong
   - Institution: University of Macau
   - Focus: Investigates the necessity of all fine-tuned LoRA layers during inference and
   proposes a method to enhance large language models by retaining critical layers.

4. **A Survey on LoRa Networking: Research Problems, Current Solutions and Open Issues:**
   - Authors: Jothi Prasanna Shanmuga Sundaram, Wan Du, Zhiwei Zhao
   - Focus: Provides a comprehensive survey on LoRa networks, discussing technical challenges
   and recent solutions in the context of IoT applications.

5. **CLoQ: Enhancing Fine-Tuning of Quantized LLMs via Calibrated LoRA Initialization:**
   - Authors: Yanxia Deng, Aozhong Zhang, Selcuk Gurses, Naigang Wang, Zi Yang, Penghang Yin
   - Published in: Transactions on Machine Learning Research (08/2025)
   - Focus: Introduces CLoQ, a strategy for fine-tuning quantized LLMs with LoRA, ensuring
   strong foundations for subsequent fine-tuning.

These papers cover various aspects of LoRA, including applications in image generation,
language models, and IoT networking.
```

---

## Architecture Overview

### Frontman Agent: **ArXiv RAG Assistant**

* Serves as the **entry point** for user queries.  
* Passes the **query** to the `rag_retriever` tool.
* Aggregates and composes the answer to user query.

### Tool: `rag_retriever`

* Retrieves relevant papers from wikipedia that answer the user's query.

#### User-Defined Arguments

##### Optional

- `top_k_results` (int, default: 3): Number of results the retriever asks arXiv to return. Raise for broader coverage (e.g., 5-10).
- `get_full_documents` (bool, default True): Content scope.
    - true → download full PDFs
    - false → abstracts/summaries only
- `doc_content_chars_max` (int, default: 4000): Maximum characters of text to keep per research paper (truncates long texts). Set to None to disable.
- `load_all_available_meta` (bool, default False): Metadata scope.
    - true → include full arXiv metadata (journal ref, categories, comments, links).
    - false → minimal fields (published date, title, authors, summary). 
- `continue_on_failure` (bool, default True): Fault tolerance.
    - true → skip retrieval/parsing failures and continue.
    - false → fail fast on first error.

---

## Debugging Hints

When troubleshooting, check the following:

- Ensure that the user queries are detailed with context.
- Verify that top_k_results and doc_content_chars_max are set to values that don’t cause timeouts or memory issues or do not lose a lot of context.
- Look at logs to ensure smooth delegation across tool calls and proper response integration.
