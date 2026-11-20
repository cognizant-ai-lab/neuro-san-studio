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

import asyncio
import json
import re
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool


class LogParser(CodedTool):
    """Extracts useful incident signals from sanitized application logs."""

    EXCEPTION_RE = re.compile(r"\b(?:[\w.]+)?(?:Exception|Error)\b")
    API_RE = re.compile(r"\bAPI\s+(/[A-Za-z0-9_./{}-]+)")
    HTTP_RE = re.compile(r"\bHTTP\s+([1-5][0-9]{2})\b")
    TIMEOUT_RE = re.compile(r"\b(\d{3,6}\s?ms)\b", re.IGNORECASE)
    SERVICE_RE = re.compile(r"\b(?:ERROR|WARN|INFO)\s+([A-Za-z][A-Za-z0-9_-]*(?:Service|API|Worker|Job))\b")
    POOL_RE = re.compile(r"\b([A-Za-z]+Pool-[0-9]+)\b")

    def invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any] | str:
        log_text = str(args.get("log_text", "")).strip()
        if not log_text:
            return {"error": "log_text is required"}

        lines = [line.strip() for line in log_text.splitlines() if line.strip()]
        exceptions = sorted(set(self.EXCEPTION_RE.findall(log_text)))
        apis = sorted(set(self.API_RE.findall(log_text)))
        http_statuses = sorted(set(self.HTTP_RE.findall(log_text)))
        timeouts = sorted(set(match.replace(" ", "") for match in self.TIMEOUT_RE.findall(log_text)))
        services = sorted(set(self.SERVICE_RE.findall(log_text)))
        pools = sorted(set(self.POOL_RE.findall(log_text)))

        issue_type = self._classify(log_text)
        evidence = self._evidence(lines)

        return {
            "issue_type": issue_type,
            "services": services,
            "apis": apis,
            "exceptions": exceptions,
            "http_statuses": http_statuses,
            "timeouts": timeouts,
            "pools": pools,
            "evidence": evidence,
            "summary": self._summary(issue_type, services, apis, exceptions, http_statuses),
        }

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any] | str:
        return await asyncio.to_thread(self.invoke, args, sly_data)

    @staticmethod
    def _classify(log_text: str) -> str:
        text = log_text.lower()
        if "outofmemoryerror" in text or "java heap space" in text or "oomkilled" in text:
            return "memory_issue"
        if "sqltransientconnectionexception" in text or "hikaripool" in text:
            return "db_timeout"
        if "http 500" in text or "http 502" in text or "http 503" in text or "http 504" in text:
            return "api_failure"
        if "connection refused" in text or "read timed out" in text:
            return "api_failure"
        return "unknown"

    @staticmethod
    def _evidence(lines: list[str]) -> list[str]:
        keywords = (
            "error",
            "exception",
            "http ",
            "timeout",
            "timed out",
            "connection",
            "hikaripool",
            "outofmemory",
            "heap",
        )
        evidence = [line for line in lines if any(keyword in line.lower() for keyword in keywords)]
        return evidence[:8]

    @staticmethod
    def _summary(
        issue_type: str,
        services: list[str],
        apis: list[str],
        exceptions: list[str],
        http_statuses: list[str],
    ) -> str:
        service = services[0] if services else "the application"
        api = apis[0] if apis else "an impacted endpoint"
        exception = exceptions[0] if exceptions else "log errors"
        status = f"HTTP {http_statuses[0]}" if http_statuses else "an error response"

        if issue_type == "db_timeout":
            return f"{service} is showing database connection timeout symptoms for {api}, resulting in {status}."
        if issue_type == "api_failure":
            return f"{service} is showing API failure symptoms for {api}, resulting in {status}."
        if issue_type == "memory_issue":
            return f"{service} is showing memory issue symptoms around {exception}, resulting in {status}."
        return f"{service} has an unclassified issue around {exception}."

    @staticmethod
    def format_json(result: dict[str, Any]) -> str:
        return json.dumps(result, indent=2)
