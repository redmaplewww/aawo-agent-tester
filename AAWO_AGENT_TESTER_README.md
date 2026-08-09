# AAWO Agent Tester P2

这是 AAWO Agent 理解与客户仿真测试器的独立确定性内核、Skill 化入口和可选 AAWO 运行时。它不复制 AAWO 源码：领域测试语义留在 `aawo_agent_tester`，组织、工作流、作用域证据、Checkpoint 和生命周期通过 AAWO 0.6.0.dev41 公共 API 承担。

## 本地运行

```powershell
$env:PYTHONPATH = "src"
py -3.12 -m pytest -q
py -3.12 -m compileall -q src tests examples
py -3.12 -m ruff check src tests examples
py -3.12 -m aawo_agent_tester.cli demo
py -3.12 examples\p0_demo.py
```

真实 AAWO Team Tree smoke（需安装用户交付的 dev41 wheel）：

```powershell
py -3.12 -m pip install --no-deps <aawo-dev41-wheel> .[aawo]
py -3.12 examples\aawo_team_tree_smoke.py
py -3.12 examples\aawo_controlled_evolution_smoke.py
py -3.12 examples\aawo_real_llm_proposal_smoke.py
```

真实 LLM 提案 smoke（先用 `llm-api-config` 的受管配置档注入 `.env.local`）：

```powershell
$env:PYTHONPATH = "src"
py -3.12 examples\real_llm_proposal_smoke.py
```

## 当前能力

- Callable、HTTP GET/POST、无 Shell 的 CLI 子进程 Adapter；
- HTTP 黑盒 Journey Runner 和结构化字段断言；
- Agent Contract Profile 与 JSON Schema 子集校验；
- 客户旅程逐步执行和原始请求/响应记录；
- SQLite 追加式 Evidence Ledger；
- `PASS / FAIL / BLOCKED / INCONCLUSIVE / NEEDS_HUMAN` 结论；
- 声明、观察、确认、纠正和 supersession 的 Profile 版本；
- Profile 从追加式账本恢复；
- 纠正影响分析与最小回归计划；
- 可选 OpenAI-compatible 推理接口和 fail-closed EvolutionProposal；
- 已接入真实 OpenAI-compatible LLM：从 `LLM_*`/`OPENAI_*` 或兼容的 `AAWO_TESTER_LLM_*` 环境变量读取配置，真实调用只生成提案；
- `propose_evolution` 会把 Agent 契约、客户旅程、证据摘要和用户纠正组成受限上下文，并校验 proposal kind、base revision 与 evidence scope；
- `AAWOTestTeamRunner` 可接收真实 ReasoningProvider，在基线旅程后生成提案；未提供人工批准时，AAWO 控制面明确拒绝，绝不自动应用；
- 异步 Job submit/poll Adapter、可重置 FixtureEnvironment 和副作用策略门禁；
- 基础客户摩擦发现；
- AAWO 兼容的单 Department 注册桥，以及严格模式下五个权责 Department；
- 真实 AAWO Adaptive Workflow：一个可执行工作节点负责完整客户旅程测试，不把客户步骤或 Team Tree 冒充成彼此；
- 真实 AAWO Team Tree/TeamExecutor：环境、契约、客户执行、协议、结果、摩擦和证据七个角色按子到父责任链收束；
- AAWO scope-bound `EvidenceRef`、Runtime Event、State/Transfer、Checkpoint 和显式 IDLE 释放；
- AAWO 运行层仍保留确定性 `PASS / FAIL / BLOCKED / INCONCLUSIVE`，测试流程成功不等于被测 Agent 通过。
- 受控工作流演化纵切：`quality-evolution` Agent 具备 AAWO Workflow/Team Optimizer 能力，但只能通过 `AgentServices` 提案；`ProductionControlPlane` 审批记录携带 Team Owner fencing token；
- shadow/canary 不复用基线结果：语义修订必须重新打开工作节点，并使用按 workflow revision 隔离的 TeamExecutor composition identity，完整重跑客户旅程；
- canary 指标由确定性 TestRun、finding 数和账本完整性计算，不接受模型自评；无人工批准、证据缺失、非执行变化、回归或低于阈值均 fail-closed；
- 有害 canary 由 AAWO `rollback_workflow` 恢复旧语义为新的审计修订，原失败 run、审批、指标、冻结和 rollback history 均保留；
- contract/scenario/evaluator/team 演化当前仍为 proposal-only，不会伪装成已经可应用的通用自进化。
- 可发现 Skill：`C:\Users\zzg\.codex\skills\aawo-agent-tester\SKILL.md`；
- 标准化 JSON 报告和 SQLite 证据：`artifacts\agent-tests\`。

Skill 已对本机 M8 ID Agent (`http://127.0.0.1:8000`) 完成健康、Agent 注册表、CAD 预留契约和破坏性操作门禁实测；对 Yunpai Orchestrator 完成原 9000 端口状态检查及隔离配置下的真实 uvicorn 健康实测。报告中的 `inconclusive`、`fail` 和隔离限制必须保留，不能扩大为生产或真实 LLM 质量结论。

当前仍未验证：外部真实 LLM 的领域质量（协议接通不等于理解质量）、MCP/浏览器 Adapter、生产副作用、远程/分布式 Store、多租户生产安全、跨团队可复用 SOP 晋升、Team Optimizer 组织变更的 canary/compensation，以及 contract/scenario/evaluator 的受控 registry 应用。当前工作流演化验收只覆盖单个受控团队内的用户交付 SQLite 参考运行时。

原始 AAWO 开发包：`F:\opencode\云湃智算\云湃一体机\deliverables\AAWO_0.6.0.dev41_development_2026-07-30.zip`。它保持不变。
