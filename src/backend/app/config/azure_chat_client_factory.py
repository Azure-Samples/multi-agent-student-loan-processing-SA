"""Dependency injection container configuration."""

from dependency_injector import containers, providers
from app.config.azure_credential import get_azure_credential
from app.config.settings import settings
#Azure Chat based agents dependencies
from app.agents.loan_workflow.loan_workflow_orchestrator import OrchestrationAgent
from app.agents.loan_workflow.loan_document_extractor import DocumentExtractorAgent
from app.agents.loan_workflow.extraction_result_formatter import ResponseFormatterExecutor
from app.agents.loan_workflow.user_intent_classifier import IntentClassifierExecutor
from app.agents.loan_workflow.error_handler import ErrorHandlerExecutor
from app.agents.loan_workflow.general_chat_handler import ChatResponseExecutor
from app.agents.loan_workflow.loan_application_instructions_provider import LoanApplicationExecutor
from app.agents.loan_workflow.loan_application_validator import TriageAgentFactory
from app.agents.loan_workflow.loan_approval_decision_maker import DecisionMakerAgent


from agent_framework.azure import AzureOpenAIChatClient
from agent_framework import MCPStreamableHTTPTool, InMemoryCheckpointStorage


def create_azure_chat_client():
    """Factory function to create Azure chat client with proper authentication."""
    if settings.AZURE_OPENAI_KEY:
        print("Creating AzureOpenAIChatClient with API key")
        return AzureOpenAIChatClient(
            api_key=settings.AZURE_OPENAI_KEY,
            endpoint=settings.AZURE_OPENAI_ENDPOINT,
            deployment_name=settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME
        )
    else:
        print("Creating AzureOpenAIChatClient with credential")
        return AzureOpenAIChatClient(
            credential=get_azure_credential(),
            endpoint=settings.AZURE_OPENAI_ENDPOINT,
            deployment_name=settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME
        )


class Container(containers.DeclarativeContainer):
    """IoC container for application dependencies."""
   

    # Azure Chat based agents
    _azure_chat_client = providers.Singleton(create_azure_chat_client)

    # Agent Framework Executors
    document_extractor = providers.Singleton(
        DocumentExtractorAgent,
        id="document_extractor"
    )
    
    response_formatter = providers.Singleton(
        ResponseFormatterExecutor,
        id="response_formatter"
    )
    
    intent_classifier = providers.Singleton(
        IntentClassifierExecutor,
        id="intent_classifier"
    )
    
    error_handler = providers.Singleton(
        ErrorHandlerExecutor,
        id="error_handler"
    )
    
    checkpoint_storage = providers.Singleton(
        InMemoryCheckpointStorage
    )
    
    loan_application = providers.Singleton(
        LoanApplicationExecutor,
        id="loan_application"
    )
    
    # Triage Agent (ChatAgent for validation)
    triage_agent = providers.Singleton(
        lambda: TriageAgentFactory.create_triage_agent(create_azure_chat_client())
    )
    
    # Decision Maker Agent (ChatAgent with MCP tools for loan approval)
    decision_maker_agent = providers.Singleton(
        DecisionMakerAgent,
        azure_chat_client=_azure_chat_client,
        loan_approval_mcp_url=settings.LOAN_APPROVAL_MCP_URL
    )

    #Orchestration Agent with Azure chat based agents. A per request instance is created as it holds the thread state
    orchestration_agent = providers.Factory(
        OrchestrationAgent,
        azure_chat_client=_azure_chat_client,
        doc_extractor=document_extractor,
        response_formatter=response_formatter,
        intent_classifier=intent_classifier,
        error_handler=error_handler,
        checkpoint_storage=checkpoint_storage,
        loan_application=loan_application,
        triage_agent=triage_agent,
        decision_maker_agent=decision_maker_agent
    )


   