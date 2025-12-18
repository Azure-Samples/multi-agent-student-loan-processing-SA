# Deployment Fixes Applied

This document summarizes all fixes applied to enable successful one-click deployment with Azure managed identity authentication.

## Changes Made

### 1. **Azure OpenAI Resource Configuration**
**File**: `deploy-clean.ps1` (line ~175)

**Issue**: Original deployment created Azure OpenAI without custom subdomain, which is required for Entra ID (managed identity) authentication.

**Fix**: Added `--custom-domain` parameter to create Azure OpenAI with resource-specific endpoint.

```powershell
# Before
az cognitiveservices account create --name $OPENAI_RESOURCE --kind OpenAI --sku S0

# After
az cognitiveservices account create --name $OPENAI_RESOURCE --kind OpenAI --sku S0 --custom-domain $OPENAI_RESOURCE
```

**Result**: Azure OpenAI endpoint changes from regional `https://westus.api.cognitive.microsoft.com/` to resource-specific `https://<resource-name>.openai.azure.com/`, which supports token-based authentication.

---

### 2. **Backend Managed Identity Configuration**
**File**: `src/backend/app/config/azure_credential.py`

**Issue**: Code was passing `client_id="system-managed-identity"` string literal to `ManagedIdentityCredential()`, causing authentication failures.

**Fix**: Only pass `client_id` parameter when using user-assigned managed identity, not for system-assigned.

```python
# Before
return AioManagedIdentityCredential(client_id=settings.AZURE_CLIENT_ID)

# After
if settings.AZURE_CLIENT_ID and settings.AZURE_CLIENT_ID != "system-managed-identity":
    return AioManagedIdentityCredential(client_id=settings.AZURE_CLIENT_ID)
else:
    return AioManagedIdentityCredential()
```

**Result**: Managed identity authenticates correctly using system-assigned identity.

---

### 3. **Removed API Key Authentication**
**File**: `deploy-clean.ps1` (line ~300)

**Issue**: Backend was configured with AZURE_OPENAI_KEY secret, but subscription policy blocks key-based authentication.

**Fix**: Removed API key from secrets and environment variables, relying entirely on managed identity.

```powershell
# Before
--secrets "azure-openai-key=$AZURE_OPENAI_KEY" `
--env-vars "AZURE_OPENAI_KEY=secretref:azure-openai-key" ...

# After
# No secrets, no AZURE_OPENAI_KEY environment variable
--env-vars "PROFILE=prod" "AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT" ...
```

**Result**: Backend uses managed identity exclusively for Azure OpenAI authentication.

---

### 4. **MCP Server Port Configuration**
**File**: `deploy-clean.ps1` (line ~275)

**Issue**: MCP server ingress configured for port 8070, but application runs on port 8080 in production mode.

**Fix**: Changed target port from 8070 to 8080.

```powershell
# Before
--target-port 8070 `

# After
--target-port 8080 `
```

**Result**: Backend can successfully connect to MCP server on correct port.

---

### 5. **MCP Server Dependencies**
**Files**: 
- `src/biz_api/loan_approval/pyproject.toml`
- `src/biz_api/loan_approval/Dockerfile`

**Issue**: `fastmcp` package depends on `httpx-sse` which has version conflicts with default `httpx` installation, causing `AttributeError: module 'httpx' has no attribute 'TransportError'`.

**Fix**: Pinned compatible versions and added `--upgrade` flag to Docker build.

```toml
# pyproject.toml
dependencies = [
    "fastmcp",
    "pydantic",
    "httpx==0.28.1",
    "httpx-sse==0.4.0"
]
```

```dockerfile
# Dockerfile
RUN uv venv && \
    . .venv/bin/activate && \
    uv pip install -e . --prerelease=allow --upgrade
```

**Result**: MCP server starts successfully without import errors.

---

## Deployment Flow

The updated `deploy-clean.ps1` now follows this flow:

1. **Create Azure OpenAI** with custom subdomain → Enables managed identity
2. **Deploy MCP Server** on port 8080 → Ensures connectivity
3. **Deploy Backend** with system-assigned managed identity → No API keys
4. **Assign RBAC roles** to backend identity:
   - Storage Blob Data Contributor (for Azure Blob Storage)
   - Cognitive Services OpenAI User (for Azure OpenAI)
5. **Deploy Frontend** with backend API URL

## Testing

After deployment completes:

1. Navigate to the frontend URL: `https://frontend-web.<environment>.azurecontainerapps.io`
2. Send a message like "hello" or "I want to apply for a loan"
3. The system should respond using GPT-4o via managed identity

## Architecture

```
┌─────────────┐         ┌──────────────┐         ┌─────────────────┐
│  Frontend   │────────>│  Backend API │────────>│  Azure OpenAI   │
│  (Nginx)    │         │  (FastAPI)   │         │  (GPT-4o)       │
└─────────────┘         └──────────────┘         └─────────────────┘
                               │                          ▲
                               │                          │
                               │                  Managed Identity
                               │                    (Token Auth)
                               │
                               ▼
                        ┌─────────────┐
                        │ MCP Server  │
                        │ (FastMCP)   │
                        └─────────────┘
```

## Notes

- All authentication uses **Managed Identity** (no keys stored)
- MCP server is **internal** (not exposed to internet)
- Backend has **system-assigned** managed identity
- Storage account uses **Entra ID authentication only**
- CORS is configured to allow frontend-backend communication

## Troubleshooting

If deployment fails:

1. **Check Azure OpenAI has custom domain**:
   ```powershell
   az cognitiveservices account show -n <openai-name> -g <rg> --query properties.customSubDomainName
   ```

2. **Verify MCP server is running on port 8080**:
   ```powershell
   az containerapp logs show -n mcp-server -g <rg> --tail 50
   ```

3. **Confirm backend managed identity has RBAC roles**:
   ```powershell
   az role assignment list --assignee <backend-identity-id> --all
   ```

4. **Test backend connectivity to MCP server**:
   ```powershell
   az containerapp logs show -n backend-api -g <rg> --tail 100
   ```
