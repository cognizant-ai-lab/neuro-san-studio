import importlib
import sys

sys.modules["coded_tools.agent_network_designer"] = importlib.import_module(
    "coded_tools.experimental.agent_network_designer"
)
sys.modules["coded_tools.agent_network_editor"] = importlib.import_module(
    "coded_tools.experimental.agent_network_editor"
)
sys.modules["coded_tools.agent_network_instructions_editor"] = importlib.import_module(
    "coded_tools.experimental.agent_network_instructions_editor"
)
sys.modules["coded_tools.agent_network_architect"] = importlib.import_module(
    "coded_tools.experimental.agent_network_architect"
)
sys.modules["coded_tools.kwik_agents"] = importlib.import_module("coded_tools.experimental.kwik_agents")
sys.modules["coded_tools.cruse_agent"] = importlib.import_module("coded_tools.experimental.cruse_agent")
