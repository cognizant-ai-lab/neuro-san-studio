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

"""Tests for ProcessLoggerInterface ABC."""

import pytest

from neuro_san_studio.interfaces.process_logger_interface import ProcessLoggerInterface


class TestProcessLoggerInterface:
    """Tests for the ProcessLoggerInterface abstract base class."""

    def test_cannot_instantiate_directly(self):
        """Test that ProcessLoggerInterface cannot be instantiated."""
        with pytest.raises(TypeError):
            ProcessLoggerInterface()  # pylint: disable=abstract-class-instantiated

    def test_concrete_subclass_must_implement_method(self):
        """Test that a subclass without attach_process_logger raises TypeError."""

        class IncompleteLogger(ProcessLoggerInterface):  # pylint: disable=too-few-public-methods
            """Intentionally incomplete subclass for testing."""

        with pytest.raises(TypeError):
            IncompleteLogger()  # pylint: disable=abstract-class-instantiated

    def test_concrete_subclass_can_be_instantiated(self):
        """Test that a fully implemented subclass can be instantiated."""

        class ConcreteLogger(ProcessLoggerInterface):  # pylint: disable=too-few-public-methods
            """Minimal concrete implementation for testing."""

            def attach_process_logger(self, process, process_name, log_file):
                pass

        logger = ConcreteLogger()
        assert isinstance(logger, ProcessLoggerInterface)
