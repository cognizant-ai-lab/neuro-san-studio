# Consumer Decision Assistant

The **Consumer Decision Assistant** is a multi-agent system designed to help consumers make informed decisions across various domains including retail purchases, travel planning, financial planning, career development, lifestyle choices, and healthcare. The system operates as a consumer advocate, interacting with external B2C business agent networks while maintaining focus on the user's best interests rather than corporate objectives.

**Note**: This agent network calls other external agent networks representing businesses (Macy's, CarMax, Booking, Expedia, Airbnb, LinkedIn). These downstream networks use web search capabilities with DuckDuckGo, subject to daily quota limits.

---

## File

[consumer_decision_assistant.hocon](../../../registries/industry/consumer_decision_assistant.hocon)

---

## Description

This hierarchical multi-agent network coordinates six specialized domain experts to assist users in making complex decisions. The system delegates user inquiries to appropriate domain specialists, who conduct research by querying external business agent networks and compiling recommendations based on the user's preferences, constraints, and priorities.

**Key Capabilities:**
- **Cross-Domain Decision Support**: Handles retail, travel, financial, career, lifestyle, and healthcare decisions.
- **External Network Integration**: Calls external B2C business agent networks and negotiates on behalf of the consumer.
- **Consumer-Centric Approach**: Agents are instructed to withhold unnecessary information from external networks and prioritize user interests over corporate interests.
- **Structured Decision Framework**: Guides users through clarifying objectives, researching options, comparing alternatives, and making final decisions.

---

## Example Conversation

### Human

```text
I need to book a room in downtown Santa Cruz for this weekend. My budget is less than $250.
```

### AI (decision_consultant)

```text
I'll help you find accommodation in downtown Santa Cruz for this weekend within your $250 budget. Let me gather some
additional details to provide the best options:

1. How many nights will you be staying?
2. How many guests will be staying in the room?
3. Do you have any specific preferences for amenities (parking, Wi-Fi, breakfast, pet-friendly, etc.)?
4. What is your preferred accommodation type (hotel, vacation rental, hostel)?

Once I have this information, I'll search across multiple platforms to find the best options that match your criteria
and budget.
```

### Human

```text
2 nights, 2 guests, need parking and Wi-Fi. Hotel or vacation rental is fine.
```

### AI (decision_consultant : travel_decision_specialist)

```text
I've researched accommodation options in downtown Santa Cruz for 2 nights this weekend for 2 guests with parking and
Wi-Fi. Here are the best options within your $250 budget:

**Option 1: Hotel Santa Cruz** (via Booking)
- Price: $230 for 2 nights
- Location: Downtown Santa Cruz, 0.3 miles from Beach Boardwalk
- Amenities: Free Wi-Fi, free parking, complimentary breakfast
- Rating: 4.2/5 (based on 340 reviews)
- Pros: Central location, includes breakfast, free parking
- Cons: Older building, limited room sizes

**Option 2: Coastal Vacation Rental** (via Airbnb)
- Price: $245 for 2 nights
- Location: Downtown area, 0.5 miles from Beach Boardwalk
- Amenities: Full kitchen, Wi-Fi, 1 parking spot, washer/dryer
- Rating: 4.6/5 (based on 87 reviews)
- Pros: More space, full kitchen, highly rated
- Cons: Slightly farther from boardwalk, no daily housekeeping

**Option 3: Pacific Inn Downtown** (via Expedia)
- Price: $210 for 2 nights
- Location: Downtown Santa Cruz, walking distance to restaurants
- Amenities: Free Wi-Fi, parking ($10/night additional)
- Rating: 3.9/5 (based on 215 reviews)
- Pros: Lowest base price, good location
- Cons: Parking costs extra, lower ratings for room condition

**Recommendation**: Option 2 (Coastal Vacation Rental) offers the best value if you want more space and amenities.
Option 1 (Hotel Santa Cruz) is ideal if you prefer traditional hotel service with breakfast included.

Would you like me to provide booking links or additional details about any of these options?
```

---

## Architecture Overview

### Frontman Agent: **decision_consultant**

- Serves as the primary interface for all user inquiries.
- Determines which domain specialist(s) to engage based on the user's decision-making needs.
- Coordinates information gathering, option comparison, and final recommendation delivery.
- Manages user interaction through clarifying questions and structured decision guidance.

---

### Primary Domains (Tools called by the Frontman)

1. **retail_decision_specialist**
   - Assists with retail purchase decisions all the way from home goods to cars.
   - Delegates to:
     - `product_researcher` - Researches products via external networks: [macys](../../../registries/industry/macys.hocon), [carmax](../../../registries/industry/carmax.hocon)
     - `price_comparison_agent` - Compares prices across retailers via: [macys](../../../registries/industry/macys.hocon), [carmax](../../../registries/industry/carmax.hocon)

2. **travel_decision_specialist**
   - Helps plan and compare travel options including destinations, accommodations, and transportation.
   - Delegates to:
     - `destination_researcher` - Researches destinations via: [airbnb](../../../registries/industry/airbnb.hocon), [expedia](../../../registries/industry/expedia.hocon), [booking](../../../registries/industry/booking.hocon)
     - `travel_cost_analyzer` - Analyzes travel costs via: [airbnb](../../../registries/industry/airbnb.hocon), [expedia](../../../registries/industry/expedia.hocon), [booking](../../../registries/industry/booking.hocon)

3. **financial_decision_specialist**
   - Assists with financial decisions including investments, loans, and savings plans.
   - Delegates to:
     - `investment_researcher` - Researches investment opportunities (stocks, bonds, real estate)
     - `loan_evaluator` - Compares loan options based on interest rates, terms, and eligibility

4. **career_decision_specialist**
   - Guides users through career decisions including job changes, skill development, and long-term planning.
   - Delegates to:
     - `job_opportunity_researcher` - Researches job opportunities via: [LinkedInJobSeekerSupportNetwork](../../../registries/industry/LinkedInJobSeekerSupportNetwork.hocon)
     - `skill_development_advisor` - Identifies training programs, certifications, and skill development resources

5. **lifestyle_decision_specialist**
   - Supports decisions related to hobbies, personal development, and relationships.
   - Delegates to:
     - `hobby_explorer` - Researches potential hobbies based on user preferences and resources
     - `relationship_guidance_agent` - Provides decision-making support for relationship matters

6. **healthcare_decision_specialist**
   - Helps users make healthcare decisions including selecting doctors, treatments, and wellness plans.
   - Delegates to:
     - `doctor_researcher` - Researches healthcare providers based on specialization, location, and reviews
     - `treatment_comparator` - Compares treatment options based on efficacy, costs, and user preferences

---

## External Agent Networks

The system integrates with six external B2C business agent networks:

1. **[macys](../../../registries/industry/macys.hocon)** - Retail product information and pricing
2. **[carmax](../../../registries/industry/carmax.hocon)** - Vehicle purchasing information
3. **[airbnb](../../../registries/industry/airbnb.hocon)** - Vacation rental accommodations
4. **[expedia](../../../registries/industry/expedia.hocon)** - Travel bookings (flights, hotels)
5. **[booking](../../../registries/industry/booking.hocon)** - Hotel and accommodation bookings
6. **[LinkedInJobSeekerSupportNetwork](../../../registries/industry/LinkedInJobSeekerSupportNetwork.hocon)** - Job search and career information

**Note**: Agents interacting with external networks are instructed to protect consumer interests, as these networks represent corporate entities whose goals may not fully align with the user's needs.

---

## External Dependencies

**DuckDuckGo Search API** (`/tools/ddgs_search`)

The downstream B2C business networks rely on the DuckDuckGo search API to simulate web searches and return information:

- **Networks using DuckDuckGo**: airbnb, booking, expedia, carmax, LinkedInJobSeekerSupportNetwork (5 out of 6)
- **Network NOT using DuckDuckGo**: macys (uses internal knowledge/simulation only)
- **Quota Limitation**: Subject to DuckDuckGo's daily search quota limits
- **Purpose**: Simulates web searches to return URLs and business information in response to consumer queries

**Important**: If DuckDuckGo quota limits are reached, the affected downstream networks may fail to provide search results, impacting the consumer decision assistant's ability to research options across travel, career, and automotive domains.

---

## Testing

This agent network includes comprehensive test coverage:

[consumer_decision_assistant_comprehensive.hocon](../../../tests/fixtures/industry/consumer_decision_assistant_comprehensive.hocon) - Tests all major domain specialists (travel, automotive, career, retail) with independent single-turn questions

Run tests using:
```bash
# Run comprehensive domain test
pytest tests/integration/test_integration_test_hocons.py -k "comprehensive"
```
