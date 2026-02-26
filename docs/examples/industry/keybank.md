# KeyBank Financial Services Assistant

The **KeyBank Financial Services Assistant** is a hierarchically organized
multi-agent system that simulates KeyBank's financial services operations.
It covers consumer banking, commercial lending, wealth management, investment
advisory, estate and retirement planning, and risk management including fraud
prevention and compliance. Specialized agents coordinate through the AAOSA
pattern to deliver personalized, context-aware financial guidance.

The system currently operates in demo mode and can be grounded in real data and
systems as needed.

---

## File

[keybank.hocon](../../../registries/industry/keybank.hocon)

---

## Description

This network organizes its intelligence into nested layers, with specialized
agents collaborating to resolve client inquiries across banking and financial
service domains. A central Client Relationship Manager (top-level "front-man"
agent) receives and parses incoming questions, dispatches relevant portions to
subject matter agents, and collates the final output for the end user while
maintaining clarity and helpfulness.

- **Domain Expertise Delegation**: Each agent is domain-specific and may
  offload subtasks to its own subordinate agents, mirroring how departments
  operate in an actual bank.
- **Human-like Dialogue Management**: The front-man agent ensures a smooth,
  conversational experience by abstracting the underlying agent collaboration
  from the user.
- **Interactive Follow-ups**: Agents may request additional user input before
  responding, using clearly formatted, human-friendly prompts.
- **Expandable Structure**: Adding new banking functions (e.g., tax advisory,
  digital banking) is as simple as plugging in new agents and updating tool
  references.

---

## Example Conversations

### Example 1

#### Human

```text
What mortgage options are available for a first-time home buyer?
```

#### AI (client_relationship_manager)

```text
As a first-time home buyer, KeyBank offers a variety of mortgage options to fit
your needs. Here are some options available:

1. **Fixed-Rate Mortgages**: These feature a consistent interest rate and
predictable monthly payments, making budgeting easier. Ideal if you plan to
stay in your home long-term.

2. **Adjustable-Rate Mortgages (ARMs)**: These offer lower initial interest rates
and payments. The rate is fixed for an introductory period, then adjusts
periodically. This may be suitable if you plan to move or refinance within a few
years.

3. **FHA Loans**: Backed by the Federal Housing Administration, these loans
typically have lower down payment requirements and more flexible credit
requirements, making them ideal for those with limited funds for a down payment
or less-than-perfect credit.

4. **VA Loans**: Available for veterans and active military members, these
government-backed loans offer competitive interest rates with no down payment
required.

5. **First-Time Home Buyer Programs**: KeyBank may also offer specific programs
designed to assist first-time home buyers with benefits like lower down payments
or closing cost assistance.

It's important to consider your financial situation, including your credit score,
income, and how long you plan to stay in the home, to choose the best mortgage
product for you. For personalized advice, you may want to consult one of KeyBank's
mortgage advisors who can guide you through the options and application process.
```

### Example 2

#### Human

```text
Can you help me build a retirement savings plan?
```

#### AI (client_relationship_manager)

```text
To build a retirement savings plan, you should start by setting realistic retirement
goals based on your future lifestyle needs. Consider factors such as your current age,
expected retirement age, and life expectancy to determine your time horizon. Evaluate
your existing savings, and then choose appropriate retirement vehicles like IRAs or
401(k)s to fund your plan.

Explore various investment options within these accounts, such as stocks, bonds, and
mutual funds, tailored to your risk tolerance and time horizon. Additionally, be mindful
of the tax benefits associated with different savings plans and form a withdrawal
strategy for retirement. Regularly review your plan to ensure it aligns with your goals
as circumstances change. 

For a personalized approach, consulting with a wealth management advisor can be beneficial
in crafting a plan that suits your specific needs and preferences.
```

---

## Architecture Overview

### Frontman Agent: `client_relationship_manager`

- Serves as the primary point of contact for all client inquiries at KeyBank.
- Understands client needs, provides personalized solutions, and ensures a
  seamless banking experience.
- Determines which specialized sub-agents to engage based on the inquiry.
- Coordinates and compiles responses from down-chain agents for a final resolution.

---

### Primary Domains (Tools called by the Frontman)

#### consumer_banking_specialist

- Handles individual client services including checking and savings accounts,
  personal loans, mortgages, credit cards, and financial wellness services.
- Delegates to:
    - `mortgage_advisor` - Provides mortgage options, refinancing, and home equity
      lines of credit
        - `underwriting_specialist` - Reviews and assesses mortgage applications
          against lending criteria
    - `personal_loan_officer` - Supports clients seeking personal loans with terms,
      eligibility, and repayment options
    - `credit_card_specialist` - Assists with choosing and managing credit card
      products, rewards, and dispute resolution

#### commercial_banking_specialist

- Manages financial services for business clients including loans, lines of credit,
  cash management, equipment financing, and commercial real estate services.
- Delegates to:
    - `business_loan_officer` - Assists businesses with securing loans and lines
      of credit
        - `loan_underwriter` - Analyzes financial documents and assesses risks for
          business loan applications
    - `cash_management_specialist` - Provides cash flow management solutions
      including payment processing and liquidity management
    - `equipment_financing_consultant` - Helps businesses secure financing for
      purchasing or leasing equipment

#### wealth_management_advisor

- Offers wealth management services including investment advisory, trust and estate
  planning, and retirement planning for high-net-worth clients.
- Delegates to:
    - `investment_decisioning_agent` - Analyzes client profiles, market data, and
      risk factors to recommend optimized investment strategies
        - `investment_portfolio_manager` - Manages investment portfolios, balancing
          risk and return to meet financial goals
    - `estate_planning_specialist` - Advises on estate planning strategies including
      wills, trusts, and tax implications
    - `retirement_plan_consultant` - Assists with retirement plans including IRAs,
      401(k)s, and other retirement vehicles

#### risk_management_officer

- Provides risk management advice covering insurance, fraud prevention, and financial
  security for both individual and business clients.
- Delegates to:
    - `fraud_prevention_specialist` - Monitors transactions for signs of fraud and
      provides guidance on protecting financial information
    - `insurance_advisor` - Offers life, health, and property insurance products
      tailored to client needs
    - `compliance_officer` - Ensures KeyBank's operations adhere to legal regulations
      and internal policies

---

## Debugging Hints

Check the logs for:

- Correct routing of inquiries to appropriate domain-specific agents.
- Verify that sub-agents requested all necessary input parameters before producing a
  response.

---
