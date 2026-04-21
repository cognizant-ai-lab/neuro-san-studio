# Coding Assistant

A coding problem solver that uses `AgentChecklistMiddleware` to plan and track its own
reasoning steps. The checklist is the agent's private internal scratchpad — it is never
shown to the user.

## File

[coding_assistant.hocon](../../../registries/basic/coding_assistant.hocon)

## Description

The Coding Assistant demonstrates how middleware can give an agent persistent working
memory across multiple model calls within a single session. When given a coding problem,
the agent must plan before writing any code: it creates an internal checklist that
decomposes the problem into reasoning steps (understand constraints, choose data
structure, design algorithm, write solution, validate, etc.), then works through each
step one at a time, marking steps `in_progress` and `done` as it goes.

The checklist state is injected into the system prompt automatically before every model
call by `AgentChecklistMiddleware`, so the agent always sees its current progress without
needing to query a tool. If the agent realises mid-solution that its approach needs to
change, it can rewrite individual checklist steps in place using `edit_checklist_item`
rather than discarding its entire plan.

Once all steps are done, the agent runs the solution through the `code_interpreter` tool
to verify correctness with the provided example inputs and at least one edge case before
presenting the final answer.

### Agents

- **`coding_problem_solver`** (front man): Receives the user's problem, creates and
  manages the internal checklist, writes the solution, and validates it with
  `code_interpreter`.
- **`code_interpreter`**: An OpenAI Code Interpreter toolbox agent that executes Python
  code and returns the output.

### Middleware

`AgentChecklistMiddleware` provides three tools to the agent:

| Tool | Purpose |
|---|---|
| `create_checklist(items)` | Create or replace the plan at the start of a problem |
| `update_checklist_item(index, status, notes?)` | Advance a step to `in_progress` or `done` |
| `edit_checklist_item(index, new_item)` | Rewrite a step's description when the approach changes |

## Example conversation

```text
Human: Given a list of integers, find all pairs that sum to a target value.

AI: [internally: creates checklist with steps — understand problem, identify edge cases,
    choose data structure, design algorithm, analyse complexity, write solution,
    run via code_interpreter, fix if needed]

    [works through each step, marking in_progress → done]

    [calls code_interpreter to run the solution]

    Here is the solution using a hash set for O(n) time complexity:

    def find_pairs(nums, target):
        seen = set()
        pairs = []
        for num in nums:
            complement = target - num
            if complement in seen:
                pairs.append((complement, num))
            seen.add(num)
        return pairs

    Approach: For each number, check if its complement (target - num) has already been
    seen. This avoids the O(n²) brute-force approach.

    Time: O(n) | Space: O(n)

    Output from code_interpreter:
      find_pairs([1, 2, 3, 4, 5], 6)  → [(1, 5), (2, 4)]
      find_pairs([], 6)               → []
      find_pairs([3, 3], 6)           → [(3, 3)]
```
