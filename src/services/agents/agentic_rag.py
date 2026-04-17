import logging
import time
from typing import Dict, List, Optional
from uuid import UUID

from langchain_core.messages import HumanMessage, ToolMessage
from langfuse.langchain import CallbackHandler
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src.services.citation.citation_engine import CitationEngine
from src.repositories.domain_profile import DomainProfileRepository
from src.repositories.project import ProjectRepository
from src.services.domain.external_web_search_policy import ExternalWebSearchPolicy
from src.services.domain.models import DomainPreset, ExternalSearchPolicyConfig
from src.services.domain.preset_loader import PresetLoader, PresetLoaderError
from src.services.embeddings.base import BaseEmbeddingsClient
from src.services.tracing.base import BaseTracer
from src.services.ollama.client import OllamaClient
from src.services.vector_store.base import BaseVectorStore

from .config import GraphConfig
from .context import Context
from .image_perception_tool import create_image_perception_tool
from .nodes import (
    ainvoke_generate_answer_step,
    ainvoke_grade_documents_step,
    ainvoke_guardrail_step,
    ainvoke_human_approval_step,
    ainvoke_insufficient_knowledge_step,
    ainvoke_planner_step,
    ainvoke_out_of_scope_step,
    ainvoke_retrieve_step,
    ainvoke_rewrite_query_step,
    continue_after_human_approval,
    continue_after_guardrail,
    continue_after_planner,
)
from .state import AgentState
from .tools import create_retriever_tool
from .web_search_tool import create_web_search_tool

logger = logging.getLogger(__name__)


class AgenticRAGService:
    """Agentic RAG service 

    This implementation uses:
    - context_schema for dependency injection
    - Runtime[Context] for type-safe access in nodes
    - Direct client invocation (no pre-built runnables)
    - Lightweight nodes as pure functions
    """

    def __init__(
        self,
        opensearch_client: BaseVectorStore,
        ollama_client: OllamaClient,
        embeddings_client: BaseEmbeddingsClient,
        langfuse_tracer: Optional[BaseTracer] = None,
        graph_config: Optional[GraphConfig] = None,
        domain_profile_repository: Optional[DomainProfileRepository] = None,
        project_repository: Optional[ProjectRepository] = None,
    ):
        """Initialize agentic RAG service.

        :param opensearch_client: Client for document search
        :param ollama_client: Client for LLM generation
        :param embeddings_client: Client for embeddings
        :param langfuse_tracer: Optional Langfuse tracer
        :param graph_config: Configuration for graph execution
        """
        self.opensearch = opensearch_client
        self.ollama = ollama_client
        self.embeddings = embeddings_client
        self.langfuse_tracer = langfuse_tracer
        self.graph_config = graph_config or GraphConfig()
        self.domain_profile_repository = domain_profile_repository
        self.project_repository = project_repository
        self.citation_engine = CitationEngine()
        self.preset_loader = PresetLoader(
            preset_dir=self.graph_config.settings.preset_dir,
            default_preset_id=self.graph_config.settings.default_preset_id,
        )

        logger.info("Initializing AgenticRAGService with configuration:")
        logger.info(f"  Model: {self.graph_config.model}")
        logger.info(f"  Top-k: {self.graph_config.top_k}")
        logger.info(f"  Hybrid search: {self.graph_config.use_hybrid}")
        logger.info(f"  Max retrieval attempts: {self.graph_config.max_retrieval_attempts}")
        logger.info(f"  Guardrail threshold: {self.graph_config.guardrail_threshold}")
        logger.info(f"  Mode: {self.graph_config.mode}")
        logger.info(f"  External web search enabled: {self.graph_config.allow_external_web_search}")
        logger.info(
            f"  Require human approval for external search: {self.graph_config.require_human_approval_for_external_search}"
        )
        logger.info(f"  Image perception enabled: {self.graph_config.allow_image_perception}")
        logger.info(f"  Preset directory: {self.graph_config.settings.preset_dir}")
        logger.info(f"  Default preset: {self.graph_config.settings.default_preset_id}")

        # Build graph once (no runnables needed!)
        self.graph = self._build_graph()
        logger.info("✓ AgenticRAGService initialized successfully")

    def _build_graph(self):
        """Build and compile the LangGraph workflow.

        Uses context_schema for type-safe dependency injection.
        Nodes are lightweight functions that receive Runtime[Context].

        :returns: Compiled graph ready for invocation
        """
        logger.info("Building LangGraph workflow with context_schema")

        # Create workflow with AgentState and Context schema
        workflow = StateGraph(AgentState, context_schema=Context)

        # Create tools (these still need to be created upfront for ToolNode)
        retriever_tool = create_retriever_tool(
            opensearch_client=self.opensearch,
            embeddings_client=self.embeddings,
            top_k=self.graph_config.top_k,
            use_hybrid=self.graph_config.use_hybrid,
        )
        web_search_tool = create_web_search_tool(
            enabled=True,
        )
        image_perception_tool = create_image_perception_tool(
            enabled=True,
        )
        tools = [retriever_tool, web_search_tool, image_perception_tool]

        # Add nodes (just function references - no closures needed!)
        logger.info("Adding nodes to workflow graph")
        workflow.add_node("guardrail", ainvoke_guardrail_step)
        workflow.add_node("planner", ainvoke_planner_step)
        workflow.add_node("human_approval", ainvoke_human_approval_step)
        workflow.add_node("out_of_scope", ainvoke_out_of_scope_step)
        workflow.add_node("insufficient_knowledge", ainvoke_insufficient_knowledge_step)
        workflow.add_node("retrieve", ainvoke_retrieve_step)
        workflow.add_node("tool_retrieve", ToolNode(tools))
        workflow.add_node("grade_documents", ainvoke_grade_documents_step)
        workflow.add_node("rewrite_query", ainvoke_rewrite_query_step)
        workflow.add_node("generate_answer", ainvoke_generate_answer_step)

        # Add edges
        logger.info("Configuring graph edges and routing logic")

        # Start → guardrail validation
        workflow.add_edge(START, "guardrail")

        # Guardrail → route based on score
        workflow.add_conditional_edges(
            "guardrail",
            continue_after_guardrail,
            {
                "continue": "planner",
                "out_of_scope": "insufficient_knowledge",
            },
        )

        # Out of scope → END
        workflow.add_edge("out_of_scope", END)
        workflow.add_edge("insufficient_knowledge", END)

        workflow.add_conditional_edges(
            "planner",
            continue_after_planner,
            {
                "retrieve": "retrieve",
                "human_approval": "human_approval",
                "insufficient_knowledge": "insufficient_knowledge",
            },
        )

        workflow.add_conditional_edges(
            "human_approval",
            continue_after_human_approval,
            {
                "approved": "retrieve",
                "rejected": "insufficient_knowledge",
            },
        )

        # Retrieve node creates tool call
        workflow.add_conditional_edges(
            "retrieve",
            tools_condition,
            {
                "tools": "tool_retrieve",
                END: END,
            },
        )

        # After tool retrieval → grade documents
        workflow.add_edge("tool_retrieve", "grade_documents")

        # After grading → route based on relevance
        workflow.add_conditional_edges(
            "grade_documents",
            lambda state: state.get("routing_decision", "generate_answer"),
            {
                "generate_answer": "generate_answer",
                "rewrite_query": "rewrite_query",
                "insufficient_knowledge": "insufficient_knowledge",
            },
        )

        # After rewriting → try retrieve again
        workflow.add_edge("rewrite_query", "planner")

        # After answer generation → done
        workflow.add_edge("generate_answer", END)

        # Compile graph
        logger.info("Compiling LangGraph workflow")
        compiled_graph = workflow.compile()
        logger.info("✓ Graph compilation successful")

        return compiled_graph

    async def ask(
        self,
        query: str,
        user_id: str = "api_user",
        model: Optional[str] = None,
        mode: Optional[str] = None,
        project_id: Optional[str] = None,
        preset_id: Optional[str] = None,
        domain_id: Optional[str] = None,
        human_approval_granted: bool = False,
        allow_external_web_search: Optional[bool] = None,
        allow_image_perception: Optional[bool] = None,
        image_inputs: Optional[List[str]] = None,
    ) -> dict:
        """Ask a question using agentic RAG.

        :param query: User question
        :param user_id: User identifier for tracing
        :param model: Optional model override
        :returns: Dictionary with answer, sources, reasoning steps, and metadata
        :raises ValueError: If query is empty
        """
        model_to_use = model or self.graph_config.model

        logger.info("=" * 80)
        logger.info("Starting Agentic RAG Request")
        logger.info(f"Query: {query}")
        logger.info(f"User ID: {user_id}")
        logger.info(f"Model: {model_to_use}")
        logger.info("=" * 80)

        # Validate input
        if not query or len(query.strip()) == 0:
            logger.error("Empty query received")
            raise ValueError("Query cannot be empty")

        # Create trace if Langfuse is enabled (v3 SDK)
        trace = None
        if self.langfuse_tracer and self.langfuse_tracer.client:
            logger.info("Creating Langfuse trace (v3 SDK)")
            metadata = {
                "env": self.graph_config.settings.environment,
                "service": "agentic_rag",
                "top_k": self.graph_config.top_k,
                "use_hybrid": self.graph_config.use_hybrid,
                "model": model_to_use,
                "mode": mode or self.graph_config.mode,
                "project_id": project_id,
                "domain_id": domain_id,
                "preset_id": preset_id,
            }
            # V3 SDK: Use start_as_current_span - will be used with 'with' statement
            trace = self.langfuse_tracer.client.start_as_current_span(
                name="agentic_rag_request",
            )

        # Use proper context manager pattern
        async def _execute_with_trace():
            """Execute the workflow with or without tracing context."""
            if trace is not None:
                with trace as trace_obj:
                    trace_obj.update(
                        input={"query": query},
                        metadata=metadata,
                        user_id=user_id,
                        session_id=f"session_{user_id}",
                    )
                    logger.debug(f"Trace created: {trace_obj}")
                    return await self._run_workflow(
                        query=query,
                        model_to_use=model_to_use,
                        user_id=user_id,
                        trace=trace_obj,
                        mode=mode,
                        project_id=project_id,
                        preset_id=preset_id,
                        domain_id=domain_id,
                        human_approval_granted=human_approval_granted,
                        allow_external_web_search=allow_external_web_search,
                        allow_image_perception=allow_image_perception,
                        image_inputs=image_inputs,
                    )
            else:
                return await self._run_workflow(
                    query=query,
                    model_to_use=model_to_use,
                    user_id=user_id,
                    trace=None,
                    mode=mode,
                    project_id=project_id,
                    preset_id=preset_id,
                    domain_id=domain_id,
                    human_approval_granted=human_approval_granted,
                    allow_external_web_search=allow_external_web_search,
                    allow_image_perception=allow_image_perception,
                    image_inputs=image_inputs,
                )

        try:
            return await _execute_with_trace()
        except Exception as e:
            logger.error(f"Error in Agentic RAG execution: {str(e)}")
            logger.exception("Full traceback:")
            raise

    async def _run_workflow(
        self,
        query: str,
        model_to_use: str,
        user_id: str,
        trace,
        mode: Optional[str] = None,
        project_id: Optional[str] = None,
        preset_id: Optional[str] = None,
        domain_id: Optional[str] = None,
        human_approval_granted: bool = False,
        allow_external_web_search: Optional[bool] = None,
        allow_image_perception: Optional[bool] = None,
        image_inputs: Optional[List[str]] = None,
    ) -> dict:
        """Execute the workflow with the given trace context."""
        try:
            start_time = time.time()

            logger.info("Invoking LangGraph workflow")
            resolved_preset = self._resolve_preset(
                preset_id=preset_id,
                project_id=project_id,
                domain_id=domain_id,
            )
            resolved_mode = mode or resolved_preset.mode_default or self.graph_config.mode
            resolved_allow_external_web_search = (
                resolved_preset.allow_external_web_search
                if allow_external_web_search is None
                else allow_external_web_search
            )
            resolved_allow_image_perception = (
                resolved_preset.allow_image_perception
                if allow_image_perception is None
                else allow_image_perception
            )
            resolved_require_human_approval = (
                resolved_preset.require_human_approval_for_external_search
                if allow_external_web_search is None
                else self.graph_config.require_human_approval_for_external_search
            )

            # State initialization
            state_input = {
                "messages": [HumanMessage(content=query)],
                "retrieval_attempts": 0,
                "guardrail_result": None,
                "routing_decision": None,
                "sources": None,
                "relevant_sources": [],
                "relevant_tool_artefacts": None,
                "grading_results": [],
                "metadata": {
                    "mode": resolved_mode,
                    "project_id": project_id,
                    "domain_id": resolved_preset.id,
                    "preset_id": resolved_preset.id,
                    "human_approval_granted": human_approval_granted,
                    "image_inputs_count": len(image_inputs or []),
                    "external_web_search_calls": 0,
                },
                "original_query": None,
                "rewritten_query": None,
            }

            external_policy = ExternalWebSearchPolicy(
                config=ExternalSearchPolicyConfig(
                    enabled=resolved_allow_external_web_search,
                    require_human_approval=resolved_require_human_approval,
                    allowed_domains=resolved_preset.allowed_external_domains,
                )
            )

            # Runtime context (dependencies)
            runtime_context = Context(
                ollama_client=self.ollama,
                opensearch_client=self.opensearch,
                embeddings_client=self.embeddings,
                langfuse_tracer=self.langfuse_tracer,
                trace=trace,
                langfuse_enabled=self.langfuse_tracer is not None and self.langfuse_tracer.client is not None,
                model_name=model_to_use,
                temperature=self.graph_config.temperature,
                top_k=self.graph_config.top_k,
                max_retrieval_attempts=self.graph_config.max_retrieval_attempts,
                guardrail_threshold=self.graph_config.guardrail_threshold,
                mode=resolved_mode,
                project_id=project_id,
                allow_external_web_search=resolved_allow_external_web_search,
                require_human_approval_for_external_search=resolved_require_human_approval,
                allow_image_perception=resolved_allow_image_perception,
                human_approval_granted=human_approval_granted,
                image_inputs=image_inputs or [],
                external_web_search_policy=external_policy,
                preset_id=resolved_preset.id,
                system_prompt_addon=resolved_preset.system_prompt_addon,
            )

            # Create config with CallbackHandler if Langfuse is enabled (v3 SDK)
            config = {"thread_id": f"user_{user_id}_session_{int(time.time())}"}

            # Add CallbackHandler for automatic LLM tracing
            # IMPORTANT: CallbackHandler automatically inherits the current span context
            # Since we're inside start_as_current_span, it will be linked automatically
            if self.langfuse_tracer and trace:
                try:
                    # V3 SDK: CallbackHandler() automatically uses current trace context
                    # No need to pass trace explicitly - it's handled by context propagation
                    callback_handler = CallbackHandler()
                    config["callbacks"] = [callback_handler]
                    logger.info("✓ CallbackHandler added (will auto-link to current trace)")
                except Exception as e:
                    logger.warning(f"Failed to create CallbackHandler: {e}")

            result = await self.graph.ainvoke(
                state_input,
                config=config,
                context=runtime_context,
            )

            execution_time = time.time() - start_time
            logger.info(f"✓ Graph execution completed in {execution_time:.2f}s")

            # Extract results
            answer = self._extract_answer(result)
            sources = self._extract_sources(result)
            cited_response = self.citation_engine.format_response(llm_answer=answer, source_chunks=sources)
            answer = cited_response.answer
            retrieval_attempts = result.get("retrieval_attempts", 0)
            reasoning_steps = self._extract_reasoning_steps(result)
            metadata = result.get("metadata") or {}
            citations = [item.model_dump() for item in cited_response.citations]
            source_count = cited_response.source_count
            chunks_used = self._estimate_chunks_used(result)
            planned_actions = list(metadata.get("planned_actions", []))
            approval_required = bool(metadata.get("approval_required", False))
            search_mode = "hybrid" if self.graph_config.use_hybrid else "bm25"
            if "external_web_search" in planned_actions:
                search_mode = "external_web"
            elif "image_perception" in planned_actions:
                search_mode = "image_perception"

            # Update trace (cleanup handled by context manager)
            if trace:
                trace.update(
                    output={
                        "answer": answer,
                        "sources_count": len(sources),
                        "citation_count": source_count,
                        "retrieval_attempts": retrieval_attempts,
                        "reasoning_steps": reasoning_steps,
                        "execution_time": execution_time,
                        "mode": resolved_mode,
                        "planned_actions": planned_actions,
                    }
                )
                trace.end()
                self.langfuse_tracer.flush()

            logger.info("=" * 80)
            logger.info("Agentic RAG Request Completed Successfully")
            logger.info(f"Answer length: {len(answer)} characters")
            logger.info(f"Sources found: {len(sources)}")
            logger.info(f"Retrieval attempts: {retrieval_attempts}")
            logger.info(f"Execution time: {execution_time:.2f}s")
            logger.info("=" * 80)

            return {
                "query": query,
                "answer": answer,
                "sources": sources,
                "citations": citations,
                "source_count": source_count,
                "reasoning_steps": reasoning_steps,
                "retrieval_attempts": retrieval_attempts,
                "rewritten_query": result.get("rewritten_query"),
                "execution_time": execution_time,
                "guardrail_score": result.get("guardrail_result").score if result.get("guardrail_result") else None,
                "mode": resolved_mode,
                "project_id": project_id,
                "domain_id": resolved_preset.id,
                "preset_id": resolved_preset.id,
                "planned_actions": planned_actions,
                "approval_required": approval_required,
                "search_mode": search_mode,
                "chunks_used": chunks_used,
                "allow_external_web_search": resolved_allow_external_web_search,
                "allow_image_perception": resolved_allow_image_perception,
            }

        except Exception as e:
            logger.error(f"Error in workflow execution: {str(e)}")
            logger.exception("Full traceback:")

            # Update trace with error (cleanup handled by context manager)
            if trace:
                trace.update(output={"error": str(e)}, level="ERROR")
                trace.end()
                self.langfuse_tracer.flush()

            raise

    def _resolve_preset(
        self,
        preset_id: Optional[str],
        project_id: Optional[str] = None,
        domain_id: Optional[str] = None,
    ) -> DomainPreset:
        domain_candidates: list[str] = []
        if domain_id:
            domain_candidates.append(domain_id)

        if project_id and self.project_repository:
            parsed_project_id = self._parse_uuid(project_id)
            if parsed_project_id:
                project = self.project_repository.get_by_id(parsed_project_id)
                if project and getattr(project, "domain_id", None):
                    domain_candidates.append(project.domain_id)

        if preset_id:
            domain_candidates.append(preset_id)

        for candidate in dict.fromkeys(domain_candidates):
            domain_profile_preset = self._resolve_domain_profile_preset(candidate)
            if domain_profile_preset:
                return domain_profile_preset

        try:
            return self.preset_loader.resolve(preset_id=preset_id)
        except PresetLoaderError as exc:
            raise ValueError(f"Preset resolution failed: {exc}") from exc

    def _resolve_domain_profile_preset(self, domain_id: str) -> Optional[DomainPreset]:
        if not self.domain_profile_repository:
            return None

        domain = self.domain_profile_repository.get_by_domain_id(domain_id)
        if not domain:
            return None

        return DomainPreset(
            id=domain.domain_id,
            display_name=domain.display_name,
            mode_default=domain.mode_default,
            system_prompt_addon=domain.system_prompt_addon,
            metadata_extract=domain.metadata_extract or [],
            search_boost=domain.search_boost or [],
            answer_policy=domain.answer_policy or {},
            allow_external_web_search=domain.allow_external_web_search,
            require_human_approval_for_external_search=domain.require_human_approval_for_external_search,
            allow_image_perception=domain.allow_image_perception,
            allowed_external_domains=domain.allowed_external_domains or [],
        )

    def _parse_uuid(self, value: str) -> Optional[UUID]:
        try:
            return UUID(str(value))
        except (TypeError, ValueError):
            return None

    def _extract_answer(self, result: dict) -> str:
        """Extract final answer from graph result."""
        messages = result.get("messages", [])
        if not messages:
            return "No answer generated."

        final_message = messages[-1]
        return final_message.content if hasattr(final_message, "content") else str(final_message)

    def _extract_sources(self, result: dict) -> List[dict]:
        """Extract sources from graph result."""
        sources = []
        relevant_sources = result.get("relevant_sources", [])

        for source in relevant_sources:
            if hasattr(source, "to_dict"):
                sources.append(source.to_dict())
            elif isinstance(source, dict):
                sources.append(source)

        return sources

    def _estimate_chunks_used(self, result: dict) -> int:
        """Estimate chunks used from tool messages when explicit source list is unavailable."""
        explicit_sources = result.get("relevant_sources") or []
        if explicit_sources:
            return len(explicit_sources)

        messages = result.get("messages", [])
        return sum(1 for message in messages if isinstance(message, ToolMessage))

    def _extract_reasoning_steps(self, result: dict) -> List[str]:
        """Extract reasoning steps from graph result."""
        steps = []
        retrieval_attempts = result.get("retrieval_attempts", 0)
        guardrail_result = result.get("guardrail_result")
        grading_results = result.get("grading_results", [])
        metadata = result.get("metadata") or {}
        planned_actions = metadata.get("planned_actions", [])

        if guardrail_result:
            steps.append(f"Validated query scope (score: {guardrail_result.score}/100)")

        if planned_actions:
            steps.append(f"Planned actions: {', '.join(planned_actions)}")

        if metadata.get("approval_required"):
            steps.append("Human approval required for external action")

        if retrieval_attempts > 0:
            steps.append(f"Retrieved documents ({retrieval_attempts} attempt(s))")

        if grading_results:
            relevant_count = sum(1 for g in grading_results if g.is_relevant)
            steps.append(f"Graded documents ({relevant_count} relevant)")

        if result.get("rewritten_query"):
            steps.append("Rewritten query for better results")

        final_message = result.get("messages", [])[-1] if result.get("messages") else None
        final_text = final_message.content if hasattr(final_message, "content") else str(final_message or "")
        if "insufficient" in final_text.lower() or "cannot find enough grounded evidence" in final_text.lower():
            steps.append("Generated insufficient-knowledge response")
        else:
            steps.append("Generated grounded answer from available context")

        return steps

    def get_graph_visualization(self) -> bytes:
        """Get the LangGraph workflow visualization as PNG.

        This method generates a visual representation of the graph workflow
        using mermaid diagram format, then converts it to PNG.

        :returns: PNG image bytes
        :raises ImportError: If required dependencies (pygraphviz/graphviz) are not installed
        :raises Exception: If graph visualization generation fails

        Example:
            >>> service = AgenticRAGService(...)
            >>> png_bytes = service.get_graph_visualization()
            >>> with open("graph.png", "wb") as f:
            ...     f.write(png_bytes)
        """
        try:
            logger.info("Generating graph visualization as PNG")
            png_bytes = self.graph.get_graph().draw_mermaid_png()
            logger.info(f"✓ Generated PNG visualization ({len(png_bytes)} bytes)")
            return png_bytes
        except ImportError as e:
            logger.error(f"Failed to generate visualization - missing dependencies: {e}")
            logger.error("Install with: pip install pygraphviz or apt-get install graphviz")
            raise ImportError(
                "Graph visualization requires pygraphviz. "
                "Install with: pip install pygraphviz (requires graphviz system package)"
            ) from e
        except Exception as e:
            logger.error(f"Failed to generate graph visualization: {e}")
            raise

    def get_graph_mermaid(self) -> str:
        """Get the LangGraph workflow as a mermaid diagram string.

        This method generates the graph workflow representation in mermaid
        diagram syntax, which can be rendered in markdown or mermaid viewers.

        :returns: Mermaid diagram syntax as string

        Example:
            >>> service = AgenticRAGService(...)
            >>> mermaid = service.get_graph_mermaid()
            >>> print(mermaid)
            graph TD
                __start__ --> guardrail
                ...
        """
        try:
            logger.info("Generating graph as mermaid diagram")
            mermaid_str = self.graph.get_graph().draw_mermaid()
            logger.info(f"✓ Generated mermaid diagram ({len(mermaid_str)} characters)")
            return mermaid_str
        except Exception as e:
            logger.error(f"Failed to generate mermaid diagram: {e}")
            raise

    def get_graph_ascii(self) -> str:
        """Get ASCII representation of the graph.

        This method generates a simple ASCII art representation of the
        graph structure, useful for quick inspection in terminals.

        :returns: ASCII art representation of the graph

        Example:
            >>> service = AgenticRAGService(...)
            >>> print(service.get_graph_ascii())
        """
        try:
            logger.info("Generating ASCII graph representation")
            ascii_str = self.graph.get_graph().print_ascii()
            logger.info("✓ Generated ASCII graph representation")
            return ascii_str
        except Exception as e:
            logger.error(f"Failed to generate ASCII graph: {e}")
            raise
