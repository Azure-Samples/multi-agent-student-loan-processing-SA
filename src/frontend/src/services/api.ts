// API Service for communicating with backend

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  attachments?: string[];
}

export interface ChatRequest {
  stream: boolean;
  messages: ChatMessage[];
  attachments?: string[];
  threadId?: string;
  files?: File[];  // Add support for actual File objects
}

export interface ChatResponseMessage {
  content: string;
  role: string;
  attachments: any[];
}

export interface ChatContext {
  thoughts: string;
  data_points: any[];
}

export interface ChatDelta {
  content: string;
  role: string;
  attachments: any[];
}

export interface ChatChoice {
  index: number;
  message?: ChatResponseMessage;
  context?: ChatContext;
  delta: ChatDelta;
}

export interface ChatResponse {
  choices: ChatChoice[];
  threadId?: string;
  error?: string;
}

export interface LoanStage {
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'active' | 'completed' | 'error';
  icon: string;
}

export interface LoanStatusResponse {
  applicationId: string;
  currentStage: string;
  currentState: string;
  timestamp: string;
  message: string;
  stages: LoanStage[];
  note: string;
}

export const api = {
  // Send a non-streaming chat message
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
  },

  // Send a streaming chat message
  async *sendMessageStream(request: ChatRequest): AsyncGenerator<ChatResponse, void, unknown> {
    let response: Response;
    
    // If files are attached, use FormData
    if (request.files && request.files.length > 0) {
      const formData = new FormData();
      
      // Append files
      request.files.forEach((file, index) => {
        formData.append('files', file);
      });
      
      // Append other data as JSON string
      formData.append('stream', request.stream.toString());
      formData.append('messages', JSON.stringify(request.messages));
      if (request.threadId) {
        formData.append('threadId', request.threadId);
      }
      
      response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        body: formData,
      });
    } else {
      // Regular JSON request without files
      response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ...request, stream: true }),
      });
    }

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        
        // Keep the last incomplete line in the buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.trim()) {
            try {
              const data = JSON.parse(line);
              yield data as ChatResponse;
            } catch (e) {
              console.error('Failed to parse line:', line, e);
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  },

  // Get loan application status
  async getLoanStatus(threadId: string): Promise<LoanStatusResponse> {
    const response = await fetch(`${API_BASE_URL}/loan-status/${threadId}`);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return response.json();
  },
};
