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
2. **Domain agents** — five mid-tier agents that coordinate a functional area and delegate to leaf agents.
3. **Leaf agents** — specialized agents that each own a narrow topic and call a `webpage_rag` RAG tool to scrape the
   airline's FAQ and policy pages at query time.

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

1. **Baggage_Handling**
   - Covers all baggage policies: carry-on items, checked bags, bag fees and quantity limits, bag issues, and special baggage.
   - Delegates to:
     - `Baggage_Info` — carry-on and checked bag size/weight limits, pricing, overweight and oversized fees
     - `Bag_Issues` — delayed, damaged, and missing item claims for checked bags
     - `Special_Baggage` — sporting equipment, musical instruments, firearms, bicycles, and smart luggage

2. **Fares_And_Seating**
   - Covers fare types, bundle differences, seating categories, and in-flight amenities.
   - Delegates to:
     - `Fare_Info` — what is included or excluded in the base fare; Economy, Premium, and Business bundle differences
     - `Seating_And_Amenities` — seat types, seat selection, elite upgrade windows, and in-flight food and beverages

3. **Loyalty_And_Benefits**
   - Covers the airline's loyalty program and military travel benefits.
   - Delegates to:
     - `Loyalty_Program` — earning miles and points, elite status tiers and travel benefits, co-branded credit card perks, and partner earning opportunities
     - `Military_Benefits` — military baggage allowances, fee waivers, eligibility, and benefits for accompanying family members

4. **Travel_Requirements**
   - Covers pre-flight documentation and TSA restrictions.
   - Delegates to:
     - `Travel_Documents` — domestic ID requirements, international passports and travel documents, children's ID rules, permanent resident travel
     - `Restricted_Items` — TSA allowed and prohibited items on flights

5. **Special_Assistance**
   - Covers passengers with special needs: families, pets, and accessibility services.
   - Delegates to:
     - `Kids_And_Family` — traveling with small children, Kids Fly Free program, family seating guarantee
     - `Pets` — allowed species, carrier size limits, fees, minimum pet age, international restrictions
     - `Accessibility` — wheelchair assistance, battery-powered mobility aids, traveling with oxygen and medical devices

---

## RAG Tools (Leaf Tool Layer)

Each leaf agent owns a single `webpage_rag` tool from the toolbox that scrapes a fixed set of the airline's URLs at query time. The
leaf agent answers solely from the retrieved content.

| RAG Tool | URLs Scraped |
|---|---|
| `Baggage_Info_RAG` | Bag size/weight limits FAQ, bag quantity FAQ, bag pricing FAQ, optional services page |
| `Bag_Issues_RAG` | Delayed bag FAQ, damaged bag FAQ, missing items FAQ |
| `Special_Baggage_RAG` | Sporting/musical equipment FAQ, firearms FAQ, bicycle FAQ, smart luggage FAQ |
| `Fare_Info_RAG` | What's included in fare FAQ, what's not included FAQ, bundle differences FAQ |
| `Seating_And_Amenities_RAG` | Seating options page, upfront/premium/preferred seating FAQ, food and beverages FAQ |
| `Loyalty_Program_RAG` | Miles and points earning FAQ, how-to-earn-miles page, elite status benefits FAQ |
| `Military_Benefits_RAG` | Military personnel bags FAQ |
| `Travel_Documents_RAG` | ID and travel documents FAQ, international travel and security page |
| `Restricted_Items_RAG` | TSA allowed/prohibited items FAQ |
| `Kids_And_Family_RAG` | Traveling with small children FAQ, Kids Fly Free FAQ, family seating FAQ |
| `Pets_RAG` | Pets on the plane FAQ |
| `Accessibility_RAG` | Wheelchair travel FAQ, airport wheelchair availability FAQ, battery-powered mobility aid FAQ, oxygen FAQ, medicine and medical devices FAQ |

---

## Test Fixtures

21 integration tests for this agent network are located in
[tests/fixtures/industry/airline_policy_web_search/](../../../tests/fixtures/industry/airline_policy_web_search/).

---

## Debugging Hints

- **No external knowledge**: Every claim in the answer must trace back to a sub-agent response from a RAG tool.
  If the agent is hallucinating, check whether the tool is actually being called.
- **Agent routing**: Confirm the frontman called all relevant domain agents for a given query. A query about
  carry-on bags in Economy should route to both `Baggage_Handling` and `Fares_And_Seating`.
- **RAG content gaps**: If a leaf agent says information is unavailable, verify the target URLs are reachable
  and returning expected content. Page structure changes can cause silent content gaps, or a page may have moved to a different URL.
- **Conflicting pages**: The system is designed to surface conflicts across pages. If the answer omits a
  conflict you expect, check whether the relevant RAG tools were both called.
- **Timeout**: Each integration test interaction has a 180-second timeout. If tests are timing out, check
  network connectivity to the scraped URLs.
