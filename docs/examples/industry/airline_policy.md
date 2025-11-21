# Airline Policy 360 Assistant

The **Airline Policy 360 Assistant** is a sophisticated multi-agent system designed to manage and respond to customer inquiries
by referring to related airline policies with structured delegation. It mimics a real-world helpdesk with specialized teams,
each handling a specific domain of airline policies such as baggage, flights, international travel, and more.

This demo can be modified and extended to other domains as needed.

---

## File

[airline_policy.hocon](../../../registries/industry/airline_policy.hocon)

---

## Description

This network follows a modular and hierarchical architecture: a top-level "front-man" agent delegates questions to the
relevant policy agents, which further delegate to sub-agents or tools if needed. All responses are given from the airline's
perspective, ensuring strict adherence to the given policy while maintaining clarity and helpfulness.

- **Domain Expertise Delegation**: Inquiries are routed to highly specialized agents that handle only what they are best
suited for. Agents may act as intermediaries—delegating part of a task to down-chain agents and compiling their responses.
- **Human-like Dialogue Management**: The front-man agent ensures a smooth, conversational experience by abstracting the
underlying agent collaboration from the user.
- **Document Intelligence**: Agents use a document extraction tool (`ExtractDocs`) to read airline policies from internal
texts and PDFs.
- **Resource Linking**: Agents call a `URLProvider` tool to fetch the official URLs related to a policy or topic.

---

## Example Conversation

### Human

```text
Can I carry my guitar as a cabin item on my flight to Madrid?
```

### AI (Airline Policy 360 Assistant)

```text
You can carry your guitar as a cabin item on your flight to Madrid under the following conditions:

1. **Carry-On Baggage Policy**: Your guitar can be considered a cabin item if it fits within the carry-on size limits, which
are 9 in x 14 in x 22 in (23 cm x 35 cm x 56 cm). If the guitar exceeds these dimensions, it may need to be gate-checked,
especially if the overhead space is limited. For detailed information, visit the [Carry On Baggage page](https://www.united.com/en/us/fly/baggage/carry-on-bags.html).

2. **Special Items Policy**: Musical instruments like guitars can be carried as cabin baggage if they meet the size and
weight restrictions. They should fit in the overhead bin or under the seat. For more details, visit the [Special Items section](https://www.tsa.gov/travel/security-screening/whatcanibring/sporting-and-camping).

3. **Basic Economy Considerations**: If you're flying under a Basic Economy fare, carry-on bags are generally not included
unless you're on specific international routes. Ensure the guitar fits the dimensions allowed for a personal item or carry-on.
Otherwise, it will need to be checked in, possibly incurring additional fees. For more information, check the
[Basic Economy Restrictions](https://www.united.com/en/us/fly/travel/inflight/basic-economy.html).

Please ensure your guitar fits within the specified dimensions and policies to avoid any issues during your travel.
```

---

## Architecture Overview

### Frontman Agent: **Airline 360 Assistant**

- Acts as the entry point for all user queries.
- Determines which sub-agents need to respond.
- Gathers and compiles final answers from sub-agents.

### Primary Domains (Tools called by the Frontman)

1. **Baggage_Handling**
   - Manages all baggage-related subdomains.
   - Delegates to:
     - `Carry_On_Baggage`
     - `Checked_Baggage`
     - `Bag_Issues`
     - `Special_Items`
     - `Bag_Fee_Calculator`

2. **Flights**
   - Deals with flight-specific policies.
   - Delegates to:
     - `Military_Personnel`
     - `Basic_Economy_Restrictions`
     - `Mileage_Plus`

3. **International_Travel**
   - Handles international-specific regulations.
   - Delegates to:
     - `International_Checked_Baggage`
     - `Embargoes`

---

## Functional Tools

These are coded tools called by various policy agents:

- **ExtractDocs**
    - Retrieves text content from internal policy documents.

    - **URLProvider**
    - Provides links to official airline pages for additional resources.

---

## Debugging Hints

Check the logs for:

- Whether the front-man correctly determined the responsible domains.
- If sub-agents asked for required parameters before generating an answer.
- Proper use of `ExtractDocs` and `URLProvider` for content and links.

---
