# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
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

"""Implementation of the `neuro-san-studio init` command."""

import importlib.resources
import os
import shutil
import sys
from typing import Dict
from typing import List
from typing import Optional

PROVIDERS: Dict[str, Dict[str, str]] = {
    "openai": {"label": "OpenAI", "model_name": "gpt-5.2"},
    "anthropic": {"label": "Anthropic", "model_name": "claude-sonnet"},
    "google": {"label": "Google Gemini", "model_name": "gemini-3-flash"},
}


MANIFEST_HOCON = """{
    "music_nerd.hocon": true
}
"""


# Minimal starter MCP config. Users can uncomment and add servers as they need them.
MCP_INFO_HOCON = """# This file contains the MCP server configurations in the following format:
#     "mcp_server_url_1": {
#         "http_headers": {
#                "Authorization": "Bearer <token>",
#         }, # Optional: if the server requires authentication
#         # Optional: specific tools to load from this server. Loads all if omitted.
#         "tools": ["tool_1", "tool_2"]
#     },

{
    "https://mcp.deepwiki.com/mcp": {
        "tools": ["read_wiki_structure", "ask_question"]
    },
}
"""


class InitCommand:  # pylint: disable=too-few-public-methods
    """Scaffold a starter neuro-san-studio project in the current directory."""

    def __init__(self, providers_arg: Optional[str] = None, root_dir: Optional[str] = None):
        """Initialize the command.

        Args:
            providers_arg: Comma-separated provider keys (e.g. "openai,anthropic").
                When provided, skips the interactive prompt.
            root_dir: Directory to scaffold into. Defaults to the current working directory.
        """
        self.providers_arg = providers_arg
        self.root_dir = root_dir or os.getcwd()

    def run(self) -> None:
        """Resolve providers and write starter files."""
        providers = self._resolve_providers()
        print(f"Selected providers: {', '.join(PROVIDERS[p]['label'] for p in providers)}\n")

        self._copy_music_nerd()
        self._write_file(os.path.join("mcp", "mcp_info.hocon"), MCP_INFO_HOCON)
        self._write_file(os.path.join("registries", "manifest.hocon"), MANIFEST_HOCON)
        self._write_file(os.path.join("config", "llm_config.hocon"), self._render_llm_config(providers))

        self._print_next_steps()

    def _resolve_providers(self) -> List[str]:
        """Return the ordered list of provider keys to enable."""
        if self.providers_arg is not None:
            return self._parse_providers_arg(self.providers_arg)
        if not sys.stdin.isatty():
            print("No --providers flag and non-interactive terminal. Defaulting to OpenAI.\n")
            return ["openai"]
        return self._prompt_providers()

    @staticmethod
    def _parse_providers_arg(raw: str) -> List[str]:
        """Parse a comma-separated list of provider keys, preserving order and de-duplicating."""
        seen: List[str] = []
        for token in raw.split(","):
            key = token.strip().lower()
            if not key:
                continue
            if key not in PROVIDERS:
                valid = ", ".join(PROVIDERS.keys())
                raise ValueError(f"Unknown provider '{key}'. Valid providers: {valid}.")
            if key not in seen:
                seen.append(key)
        if not seen:
            raise ValueError("--providers must list at least one provider.")
        return seen

    @staticmethod
    def _prompt_providers() -> List[str]:
        """Prompt the user interactively for provider selection."""
        keys = list(PROVIDERS.keys())
        print("Which LLM providers do you want to enable?")
        for idx, key in enumerate(keys, start=1):
            info = PROVIDERS[key]
            default_tag = "  [default]" if key == "openai" else ""
            print(f"  {idx}) {info['label']:<14} ({info['model_name']}){default_tag}")
        raw = input("Enter numbers separated by commas (default: 1): ").strip()
        if not raw:
            return ["openai"]
        selected: List[str] = []
        for token in raw.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                idx = int(token)
            except ValueError as exc:
                raise ValueError(f"'{token}' is not a number.") from exc
            if idx < 1 or idx > len(keys):
                raise ValueError(f"Choice {idx} is out of range (1-{len(keys)}).")
            key = keys[idx - 1]
            if key not in selected:
                selected.append(key)
        if not selected:
            return ["openai"]
        return selected

    @staticmethod
    def _render_llm_config(providers: List[str]) -> str:
        """Render config/llm_config.hocon for the selected providers.

        Ordering: if OpenAI is selected, it is promoted to first position. Otherwise
        providers are emitted in user-selected order.
        """
        ordered = providers[:]
        if "openai" in ordered and ordered[0] != "openai":
            ordered.remove("openai")
            ordered.insert(0, "openai")

        if len(ordered) == 1:
            model = PROVIDERS[ordered[0]]["model_name"]
            return '{\n    "llm_config": {\n        "model_name": "' + model + '"\n    }\n}\n'

        lines = ["{", '    "llm_config": {', '        "fallbacks": [']
        for i, key in enumerate(ordered):
            model = PROVIDERS[key]["model_name"]
            comma = "," if i < len(ordered) - 1 else ""
            lines.append(f'            {{ "model_name": "{model}" }}{comma}')
        lines.extend(["        ]", "    }", "}", ""])
        return "\n".join(lines)

    def _copy_music_nerd(self) -> None:
        """Copy music_nerd.hocon from the installed neuro_san package into the project."""
        dest_rel = os.path.join("registries", "music_nerd.hocon")
        dest_abs = os.path.join(self.root_dir, dest_rel)
        if os.path.exists(dest_abs):
            print(f"[skip]  {dest_rel} (already exists)")
            return
        os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
        source = importlib.resources.files("neuro_san.registries") / "music_nerd.hocon"
        with source.open("rb") as src, open(dest_abs, "wb") as dst:
            shutil.copyfileobj(src, dst)
        print(f"[ok]    {dest_rel}")

    def _write_file(self, rel_path: str, content: str) -> None:
        """Write content to rel_path under root_dir, skipping if the file already exists."""
        dest_abs = os.path.join(self.root_dir, rel_path)
        if os.path.exists(dest_abs):
            print(f"[skip]  {rel_path} (already exists)")
            return
        os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
        with open(dest_abs, "w", encoding="utf-8") as fh:
            fh.write(content)
        print(f"[ok]    {rel_path}")

    def _print_next_steps(self) -> None:
        """Print the final instructions shown after scaffolding completes."""
        print("\n" + "=" * 60)
        print("Project initialized.")
        print("\nNext steps:")
        print("  1. Set the API keys for the providers you enabled (e.g. in a .env file).")
        print("  2. Start the server:  neuro-san-studio run")
        print("=" * 60)
