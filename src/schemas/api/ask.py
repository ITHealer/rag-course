from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """Request model for RAG question answering."""

    query: str = Field(..., description="User's question", min_length=1, max_length=1000)
    top_k: int = Field(3, description="Number of top chunks to retrieve", ge=1, le=10)
    use_hybrid: bool = Field(True, description="Use hybrid search (BM25 + vector)")
    model: str = Field("llama3.2:1b", description="Ollama model to use for generation")
    categories: Optional[List[str]] = Field(None, description="Filter by arXiv categories")
    project_id: Optional[str] = Field(None, description="Project scope identifier")
    preset_id: Optional[str] = Field(None, description="Domain preset identifier")
    domain_id: Optional[str] = Field(None, description="Domain profile identifier managed via API")
    mode: Literal["strict", "augmented"] = Field("strict", description="Knowledge mode")
    human_approval_granted: bool = Field(False, description="Human approval flag for boundary-crossing actions")
    allow_external_web_search: bool = Field(False, description="Enable external web search for this request")
    allow_image_perception: bool = Field(True, description="Enable image perception for this request")
    image_inputs: Optional[List[str]] = Field(None, description="User-provided image references for perception")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are transformers in machine learning?",
                "top_k": 3,
                "use_hybrid": True,
                "model": "llama3.2:1b",
                "categories": ["cs.AI", "cs.LG"],
                "project_id": "project-demo-001",
                "preset_id": "scoped_knowledge",
                "domain_id": "cv_recruitment",
                "mode": "strict",
                "human_approval_granted": False,
                "allow_external_web_search": False,
                "allow_image_perception": True,
                "image_inputs": [],
            }
        }


class AskResponse(BaseModel):
    """Response model for RAG question answering."""

    query: str = Field(..., description="Original user question")
    answer: str = Field(..., description="Generated answer from LLM")
    sources: List[str] = Field(..., description="Source URLs")
    chunks_used: int = Field(..., description="Number of chunks used for generation")
    search_mode: str = Field(..., description="Search mode used: bm25 or hybrid")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are transformers in machine learning?",
                "answer": "Transformers are a neural network architecture...",
                "sources": ["https://arxiv.org/pdf/1706.03762.pdf", "https://arxiv.org/pdf/1810.04805.pdf"],
                "chunks_used": 3,
                "search_mode": "hybrid",
            }
        }


class AgenticAskResponse(AskResponse):
    """Response model for agentic RAG question answering."""

    reasoning_steps: List[str] = Field(..., description="Agent's decision-making steps")
    retrieval_attempts: int = Field(..., description="Number of document retrieval attempts")
    trace_id: Optional[str] = Field(None, description="Langfuse trace ID for feedback and debugging")
    mode: str = Field("strict", description="Resolved knowledge mode")
    approval_required: bool = Field(False, description="Whether human approval was required")
    planned_actions: List[str] = Field(default_factory=list, description="Planner-selected action sequence")
    rewritten_query: Optional[str] = Field(None, description="Rewritten query when planner triggered rewrite")
    preset_id: Optional[str] = Field(None, description="Resolved domain preset id")
    domain_id: Optional[str] = Field(None, description="Resolved domain profile id")
    source_count: int = Field(0, description="Number of citation entries")
    citations: List[dict] = Field(default_factory=list, description="Structured citation entries")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are transformers in machine learning?",
                "answer": "Transformers are neural network architectures...",
                "sources": ["https://arxiv.org/pdf/1706.03762.pdf"],
                "chunks_used": 3,
                "search_mode": "hybrid",
                "reasoning_steps": [
                    "Decided to retrieve relevant papers",
                    "Retrieved documents from database",
                    "Generated answer from relevant documents",
                ],
                "retrieval_attempts": 1,
                "trace_id": "abc123-def456-ghi789",
                "mode": "strict",
                "approval_required": False,
                "planned_actions": ["project_retrieval"],
                "rewritten_query": None,
                "preset_id": "scoped_knowledge",
                "domain_id": "scoped_knowledge",
                "source_count": 1,
                "citations": [
                    {
                        "ref": 1,
                        "source_type": "project",
                        "doc_name": "sample.pdf",
                        "page_number": 3,
                        "source_uri": "file://sample.pdf",
                        "excerpt": "Key grounded evidence excerpt.",
                    }
                ],
            }
        }


class FeedbackRequest(BaseModel):
    """Request model for user feedback on RAG answers."""

    trace_id: str = Field(..., description="Langfuse trace ID from the response")
    score: float = Field(..., description="Feedback score (0-1 or -1 to 1)", ge=-1, le=1)
    comment: Optional[str] = Field(None, description="Optional feedback comment", max_length=1000)

    class Config:
        json_schema_extra = {
            "example": {
                "trace_id": "abc123-def456-ghi789",
                "score": 1.0,
                "comment": "This answer was very helpful and accurate!",
            }
        }


class FeedbackResponse(BaseModel):
    """Response model for feedback submission."""

    success: bool = Field(..., description="Whether feedback was recorded successfully")
    message: str = Field(..., description="Status message")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Feedback recorded successfully",
            }
        }
