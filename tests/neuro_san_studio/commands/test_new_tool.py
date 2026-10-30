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

"""Tests for the `ns new tool` command."""

from pathlib import Path

import pytest

from neuro_san_studio.commands.new_tool import NewToolCommand


class TestToClassName:
    """Unit tests for NewToolCommand._to_class_name."""

    def test_snake_case(self) -> None:
        """Snake-case name converts to PascalCase."""
        assert NewToolCommand._to_class_name("my_tool") == "MyTool"  # pylint: disable=protected-access

    def test_single_word(self) -> None:
        """Single-word name is capitalized."""
        assert NewToolCommand._to_class_name("fetcher") == "Fetcher"  # pylint: disable=protected-access

    def test_three_words(self) -> None:
        """Three-word name converts every segment."""
        assert NewToolCommand._to_class_name("get_arxiv_paper") == "GetArxivPaper"  # pylint: disable=protected-access


class TestNewToolValidation:
    """Name validation tests."""

    def test_invalid_name_uppercase_returns_error(self, tmp_path: Path) -> None:
        """Uppercase letters in the name are rejected."""
        assert NewToolCommand(name="MyTool", root_dir=str(tmp_path)).run() == 1

    def test_invalid_name_leading_digit_returns_error(self, tmp_path: Path) -> None:
        """Names starting with a digit are rejected."""
        assert NewToolCommand(name="1tool", root_dir=str(tmp_path)).run() == 1

    def test_invalid_name_python_keyword_returns_error(self, tmp_path: Path) -> None:
        """Python keywords are rejected to avoid syntax errors in generated imports."""
        assert NewToolCommand(name="class", root_dir=str(tmp_path)).run() == 1


class TestNewToolRun:
    """Integration tests for NewToolCommand.run()."""

    def _run(self, tmp_path: Path, name: str = "my_tool") -> int:
        """Run the command in a temporary project root."""
        return NewToolCommand(name=name, root_dir=str(tmp_path)).run()

    def test_creates_tool_py(self, tmp_path: Path) -> None:
        """The tool source file is created under coded_tools/."""
        self._run(tmp_path)
        assert (tmp_path / "coded_tools" / "my_tool" / "my_tool.py").is_file()

    def test_creates_init_py(self, tmp_path: Path) -> None:
        """An __init__.py package marker is created alongside the tool."""
        self._run(tmp_path)
        assert (tmp_path / "coded_tools" / "my_tool" / "__init__.py").is_file()

    def test_creates_test_file(self, tmp_path: Path) -> None:
        """A unit test stub is created under tests/neuro_san_studio/coded_tools/."""
        self._run(tmp_path)
        assert (tmp_path / "tests" / "neuro_san_studio" / "coded_tools" / "test_my_tool.py").is_file()

    def test_tool_py_contains_class_name(self, tmp_path: Path) -> None:
        """The generated file declares the correct CodedTool subclass."""
        self._run(tmp_path)
        text = (tmp_path / "coded_tools" / "my_tool" / "my_tool.py").read_text()
        assert "class MyTool(CodedTool):" in text

    def test_tool_py_contains_async_invoke(self, tmp_path: Path) -> None:
        """The generated file contains the async_invoke stub."""
        self._run(tmp_path)
        text = (tmp_path / "coded_tools" / "my_tool" / "my_tool.py").read_text()
        assert "async def async_invoke" in text

    def test_test_py_contains_class_reference(self, tmp_path: Path) -> None:
        """The generated test file imports and references the tool class."""
        self._run(tmp_path)
        text = (tmp_path / "tests" / "neuro_san_studio" / "coded_tools" / "test_my_tool.py").read_text()
        assert "MyTool" in text
        assert "async_invoke" in text

    def test_skips_existing_tool_file(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """An existing tool file is left untouched and reported as skipped."""
        tool_dir = tmp_path / "coded_tools" / "my_tool"
        tool_dir.mkdir(parents=True)
        existing = tool_dir / "my_tool.py"
        existing.write_text("DO NOT OVERWRITE\n", encoding="utf-8")

        self._run(tmp_path)

        assert existing.read_text() == "DO NOT OVERWRITE\n"
        out = capsys.readouterr().out
        assert "[skip]" in out

    def test_returns_zero_on_success(self, tmp_path: Path) -> None:
        """A successful run returns exit code 0."""
        assert self._run(tmp_path) == 0

    def test_three_word_name(self, tmp_path: Path) -> None:
        """Three-word names produce the correct PascalCase class declaration."""
        self._run(tmp_path, name="get_arxiv_paper")
        text = (tmp_path / "coded_tools" / "get_arxiv_paper" / "get_arxiv_paper.py").read_text()
        assert "class GetArxivPaper(CodedTool):" in text
