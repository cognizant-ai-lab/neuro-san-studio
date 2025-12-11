# Neuro SAN Studio

**Your launchpad for building intelligent multi-agent systems.** Neuro SAN Studio is a hands-on playground for the
[Neuro SAN](https://github.com/cognizant-ai-lab/neuro-san) framework, featuring ready-to-run examples, tutorials, and
tools that let you design, test, and deploy sophisticated agent networks in minutes—not months. Whether you're a
researcher exploring adaptive AI systems, a developer prototyping production solutions, or a domain expert configuring
agents without code, this studio handles the orchestration complexity so you can focus on solving real problems.

<!-- pyml disable-next-line no-inline-html -->
<p align="center">
  <a href="https://deepwiki.com/cognizant-ai-lab/neuro-san-studio">
  <img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki: Neuro SAN Studio" /></a>
</p>

---

<!-- pyml disable-next-line no-inline-html -->
<p align="center">
  Neuro SAN is the open-source library powering the Cognizant Neuro® AI Multi-Agent Accelerator, allowing domain experts,
  researchers and developers to immediately start prototyping and building agent networks across any industry vertical.
</p>

---
<!-- pyml disable-next-line no-inline-html -->
<p align="center">
  <!-- GitHub Stats -->
  <img src="https://img.shields.io/github/stars/cognizant-ai-lab/neuro-san-studio?style=social" alt="GitHub stars">
  <img src="https://img.shields.io/github/forks/cognizant-ai-lab/neuro-san-studio?style=social" alt="GitHub forks">
  <img src="https://img.shields.io/github/watchers/cognizant-ai-lab/neuro-san-studio?style=social" alt="GitHub watchers">
</p>
<p align="center">
  <!-- GitHub Info -->
  <img src="https://img.shields.io/github/last-commit/cognizant-ai-lab/neuro-san-studio" alt="Last Commit">
  <img src="https://img.shields.io/github/issues/cognizant-ai-lab/neuro-san-studio" alt="Issues">
  <img src="https://img.shields.io/github/issues-pr/cognizant-ai-lab/neuro-san-studio" alt="Pull Requests">
</p>

<!-- pyml disable-next-line no-inline-html -->
<p align="center">
  <!-- Neuro SAN Stats -->
  Neuro SAN library <br>
  <a href="https://github.com/cognizant-ai-lab/neuro-san"><img alt="GitHub Repo"
  src="https://img.shields.io/badge/GitHub-Repo-green.svg" /></a>
  <img src="https://img.shields.io/github/commit-activity/m/cognizant-ai-lab/neuro-san" alt="commit activity">
  <a href="https://pepy.tech/projects/neuro-san"><img alt="PyPI Downloads"
  src="https://static.pepy.tech/badge/neuro-san" /></a>
  <a href="https://pypi.org/project/neuro-san/">
  <img alt="neuro-san@PyPI" src="https://img.shields.io/pypi/v/neuro-san.svg?style=flat-square"></a>
  <a href="https://deepwiki.com/cognizant-ai-lab/neuro-san">
  <img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki: Neuro SAN" /></a>
</p>

## What is Neuro SAN?

[**Neuro AI system of agent networks (Neuro SAN)**](https://github.com/cognizant-ai-lab/neuro-san) is an open-source,
data-driven multi-agent orchestration framework designed to simplify and accelerate the development of collaborative AI
systems. It allows users—from machine learning engineers to business domain experts—to quickly build sophisticated
multi-agent applications without extensive coding, using declarative configuration files (in HOCON format).

Neuro SAN enables multiple large language model (LLM)-powered agents to collaboratively solve complex tasks, dynamically
delegating subtasks through adaptive inter-agent communication protocols. This approach addresses the limitations inherent
to single-agent systems, where no single model has all the expertise or context necessary for multifaceted problems.

<!-- pyml disable line-length -->
| Build a multi-agent network in minutes                                              | Neuro SAN overview                                                                     | Quick start                                                              |
|-------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| [![Build](./docs/images/designer.png)](https://www.youtube.com/watch?v=wGxvPBN34Mk) | [![Overview](./docs/images/overview.png)](https://www.youtube.com/watch?v=NmniQWQT6vI) | [![Start](./docs/images/nsflow_thumb.png)](https://youtu.be/gfem8ylphWA) |

<!-- pyml enable line-length -->
---

### ✨ Key Features

* **🗂️ Data-Driven Configuration**: Entire agent networks are defined declaratively via simple HOCON files, empowering
technical and non-technical stakeholders to design agent interactions intuitively.
* **🔀 Adaptive Communication ([AAOSA Protocol](https://arxiv.org/abs/cs/9812015))**: Agents autonomously determine how
to delegate tasks, making interactions fluid and dynamic with decentralized decision-making.
* **🔒 Sly-Data**: Sly Data facilitates safe handling and transfer of sensitive data between agents without exposing it
directly to any language models.
* **🧩 Dynamic Agent Network Designer**: Includes a meta-agent called the Agent Network Designer – essentially, an agent
that creates other agent networks. Provided as an example with Neuro SAN, it can take a high-level description of a
use-case as input and generate a new custom agent network for it.
* **🛠️ Flexible Tool Integration**: Integrate custom Python-based "coded tools," APIs, databases, and even external
agent ecosystems (Agentforce, Agentspace, CrewAI, MCP, A2A agents, LangChain tools and more) seamlessly into your agent workflows.
* **📈 Robust Traceability**: Detailed logging, tracing, and session-level metrics enhance transparency, debugging, and
operational monitoring.
* **🌐 Extensible and Cloud-Agnostic**: Compatible with a wide variety of LLM providers (OpenAI, Anthropic, Azure, Ollama,
etc.) and deployable in diverse environments (local machines, containers, or cloud infrastructures).

---

### Use Cases

Here are a few examples of use-cases that have been implemented with Neuro SAN.
For more examples, check out [docs/examples.md](docs/examples.md).
<!-- pyml disable no-inline-html -->
<table>
  <thead>
    <tr>
      <th>Agent Network</th>
      <th>Use-Case</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>🧬 <strong>Agent Network Designer</strong></td>
      <td>Automated generation of multi-agent HOCON configurations.</td>
      <td>Generates complex multi-agent configurations from natural language input, simplifying the creation of intricate
      agent workflows.</td>
    </tr>
    <tr>
      <td>🛫 <strong>Airline Policy Assistance</strong></td>
      <td>Customer support for airline policies.</td>
      <td>Agents interpret and explain airline policies, assisting customers with inquiries about baggage allowances, cancellations,
      and travel-related concerns.</td>
    </tr>
    <tr>
      <td>🏦 <strong>Banking Operations & Compliance</strong></td>
      <td>Automated financial operations and regulatory compliance.</td>
      <td>Automates tasks such as transaction monitoring, fraud detection, and compliance reporting, ensuring adherence to
      regulations and efficient routine operations.</td>
    </tr>
    <tr>
      <td>🛍️ <strong>Consumer Packaged Goods (CPG)</strong></td>
      <td>Market analysis and product development in CPG.</td>
      <td>Gathers and analyzes market trends, customer feedback, and sales data to support product development and strategic
      marketing.</td>
    </tr>
    <tr>
      <td>🛡️ <strong>Insurance Agents</strong></td>
      <td>Claims processing and risk assessment.</td>
      <td>Automates claims evaluation, assesses risk factors, ensures policy compliance, and improves claim-handling efficiency
      and customer satisfaction.</td>
    </tr>
    <tr>
      <td>🏢 <strong>Intranet Agents</strong></td>
      <td>Internal knowledge management and employee support.</td>
      <td>Provides employees with quick access to policies, HR, and IT support, enhancing internal communications and resource
      accessibility.</td>
    </tr>
    <tr>
      <td>🛒 <strong>Retail Operations & Customer Service</strong></td>
      <td>Enhancing retail customer experience and operational efficiency.</td>
      <td>Handles customer inquiries, inventory management, and supports sales processes to optimize operations and service
      quality.</td>
    </tr>
    <tr>
      <td>📞 <strong>Telco Network Support</strong></td>
      <td>Technical support and network issue resolution.</td>
      <td>Diagnoses network problems, guides troubleshooting, and escalates complex issues, reducing downtime and enhancing
      customer service.</td>
    </tr>
    <tr>
      <td>📞 <strong>Therapy Vignette Supervision</strong></td>
      <td>Generates treatment plan for a given therapy vignette.</td>
      <td>A good example of using multiple different expert agents working together to come up with a single plan.</td>
    </tr>
  </tbody>
</table>
<!-- pyml enable no-inline-html -->

And many more: check out [docs/examples.md](docs/examples.md).

---

## High level Architecture

<!-- pyml disable no-inline-html -->
<p align="left">
  <img src="./docs/images/neuroai_arch_diagram.png" alt="neuro-san architecture" width="800"/>
</p>
<!-- pyml enable no-inline-html -->

---

## Getting Started

To dive into Neuro SAN and start building your own multi-agent networks, this repository contains a collection of demos
for the [neuro-san library](https://github.com/cognizant-ai-lab/neuro-san).

You'll find comprehensive documentation, example agent networks, and tutorials to guide you through your first steps.

---

### Installation

Clone the repo:

```bash
git clone https://github.com/cognizant-ai-lab/neuro-san-studio
```

Go to dir:

```bash
cd neuro-san-studio
```

Ensure you have a supported version of python (e.g. 3.12 or 3.13):

```bash
python --version
```

Create a dedicated Python virtual environment:

```bash
python -m venv venv
```

Source it:

* For Windows:

  ```cmd
  .\venv\Scripts\activate.bat && set PYTHONPATH=%CD%
  ```

* For Mac:

  ```bash
  source venv/bin/activate && export PYTHONPATH=`pwd`
  ```

Install the requirements:

```bash
pip install -r requirements.txt
```

**IMPORTANT**: By default, the server relies on OpenAI's `gpt-4o` model. Set the OpenAI API key and add it to your shell
configuration so it's available in future sessions.

You can get your OpenAI API key from <https://platform.openai.com/signup>. After signing up, create a new API key in the
API keys section in your profile.

**NOTE**: Replace `XXX` with your actual OpenAI API key.  
**NOTE**: This is OS dependent.

* For macOS and Linux:

  ```bash
  export OPENAI_API_KEY="XXX" && echo 'export OPENAI_API_KEY="XXX"' >> ~/.zshrc
  ```

<!-- pyml disable commands-show-output -->
* For Windows:
    * On Command Prompt:

    ```cmd
    set OPENAI_API_KEY=XXX
    ```

    * On PowerShell:

    ```powershell
    $env:OPENAI_API_KEY="XXX"
    ```

<!-- pyml enable commands-show-output -->

Other providers such as Anthropic, AzureOpenAI, Ollama and more are supported too but will require proper setup.
Look at the `.env.example` file to set up environment variables for specific use-cases.

For testing the API keys, please refer to this [documentation](./docs/api_key.md)

---

### Run

Neuro SAN Studio provides a user-friendly environment to interact with agent networks.

1. Start the server and client with a single command, from the project root directory:

    ```bash
    python -m run
    ```

2. Navigate to [http://localhost:4173/](http://localhost:4173/) to access the UI.
3. (Optional) Check the logs:
   * For the server logs: `logs/server.log`
   * For the client logs: `logs/nsflow.log`
   * For the agents logs: `logs/thinking_dir/*`

Use the `--help` option to see the various config options for the `run` command:

```bash
python -m run --help
```

Screenshot:

![NSFlow UI Snapshot](https://raw.githubusercontent.com/cognizant-ai-lab/nsflow/main/docs/snapshot01.png)

---

## User guide

Ready to dive in? Check out the [user guide](docs/user_guide.md) for a detailed overview of the neuro-san library
and its features.

---

## Tutorial

For a detailed tutorial, refer to [docs/tutorial.md](docs/tutorial.md).

---

## Examples

For examples of agent networks, check out [docs/examples.md](docs/examples.md).

---

## Developer Guide

For the development guide, check out [docs/dev_guide.md](docs/dev_guide.md).

---

## Community Projects

### Applications

* [Climate Change](https://github.com/cognizant-ai-lab/neuro-san-cc):
a tool to answer questions about COP, the Paris Agreement or the Kyoto Protocol using UNFCCC documents.
* [F1 fans eval](https://github.com/deepsaia/f1-fan-eval):
an app that evaluates F1 fan submissions about why they are the biggest F1 fans.
* [PDF Knowledge Assistant](https://github.com/M-Elsaied/neuro-san-studio/tree/pdf-knowledge-base/apps/pdf_knowledge_assistant):
a Flask web app that queries PDFs using RAG with topic-based long-term memory synthesis across documents.
* [Vibe coding project evaluator](https://github.com/deepsaia/vibe-coding-eval):
a scalable framework that evaluates vibe-coded projects on different criteria.

### Utilities

* [Neuro SAN Web Client](https://github.com/cognizant-ai-lab/neuro-san-web-client):
a basic Flask web client interface for Neuro SAN.
* [Neuro SAN Slack app](./apps/slack/README.md)
a Slack integration that lets you interact with Neuro SAN directly from your workspace.

---

## Links

* Website: [Cognizant AI Lab](https://www.cognizant.com/us/en/ai-lab)
* YouTube: [Decision AI](https://www.youtube.com/@decision-ai)
* X: [@cognizantailab](https://x.com/cognizantailab)
* LinkedIn: [Cognizant AI Lab](https://www.linkedin.com/showcase/cognizant-ai-lab)

---

## More details

For more information, check out the [Cognizant AI Lab Neuro SAN landing page](https://www.cognizant.com/us/en/ai-lab/neuro-san).
