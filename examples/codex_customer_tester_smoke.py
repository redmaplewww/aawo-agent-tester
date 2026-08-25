"""Run the Codex customer tester against a local deterministic Agent.

The example requires an existing Codex login. It never writes to the target;
the target is a callable fixture and all test evidence is kept in a temporary
SQLite ledger.
"""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from codex_agent_tester import CallableAdapter, CodexCustomerTester, CodexReasoner, EvidenceLedger


async def main() -> int:
    with tempfile.TemporaryDirectory(prefix="codex-customer-test-") as directory:
        ledger = EvidenceLedger(Path(directory) / "evidence.sqlite3")
        reasoner = CodexReasoner(cwd=Path.cwd())
        tester = CodexCustomerTester(ledger, reasoner)

        def customer_agent(payload: dict[str, object]) -> dict[str, object]:
            return {"answer": f"processed:{payload.get('question', '')}"}

        try:
            report = await tester.test(
                CallableAdapter("fixture-agent", customer_agent),
                target={"channel": "callable", "name": "fixture-agent"},
                customer_goal="客户提交问题并获得可用回答",
                declared_capabilities=("answer", "failure recovery"),
            )
            print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
            return 0 if report.status in {"pass", "fail", "incomplete", "inconclusive"} else 2
        finally:
            reasoner.close()
            ledger.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
