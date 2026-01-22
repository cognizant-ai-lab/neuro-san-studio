# MDAP Decomposer

The **MDAP Decomposer** is an agentic system designed to break problems down into smaller sub-problems recursively.

---

## File

[mdap_decomposer.hocon](../../../registries/experimental/mdap_decomposer.hocon)

---

## Description

MDAP stands for "Massively Decomposed Agentic Processes"

This agent network uses the basis of the [MAKER paper](https://arxiv.org/abs/2511.09030)'s
voting strategy to determine both the best sub-problem descriptions and the best solutions
for any given sub-problem stage.

This agent network also provides an example of how:
* a CodedTool can make calls to other agents within an agent network.
* voting on multple calls to the same agent can yield better results.

---

## Prerequisites

Currently this agent network is tuned to be used with a specific OpenAI model (gpt-4.1-mini).
Further prompt optimization is needed to be sure other models/providers will work as well.

This agent network requires the following setup:

### Python Dependencies

This agent network requires langchain-openai to use the model that the prompts are tuned for.
This is already a prerequisite for the neuro-san library, so no need to install anything new.

### Environment Variables

```bash
export OPENAI_API_KEY="your_openai_api_key_here"
```

---

## Example Conversation

### Human

```text
What is 46048 × 42098?
```

This is an example of a long multiplication problem that is too big for a typical reasoning LLM 
to get right.

### AI

```text
1938528704
```

A fairly heavy-duty sly_data structure is also returned which outlines implementation details
of the decomposition process for assessing the approaches taken to problem solving.

---

## Architecture Overview

### Frontman Agent: multiagent_decomposer

- Main entry point for user inquiry. Requires at least an initial promblem description.

- max_depth and winning_vote_count can be tweaked from their defaults by simple statements added to the problem description text.

- Interprets natural language queries and delegates tasks to the decomposition_solver tool.

### Tool: decomposition_solver

This agent is a CodedTool that performs the required recursive decomposition by calling other agents
defined withinin the network.  We specifically do not leave this to LLM-based agents themselves to
carry out because there is quite a bit of state to properly maintain during the recrusive decomposition
and LLMs are not well-suited to this large-scale exact copy task.

The DecompostionSolver tool is also home to decent examples of the 3 things needed for CodedTools
to call back out to the agents available in the network:

1. The CodedTool must derive from BranchActivation and CodedTool.
   BranchActivation is an internal object used during the execution of a CodedTool.

2. When deriving from BranchActivation, the use_tool() method becomes available for use
   to actually call back out to other agents in the network by name. For this example,
   use_tool() actually gets invoked from multiple CodedToolAgentCaller instances
   used by the DecompositionSolver.

3. The agents called upon by use_tool() should be listed in the "tools" parameter of the
   decomposition_solver's args definition.  This is a dictionary mapping agent roles
   to concrete agent names within the network hocon file.  While the mapping itself
   may or not be used so abstractly by the BranchActivation/CodedTool implementation itself,
   the mapping is used as a convention to allow for proper connectivity reporting for visualizing
   clients.

Within this implementation there is also an example of using first-to-K voting.
In the future we may augment this with different voting strategies selectable by parameters.
For instance the original MAKER paper uses ahead-by-K voting, which is not yet implemented
for this example.

#### Tool Arguments and Parameters

- `problem`: The Description of a problem.

- `max_depth`: The maximum depth of solution decomposition.

- `winning_vote_count`: Number of votes for any one problem description or solution required to win.

- `candidate_count`: Number of candidates to consider during the decomposition stage.

- `number_of_votes`: Number of candidates for any round of voting.

- `solution_candidate_count`: Number of candidates to consider during the problem solving stage.

- `tools`: A dictionary of agents to use for various stages of the decomposition.
    Keys are strings which are names for abstract roles for the implementation to use,
    and values are strings which are concrete agent names from the hocon file.

    The values from this dictionary also contribute to better Connectivity() reporting
    over the neuro-san protocol when CodedTools are calling agents for visualizing clients.
    Without this information, the neuro-san system assumes that CodedTools are leaf nodes
    in the graph for Connectivity reporting.

    The tool role keys for this implementation simply have keys that correspond to their
    agent-name values, as we are not really using any dynamism here, but we still want to follow
    the tools argument convention for connectivity reporting. This particular tool
    can call each of the reamining agents programmatically.

##### Tool: decomposer

Receives a single problem statement and performs a single attempt to break the problem down into into exactly 2 smaller sub-problems.  This gets called repeatedly from the DecompositionSolver to get mulitple ideas for sub-problems.

##### Tool: solution_discriminator

Receives a problem statement along with a particular set of suggested decompositions of the problem.
This guy then checks each candidate for correctness with respect to the original problem description
and returns what it thinks would be the best candidate for breaking down the problem.
This gets called repeatedly from the DecompositionSolver as part of the voting process as to
which direction to take in the decompostion process.

##### Tool: problem_solver

This guy receives a problem statement and attempts to actually solve the problem via LLM magic.
This gets called repeatedly from the DecompositionSolver as part of the collection of potential
solutions for one of the sub-problems.

##### Tool: composition_discriminator

This guy receives a problem statement along with a particular set of suggested answers for the problem.
Not unlike the solution_discriminator, he returns what he thinks is the best candidate solution
for the problem.
This gets called repeatedly from the DecompositionSolver as part of the voting process as to
which solution is best for a particular problem decomposition.

---

## Debugging Hints

When developing or debugging with OpenAI models, keep the following in mind:

- **API Key Validation**: Ensure your `OPENAI_API_KEY` is valid and has access to preview tools.

- **Rate Limits**: Be aware of API rate limits that may affect LLM calling frequency.

### Common Issues

- **Import Errors**: Ensure langchain-openai is installed

- **Authentication Failures**: Verify API key is set and valid

- **Model Errors**: Confirm the specified GPT model is accessible

---

## Resources

- [Coded Tools Implementation Guide](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/user_guide.md#coded-tools)
  Learn how to implement and integrate custom coded tools in Neuro-SAN Studio.

- [Solving a Milltion-Step LLM Task with Zero Errors](https://arxiv.org/abs/2511.09030)
  The original MAKER paper from Meyerson, et al., 2025.  This paper did not originally use neuro-san,
  later expansions by Shahrzad and Hodjat led to this neuro-san implementation.
