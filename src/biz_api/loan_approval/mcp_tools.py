from fastmcp import FastMCP
import logging
from typing import Annotated
from services import LoanApprovalService
from models import LoanApplication, ApplicantFinancials

logger = logging.getLogger(__name__)
loan_approval_service = LoanApprovalService()
mcp = FastMCP("Loan Approval MCP Server")

@mcp.tool(name="calculateDTI", description="Calculate debt-to-income ratio from financial information")
def calculate_dti(
    grossMonthlyIncome: Annotated[float, "Gross monthly income in dollars"],
    monthlyDebtPayments: Annotated[float, "Total monthly debt payments in dollars"]
) -> dict:
    """
    Calculate debt-to-income ratio (DTI) as a percentage.
    Formula: DTI = (monthly_debt_payments / gross_monthly_income) * 100
    """
    logger.info(
        "calculateDTI called with grossMonthlyIncome=%s, monthlyDebtPayments=%s",
        grossMonthlyIncome,
        monthlyDebtPayments
    )
    
    financials = ApplicantFinancials(
        grossMonthlyIncome=grossMonthlyIncome,
        monthlyDebtPayments=monthlyDebtPayments
    )
    
    dti = loan_approval_service.calculate_dti(financials)
    
    return {
        "dti": round(dti, 2),
        "grossMonthlyIncome": grossMonthlyIncome,
        "monthlyDebtPayments": monthlyDebtPayments
    }


@mcp.tool(name="evaluateLoanApplication", description="Evaluate loan application and return approval decision based on DTI")
def evaluate_loan_application(
    studentNumber: Annotated[str, "Student number (required unique identifier)"],
    applicantName: Annotated[str, "Full name of the applicant"],
    loanAmount: Annotated[float, "Requested loan amount in dollars"],
    grossMonthlyIncome: Annotated[float, "Gross monthly income in dollars"],
    monthlyDebtPayments: Annotated[float, "Total monthly debt payments in dollars"],
    dti: Annotated[float | None, "Pre-calculated DTI (optional, will calculate if not provided)"] = None
) -> dict:
    """
    Evaluate loan application using DTI-based business rules:
    - DTI > 45%: Reject
    - 40% ≤ DTI ≤ 45%: Approve at 7.5% APR
    - DTI < 40%: Approve at 5.5% APR
    
    Student number is required and used as the key identifier.
    Loan application ID is auto-generated in the response.
    """
    logger.info(
        "evaluateLoanApplication called for applicant=%s (Student#: %s), amount=$%.2f",
        applicantName,
        studentNumber,
        loanAmount
    )
    
    financials = ApplicantFinancials(
        grossMonthlyIncome=grossMonthlyIncome,
        monthlyDebtPayments=monthlyDebtPayments,
        dti=dti
    )
    
    application = LoanApplication(
        studentNumber=studentNumber,
        applicantName=applicantName,
        loanAmount=loanAmount,
        financials=financials
    )
    
    decision = loan_approval_service.evaluate_loan_application(application)
    
    return decision.model_dump()
