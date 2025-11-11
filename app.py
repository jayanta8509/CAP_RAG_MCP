from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import logging
import time

from client import ask_question

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="CapAmerica AI - Product Catalog API",
    description="AI-powered CapAmerica product catalog with conversation memory",
    version="1.0.0"
)

# CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class NexusFlowRequest(BaseModel):
    user_id: str
    query: str
    use_agent: bool = True


@app.post("/chat/agent")
async def ask_question_endpoint(request: NexusFlowRequest):
    """
    Ask a CapAmerica product catalog question with memory support

    Request Format:
    {
        "user_id": "xyz",
        "query": "What's the price for 48 units of i7041?"
    }

    Example Queries:
    - "What caps do you have for outdoor events?"
    - "Show me trucker style caps"
    - "What's the price for 48 units of i7041?"
    - "Do you have caps with UV protection?"

    Memory Features:
    - Conversations are remembered per user_id
    - Follow-up questions will remember previous context
    - Each user gets their own conversation thread
    """
    try:
        logger.info(f"Received query from user {request.user_id}: {request.query}")

        if not request.query or request.query.strip() == "":
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        if not request.user_id or request.user_id.strip() == "":
            raise HTTPException(status_code=400, detail="User ID cannot be empty")

        # Process the query with memory
        answer = await ask_question(question=request.query, user_id=request.user_id)

        logger.info(f"Successfully processed query for user {request.user_id}")
        return {
            "response": answer,
            "status_code": 200,
            "query": request.query,
            "user_id": request.user_id,
            "timestamp": time.time(),
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "CapAmerica AI",
        "version": "1.0.0",
        "features": ["product_catalog", "conversation_memory", "mcp_tools"]
    }


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8021,
        reload=True,
        log_level="info"
    )