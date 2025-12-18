"""Decision Maker Agent for loan approval decisions using MCP tools."""

import json
import logging
from typing import Dict, Any
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework import ChatAgent, MCPStreamableHTTPTool

logger = logging.getLogger(__name__)


class DecisionMakerAgent:
    """Decision Maker Agent for evaluating loan applications via MCP."""
    
    # Decision Maker instructions for the ChatAgent
    DECISION_MAKER_INSTRUCTIONS = """
    You are a loan approval decision specialist. Your role is to evaluate student loan applications
    by calculating the Debt-to-Income (DTI) ratio and applying business rules to make approval decisions.
    
    WORKFLOW:
    
    1. RECEIVE VALIDATED DATA:
       You will receive validated loan application data in JSON format:
       {
           "studentNumber": "STU45678",
           "applicantName": "Jane Smith",
           "loanAmount": 30000.0,
           "grossMonthlyIncome": 5000.0,
           "monthlyDebtPayments": 2200.0,
           "bankName": "Metro Federal",
           "accountType": "Checking"
       }
    
    2. CALCULATE DTI:
       First, call the `calculateDTI` tool with:
       - grossMonthlyIncome
       - monthlyDebtPayments
       
       This will return the DTI ratio as a percentage.
    
    3. EVALUATE LOAN APPLICATION:
       Next, call the `evaluateLoanApplication` tool with:
       - studentNumber (required - unique identifier)
       - applicantName
       - loanAmount
       - grossMonthlyIncome
       - monthlyDebtPayments
       - dti (from step 2)
       
       This will return the loan decision with:
       - status: APPROVED or REJECTED
       - aprRate: Interest rate (if approved)
       - reason: Explanation for the decision
       - loanApplicationId: Generated application ID
    
    4. RETURN STRUCTURED RESULT:
       Return the complete decision in JSON format exactly as received from evaluateLoanApplication.
       Do NOT add any additional text or explanation outside the JSON structure.
    
    IMPORTANT RULES:
    - Always call both tools in sequence (calculateDTI first, then evaluateLoanApplication)
    - Use the exact field names from the input data
    - Return only the JSON response from evaluateLoanApplication
    
    BUSINESS RULES (FYI - the MCP tools will apply these):
    - DTI > 45%: REJECTED (high financial risk)
    - 40% ≤ DTI ≤ 45%: APPROVED at 7.5% APR (standard rate)
    - DTI < 40%: APPROVED at 5.5% APR (preferred rate)
    """
    
    name = "LoanDecisionMaker"
    description = "This agent evaluates loan applications by calculating DTI and applying approval rules via MCP tools"
    
    def __init__(self, azure_chat_client: AzureOpenAIChatClient, loan_approval_mcp_url: str):
        """Initialize Decision Maker Agent.
        
        Args:
            azure_chat_client: Azure OpenAI chat client
            loan_approval_mcp_url: URL to the loan approval MCP server
        """
        self.azure_chat_client = azure_chat_client
        self.loan_approval_mcp_url = loan_approval_mcp_url
    
    async def build_af_agent(self) -> ChatAgent:
        """Build the Agent Framework ChatAgent with MCP tools.
        Always rebuilds to ensure fresh MCP connection (avoids stale connection issues).
        
        Returns:
            Configured ChatAgent with MCP tools
        """
        # Always rebuild to ensure fresh connection
        logger.debug(f"Building Decision Maker Agent with MCP URL: {self.loan_approval_mcp_url}")
        
        try:
            # Create MCP tool for loan approval service
            mcp_tool = MCPStreamableHTTPTool(
                name="loan_approval_mcp",
                url=self.loan_approval_mcp_url
            )
            
            # Connect to the MCP server
            logger.debug("Connecting to MCP server...")
            await mcp_tool.connect()
            logger.debug("MCP server connected successfully")
            
            # Create ChatAgent with MCP tools
            agent = ChatAgent(
                name=self.name,
                instructions=self.DECISION_MAKER_INSTRUCTIONS,
                chat_client=self.azure_chat_client,
                tools=[mcp_tool],
                max_turns=10  # Allow multiple turns for tool calling
            )
            
            logger.debug("Decision Maker Agent created successfully")
            return agent
            
        except Exception as e:
            logger.error(f"Error building Decision Maker Agent: {str(e)}", exc_info=True)
            raise


async def run_decision_maker(
    decision_maker_agent: DecisionMakerAgent,
    validated_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Run Decision Maker Agent to evaluate loan application.
    
    Args:
        decision_maker_agent: DecisionMakerAgent instance
        validated_data: Validated loan application data from Triage Agent
        
    Returns:
        Dictionary containing loan decision with status, aprRate, reason, etc.
        
    Raises:
        Exception: If decision making fails
    """
    import asyncio
    
    logger.debug("Starting loan decision evaluation...")
    logger.debug(f"Input data: {json.dumps(validated_data, indent=2)}")
    
    agent = None
    mcp_tools = []
    
    try:
        # Build the agent if not already built
        agent = await decision_maker_agent.build_af_agent()
        
        # Keep track of MCP tools for cleanup
        if hasattr(agent, 'tools'):
            mcp_tools = [tool for tool in agent.tools if hasattr(tool, 'disconnect')]
        
        # Prepare input message for the agent
        input_json = json.dumps(validated_data, indent=2)
        
        # Run the agent with timeout (60 seconds)
        try:
            result = await asyncio.wait_for(agent.run(input_json), timeout=60.0)
        except asyncio.TimeoutError:
            logger.error("Decision Maker Agent timed out after 60 seconds")
            raise Exception("Decision Maker Agent timed out - MCP server may not be responding")
        
        # Extract response
        if hasattr(result, 'messages') and result.messages:
            response_text = result.messages[-1].text if hasattr(result.messages[-1], 'text') else str(result.messages[-1])
        else:
            response_text = str(result)
        
        logger.debug(f"Agent response: {response_text}")
        
        # Remove markdown code blocks if present
        response_text = response_text.strip()
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.startswith('```'):
            response_text = response_text[3:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        
        # Parse the JSON response
        try:
            decision = json.loads(response_text.strip())
            status = decision.get('status', 'UNKNOWN')
            logger.info(f"Loan decision completed: {status}")
            logger.debug(f"Decision details: {decision.get('reason')}, APR: {decision.get('aprRate')}")
            return decision
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse agent response as JSON: {e}")
            logger.error(f"Raw response: {response_text}")
            raise ValueError(f"Decision Maker returned invalid JSON: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error in Decision Maker: {str(e)}", exc_info=True)
        raise
    finally:
        # CRITICAL: Properly disconnect MCP tools to avoid async context errors
        for tool in mcp_tools:
            try:
                logger.debug(f"Disconnecting MCP tool: {tool.name if hasattr(tool, 'name') else 'unknown'}")
                await tool.disconnect()
            except Exception as cleanup_error:
                logger.warning(f"Error disconnecting MCP tool: {cleanup_error}")
