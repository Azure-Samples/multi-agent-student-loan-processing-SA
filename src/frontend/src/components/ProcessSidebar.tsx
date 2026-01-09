import { CheckCircle, Circle, Clock, XCircle } from "lucide-react";
import { Badge } from "./ui/badge";
import { LoanStage } from "../services/api";

interface ProcessSidebarProps {
  applicationId?: string;
  stages?: LoanStage[];
  note?: string;
}

// Default stages when no data is provided
const defaultStages: LoanStage[] = [
  {
    id: "application_initiated",
    title: "Application Initiated",
    description: "Documents received",
    status: "pending",
    icon: "document"
  },
  {
    id: "identity_verification",
    title: "Identity Verification",
    description: "Document validation",
    status: "pending",
    icon: "shield-check"
  },
  {
    id: "financial_assessment",
    title: "Financial Assessment",
    description: "Credit & income review",
    status: "pending",
    icon: "currency-dollar"
  },
  {
    id: "underwriting_review",
    title: "Underwriting Review",
    description: "Risk evaluation",
    status: "pending",
    icon: "clipboard-check"
  },
  {
    id: "approval_disbursement",
    title: "Approval & Disbursement",
    description: "Final decision",
    status: "pending",
    icon: "check-circle"
  },
];

export function ProcessSidebar({ applicationId = "#LA-2025-1847", stages = defaultStages, note }: ProcessSidebarProps) {
  return (
    <div className="w-80 bg-sidebar border-r border-sidebar-border h-screen p-6 overflow-y-auto">
      <div className="mb-8 pb-6 border-b border-sidebar-border">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-8 h-8 bg-sidebar-primary rounded flex items-center justify-center">
            <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h2 className="text-sidebar-foreground mb-0">Loan Application</h2>
        </div>
        <p className="text-sidebar-foreground/70 text-sm">
          Application ID: {applicationId}
        </p>
      </div>

      <div className="space-y-1">
        {stages.map((stage, index) => (
          <div key={stage.id}>
            <div
              className={`flex gap-4 p-4 rounded-lg transition-colors ${
                stage.status === "active"
                  ? "bg-sidebar-primary/10 border border-sidebar-primary/30"
                  : stage.status === "completed"
                  ? "bg-sidebar-accent/50"
                  : stage.status === "error"
                  ? "bg-red-500/20 border-2 border-red-500"
                  : "bg-transparent"
              }`}
            >
              <div className="flex-shrink-0 mt-0.5">
                {stage.status === "completed" && <CheckCircle className="w-5 h-5 text-emerald-500" />}
                {stage.status === "active" && <Clock className="w-5 h-5 text-sidebar-primary" />}
                {stage.status === "pending" && <Circle className="w-5 h-5 text-sidebar-foreground/30" />}
                {stage.status === "error" && <XCircle className="w-7 h-7 text-red-600" strokeWidth={4} style={{ color: '#dc2626' }} />}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1">
                    <h4 className="mb-0.5 text-sidebar-foreground">{stage.title}</h4>
                    <p className="text-sm text-sidebar-foreground/60">
                      {stage.description}
                    </p>
                  </div>
                  {stage.status === "active" && (
                    <Badge variant="default" className="bg-sidebar-primary text-white shrink-0 border-0">
                      Active
                    </Badge>
                  )}
                </div>
              </div>
            </div>

            {index < stages.length - 1 && (
              <div className="ml-[30px] h-4 w-0.5 bg-sidebar-border" />
            )}
          </div>
        ))}
      </div>

      {note && (
        <div className="mt-8 p-4 bg-sidebar-primary/10 rounded-lg border border-sidebar-primary/20">
          <p className="text-sm text-sidebar-foreground/80">
            <span className="text-sidebar-primary">ⓘ Note:</span> {note}
          </p>
        </div>
      )}
    </div>
  );
}
