# Airline Policy Web Search Assistant

The **Airline Policy Web Search Assistant** is a multi-agent system that answers customer questions about airline
policies by scraping the airline's official webpages at runtime. It requires no coded tools — built entirely using
AAOSA and the toolbox — and covers baggage, fares, seating, loyalty programs, travel requirements, and special
assistance, all grounded strictly in live content retrieved from the airline's own site.

---

## File

[airline_policy_web_search.hocon](../../../registries/industry/airline_policy_web_search.hocon)

---

## Description

This network follows a three-tier hierarchical architecture using the [AAOSA](../../user_guide.md) pattern:

1. **Frontman** (`Policy_Assistant`) — the sole interface with the customer. Routes queries to one or more domain agents.
2. **Domain agents** — eleven mid-tier agents, each covering a narrow policy area, that delegate to a RAG leaf tool.
3. **RAG tools** — each domain agent owns a single `webpage_rag` tool that scrapes a fixed set of the airline's FAQ
   and policy pages at query time.

All answers are strictly grounded in content retrieved from the airline's webpages. External knowledge is never used.
When multiple pages return conflicting information, the system surfaces the conflict to the user rather than silently
resolving it.

---

## Prerequisites

This agent network uses the `webpage_rag` toolbox, which scrapes live URLs at runtime.

Ensure the `webpage_rag` toolbox is registered and its dependencies are installed. See
[Toolbox Reference](../../toolbox.md) for setup instructions.

---

## Example Conversation

### Human

```text
On a domestic Economy bundle fare, do I get a free carry-on bag?
```

### AI (Policy_Assistant)

```text
Yes — on a domestic Economy bundle fare, carry-on bags are included for free. You are entitled to one carry-on bag
at no additional charge under this fare type.

For size and weight requirements for carry-on bags, please refer to the airline's baggage policy page.
```

---

### Human

```text
What boarding and seating options are available for families traveling with young children?
```

### AI (Policy_Assistant)

```text
Families traveling with children 13 and under are guaranteed an adjacent seat with an accompanying adult at no extra
cost, provided all travelers are on the same reservation. The airline's family seating policy ensures children are
not separated from their parent or guardian.

Additional boarding assistance for families with young children may be available — check in with gate staff for
early boarding options.
```

---

## Architecture Overview

### Frontman Agent: **Policy_Assistant**

- Acts as the sole interface with the customer — does not expose sub-agents or internal systems.
- Reads the customer query and simultaneously calls all domain agents whose scope is relevant.
- Merges sub-agent responses into a single, complete answer — never drops restrictions, fee tiers, or profile-based variations.
- Surfaces conflicting information found across pages rather than silently resolving it.

---

### Domain Agents (Tools called by the Frontman)

| Agent | Scope |
|---|---|
| `Baggage_Info` | Carry-on and checked bag size/weight limits, quantity limits, pricing, overweight/oversized fees, fare bundle inclusions, optional services |
| `Bag_Issues` | Post-travel checked bag problems: delayed, damaged, or missing items |
| `Special_Baggage` | Non-standard items: sporting equipment, musical instruments, firearms, bicycles, smart luggage |
| `Fare_Info` | Fare inclusions/exclusions; Economy, Premium, and Business bundle differences |
| `Seating_And_Amenities` | Seat categories (UpFront Plus, Premium, Preferred, standard), seat selection, elite upgrade windows, in-flight food and beverages |
| `Loyalty_Program` | Elite status tiers (Silver, Gold, Platinum, Diamond), qualification thresholds, and associated travel benefits |
| `Military_Benefits` | Travel benefits for military personnel and eligible accompanying family members |
| `Travel_Documents_And_Guidelines` | Domestic ID requirements, international passports and travel documents, children's ID rules |
| `Restricted_Items` | TSA allowed and prohibited items on flights |
| `Kids_and_Pets` | Traveling with children and pets: lap infants, family seating, strollers, car seats, formula, pet species and fees |
| `Accessibility` | Wheelchair assistance, mobility aids, oxygen and medical devices, service animals, sensory accommodations, unaccompanied minors |

---

## RAG Tools (Leaf Tool Layer)

Each domain agent owns a single `webpage_rag` tool from the toolbox that scrapes a fixed set of the airline's URLs at query time. The
agent answers solely from the retrieved content.

| RAG Tool | URLs Scraped |
|---|---|
| `Baggage_Info_RAG` | Optional services page, bag quantity limits FAQ |
| `Bag_Issues_RAG` | Delayed bag FAQ, damaged bag FAQ, missing items FAQ |
| `Special_Baggage_RAG` | Sporting/musical equipment FAQ, firearms FAQ, smart luggage FAQ |
| `Fare_Info_RAG` | What's included in fare FAQ, bundle differences FAQ |
| `Seating_And_Amenities_RAG` | Seating options page, food and beverages FAQ |
| `Loyalty_Program_RAG` | Miles and points earning FAQ, elite status benefits FAQ |
| `Military_Benefits_RAG` | Military personnel bags FAQ |
| `Travel_Documents_And_Guidelines_RAG` | ID and travel documents FAQ |
| `Restricted_Items_RAG` | TSA allowed/prohibited items FAQ |
| `Kids_and_Pets_RAG` | Traveling with children or pets FAQ |
| `Accessibility_RAG` | Special services FAQ |

---

## Test Fixtures

23 integration tests for this agent network are located in
[tests/fixtures/industry/airline_policy_web_search/](../../../tests/fixtures/industry/airline_policy_web_search/).

---

## Debugging Hints

- **No external knowledge**: Every claim in the answer must trace back to a sub-agent response from a RAG tool.
  If the agent is hallucinating, check whether the tool is actually being called.
- **RAG content gaps**: If a leaf agent says information is unavailable, verify the target URLs are reachable
  and returning expected content. Page structure changes can cause silent content gaps, or a page may have moved to a different URL.
- **Conflicting pages**: The system is designed to surface conflicts across pages. If the answer omits a
  conflict you expect, check whether the relevant RAG tools were both called.
- **Timeout**: Each integration test interaction has a 180-second timeout. If tests are timing out, check
  network connectivity to the scraped URLs.
