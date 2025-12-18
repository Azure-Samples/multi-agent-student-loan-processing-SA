import { useState, useEffect } from "react";
import { ProcessSidebar } from "./components/ProcessSidebar";
import { ChatInterface } from "./components/ChatInterface";
import { api, LoanStatusResponse } from "./services/api";

export default function App() {
  const [applicationStarted, setApplicationStarted] = useState(false);
  const [threadId, setThreadId] = useState<string | undefined>(undefined);
  const [loanStatus, setLoanStatus] = useState<LoanStatusResponse | null>(null);

  const handleApplicationStart = () => {
    setApplicationStarted(true);
  };

  const handleThreadIdUpdate = (newThreadId: string) => {
    setThreadId(newThreadId);
  };

  // Poll for loan status when threadId is available
  useEffect(() => {
    if (!threadId) return;

    let intervalId: NodeJS.Timeout | null = null;

    const pollStatus = async () => {
      try {
        const status = await api.getLoanStatus(threadId);
        setLoanStatus(status);
        
        // Stop polling if completed or error
        if (status.currentState === 'completed' || status.currentState === 'error') {
          if (intervalId) {
            clearInterval(intervalId);
            intervalId = null;
          }
        }
      } catch (error) {
        console.error('Failed to fetch loan status:', error);
      }
    };

    // Initial fetch
    pollStatus();

    // Poll every 2 seconds
    intervalId = setInterval(pollStatus, 2000);

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [threadId]);

  return (
    <div className="size-full flex">
      {applicationStarted && (
        <ProcessSidebar 
          applicationId={loanStatus?.applicationId}
          stages={loanStatus?.stages}
          note={loanStatus?.note}
        />
      )}
      
      <div className="flex-1 overflow-y-auto bg-background">
        <div className="max-w-4xl mx-auto p-8">
          <div className="mb-6 p-8 bg-card rounded-lg border border-border shadow-sm">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="mb-2">Welcome, Loan Applicant</h2>
                <p className="text-muted-foreground">
                  {applicationStarted 
                    ? "Your loan application is being processed. Our team will keep you informed of any updates."
                    : "Access professional loan advisory services and explore financing options tailored to your needs."}
                </p>
              </div>
              <div className="flex-shrink-0 ml-4">
                <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
                  <svg className="w-6 h-6 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                </div>
              </div>
            </div>
            {applicationStarted && loanStatus && (
              <div className="mt-4 pt-4 border-t border-border flex items-center gap-2 text-sm text-muted-foreground">
                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                Application Status: {loanStatus.currentStage.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
              </div>
            )}
          </div>

          <div className="h-[calc(100vh-240px)]">
            <ChatInterface 
              onApplicationStart={handleApplicationStart}
              threadId={threadId}
              onThreadIdUpdate={handleThreadIdUpdate}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
