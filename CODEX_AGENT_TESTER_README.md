# Codex Agent Tester

这是一个以 OpenAI Codex Python SDK 为理解引擎、以确定性适配器和证据账本为执行内核的通用 Agent 测试器。它的目标不是生成随机测试，而是替客户完成真实使用旅程，找到客户会遇到的功能、契约、错误恢复、交互摩擦和“声明已实现但实际上不可用”的问题。

## 工作方式

1. Codex thread 读取目标边界、客户目标、已声明能力和已有证据，生成带覆盖维度的客户旅程。
2. `CodexCustomerTester` 严格校验旅程结构；不支持的步骤或断言直接阻塞，不静默改写。
3. `CustomerSimulationRunner` 通过 Callable、HTTP、CLI 或异步 Job Adapter 执行真实输入，记录原始请求/响应和 SQLite 证据。
4. 确定性校验结算 `PASS / FAIL / BLOCKED / INCONCLUSIVE`，Codex 不能覆盖结论。
5. Codex 复核执行证据，指出客户可见问题和缺失实现覆盖；缺失必测维度会直接标记 `incomplete`。
6. 用户纠正由 Profile supersession、最小回归计划和新的独立 Run 保留，原假设和失败证据不覆盖。

## Codex SDK 边界

- 使用官方 `openai-codex` Python SDK 的 Codex thread/turn。
- Codex thread 默认 `read_only + deny_all + ephemeral`，只负责理解、规划和复核。
- 不接受 OpenAI-compatible URL，不拼接 Chat Completions 请求，不读取项目 API Key。
- Codex 输出必须通过本地结构校验；模型自评不能成为 PASS。
- SDK 不可用或没有有效登录态时，测试报告为 `blocked/inconclusive`，不会降级为“模型猜测”。
- 每个 Codex turn 有超时边界；超时会关闭本地 SDK 会话并保留阻塞原因，不会无限等待或伪造结果。

## 快速开始

```powershell
py -3.12 -m pip install -e .
$env:PYTHONPATH = "src"
py -3.12 -m pytest -q
py -3.12 -m compileall -q src tests examples
codex-agent-tester demo
codex-agent-tester codex-status
```

真实 Codex 客户仿真示例：

```powershell
$env:PYTHONPATH = "src"
py -3.12 examples\codex_customer_tester_smoke.py
```

该示例会使用本机已有 Codex 登录态；目标 Agent 是本地 fixture，不产生外部写操作。

## 状态语义

| 状态 | 含义 |
|---|---|
| `pass` | 所有已执行旅程和必需覆盖维度均有确定性证据，未发现问题 |
| `fail` | 真实执行出现契约、结果、错误恢复或客户摩擦问题 |
| `incomplete` | 旅程可以执行，但声明能力或必需客户维度没有实现证据 |
| `blocked` | Codex 计划无效、权限/副作用门禁或目标边界不可执行 |
| `inconclusive` | 目标或依赖不可用、超时、未知副作用或 Codex 复核无法结算 |

完整的客户仿真与实现完整性设计见 [技术方案](CODEX_AGENT_TESTER_TECHNICAL_PLAN.md)。
