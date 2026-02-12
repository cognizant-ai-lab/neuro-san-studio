# Repo Memory — neuro-san-studio

Track workarounds, upstream bugs, and things to revisit when dependencies are updated.

---

## Active Workarounds

### 1. hvac.VaultClient monkey-patch (deploy/nsflow_start.py)

**Added:** 2026-02-12
**Affected versions:** neuro-san==0.6.26, nsflow==0.6.7, leaf_common (transitive)
**File:** `deploy/nsflow_start.py`

**Problem:** `leaf_common.security.vault.vault_login` (line 27) references `hvac.VaultClient`, but the `hvac` package has only ever provided `hvac.Client`. There was never a `VaultClient` class in any version of `hvac`. This causes an `AttributeError` at import time, crashing nsflow on startup.

**Error:**
```
File "leaf_common/security/vault/vault_login.py", line 27, in <module>
    LazyVaultClient = ResolverUtil.create_type("hvac.VaultClient", install_if_missing="hvac")
AttributeError: module 'hvac' has no attribute 'VaultClient'
```

**Import chain:** nsflow → leaf_common.security.service.vault_dynamic_token_service_accessor → leaf_common.security.vault.vault_login → hvac (crash)

**Workaround:** `deploy/nsflow_start.py` patches `hvac.VaultClient = hvac.Client` before importing nsflow/uvicorn. The entrypoint.sh uses this wrapper instead of calling uvicorn directly.

**When to remove:** Check if a newer version of `neuro-san`, `nsflow`, or `leaf_common` fixes the `hvac.VaultClient` reference. If the upstream fix changes it to `hvac.Client`, the wrapper can be replaced with a direct uvicorn call in `entrypoint.sh`. To revert:
1. In `deploy/entrypoint.sh`, change the nsflow start line back to:
   ```bash
   ${PYTHON} -u -m uvicorn nsflow.backend.main:app --host "${NSFLOW_HOST}" --port "${NSFLOW_PORT}" &
   ```
2. Delete `deploy/nsflow_start.py`
3. Remove the `COPY` line for `nsflow_start.py` from `Dockerfile`

---

## Deployment Notes

### Azure Container Apps startup behavior

**Learned:** 2026-02-12

- Azure Container Apps startup probes check the ingress target port **immediately** (every ~1 second).
- If the target port isn't listening within the probe failure threshold, Azure kills the container.
- Both services (neuro-san server + nsflow) must start **in parallel**, not sequentially.
- nsflow/uvicorn binds to its port within seconds, which satisfies the startup probe.
- Agent functionality becomes available once the neuro-san server finishes initializing (may take 10-30s).

### Entrypoint bash safety

**Learned:** 2026-02-12

- Do NOT use `set -u` (nounset) in `deploy/entrypoint.sh` — Docker starts the container with no arguments, so `$1` is unset and causes immediate exit.
- Use `set -eo pipefail` (without `-u`) for safety without breaking on unset positional parameters.

---

## Config Editor (HOCON Management UI)

**Added:** 2026-02-12

### Architecture
- `config_editor/` — FastAPI app with REST API + Jinja2/CodeMirror web UI
- Runs on port **4174** (separate from nsflow on 4173)
- `deploy/config_editor_start.py` — uvicorn launcher (mirrors nsflow_start.py)
- `deploy/entrypoint.sh` — manages 3 processes: neuro-san, nsflow, config editor

### Azure File Share Integration
- Registries baked into image at `registries-seed/` (Dockerfile)
- Azure File Share mounted at `registries/` (the live config path)
- `entrypoint.sh` seeds the file share from `registries-seed/` on first boot (empty share)
- `AGENT_MANIFEST_UPDATE_PERIOD_SECONDS=30` enables live reload

### Authentication
- Entra ID MFA configured on port 4174 ingress (Cognizant tenant only)
- Azure File Share RBAC for admin access via Azure Portal/Storage Explorer

### Dependencies
- `pyhocon>=0.3.60` (latest is 0.3.x — there is NO 1.x release)
- `jinja2>=3.1.0` (may be transitively available but explicitly declared)

### Environment Variables
| Variable | Default | Purpose |
|----------|---------|---------|
| `CONFIG_EDITOR_ENABLED` | `true` | Enable/disable config editor process |
| `CONFIG_EDITOR_HOST` | `0.0.0.0` | Bind host |
| `CONFIG_EDITOR_PORT` | `4174` | Bind port |
| `CONFIG_EDITOR_REGISTRIES_PATH` | `${APP_SOURCE}/registries` | Path to registries directory |

---

## Version History

| Date | neuro-san | nsflow | Notes |
|------|-----------|--------|-------|
| 2026-02-12 | 0.6.26 | 0.6.7 | hvac workaround needed, dual-process container |
