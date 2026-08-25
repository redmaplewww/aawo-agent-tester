---
name: codex-agent-tester
description: Use the OpenAI Codex Python SDK to simulate a real customer testing an unfamiliar Agent, discover its input/output contract, exercise realistic journeys, inspect implementation completeness, detect customer friction and hostile workflows, and produce evidence-backed PASS/FAIL/BLOCKED/INCONCLUSIVE findings. Use when the user asks to test an Agent, verify whether its promised functions really work, or record issues without silently repairing them.
---

# Codex Agent Tester

Use the repository's `CodexCustomerTester` as the model-guided test planner
and `CustomerSimulationRunner` as the deterministic execution authority.

## Operating rules

1. Identify the exact Agent boundary and the customer's goal before planning.
2. Use the official `openai-codex` Python SDK. Do not fall back to AAWO,
   OpenAI-compatible Chat Completions, random fuzzing, or a health-only ping.
3. Let one read-only, deny-all Codex thread discover the contract and produce
   customer journeys. Reject malformed plans, unknown step kinds and unknown
   assertions; never silently rewrite them.
   The official SDK path may use one bounded turn per required coverage
   dimension and merge only locally validated results; conflicting contract
   hypotheses remain unconfirmed.
4. Execute journeys through a real `CallableAdapter`, `HttpAdapter`,
   `CliAdapter`, or `AsyncJobAdapter`. Preserve raw request/response evidence
   in the SQLite ledger.
5. Treat failed, blocked, timed-out and unknown observations as terminal
   evidence. Never retry a write whose result is unknown and never promote a
   model explanation to PASS.
6. Require coverage for normal success, invalid/incomplete input, output
   contract, failure recovery, and repeated input or correction. Map every
   user-declared capability to an executed scenario. Missing coverage is an
   implementation-completeness finding, not a pass.
7. Keep writes behind an isolated fixture or explicit human approval. A
   read-only journey must block a write-capable adapter before invocation.
8. When the user corrects the interpretation, write a new Profile revision,
   supersede the old hypothesis, and run the minimum explicit regression set.
9. Report exact target, journey goal, run status, evidence IDs, findings,
   skipped coverage and external limitations. Do not claim arbitrary-domain or
   production coverage from one run.

## Suggested invocation

```python
from codex_agent_tester import CodexCustomerTester, CodexReasoner, EvidenceLedger

ledger = EvidenceLedger("artifacts/evidence.sqlite3")
tester = CodexCustomerTester(ledger, CodexReasoner(cwd="."))
report = await tester.test(
    adapter,
    target={"channel": "http", "url": "http://127.0.0.1:3000/api/demo"},
    customer_goal="客户完成一次真实业务操作并得到可用结果",
    declared_capabilities=("normal operation", "error recovery"),
)
```

The returned report contains the Codex plan, deterministic `TestRun` records,
coverage status, Codex evidence review and limitations. If Codex is not
authenticated or its plan is invalid, keep the report blocked/inconclusive and
inspect the reason; do not substitute a hand-written model result.
