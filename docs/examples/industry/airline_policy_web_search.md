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

This network follows a four-tier hierarchical architecture using the [AAOSA](../../user_guide.md) pattern:

1. **Frontman** (`Airline_Policy_Agent`) — the sole interface with the customer. Calls `Policy_Router` for answers and `Source_Resolver` for source URLs.
2. **Router and Resolver** (`Policy_Router`, `Source_Resolver`) — `Policy_Router` routes queries to one or more domain agents and composes a unified answer. `Source_Resolver` maps the agents used to their source URLs.
3. **Domain agents** — eighteen agents, each covering a narrow policy area, that delegate to a RAG leaf tool.
4. **RAG tools** — each domain agent owns a single `webpage_rag` tool that scrapes a specific airline FAQ or policy page at query time.

All answers are strictly grounded in content retrieved from the airline's webpages. External knowledge is never used.
When multiple pages return conflicting information, the system surfaces the conflict to the user rather than silently
resolving it.

---

## Example Conversation

### Human

```text
On a domestic Economy bundle fare, do I get a free carry-on bag?
```

### AI (Airline_Policy_Agent)

```text
Yes. On an Economy bundle fare, you get a personal item and a carry-on bag included.

Sources:
- https://faq.flyfrontier.com/help/what-is-the-difference-between-economy-premium-and-business-bundles
```

---

### Human

```text
What boarding and seating options are available for families traveling with young children?
```

### AI (Airline_Policy_Agent)

```text
Frontier offers a family seating guarantee for children 13 or younger traveling with an accompanying adult, but boarding options for families with young children are not provided in the retrieved information.

Seating (family seating guarantee):
- Frontier will guarantee adjacent seats for a child or children (13 years of age or younger) and an accompanying adult (over age 13) at no additional cost for all fare types, if all of the following are met:
  - The child (13 or younger) and the accompanying adult (over 13) are on the same reservation.
  - Adjacent seats are available at the time of booking in the selected class of service.
  - The adult either chooses seats for the entire reservation or skips seats for the entire reservation.
  - You must not make changes to seat assignments once seats are assigned.
  - It must be physically possible based on the seat layout to seat the number of children traveling next to the accompanying adult(s).

Boarding:
- The retrieved information does not include any specific boarding options for families traveling with young children (for example, family boarding or pre-boarding), so I can’t confirm what Frontier offers for boarding from the available content.

Sources:
- https://www.flyfrontier.com/travel-information/seating-options
- https://faq.flyfrontier.com/help/traveling-with-children-or-pets
```

---

## Architecture Overview

### Frontman Agent: **Airline_Policy_Agent**

- Acts as the sole interface with the customer — does not expose sub-agents or internal systems.
- Calls `Policy_Router` with the customer's question to get an answer and a list of agents used.
- Calls `Source_Resolver` with the list of agents used to get source URLs.
- Composes a final response by combining the answer with a "Sources:" section of URLs.

---

### Router and Resolver

| Agent | Role |
|---|---|
| `Policy_Router` | Routes customer queries to the relevant domain agents and composes a unified answer. Tags each response with the agents used. |
| `Source_Resolver` | Maps agent names to their source URLs using a fixed lookup table. |

---

### Domain Agents (Tools called by Policy_Router)

| Agent | Scope |
|---|---|
| `Optional_Services_Pricing` | Baggage fees, carry-on/checked bag size and weight limits, overweight/oversized fees, booking extras, premium services, and other optional service charges |
| `Bag_Count_Restrictions` | Maximum number of carry-on, personal item, and checked bags allowed |
| `Bag_Delayed` | Delayed or missing checked bag claims, tracking, and resolution procedures |
| `Bag_Damaged` | Damaged checked bag claims and what qualifies as damage |
| `Bag_Missing_Items` | Items missing from inside a checked bag or left on the aircraft or at the airport |
| `Sporting_Musical_Equipment` | Traveling with sporting equipment and musical instruments |
| `Firearms_Policy` | Rules, restrictions, and fees for traveling with firearms and ammunition |
| `Smart_Luggage` | Rules, restrictions, and fees for smart luggage containing lithium batteries |
| `Bundle_Differences` | Differences between Economy, Premium, and Business bundles |
| `Seating_Options` | Seat categories (First, UpFront Plus, Premium, Preferred, Standard), seat selection, elite seat upgrades, and family seating |
| `Food_And_Beverages` | In-flight food and beverage availability |
| `Miles_And_Points` | How Frontier miles and points are earned: spending rates, credit card earnings, and mileage partners |
| `Elite_Status_Benefits` | Elite Status tiers (Silver, Gold, Platinum, Diamond) and their travel benefits |
| `Military_Benefits` | Travel benefits for active U.S. military personnel and accompanying family |
| `Travel_Documents` | Accepted forms of ID (REAL ID) and travel document requirements for domestic and international travel |
| `Restricted_Items` | TSA allowed and prohibited items in carry-on and checked bags |
| `Kids_and_Pets` | Traveling with children and pets: lap infants, family seating, strollers, car seats, formula, and pet policies |
| `Accessibility` | Wheelchair assistance, mobility devices, oxygen and medical devices, service animals, sensory accommodations, unaccompanied minors, and special service requests |

---

## RAG Tools (Leaf Tool Layer)

Each domain agent owns a single `webpage_rag` tool from the toolbox that scrapes a specific airline URL at query time. The
agent answers solely from the retrieved content.

| RAG Tool | URL Scraped |
|---|---|
| `Optional_Services_Pricing_RAG` | `flyfrontier.com/optional-services/` |
| `Bag_Count_Restrictions_RAG` | `faq.flyfrontier.com/.../are-there-any-restrictions-on-how-many-bags-i-can-bring` |
| `Bag_Delayed_RAG` | `faq.flyfrontier.com/.../my-bag-is-delayed-who-can-i-talk-to` |
| `Bag_Damaged_RAG` | `faq.flyfrontier.com/.../my-bag-has-been-damaged-what-should-i-do` |
| `Bag_Missing_Items_RAG` | `faq.flyfrontier.com/.../what-do-i-do-if-an-item-is-missing-in-my-checked-bag` |
| `Sporting_Musical_Equipment_RAG` | `faq.flyfrontier.com/.../can-i-bring-sporting-or-musical-equipment-with-me` |
| `Firearms_Policy_RAG` | `faq.flyfrontier.com/.../can-i-bring-a-firearm-with-me` |
| `Smart_Luggage_RAG` | `faq.flyfrontier.com/.../can-i-bring-smart-luggage-on-my-flight` |
| `Bundle_Differences_RAG` | `faq.flyfrontier.com/.../what-is-the-difference-between-economy-premium-and-business-bundles` |
| `Seating_Options_RAG` | `flyfrontier.com/travel-information/seating-options` |
| `Food_And_Beverages_RAG` | `faq.flyfrontier.com/.../do-you-offer-complimentary-food-and-beverages-in-flight` |
| `Miles_And_Points_RAG` | `faq.flyfrontier.com/.../how-are-frontier-miles-and-points-earned` |
| `Elite_Status_Benefits_RAG` | `faq.flyfrontier.com/.../what-travel-benefits-are-included-with-elite-status` |
| `Military_Benefits_RAG` | `faq.flyfrontier.com/.../military-personnel-bags` |
| `Travel_Documents_RAG` | `faq.flyfrontier.com/.../what-identification-or-documents-do-i-need-in-order-to-travel` |
| `Restricted_Items_RAG` | `faq.flyfrontier.com/.../what-does-tsa-allow-and-not-allow-on-flights` |
| `Kids_and_Pets_RAG` | `faq.flyfrontier.com/.../traveling-with-children-or-pets` |
| `Accessibility_RAG` | `faq.flyfrontier.com/.../special-services` |

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
- **Missing sources**: `Airline_Policy_Agent` relies on parsing the `[USED_AGENTS]` tag from `Policy_Router`'s
  response to call `Source_Resolver`. If sources are missing, check that `Policy_Router` is emitting the tag and
  that every domain agent has a corresponding entry in `Source_Resolver`'s agent-to-URL mapping.
- **Timeout**: Each integration test interaction has a 180-second timeout. If tests are timing out, check
  network connectivity to the scraped URLs.
