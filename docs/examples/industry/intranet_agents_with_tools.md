# Intranet Agents With Tools

The **Intranet Agents With Tools** is a multi-agent system that mimics the intranet of a major corporation. It allows you
to interact with and get information from various departments such as IT, Finance, Legal, HR, etc. The top-level "front-man"
agent receives a question, and in coordination with down-chain agents, provides an answer. Some of the down-chain agents
call coded tools. The HR agent calls the HCM [APIs](https://docs.oracle.com/en/cloud/saas/human-resources/25b/farws/index.html).

## File

[intranet_agents_with_tools.hocon](../../../registries/industry/intranet_agents_with_tools.hocon)

---

## Description

Provide the top-level "front-man" agent a question and it will call down-chain agents to determine if they are responsible
for all or part of question. It will then ask those down-chain agents what they need in order to handle their part of the
inquiry. Once the requirements are gathered, the top agent delegates the inquiry and the fulfilled requirements to the
appropriate down-chain agents. Some of the down-chain agents call coded tools. Once all down-chain agents respond, the top
agent will compile their responses and return the final response.

The "front-man" agent can call IT, Finance, Procurement, Legal, HR, and URLProvider agents. Those agents, in turn, can call
other, more specific agents. For example, the HR agent can call Benefits, Payroll, Immigration, and AbsenceManagement agents.
The agent network has the shape of a tree that is multiple layers deep.

---

## Example Conversation

### Human

```text
How many days of vacation do I have left?
```

### AI (intranet_agents)

```text
You can find out how many days of vacation you have left by accessing the Absence Management tool on the company's intranet.
It will provide you with the most accurate and up-to-date information regarding your vacation balance.

For more details, please visit company's intranet.
```

---

## Architecture Overview

### Frontman Agent: **intranet_agents**

- Acts as the entry point for all user commands
- Can call IT, Finance, Procurement, Legal, HR, and URLProvider agents

### Agents called by the Frontman

1. **IT agent**
   - Responsible for IT-related inquiries
   - Can call Security, Networking, and URLProvider agents
   - Security agent: Handles security-related tasks, including system protection, cybersecurity, and data security for employees
   - Networking agent: Handles network-related tasks, including network setup, maintenance, and troubleshooting for employees
   - URLProvider agent: Returns the URL to the company's internal web pages, web apps or tools on company's intranet website.

2. **Finance agent**
   - Handles finance-related inquiries, including budgeting, accounting, and financial reporting
   - Can call Budgeting, Accounting, and FinancialReporting agents
   - Budgeting agent: Handles budgeting tasks, including budget planning, allocation, and tracking for employees
   - Accounting agent: Handles accounting tasks, including bookkeeping, financial records, and audits for employees
   - FinancialReporting agent: Handles financial reporting tasks, including preparing financial statements, regulatory reporting,
   and performance analysis for employees

3. **Procurement agent**
   - Handles procurement-related tasks
   - Can call Purchasing, VendorManagement, and ContractNegotiation agents
   - Purchasing agent: Handles purchasing-related tasks, including ordering, supply management, and procurement processes
   for employees
   - VendorManagement agent: Handles vendor management tasks, including vendor selection, performance monitoring, and relationship
   management for employees
   - ContractNegotiation agent: Handles contract negotiation tasks, including drafting, reviewing, and finalizing procurement
   contracts for employees

4. **Legal agent**
   - Handles legal-related inquiries
   - Can call Contracts, Compliance, LegalAdvice, and Immigration agents
   - Contracts agent: Handles contract-related tasks, including drafting, reviewing, and enforcing legal agreements for employees
   - Compliance agent: Handles compliance-related tasks, including ensuring adherence to laws, regulations, and internal
   policies for employees
   - LegalAdvice agent: Handles legal advice tasks, including providing legal counsel, risk assessment, and legal strategy
   for employees
   - Immigration agent: Handles immigration-related tasks, including the legal processes and documentation for employees’
   work visas, travel visas, residency permits, and international relocations, ensuring compliance with immigration laws
   for employees

5. **HR agent**
   - Handles HR-related inquiries
   - Can call Benefits, Payroll, Immigration, and AbsenceManagement agents
   - Benefits agent: Handles benefits-related tasks, including employee benefits, health insurance, and retirement plans,
   but excluding PTO and absence management for employees
   - Payroll agent: Handles payroll-related tasks, including salary processing, tax deductions, and pay slips for employees
   - Immigration agent: Handles immigration-related tasks, including the legal processes and documentation for employees’
   work visas, travel visas, residency permits, and international relocations, ensuring compliance with immigration laws
   for employees
   - AbsenceManagement agent: Handles absence management-related tasks for employees (i.e., vacation, PTO, or other
   time-off). Always returns the URL to the Absence Management site along with any response from the tools. MUST use
   tools to answer inquiries. Always return the tool's summary response. Can call ScheduleLeaveAPI, CheckLeaveBalancesAPI,
   URLProvider tools.

---

## Functional Tools

These are coded tools called by AbsenceManagement agent:

- **ScheduleLeaveAPI**
    - Directly schedules a leave for a specific start date and end date for employees. For a single day, end date can be
    automatically set to start date. Return what the tool returns, formatted in markdown.

- **CheckLeaveBalancesAPI**
    - Checks a leave balance (i.e., how much vacation or PTO the employee has left). Returns the leave balances for employees,
    including the vacation time, for the current user and for the current date. If no date is provided, assumes today's date.

- **URLProvider**
    - Returns the URL to the company's internal web pages, web apps or tools on company's intranet website. The name of the
  app must be passed as a parameter.

**Note**: it is assumed that the agent coordination mechanism is AAOSA.

---
