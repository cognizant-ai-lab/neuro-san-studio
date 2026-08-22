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

import sys
from unittest import TestCase
from unittest.mock import patch

from neuro_san_studio.commands.chat import ChatCommand

_MODULE = "neuro_san_studio.commands.chat"


class TestChatCommandRun(TestCase):
    """Tests for ChatCommand.run - a thin wrapper over AgentCli."""

    def test_normal_return_gives_zero(self):
        """When AgentCli.main() returns normally, run() returns 0."""
        with patch(f"{_MODULE}.AgentCli") as mock_cli:
            mock_cli.return_value.main.return_value = None
            assert ChatCommand("music_nerd").run() == 0

    def test_exception_returns_one(self):
        """When AgentCli.main() raises, run() returns 1."""
        with patch(f"{_MODULE}.AgentCli") as mock_cli:
            mock_cli.return_value.main.side_effect = ValueError("agent not found")
            assert ChatCommand("music_nerd").run() == 1

    def test_keyboard_interrupt_returns_zero(self):
        """Ctrl+C during interactive chat is a normal exit (code 0)."""
        with patch(f"{_MODULE}.AgentCli") as mock_cli:
            mock_cli.return_value.main.side_effect = KeyboardInterrupt()
            assert ChatCommand("music_nerd").run() == 0

    def test_builds_argv_with_all_options(self):
        """All explicit options are marshaled into the argv passed to AgentCli."""
        captured = {}

        def fake_main():
            captured["argv"] = list(sys.argv)

        with patch(f"{_MODULE}.AgentCli") as mock_cli:
            mock_cli.return_value.main.side_effect = fake_main
            ChatCommand(
                "music_nerd",
                connection="http",
                host="myhost",
                port=9090,
                one_shot=True,
            ).run()

        argv = captured["argv"]
        assert argv[0] == "agent_cli"
        assert "--agent" in argv
        assert "music_nerd" in argv
        assert "--connection" in argv
        assert "http" in argv
        assert "--host" in argv
        assert "myhost" in argv
        assert "--port" in argv
        assert "9090" in argv
        assert "--one_shot" in argv

    def test_list_mode_skips_agent_flag(self):
        """When list_agents is True, --agent is not emitted."""
        captured = {}

        def fake_main():
            captured["argv"] = list(sys.argv)

        with patch(f"{_MODULE}.AgentCli") as mock_cli:
            mock_cli.return_value.main.side_effect = fake_main
            ChatCommand(None, list_agents=True).run()

        argv = captured["argv"]
        assert "--list" in argv
        assert "--agent" not in argv

    def test_none_agent_without_list_skips_agent_flag(self):
        """When agent is None and list is False, --agent is not emitted."""
        captured = {}

        def fake_main():
            captured["argv"] = list(sys.argv)

        with patch(f"{_MODULE}.AgentCli") as mock_cli:
            mock_cli.return_value.main.side_effect = fake_main
            ChatCommand(None, extra_args=["--tag", "demo"]).run()

        argv = captured["argv"]
        assert "--agent" not in argv
        assert "--tag" in argv
        assert "demo" in argv

    def test_extra_args_forwarded(self):
        """Extra arguments from the Typer context are appended to argv."""
        captured = {}

        def fake_main():
            captured["argv"] = list(sys.argv)

        with patch(f"{_MODULE}.AgentCli") as mock_cli:
            mock_cli.return_value.main.side_effect = fake_main
            ChatCommand("music_nerd", extra_args=["--tokens", "--minimal"]).run()

        argv = captured["argv"]
        assert "--tokens" in argv
        assert "--minimal" in argv

    def test_default_connection_is_direct(self):
        """The default connection type is 'direct'."""
        captured = {}

        def fake_main():
            captured["argv"] = list(sys.argv)

        with patch(f"{_MODULE}.AgentCli") as mock_cli:
            mock_cli.return_value.main.side_effect = fake_main
            ChatCommand("music_nerd").run()

        argv = captured["argv"]
        idx = argv.index("--connection")
        assert argv[idx + 1] == "direct"

    def test_sys_argv_restored_after_success(self):
        """sys.argv is restored after a normal run."""
        before = list(sys.argv)
        with patch(f"{_MODULE}.AgentCli") as mock_cli:
            mock_cli.return_value.main.return_value = None
            ChatCommand("music_nerd").run()
        assert sys.argv == before

    def test_sys_argv_restored_after_exception(self):
        """sys.argv is restored even when AgentCli raises."""
        before = list(sys.argv)
        with patch(f"{_MODULE}.AgentCli") as mock_cli:
            mock_cli.return_value.main.side_effect = RuntimeError("boom")
            ChatCommand("music_nerd").run()
        assert sys.argv == before

    def test_applies_project_environment_before_chat(self):
        """run() sets up the project env (manifest, tool path, etc.) before delegating.

        A direct chat is in-process, so without this neuro-san falls back to its bundled
        library manifest and cannot find the project's own agents.
        """
        with patch(f"{_MODULE}.AgentCli") as mock_cli, patch(f"{_MODULE}.ProjectEnvironment") as mock_env:
            mock_cli.return_value.main.return_value = None
            ChatCommand("music_nerd").run()
        mock_env.return_value.apply.assert_called_once()
