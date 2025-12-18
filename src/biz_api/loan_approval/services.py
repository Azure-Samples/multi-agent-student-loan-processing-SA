from typing import Optional
from models import LoanApplication, LoanDecision, LoanDecisionStatus, ApplicantFinancials
import logging

logger = logging.getLogger(__name__)


class LoanApprovalService:
    """
    Service implementing DTI-based loan approval business rules:
    - DTI > 45%: Reject with reason "High debt-to-income"
    - 40% ≤ DTI ≤ 45%: Approve at 7.5% APR
    - DTI < 40%: Approve at 5.5% APR
    """

    def calculate_dti(self, financials: ApplicantFinancials) -> float:
        """
        Calculate debt-to-income ratio.
        
        Args:
            financials: Applicant financial information
            
        Returns:
            DTI as percentage (0-100+)
        """
        logger.info(
            "Calculating DTI: monthly_debt=%s, monthly_income=%s",
            financials.monthlyDebtPayments,
            financials.grossMonthlyIncome
        )
        
        if financials.grossMonthlyIncome <= 0:
            raise ValueError("Gross monthly income must be greater than zero")
        
        dti = (financials.monthlyDebtPayments / financials.grossMonthlyIncome) * 100
        logger.info("Calculated DTI: %.2f%%", dti)
        return dti

    def evaluate_loan_application(self, application: LoanApplication) -> LoanDecision:
        """
        Evaluate loan application based on DTI and return decision.
        
        Args:
            application: Loan application with financial information
            
        Returns:
            LoanDecision with status, APR rate, and reason
        """
        student_number = application.get_key_id()
        loan_application_id = application.generate_loan_application_id()
        
        logger.info(
            "Evaluating loan application for %s (Student#: %s, LoanApp#: %s), amount: $%.2f",
            application.applicantName,
            student_number,
            loan_application_id,
            application.loanAmount
        )
        
        # Calculate or use existing DTI
        if application.financials.dti is None:
            dti = self.calculate_dti(application.financials)
            application.financials.dti = dti
        else:
            dti = application.financials.dti
        
        # Apply business rules
        if dti > 45:
            # Reject: High DTI
            decision = LoanDecision(
                status=LoanDecisionStatus.REJECTED,
                aprRate=None,
                reason="High debt-to-income ratio. DTI must be 45% or lower to qualify.",
                dti=dti,
                studentNumber=student_number,
                loanApplicationId=loan_application_id,
                applicantName=application.applicantName,
                loanAmount=application.loanAmount
            )
            logger.info("Loan REJECTED: DTI=%.2f%% (threshold: 45%%)", dti)
        
        elif 40 <= dti <= 45:
            # Approve at 7.5% APR
            decision = LoanDecision(
                status=LoanDecisionStatus.APPROVED,
                aprRate=7.5,
                reason="Approved with standard rate due to moderate debt-to-income ratio.",
                dti=dti,
                studentNumber=student_number,
                loanApplicationId=loan_application_id,
                applicantName=application.applicantName,
                loanAmount=application.loanAmount
            )
            logger.info("Loan APPROVED at 7.5%% APR: DTI=%.2f%%", dti)
        
        else:  # dti < 40
            # Approve at 5.5% APR
            decision = LoanDecision(
                status=LoanDecisionStatus.APPROVED,
                aprRate=5.5,
                reason="Approved with preferred rate due to excellent debt-to-income ratio.",
                dti=dti,
                studentNumber=student_number,
                loanApplicationId=loan_application_id,
                applicantName=application.applicantName,
                loanAmount=application.loanAmount
            )
            logger.info("Loan APPROVED at 5.5%% APR: DTI=%.2f%%", dti)
        
        return decision
