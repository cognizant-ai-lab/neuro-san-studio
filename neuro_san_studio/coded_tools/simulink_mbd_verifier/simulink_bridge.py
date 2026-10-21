import json
import logging
import os
import pathlib
import platform
import shutil
from typing import Any, Dict, List

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from neuro_san.interfaces.coded_tool import CodedTool

logger = logging.getLogger(__name__)


def _unwrap_exception(exc: BaseException) -> str:
    """Recursively extracts the real underlying error from Python 3.11+ TaskGroup ExceptionGroups."""
    if hasattr(exc, "exceptions") and exc.exceptions:
        sub_messages = [_unwrap_exception(sub) for sub in exc.exceptions]
        return " | ".join(sub_messages)
    return f"{type(exc).__name__}: {exc}"


def _resolve_matlab_mcp_bin() -> str:
    env_bin = os.environ.get("MATLAB_MCP_BIN", "").strip().strip('"').strip("'")
    if env_bin and os.path.isfile(env_bin):
        return env_bin

    default_win = (
        pathlib.Path.home()
        / ".matlab"
        / "agentic-toolkits"
        / "bin"
        / ("matlab-mcp-server.exe" if platform.system() == "Windows" else "matlab-mcp-server")
    )
    if default_win.is_file():
        return str(default_win)

    return env_bin or "matlab-mcp-server"


def _resolve_satk_tools_json() -> str:
    env_tools = os.environ.get("SATK_TOOLS_JSON", "").strip().strip('"').strip("'")
    if env_tools and os.path.isfile(env_tools):
        return env_tools

    default_tools = (
        pathlib.Path.home()
        / ".matlab"
        / "agentic-toolkits"
        / "simulink"
        / "tools"
        / "tools.json"
    )
    if default_tools.is_file():
        return str(default_tools)

    return env_tools


def _normalize_satk_args(
    tool_name: str, tool_args: Dict[str, Any], schema_props: Dict[str, Any]
) -> Dict[str, Any]:
    """Normalizes LLM tool arguments to match matlab-mcp-server's strict string-encoded JSON schemas."""
    normalized = dict(tool_args)

    # 1. Fix model / scope mix-ups on SATK model_* tools
    if "model" in schema_props:
        if "model" not in normalized and "model_name" in normalized:
            normalized["model"] = normalized.pop("model_name")
        elif "model" not in normalized and "scope" in normalized:
            scope_val = str(normalized["scope"])
            if scope_val != "root" and not scope_val.startswith(("blk_", "sf_")):
                normalized["model"] = scope_val
                normalized["scope"] = "root"

    if "scope" in schema_props and "scope" not in normalized:
        normalized["scope"] = "root"

    # 2. Provide sensible defaults for required SATK fields if omitted by 7B models
    if tool_name == "model_edit" and "layout_mode" not in normalized:
        normalized["layout_mode"] = "full"
    elif tool_name == "model_check" and "checks" not in normalized:
        normalized["checks"] = '["all"]'
    elif tool_name == "model_read" and "depth" not in normalized:
        normalized["depth"] = "1"
    elif tool_name == "model_overview" and "detail" not in normalized:
        normalized["detail"] = "full"

    # 3. Clean up operation objects inside model_edit before stringifying
    if tool_name == "model_edit" and isinstance(normalized.get("operations"), list):
        cleaned_ops = []
        for op in normalized["operations"]:
            if isinstance(op, dict):
                op_copy = dict(op)
                # Convert "Key:Val" string params into {"Key": "Val"} dict
                raw_params = op_copy.get("params")
                if isinstance(raw_params, str) and ":" in raw_params:
                    k, v = raw_params.split(":", 1)
                    op_copy["params"] = {k.strip(): v.strip()}
                # Map "Outport"/"Inport" to Simulink's built-in BlockType names if needed
                cleaned_ops.append(op_copy)
        normalized["operations"] = cleaned_ops

    # 4. Auto-stringify any list/dict/number when the MCP tool schema expects a string
    for key, val in list(normalized.items()):
        expected_type = schema_props.get(key, {}).get("type")
        if expected_type == "string" and not isinstance(val, str):
            normalized[key] = json.dumps(val, separators=(",", ":"))
        elif expected_type == "string" and isinstance(val, str):
            # Ensure single-line JSON string (strip newlines)
            normalized[key] = val.replace("\r", "").replace("\n", " ")

    if "project_path" in schema_props and "project_path" not in normalized:
        normalized["project_path"] = os.getcwd()

    return normalized


class LoadSimulinkSkill(CodedTool):
    """Loads the top matching MathWorks SKILL.md instructions."""

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        raw_topic = args.get("skill_topic")
        skill_query = raw_topic.strip().lower() if isinstance(raw_topic, str) else ""
        if not skill_query:
            skill_query = "building-simulink-models"

        satk_tools = _resolve_satk_tools_json()
        if satk_tools and os.path.isfile(satk_tools):
            toolkit_root = pathlib.Path(satk_tools).parent.parent
        else:
            toolkit_root = pathlib.Path.home() / ".matlab" / "agentic-toolkits" / "simulink"

        skills_dir = toolkit_root / "skills-catalog"
        if not skills_dir.exists():
            return {
                "status": "not_found",
                "checked_path": str(skills_dir),
                "message": "Set SATK_TOOLS_JSON to point to your simulink-agentic-toolkit/tools/tools.json file.",
            }

        query_tokens = [tok for tok in skill_query.replace("-", " ").split() if len(tok) > 2]
        scored_skills = []

        for skill_file in skills_dir.rglob("SKILL.md"):
            skill_folder = skill_file.parent
            skill_name = skill_folder.name.lower()

            if skill_query == skill_name:
                score = 1000
            elif skill_query in skill_name:
                score = 200
            else:
                score = sum(10 for tok in query_tokens if tok in skill_name)

            if score > 0:
                content = skill_file.read_text(encoding="utf-8", errors="ignore")
                scored_skills.append((
                    score,
                    {
                        "skill": skill_folder.name,
                        "skill_dir": str(skill_folder),
                        "instructions": content[:6000],
                    },
                ))

        scored_skills.sort(key=lambda item: item[0], reverse=True)
        top_skill = scored_skills[0][1] if scored_skills else None

        return {
            "status": "success",
            "requested_topic": skill_query,
            "loaded_skill": top_skill,
        }


class SimulinkMcpBridge(CodedTool):
    """Invokes any Simulink Agentic Toolkit MCP tool with automatic schema normalization."""

    async def _call_mcp_session(
        self, command: str, server_args: List[str], tool_name: str, tool_args: Dict[str, Any]
    ) -> Dict[str, Any]:
        server_params = StdioServerParameters(command=command, args=server_args)
        response_payload: Dict[str, Any] = {}

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_list = await session.list_tools()
                    available_tools = {
                        t.name: {
                            "description": t.description,
                            "inputSchema": getattr(t, "inputSchema", {}),
                        }
                        for t in tools_list.tools
                    }

                    if tool_name == "list_available_tools":
                        response_payload = {
                            "mode": "live_satk_mcp",
                            "status": "success",
                            "available_mcp_tools": available_tools,
                        }
                        return response_payload

                    if tool_name not in available_tools:
                        response_payload = {
                            "status": "error",
                            "message": f"Tool '{tool_name}' not found. Available tools: {list(available_tools.keys())}",
                        }
                        return response_payload

                    schema_props = (
                        available_tools[tool_name].get("inputSchema", {}).get("properties", {})
                    )
                    normalized_args = _normalize_satk_args(tool_name, tool_args, schema_props)

                    result = await session.call_tool(tool_name, arguments=normalized_args)
                    raw_output = "\n".join(
                        getattr(block, "text", str(block)) for block in result.content
                    )
                    is_err = getattr(result, "isError", False)
                    response_payload = {
                        "mode": "live_satk_mcp",
                        "tool_called": tool_name,
                        "arguments_sent": normalized_args,
                        "status": "error" if is_err else "success",
                        "raw_output": raw_output,
                        "summary": raw_output[:2500],
                    }
                    return response_payload
        except BaseException as exc:
            if response_payload:
                return response_payload
            unwrapped = _unwrap_exception(exc)
            logger.error("MCP session error: %s", unwrapped)
            return {
                "status": "error",
                "tool_called": tool_name,
                "arguments_sent": tool_args,
                "error_details": unwrapped,
            }

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        raw_tool_args = args.get("tool_arguments")
        if raw_tool_args is None:
            tool_args: Dict[str, Any] = {}
        elif isinstance(raw_tool_args, str):
            try:
                tool_args = json.loads(raw_tool_args) if raw_tool_args.strip() else {}
            except json.JSONDecodeError:
                tool_args = {"code": raw_tool_args, "project_path": os.getcwd()}
        elif isinstance(raw_tool_args, dict):
            tool_args = dict(raw_tool_args)
        else:
            tool_args = {}

        raw_tool_name = args.get("tool_name") or tool_args.pop("tool_name", None)
        if isinstance(raw_tool_name, str) and raw_tool_name.strip():
            tool_name = raw_tool_name.strip()
        elif "code" in tool_args:
            tool_name = "evaluate_matlab_code"
        elif "operations" in tool_args:
            tool_name = "model_edit"
        else:
            tool_name = "list_available_tools"

        mcp_bin = _resolve_matlab_mcp_bin()
        satk_tools = _resolve_satk_tools_json()
        mock_mode = os.environ.get("SIMULINK_MOCK_MODE", "false").lower() == "true"

        if mock_mode or (not os.path.isfile(mcp_bin) and not shutil.which(mcp_bin)):
            mock_telemetry = {
                "tool_called": tool_name,
                "arguments": tool_args,
                "diagnostics": "0 Errors, 0 Warnings (Mock Mode).",
            }
            sly_data["last_simulink_telemetry"] = mock_telemetry
            return {"mode": "mock_dry_run", "status": "success", "result": mock_telemetry}

        server_args = ["--matlab-session-mode=existing", "--disable-telemetry=true"]
        if satk_tools and os.path.isfile(satk_tools):
            server_args.append(f"--extension-file={satk_tools}")

        response = await self._call_mcp_session(mcp_bin, server_args, tool_name, tool_args)
        sly_data["last_simulink_telemetry"] = response.get("raw_output", response)
        return response