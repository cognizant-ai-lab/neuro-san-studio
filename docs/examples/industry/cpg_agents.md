# CPG Operations Management

The **CPG Operations Management** agent network is a comprehensive enterprise system designed
to coordinate global operations for a Consumer Packaged Goods (CPG) company. The system
manages cross-functional activities including supply chain, product development, sales and
marketing, and regional operations through a hierarchical leadership structure.

---

## File

[cpg_agents.hocon](../../../registries/industry/cpg_agents.hocon)

---

## Description

This hierarchical multi-agent network simulates the C-suite and executive leadership
structure of a global CPG company. The system coordinates strategic decision-making,
operational execution, and cross-departmental alignment through specialized vice presidents
and functional managers reporting to a Chief Operating Officer.

Key Capabilities:

- **Strategic Operations Oversight**: Executive-level coordination across all functional areas.
- **Supply Chain Management**: End-to-end management of sourcing, manufacturing, and logistics.
- **Product Development**: Research, design, and quality assurance for new and existing products.
- **Sales and Marketing**: Global brand strategy, digital marketing, and sales operations.
- **Regional Coordination**: Local execution of global strategies with regional customization.

---

## Example Conversation

### Human

```text
We're experiencing supply chain delays in our Southeast Asia region that are affecting
our new product launch. Can you help me understand the root cause and develop a
mitigation plan?
```

### AI (chief_operating_officer)

```text
I'll help you address the supply chain delays affecting your Southeast Asia product
launch. To develop an effective mitigation plan, I need to gather some key information:

1. Which specific countries or facilities in Southeast Asia are experiencing delays?
2. What product line is affected by this launch?
3. What is the planned launch date?
4. What type of delays are occurring? (raw material sourcing, manufacturing,
   logistics/shipping, or warehousing)
5. How significant are the delays? (days, weeks, or months)
6. What is the production volume target for this launch?

This information will help me coordinate with our supply chain, regional operations,
and product development teams to identify root causes and develop actionable solutions.
```

<!-- pyml disable-next-line MD024 -->
### Human

```text
Thailand and Vietnam manufacturing facilities. It's our new organic snack line.
Launch date is March 15th, currently 3 weeks away. Delays are in raw material
sourcing - organic grains and packaging materials. We're about 2 weeks behind
schedule. Target production is 500,000 units for initial launch inventory.
```

<!-- pyml disable-next-line MD024 -->
### AI (chief_operating_officer)

```text
Here's the compiled response addressing the delays in raw material sourcing for organic grains and packaging materials for the Thailand and Vietnam manufacturing facilities:

### Root Cause Analysis
1. **Supplier Issues:**
   - Capacity constraints and operational challenges at the supplier's end.
   - Supply chain disruptions due to geopolitical factors or natural disasters.
   - Increased demand from other sectors.

2. **Logistics Delays:**
   - Transportation bottlenecks affecting delivery.
   - Port congestion or customs clearance delays.
   - Inefficiencies in transportation routes.

3. **Demand Forecasting:**
   - Underestimation of raw material needs.
   - Inaccurate demand forecasting tools and methods.

4. **Quality Compliance:**
   - Delays due to quality rejections or compliance with organic standards.

5. **Internal Coordination:**
   - Miscommunication or gaps in coordination between procurement, logistics, and production teams.

### Mitigation Plan
1. **Supplier Management:**
   - Engage with suppliers for expedited shipments and alternative sources.
   - Set up contingency agreements with secondary suppliers.

2. **Logistics Optimization:**
   - Prioritize shipments with logistics partners and explore express shipping options.
   - Coordinate with customs brokers to expedite clearances.

3. **Inventory Management:**
   - Re-evaluate safety stock levels and adjust reorder points.
   - Implement a just-in-time inventory strategy.

4. **Cross-functional Teams:**
   - Establish a task force comprising procurement, logistics, and production teams.
   - Use project management tools for tracking.

5. **Communication Plan:**
   - Keep stakeholders informed about status and schedule changes.
   - Prepare a contingency communication strategy.

By addressing these areas, the goal is to align the production schedule with the March 15th launch date, ensuring timely delivery of the initial 500,000 units. Implementing these strategies should help mitigate current delays and ensure successful launch execution. If you need further assistance or specific action steps, please let me know!
```

---

## Architecture Overview

### Frontman Agent: **chief_operating_officer**

- Serves as the executive leader overseeing all global operations.
- Sets strategic goals and ensures cross-functional alignment.
- Manages company-wide objectives across product development, supply chain, marketing, and regional operations.
- Acts as single point of interaction for enterprise-level inquiries and decision-making.

---

### Primary Agents (Vice Presidents reporting to COO)

1. **vp_supply_chain** - Vice President of Supply Chain
   - Manages the entire global supply chain from sourcing to delivery.
   - Optimizes costs and ensures timely delivery of materials and products.
   - Delegates to:
     - `procurement_manager` - Oversees raw material sourcing and supplier relationships
     - `manufacturing_manager` - Manages production workflows and quality control
     - `logistics_manager` - Handles transportation and warehousing operations

2. **vp_product_development** - Vice President of Product Development
   - Oversees product research, testing, and design across all product lines.
   - Ensures alignment with consumer preferences within budget and time constraints.
   - Delegates to:
     - `product_research_manager` - Conducts consumer research and identifies market trends
     - `product_design_manager` - Oversees product formulation and design
     - `quality_assurance_manager` - Ensures products meet safety and regulatory standards

3. **vp_sales_marketing** - Vice President of Sales and Marketing
   - Manages global sales and marketing strategies.
   - Develops brand positioning and marketing campaigns to drive revenue.
   - Delegates to:
     - `brand_manager` - Manages brand strategy and consumer engagement campaigns
     - `digital_marketing_manager` - Oversees digital channels and e-commerce strategies
     - `sales_director` - Leads sales operations and market expansion strategies

4. **regional_operations_director** - Regional Operations Director
   - Oversees operations within specific global regions.
   - Ensures local execution of global strategies with regional customization.
   - Manages regional compliance and market adaptation.
   - Delegates to:
     - `regional_supply_chain_manager` - Coordinates regional logistics and production
     - `regional_sales_manager` - Leads regional sales teams and adapts tactics
     - `regional_marketing_manager` - Implements localized marketing strategies

---

## Organizational Hierarchy

### Supply Chain Division

```text
chief_operating_officer
  └─ vp_supply_chain
       ├─ procurement_manager
       ├─ manufacturing_manager
       └─ logistics_manager
```

### Product Development Division

```text
chief_operating_officer
  └─ vp_product_development
       ├─ product_research_manager
       ├─ product_design_manager
       └─ quality_assurance_manager
```

### Sales & Marketing Division

```text
chief_operating_officer
  └─ vp_sales_marketing
       ├─ brand_manager
       ├─ digital_marketing_manager
       └─ sales_director
```

### Regional Operations Division

```text
chief_operating_officer
  └─ regional_operations_director
       ├─ regional_supply_chain_manager
       ├─ regional_sales_manager
       └─ regional_marketing_manager
```

---

## Use Cases

This agent network is designed for enterprise operations scenarios including:

- **Supply Chain Optimization**: Identifying bottlenecks, optimizing procurement, and improving logistics efficiency
- **Product Launch Planning**: Coordinating cross-functional teams for new product introductions
- **Regional Market Strategy**: Adapting global strategies to local market conditions
- **Crisis Management**: Responding to supply disruptions, quality issues, or market changes
- **Strategic Planning**: Evaluating expansion opportunities, capacity planning, and resource allocation
- **Performance Analysis**: Assessing operational metrics across functions and regions

---

## External Dependencies

None - this agent network operates using internal knowledge and organizational structure
simulation. It does not rely on external APIs, databases, or web search services. All
decision-making, coordination, and strategic planning are handled through the internal
agent hierarchy.

---

## Testing

This agent network includes test coverage:

- [cpg_agents_test.hocon](../../../tests/fixtures/industry/cpg_agents_test.hocon) - Tests
  basic supply chain inquiry handling with product launch delay scenario

Run tests using:

```bash
# Run cpg agents test
pytest tests/integration/test_integration_test_hocons.py -k "cpg_agents"
```
