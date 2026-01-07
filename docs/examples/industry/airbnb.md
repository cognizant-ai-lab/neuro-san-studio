# Airbnb

The **Airbnb** agent network is a consumer-facing system designed to assist users with travel planning, including finding accommodations, booking experiences, and managing travel arrangements through Airbnb's platform. The system emphasizes personalized service, transparent pricing, and authentic local experiences aligned with Airbnb's mission of creating a world where anyone can belong anywhere.

---

## File

[airbnb.hocon](../../../registries/industry/airbnb.hocon)

---

## Description

This hierarchical multi-agent network coordinates travel planning services through specialized agents handling accommodations, pricing, vacation packages, and travel support. The system operates from Airbnb's corporate perspective, focusing on converting user inquiries into bookings while providing personalized recommendations and transparent information.

**Key Capabilities:**
- **Accommodation Discovery**: Search and recommend Airbnb listings based on user preferences, budget, and travel requirements.
- **Pricing Transparency**: Provide detailed cost breakdowns including base prices, fees, taxes, and available discounts.
- **Vacation Package Planning**: Create comprehensive travel itineraries combining accommodations and experiences.
- **Experience Booking**: Discover and book unique local experiences such as tours, classes, and activities.
- **Travel Support**: Handle booking modifications, cancellations, policy clarifications, and issue resolution.

---

## Example Conversation

### Human

```text
I'm looking for a place to stay in Austin, Texas for a weekend getaway next month. Budget is around $150 per night.
```

### AI (travel_planning_assistant)

```text
I'd be happy to help you find the perfect place in Austin for your weekend getaway! To provide the best recommendations, I need a few more details:

1. Which specific dates are you planning to visit? (This helps check availability and pricing)
2. How many guests will be staying?
3. What amenities are most important to you? (e.g., Wi-Fi, parking, kitchen, pool, pet-friendly)
4. Do you prefer to stay in a specific area of Austin? (e.g., downtown, near University of Texas, South Congress)
5. What type of accommodation interests you? (entire home, private room, unique stays)
```

### Human

```text
March 15-17, 2 guests, need Wi-Fi and parking. Prefer downtown or South Congress area. Entire home would be great.
```

### AI (travel_planning_assistant)

```text
Perfect! I've found several great options for your Austin weekend (March 15-17) in downtown and South Congress:

**Option 1: Modern Downtown Loft**
- Location: Downtown Austin, 0.4 miles from 6th Street
- Price: $145/night ($290 total for 2 nights)
- Amenities: Free Wi-Fi, dedicated parking spot, full kitchen, workspace
- Guest Rating: 4.8/5 (142 reviews)
- Highlights: Walking distance to restaurants and live music venues, recently renovated
- Total Cost Breakdown:
  - Base price: $290
  - Cleaning fee: $75
  - Service fee: $52
  - Taxes: $28
  - **Total: $445**

**Option 2: South Congress Bungalow**
- Location: South Congress, 0.2 miles from SoCo shopping district
- Price: $155/night ($310 total for 2 nights)
- Amenities: Free Wi-Fi, street parking, outdoor patio, full kitchen
- Guest Rating: 4.9/5 (87 reviews)
- Highlights: Charming historic home, walk to trendy shops and cafes
- Total Cost Breakdown:
  - Base price: $310
  - Cleaning fee: $60
  - Service fee: $55
  - Taxes: $30
  - **Total: $455**

**Option 3: East Austin Studio**
- Location: East Austin, 1.2 miles from downtown
- Price: $120/night ($240 total for 2 nights)
- Amenities: Free Wi-Fi, parking included, kitchenette
- Guest Rating: 4.7/5 (203 reviews)
- Highlights: Budget-friendly, near restaurants and parks, easy downtown access
- Total Cost Breakdown:
  - Base price: $240
  - Cleaning fee: $50
  - Service fee: $43
  - Taxes: $23
  - **Total: $356**

I recommend **Option 1** for the best downtown location and value, or **Option 2** if you want to be in the heart of South Congress. Would you like more details about any of these properties, or would you like me to help you book one?
```

---

## Architecture Overview

### Frontman Agent: **travel_planning_assistant**

- Serves as the primary interface for all user travel planning inquiries.
- Engages users to understand travel goals, preferences, and constraints.
- Delegates specialized tasks to domain experts while maintaining single point of contact.
- Coordinates personalized recommendations, pricing transparency, and seamless booking guidance.

---

### Primary Agents (Tools called by the Frontman)

1. **accommodation_specialist**
   - Finds and recommends Airbnb listings based on user preferences.
   - Filters properties by location, amenities, budget, ratings, and reviews.
   - Presents curated options with detailed property information and pricing.
   - Assists with decision-making and addresses special requests.
   - Delegates to:
     - `host_communication_facilitator` - Facilitates communication between guests and hosts for specific questions or requests

2. **pricing_and_discounts_advisor**
   - Provides detailed cost breakdowns for bookings (base price, fees, taxes).
   - Informs users about available discounts, promotions, and special offers.
   - Suggests cost-saving strategies (early booking, flexible dates, extended stays).
   - Explains Airbnb's pricing policies and payment terms.
   - Uses:
     - `AirbnbSearch` - Web search tool for finding accommodation options via DuckDuckGo

3. **vacation_packages_consultant**
   - Creates comprehensive travel itineraries combining accommodations and experiences.
   - Provides end-to-end planning with flexible mix-and-match options.
   - Offers transparent package pricing with itemized cost structures.
   - Guides users through booking process for all package components.
   - Delegates to:
     - `experience_booking_agent` - Books unique Airbnb experiences (tours, classes, activities)
       - Uses: `AirbnbSearch` - Web search tool for finding experiences

4. **travel_support_agent**
   - Handles booking modifications, cancellations, and policy clarifications.
   - Provides real-time problem solving for access issues or accommodation concerns.
   - Assists with travel disruptions and emergency situations.
   - Manages post-travel issue resolution and feedback collection.

---

## External Dependencies

**DuckDuckGo Search API** (`/tools/ddgs_search`)

- **Tool Name**: AirbnbSearch
- **Used By**: `pricing_and_discounts_advisor`, `experience_booking_agent`
- **Purpose**: Simulates web searches on airbnb.com to return URLs and options for accommodations and travel services
- **Quota Limitation**: Subject to DuckDuckGo's daily search quota limits
- **Impact if Unavailable**: The network will be unable to search for accommodations, experiences, or pricing information, severely limiting its ability to provide recommendations