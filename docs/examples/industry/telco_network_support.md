# Telecom Network Support

The **Telecom Network Support** agent network is a comprehensive service delivery system designed to handle customer inquiries, network operations, and project management for ethernet and optical network services across multiple locations. The system coordinates technical support, installation, monitoring, and business relationship management through specialized agents.

---

## File

[telco_network_support.hocon](../../../registries/industry/telco_network_support.hocon)

---

## Description

This hierarchical multi-agent network coordinates telecom network services through specialized agents handling customer support, technical operations, field services, and account management. The system operates from a telecom service provider's perspective, focusing on delivering reliable network infrastructure, responsive support, and seamless service delivery.

**Key Capabilities:**
- **Customer Support**: Single point of contact for all network service inquiries and issue resolution.
- **Network Operations**: 24/7 monitoring, troubleshooting, and maintenance of network infrastructure.
- **Field Services**: Onsite installation, maintenance, and repair of network equipment.
- **Project Management**: Coordination of complex multi-location network deployments and upgrades.
- **Account Management**: Business relationship oversight and ongoing customer satisfaction.
- **Technical Architecture**: Design and implementation of large-scale network solutions.

---

## Example Conversation

### Human

```text
We're experiencing intermittent connectivity issues at our downtown office. Our ethernet connection keeps dropping every few hours. Can you help diagnose and fix this?
```

### AI (customer_support_rep)

```text
I'm sorry to hear you're experiencing connectivity issues at your downtown office. I'll help you get this resolved as quickly as possible. Let me gather some information to diagnose the problem:

1. When did the connectivity issues start? (specific date/time if possible)
2. How long do the connection drops typically last?
3. What is your office location/address?
4. Does the issue affect all workstations or specific devices?
5. Have there been any recent changes to your network setup or equipment?
6. What type of service plan do you have with us? (bandwidth tier)

Once I have this information, I'll coordinate with our Network Operations Center to analyze your connection logs and dispatch a field technician if needed.
```

### Human

```text
Started yesterday around 2 PM. Drops last about 5-10 minutes. Address is 123 Main Street, Suite 500. Affects all 25 workstations. No recent changes. We have the 1 Gbps ethernet plan.
```

### AI (customer_support_rep)

```text
Thank you for the detailed information. I've initiated a diagnostic investigation for your location at 123 Main Street, Suite 500. Here's what we're doing:

**Immediate Actions Taken:**

1. **Network Monitoring Analysis** (In Progress)
   - Our Network Operations Center is reviewing your connection logs from the past 48 hours
   - Analyzing traffic patterns and error rates on your circuit
   - Checking for equipment alerts or performance degradation signals

2. **Initial Findings**
   - NOC has identified intermittent packet loss starting at 2:15 PM yesterday
   - Pattern suggests potential issue with optical transceiver or fiber connection
   - No outages reported in your area, issue appears isolated to your circuit

3. **Recommended Next Steps**

   **Option A: Remote Troubleshooting (Fastest)**
   - NOC specialist can perform remote diagnostics on your customer premises equipment (CPE)
   - Test optical signal levels and circuit performance
   - Timeline: 30-45 minutes
   - May resolve issue if it's configuration-related

   **Option B: Onsite Field Service**
   - Schedule field technician to inspect physical connections and equipment
   - Replace optical transceiver or patch cables if faulty
   - Timeline: Technician available today between 4-6 PM or tomorrow 8-10 AM
   - Recommended if remote diagnostics don't resolve the issue

**My Recommendation**: Start with Option A (remote troubleshooting) right now. If we can't resolve it remotely, I'll immediately schedule the field technician for today's 4-6 PM window to minimize your downtime.

Would you like me to proceed with the remote diagnostics now?
```

### Human

```text
Yes, let's start with remote diagnostics now.
```

### AI (customer_support_rep)

```text
Perfect! I'm connecting you with our Network Operations Center specialist who will perform the remote diagnostics. They'll be working on your circuit for the next 30-45 minutes.

**What to Expect:**
- NOC specialist will monitor your connection in real-time
- You may experience brief (1-2 minute) service interruptions during testing
- They'll test optical signal strength, circuit configuration, and equipment status

I'll stay assigned to your case and follow up with you once diagnostics are complete. You should receive:
1. Real-time updates if any issues are found
2. A full diagnostic report within the next hour
3. Immediate notification if field service dispatch is needed

**Case Number**: NET-20251228-0547

I'll contact you via this channel as soon as we have results. Is there a backup phone number where we can reach you if needed?
```

---

## Architecture Overview

### Frontman Agent: **customer_support_rep**

- Serves as the single point of interaction for all customer network service inquiries.
- Handles initial triage and coordinates with appropriate technical and business teams.
- Provides clear communication and manages customer expectations throughout service delivery.
- Acts as the main escalation point for complex issues requiring cross-functional coordination.

---

### Primary Agents (Tools called by the Frontman)

1. **service_delivery_coordinator**
   - Manages and tracks the overall process of fulfilling orders and resolving network service issues.
   - Ensures customer requests are assigned to the right departments with proper follow-up.
   - Coordinates order progress tracking and status communication.

2. **network_engineer**
   - Handles technical aspects of configuring and troubleshooting ethernet and optical networks.
   - Configures and maintains network infrastructure across multiple locations.
   - Provides technical support for complex network issues.
   - Delegates to:
     - `network_ops_center_specialist` - Monitors network health and responds to alerts remotely
       - Sub-delegates to: `noc_manager` - Oversees NOC team performance and escalations
         - Sub-delegates to: `senior_management` - Provides strategic oversight
     - `field_technician` - Performs onsite installation, maintenance, and troubleshooting
       - Sub-delegates to: `logistics_coordinator` - Manages equipment shipment and delivery

3. **account_manager**
   - Manages business relationships with customers post-sale.
   - Ensures ongoing customer satisfaction and addresses business needs.
   - Acts as main point of contact for clients regarding service performance.
   - Delegates to:
     - `sales_engineer` - Engages in pre-sales technical discussions and solution design
     - `project_manager` - Oversees complex multi-location network projects
       - Sub-delegates to: `senior_network_architect`, `logistics_coordinator`
     - `service_delivery_coordinator` - (Shared) Coordinates service fulfillment

---

## Agent Hierarchy Breakdown

### Network Operations Path
```
customer_support_rep
  └─ network_engineer
       ├─ network_ops_center_specialist
       │    └─ noc_manager
       │         └─ senior_management
       └─ field_technician
            └─ logistics_coordinator
```

### Account Management Path
```
customer_support_rep
  └─ account_manager
       ├─ sales_engineer
       ├─ project_manager
       │    ├─ senior_network_architect
       │    └─ logistics_coordinator
       └─ service_delivery_coordinator
```

---

## External Dependencies

**None**

This agent network operates using internal knowledge and does not rely on external APIs or web search services. All network diagnostics, project coordination, and customer service operations are handled through the internal agent hierarchy and simulated technical knowledge.

---