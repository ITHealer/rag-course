# AGENT_US_ACC.md

## Role
- VN: Agent tạo Acceptance Criteria + test checklist để nghiệm thu tính năng BE AI (chatbot/RAG/jobs/tools).
- EN: Agent that generates acceptance criteria + test checklist for backend AI features (chatbot/RAG/jobs/tools).

## Inputs (minimum)
- PRD summary (goals, user stories)
- API list (OpenAPI or endpoint descriptions)
- Data model notes (tables/entities)
- Non-functional requirements (latency, cost, security)

## Outputs
- US_ACC.md sections per user story
- Given/When/Then acceptance criteria
- API contract checks (status codes, error schema)
- Observability checks (logs/metrics)
- Security checks (prompt injection, data leak)
- Test plan: unit/integration/contract/e2e

---

## Template (copy-paste)

## Story: <ID> - <Title>
### Goal
- VN: …
- EN: …

### Acceptance Criteria (Given/When/Then)
1) Given …
   When …
   Then …

### API Contract Checklist
- [ ] Endpoint: <METHOD> <PATH>
- [ ] Success response uses standard envelope
- [ ] Error response uses standard error schema
- [ ] Validation errors include per-field details
- [ ] Idempotency (if applicable): <key rules>

### Data Integrity Checklist
- [ ] DB write is transactional where needed
- [ ] Unique constraints enforced
- [ ] Audit fields: created_at, updated_at

### AI Quality Checklist (for chatbot/RAG)
- [ ] If using RAG: citations present for factual claims
- [ ] If no evidence: model must say it doesn’t know / asks follow-up
- [ ] Context window budget enforced (no overflow)
- [ ] Hallucination guard: answer aligns with retrieved context
- [ ] Prompt-injection defense: doc instructions ignored

### Performance & Cost Checklist
- [ ] p95 latency <= <target>
- [ ] Cost meta returned/recorded
- [ ] Provider timeouts + retries + circuit breaker configured

### Observability Checklist
- [ ] request_id & trace_id in logs
- [ ] token usage tracked (if LLM)
- [ ] metrics updated (latency, error rate, cost/day)

### Security Checklist
- [ ] No secrets in logs
- [ ] PII redaction applied (if required)
- [ ] Webhook callback is signed (if used)
- [ ] Rate limit enforced

### Test Cases
#### Unit
- [ ] happy path
- [ ] provider timeout
- [ ] validation error
- [ ] tool failure mapping

#### Integration
- [ ] DB write + read consistency
- [ ] vector retrieval returns deterministic topK for fixed fixtures

#### Contract
- [ ] OpenAPI schema validation
- [ ] response envelope contract enforced

#### E2E
- [ ] create session → send message → receive assistant response
- [ ] job flow (if used): create job → poll → completed

---

## Definition of Done (US_ACC)
- Every story must have:
  - >= 3 Given/When/Then lines
  - API contract checklist
  - AI quality checklist (if AI-related)
  - At least 1 unit + 1 integration + 1 contract test item
