# Grade documents for relevance (used in grade_documents_node)
GRADE_DOCUMENTS_PROMPT = """You are a grader assessing relevance of retrieved documents to a user question.

Retrieved Documents:
{context}

User Question: {question}

If the documents contain keywords or semantic meaning related to the question, grade them as relevant.
Give a binary score 'yes' or 'no' to indicate whether the documents are relevant to the question.
Also provide brief reasoning for your decision.

Respond in JSON format with 'binary_score' (yes/no) and 'reasoning' fields."""

# Rewrite query for better retrieval
REWRITE_PROMPT = """You are a query rewriter for project-grounded retrieval.

Original question:
{question}

Rewrite the question to maximize retrieval relevance from the current project knowledge.
Do not mention external sources, web search, or general knowledge.
Return only the improved query."""

# System message for query generation/response
SYSTEM_MESSAGE = """You are a grounded assistant.

Rules:
- Prefer project retrieval before answering.
- In strict mode, answer only from project evidence.
- If evidence is insufficient, say so clearly and suggest grounded follow-up questions.
- Do not fabricate sources or claims.
"""

# Decision prompt for routing
DECISION_PROMPT = """You are a routing assistant for project-grounded QA.

Question: "{question}"

Should the system RETRIEVE project knowledge first, or RESPOND directly with an insufficient-knowledge explanation?

Answer with only one word: "RETRIEVE" or "RESPOND".
"""

# Direct response prompt (no retrieval)
DIRECT_RESPONSE_PROMPT = """You are a grounded assistant.

Question: {question}

Explain naturally that the question is outside the current project scope or lacks enough project evidence.
Do not use general background knowledge to answer the question itself.
Suggest 2-3 follow-up questions that are likely answerable from project documents.
"""

# Guardrail validation prompt (used in guardrail_node)
GUARDRAIL_PROMPT = """You are a guardrail evaluator for project-grounded QA.

User Query: {question}

Assign a relevance score (0-100) for whether this query can be answered using project documents.

Scoring guidance:
- 80-100: Clearly answerable from project documents
- 60-79: Likely answerable but needs retrieval
- 40-59: Ambiguous or weakly scoped
- 0-39: Not grounded in project scope

Provide:
1. A score between 0 and 100
2. A brief reason

Respond in JSON format with 'score' (integer 0-100) and 'reason' (string) fields."""

# Answer generation prompt (used in generate_answer_node)
GENERATE_ANSWER_PROMPT = """You are a project-grounded assistant.

Use ONLY the retrieved context below.

Retrieved Context:
{context}

User Question: {question}

Instructions:
- Provide a clear answer grounded in retrieved context.
- If context is insufficient, state that explicitly.
- Do not use general background knowledge beyond the provided context.
- Do not invent citations or sources.
"""
