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
To address the intermittent connectivity issues at your downtown office, both the Network Operations Center Specialist and the Field Technician are involved. Here's how we can proceed to diagnose and fix the problem:

1. Network Operations Center Specialist:
   - Remote Analysis:
     - Check the physical connections and cables for damage or loose connections.
     - Verify the status of the network switches and routers.
     - Review network logs for error messages or patterns.
     - Conduct a network performance assessment to identify potential congestion or bottlenecks.
     - Update network device firmware and drivers if needed.

2. Field Technician:
   - Onsite Inspection:
     - Coordinate with a network engineer for diagnosing network issues.
     - Access and inspect network equipment at your premises.

Steps to Resolve:
- Assign to Network Support Team: Involve the network support team for diagnosis and resolution.
- Initial Diagnosis:
  - Check for known outages or issues in your area.
  - Review service logs for relevant events or errors.
- Physical Inspection:
  - Inspect cabling and connections for wear or damage.
  - Examine network devices for errors or unusual behavior.
- Configuration Review:
  - Verify network settings and IP/DNS configurations.
- Testing and Monitoring:
  - Conduct connectivity tests and monitor network performance.

If you'd like us to coordinate efforts between the Network Operations Center Specialist and the Field Technician to comprehensively address the issue, please let us know.

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

## Testing

This agent network includes test coverage:

[telco_network_support_test.hocon](../../../tests/fixtures/industry/telco_network_support_test.hocon) - Tests basic network support inquiry handling with network outage scenario

Run tests using:
```bash
# Run telco network support test
pytest tests/integration/test_integration_test_hocons.py -k "telco_network_support"
```

---