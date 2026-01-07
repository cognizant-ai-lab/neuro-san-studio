# CarMax

The **CarMax** agent network is a consumer-facing system designed to assist customers with vehicle purchases, service appointments, and financing inquiries. The system embodies CarMax's commitment to integrity, transparency, and customer satisfaction through a hassle-free car-buying and service experience.

---

## File

[carmax.hocon](../../../registries/industry/carmax.hocon)

---

## Description

This hierarchical multi-agent network coordinates automotive sales, service, and financing through specialized agents handling vehicle selection, maintenance, and loan processing. The system operates from CarMax's corporate perspective, focusing on providing exceptional customer service with no-pressure sales and transparent information.

**Key Capabilities:**
- **Vehicle Sales**: Inventory search, vehicle recommendations, test drive coordination, and purchase guidance.
- **Service Coordination**: Maintenance scheduling, repair services, vehicle status updates, and parts management.
- **Financing Assistance**: Loan application processing, credit analysis, underwriting, and payment plan explanations.
- **Customer Support**: Comprehensive assistance across sales, service, and finance departments.

---

## Example Conversation

### Human

```text
I'm looking for a reliable used SUV for my family. Budget is around $25,000. What do you have available?
```

### AI (customer_service_representative)

```text
I'd be happy to help you find the perfect family SUV! To recommend the best options from our inventory, I need a few more details:

1. How many passengers do you need to accommodate? (5, 7, or 8 seaters)
2. What features are most important to you? (e.g., third-row seating, good fuel economy, advanced safety features, all-wheel drive)
3. Do you have any brand or model preferences?
4. What's your zip code? (This helps me show you vehicles available at nearby CarMax locations or that can be transferred to you)
5. Are you considering trading in your current vehicle?
```

### Human

```text
Need 7 seats, prefer good safety ratings and fuel efficiency. No brand preference. Zip code 30318. Yes, I have a 2015 Honda Accord to trade in.
```

### AI (customer_service_representative)

```text
Excellent! I've searched our inventory for 7-seater SUVs with strong safety ratings and fuel efficiency near Atlanta (30318). Here are the top options within your $25,000 budget:

**Option 1: 2019 Honda Pilot EX-L**
- Price: $24,998
- Mileage: 42,500 miles
- Features: 8-passenger seating, Honda Sensing safety suite, 19/26 MPG city/highway
- Safety: 5-star NHTSA rating
- Location: CarMax Atlanta - Available for test drive today
- Warranty: CarMax Limited Warranty included, extended warranties available

**Option 2: 2020 Toyota Highlander LE**
- Price: $24,795
- Mileage: 38,200 miles
- Features: 8-passenger seating, Toyota Safety Sense 2.0, 21/29 MPG city/highway
- Safety: IIHS Top Safety Pick
- Location: CarMax Kennesaw - Can transfer to Atlanta in 3-5 days
- Warranty: CarMax Limited Warranty included

**Option 3: 2018 Mazda CX-9 Touring**
- Price: $23,495
- Mileage: 48,900 miles
- Features: 7-passenger seating, i-ACTIVSENSE safety features, 20/26 MPG city/highway
- Safety: 5-star NHTSA rating
- Location: CarMax Atlanta - Available now
- Warranty: CarMax Limited Warranty included

**Trade-In Information:**
Based on your 2015 Honda Accord, I can provide a preliminary trade-in estimate. To get an accurate appraisal, I'll need:
- Current mileage
- Trim level (LX, Sport, EX, EX-L, Touring)
- Overall condition

You can also get an instant online offer at carmax.com that's valid for 7 days.

**Next Steps:**
1. Would you like to schedule a test drive for any of these SUVs?
2. Would you like information about financing options? CarMax Auto Finance can pre-qualify you in minutes.
3. I can arrange a trade-in appraisal for your Accord at the same time as your test drive.

Which option interests you most, or would you like to see more vehicles?
```

---

## Architecture Overview

### Frontman Agent: **customer_service_representative**

- Serves as the primary contact for all customer inquiries.
- Handles vehicle purchases, service scheduling, and financing questions.
- Provides comprehensive assistance and guides customers through CarMax processes.
- Maintains CarMax's commitment to integrity, transparency, and customer satisfaction.

---

### Primary Agents (Tools called by the Frontman)

1. **sales_consultant**
   - Assists customers in selecting and purchasing vehicles from inventory.
   - Provides detailed vehicle information and facilitates test drives.
   - Guides customers through the purchasing process with no-pressure approach.
   - Delegates to:
     - `inventory_specialist` - Manages vehicle inventory and availability information
       - Uses: `carmax_search` - Web search tool for inventory via DuckDuckGo
     - `test_drive_coordinator` - Schedules and organizes test drives with vehicle preparation

2. **service_advisor**
   - Coordinates vehicle service appointments and maintenance.
   - Provides information on repair services and estimated costs.
   - Keeps customers informed about vehicle status during service.
   - Delegates to:
     - `technician` - Performs maintenance and repairs on customer vehicles
     - `parts_specialist` - Manages parts inventory and coordinates with technicians

3. **finance_specialist**
   - Provides information and assistance regarding CarMax Auto Finance options.
   - Helps customers understand loan terms and payment structures.
   - Assists with financing applications and documentation.
   - Delegates to:
     - `loan_underwriter` - Assesses and approves auto loan applications
     - `credit_analyst` - Analyzes customer credit reports for loan eligibility

---

## External Dependencies

**DuckDuckGo Search API** (`/tools/ddgs_search`)

- **Tool Name**: carmax_search
- **Used By**: `inventory_specialist`
- **Purpose**: Searches carmax.com to return URLs for available vehicles in CarMax inventory
- **Quota Limitation**: Subject to DuckDuckGo's daily search quota limits
- **Impact if Unavailable**: The network will be unable to search for vehicle inventory, significantly limiting the ability to provide vehicle recommendations and availability information to customers

---


