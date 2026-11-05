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


class LinearScale:
    """
    Maps a data range onto a pixel range, for the charts drawn by SvgCharts.
    """

    def __init__(self, domain_low: float, domain_high: float, range_low: float, range_high: float):
        """
        :param domain_low: Lowest data value.
        :param domain_high: Highest data value.
        :param range_low: Pixel position for domain_low.
        :param range_high: Pixel position for domain_high.
        """
        # A degenerate domain would divide by zero; widen it symmetrically instead.
        if domain_high - domain_low < 1e-12:
            padding: float = max(abs(domain_low) * 0.05, 0.5)
            domain_low, domain_high = domain_low - padding, domain_high + padding
        self.domain_low: float = domain_low
        self.domain_high: float = domain_high
        self.range_low: float = range_low
        self.range_high: float = range_high

    def get_domain(self) -> tuple[float, float]:
        """
        :return: Tuple of (lowest, highest) data value, after any widening.
        """
        return self.domain_low, self.domain_high

    def place(self, value: float) -> float:
        """
        :param value: Data value to place.
        :return: Pixel position.
        """
        fraction: float = (value - self.domain_low) / (self.domain_high - self.domain_low)
        return self.range_low + fraction * (self.range_high - self.range_low)
