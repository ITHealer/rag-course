from src.services.citation.citation_engine import CitationEngine


def test_citation_engine_formats_unique_citations():
    engine = CitationEngine(excerpt_max_chars=50)
    sources = [
        {
            "source_type": "project",
            "doc_name": "cv_a.pdf",
            "page_number": 2,
            "source_uri": "file://cv_a.pdf",
            "excerpt": "Python, FastAPI, and OpenSearch experience across multiple projects.",
        },
        {
            "source_type": "project",
            "doc_name": "cv_a.pdf",
            "page_number": 2,
            "source_uri": "file://cv_a.pdf",
            "excerpt": "Python, FastAPI, and OpenSearch experience across multiple projects.",
        },
    ]

    response = engine.format_response("Answer", sources)

    assert response.answer == "Answer"
    assert response.source_count == 1
    assert len(response.citations) == 1
    assert response.citations[0].doc_name == "cv_a.pdf"


def test_citation_engine_handles_missing_fields():
    engine = CitationEngine()
    response = engine.format_response("Answer", [{"title": "Fallback Title"}])

    assert response.source_count == 1
    assert response.citations[0].doc_name == "Fallback Title"
