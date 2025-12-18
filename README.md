# Multi-Agent Student Loan Assistant with Python and Microsoft Agent Framework

⭐ If you like this sample, star it on GitHub — it helps a lot!

[Overview](#overview) • [Architecture](#architecture) • [Getting Started](#getting-started) • [Resources](#resources)

![Student Loan Processing Demo](docs/assets/demo.gif)

## Overview

The core use case of this application revolves around a **student loan processing assistant** designed to revolutionize the way students interact with loan applications. Utilizing the power of generative AI within a multi-agent architecture, this assistant aims to provide a seamless, conversational interface through which users can effortlessly inquire about student loans, prepare their applications, and receive automated loan decisions.

Instead of navigating through traditional web forms and submission processes, users can simply **converse with the AI-powered assistant** to:
- Ask general questions about student loan requirements and eligibility
- Get guidance on required documentation
- Upload loan application and bank statement documents
- Review extracted data and validation results
- Receive automated loan approval decisions based on financial analysis

The assistant leverages existing document processing APIs and business rules to ensure a reliable and secure service. Student loan applications and bank statements are processed using Azure OpenAI GPT-4o for data extraction. All business logic for loan approval (DTI calculation, credit evaluation) is exposed as external REST APIs and MCP tools consumed by the agents to provide the user with loan decisions.

This sample is powered by:

**[Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/agent-framework-overview)** - A Python framework for building multi-agent AI applications

## Features

This project provides the following features and technical patterns:

- **Multi-agent supervisor architecture** using GPT-4o on Azure AI Foundry
- **Exposing business APIs as MCP tools** for agents using [FastMCP](https://gofastmcp.com/getting-started/welcome)
- **Agent tools configuration** and automatic tools invocations with [Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/agent-framework-overview)
- **Chat-based conversation** implemented as React Single Page Application with support for PDF document upload (loan applications and bank statements)
- **Document scanning and data extraction** with Azure OpenAI GPT-4o using structured outputs (Pydantic models)
- **Three-tier architecture** with FastAPI backend, React frontend, and separate business logic tier (MCP server)
- **Real-time streaming** responses with FastAPI Server-Sent Events (SSE)
- **Automated validation** with cross-document verification and completeness checks
- **State management** for tracking loan application workflow progress

## Architecture

![Architecture Diagram](docs/assets/architecture.png)

The student loan processing assistant is designed as a **conversational multi-agent system** with each agent specializing in a specific functional domain (e.g., document extraction, validation, loan approval). The architecture consists of the following key components:

### Components

**🔵 Copilot Assistant (FastAPI Microservice)**

Serves as the central hub for processing user chat requests. It's a [FastAPI](https://fastapi.tiangolo.com/) app which uses Agent Framework to create specialized agents equipped with tools and orchestrates them using a custom workflow pattern.

- **Orchestration Agent**: Responsible for coordinating the entire loan application workflow. It triages user requests (general questions, document upload, confirmation), delegates tasks to specialized agents, and manages the conversation flow. This component ensures that user queries are efficiently handled by the relevant agent or executor. The orchestrator engages agents in a multi-turn conversation, collecting user feedback when data verification or action approval (like proceeding with loan decision) is required.

- **Intent Classifier Executor**: Detects user intent from chat messages (general_chat, document_upload, confirm_validation, proceed_to_decision) to route the conversation appropriately.

- **Document Scanner Service**: Specializes in extracting structured data from uploaded PDF documents (student loan applications and bank statements). It leverages Azure OpenAI GPT-4o with structured outputs (Pydantic models) to accurately extract fields like student number, loan amount, income, bank details, and account information.

- **Triage Validator Agent**: Focuses on validating extracted data through three levels: 1) Cross-document validation (matching bank names, account numbers between documents), 2) Database validation (checking if applicant exists - future feature), 3) Completeness check (ensuring all required fields are present with valid formats). Uses Azure OpenAI with Pydantic structured outputs to return validation results.

- **Decision Maker Agent**: Interfaces with the MCP Server to make final loan approval decisions. This agent calls multiple MCP tools such as `calculate_dti_ratio()` (Debt-to-Income calculation), `evaluate_credit_profile()` (credit scoring), and receives recommendations for approval/denial with interest rates and monthly payments.

- **Chat Agent**: Handles general conversational queries about student loans, eligibility requirements, and application process outside the formal loan workflow.

**🟢 Frontend Web App (React + Vite)**

A React-based single-page application providing the user interface for the chat experience.

- Real-time chat interface with streaming message support
- PDF document upload capability (drag-and-drop or file picker)
- Workflow status tracking and progress indicators
- Response formatting with markdown support
- Mobile-responsive design

**🟡 Business API - MCP Services (FastAPI Microservices)**

Backend systems exposed as MCP (Model Context Protocol) endpoints to provide business logic and data operations.

- **Loan Approval MCP Service**: Provides loan decision-making capabilities including DTI ratio calculation, credit profile evaluation, interest rate determination, and monthly payment calculation. This service implements the core business rules for approving or denying student loan applications based on financial criteria (DTI < 40% for approval).

### Typical User Journey

1. **General Inquiry** - User asks questions about student loans
   - Intent: `general_chat`
   - Agent: Chat Agent responds with general information

2. **Document Upload** - User uploads loan application + bank statement PDFs
   - Intent: `document_upload`
   - Service: Document Scanner extracts structured data using GPT-4o
   - Output: StudentLoanApplication and BankStatement Pydantic models

3. **Validation** - System validates extracted data
   - Agent: Triage Validator performs 3-level validation
   - Checks: Bank name match, account number match, field completeness
   - Output: PASS / CONDITIONAL_PASS / FAIL status

4. **User Confirmation** - System presents validation results
   - User reviews extracted data
   - User types "yes" or "proceed" to confirm

5. **Loan Decision** - System evaluates loan application
   - Agent: Decision Maker Agent calls MCP Server
   - Tools: `calculate_dti_ratio()`, `evaluate_credit_profile()`
   - Output: APPROVED / DENIED with interest rate and payment details

6. **Final Response** - User receives decision
   - Chat interface displays approval status
   - Includes loan amount, interest rate, monthly payment

## 📁 Project Structure

```
agent-loan-processing/
├── README.md                           # Project documentation
├── LICENSE                             # MIT License
├── .gitignore                          # Git ignore configuration
├── deploy-clean.ps1                    # Automated Azure deployment script
├── DEPLOYMENT-FIXES.md                 # Deployment fixes documentation
│
└── src/                                # Source code root
    │
    ├── backend/                        # 🔵 BACKEND API (FastAPI + AI Agents)
    │   ├── Dockerfile                  # Container image definition
    │   ├── pyproject.toml              # Python dependencies (uv)
    │   ├── applicationinsights.json    # Azure Application Insights config
    │   │
    │   └── app/
    │       ├── main.py                 # FastAPI application entry point
    │       │
    │       ├── agents/                 # Multi-agent orchestration
    │       │   └── loan_workflow/
    │       │       ├── loan_workflow_orchestrator.py      # Supervisor agent
    │       │       ├── loan_document_extractor.py         # Document extraction agent
    │       │       ├── loan_application_validator.py      # Validation agent
    │       │       ├── loan_approval_decision_maker.py    # Decision agent (MCP client)
    │       │       ├── general_chat_handler.py            # General Q&A agent
    │       │       ├── user_intent_classifier.py          # Intent classification
    │       │       ├── extraction_result_formatter.py     # Response formatting
    │       │       ├── error_handler.py                   # Error handling
    │       │       └── loan_application_instructions_provider.py  # Instructions
    │       │
    │       ├── api/                    # REST API routes
    │       │   ├── chat_routes.py      # Chat & document upload
    │       │   ├── auth_routes.py      # Authentication
    │       │   └── status_routes.py    # Health & status checks
    │       │
    │       ├── services/               # Business services
    │       │   ├── loan_document_scanner.py       # GPT-4o document extraction
    │       │   └── azure_blob_storage_client.py   # Azure Blob Storage client
    │       │
    │       ├── models/                 # Pydantic data models
    │       │   ├── validation.py       # Validation result models
    │       │   ├── documents.py        # Document structure models
    │       │   ├── chat.py             # Chat request/response models
    │       │   └── user.py             # User authentication models
    │       │
    │       ├── config/                 # Application configuration
    │       │   ├── settings.py         # Environment settings
    │       │   ├── azure_credential.py # Managed identity authentication
    │       │   ├── logging_config.py   # Logging configuration
    │       │   └── azure_chat_client_factory.py  # Dependency injection
    │       │
    │       ├── utils/                  # Utility functions
    │       │   └── status_helpers.py   # Workflow state helpers
    │       │
    │       └── tests/                  # Unit tests
    │           └── agents/
    │               └── test_triage_agent.py
    │
    ├── frontend/                       # 🟢 FRONTEND WEB APP (React + Vite + TypeScript)
    │   ├── Dockerfile                  # Container image definition
    │   ├── nginx.conf                  # Nginx server configuration
    │   ├── package.json                # Node.js dependencies
    │   ├── vite.config.ts              # Vite build configuration
    │   ├── index.html                  # HTML entry point
    │   ├── README.md                   # Frontend documentation
    │   │
    │   └── src/
    │       ├── App.tsx                 # Main React component
    │       ├── main.tsx                # Application entry point
    │       ├── index.css               # Global styles
    │       │
    │       ├── components/             # React components
    │       │   ├── ChatInterface.tsx   # Chat UI component
    │       │   ├── ProcessSidebar.tsx  # Workflow status sidebar
    │       │   └── ui/                 # Reusable UI components
    │       │
    │       ├── services/               # API client services
    │       │   └── api.ts              # Backend API client
    │       │
    │       └── styles/                 # Component styles
    │           └── globals.css
    │
    └── biz_api/                        # 🟡 BUSINESS API LAYER (MCP Server)
        └── loan_approval/
            ├── Dockerfile              # Container image definition
            ├── pyproject.toml          # Python dependencies (uv)
            ├── main.py                 # MCP server entry point (FastMCP)
            ├── mcp_tools.py            # MCP tool definitions
            ├── services.py             # Business logic (DTI, credit scoring)
            ├── models.py               # Pydantic request/response models
            ├── logging_config.py       # Logging configuration
            ├── README.md               # MCP server documentation
            ├── DTI_IMPLEMENTATION.md   # DTI calculation details
            ├── test_loan_approval.py   # Unit tests
            │
            └── test_data/              # Test cases
                ├── approved_preferred_rate_input.json
                ├── approved_preferred_rate_output.json
                ├── approved_standard_rate_input.json
                ├── approved_standard_rate_output.json
                ├── rejected_high_dti_input.json
                └── rejected_high_dti_output.json
```

## 🚀 Quick Start

## Prerequisites

### Required Software & Tools

Before deploying or running this solution, ensure you have the following installed:

#### 1. **Azure CLI** (Required for deployment)
   - **Version**: Latest (2.80.0+)
   - **Installation**: 
     - **Windows**: `winget install -e --id Microsoft.AzureCLI`
     - **macOS**: `brew install azure-cli`
     - **Linux**: [Install via apt/yum](https://docs.microsoft.com/cli/azure/install-azure-cli)
   - **Verify**: `az --version`
   - **Purpose**: Deploy Azure resources and manage infrastructure

#### 2. **PowerShell 7+** (Windows) or **Bash** (Linux/macOS)
   - **Windows**: PowerShell 7+ (comes with Windows 11, or install from Microsoft Store)
   - **macOS/Linux**: Bash (pre-installed)
   - **Purpose**: Run deployment scripts

#### 3. **Python 3.11+** (For local development)
   - **Installation**: [Download from python.org](https://www.python.org/downloads/)
   - **Verify**: `python --version`
   - **Recommended**: Use `uv` package manager: `pip install uv`
   - **Purpose**: Run backend and MCP server locally

#### 4. **Node.js 18+** and **npm** (For local development)
   - **Installation**: [Download from nodejs.org](https://nodejs.org/)
   - **Verify**: `node --version` and `npm --version`
   - **Purpose**: Run frontend React application locally

#### 5. **Docker** (Optional, for containerized local development)
   - **Installation**: [Docker Desktop](https://www.docker.com/products/docker-desktop/)
   - **Purpose**: Build and test containers locally before deployment

### Azure Subscription & Access Requirements

#### 1. **Active Azure Subscription**
   - You must have an active Azure subscription
   - **Free tier**: [Create a free account](https://azure.microsoft.com/free/)
   - **Verify**: `az account show`

#### 2. **Required Azure RBAC Permissions**
   
   Your Azure account must have the following **Role-Based Access Control (RBAC)** permissions:

   - ✅ **Contributor** role on the subscription or resource group (minimum requirement)
     - Create/delete resource groups
     - Create/manage Azure Container Apps
     - Create/manage Azure Container Registry
     - Create/manage Azure Storage Accounts
     - Create/manage Azure OpenAI resources
     - Assign managed identities
   
   - ✅ **User Access Administrator** role (for role assignments)
     - Assign "Storage Blob Data Contributor" role to managed identities
     - Assign "Cognitive Services OpenAI User" role to managed identities
   
   **Alternative**: If you don't have User Access Administrator, ask your Azure admin to:
   - Pre-assign the necessary roles to your user account
   - OR grant you **Owner** role on a dedicated resource group

   **Verify your permissions**:
   ```powershell
   az role assignment list --assignee $(az ad signed-in-user show --query id -o tsv) --all
   ```

#### 3. **Azure OpenAI Service Access**
   
   - **Azure OpenAI Access**: You need approval to use Azure OpenAI
   - **Apply here**: [Request Azure OpenAI Access](https://aka.ms/oai/access)
   - **Approval time**: Usually instant for existing Azure customers
   - **Region availability**: Ensure your region supports GPT-4o model
   
   **Supported regions for GPT-4o**:
   - `eastus`, `eastus2`, `westus`, `westus2`, `swedencentral`, `northcentralus`

#### 4. **Resource Quotas & Limits**
   
   Ensure your subscription has sufficient quota for:
   - **Azure Container Apps**: At least 3 container apps
   - **Azure Container Registry**: 1 registry (Basic SKU minimum)
   - **Azure Storage**: 1 storage account (Standard LRS)
   - **Azure OpenAI**: 1 resource with GPT-4o deployment (S0 tier)
   
   **Check quotas**: Navigate to Azure Portal → Subscriptions → Usage + quotas

### PowerShell Execution Policy (Windows Only)

If you're on Windows, you may need to adjust PowerShell execution policy to run the deployment script:

```powershell
# Option 1: Allow for current session only (recommended)
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force

# Option 2: Allow for current user permanently (requires admin)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
```

### Pre-Deployment Checklist

Before running `deploy-clean.ps1`, verify:

- [ ] Azure CLI installed and working: `az --version`
- [ ] Logged into Azure: `az login`
- [ ] Correct subscription selected: `az account show`
- [ ] Contributor + User Access Administrator roles assigned
- [ ] Azure OpenAI access approved
- [ ] Chosen Azure region supports GPT-4o
- [ ] PowerShell execution policy set (Windows)

## 🚀 Deployment to Azure

### One-Click Deployment

This repository includes an automated deployment script that provisions all Azure resources and deploys the application.

**Run the deployment script**:

```powershell
# Windows PowerShell
.\deploy-clean.ps1
```

The script will:
1. Create Azure resource group
2. Create Log Analytics Workspace for monitoring
3. Create Azure Storage Account with blob container
4. Create Azure OpenAI resource with custom domain
5. Deploy GPT-4o model
6. Create Azure Container Registry
7. Build and push 3 Docker images (backend, frontend, MCP server)
8. Create Azure Container Apps Environment (with Log Analytics integration)
9. Deploy 3 Container Apps with managed identities
10. Configure networking and CORS

**Total deployment time**: ~15-20 minutes

**Interactive Prompts**:
- Resource group name (default: `rg-loan-processing`)
- Azure region (default: `eastus`)
- Unique prefix for resources (default: random)
- GPT-4o deployment name (default: `gpt-4o`)

**Post-Deployment**:
- Frontend URL: `https://<prefix>-frontend-web.azurecontainerapps.io`
- Backend API: `https://<prefix>-backend-api.azurecontainerapps.io`
- MCP Server: `https://<prefix>-mcp-server.azurecontainerapps.io`

**Note**: The deployment script automatically handles:
- Managed identity authentication (no API keys needed)
- RBAC role assignments
- CORS configuration
- Environment variable injection

### Troubleshooting Deployment

**Issue**: `InternalServerError` when creating Azure OpenAI
- **Solution**: Retry the script or try a different region (e.g., `eastus` instead of `westus`)

**Issue**: PowerShell script execution blocked
- **Solution**: Run `Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force`

**Issue**: Insufficient permissions
- **Solution**: Contact your Azure admin to grant Contributor + User Access Administrator roles

**Issue**: Azure OpenAI quota exceeded
- **Solution**: Request quota increase in Azure Portal or use a different subscription

## � Cost Estimation

Pricing varies per region and usage, so it isn't possible to predict exact costs for your usage. However, you can try the [Azure pricing calculator](https://azure.microsoft.com/pricing/calculator/) for the resources below:

- **Azure OpenAI**: Standard tier, GPT-4o model. Pricing per 1K tokens used, and at least 1K tokens are used per question. [Pricing](https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/)
- **Azure Blob Storage**: Standard tier with ZRS (Zone-redundant storage). Pricing per storage and read operations. [Pricing](https://azure.microsoft.com/pricing/details/storage/blobs/)
- **Azure Document Intelligence**: Standard tier using pre-built layout (future). [Pricing](https://azure.microsoft.com/pricing/details/form-recognizer/)
- **Azure Monitor**: Pay-as-you-go tier. Costs based on data ingested (future). [Pricing](https://azure.microsoft.com/pricing/details/monitor/)

⚠️ To avoid unnecessary costs, remember to take down your app if it's no longer in use by stopping local servers or deleting Azure resource groups if deployed.

## Resources

Here are some resources to learn more about multi-agent architectures and technologies used in this sample:

- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
- [AI Agents For Beginners](https://github.com/microsoft/ai-agents-for-beginners)
- [Azure AI Foundry](https://learn.microsoft.com/azure/ai-foundry/what-is-azure-ai-foundry)
- [Develop AI apps using Azure services](https://aka.ms/azai)
- [Building Effective Agents - Anthropic](https://www.anthropic.com/engineering/building-effective-agents)
- [AI agent orchestration patterns](https://learn.microsoft.com/azure/architecture/ai-ml/guide/ai-agent-design-patterns)

You can also find [more Azure AI agents samples here](https://aka.ms/aiapps).

## Getting Help

If you get stuck or have any questions about building AI apps, join:

[Azure AI Foundry Discord](https://aka.ms/foundry/discord)

If you have product feedback or errors while building visit:

[Azure AI Foundry Developer Forum](https://aka.ms/foundry/forum)

## 📚 Documentation

- **[RUNNING.md](./RUNNING.md)**: Detailed setup and running instructions
- **[src/biz_api/loan_approval/README.md](./src/biz_api/loan_approval/README.md)**: MCP server documentation
- **[src/biz_api/loan_approval/DTI_IMPLEMENTATION.md](./src/biz_api/loan_approval/DTI_IMPLEMENTATION.md)**: DTI calculation logic
- **[src/frontend/README.md](./src/frontend/README.md)**: Frontend development guide

## 🧪 Testing

### Manual Testing

1. **Backend Health Check**:
```bash
curl http://localhost:8000/api/status
# Expected: {"status": "healthy", "timestamp": "..."}
```

2. **MCP Server Test**:
```bash
cd src/biz_api/loan_approval
pytest test_loan_approval.py -v
# Tests DTI calculation, credit evaluation, and decision logic
```

3. **Full Workflow Test**:
   - Upload sample documents from `data/sample_documents/`
   - Use the chat interface to process application
   - Verify all workflow stages complete successfully

### Sample Test Data

- **Student Loan Application**: `data/sample_documents/sample-filled-student-loan-application.pdf`
- **Bank Statement**: `data/sample_documents/bank-statement-sample.pdf`
- **Expected Results**:
  - Extraction: Student number, loan amount, income, bank details
  - Validation: PASS (all fields match)
  - Decision: APPROVED or DENIED based on DTI ratio

### Unit Tests

```bash
# Test MCP business logic
cd src/biz_api/loan_approval
pytest test_loan_approval.py

# Test coverage includes:
# - DTI calculation (approved: <40%, denied: ≥40%)
# - Credit evaluation (excellent/good/fair/poor)
# - Interest rate determination
# - Monthly payment calculation
```

## � Current Status

### ✅ Completed Features

- [x] **Backend Server**: FastAPI with AI agent orchestration
- [x] **Frontend**: React chat interface with file upload
- [x] **Business API**: MCP server for loan decisions
- [x] **Document Extraction**: Azure OpenAI GPT-4o with structured outputs
- [x] **Validation System**: 3-level validation (cross-document, DB, completeness)
- [x] **Authentication**: JWT-based user authentication system
- [x] **Blob Storage**: Azure Blob Storage for document persistence
- [x] **Status Tracking**: Real-time workflow state management
- [x] **Error Handling**: Comprehensive error handling and logging
- [x] **Code Refactoring**: Modular architecture with utilities and models

### 🔮 Future Enhancements

- [ ] **Cosmos DB Integration**: Persistent applicant history and workflow state
- [ ] **Azure AI Search**: RAG pattern for loan policy queries
- [ ] **Azure Document Intelligence**: Advanced form recognition (alternative to GPT-4o)
- [ ] **Real-time Notifications**: WebSocket for instant status updates
- [ ] **Admin Dashboard**: Monitoring and analytics interface
- [ ] **Multi-language Support**: Internationalization (i18n)
- [ ] **Responsible AI**: Content safety filters and bias detection
- [ ] **Integration Tests**: End-to-end testing suite
- [ ] **CI/CD Pipeline**: Automated deployment to Azure

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Commit your changes: `git commit -am 'Add new feature'`
4. Push to the branch: `git push origin feature/new-feature`
5. Create a Pull Request

### Development Guidelines

**Backend**:
- Use dependency injection via `dependency_injector`
- Follow Agent Framework patterns (executors, workflows)
- Use Pydantic models for all data validation
- Log at appropriate levels (info=essential, debug=detailed)
- Keep business logic in `services/` directory

**Frontend**:
- Follow React best practices with TypeScript
- Use Vite for development and building
- Maintain component modularity
- Handle loading and error states gracefully

**Business API**:
- Use MCP protocol for tool definitions
- Keep business rules testable and documented
- Provide comprehensive unit test coverage
- Document DTI thresholds and credit scoring logic

## Troubleshooting

If you have any issue when running or deploying this sample, [open an issue](https://github.com/redhatpeter/agentic-loan-processing/issues) in this repository.

## Contributing

This project welcomes contributions and suggestions. Most contributions require you to agree to a Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us the rights to use your contribution. For details, visit [https://cla.opensource.microsoft.com](https://cla.opensource.microsoft.com/).

When you submit a pull request, a CLA bot will automatically determine whether you need to provide a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general). Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos are subject to those third-party's policies.
#   E m e r g i n g - T e c h - T e a m 
 
 