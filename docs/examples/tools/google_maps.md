# Google Maps Platform Grounding Lite

The **Google Maps** agent network is a task-oriented agentic system designed to help users search for places,
check weather conditions, and calculate routes using Google Maps data. It leverages Google Maps Platform Grounding Lite
MCP server to provide real-time location-based information through natural language queries.

---

## File

[google_maps.hocon](../../../registries/tools/google_maps.hocon)

---

## Description

At the core of the system is the Map Searcher agent, which serves as the primary interface between the user and
Google Maps Platform Grounding Lite MCP server. When a user asks questions like
"Give me a list of coffee shops near Golden Gate Park," "What is the weather like in San Francisco today?" or
"What is the driving distance from Mountain View, CA to San Francisco, CA?"—the agent intelligently routes the request
to the appropriate Google Maps tools to retrieve accurate, real-time information.

The system provides comprehensive location-based services including place search, weather information, and route
calculations with distances.

---

## Prerequisites

This agent network requires the following setup:

### Python Dependencies

```bash
pip install neuro-san>=0.6.24
```

### Environment Variables

```bash
export GOOGLE_API_KEY="your_google_api_key_here"
```

### Google Cloud Configuration

- **Maps Grounding Lite API**: Must be enabled in your Google Cloud project

For more information on setting up Google Maps Platform Grounding Lite, see:

- [Google Maps AI Grounding Lite Documentation](https://developers.google.com/maps/ai/grounding-lite)

### Authentication

Authentication is handled through either:

- **Sly data**: Configuration passed through the agent network
- **MCP_SERVERS_INFO_FILE**: Environment variable pointing to MCP server configuration file

For detailed authentication setup, see:

- [Neuro-SAN Authentication Guide](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/user_guide.md#authentication)

---

## Example Conversations

### Example 1: Place Search

#### Human

```text
Give me a list of coffee shops near Golden Gate Park.
```

#### AI (Map Searcher)

```text
Here are some coffee shops near Golden Gate Park:

1. Blue Danube Coffee House - 306 Clement St
2. Trouble Coffee Company - 4033 Judah St
3. Arizmendi Bakery - 1331 9th Ave
4. The Beanery - 635 Clement St

All of these are within walking distance of the park and highly rated by visitors.
```

### Example 2: Weather Information

#### Human

```text
What is the weather like in San Francisco today?
```

#### AI (Map Searcher)

```text
The current weather in San Francisco is partly cloudy with a temperature of 62°F (17°C).
Winds are light at 8 mph from the west. There's no precipitation expected today.
```

### Example 3: Route Distance

#### Human

```text
What is the driving distance from Mountain View, CA to San Francisco, CA?
```

#### AI (Map Searcher)

```text
The driving distance from Mountain View, CA to San Francisco, CA is approximately 38 miles (61 km).
Under normal traffic conditions, this drive takes about 45-50 minutes via US-101 N.
```

---

## Architecture Overview

### Frontman Agent: map_searcher

- Main entry point for all Google Maps-related queries.
- Interprets natural language requests for places, weather, and routes.
- Delegates requests to the Google Maps Platform Grounding Lite MCP server.
- Processes and formats results for clear presentation to users.

### Tools: Google Maps Platform Grounding Lite MCP Server

The agent connects to the Google Maps Platform Grounding Lite MCP server at `https://mapstools.googleapis.com/mcp`,
which provides access to:

#### Available Capabilities

- **Place Search**: Find businesses, landmarks, and points of interest
  - Search by location, category, or name
  - Get detailed place information
  - Access ratings and reviews

- **Weather Information**: Get current weather conditions
  - Temperature and conditions
  - Wind speed and direction
  - Precipitation forecasts

- **Route Calculation**: Calculate distances and travel times
  - Distances between locations
  - Estimated travel times
  - Does **not** provide step-by-step routing, directions, real-time traffic, or navigation information

---

## Key Features

### Natural Language Interface

- Understands conversational queries
- Flexible query formatting
- Context-aware responses

### Comprehensive Location Services

- Place discovery and search
- Weather conditions
- Distance and route planning
- All integrated in a single agent

### MCP Integration

- Uses Model Context Protocol (MCP) for standardized tool access
- Seamless integration with Google Maps Platform
- Secure authentication and API access

---

## Debugging Hints

When developing or debugging the Google Maps Platform Grounding Lite agent, keep the following in mind:

- **API Key Validation**: Ensure your `GOOGLE_API_KEY` is valid and has the necessary permissions.

- **Maps Grounding Lite API**: Verify that the Maps Grounding Lite API is enabled in your Google Cloud project.

- **Neuro-SAN Version**: Confirm that neuro-san>=0.6.24 is installed.

- **Authentication Setup**: Ensure either sly data or MCP_SERVERS_INFO_FILE is properly configured for MCP server
authentication.

- **MCP Server Connectivity**: Verify that the agent can connect to `https://mapstools.googleapis.com/mcp`.

- **Query Formatting**: Check that location names and addresses are properly formatted for accurate results.

- **API Quotas**: Monitor your Google Maps Platform API usage and quotas.

- **Network Access**: Ensure the system has network access to Google Maps Platform services.

- **Response Parsing**: Verify that responses from the MCP server are being parsed correctly.

- **Tool Registration**: Confirm that the MCP server URL is correctly specified in the tools array.

### Common Issues

- **Authentication Failures**: Verify API key is set and Maps Grounding Lite API is enabled

- **MCP Connection Errors**: Check network connectivity and MCP server URL

- **Missing API Access**: Ensure your Google Cloud project has Maps Grounding Lite enabled

- **Version Compatibility**: Confirm neuro-san>=0.6.24 is installed

- **Invalid Locations**: Verify that location queries are specific enough for accurate results

- **Quota Exceeded**: Monitor API usage limits and adjust queries accordingly

- **Configuration Issues**: Check authentication setup (sly data or MCP_SERVERS_INFO_FILE)

- **Network Timeouts**: Ensure stable network connection for API calls

- **Permission Errors**: Verify that the API key has appropriate permissions for all required services

---

## Resources

- [Google Maps AI Grounding Lite Documentation](https://developers.google.com/maps/ai/grounding-lite)  
  Complete guide to Google Maps Platform Grounding Lite and its capabilities.

- [Neuro-SAN Authentication Guide](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/user_guide.md#authentication)  
  Detailed instructions for setting up authentication with MCP servers.

- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)  
  Learn about the Model Context Protocol standard used for tool integration.

- [Google Cloud Console](https://console.cloud.google.com/)  
  Manage your Google Cloud project and enable required APIs.

- [Agent HOCON Reference](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md)  
  Schema specifications for agent configuration files.
