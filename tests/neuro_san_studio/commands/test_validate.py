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

"""Tests for the validate command wrapper and its manifest-driven external agent discovery."""

import io
import os
import sys
from unittest import TestCase
from unittest.mock import patch

from neuro_san_studio.commands.validate import ValidateCommand
from neuro_san_studio.discovery.manifest_read_error import ManifestReadError

_MODULE = "neuro_san_studio.commands.validate"


class TestValidateCommandRun(TestCase):
    """Tests for ValidateCommand.run - a thin wrapper over HoconValidatorCli plus manifest discovery."""

    def setUp(self):
        """Keep discovery away from the real repo manifest and the developer's environment."""
        lister_patcher = patch(f"{_MODULE}.ServedNetworkLister")
        self.mock_lister = lister_patcher.start()
        self.addCleanup(lister_patcher.stop)
        self.mock_lister.return_value.list_names.return_value = []
        self.mock_lister.return_value.warnings = []

        env_patcher = patch.dict(os.environ)
        env_patcher.start()
        self.addCleanup(env_patcher.stop)
        os.environ.pop("AGENT_MANIFEST_FILE", None)

    @staticmethod
    def _run_capturing_argv(command: ValidateCommand) -> list:
        """Run the command against a fake HoconValidatorCli and return the argv it saw."""
        captured = {}

        def fake_main():
            captured["argv"] = list(sys.argv)
            return 0

        with patch(f"{_MODULE}.HoconValidatorCli") as mock_cli:
            mock_cli.return_value.main.side_effect = fake_main
            command.run()
        return captured["argv"]

    @staticmethod
    def _external_agents_arg(argv: list) -> str:
        """Return the value that followed --external-agents in argv."""
        return argv[argv.index("--external-agents") + 1]

    def test_valid_returns_zero(self):
        """When the underlying validator returns 0, run() returns 0."""
        with patch(f"{_MODULE}.HoconValidatorCli") as mock_cli:
            mock_cli.return_value.main.return_value = 0
            self.assertEqual(ValidateCommand("agent.hocon").run(), 0)

    def test_validation_errors_return_one(self):
        """When the underlying validator returns 1, run() returns 1."""
        with patch(f"{_MODULE}.HoconValidatorCli") as mock_cli:
            mock_cli.return_value.main.return_value = 1
            self.assertEqual(ValidateCommand("agent.hocon").run(), 1)

    def test_load_error_code_two_is_normalized_to_one(self):
        """The library's exit code 2 (load error) is normalized to 1 for studio's CLI."""
        with patch(f"{_MODULE}.HoconValidatorCli") as mock_cli:
            mock_cli.return_value.main.return_value = 2
            self.assertEqual(ValidateCommand("agent.hocon").run(), 1)

    def test_unexpected_validator_error_returns_one(self):
        """An exception raised by the validator is caught and reported as exit code 1."""
        with patch(f"{_MODULE}.HoconValidatorCli") as mock_cli:
            mock_cli.return_value.main.side_effect = AttributeError("boom")
            self.assertEqual(ValidateCommand("agent.hocon").run(), 1)

    def test_builds_argv_from_all_options(self):
        """All command options are marshaled into the argv passed to HoconValidatorCli."""
        argv = self._run_capturing_argv(
            ValidateCommand(
                "agent.hocon",
                verbose=True,
                external_agents="/a,/b",
                mcp_servers="https://mcp.example.com",
                registry_dir="/reg",
            )
        )
        self.assertEqual(argv[1], "agent.hocon")
        self.assertIn("--verbose", argv)
        self.assertEqual(self._external_agents_arg(argv), "/a,/b")
        self.assertIn("--mcp-servers", argv)
        self.assertIn("https://mcp.example.com", argv)
        self.assertIn("--registry-dir", argv)
        self.assertIn("/reg", argv)

    def test_optional_flags_omitted_when_not_set(self):
        """Only the file path is passed when no optional flags are provided and nothing is discovered."""
        argv = self._run_capturing_argv(ValidateCommand("agent.hocon"))
        self.assertEqual(argv, ["hocon_validator_cli", "agent.hocon"])

    def test_sys_argv_restored_after_success(self):
        """sys.argv is restored after a normal run."""
        before = list(sys.argv)
        with patch(f"{_MODULE}.HoconValidatorCli") as mock_cli:
            mock_cli.return_value.main.return_value = 0
            ValidateCommand("agent.hocon").run()
        self.assertEqual(sys.argv, before)

    def test_sys_argv_restored_after_exception(self):
        """sys.argv is restored even when the validator raises."""
        before = list(sys.argv)
        with patch(f"{_MODULE}.HoconValidatorCli") as mock_cli:
            mock_cli.return_value.main.side_effect = RuntimeError("boom")
            ValidateCommand("agent.hocon").run()
        self.assertEqual(sys.argv, before)


class TestValidateCommandManifestDiscovery(TestCase):
    """Tests for how ValidateCommand seeds --external-agents from the composed manifest(s)."""

    def setUp(self):
        """Patch the lister and isolate the environment, as in TestValidateCommandRun."""
        lister_patcher = patch(f"{_MODULE}.ServedNetworkLister")
        self.mock_lister = lister_patcher.start()
        self.addCleanup(lister_patcher.stop)
        self.mock_lister.return_value.list_names.return_value = []
        self.mock_lister.return_value.warnings = []

        env_patcher = patch.dict(os.environ)
        env_patcher.start()
        self.addCleanup(env_patcher.stop)
        os.environ.pop("AGENT_MANIFEST_FILE", None)

    def _run_capturing_argv(self, command: ValidateCommand, stream_name: str = None) -> tuple:
        """Run the command against a fake HoconValidatorCli; return (exit_code, argv, captured stream text)."""
        captured = {}

        def fake_main():
            captured["argv"] = list(sys.argv)
            return 0

        stream = io.StringIO()
        with patch(f"{_MODULE}.HoconValidatorCli") as mock_cli:
            mock_cli.return_value.main.side_effect = fake_main
            if stream_name:
                with patch(f"sys.{stream_name}", stream):
                    exit_code = command.run()
            else:
                exit_code = command.run()
        return exit_code, captured.get("argv"), stream.getvalue()

    def test_discovered_names_are_passed_as_external_agents(self):
        """Names discovered from the manifest are forwarded as --external-agents."""
        self.mock_lister.return_value.list_names.return_value = ["/a", "/tools/b"]
        _, argv, _ = self._run_capturing_argv(ValidateCommand("agent.hocon"))
        self.assertEqual(argv[argv.index("--external-agents") + 1], "/a,/tools/b")

    def test_explicit_names_come_first_and_duplicates_dropped(self):
        """Explicit --external-agents precede discovered names, and repeats are removed."""
        self.mock_lister.return_value.list_names.return_value = ["/a", "/b"]
        _, argv, _ = self._run_capturing_argv(ValidateCommand("agent.hocon", external_agents="/b,/c"))
        self.assertEqual(argv[argv.index("--external-agents") + 1], "/b,/c,/a")

    def test_manifest_read_error_warns_and_continues(self):
        """A ManifestReadError is reported on stderr and validation still runs without discovered names."""
        self.mock_lister.return_value.list_names.side_effect = ManifestReadError(
            "include base directory '/reg' does not exist"
        )
        exit_code, argv, stderr = self._run_capturing_argv(ValidateCommand("agent.hocon"), stream_name="stderr")
        self.assertEqual(exit_code, 0)
        self.assertIn(
            "Warning: include base directory '/reg' does not exist; "
            "no external agents will be discovered from the manifest.",
            stderr,
        )
        self.assertNotIn("--external-agents", argv)

    def test_lister_warnings_are_printed(self):
        """Each manifest the lister skipped is reported on stderr while the discovered names are still used."""
        self.mock_lister.return_value.list_names.return_value = ["/a"]
        self.mock_lister.return_value.warnings = ["manifest file '/m' not found"]
        _, argv, stderr = self._run_capturing_argv(ValidateCommand("agent.hocon"), stream_name="stderr")
        self.assertIn(
            "Warning: manifest file '/m' not found; "
            "networks from this manifest will not be accepted as external agents.",
            stderr,
        )
        self.assertEqual(argv[argv.index("--external-agents") + 1], "/a")

    def test_manifest_option_takes_precedence_over_env(self):
        """--manifest wins over AGENT_MANIFEST_FILE."""
        os.environ["AGENT_MANIFEST_FILE"] = "/env/registries/manifest.hocon"
        self._run_capturing_argv(ValidateCommand("agent.hocon", manifest="/opt/registries/manifest.hocon"))
        self.mock_lister.assert_called_once_with(["/opt/registries/manifest.hocon"], base_dir=None)

    def test_env_manifest_pathsep_list_is_composed_in_one_lister(self):
        """An os.pathsep-separated AGENT_MANIFEST_FILE is handed to a single lister, in order."""
        first = "/p1/registries/manifest.hocon"
        second = "/p2/registries/manifest.hocon"
        os.environ["AGENT_MANIFEST_FILE"] = os.pathsep.join([first, second])
        self._run_capturing_argv(ValidateCommand("agent.hocon"))
        self.mock_lister.assert_called_once_with([first, second], base_dir=None)

    def test_default_manifest_is_under_registry_dir(self):
        """Without --manifest or the env var, the manifest is <registry_dir>/registries/manifest.hocon."""
        self._run_capturing_argv(ValidateCommand("agent.hocon", registry_dir="/reg"))
        expected = os.path.join("/reg", "registries", "manifest.hocon")
        self.mock_lister.assert_called_once_with([expected], base_dir="/reg")

    def test_default_manifest_is_under_cwd_without_registry_dir(self):
        """Without --registry-dir either, the manifest is <cwd>/registries/manifest.hocon."""
        self._run_capturing_argv(ValidateCommand("agent.hocon"))
        expected = os.path.join(os.getcwd(), "registries", "manifest.hocon")
        self.mock_lister.assert_called_once_with([expected], base_dir=None)

    def test_verbose_prints_discovery_summary(self):
        """--verbose reports how many names were taken from which manifest(s)."""
        self.mock_lister.return_value.list_names.return_value = ["/a", "/b"]
        command = ValidateCommand("agent.hocon", verbose=True, manifest="/m/registries/manifest.hocon")
        _, _, stdout = self._run_capturing_argv(command, stream_name="stdout")
        self.assertIn("Using 2 external agent name(s) from manifest(s): /m/registries/manifest.hocon", stdout)

    def test_discovery_exception_is_caught_by_run_guard(self):
        """An unexpected error during discovery is reported as exit code 1 and sys.argv is restored."""
        self.mock_lister.return_value.list_names.side_effect = RuntimeError("boom")
        before = list(sys.argv)
        with patch(f"{_MODULE}.HoconValidatorCli") as mock_cli, patch("sys.stderr", io.StringIO()):
            mock_cli.return_value.main.return_value = 0
            self.assertEqual(ValidateCommand("agent.hocon").run(), 1)
        self.assertEqual(sys.argv, before)
