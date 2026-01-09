from fastapi import APIRouter, HTTPException, Depends
import logging
from app.agents.loan_workflow.loan_workflow_orchestrator import OrchestrationAgent
from app.config.azure_chat_client_factory import Container
from dependency_injector.wiring import Provide, inject

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/loan-status/{thread_id}")
@inject
async def get_loan_status(
    thread_id: str,
    orchestration_agent: OrchestrationAgent = Depends(Provide[Container.orchestration_agent])
):
    """
    Get the current loan application status for a given thread.
    
    Returns structured status information matching the UI stages:
    - Application Initiated (Documents received)
    - Identity Verification (Document validation)
    - Financial Assessment (Credit & income review)
    - Underwriting Review (Risk evaluation)
    - Approval & Disbursement (Final decision)
    """
    try:
        status_data = orchestration_agent.get_loan_application_status(thread_id)
        return status_data
    except Exception as e:
        logger.error(f"Error retrieving loan status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving status: {str(e)}")
