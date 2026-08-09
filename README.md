# AAWO Agent Tester

面向任意领域 Agent 的“模拟人工客户”测试 Agent。它先理解被测 Agent 的输入、输出、契约和用户目标，再按客户旅程执行；不会把跑不通的步骤悄悄走通，也不会把模型自评当作通过。

## 核心能力

- Callable、HTTP 和 CLI Adapter
- Agent Contract Profile 与 JSON Schema 子集校验
- 客户旅程逐步执行、纠正、supersession 和最小回归
- SQLite 追加式 Evidence Ledger
- `PASS / FAIL / BLOCKED / INCONCLUSIVE / NEEDS_HUMAN` fail-closed 结论
- 基础客户摩擦识别：无反馈、反人类流程、假成功和副作用风险
- 可选 OpenAI-compatible LLM：只生成受限 EvolutionProposal，不直接修改测试基线
- 可选 AAWO 0.6.0.dev41 Team Tree、Workflow、Checkpoint 和人工审批边界

## 快速开始

```powershell
uv sync --dev
$env:PYTHONPATH = "src"
uv run pytest -q
uv run python -m compileall -q src tests examples
uv run ruff check src tests examples
uv run python -m aawo_agent_tester.cli demo
```

安装可选 AAWO 适配：

```powershell
uv sync --extra aawo
```

真实 LLM 配置请使用本机的受管 `llm-api-config` profile；不要把 API Key 写入命令行、源码、日志或 Git。

## 设计边界

测试内核负责领域无关的契约、客户旅程、证据和纠正语义；AAWO 只承担组织树、工作流、作用域证据、Checkpoint 和受控生命周期。真实外部写操作、生产 IAM、远程 Store 和模型质量仍需要独立验收。

更完整的能力说明见 [AAWO Agent Tester README](AAWO_AGENT_TESTER_README.md) 和 [技术方案](AAWO_AGENT_UNDERSTANDING_TESTER_TECHNICAL_PLAN.md)。

## 许可证与发布

项目当前为开发版本，AAWO 依赖为可选依赖。发布前请根据实际授权补充许可证和依赖声明。
