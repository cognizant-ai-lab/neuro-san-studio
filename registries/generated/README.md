# Website Traffic Analysis Agent Network

## Overview

The **Website Traffic Analysis** agent network is a sophisticated multi-agent system designed to process, analyze, and generate strategic insights from website traffic data. It orchestrates seven specialized agents that work collaboratively to transform raw analytics data into executive-level reports with actionable business recommendations.

### What It Does

This agent network automates the complete analytics workflow:

1. **Data Ingestion**: Processes raw traffic datasets (Google Analytics 4, Matomo, etc.)
2. **Data Normalization**: Cleans, standardizes, and aggregates traffic metrics
3. **Behavioral Analysis**: Identifies user navigation patterns and engagement trends
4. **Page Performance**: Ranks pages by popularity and engagement metrics
5. **Executive Synthesis**: Generates comprehensive reports with strategic recommendations
6. **Strategic Guidance**: Provides actionable advice to optimize website performance

### Key Agents

- **traffic_analyst**: Extracts foundational traffic metrics (visitors, duration, bounce rates)
- **data_processor**: Normalizes and aggregates data for consistency
- **user_behavior_analyst**: Maps user journeys and identifies drop-off points
- **page_ranking_engine**: Ranks pages by performance and engagement
- **insight_generator**: Synthesizes insights from all analysis agents
- **strategic_advisor**: Translates insights into business recommendations
- **report_compiler**: Formats final executive-friendly reports

For detailed architecture documentation, see [architecture.md](architecture.md).

## Setup Instructions

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- API key for your chosen LLM provider (OpenAI, Anthropic, Google Gemini, etc.)

### Installation

#### Option 1: Fresh Installation (Recommended)

1. **Install Neuro SAN Studio** from PyPI:
   ```bash
   pip install neuro-san-studio
   ```

2. **Scaffold a starter project**:
   ```bash
   ns init
   ```
   Follow the prompts to select your LLM provider(s).

3. **Import the Website Traffic Analysis network**:
   ```bash
   ns import website_traffic_analysis
   ```
   Or import it from this file directly:
   ```bash
   ns import registries/generated/website_traffic_analysis.hocon
   ```

#### Option 2: From Repository

If you're working with the Lakshmi_aihackthon repository:

1. **Clone the repository** (if not already done):
   ```bash
   git clone https://github.com/cognizant-ai-lab/neuro-san-studio.git
   cd neuro-san-studio
   ```

2. **Install development dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up your LLM configuration**:
   ```bash
   cp config/llm_config.hocon.template config/llm_config.hocon
   # Edit config/llm_config.hocon with your LLM provider details
   ```

### Configuration

1. **Set your LLM API key** as an environment variable:
   ```bash
   # For OpenAI (default)
   export OPENAI_API_KEY="your-api-key-here"
   
   # For Anthropic
   export ANTHROPIC_API_KEY="your-api-key-here"
   
   # For Google Gemini
   export GOOGLE_API_KEY="your-api-key-here"
   ```

   Alternatively, create a `.env` file in the project directory:
   ```
   OPENAI_API_KEY=your-api-key-here
   ```

2. **Verify LLM configuration**:
   ```bash
   ns check-llm-keys
   ns check-config --hocon-path config/llm_config.hocon
   ```

3. **Update LLM model** (optional):
   Edit `config/llm_config.hocon` to change the model:
   ```hocon
   openai {
     model = "gpt-4o"  # or another model of your choice
   }
   ```

## Running the Agent Network

### Method 1: Web UI (Recommended)

Start the Neuro SAN server and nsflow UI:

```bash
ns run
```

The server listens on `localhost:8080` and the UI is served at [http://localhost:4173/](http://localhost:4173/).

Then:
1. Open the UI in your browser
2. Navigate to the agent networks section
3. Select "website_traffic_analysis"
4. Enter one of the sample queries (see below)
5. Monitor agent execution and review results

Logs are stored in:
- `logs/server.log` - Server logs
- `logs/nsflow.log` - UI logs
- `logs/thinking_dir/` - Agent thinking and reasoning

### Method 2: Command-Line Chat

Query the agent directly without the server:

```bash
ns chat website_traffic_analysis
```

Then type your query at the prompt. Example:
```
Analyze the latest website traffic data and provide key metrics like total visitors, session duration, and bounce rate.
```

For one-shot queries:
```bash
ns chat website_traffic_analysis --one-shot "Analyze the latest website traffic data and provide key metrics like total visitors, session duration, and bounce rate."
```

### Method 3: Python API

Programmatically interact with the agent network:

```python
from neuro_san_studio.runner import AgentNetworkRunner

runner = AgentNetworkRunner("website_traffic_analysis")
result = runner.query("Analyze the latest website traffic data and provide key metrics.")
print(result)
```

## Sample Queries

Try these queries to explore the agent network's capabilities:

### 1. Traffic Metrics Analysis
```
Analyze the latest website traffic data and provide key metrics like total visitors, 
session duration, and bounce rate.
```
**Expected Output**: Foundational traffic metrics and key statistics

### 2. Page Performance Report
```
Generate a report on the most visited pages, including their entry rates, exit rates, 
and average time spent.
```
**Expected Output**: Ranked page metrics with performance indicators

### 3. User Journey Analysis
```
Identify common user navigation paths and drop-off points from the processed traffic data.
```
**Expected Output**: User behavior patterns and engagement insights

### 4. Strategic Recommendations
```
What are the top three strategic recommendations to improve user engagement based on 
the latest traffic analysis?
```
**Expected Output**: Actionable business recommendations with priorities

## Agent Execution Flow

When you submit a query, the agents execute in the following order:

```
User Query
    ↓
insight_generator (coordinates execution)
    ├→ traffic_analyst (extracts raw metrics)
    │   └→ data_processor (normalizes data)
    │       ├→ user_behavior_analyst (analyzes behavior)
    │       └→ page_ranking_engine (ranks pages)
    ├→ strategic_advisor (evaluates recommendations)
    │   └→ report_compiler (formats final output)
    ↓
Executive Report
```

## Demo Mode

The agent network includes a **demo mode** setting that generates realistic synthetic responses without requiring live analytics data. This is useful for:

- Testing agent interactions
- Demonstrating capabilities
- Prototyping workflows

To enable demo mode, ensure the `demo_mode` setting is active in the configuration.

## Customization

### Extending the Network

To add additional analysis agents:

1. Define the new agent in the HOCON configuration
2. Add it to the `insight_generator`'s tool list
3. Update the instructions and tool dependencies as needed

Example:
```hocon
{
    "name": "custom_analyzer",
    "function": ${aaosa_call}{
        "description": "Analyzes custom metrics"
    },
    "instructions": "Your custom instructions here",
}
```

### Modifying Instructions

Edit the agent instructions in `website_traffic_analysis.hocon` to adjust behavior:

```hocon
"instructions": """
Your custom instructions here.
Focus on specific aspects you need emphasized.
"""
```

## Troubleshooting

### Issue: "File not found" error for registries/aaosa.hocon

**Solution**: Ensure you're running from the repository root:
```bash
cd /path/to/neuro-san-studio
python -m neuro_san_studio run
```

### Issue: LLM API key not recognized

**Solution**: 
1. Verify environment variable is set: `echo $OPENAI_API_KEY`
2. Check `.env` file exists in project root
3. Run configuration check: `ns check-llm-keys --tier 3`

### Issue: Agents timeout or fail to respond

**Solution**:
1. Check logs: `tail -f logs/server.log`
2. Verify network connectivity
3. Check LLM provider status
4. Increase timeout in configuration if needed

### Issue: Partial or incomplete results

**Solution**:
1. Run simpler queries first
2. Check agent logs in `logs/thinking_dir/`
3. Verify all upstream agents executed successfully
4. Try a different LLM provider

## Integration Options

### Integrate with External Systems

The agent network can be extended to integrate with:

- **Google Analytics API**: Fetch real traffic data programmatically
- **Matomo API**: Connect to self-hosted analytics
- **Slack**: Send reports to Slack channels
- **Databases**: Store analysis results in SQL/NoSQL databases
- **Custom APIs**: Add coded tools for specialized integrations

### Adding Coded Tools

Extend functionality by adding Python-based coded tools:

```python
# coded_tools/traffic_integrations.py
from neuro_san_studio.tools import CodedTool

class GoogleAnalyticsConnector(CodedTool):
    """Fetches data from Google Analytics"""
    
    def execute(self, property_id: str, date_range: str):
        # Implementation here
        pass
```

## Performance Notes

- **Data Size**: Network handles datasets with millions of records
- **Execution Time**: Typical analysis completes in 30-60 seconds
- **Parallel Agents**: Multiple analysis agents run concurrently for efficiency
- **Report Generation**: Final reports compile in under 10 seconds

## Support & Documentation

- **Full Documentation**: [Neuro SAN Studio Docs](https://github.com/cognizant-ai-lab/neuro-san-studio/tree/main/docs)
- **Architecture Details**: See [architecture.md](architecture.md) in this directory
- **CLI Reference**: `ns --help` or `ns <command> --help`
- **Community**: GitHub Issues and Discussions

## License

This agent network is part of **Neuro SAN Studio**, distributed under the **Apache 2.0 License**.

## Related Resources

- [Neuro SAN Framework](https://github.com/cognizant-ai-lab/neuro-san)
- [Neuro SAN Studio Repository](https://github.com/cognizant-ai-lab/neuro-san-studio)
- [Agent Network Architecture Documentation](architecture.md)
- [Project Summary](../../../summary.md)
