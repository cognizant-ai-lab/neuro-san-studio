# KWIK Agents

The **KWIK Agents** is a basic multi-agent system that uses tools to remember new facts and to recall them and use them
in chatting with users.

**Note**: this demo will add a file to your directory store its memory in the file. You can turn this feature off by
changing LONG_TERM_MEMORY_FILE to False in [list_topics.py](../../coded_tools/kwik_agents/list_topics.py)

---

## File

[kwik_agents.hocon](../../registries/kwik_agents.hocon)

---

## Description

This network loads memory topics from the past, and uses relevant memories to respond to user chats. It also saves new
'facts' to memory if it encounters any in the user input.

This can be considered as an example of agent-oriented software that stores and retrieves memories into sly_data that
can in turn be persisted in a file.

---

## Example Conversation

### Human

```text
Bill has a dog named Max
```

### AI (agent_network_designer)

```text
Saved the fact that Bill has a dog named Max, under the topic 'pets'.
```

### Human

```text
Bill loves it. What is 'it' referring to?
```

### AI (agent_network_designer)

```text
Retrieved the fact that Bill has a dog named Max from memory. Based on this fact, 'it' refers to 'Max'.
```

[Stop and restart the session - the memory will be loaded from file]

### Human

```text
What do you know about Bill?
```

### AI (agent_network_designer)

```text
Retrieved the fact that Bill has a dog named Max from memory. Based on this fact, Bill has a pet named Max.
```

---

## Architecture Overview

### Frontman Agent: **kwik_agent**

- Acts as the entry point for all user commands.
- Follows a set of steps to:
    - retrieve past memory topics (this triggers a memory file load)
    - determines relevant topics and retrieves all memories related to those topics
    - stores to memory any new facts encountered in the user input
    - formulates a response based on the retrieved memories (if any)
- Note that the agent determines topics and memory entries by itself.
- Memory entries are time stamped

### Agents called by the Frontman

1. **list_topics**
   - Retrieves list of memory topics from sly_data (if any)
   - If no sly_data exists, it will attempt to load the memories from file.
   - See [list_topics.py](../../coded_tools/kwik_agents/list_topics.py)

2. **recall_memory**
   - Retrieves the memory entries associated with a given topic using the [recall_memory.py](../../coded_tools/kwik_agents/recall_memory.py)
   tool.

3. **commit_to_memory**
   - Adds a memory entry to a topic using the [commit_to_memory.py](../../coded_tools/kwik_agents/commit_to_memory.py) tool.
