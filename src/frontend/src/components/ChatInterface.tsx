import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Plus, Paperclip, FileText, X, Upload, FileStack, Loader2 } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { ScrollArea } from "./ui/scroll-area";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "./ui/popover";
import { api } from "../services/api";

interface Message {
  id: number;
  text: string;
  sender: "user" | "bot";
  timestamp: Date;
  attachments?: { name: string; size: number }[];
}

interface ChatInterfaceProps {
  onApplicationStart: () => void;
  threadId?: string;
  onThreadIdUpdate: (threadId: string) => void;
}

export function ChatInterface({ onApplicationStart, threadId, onThreadIdUpdate }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 1,
      text: "Good day! I'm your dedicated loan advisor. I'm here to assist you with loan inquiries, application procedures, eligibility criteria, and terms. How may I help you today?",
      sender: "bot",
      timestamp: new Date(),
    },
  ]);
  const [inputValue, setInputValue] = useState("");
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [applicationIntentDetected, setApplicationIntentDetected] = useState(false);
  const [applicationStarted, setApplicationStarted] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };

    if (menuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      // Scroll to make the menu visible
      setTimeout(() => {
        menuRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }, 0);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [menuOpen]);

  const handleSendMessage = async () => {
    if (!inputValue.trim() && attachedFiles.length === 0) return;
    if (isLoading) return;

    const hasFiles = attachedFiles.length > 0;

    const userMessage: Message = {
      id: messages.length + 1,
      text: inputValue || "Sent files",
      sender: "user",
      timestamp: new Date(),
      attachments: attachedFiles.map((file) => ({
        name: file.name,
        size: file.size,
      })),
    };

    setMessages((prev) => [...prev, userMessage]);
    
    // Detect application intent in user message
    const lowerText = inputValue.toLowerCase();
    const intentKeywords = ['apply', 'application', 'start', 'begin', 'submit'];
    const hasIntent = intentKeywords.some(keyword => lowerText.includes(keyword));

    const currentInput = inputValue;
    setInputValue("");
    setAttachedFiles([]);
    setIsLoading(true);

    try {
      // Build conversation history for API
      const conversationHistory: Array<{ role: 'user' | 'assistant', content: string }> = [];
      
      // Add previous messages to history
      messages.forEach(msg => {
        conversationHistory.push({
          role: msg.sender === 'user' ? 'user' : 'assistant',
          content: msg.text
        });
      });
      
      // Add current message
      conversationHistory.push({
        role: 'user',
        content: currentInput || "Sent files"
      });

      // Call backend API with streaming
      let botText = "";
      const botMessageId = messages.length + 2;
      
      // Add a placeholder bot message
      const botMessage: Message = {
        id: botMessageId,
        text: "",
        sender: "bot",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, botMessage]);

      // Stream the response
      for await (const chunk of api.sendMessageStream({
        stream: true,
        messages: conversationHistory,
        threadId: threadId,
        files: attachedFiles  // Pass the actual File objects
      })) {
        if (chunk.threadId && chunk.threadId !== threadId) {
          onThreadIdUpdate(chunk.threadId);
        }
        
        if (chunk.choices && chunk.choices[0]?.delta?.content) {
          botText += chunk.choices[0].delta.content;
          
          // Update the bot message with accumulated content
          setMessages((prev) => 
            prev.map(msg => 
              msg.id === botMessageId 
                ? { ...msg, text: botText }
                : msg
            )
          );
        }

        if (chunk.error) {
          console.error("Stream error:", chunk.error);
          setMessages((prev) => 
            prev.map(msg => 
              msg.id === botMessageId 
                ? { ...msg, text: `Error: ${chunk.error}` }
                : msg
            )
          );
          break;
        }
      }

      // Detect if application should be started based on intent
      if (hasFiles && !applicationStarted) {
        setApplicationStarted(true);
        onApplicationStart();
      } else if (hasIntent && !applicationIntentDetected && !applicationStarted) {
        setApplicationIntentDetected(true);
        setApplicationStarted(true);
        onApplicationStart();
      }

    } catch (error) {
      console.error("Error sending message:", error);
      const errorMessage: Message = {
        id: messages.length + 2,
        text: "Sorry, I encountered an error processing your request. Please try again.",
        sender: "bot",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileSelect = (files: FileList | null) => {
    if (!files) return;
    const newFiles = Array.from(files);
    setAttachedFiles((prev) => [...prev, ...newFiles]);
  };

  const removeAttachedFile = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
  };

  const formatMessageText = (text: string) => {
    // Split text into paragraphs and format
    return text.split('\n').map((paragraph, index) => {
      if (!paragraph.trim()) return null;
      
      // Remove horizontal rules (---)
      if (/^[-]{3,}$/.test(paragraph.trim())) {
        return <div key={index} className="border-t border-border my-3" />;
      }
      
      // Check if it's a header (## or ### or ####)
      if (/^#{1,4}\s/.test(paragraph.trim())) {
        const level = paragraph.trim().match(/^(#{1,4})/)?.[0].length || 2;
        const headerText = paragraph.replace(/^#{1,4}\s+/g, '').trim();
        const fontSize = level === 1 ? 'text-base' : level === 2 ? 'text-base' : 'text-sm';
        return (
          <div key={index} className={`font-semibold ${fontSize} mt-4 mb-2`}>
            {headerText}
          </div>
        );
      }
      
      // Check if it's a table row (contains |)
      if (paragraph.includes('|') && paragraph.split('|').length > 2) {
        const cells = paragraph.split('|').map(cell => cell.trim()).filter(cell => cell);
        const isHeaderRow = cells.some(cell => cell.startsWith('**'));
        
        return (
          <div key={index} className="flex gap-2 text-xs mb-1">
            {cells.map((cell, idx) => (
              <div 
                key={idx} 
                className={`flex-1 ${isHeaderRow ? 'font-semibold' : ''}`}
              >
                {cell.replace(/\*\*/g, '')}
              </div>
            ))}
          </div>
        );
      }
      
      // Check if it's a numbered list item
      if (/^\d+\./.test(paragraph.trim())) {
        const content = paragraph.replace(/\*\*/g, '');
        return (
          <div key={index} className="mb-2 ml-2">
            {content}
          </div>
        );
      }
      
      // Check if it's a bullet point
      if (/^[-•*]\s/.test(paragraph.trim())) {
        const content = paragraph.replace(/\*\*/g, '');
        return (
          <div key={index} className="mb-1 ml-2">
            {content}
          </div>
        );
      }
      
      // Regular paragraph - remove ** bold markers
      const cleanedText = paragraph.replace(/\*\*/g, '');
      return (
        <div key={index} className="mb-2">
          {cleanedText}
        </div>
      );
    }).filter(Boolean);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="flex flex-col h-full bg-background rounded-lg border border-border">
      <div className="p-5 border-b border-border bg-card">
        <h3 className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
            <Bot className="w-4 h-4 text-primary" />
          </div>
          {applicationStarted ? "Loan Application Support" : "Loan Advisory Service"}
        </h3>
        <p className="text-sm text-muted-foreground mt-1.5">
          {applicationStarted 
            ? "Professional assistance with your application"
            : "Expert guidance on loan products and services"}
        </p>
      </div>

      <ScrollArea className="flex-1 p-4">
        <div ref={scrollRef} className="space-y-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex gap-3 ${
                message.sender === "user" ? "flex-row-reverse" : "flex-row"
              }`}
            >
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                  message.sender === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-primary/10 text-primary"
                }`}
              >
                {message.sender === "user" ? (
                  <User className="w-4 h-4" />
                ) : (
                  <Bot className="w-4 h-4" />
                )}
              </div>

              <div
                className={`max-w-[70%] rounded-lg p-3 ${
                  message.sender === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted"
                }`}
              >
                {message.attachments && message.attachments.length > 0 && (
                  <div className="mb-2 space-y-1">
                    {message.attachments.map((file, idx) => (
                      <div
                        key={idx}
                        className={`flex items-center gap-2 p-2 rounded ${
                          message.sender === "user"
                            ? "bg-primary-foreground/10"
                            : "bg-background/50"
                        }`}
                      >
                        <FileText className="w-4 h-4 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs truncate">{file.name}</p>
                          <p className="text-xs opacity-70">
                            {formatFileSize(file.size)}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                <div className="text-sm whitespace-pre-wrap">
                  {formatMessageText(message.text)}
                </div>
                <p
                  className={`text-xs mt-1 ${
                    message.sender === "user"
                      ? "text-primary-foreground/70"
                      : "text-muted-foreground"
                  }`}
                >
                  {message.timestamp.toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </p>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      <div className="p-4 border-t border-border">
        {attachedFiles.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {attachedFiles.map((file, index) => (
              <div
                key={index}
                className="flex items-center gap-2 bg-muted px-3 py-2 rounded-lg text-sm"
              >
                <FileText className="w-4 h-4 text-blue-600" />
                <span className="max-w-[150px] truncate">{file.name}</span>
                <button
                  onClick={() => removeAttachedFile(index)}
                  className="hover:bg-background rounded p-0.5"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        )}
        <div className="flex gap-2 relative">
          <div className="relative">
            <Button 
              variant="ghost" 
              size="icon" 
              className="flex-shrink-0 hover:bg-accent rounded-full"
              type="button"
              onClick={() => setMenuOpen(!menuOpen)}
            >
              <Plus className="w-5 h-5" />
            </Button>
            
            {menuOpen && (
              <div 
                ref={menuRef}
                className="absolute bottom-full left-0 mb-2 w-72 p-0 border shadow-lg rounded-xl bg-background z-50"
              >
                <div className="p-2 space-y-0.5">
                  <div className="px-3 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                    Tools
                  </div>
                  
                  <button
                    onClick={() => {
                      fileInputRef.current?.click();
                      setMenuOpen(false);
                    }}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-accent transition-colors text-left"
                  >
                    <div className="w-8 h-8 rounded-lg bg-muted border flex items-center justify-center flex-shrink-0">
                      <Upload className="w-4 h-4" />
                    </div>
                    <span className="text-sm font-medium">Upload images and files</span>
                  </button>
                </div>
              </div>
            )}
          </div>
          
          <Input
            placeholder="Ask anything"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            className="flex-1"
            disabled={isLoading}
          />
          <Button onClick={handleSendMessage} size="icon" disabled={isLoading}>
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </Button>
        </div>
        
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => handleFileSelect(e.target.files)}
          accept=".pdf,.jpg,.jpeg,.png,.doc,.docx"
        />
      </div>
    </div>
  );
}
