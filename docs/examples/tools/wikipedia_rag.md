# Wikipedia RAG Assistant

The **Wikipedia RAG Assistant** answers user queries using Retrieval-Augmented Generation (RAG) over Wikipedia articles.

---

## File

[wikipedia_rag.hocon](../../../registries/tools/wikipedia_rag.hocon)

---

## Prerequisites for RAG:

This agent is **disabled by default**. To use it:

1. Enable hocon file:

   ```hocon
   "wikipedia_rag.hocon": true
   ```

2. Install the required package:

   ```bash
   pip install wikipedia
   ```

---

## Example Conversation

### Human

```text
Compare ResNet, DenseNet, and EfficientNet for image classification.
```

### AI (Wikipedia RAG Assistant)

```text
Here is a comparison of ResNet, DenseNet, and EfficientNet for image classification:

- **ResNet (Residual Networks):** Known for its innovative use of skip connections or residual blocks,
ResNet allows models to be much deeper by mitigating the vanishing gradient problem that deep networks
face. It was a breakthrough in the ImageNet competition and remains a widely used architecture for
image classification tasks.

- **DenseNet:** This network architecture connects each layer to every other layer in a feed-forward
fashion. While traditional convolutional networks with L layers have L connections (one between each
layer and the next), DenseNet has L(L+1)/2 direct connections. This design improves the flow of
information and gradients throughout the network, making it very effective for image classification
tasks.

- **EfficientNet:** Introduced by Google AI in 2019, EfficientNet uses a new scaling method that
uniformly scales all dimensions of depth, width, and resolution using a compound coefficient. This
model is known for achieving better accuracy and efficiency than previous models and is widely used
in various computer vision tasks, including image classification, object detection, and segmentation.

Each of these models has unique strengths and innovations that contribute to their effectiveness in
image classification tasks.
```

---

## Architecture Overview

### Frontman Agent: **Wikipedia RAG Assistant**

* Serves as the **entry point** for user queries.
* Passes the **query** to the `rag_retriever` tool.
* Aggregates and composes the final answer.

### Tool: `rag_retriever`

* Retrieves relevant pages from wikipedia that answer the user's query.

#### User-Defined Arguments

##### Optional

- `lang` (str, default: "en"): Language code for Wikipedia articles.
- `top_k_results` (int, default: 3): Maximum number of Wikipedia pages to load.
- `doc_content_chars_max` (int, default: 4000): Maximum characters of text to keep per page (truncates for efficiency).

---

## Debugging Hints

When troubleshooting, check the following:

- Ensure that the user queries are detailed with context.
- Verify that top_k_results and doc_content_chars_max are set to values that don’t cause timeouts or memory issues or do not lose a lot of context.
- Look at logs to ensure smooth delegation across tool calls and proper response integration.
