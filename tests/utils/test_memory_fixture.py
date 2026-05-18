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

"""Seed, validate, and tear down the live persistent-memory file for one test.

Writes land under ``memory/test/`` when the HOCON sets
``sly_data["test_mode"] = true``; this fixture reads from the same place.
"""

import json
from pathlib import Path
from typing import Any
from typing import ClassVar
from unittest import TestCase


class TestMemoryFixture:
    """Per-test seeder / asserter / cleaner for the live memory file.

    Sidecars next to the test HOCON:
      ``<hocon>.initial_memory.json``  — flat ``{topic: content}`` seed.
      ``<hocon>.expected_memory.json`` — assertion schema (see
      :py:meth:`assert_matches_expected`).

    Use as a context manager around the agent call::

        with TestMemoryFixture("CoffeeFinder", "UserPreferences",
                               test_hocon_path=Path(test_hocon)) as fx:
            run_the_test(...)
            fx.assert_matches_expected(self)
    """

    # Matches TopicStoreFactory's test_mode subfolder so seeding and the
    # agent's writes target the same file.
    MEMORY_ROOT_DIR: ClassVar[str] = "memory/test"
    DEFAULT_FILE_NAME: ClassVar[str] = "memory"
    INITIAL_SIDECAR_SUFFIX: ClassVar[str] = ".initial_memory.json"
    EXPECTED_SIDECAR_SUFFIX: ClassVar[str] = ".expected_memory.json"

    def __init__(
        self,
        agent_network: str,
        agent_name: str,
        test_hocon_path: str | Path | None = None,
        file_name: str = DEFAULT_FILE_NAME,
        store_root: str | Path | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self._agent_network: str = agent_network
        self._agent_name: str = agent_name
        self._file_name: str = f"{file_name}.json"
        self._repo_root: Path = (repo_root or self._infer_repo_root()).resolve()
        self._store_root: Path = self._resolve_store_root(store_root)
        self._test_hocon_path: Path | None = Path(test_hocon_path).resolve() if test_hocon_path else None

    @property
    def default_fixture_file(self) -> Path:
        """Seed fallback path, used when no ``initial_memory`` sidecar exists."""
        return self._repo_root / self.MEMORY_ROOT_DIR / self._agent_network / self._agent_name / self._file_name

    @property
    def initial_sidecar(self) -> Path | None:
        """``<hocon>.initial_memory.json`` path, or ``None``."""
        return self._sidecar(self.INITIAL_SIDECAR_SUFFIX)

    @property
    def expected_sidecar(self) -> Path | None:
        """``<hocon>.expected_memory.json`` path, or ``None``."""
        return self._sidecar(self.EXPECTED_SIDECAR_SUFFIX)

    @property
    def live_file(self) -> Path:
        """Absolute path to the live persistent-memory JSON file."""
        return self._store_root / self._agent_network / self._agent_name / self._file_name

    def setup(self) -> None:
        """Wipe and recreate the agent's live folder, then seed it if possible.

        Seed priority: per-test sidecar, then per-(network, agent) default,
        else empty.
        """
        self._remove_live_dir()
        live: Path = self.live_file
        live.parent.mkdir(parents=True, exist_ok=True)
        source: Path | None = self._resolve_seed_source()
        if source is None:
            return
        live.write_bytes(source.read_bytes())

    def teardown(self) -> None:
        """Remove the live memory folder."""
        self._remove_live_dir()

    def assert_matches_expected(self, test_case: TestCase) -> None:
        """Assert live memory satisfies the ``expected_memory`` sidecar; no-op if absent.

        Sidecar schema (all sections optional)::

            {
              "topics_present":    {"<topic>": ["<substring>", ...]},
              "topics_absent":     ["<topic>", ...],
              "substrings_absent": {"<topic>": ["<substring>", ...]}
            }

        Substring matches are case-insensitive. Empty substring list means
        require the topic but don't constrain its body.
        """
        sidecar: Path | None = self.expected_sidecar
        if sidecar is None or not sidecar.is_file():
            return
        expected: dict[str, Any] = self._load_json(sidecar)
        actual: dict[str, str] = self._load_live_memory()

        self._assert_topics_present(test_case, expected.get("topics_present") or {}, actual)
        self._assert_topics_absent(test_case, expected.get("topics_absent") or [], actual)
        self._assert_substrings_absent(test_case, expected.get("substrings_absent") or {}, actual)

    def __enter__(self) -> "TestMemoryFixture":
        self.setup()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        del exc_type, exc, traceback
        self.teardown()

    def _resolve_seed_source(self) -> Path | None:
        """Sidecar if present, else default fixture, else ``None``."""
        sidecar: Path | None = self.initial_sidecar
        if sidecar is not None and sidecar.is_file():
            return sidecar
        default: Path = self.default_fixture_file
        if default.is_file():
            return default
        return None

    def _sidecar(self, suffix: str) -> Path | None:
        """Sidecar path next to the test HOCON, or ``None`` if none was given."""
        if self._test_hocon_path is None:
            return None
        stem: str = self._test_hocon_path.with_suffix("").name
        return self._test_hocon_path.parent / f"{stem}{suffix}"

    def _remove_live_dir(self) -> None:
        """Recursively delete ``<store_root>/<network>/<agent>/`` (no ``shutil``)."""
        folder: Path = self.live_file.parent
        if not folder.exists():
            return
        for path in sorted(folder.rglob("*"), reverse=True):
            if path.is_file() or path.is_symlink():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        folder.rmdir()

    def _load_live_memory(self) -> dict[str, str]:
        """Read the live memory file; ``{}`` if absent or unreadable."""
        live: Path = self.live_file
        if not live.is_file():
            return {}
        return self._load_json(live)

    def _assert_topics_present(
        self,
        test_case: TestCase,
        topics_present: dict[str, list[str]],
        actual: dict[str, str],
    ) -> None:
        """Each listed topic must exist with all required substrings in its body."""
        for topic, substrings in topics_present.items():
            test_case.assertIn(
                topic,
                actual,
                f"expected memory to contain topic '{topic}'. Got: {sorted(actual.keys())}",
            )
            body_lower: str = actual[topic].lower()
            for substring in substrings:
                test_case.assertIn(
                    substring.lower(),
                    body_lower,
                    f"memory[{topic!r}] missing substring {substring!r}. Got: {actual[topic]!r}",
                )

    def _assert_topics_absent(
        self,
        test_case: TestCase,
        topics_absent: list[str],
        actual: dict[str, str],
    ) -> None:
        """None of the listed topics may be present."""
        for topic in topics_absent:
            test_case.assertNotIn(
                topic,
                actual,
                f"memory should not contain topic '{topic}'. Got: {sorted(actual.keys())}",
            )

    def _assert_substrings_absent(
        self,
        test_case: TestCase,
        substrings_absent: dict[str, list[str]],
        actual: dict[str, str],
    ) -> None:
        """For topics that exist, none of the disallowed substrings may appear."""
        for topic, substrings in substrings_absent.items():
            if topic not in actual:
                continue
            body_lower: str = actual[topic].lower()
            for substring in substrings:
                test_case.assertNotIn(
                    substring.lower(),
                    body_lower,
                    f"memory[{topic!r}] should not contain {substring!r}. Got: {actual[topic]!r}",
                )

    def _resolve_store_root(self, store_root: str | Path | None) -> Path:
        """Resolve store root, anchoring relative paths to the repo root."""
        candidate: Path = Path(store_root or self.MEMORY_ROOT_DIR).expanduser()
        if not candidate.is_absolute():
            candidate = self._repo_root / candidate
        return candidate.resolve()

    @classmethod
    def _load_json(cls, path: Path) -> dict[str, Any]:
        """Parse JSON into a dict; ``{}`` if malformed or non-object."""
        try:
            parsed: Any = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @classmethod
    def _infer_repo_root(cls) -> Path:
        """Repo root, two levels above this file (``<root>/tests/utils/``)."""
        return Path(__file__).resolve().parents[2]
