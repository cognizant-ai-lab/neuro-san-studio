# Booking.com

The **Booking.com** agent network is a consumer-facing system designed to assist users with comprehensive travel planning, including accommodations, pricing, vacation packages, and customer support. The system embodies Booking.com's mission of "making it easier for everyone to experience the world" through personalized recommendations, transparent pricing, and seamless booking assistance.

---

## File

[booking.hocon](../../../registries/industry/booking.hocon)

---

## Description

This hierarchical multi-agent network coordinates travel services through specialized agents handling trip planning, pricing optimization, and customer support. The system operates from Booking.com's corporate perspective, focusing on converting user inquiries into bookings while maintaining customer-centric service and transparency.

**Key Capabilities:**
- **Trip Planning**: Personalized destination selection, accommodation recommendations, and activity coordination.
- **Pricing Optimization**: Real-time pricing information, discount identification, and vacation package customization.
- **Customer Support**: Booking management, modifications, cancellations, and payment assistance.
- **Comprehensive Search**: Access to Booking.com's database of accommodations, activities, and travel options.
- **Loyalty Integration**: Genius program benefits and promotional offers.

---

## Example Conversation

### Human

```text
I need to book a hotel in Paris for a week in April. Looking for something central with breakfast included. Budget is around 150 euros per night.
```

### AI (booking_assistant)

```text
I'd be happy to help you find the perfect hotel in Paris for your week in April! Let me gather a few more details to provide the best options:

1. Which specific dates in April are you planning to visit?
2. How many guests will be staying?
3. Besides being central and including breakfast, are there any other amenities you need? (e.g., Wi-Fi, air conditioning, gym)
4. Do you prefer to be near specific landmarks or neighborhoods? (e.g., Eiffel Tower, Louvre, Marais, Latin Quarter)
5. What type of room would you like? (e.g., double room, suite)
```

### Human

```text
April 10-17, 2 adults, need Wi-Fi and air conditioning. Prefer to be near the Louvre or Marais. Double room is fine.
```

### AI (booking_assistant)

```text
Excellent! I've found several great hotel options in central Paris near the Louvre and Marais for April 10-17 (7 nights):

**Option 1: Hotel du Louvre**
- Location: 1st arrondissement, 0.2 km from Louvre Museum
- Price: €148/night (€1,036 total for 7 nights)
- Rating: 4.5/5 (1,234 reviews)
- Amenities: Free Wi-Fi, air conditioning, buffet breakfast included, fitness center
- Highlights: Historic building with Louvre views, 24-hour front desk
- Total Cost Breakdown:
  - Room: €1,036
  - City tax: €18
  - **Total: €1,054**

**Option 2: Le Marais Boutique Hotel**
- Location: 3rd arrondissement, Marais district
- Price: €142/night (€994 total for 7 nights)
- Rating: 4.6/5 (856 reviews)
- Amenities: Free Wi-Fi, air conditioning, continental breakfast, terrace
- Highlights: Charming boutique property in trendy Marais, walking distance to cafes
- Total Cost Breakdown:
  - Room: €994
  - City tax: €18
  - **Total: €1,012**

**Option 3: Central Paris Inn**
- Location: 4th arrondissement, between Louvre and Marais
- Price: €155/night (€1,085 total for 7 nights)
- Rating: 4.4/5 (2,103 reviews)
- Amenities: Free Wi-Fi, air conditioning, breakfast buffet, bar
- Highlights: Modern rooms, excellent location for sightseeing
- Genius Discount Available: Save 10% if you're a Genius member (€1,076 after discount)
- Total Cost Breakdown:
  - Room: €1,085 (€976 with Genius discount)
  - City tax: €18
  - **Total: €1,103 (€994 with Genius)**

**Recommendation**: I recommend **Option 2** for the best value in the heart of Marais with excellent reviews. If you prefer to be closest to the Louvre, **Option 1** is ideal. Option 3 offers great savings if you're a Genius member.

Would you like to proceed with one of these bookings, or would you like me to show more options?
```

---

## Architecture Overview

### Frontman Agent: **booking_assistant**

- Serves as the primary interface for all customer travel inquiries.
- Provides comprehensive solutions for accommodations, flights, and activities.
- Handles pricing transparency and booking facilitation.
- Maintains customer-centric approach aligned with Booking.com's values.

---

### Primary Agents (Tools called by the Frontman)

1. **trip_planner**
   - Assists customers in planning trips using Booking.com's AI Trip Planner.
   - Provides personalized recommendations for destinations, accommodations, and activities.
   - Creates flexible itineraries with mix-and-match travel components.
   - Delegates to:
     - `destination_specialist` - Provides detailed destination information and recommendations
       - Uses: `BookingSearch` - Web search tool via DuckDuckGo
     - `accommodation_specialist` - Assists with selecting suitable accommodations from listings
       - Uses: `BookingSearch` - Web search tool via DuckDuckGo
     - `activity_coordinator` - Suggests activities, tours, and local experiences
       - Uses: `BookingSearch` - Web search tool via DuckDuckGo

2. **pricing_specialist**
   - Provides real-time pricing information for accommodations and packages.
   - Identifies available promotions, discounts, and Genius loyalty benefits.
   - Offers cost-effective options and explains price fluctuations.
   - Delegates to:
     - `discount_advisor` - Informs about current discounts and promotional offers
     - `package_deal_expert` - Provides vacation packages combining accommodations, flights, and activities

3. **customer_support_representative**
   - Handles existing bookings, cancellations, and modifications.
   - Assists with booking confirmations, payment concerns, and support questions.
   - Manages complaints and escalations with empathy and efficiency.
   - Delegates to:
     - `booking_manager` - Manages booking changes, cancellations, and special requests
     - `payment_support_agent` - Assists with payment inquiries, billing issues, and refund requests

---

## External Dependencies

**DuckDuckGo Search API** (`/tools/ddgs_search`)

- **Tool Name**: BookingSearch
- **Used By**: `destination_specialist`, `accommodation_specialist`, `activity_coordinator`
- **Purpose**: Simulates web searches on booking.com to return URLs and options for accommodations, destinations, and activities
- **Quota Limitation**: Subject to DuckDuckGo's daily search quota limits
- **Impact if Unavailable**: The network will be unable to search for accommodations, destinations, or activities, significantly limiting its ability to provide travel recommendations and options

---
