from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class LoanDecisionStatus(str, Enum):
    """Loan decision status enum"""
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CONDITIONAL = "CONDITIONAL"


class ApplicantFinancials(BaseModel):
    """Financial information extracted from documents"""
    grossMonthlyIncome: float = Field(..., description="Gross monthly income in dollars")
    monthlyDebtPayments: float = Field(..., description="Total monthly debt payments in dollars")
    dti: Optional[float] = Field(None, description="Debt-to-income ratio as percentage")


class LoanApplication(BaseModel):
    """Loan application request"""
    studentNumber: str = Field(..., description="Student number (unique identifier/key)")
    applicantName: str = Field(..., description="Full name of the applicant")
    loanAmount: float = Field(..., description="Requested loan amount in dollars")
    financials: ApplicantFinancials = Field(..., description="Applicant's financial information")
    
    def get_key_id(self) -> str:
        """Get the primary key ID (studentNumber)"""
        return self.studentNumber
    
    def generate_loan_application_id(self) -> str:
        """Generate loan application ID from student number"""
        return f"LOAN-{self.studentNumber}"


class LoanDecision(BaseModel):
    """Loan decision response"""
    status: LoanDecisionStatus = Field(..., description="Decision status (APPROVED/REJECTED/CONDITIONAL)")
    aprRate: Optional[float] = Field(None, description="Approved APR rate as percentage")
    reason: str = Field(..., description="Reason for the decision")
    dti: float = Field(..., description="Calculated debt-to-income ratio")
    studentNumber: str = Field(..., description="Student number (key identifier)")
    loanApplicationId: str = Field(..., description="Generated loan application ID")
    applicantName: str = Field(..., description="Applicant name")
    loanAmount: float = Field(..., description="Requested loan amount")
