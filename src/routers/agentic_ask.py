from fastapi import APIRouter, HTTPException
from src.dependencies import AgenticRAGDep, LangfuseDep
from src.schemas.api.ask import AgenticAskResponse, AskRequest, FeedbackRequest, FeedbackResponse

router = APIRouter(prefix="/api/v1", tags=["agentic-rag"])


@router.post("/ask-agentic", response_model=AgenticAskResponse)
async def ask_agentic(
    request: AskRequest,
    agentic_rag: AgenticRAGDep,
) -> AgenticAskResponse:
    """
    Agentic RAG endpoint with intelligent retrieval and query refinement.

    Features:
    - Decides if retrieval is needed
    - Grades document relevance
    - Rewrites queries if needed
    - Provides reasoning transparency

    The agent will automatically:
    1. Determine if the question requires research paper retrieval
    2. If needed, search for relevant papers
    3. Grade retrieved documents for relevance
    4. Rewrite the query if documents aren't relevant
    5. Generate an answer with citations

    Args:
        request: Question and parameters
        agentic_rag: Injected agentic RAG service

    Returns:
        Answer with sources and reasoning steps

    Raises:
        HTTPException: If processing fails
    """
    try:
        result = await agentic_rag.ask(
            query=request.query,
            model=request.model,
            mode=request.mode,
            project_id=request.project_id,
            preset_id=request.preset_id,
            domain_id=request.domain_id,
            human_approval_granted=request.human_approval_granted,
            allow_external_web_search=request.allow_external_web_search,
            allow_image_perception=request.allow_image_perception,
            image_inputs=request.image_inputs,
        )

        raw_sources = result.get("sources", [])
        source_urls = []
        for source in raw_sources:
            if isinstance(source, str):
                source_urls.append(source)
                continue
            if isinstance(source, dict):
                source_url = source.get("url") or source.get("source_uri") or source.get("source")
                if source_url:
                    source_urls.append(source_url)

        return AgenticAskResponse(
            query=result["query"],
            answer=result["answer"],
            sources=source_urls,
            chunks_used=result.get("chunks_used", 0),
            search_mode=result.get("search_mode", "hybrid" if request.use_hybrid else "bm25"),
            reasoning_steps=result.get("reasoning_steps", []),
            retrieval_attempts=result.get("retrieval_attempts", 0),
            trace_id=result.get("trace_id"),
            mode=result.get("mode", request.mode),
            approval_required=result.get("approval_required", False),
            planned_actions=result.get("planned_actions", []),
            rewritten_query=result.get("rewritten_query"),
            preset_id=result.get("preset_id", request.preset_id),
            domain_id=result.get("domain_id", request.domain_id),
            source_count=result.get("source_count", 0),
            citations=result.get("citations", []),
        )

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing question: {str(e)}")


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    langfuse_tracer: LangfuseDep,
) -> FeedbackResponse:
    """
    Submit user feedback for an agentic RAG response.

    This endpoint allows users to rate the quality of answers and provide
    optional comments. Feedback is tracked in Langfuse for continuous improvement.

    Args:
        request: Feedback data including trace_id, score, and optional comment
        langfuse_tracer: Injected Langfuse tracer service

    Returns:
        FeedbackResponse indicating success or failure

    Raises:
        HTTPException: If feedback submission fails
    """
    try:
        if not langfuse_tracer:
            raise HTTPException(
                status_code=503,
                detail="Langfuse tracing is disabled. Cannot submit feedback."
            )

        success = langfuse_tracer.submit_feedback(
            trace_id=request.trace_id,
            score=request.score,
            comment=request.comment,
        )

        if success:
            # Flush to ensure feedback is sent immediately
            langfuse_tracer.flush()

            return FeedbackResponse(
                success=True,
                message="Feedback recorded successfully"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to submit feedback to Langfuse"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error submitting feedback: {str(e)}"
        )
