from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.services.agents.context import Context


@pytest.fixture
def mock_jina_embeddings_client():
    client = Mock()
    client.embed_query = AsyncMock(return_value=[0.1, 0.2, 0.3, 0.4])
    return client


@pytest.fixture
def mock_opensearch_client():
    client = Mock()
    client.search_unified = Mock(
        return_value={
            "hits": [
                {
                    "chunk_text": (
                        "Transformers are neural network architectures based on "
                        "self-attention mechanisms."
                    ),
                    "arxiv_id": "1706.03762",
                    "title": "Attention Is All You Need",
                    "authors": "Ashish Vaswani et al.",
                    "score": 0.95,
                    "section_name": "Abstract",
                },
                {
                    "chunk_text": "BERT improves language understanding with bidirectional training.",
                    "arxiv_id": "1810.04805",
                    "title": "BERT: Pre-training of Deep Bidirectional Transformers",
                    "authors": "Jacob Devlin et al.",
                    "score": 0.91,
                    "section_name": "Introduction",
                },
            ]
        }
    )
    return client


@pytest.fixture
def mock_ollama_client():
    llm = Mock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="Grounded response"))

    client = Mock()
    client.get_langchain_model = Mock(return_value=llm)
    return client


@pytest.fixture
def test_context(mock_ollama_client, mock_opensearch_client, mock_jina_embeddings_client):
    return Context(
        ollama_client=mock_ollama_client,
        opensearch_client=mock_opensearch_client,
        embeddings_client=mock_jina_embeddings_client,
        langfuse_tracer=None,
        trace=None,
        langfuse_enabled=False,
        model_name="llama3.2:1b",
        temperature=0.0,
        top_k=3,
        max_retrieval_attempts=2,
        guardrail_threshold=60,
    )


@pytest.fixture
def sample_human_message():
    return HumanMessage(content="How do transformers work?")


@pytest.fixture
def sample_ai_message():
    return AIMessage(content="I will search relevant project documents.")


@pytest.fixture
def sample_tool_message():
    return ToolMessage(
        content="Transformers rely on self-attention to model token relations.",
        name="retrieve_papers",
        tool_call_id="retrieve_1",
    )
