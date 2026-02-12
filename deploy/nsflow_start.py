"""
Wrapper to start nsflow with a workaround for a bug in leaf_common.

leaf_common.security.vault.vault_login references hvac.VaultClient,
but the hvac package only provides hvac.Client. This monkey-patch
adds the missing alias so the import chain doesn't crash.

Bug: leaf_common/security/vault/vault_login.py line 27
  LazyVaultClient = ResolverUtil.create_type("hvac.VaultClient", ...)
  Should be: "hvac.Client"

Affected versions: neuro-san==0.6.26, nsflow==0.6.7, leaf_common (transitive)
This can be removed once leaf_common fixes the reference upstream.
"""
import os

import hvac

hvac.VaultClient = hvac.Client  # noqa: leaf_common expects VaultClient

import uvicorn  # noqa: E402 — must import after patching hvac

if __name__ == "__main__":
    host = os.environ.get("NSFLOW_HOST", "0.0.0.0")
    port = int(os.environ.get("NSFLOW_PORT", "4173"))
    uvicorn.run("nsflow.backend.main:app", host=host, port=port)
