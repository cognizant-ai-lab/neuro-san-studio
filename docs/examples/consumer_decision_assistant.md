# Consumer Decision Assistant

The **Consumer Decision Assistant** is a multi-agent system that helps consumers with their decisions. This agent network
makes calls to other agent networks from B2C businesses that might not be fully aligned.

**Note**: This agent-network calls other agent networks, which in turn call a web search agent that uses duckduckgo, with
a limited daily search quota.

---

## File

[consumer_decision_assistant.hocon](../../registries/consumer_decision_assistant.hocon)

---

## Description

This network helps with various consumer decisions, ranging from purchases, to travel planning, to hobby selection.

This is an example of agents calling other external agent networks.

---

## Example Conversation

### Human

```text
I need to book a room in downtown Santa Cruz for this weekend. My budget is less than $250.
```

### AI (agent_network_designer)

```text
TBD
```

---

## Architecture Overview

### Frontman Agent: **decision_consultant**

- Acts as the entry point for all user commands.

### Agents calling other agent networks

1. **product_researcher**
   - This agent calls the [macys](../../registries/macys.hocon) and the [carmax](../../registries/carmax.hocon) agent
   network front-men.

2. **destination_researcher** and **travel_cost_analyzer**
   - These agents call the [booking](../../registries/booking.hocon), [expedia](../../registries/expedia.hocon) and
 the [airbnb](../../registries/airbnb.hocon) agent network front-men.

3. **job_opportunity_researcher**
   - This agent calls the [LinkedInJobSeekerSupportNetwork](../../registries/LinkedInJobSeekerSupportNetwork.hocon) agent
   network front-man.
