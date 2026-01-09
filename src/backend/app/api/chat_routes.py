from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Request
from typing import List, Any, Optional
import logging

print("=" * 80)
print("CHAT_ROUTERS.PY MODULE LOADED - NEW VERSION WITH DEBUG")
print("=" * 80)

# Foundry Agent based dependencies
#from app.agents.foundry.supervisor_agent_foundry import SupervisorAgent
#from app.config.container_foundry import Container

# Azure Chat based agents dependencies
from app.agents.loan_workflow.loan_workflow_orchestrator import OrchestrationAgent
from app.config.azure_chat_client_factory import Container

from app.models.chat import ChatAppRequest, ChatResponse, ChatResponseMessage, ChatChoice, ChatContext, ChatDelta
from app.models.chat import ChatMessage as AppChatMessage
# from agent_framework import ChatMessage, Role
from dependency_injector.wiring import Provide, inject
from fastapi.responses import StreamingResponse
import json
from typing import AsyncGenerator


router = APIRouter()
logger = logging.getLogger(__name__)



# Helper function to convert messages

def _convert_string_to_chat_response(content: str, thread_id: str | None) -> ChatResponse:
    """Convert a string response to ChatResponse format."""
    chat_message = ChatResponseMessage(
        content=content,
        role="assistant",
        attachments=[]
    )
    
    context = ChatContext(
        thoughts="",
        data_points=[]
    )
    
    delta = ChatDelta(
        content=content,
        role="assistant",
        attachments=[]
    )
    
    choice = ChatChoice(
        index=0,
        message=chat_message,
        context=context,
        delta=delta
    )

    return ChatResponse(choices=[choice], threadId=thread_id if thread_id else "")

# Helper function to convert ChatAppRequest to ChatMessageList
# def _chat_app_request_to_chat_message_list(chat_request: ChatAppRequest) -> ChatMessageList:
#     """Convert a ChatAppRequest to a ChatMessageList for agent-framework threading, mapping roles appropriately."""
#     messages: list[ChatMessage] = []
#     for msg in chat_request.messages[:-1]:
#         # Map roles from ChatAppRequest to agent-framework ChatMessage roles
#         if msg.role == "user":
#             af_role = Role.USER
#         elif msg.role == "assistant":
#             af_role = Role.ASSISTANT
#         else:
#             # raise exception that role is not recognized
#             raise ValueError(f"Unrecognized role from ChatAppRequest: {msg.role}. The message content is: {msg.content} ")

#         # Create a new ChatMessage instance
#         af_message = ChatMessage(
#             role=af_role,
#             text=msg.content
#         )
#         messages.append(af_message)
#     return ChatMessageList(messages)

def _format_stream_chunk(content: str, is_final: bool = False, thread_id: str | None = None) -> str:
    """Format a chunk for streaming response in NDJSON format."""
    if is_final:
        # Final chunk with thread_id only, no content (content was already streamed)
        response = {
            "choices": [{
                "index": 0,
                "delta": {
                    "content": "",  # Empty content since all chunks were already sent
                    "role": "assistant",
                    "attachments": []
                },
                "message": {
                    "content": "",  # Empty content
                    "role": "assistant",
                    "attachments": []
                },
                "context": {
                    "thoughts": "",
                    "data_points": []
                }
            }]
        }
        if thread_id:
            response["threadId"] = thread_id
    else:
        # Streaming chunk with delta only
        response = {
            "choices": [{
                "index": 0,
                "delta": {
                    "content": content,
                    "role": "assistant",
                    "attachments": []
                }
            }]
        }
    
    return json.dumps(response) + "\n"


async def _stream_response(
    supervisor_agent: OrchestrationAgent,
    user_message: str,
    thread_id: str | None
) -> AsyncGenerator[str, None]:
    """Stream the response from the supervisor agent."""
    full_content = ""
    final_thread_id = None
    
    try:
        print(f"\n>>> Starting stream for message: {user_message[:50]}...")
        async for content, is_final, tid in supervisor_agent.processMessageStream(user_message, thread_id):
            print(f">>> Stream chunk - is_final: {is_final}, content length: {len(content)}")
            if is_final:
                final_thread_id = tid
                # Send final chunk with just thread_id, no content
                yield _format_stream_chunk("", is_final=True, thread_id=final_thread_id)
            else:
                full_content += content
                # Send streaming chunk
                yield _format_stream_chunk(content, is_final=False)
    except Exception as e:
        print(f"\n!!! ERROR DURING STREAMING !!!: {str(e)}")
        import traceback
        traceback.print_exc()
        logger.error(f"Error during streaming: {str(e)}", exc_info=True)
        # Send error as a final chunk
        error_message = f"An error occurred: {str(e)}"
        error_response = {
            "choices": [{
                "index": 0,
                "delta": {
                    "content": error_message,
                    "role": "assistant",
                    "attachments": []
                },
                "message": {
                    "content": error_message,
                    "role": "assistant",
                    "attachments": []
                },
                "context": {
                    "thoughts": "",
                    "data_points": []
                }
            }],
            "error": str(e)
        }
        if thread_id:
            error_response["threadId"] = thread_id
        yield json.dumps(error_response) + "\n"


@router.post("/chat")
@inject
async def chat(
    request: Request,
    orchestration_agent: OrchestrationAgent = Depends(Provide[Container.orchestration_agent])
):
    """
    Chat endpoint that handles both JSON requests and multipart/form-data with file uploads.
    """
    print(f"\n{'='*80}")
    print(f"CHAT ENDPOINT CALLED")
    print(f"{'='*80}")
    
    import json as json_module
    
    # Check content type to determine how to parse the request
    content_type = request.headers.get("content-type", "")
    
    chat_request = None
    uploaded_file_info = []
    
    if "multipart/form-data" in content_type:
        # Handle multipart form data with files
        form = await request.form()
        files = form.getlist("files")
        messages_str = form.get("messages")
        stream_str = form.get("stream")
        thread_id = form.get("threadId")
        
        if not messages_str:
            raise HTTPException(status_code=400, detail="messages required with file upload")
        
        try:
            messages_data = json_module.loads(messages_str)
            stream_bool = stream_str == "true" if stream_str else False
            
            # Create ChatAppRequest from form data
            chat_request = ChatAppRequest(
                stream=stream_bool,
                messages=[AppChatMessage(**msg) for msg in messages_data],
                threadId=thread_id
            )
            
            # Process uploaded files
            if files:
                for file in files:
                    content = await file.read()
                    uploaded_file_info.append({
                        "filename": file.filename,
                        "content_type": file.content_type,
                        "size": len(content),
                        "content": content
                    })
                    logger.info(f"Received file: {file.filename} ({len(content)} bytes)")
        except Exception as e:
            logger.error(f"Error parsing form data: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid form data: {str(e)}")
    else:
        # Handle regular JSON request
        try:
            body = await request.json()
            chat_request = ChatAppRequest(**body)
        except Exception as e:
            logger.error(f"Error parsing JSON request: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid JSON request: {str(e)}")
    
    if not chat_request or not chat_request.messages:
        raise HTTPException(status_code=400, detail="history cannot be null in Chat request")
    
    # Check the request for attachments reference
    last_message = chat_request.messages[-1]
    
    # If files were uploaded, attach them to the agent
    if uploaded_file_info:
        file_names = [f["filename"] for f in uploaded_file_info]
        last_message.content += f" [UPLOADED_FILES: {', '.join(file_names)}]"
        
        # Store file info in agent's context
        if hasattr(orchestration_agent, '_uploaded_files'):
            orchestration_agent._uploaded_files = uploaded_file_info
        else:
            object.__setattr__(orchestration_agent, '_uploaded_files', uploaded_file_info)
    
    if last_message.attachments and not uploaded_file_info:
        # Append attachment references to the user message (legacy behavior)
        last_message.content += " " + ",".join(last_message.attachments)

    # Handle streaming vs non-streaming
    if chat_request.stream:
        try:
            # Return streaming response with NDJSON
            return StreamingResponse(
                _stream_response(orchestration_agent, last_message.content, chat_request.threadId),
                media_type="application/x-ndjson"
            )
        except Exception as e:
            print(f"\n!!! ERROR IN STREAM !!!: {str(e)}")
            import traceback
            traceback.print_exc()
            logger.error(f"Error initiating stream: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")
    else:
        try:
            # Return regular JSON response
            response_content, thread_id = await orchestration_agent.processMessage(
                last_message.content,
                chat_request.threadId
            )
            
            # Convert string response to structured ChatResponse
            return _convert_string_to_chat_response(response_content, thread_id)
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")