# Telco Network Orchestration

This agent network simulates a large-scale telecommunication network orchestration system, including monitoring, fault detection and resource allocation, for a telco company in Australia.

## File

[telco_network_orchestration.hocon](../../../registries/industry/telco_network_orchestration.hocon)

## Description

This agent network simulates the network operations of a large telecommunications company in Australia. It's organized into regions (NSW: New South Wales, VIC: Victoria, QLD: Queensland), each with a site manager and a set of nodes. The agents are NOT grounded and will simulate access to the network's systems instead.

## Example conversation #1

### Human:

What severe incidents occurred in the last 24 hours, and how were they mitigated?

### AI

In the last 24 hours, several severe incidents occurred across the company network in different regions, and they were mitigated as follows:

#### NSW Region:
1. **High CPU Load:**
   - **Details:** CPU load surged to 95% due to a spike in data processing requests.
   - **Mitigation:** Load balancing and resource optimization were implemented, resolving the issue within 1 hour.

2. **Increased Packet Loss:**
   - **Details:** Caused by faulty hardware in one of the routers.
   - **Mitigation:** Bypassed faulty hardware, corrected the configuration, and dispatched a maintenance team for hardware replacement. Packet loss was reduced to acceptable levels within 2 hours.

3. **Traffic Latency and Packet Loss in Sydney CBD:**
   - **Details:** Due to a surge in data traffic.
   - **Mitigation:** Bandwidth reallocation, traffic rerouting, and prioritization of critical traffic were applied to return to normal levels promptly.

#### VIC Region:
1. **High CPU Load on Node VIC-23:**
   - **Details:** Unexpected surge in data processing requests.
   - **Mitigation:** Load balancing reduced CPU load to stable levels within an hour.

2. **Increased Latency on VIC-North Segment:**
   - **Details:** Faulty router causing increased latency.
   - **Mitigation:** Router replacement restored normal latency within 3 hours.

3. **Increased Packet Loss and Traffic Latency:**
   - **Details:** Due to a large-scale online event.
   - **Mitigation:** Traffic rerouting and temporary bandwidth increase stabilized the network within two hours.

4. **Traffic Latency in Melbourne Network Node:**
   - **Details:** High demand during peak hours.
   - **Mitigation:** Traffic was dynamically rerouted, and additional bandwidth was allocated to critical services.

#### QLD Region:
1. **High CPU Load in Brisbane Node:**
   - **Details:** Increased traffic from a local event.
   - **Mitigation:** Rerouted traffic and allocated additional resources.

2. **Increased Latency in Gold Coast Node:**
   - **Details:** Configuration error during update.
   - **Mitigation:** Corrected the error and restored normal latency.

3. **Significant Increase in Traffic Latency in QLD:**
   - **Details:** Surge in data usage during peak hours.
   - **Mitigation:** Rerouted traffic and increased temporary bandwidth.

4. **Packet Loss in South Brisbane Node:**
   - **Details:** Hardware failure in a router.
   - **Mitigation:** Replaced faulty hardware and rerouted traffic.

These incidents were promptly addressed, ensuring minimal impact on network performance and maintaining stability and reliability across all affected regions.

## Example conversation #2

### Human:

We have a major event in Sydney this weekend. Can we reconfigure the network accordingly?

### AI

Reconfiguring the network for the major event in Sydney this weekend is indeed feasible. Here's what we need to proceed:

#### Requirements:
1. **Event Details:**
   - Location
   - Expected attendee count
   - Duration of the event
   - Specific network requirements

2. **Network Adjustments:**
   - Approval from Site Manager
   - Current network load data
   - Expected traffic increase

Both the NSW Network Node Assistant and NSW Network Node Monitor will work together to ensure optimal network performance during the event. Please provide the necessary details to proceed with the reconfiguration.
