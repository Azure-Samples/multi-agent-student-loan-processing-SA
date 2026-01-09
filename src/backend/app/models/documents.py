"""Pydantic models for loan documents.

Defines structured data models for extracting information from:
- Student loan applications
- Bank statements

These models are used with Azure OpenAI's structured outputs feature
to ensure accurate field extraction from PDF documents.
"""
from pydantic import BaseModel, Field


class StudentLoanApplication(BaseModel):
    """Structured data model for student loan application."""
    studentNumber: str = Field(default="", description="Student ID number in format STU45678 (STU followed by 5 digits)")
    applicantName: str = Field(default="", description="Full name of the applicant")
    loanAmount: float = Field(default=0.0, description="Requested loan amount in dollars")
    loanPurpose: str = Field(default="", description="Purpose of the loan")
    grossMonthlyIncome: float = Field(default=0.0, description="Gross monthly income in dollars")
    monthlyDebtPayments: float = Field(default=0.0, description="Monthly debt payments in dollars")
    bankName: str = Field(default="", description="Name of the bank")
    accountType: str = Field(default="", description="Account type (Checking or Savings)")
    accountNumber: str = Field(default="", description="Bank account number (may be masked)")


class BankStatement(BaseModel):
    """Structured data model for bank statement."""
    accountHolderName: str = Field(default="", description="Name of the account holder")
    bankName: str = Field(default="", description="Name of the bank")
    accountType: str = Field(default="", description="Account type (Checking or Savings)")
    accountNumberLast4: str = Field(default="", description="Last 4 digits of account number")
    currentBalance: float = Field(default=0.0, description="Current account balance in dollars")
    statementPeriod: str = Field(default="", description="Statement period (e.g., 'Jan 2025 - Mar 2025')")
