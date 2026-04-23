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

"""Test helper: a callable that mirrors ``TopicSummarizer.should_summarize``."""

from __future__ import annotations


class ShouldSummarize:  # pylint: disable=too-few-public-methods
    """Callable wrapping the ``max_topic_size`` threshold used in tests.

    Mirrors :py:meth:`TopicSummarizer.should_summarize` so mocks can be
    swapped in without recreating the threshold logic in every test.
    """

    def __init__(self, threshold: int) -> None:
        self._threshold: int = threshold

    def __call__(self, content: str) -> bool:
        """Return ``True`` when ``content`` exceeds the configured threshold."""
        return self._threshold > 0 and len(content) > self._threshold
