#!/usr/bin/env python

# Copyright 2023-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT

"""
Minimal diagnostic script that:
  1. Reads a HOCON file (agent network OR standalone studio llm_config)
  2. Captures all llm_configs (top-level default + per-agent overrides)
  3. Creates LLM instances via the framework's DefaultLlmFactory
  4. Invokes each LLM with a trivial prompt to verify connectivity
  5. Reports which (label, llm_config) entries are broken

Supports two HOCON formats:

  Agent network format (has "tools"):
    {
        "llm_config": { "model_name": "gpt-5.2" },
        "tools": [ ... ]
    }

  Studio llm_config format (no "tools"):
    {
        "llm_config": {
            "class": "openai",
            "model_name": "gpt-5.2"
        }
    }

Usage:
    python check_llm_configs.py <path_to_hocon_file>

Examples:
    python check_llm_configs.py neuro_san/registries/music_nerd.hocon
    python check_llm_configs.py /path/to/llm_config.hocon
"""

import asyncio
import sys
import traceback
from io import BytesIO
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple

from langchain_core.language_models.base import BaseLanguageModel
from langchain_core.messages.human import HumanMessage

# For per-agent config merging, same as CallingActivation.prepare_run_context_config
from leaf_common.config.dictionary_overlay import DictionaryOverlay

# For parsing standalone HOCON files (same deserializer the framework uses internally
# via AbstractAsyncConfigRestorer.deserialize_file_contents)
from leaf_common.serialization.format.hocon_serialization_format import HoconSerializationFormat

# Framework imports - same classes the framework itself uses
from neuro_san.internals.graph.persistence.agent_network_restorer import AgentNetworkRestorer
from neuro_san.internals.graph.registry.agent_network import AgentNetwork
from neuro_san.internals.interfaces.context_type_llm_factory import ContextTypeLlmFactory
from neuro_san.internals.run_context.factory.master_llm_factory import MasterLlmFactory
from neuro_san.internals.run_context.langchain.llms.langchain_llm_resources import LangChainLlmResources

TEST_PROMPT = "Reply with exactly one word: hello"

# Word-level tokens that mark a key as sensitive.  Matching is done against
# the underscore-split parts of the lowercased key name so that, e.g.,
# "max_tokens" is NOT redacted (its parts are ["max", "tokens"]) while
# "access_token" IS redacted (its parts include "token").
_SENSITIVE_KEY_WORDS: frozenset = frozenset({"key", "token", "secret", "credential", "credentials", "password"})


def _is_sensitive_key(key: str) -> bool:
    """Return True when *key* contains a sensitive word at a word boundary or as a substring."""
    lower_key = key.lower()
    # Fast-path: check if the literal string "key" appears anywhere in the key name
    # (catches un-separated forms such as "apikey").
    if "key" in lower_key:
        return True
    parts = lower_key.split("_")
    # Check each individual part and adjacent pairs (to catch "api_key" as a unit).
    for i, part in enumerate(parts):
        if part in _SENSITIVE_KEY_WORDS:
            return True
        if i < len(parts) - 1:
            pair = f"{part}_{parts[i + 1]}"
            if pair in _SENSITIVE_KEY_WORDS:
                return True
    return False


def redact_llm_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a shallow copy of *config* with sensitive values replaced by
    ``'***REDACTED***'``.  Works recursively on nested dicts and lists so
    that structures like ``credentials: {key: "..."}`` are also safe.

    Sensitivity is determined per-word on the underscore-split key name, so
    ``max_tokens`` is left untouched while ``access_token`` and
    ``openai_api_key`` are redacted.
    """
    redacted: Dict[str, Any] = {}
    for key, value in config.items():
        if _is_sensitive_key(key):
            redacted[key] = "***REDACTED***"
        elif isinstance(value, dict):
            redacted[key] = redact_llm_config(value)
        elif isinstance(value, list):
            redacted[key] = [redact_llm_config(item) if isinstance(item, dict) else item for item in value]
        else:
            redacted[key] = value
    return redacted


def parse_hocon_file(hocon_path: str) -> Dict[str, Any]:
    """
    Parse a raw HOCON file into a Python dict using the same
    HoconSerializationFormat that the framework uses internally
    (via AbstractAsyncConfigRestorer.deserialize_file_contents).
    """
    with open(hocon_path, "r", encoding="utf-8") as file_obj:
        file_contents: str = file_obj.read()
    string_file = BytesIO(file_contents.encode("utf-8"))
    serialization = HoconSerializationFormat()
    return serialization.to_object(string_file)


def is_agent_network_hocon(config: Dict[str, Any]) -> bool:
    """
    Detect whether the parsed HOCON is an agent network (has "tools")
    or a standalone studio llm_config file.
    """
    return "tools" in config and isinstance(config["tools"], list)


def load_agent_network(hocon_path: str) -> AgentNetwork:
    """
    Read and parse an agent network HOCON file using the framework's AgentNetworkRestorer.
    This applies the full filter chain (DefaultsConfigFilter, etc.) just like the real framework.
    """
    restorer = AgentNetworkRestorer()
    agent_network: AgentNetwork = restorer.restore(file_reference=hocon_path)
    return agent_network


def _expand_fallbacks(label: str, llm_config: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Expand an llm_config that uses a 'fallbacks' list into individual
    (label, config) tuples so each model is tested separately.

    If there is no 'fallbacks' key the config is returned as-is.
    If the primary config (outside of 'fallbacks') also carries a model_name
    it is included as the first entry.
    """
    fallbacks: Any = llm_config.get("fallbacks")
    if not isinstance(fallbacks, list) or not fallbacks:
        return [(label, llm_config)]

    results: List[Tuple[str, Dict[str, Any]]] = []

    # Primary config (everything except the fallbacks list itself)
    primary_config: Dict[str, Any] = {k: v for k, v in llm_config.items() if k != "fallbacks"}
    if primary_config.get("model_name"):
        results.append((f"{label} (primary)", primary_config))

    for i, fallback_cfg in enumerate(fallbacks):
        results.append((f"{label} (fallback {i})", fallback_cfg))

    return results


def extract_llm_configs_from_agent_network(
    agent_network: AgentNetwork,
) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Extract all (agent_name, llm_config) pairs from a parsed agent network.

    After the DefaultsConfigFilter has run, every tool spec already has an llm_config
    (either its own or inherited from top-level). We also merge with the top-level
    llm_config the same way CallingActivation.prepare_run_context_config does.
    Configs that use a 'fallbacks' list are expanded into one entry per fallback.
    """
    config: Dict[str, Any] = agent_network.get_config()
    tools: List[Dict[str, Any]] = config.get("tools", [])
    top_level_llm_config: Dict[str, Any] = config.get("llm_config", {})

    overlayer = DictionaryOverlay()
    results: List[Tuple[str, Dict[str, Any]]] = []

    for tool_spec in tools:
        # Get agent name the same way AgentNetwork does
        agent_name: str = agent_network.get_name_from_spec(tool_spec)

        # Skip CodedTool agents (they have a "class" key) - they don't use LLMs
        if tool_spec.get("class") is not None:
            continue

        # Merge llm_config: top-level defaults overlayed with per-agent overrides
        # This mirrors CallingActivation.prepare_run_context_config
        agent_llm_config: Dict[str, Any] = tool_spec.get("llm_config", {})
        merged_llm_config: Dict[str, Any] = overlayer.overlay(top_level_llm_config, agent_llm_config)

        results.extend(_expand_fallbacks(agent_name, merged_llm_config))

    return results


def extract_llm_configs_from_studio_config(
    config: Dict[str, Any],
    hocon_path: str,
) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Extract the llm_config from a standalone studio llm_config.hocon file.
    These files have no agents, just a top-level llm_config dict.
    We use the file path as the label since there are no agent names.
    Configs that use a 'fallbacks' list are expanded into one entry per fallback.
    """
    llm_config: Dict[str, Any] = config.get("llm_config")
    if not llm_config:
        return []
    return _expand_fallbacks(hocon_path, llm_config)


def create_and_load_llm_factory(config: Dict[str, Any]) -> ContextTypeLlmFactory:
    """
    Create the LLM factory using the framework's MasterLlmFactory,
    then load the llm_info (default_llm_info.hocon + any custom llm_info_file).
    This is identical to what DirectAgentSessionFactory.create_session does.
    """
    llm_factory: ContextTypeLlmFactory = MasterLlmFactory.create_llm_factory(config)
    llm_factory.load()
    return llm_factory


def create_llm_instance(
    llm_factory: ContextTypeLlmFactory,
    llm_config: Dict[str, Any],
) -> BaseLanguageModel:
    """
    Create an LLM instance from a specific llm_config using the framework's
    factory. This calls DefaultLlmFactory.create_llm which:
      - Resolves the model_name in default_llm_info.hocon
      - Builds a fully-specified config (merging class defaults)
      - Dispatches to the correct LlmPolicy (OpenAI, Anthropic, etc.)
      - Returns a LangChainLlmResources wrapping the BaseLanguageModel
    """
    llm_resources: LangChainLlmResources = llm_factory.create_llm(llm_config)
    return llm_resources.get_model()


async def invoke_llm(llm: BaseLanguageModel) -> str:
    """
    Invoke the LLM with a trivial prompt to verify it is working.
    Uses LangChain's BaseLanguageModel.ainvoke() - the same async interface
    the framework uses under the hood (RunContextRunnable calls ainvoke).
    """
    messages = [HumanMessage(content=TEST_PROMPT)]
    response = await llm.ainvoke(messages)
    # response is a BaseMessage; extract text content
    if hasattr(response, "content"):
        return response.content
    return str(response)


async def test_llm_configs(
    llm_factory: ContextTypeLlmFactory,
    llm_configs: List[Tuple[str, Dict[str, Any]]],
) -> Tuple[List[Tuple[List[str], Dict[str, Any]]], List[Tuple[List[str], Dict[str, Any], str]]]:
    """
    Test each unique llm_config by creating an LLM instance and invoking it.
    Returns (successes, failures) where each entry groups labels sharing the same config.
    """
    # pylint: disable=too-many-locals
    failures: List[Tuple[List[str], Dict[str, Any], str]] = []
    successes: List[Tuple[List[str], Dict[str, Any]]] = []

    # Deduplicate configs to avoid redundant API calls while tracking all labels
    # Key: string repr of sorted llm_config items -> (labels, llm_config)
    unique_configs: Dict[str, Tuple[List[str], Dict[str, Any]]] = {}
    for label, llm_cfg in llm_configs:
        config_key: str = str(sorted(llm_cfg.items()))
        if config_key not in unique_configs:
            unique_configs[config_key] = ([], llm_cfg)
        unique_configs[config_key][0].append(label)

    total_count: int = len(llm_configs)
    unique_count: int = len(unique_configs)
    print(f"  Found {total_count} llm_config(s) with {unique_count} unique configuration(s).")
    if unique_count < total_count:
        print(f"  Skipping {total_count - unique_count} duplicate config(s).\n")
    else:
        print()

    for config_key, (labels, llm_cfg) in unique_configs.items():
        labels_str: str = ", ".join(labels)
        model_name: str = llm_cfg.get("model_name", "<not specified>")
        print(f"  Testing model '{model_name}' (used by: {labels_str})")

        # Create the LLM instance
        try:
            llm: BaseLanguageModel = create_llm_instance(llm_factory, llm_cfg)
            print(f"    LLM instance created: {type(llm).__name__}")
        except Exception as exc:  # pylint: disable=broad-except
            error_msg: str = f"Failed to create LLM: {exc}"
            print(f"    FAIL (creation): {error_msg}")
            failures.append((labels, llm_cfg, error_msg))
            continue

        # Invoke the LLM
        try:
            response_text: str = await invoke_llm(llm)
            print(f"    Response: {response_text[:100]!r}")
            successes.append((labels, llm_cfg))
        except Exception as exc:  # pylint: disable=broad-except
            error_msg = f"Failed to invoke LLM: {exc}"
            print(f"    FAIL (invocation): {error_msg}")
            traceback.print_exc()
            failures.append((labels, llm_cfg, error_msg))

        print()

    return successes, failures


def print_results(
    successes: List[Tuple[List[str], Dict[str, Any]]],
    failures: List[Tuple[List[str], Dict[str, Any], str]],
):
    """Print the final results summary."""
    print("=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    if successes:
        print(f"\nWorking ({len(successes)} unique config(s)):")
        for labels, llm_cfg in successes:
            labels_str = ", ".join(labels)
            print(f"  model: {llm_cfg.get('model_name', 'N/A'):30s} | used by: {labels_str}")

    if failures:
        print(f"\nFailing ({len(failures)} unique config(s)):")
        for labels, llm_cfg, error_msg in failures:
            labels_str = ", ".join(labels)
            print(f"  model: {llm_cfg.get('model_name', 'N/A'):30s} | used by: {labels_str}")
            print(f"    Error: {error_msg}")
    else:
        print("\nAll LLM configurations are working.")

    print()


async def run_checks(hocon_path: str) -> bool:
    """
    Run all LLM config validation steps for the given HOCON file.

    Returns True if all configurations passed (or none were found),
    False if any fatal error or LLM test failure occurred.
    """
    # --- Step 1: Parse the HOCON file and detect format ---
    print(f"[1] Parsing HOCON file: {hocon_path}")
    try:
        raw_config: Dict[str, Any] = parse_hocon_file(hocon_path)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"    FATAL: Failed to parse HOCON file: {exc}")
        return False

    agent_network_mode: bool = is_agent_network_hocon(raw_config)

    if agent_network_mode:
        print("    Detected format: agent network (has 'tools')")
        try:
            agent_network: AgentNetwork = load_agent_network(hocon_path)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"    FATAL: Failed to load agent network: {exc}")
            return False
        config: Dict[str, Any] = agent_network.get_config()
        network_name: str = agent_network.get_network_name()
        print(f"    Agent network: {network_name}")
    else:
        print("    Detected format: standalone studio llm_config")
        config = raw_config

    # --- Step 2: Extract all llm_configs ---
    print("[2] Extracting llm_configs...")
    if agent_network_mode:
        llm_configs: List[Tuple[str, Dict[str, Any]]] = extract_llm_configs_from_agent_network(
            agent_network,
        )
    else:
        llm_configs = extract_llm_configs_from_studio_config(config, hocon_path)

    if not llm_configs:
        print("    No llm_config found in this HOCON file.")
        return True

    for label, llm_cfg in llm_configs:
        print(f"    {label:30s} | llm_config: {redact_llm_config(llm_cfg)}")

    # --- Step 3: Create and load the LLM factory ---
    print("[3] Creating LLM factory (loading default_llm_info.hocon)...")
    try:
        llm_factory: ContextTypeLlmFactory = create_and_load_llm_factory(config)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"    FATAL: Failed to create/load LLM factory: {exc}")
        return False
    print("    LLM factory loaded successfully.")

    # --- Step 4: Test each unique LLM configuration ---
    print("[4] Testing LLM configuration(s)...\n")
    successes, failures = await test_llm_configs(llm_factory, llm_configs)

    # --- Step 5: Report results ---
    print_results(successes, failures)

    return not failures


async def main():
    """Entry point: parse args, run checks, exit non-zero on failure."""
    if len(sys.argv) < 2:
        print("Usage: python check_llm_configs.py <path_to_hocon_file>")
        sys.exit(1)

    hocon_path: str = sys.argv[1]
    success: bool = await run_checks(hocon_path)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
