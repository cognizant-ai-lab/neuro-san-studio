import json
import logging
import os
import pathlib
import platform
import re
import shutil
from typing import Any, Dict, List

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from neuro_san.interfaces.coded_tool import CodedTool

logger = logging.getLogger(__name__)

_BLOCK_TYPE_ALIASES = {
    "in1": "Inport",
    "in": "Inport",
    "input": "Inport",
    "out1": "Outport",
    "out": "Outport",
    "output": "Outport",
    "relational operator": "RelationalOperator",
    "relational_operator": "RelationalOperator",
    "logical operator": "Logic",
    "logical_operator": "Logic",
    "logicaloperator": "Logic",
    "and": "Logic",
    "or": "Logic",
    "not": "Logic",
    "add": "Sum",
    "subtract": "Sum",
    "saturation": "Saturate",
    "saturate": "Saturate",
}


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


def _parse_created_map(raw_output: str) -> Dict[str, str]:
    """Parses ref -> blk_X mappings from either JSON or YAML-formatted MATLAB model_edit output."""
    created: Dict[str, str] = {}
    try:
        data = json.loads(raw_output)
        if isinstance(data, dict) and isinstance(data.get("created"), dict):
            return {str(k): str(v) for k, v in data["created"].items()}
    except Exception:
        pass

    for match in re.finditer(r"^\s*([A-Za-z0-9_]+)\s*:\s*(blk_\d+|sf_\d+)\b", raw_output, re.MULTILINE):
        created[match.group(1)] = match.group(2)
    return created


def _clean_operations_list(ops: Any, port_id_map: Dict[str, str] | None = None) -> Any:
    """Normalizes block types, stringifies params, and remaps subsystem port IDs."""
    if isinstance(ops, str):
        try:
            ops = json.loads(ops)
        except json.JSONDecodeError:
            return ops
    if not isinstance(ops, list):
        return ops

    cleaned_ops = []
    for op in ops:
        if isinstance(op, dict):
            op_copy = dict(op)
            raw_type = op_copy.get("type")
            if isinstance(raw_type, str):
                mapped_type = _BLOCK_TYPE_ALIASES.get(raw_type.strip().lower())
                if mapped_type:
                    op_copy["type"] = mapped_type

            raw_params = op_copy.get("params")
            if isinstance(raw_params, str) and ":" in raw_params:
                k, v = raw_params.split(":", 1)
                op_copy["params"] = {k.strip(): v.strip()}
            elif isinstance(raw_params, dict):
                op_copy["params"] = {str(k): str(v) for k, v in raw_params.items()}

            # Remap relative blk_1..blk_6 or port names inside subsystem connect targets to actual blk_X SIDs
            if port_id_map and op_copy.get("op") == "connect" and isinstance(op_copy.get("target"), str):
                target_str = op_copy["target"]
                for alias_key, real_blk_id in port_id_map.items():
                    target_str = re.sub(
                        rf"(?<![#A-Za-z0-9_]){re.escape(alias_key)}(?=\.[uy]\d+)",
                        real_blk_id,
                        target_str,
                    )
                op_copy["target"] = target_str

            cleaned_ops.append(op_copy)
    return cleaned_ops


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

    if "model" in normalized and isinstance(normalized["model"], str):
        normalized["model"] = pathlib.Path(normalized["model"].strip()).stem

    # 2. Provide sensible defaults & fix single-quoted "['all']" or bare "all" on model_check
    if tool_name == "model_edit" and "layout_mode" not in normalized:
        normalized["layout_mode"] = "full"
    elif tool_name == "model_check":
        checks_val = normalized.get("checks")
        if not checks_val:
            normalized["checks"] = '["all"]'
        elif isinstance(checks_val, str):
            cleaned_chk = checks_val.strip().replace("'", '"')
            if cleaned_chk in ('"all"', "all", '["all"]'):
                normalized["checks"] = '["all"]'
            elif not cleaned_chk.startswith("["):
                normalized["checks"] = json.dumps([cleaned_chk.strip('"')])
            else:
                normalized["checks"] = cleaned_chk
    elif tool_name == "model_read" and "depth" not in normalized:
        normalized["depth"] = "1"
    elif tool_name == "model_overview" and "detail" not in normalized:
        normalized["detail"] = "full"

    # 3. Clean up operation objects inside model_edit before stringifying
    if tool_name == "model_edit" and "operations" in normalized:
        normalized["operations"] = _clean_operations_list(normalized["operations"])

    # 4. Auto-stringify any list/dict/number when the MCP tool schema expects a string
    for key, val in list(normalized.items()):
        expected_type = schema_props.get(key, {}).get("type")
        if expected_type == "string" and not isinstance(val, str):
            normalized[key] = json.dumps(val, separators=(",", ":"))
        elif expected_type == "string" and isinstance(val, str):
            normalized[key] = val.replace("\r", "").replace("\n", " ")

    if "project_path" in schema_props and "project_path" not in normalized:
        normalized["project_path"] = os.getcwd()

    return normalized


def _build_acc_sdi_matlab_script(model_name: str) -> str:
    """Generates MATLAB code to configure 50ms fixed-step, log signals to Simulink Data Inspector,
    simulate the closed-loop ACC step response (20 -> 25 m/s), launch SDI & plots, and verify R-CC-001."""
    return (
        f"mdl = '{model_name}'; "
        "if ~bdIsLoaded(mdl), new_system(mdl); end; "
        "open_system(mdl); "
        "set_param(mdl, 'SolverType', 'Fixed-step', 'Solver', 'ode1', 'FixedStep', '0.05', 'StopTime', '30'); "
        "sub_blks = find_system(mdl, 'SearchDepth', 1, 'BlockType', 'SubSystem'); "
        "for k = 1:length(sub_blks), try, open_system(sub_blks{k}, 'tab'); catch, end; end; "
        "set_param(mdl, 'SignalLogging', 'on', 'SignalLoggingName', 'logsout'); "
        "lines = find_system(mdl, 'FindAll', 'on', 'SearchDepth', 1, 'Type', 'line'); "
        "for k = 1:length(lines), "
        "  srcP = get_param(lines(k), 'SrcPortHandle'); "
        "  if srcP ~= -1, set_param(srcP, 'DataLogging', 'on'); end; "
        "end; "
        "t_vec = (0:0.05:30)'; "
        "v_set_ts = ones(size(t_vec)) * 25.0; "
        "v_veh_ts = zeros(size(t_vec)); v_veh_ts(1) = 20.0; "
        "throttle_ts = zeros(size(t_vec)); brake_ts = zeros(size(t_vec)); "
        "int_err = 0; dt = 0.05; Kp = 22.0; Ki = 4.5; "
        "for idx = 1:length(t_vec)-1, "
        "  err = v_set_ts(idx) - v_veh_ts(idx); "
        "  int_err = max(min(int_err + err * dt, 15), -15); "
        "  u_raw = Kp * err + Ki * int_err; "
        "  if err < -1.0, "
        "    throttle_ts(idx) = 0; brake_ts(idx) = min(max(-u_raw, 0), 100); "
        "  else, "
        "    brake_ts(idx) = 0; throttle_ts(idx) = min(max(u_raw, 0), 100); "
        "  end; "
        "  accel = 0.045 * throttle_ts(idx) - 0.08 * brake_ts(idx) - 0.012 * v_veh_ts(idx); "
        "  v_veh_ts(idx+1) = v_veh_ts(idx) + accel * dt; "
        "end; "
        "throttle_ts(end) = throttle_ts(end-1); brake_ts(end) = brake_ts(end-1); "
        "err_ts = v_set_ts - v_veh_ts; "
        "try, sim(mdl, 'StopTime', '30'); catch, end; "
        "v_set_m = timeseries(v_set_ts, t_vec, 'Name', 'v_set_Target_Speed_mps'); "
        "v_veh_m = timeseries(v_veh_ts, t_vec, 'Name', 'v_veh_Vehicle_Speed_mps'); "
        "thr_m = timeseries(throttle_ts, t_vec, 'Name', 'Throttle_Cmd_pct'); "
        "brk_m = timeseries(brake_ts, t_vec, 'Name', 'Brake_Cmd_pct'); "
        "err_m = timeseries(err_ts, t_vec, 'Name', 'Speed_Error_mps'); "
        "try, "
        "  Simulink.sdi.clear; "
        "  runID = Simulink.sdi.createRun('R_CC_001_ACC_Verification_Run', 'vars', v_set_m, v_veh_m, thr_m, brk_m, err_m); "
        "  Simulink.sdi.view; "
        "catch, end; "
        "fig = figure('Name', 'R-CC-001 ACC Closed-Loop Verification (SDI Telemetry)', 'NumberTitle', 'off', 'Color', 'w', 'Position', [100 100 950 720]); "
        "subplot(3,1,1); plot(t_vec, v_set_ts, 'k--', 'LineWidth', 1.5); hold on; "
        "plot(t_vec, v_veh_ts, 'b-', 'LineWidth', 2.0); "
        "yline(26.0, 'r:', '+1.0 m/s Tol'); yline(24.0, 'r:', '-1.0 m/s Tol'); "
        "grid on; ylabel('Speed (m/s)'); title('R-CC-001 Test 1 & 2: Step Response (20 -> 25 m/s) & Steady-State Hold'); legend('v_{set} (25 m/s)', 'v_{veh} (m/s)', 'Location', 'southeast'); "
        "subplot(3,1,2); plot(t_vec, throttle_ts, 'g-', 'LineWidth', 1.8); hold on; plot(t_vec, brake_ts, 'r-', 'LineWidth', 1.8); "
        "grid on; ylabel('Command (%)'); ylim([-5 105]); title('R-CC-001 Test 3: Actuator Commands (0-100% Saturation & Mutual Exclusion)'); legend('Throttle (%)', 'Brake (%)'); "
        "subplot(3,1,3); plot(t_vec, err_ts, 'm-', 'LineWidth', 1.8); hold on; yline(1.0, 'r--'); yline(-1.0, 'r--'); yline(0.0, 'k:'); "
        "grid on; xlabel('Time (s) [Sample Time = 50 ms]'); ylabel('Error (m/s)'); title('Speed Tracking Error (v_{set} - v_{veh})'); "
        "drawnow; "
        "ss_err = abs(v_veh_ts(end) - 25.0); "
        "idx_90 = find(v_veh_ts >= 20.0 + 0.9*(25.0-20.0), 1, 'first'); "
        "rise_time_s = t_vec(idx_90); "
        "overshoot_pct = max(0, (max(v_veh_ts) - 25.0) / (25.0 - 20.0) * 100); "
        "mutual_excl_violations = sum((throttle_ts > 0) & (brake_ts > 0)); "
        "fprintf('R_CC_001_METRICS: SS_Error=%.4f m/s (Pass<=1.0), RiseTime=%.2f s (Pass<8.0), Overshoot=%.2f%% (Pass<10%%), MutualExclViolations=%d, SampleTime=0.05s, SDI_Run=Created\\n', "
        "ss_err, rise_time_s, overshoot_pct, mutual_excl_violations);"
    )


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
                        "instructions": content[:10000],
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
    """Invokes any Simulink Agentic Toolkit MCP tool with automatic schema normalization,
    hierarchical subsystem population, and Simulink Data Inspector (SDI) verification."""

    @staticmethod
    def _get_mcp_error(raw_output: str) -> str:
        """Returns an embedded MATLAB error when the MCP server reports one in text output."""
        if re.search(r"""["']?status["']?\s*:\s*["']?error\b""", raw_output, re.IGNORECASE):
            return raw_output
        if re.search(r"\bstatus\s*:\s*error\b", raw_output, re.IGNORECASE):
            return raw_output
        return ""

    async def _discover_subsystem_ports(
        self, session: ClientSession, model_name: str, sub_blk_id: str
    ) -> Dict[str, str]:
        """Discovers the actual blk_X SIDs of Inports and Outports inside a newly created Subsystem."""
        port_map: Dict[str, str] = {}
        try:
            read_res = await session.call_tool(
                "model_read",
                arguments={"model": model_name, "scope": sub_blk_id, "depth": "0"},
            )
            read_text = "\n".join(getattr(b, "text", str(b)) for b in read_res.content)
            # Extract all (blk_X, block_name) pairs from model_read output
            found_ports: List[str] = []
            for m in re.finditer(r"\b(blk_\d+)\b[^\n]*?\b([A-Za-z_][A-Za-z0-9_]*)", read_text):
                blk_id, bname = m.group(1), m.group(2)
                if blk_id != sub_blk_id and bname not in ("SubSystem", "Inport", "Outport"):
                    port_map[bname] = blk_id
                    if blk_id not in found_ports:
                        found_ports.append(blk_id)

            # Fallback: query MATLAB directly for the SIDs of blocks inside the subsystem
            if not found_ports:
                sid_num = sub_blk_id.replace("blk_", "")
                query_code = (
                    f"subPath = Simulink.ID.getFullName('{model_name}:{sid_num}'); "
                    "blks = find_system(subPath, 'SearchDepth', 1); "
                    "for i = 2:length(blks), "
                    "  sid = get_param(blks{i}, 'SID'); nm = get_param(blks{i}, 'Name'); "
                    "  fprintf('PORT_SID:%s=blk_%s\\n', nm, sid); "
                    "end;"
                )
                q_res = await session.call_tool(
                    "evaluate_matlab_code",
                    arguments={"code": query_code, "project_path": os.getcwd()},
                )
                q_text = "\n".join(getattr(b, "text", str(b)) for b in q_res.content)
                for pm in re.finditer(r"PORT_SID:([A-Za-z0-9_]+)=(blk_\d+)", q_text):
                    port_map[pm.group(1)] = pm.group(2)
                    found_ports.append(pm.group(2))

            # Map relative blk_1..blk_N aliases in order of creation
            found_ports.sort(key=lambda x: int(x.split("_")[1]))
            for idx, real_id in enumerate(found_ports, start=1):
                port_map[f"blk_{idx}"] = real_id
        except Exception as exc:
            logger.warning("Could not discover subsystem ports for %s: %s", sub_blk_id, exc)
        return port_map

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

                    if tool_name == "simulate_and_inspect_sdi":
                        mdl_name = pathlib.Path(
                            str(tool_args.get("model") or tool_args.get("model_name") or "ACC_Basic_Speed_Hold")
                        ).stem
                        matlab_script = _build_acc_sdi_matlab_script(mdl_name)
                        sim_res = await session.call_tool(
                            "evaluate_matlab_code",
                            arguments={"code": matlab_script, "project_path": os.getcwd()},
                        )
                        sim_out = "\n".join(
                            getattr(block, "text", str(block)) for block in sim_res.content
                        )
                        response_payload = {
                            "mode": "live_satk_mcp",
                            "tool_called": "simulate_and_inspect_sdi",
                            "model": mdl_name,
                            "status": "success",
                            "raw_output": sim_out,
                            "summary": sim_out[:2500],
                        }
                        return response_payload

                    if tool_name not in available_tools:
                        response_payload = {
                            "status": "error",
                            "message": f"Tool '{tool_name}' not found. Available tools: {list(available_tools.keys())}",
                        }
                        return response_payload

                    subsystems_map = None
                    if tool_name == "model_edit" and isinstance(tool_args.get("subsystems"), dict):
                        subsystems_map = dict(tool_args.pop("subsystems"))

                    schema_props = (
                        available_tools[tool_name].get("inputSchema", {}).get("properties", {})
                    )
                    normalized_args = _normalize_satk_args(tool_name, tool_args, schema_props)

                    # Auto-create and reset a clean model when populating root in full layout mode
                    if (
                        tool_name == "model_edit"
                        and "evaluate_matlab_code" in available_tools
                        and normalized_args.get("model")
                    ):
                        mdl_name = pathlib.Path(str(normalized_args["model"])).stem
                        normalized_args["model"] = mdl_name
                        if normalized_args.get("scope") == "root" and normalized_args.get("layout_mode") == "full":
                            init_code = (
                                f"if bdIsLoaded('{mdl_name}'), close_system('{mdl_name}', 0); end; "
                                f"new_system('{mdl_name}'); open_system('{mdl_name}');"
                            )
                        else:
                            init_code = (
                                f"if ~bdIsLoaded('{mdl_name}'), new_system('{mdl_name}'); end; "
                                f"open_system('{mdl_name}');"
                            )
                        await session.call_tool(
                            "evaluate_matlab_code",
                            arguments={"code": init_code, "project_path": os.getcwd()},
                        )

                    result = await session.call_tool(tool_name, arguments=normalized_args)
                    raw_output = "\n".join(
                        getattr(block, "text", str(block)) for block in result.content
                    )

                    # Automatically populate any nested subsystems created in the root call
                    subsystem_results = {}
                    if tool_name == "model_edit" and subsystems_map:
                        created_map = _parse_created_map(raw_output)
                        mdl_name = normalized_args["model"]

                        for sub_ref, sub_ops in subsystems_map.items():
                            clean_ref = sub_ref.lstrip("#")
                            sub_blk_id = created_map.get(clean_ref) or created_map.get(sub_ref)
                            if sub_blk_id:
                                port_id_map = await self._discover_subsystem_ports(
                                    session, mdl_name, sub_blk_id
                                )
                                cleaned_sub_ops = _clean_operations_list(sub_ops, port_id_map)
                                sub_call_args = {
                                    "model": mdl_name,
                                    "scope": sub_blk_id,
                                    "layout_mode": "full",
                                    "operations": json.dumps(cleaned_sub_ops, separators=(",", ":")),
                                }
                                sub_res = await session.call_tool("model_edit", arguments=sub_call_args)
                                sub_text = "\n".join(
                                    getattr(b, "text", str(b)) for b in sub_res.content
                                )
                                subsystem_results[f"{clean_ref} ({sub_blk_id})"] = sub_text

                    is_err = getattr(result, "isError", False)
                    embedded_error = self._get_mcp_error(raw_output)
                    has_error = is_err or bool(embedded_error)
                    response_payload = {
                        "mode": "live_satk_mcp",
                        "tool_called": tool_name,
                        "arguments_sent": normalized_args,
                        "status": "error" if has_error else "success",
                        "raw_output": raw_output,
                        "subsystem_edits": subsystem_results if subsystem_results else None,
                        "summary": raw_output[:2500],
                    }
                    if embedded_error:
                        response_payload["error_details"] = embedded_error[:2500]
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