# Real Estate Agent

The **Real Estate Agent** is a multi-agent system that provides help with real estate transaction inquiries. The
top-level "front-man" agent receives a question, and in coordination with down-chain agents, provides an answer. Some of
the down-chain agents call coded tools. For example, the Listing agent calls the Brave search [APIs](https://brave.com/search/api/).

## File

[real_estate.hocon](../../../registries/industry/real_estate.hocon)

---

## Description

Provide the top-level "front-man" agent a question and it will call down-chain agents to determine if they are
responsible for all or part of question. It will then ask those down-chain agents what they need in order to handle their
part of the inquiry. Once the requirements are gathered, the top agent delegates the inquiry and the fulfilled requirements
to the appropriate down-chain agents. Some of the down-chain agents call coded tools. Once all down-chain agents respond,
the top agent will compile their responses and return the final response.

The "front-man" agent can call Buyer, Seller, and Listing agents. Those agents, in turn, can call other, more specific
agents. For example, the Buyer agent can call the Listing, Appraiser, Mortgage, Inspection, and Legal agents. The agent
network has the shape of a tree that is multiple layers deep.

---

## Example Conversation

### Human

```text
What are the steps in purchasing a house?
```

### AI (real_estate)

```text
To assist with purchasing a house, here are the steps and requirements:

Property Search and Viewing:

Find properties that match your preferences and budget. Schedule property viewings.
Mortgage Pre-Approval and Financing Options:

Requirements: Buyer's financial information, credit report, income details, employment history, and debt-to-income ratio.
Get pre-approved for a loan and explore financing options.
Property Appraisal:

Conduct property valuation and analyze market trends to get estimated value reports.
Assess the property's worth.
Legal and Contractual Steps:

Verify title deeds and ownership, and draft sales agreements and contracts.
Ensure all legal requirements are met.
Property Inspection:

Schedule an inspection to evaluate the property's condition.
Offer and Negotiation:

Make an offer on the property, and if accepted, negotiate terms and conditions.
Closing:

Finalize all paperwork, secure the mortgage, and complete the purchase transaction.
By following these steps and fulfilling the requirements, you can successfully navigate the process of purchasing a house.
```

---

## Architecture Overview

### Frontman Agent: **real_estate**

* Acts as the entry point for all user commands
* Can call Buyer, Seller, and Listing agents

### Agents called by the Frontman

1. **Buyer agent**
   * Responsible for Buyer-related inquiries
   * Can call Listing, Appraiser, Mortgage, Inspection, and Legal agents
   * Listing agent: Handles tasks realted to property listings
   * Appraiser agent: Handles tasks realted to appraising a property
   * Mortgage agent: Handles tasks related to getting a mortgage loan
   * Inspection agent: Handles tasks related to property inspection. Calls Brave search agent network (/tools/brave_search) to
   perform web search
   * Legal agent: Handles legal tasks for property transactions

2. **Seller agent**
   * Responsible for Seller-related inquiries
   * Can call Listing, and Legal agents
   * Listing agent: Handles tasks realted to property listings
   * Legal agent: Handles legal tasks for property transactions

3. **Listing agent**
   * Handles tasks related to property listings
   * Calls Brave search agent network (/tools/brave_search) to perform web search

---

## Functional Tools

These are coded tools called by Inspection and Listing agents:

* **BraveSearch**
    * Performs web search using Brave search API. Must set Brave search environment variables specified in .env.examples.

**Note**: it is assumed that the agent coordination mechanism is AAOSA.

---
