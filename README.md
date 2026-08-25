# Codex Agent Tester

面向任意领域 Agent 的“模拟真实客户”测试器。它先用 Codex SDK 理解输入、输出、客户目标和能力声明，再按真实客户旅程执行；跑不通的地方会保留为失败、阻塞或未知，不会被测试器悄悄走通。

## 核心能力

- Codex thread 驱动的 Agent 契约发现、客户旅程规划和证据复核；
- Callable、HTTP、CLI 和 Async Job Adapter；
- JSON Schema 子集、业务断言、客户摩擦和反人类流程识别；
- SQLite 追加式 Evidence Ledger，原始请求/响应和失败不可覆盖；
- `PASS / FAIL / BLOCKED / INCONCLUSIVE` fail-closed 结论；
- 实现完整性检查：正常成功、异常输入、输出契约、失败恢复、重复输入/纠正和用户声明能力覆盖；
- 用户纠正后的 Profile supersession、最小回归和独立新 Run；
- Codex 只做理解和复核，不能直接执行目标写操作、修改基线或把模型自评当作通过。

## 安装和验证

```powershell
py -3.12 -m pip install -e .
$env:PYTHONPATH = "src"
py -3.12 -m pytest -q
py -3.12 -m compileall -q src tests examples
codex-agent-tester demo
codex-agent-tester codex-status
```

`openai-codex==0.147.0` 是唯一的模型运行时依赖。Codex SDK 复用本机 Codex 登录态；项目不读取或保存 API Key，也不再使用 AAWO 或 OpenAI-compatible Chat Completions。

## 真实客户仿真

```powershell
$env:PYTHONPATH = "src"
py -3.12 examples\codex_customer_tester_smoke.py
```

目标 Agent 可以替换为 `HttpAdapter`、`CliAdapter` 或真实的 Callable 边界。真实生产写操作默认不允许，未知结果不会自动重试或判定为成功。

## 文档

- [完整能力说明](CODEX_AGENT_TESTER_README.md)
- [技术方案](CODEX_AGENT_TESTER_TECHNICAL_PLAN.md)

当前仓库只包含 Codex SDK 路线；历史 AAWO 适配器和运行时已移除。
