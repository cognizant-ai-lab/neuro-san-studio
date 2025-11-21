# Intranet Agents

The **Intranet Agents** is a multi-agent system that mimics the intranet of a major corporation. It allows you to interact
with and get information from various departments such as IT, Finance, Legal, HR, etc. The top-level "front-man" agent
receives a question, and in coordination with down-chain agents, provides an answer.

## File

[intranet_agents.hocon](../../../registries/industry/intranet_agents.hocon)

---

## Description

Provide the top-level "front-man" agent a question and it will call down-chain agents to determine if they are responsible
for all or part of question. It will then ask those down-chain agents what they need in order to handle their part of the
inquiry. Once the requirements are gathered, the top agent delegates the inquiry and the fulfilled requirements to the
appropriate down-chain agents. Once all down-chain agents respond, the top agent will compile their responses and return
the final response.

The "front-man" agent can call IT, Finance, Procurement, Legal, and HR agents. Those agents, in turn, can call other,
more specific agents. For example, the HR agent can call Benefits or Payroll agents. The agent network has the shape of
a tree that is two layers deep.

---

## Example Conversation

### Human

```text
I recently got married
```

### AI (intranet_agents)

```markdown
Congratulations on your recent marriage! Here are some ways I can assist you across different areas:

IT and Security:

If you have specific concerns related to digital security, data privacy, or shared digital accounts with your spouse, please
let me know so I can provide guidance.

Finance:

Budgeting and Financial Planning: I can help create a budget plan and offer financial advice. Please share details such
as your current income, expenses, financial goals, and any debts or investments.
Tax Implications: Marriage can affect your tax status. Updating tax forms like the W-4 might be necessary.

Procurement:

If there are specific procurement or contract-related questions, such as name changes on contracts or vendor management,
please provide more context.

Legal:

I can assist with legal considerations like name changes, marriage certificates, and estate planning. Please specify any
particular legal concerns or areas where you need assistance.

HR and Benefits:

Employee Benefits: If you need to update benefits like health insurance or retirement plans, or if you're interested in
adding your spouse to your coverage, I can guide you through the process.
Please let me know which specific areas or questions you would like to explore further, and I will be happy to provide
more detailed assistance!
```

---

## Architecture Overview

### Frontman Agent: **intranet_agents**

- Acts as the entry point for all user commands
- Can call IT, Finance, Procurement, Legal, and HR agents

### Agents called by the Frontman

1. **IT_agent**
   - Responsible for IT-related inquiries
   - Can call Security_agent and Networking_agent
   - Security_agent: Handles security-related tasks, including system protection, cybersecurity, and data security
   - Networking_agent: Handles network-related tasks, including network setup, maintenance, and troubleshooting

2. **Finance_agent**
   - Handles finance-related inquiries, including budgeting, accounting, and financial reporting
   - Can call Budgeting_agent, Accounting_agent, and Financial_reporting_agent
   - Budgeting_agent: Handles budgeting tasks, including budget planning, allocation, and tracking
   - Accounting_agent: Handles accounting tasks, including bookkeeping, financial records, and audits
   - Financial_reporting_agent:Handles financial reporting tasks, including preparing financial statements, regulatory
   reporting, and performance analysis

3. **Procurement_agent**
   - Handles procurement-related tasks
   - Can call Purchasing_agent, Vendor_management_agent, and Contract_negotiation_agent
   - Purchasing_agent: Handles purchasing-related tasks, including ordering, supply management, and procurement processes
   - Vendor_management_agent: Handles vendor management tasks, including vendor selection, performance monitoring, and
   relationship management
   - Contract_negotiation_agent: Handles contract negotiation tasks, including drafting, reviewing, and finalizing
   procurement contracts

4. **Legal_agent**
   - Handles legal-related inquiries
   - Can call Contracts_agent, Compliance_agent, and Legal_advice_agent
   - Contracts_agent: Handles contract-related tasks, including drafting, reviewing, and enforcing legal agreements
   - Compliance_agent: Handles compliance-related tasks, including ensuring adherence to laws, regulations, and internal
   policies
   - Legal_advice_agent: Handles legal advice tasks, including providing legal counsel, risk assessment, and legal strategy

5. **HR_agent**
   - Handles HR-related inquiries
   - Can call Benefits_agent, and Payroll_agent
   - Benefits_agent: Handles benefits-related tasks, including employee benefits, health insurance, and retirement plans
   - Payroll_agent: Handles payroll-related tasks, including salary processing, tax deductions, and pay slips

**Note**: it is assumed that the agent coordination mechanism is AAOSA.

---
