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

"""Temporary success-ratio changes used to verify confident Consultant fixes."""

import logging
import os
import re

logger = logging.getLogger("network_consultant")
SUCCESS_RATIO_PATTERN = re.compile(r'("success_ratio"\s*:\s*")(\d+/\d+)(")')


class FixtureRatioManager:
    """Apply and restore fixture success ratios without abandoning partial cleanup."""

    @staticmethod
    def set_for_paths(paths: list[str], ratio: str) -> dict[str, str]:
        """
        Replace success ratios for the supplied fixture paths.

        :param paths: The fixture paths to update.
        :param ratio: The success ratio to apply.
        :return: Original ratios keyed by every changed path.
        """
        originals: dict[str, str] = {}
        for path in paths:
            with open(path, encoding="utf-8") as fixture_file:
                text = fixture_file.read()
            match = SUCCESS_RATIO_PATTERN.search(text)
            if not match or match.group(2) == ratio:
                continue
            originals.update({path: match.group(2)})
            with open(path, "w", encoding="utf-8") as fixture_file:
                fixture_file.write(SUCCESS_RATIO_PATTERN.sub(rf"\g<1>{ratio}\g<3>", text, count=1))
            logger.info("success_ratio %s -> %s: %s", originals.get(path), ratio, path)
        return originals

    @staticmethod
    def set_for_fixtures(paths: list[str], fixture_names: list[str], ratio: str) -> dict[str, str]:
        """
        Replace success ratios for the named fixtures among the supplied paths.

        :param paths: All fixture paths available for the target network.
        :param fixture_names: Fixture basenames selected for stricter verification.
        :param ratio: The success ratio to apply.
        :return: Original ratios keyed by every changed path.
        """
        wanted = set(fixture_names)
        selected_paths: list[str] = []
        for path in paths:
            if os.path.basename(path) in wanted:
                selected_paths.append(path)
        return FixtureRatioManager.set_for_paths(selected_paths, ratio)

    @staticmethod
    def restore(originals: dict[str, str]) -> None:
        """
        Restore every recorded fixture ratio while reporting individual failures.

        :param originals: The original fixture ratios keyed by path.
        """
        restored = 0
        for path, ratio in originals.items():
            try:
                with open(path, encoding="utf-8") as fixture_file:
                    text = fixture_file.read()
                with open(path, "w", encoding="utf-8") as fixture_file:
                    fixture_file.write(SUCCESS_RATIO_PATTERN.sub(rf"\g<1>{ratio}\g<3>", text, count=1))
            except OSError as error:
                logger.warning("Could not restore success_ratio %s on %s: %s", ratio, path, error)
                continue
            restored += 1
            logger.info("success_ratio restored -> %s: %s", ratio, path)
        logger.info("restore_success_ratios: restored %d/%d fixture(s)", restored, len(originals))
