# Multi-Agent Student Loan Assistant

⭐ If you like this sample, star it on GitHub!

![Student Loan Processing Demo](docs/assets/demo.gif)

## Overview

A **conversational AI assistant** for student loan processing that leverages multi-agent architecture to handle loan applications through natural conversation. Users can ask questions, upload documents, and receive automated loan decisions without navigating traditional web forms.

**Powered by [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/agent-framework-overview)**

**Key capabilities**:
- General Q&A about student loans
- PDF document upload (loan applications & bank statements)
- AI-powered data extraction with GPT-4o
- Automated validation and loan approval decisions
- Real-time streaming responses

## Prerequisites

**Required**:
- Azure CLI 2.80.0+ ([install](https://docs.microsoft.com/cli/azure/install-azure-cli))
- PowerShell 7+ (Windows) or Bash (Linux/macOS)
- Azure subscription with **Contributor** + **User Access Administrator** roles
- Azure OpenAI access ([request here](https://aka.ms/oai/access))

**For local development**:
- Python 3.11+
- Node.js 18+
- Docker (optional)

**Azure requirements**:
- Supported regions: `eastus`, `eastus2`, `westus`, `westus2`, `swedencentral`, `northcentralus`
- Sufficient quota for Container Apps (3), Container Registry (1), Storage (1), OpenAI (1)

**Windows users**: Set PowerShell execution policy:
```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
```

**Pre-deployment checklist**:
- [ ] `az login` completed
- [ ] Correct subscription selected: `az account show`
- [ ] Required RBAC roles assigned
- [ ] Azure OpenAI access approved

## 🚀 Quick Start

Run the deployment script:

```powershell
.\deploy-clean.ps1
```

**Deployment time**: ~15-20 minutes

The script provisions all resources and deploys 3 containerized services (backend API, frontend web app, MCP server) with managed identities and CORS configuration.

**Access your app**:
- Frontend: `https://<prefix>-frontend-web.azurecontainerapps.io`

**Troubleshooting**:
- Script blocked? Run: `Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force`
- OpenAI error? Try different region (e.g., `eastus`)
- Permissions issue? Request Contributor + User Access Administrator roles

## Features

- Multi-agent supervisor architecture with GPT-4o
- MCP tools for business logic ([FastMCP](https://gofastmcp.com/getting-started/welcome))
- React chat UI with PDF upload
- GPT-4o document extraction (structured outputs)
- 3-tier architecture: FastAPI backend, React frontend, MCP server
- Real-time streaming (SSE)
- Automated cross-document validation

## Architecture

![Architecture Diagram](docs/assets/architecture.png)

**3-Tier Multi-Agent System**:

**🔵 Backend (FastAPI + Agent Framework)**
- Orchestration Agent: Coordinates workflow, triages requests
- Document Scanner: Extracts data from PDFs using GPT-4o
- Validator Agent: Cross-document validation, completeness checks
- Decision Maker: Calls MCP tools for loan approval
- Chat Agent: General Q&A handler

**🟢 Frontend (React + Vite)**
- Real-time chat with streaming
- PDF upload (drag-and-drop)
- Workflow status tracking

**🟡 Business API (MCP Server)**
- DTI ratio calculation
- Credit profile evaluation
- Interest rate determination

**User Flow**: Ask questions → Upload documents → Validate data → Confirm → Get loan decision

## Resources

- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
- [Azure AI Foundry](https://learn.microsoft.com/azure/ai-foundry/what-is-azure-ai-foundry)
- [More Azure AI samples](https://aka.ms/aiapps)

**Get help**: [Azure AI Foundry Discord](https://aka.ms/foundry/discord) | [Developer Forum](https://aka.ms/foundry/forum)

## 📚 Documentation

- **[src/biz_api/loan_approval/README.md](./src/biz_api/loan_approval/README.md)**: MCP server documentation
- **[src/biz_api/loan_approval/DTI_IMPLEMENTATION.md](./src/biz_api/loan_approval/DTI_IMPLEMENTATION.md)**: DTI calculation logic
- **[src/frontend/README.md](./src/frontend/README.md)**: Frontend development guide

## 🤝 Contributing

This project welcomes contributions and suggestions. Most contributions require you to agree to a Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us the rights to use your contribution. For details, visit [https://cla.opensource.microsoft.com](https://cla.opensource.microsoft.com/).

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general). Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos are subject to those third-party's policies.