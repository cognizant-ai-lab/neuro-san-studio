# Expedia

The **Expedia** agent network is a consumer-facing system designed to assist users with comprehensive travel planning, including flights, hotels, vacation packages, and customer support. The system embodies Expedia's mission to simplify travel and create memorable experiences through personalized service, transparent pricing, and seamless booking across all travel components.

---

## File

[expedia.hocon](../../../registries/industry/expedia.hocon)

---

## Description

This hierarchical multi-agent network coordinates end-to-end travel services through specialized agents handling flights, hotels, vacation packages, and customer support. The system operates from Expedia's corporate perspective, focusing on converting user inquiries into bookings while maintaining customer obsession, innovation, and operational excellence.

**Key Capabilities:**
- **Flight Management**: Search, book, and manage flight reservations with airline partner coordination.
- **Hotel Services**: Accommodation selection, booking, and hotel partner coordination for room availability and rates.
- **Vacation Packages**: Customized travel packages combining flights, hotels, and activities with competitive pricing.
- **Customer Support**: Comprehensive support for bookings, billing, technical issues, and problem resolution.
- **Partner Coordination**: Direct liaison with airline and hotel partners for availability, pricing, and issue resolution.

---

## Example Conversation

### Human

```text
I'm planning a trip to Hawaii in June. Need flights from New York and a hotel for 5 nights. Budget is around $2000 total for 2 people.
```

### AI (travel_consultant)

```text
I'd be delighted to help you plan your Hawaii trip! To find the best options for your June getaway, I need a few more details:

1. Which specific dates in June are you looking to travel? (Departure and return dates)
2. Which Hawaiian island are you most interested in? (Oahu, Maui, Kauai, or Big Island)
3. What type of hotel accommodation would you prefer? (beachfront resort, budget-friendly hotel, vacation rental)
4. Any preferences for amenities? (ocean view, pool, breakfast included, Wi-Fi)
5. Do you prefer direct flights or are you okay with layovers to save money?
```

### Human

```text
June 10-15, flying into Honolulu. Prefer a beachfront hotel with ocean view and pool. Direct flights would be great if they fit the budget.
```

### AI (travel_consultant)

```text
Perfect! I've found several excellent options for your Honolulu trip (June 10-15, 5 nights):

**Package Option 1: Premium Beachfront Experience**
- **Flight**: United Airlines JFK to HNL, direct flights
  - Departure: June 10, 8:45 AM - Arrival: 2:15 PM (local time)
  - Return: June 15, 5:30 PM - Arrival: June 16, 6:45 AM (next day)
  - 2 passengers: $1,240 total
- **Hotel**: Waikiki Beach Resort & Spa
  - Ocean view deluxe room
  - Amenities: Beachfront location, 3 pools, fitness center, free Wi-Fi
  - Rating: 4.5/5 (2,847 reviews)
  - 5 nights: $875
- **Package Total**: $2,115 (slightly over budget)
- **Special Offer**: Book as package and save $135 = **$1,980 total**

**Package Option 2: Best Value**
- **Flight**: Hawaiian Airlines JFK to HNL, direct flights
  - Departure: June 10, 10:15 AM - Arrival: 4:00 PM
  - Return: June 15, 7:45 PM - Arrival: June 16, 8:30 AM
  - 2 passengers: $1,180 total
- **Hotel**: Pacific Beach Hotel
  - Ocean view room
  - Amenities: Beachfront, 2 pools, free breakfast, Wi-Fi
  - Rating: 4.3/5 (1,562 reviews)
  - 5 nights: $750
- **Package Total**: $1,930
- **Expedia Rewards**: Earn $96 in travel credits

**Package Option 3: Budget-Friendly**
- **Flight**: Delta Airlines JFK to HNL, direct flights
  - Departure: June 10, 6:30 AM - Arrival: 12:15 PM
  - Return: June 15, 3:00 PM - Arrival: June 16, 4:15 AM
  - 2 passengers: $1,050 total
- **Hotel**: Aqua Palms Waikiki
  - Partial ocean view room
  - Amenities: 2 blocks from beach, rooftop pool, Wi-Fi
  - Rating: 4.2/5 (1,104 reviews)
  - 5 nights: $625
- **Package Total**: $1,675
- **Savings**: $325 under budget

**Recommendation**: I recommend **Package Option 2** (Pacific Beach Hotel) as it offers the best balance of value, location, and amenities within your $2000 budget, plus you'll earn Expedia Rewards credits. The free breakfast is an added bonus that will save you money during your stay.

Would you like to proceed with one of these packages, or would you like me to show you different options?
```

---

## Architecture Overview

### Frontman Agent: **travel_consultant**

- Serves as the primary interface for all customer travel inquiries.
- Provides customized travel planning across flights, hotels, car rentals, and activities.
- Handles cross-selling, upselling, and promotional opportunities.
- Maintains Expedia's commitment to customer satisfaction, inclusivity, and sustainability.

---

### Primary Agents (Tools called by the Frontman)

1. **flight_specialist**
   - Specializes in booking and managing flight reservations.
   - Assists with flight search, fare options, and booking modifications.
   - Handles cancellations, refunds, and fare rule clarifications.
   - Educates customers on loyalty programs and travel requirements.
   - Delegates to:
     - `airline_partner_coordinator` - Liaises with airlines for availability, fare negotiation, and issue resolution
       - Uses: `ExpediaSearch` - Web search tool via DuckDuckGo

2. **hotel_specialist**
   - Specializes in booking and managing hotel reservations.
   - Assists with accommodation selection, room options, and pricing.
   - Handles reservation modifications and problem resolution.
   - Educates customers on Expedia Rewards and package benefits.
   - Delegates to:
     - `hotel_partner_coordinator` - Liaises with hotels for room availability, rate negotiation, and issue resolution
       - Uses: `ExpediaSearch` - Web search tool via DuckDuckGo

3. **vacation_package_specialist**
   - Creates and manages vacation packages combining flights, hotels, and services.
   - Customizes packages to suit customer preferences and budgets.
   - Provides personalized hotel recommendations and booking assistance.
   - Handles reservation modifications and hotel-specific issues.
   - Delegates to:
     - `package_deal_coordinator` - Collaborates with service providers to create attractive vacation packages
       - Uses: `ExpediaSearch` - Web search tool via DuckDuckGo

4. **customer_support_representative**
   - Handles general customer inquiries and support for existing bookings.
   - Assists with cancellations, refunds, and account management.
   - Resolves issues and complaints with professionalism and empathy.
   - Manages technical platform issues and proactive customer assistance.
   - Delegates to:
     - `billing_specialist` - Manages billing inquiries, payments, and refund requests
     - `technical_support_specialist` - Provides assistance with technical platform issues

---

## External Dependencies

**DuckDuckGo Search API** (`/tools/ddgs_search`)

- **Tool Name**: ExpediaSearch
- **Used By**: `airline_partner_coordinator`, `hotel_partner_coordinator`, `package_deal_coordinator`
- **Purpose**: Simulates web searches on expedia.com to return URLs and options for flights, accommodations, and vacation packages
- **Quota Limitation**: Subject to DuckDuckGo's daily search quota limits
- **Impact if Unavailable**: The network will be unable to search for flights, hotels, or package options through partner coordinators, significantly limiting the ability to provide competitive pricing and availability information

---
