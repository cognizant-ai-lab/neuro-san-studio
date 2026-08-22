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

from ipaddress import IPv4Address
from ipaddress import IPv6Address
from ipaddress import ip_address
from socket import AF_INET

# AddressFamily exists at runtime (created dynamically as an IntEnum), but pylint
# cannot see it in the socket module stubs.
from socket import AddressFamily  # pylint: disable=no-name-in-module

from aiohttp import DefaultResolver
from aiohttp.abc import AbstractResolver
from aiohttp.abc import ResolveResult


class GlobalOnlyResolver(AbstractResolver):
    """DNS resolver that only returns globally routable addresses.

    Wraps aiohttp's DefaultResolver and requires every resolved address to be
    globally routable (rejects private/loopback/link-local/multicast/reserved
    ranges), raising ValueError with a url_not_allowed prefix otherwise.

    Why a resolver instead of a pre-fetch DNS check: validating a hostname
    *before* the fetch leaves a DNS-rebinding gap. The HTTP client re-resolves
    the hostname at connection time, so an attacker-controlled DNS server can
    return a safe address during validation and an internal one (e.g.
    169.254.169.254) for the actual connection. This resolver runs *inside*
    aiohttp's TCPConnector at connection time, so the addresses validated here
    are exactly the addresses the client connects to — there is no window in
    which the answer can change.

    Usage — disable the connector's DNS cache so every new connection
    re-validates instead of reusing a previously cached answer:

        TCPConnector(resolver=GlobalOnlyResolver(), use_dns_cache=False)

    Limitations:
    - aiohttp's TCPConnector short-circuits IP-literal hosts and never calls
      the resolver for them (see TCPConnector._resolve_host), so IP literals
      must be validated before the fetch (see WebFetch._validate_hostname_safety,
      which shares ensure_global_address for that check).
    - DNS is not the only rebinding vector: this does not protect requests made
      outside the connector this resolver is attached to.
    """

    def __init__(self) -> None:
        # DefaultResolver performs the actual lookup via the event loop's
        # non-blocking getaddrinfo (type=SOCK_STREAM) and builds the
        # ResolveResult dicts that TCPConnector expects, including IPv6
        # edge-case handling — no need to reimplement that here.
        self._resolver: DefaultResolver = DefaultResolver()

    @staticmethod
    def ensure_global_address(hostname: str, address: IPv4Address | IPv6Address) -> None:
        """Raise ValueError with url_not_allowed if the address is not globally routable.

        is_global is False for private (10/8, 172.16/12, 192.168/16), loopback
        (127/8, ::1), link-local (169.254/16, fe80::/10), CGNAT (100.64/10),
        multicast, unspecified (0.0.0.0, ::), and other reserved ranges.

        :param hostname: The hostname being validated; only used in the error message.
        :param address: The IP address to check.
        """
        if not address.is_global:
            raise ValueError(
                f"url_not_allowed: Host '{hostname}' uses IP address '{address}', "
                "which is not a globally routable address."
            )

    async def resolve(self, host: str, port: int = 0, family: AddressFamily = AF_INET) -> list[ResolveResult]:
        """Resolve the host and raise ValueError if any address is not globally routable.

        :param host: The hostname to resolve (never an IP literal; aiohttp
                     short-circuits those before calling the resolver).
        :param port: The port to include in the resolved results.
        :param family: The address family to resolve for (AF_INET, AF_INET6, or AF_UNSPEC).
        :return: The resolved addresses, all verified to be globally routable.
        :raises ValueError: url_not_allowed when resolution fails, yields no
                            addresses, or yields any non-global address.
        """
        try:
            results: list[ResolveResult] = await self._resolver.resolve(host, port, family)
        except OSError as dns_exc:
            # DefaultResolver raises OSError/gaierror on lookup failure. Convert to
            # the tool's ValueError contract here: TCPConnector only wraps OSError
            # (into ClientConnectorError), so this ValueError propagates unchanged
            # out of session.get()/head() and surfaces as url_not_allowed.
            raise ValueError(f"url_not_allowed: Host '{host}' could not be resolved.") from dns_exc

        if not results:
            raise ValueError(f"url_not_allowed: Host '{host}' doesn't resolve to an IP address.")

        # Every address must be global: the connector may connect to any of the
        # returned records (including fallback across them), so a single
        # non-global record makes the host unsafe.
        for entry in results:
            # Strip an IPv6 zone id (e.g. "fe80::1%eth0") so ip_address() can
            # parse the string; zoned addresses are link-local, so they are
            # rejected as non-global right after.
            ip_string: str = entry["host"].split("%", 1)[0]
            try:
                address: IPv4Address | IPv6Address = ip_address(ip_string)
            except ValueError as parse_exc:
                # Fail closed: an address we cannot parse is an address we
                # cannot vouch for.
                raise ValueError(
                    f"url_not_allowed: Host '{host}' resolved to unparseable address '{entry['host']}'."
                ) from parse_exc
            self.ensure_global_address(host, address)

        return results

    async def close(self) -> None:
        """Release resources held by the wrapped resolver."""
        await self._resolver.close()
