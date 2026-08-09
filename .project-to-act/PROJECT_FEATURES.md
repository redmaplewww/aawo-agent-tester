# 项目功能

> 功能范围与状态的唯一清单。功能变化后同步进度；未验证的功能不得标记为已完成。

## 状态定义

- 候选：尚未批准进入范围
- 已规划：已确认但未开始
- 进行中：正在实现
- 已阻塞：等待外部条件
- 已完成：完成条件已满足且有证据
- 已取消：明确退出范围并保留原因

## 功能清单

| 功能 ID | 功能 | 优先级 | 状态 | 依赖 | 完成条件 | 证据 ID |
|---|---|---|---|---|---|---|
| F-001 | Agent Contract Profile 与假设证据 | P0 | 已完成 | 无 | 支持 declared/observed/confirmed/rejected/unknown、版本和来源 | E-002,E-008 |
| F-002 | Callable/HTTP/CLI Adapter | P0 | 已完成 | F-001 | 统一会话、发送、观察、重置、关闭接口；副作用和异常可记录 | E-002,E-005,E-006,E-008 |
| F-003 | Customer Journey 执行器 | P0 | 已完成 | F-001,F-002 | 按客户步骤执行并产生逐步 Attempt，不使用随机测试替代客户流程 | E-002,E-005,E-006 |
| F-004 | Evidence Ledger | P0 | 已完成 | F-002,F-003 | SQLite 持久化原始交互、哈希、结论和失败状态，禁止覆盖 | E-002 |
| F-005 | 契约/结果/摩擦审查 | P0 | 已完成 | F-003,F-004 | 识别结构违约、目标未完成、阻塞和基础反人类操作 | E-002 |
| F-006 | 用户纠正与最小回归 | P1 | 已完成 | F-001,F-004 | 旧假设 supersede，新 Run 可解释变化 | E-010 |
| F-007 | AAWO 能力池/团队适配 | P1 | 已完成 | F-001..F-005 | 通过 AAWO 公共 API 注册测试蓝图，不修改 AAWO 内核 | E-009 |
| F-008 | 受控质量自进化 | P2 | 进行中 | F-006,F-007,F-014 | 提案、审批、灰度、指标、回滚和有害结果冻结 | E-029,E-030,E-031,E-032（单团队工作流纵切） |
| F-009 | 可选推理 Provider 与 Proposal 解析 | P1 | 已完成 | F-001,F-004 | OpenAI-compatible 接口只产出 EvolutionProposal；真实受管配置可接入；缺字段、缺证据或高风险无人工批准均 fail-closed | E-010,E-011,E-012,E-013,E-014,E-033,E-034,E-035,E-037 |
| F-010 | 异步 Job、Fixture 和副作用门禁 | P1 | 已完成 | F-002,F-003 | submit/poll 未知结果不自动取消；Fixture 可重置；读场景阻止写 Adapter | E-015,E-016 |
| F-011 | 真实应用只读适配器 smoke | P1 | 已完成 | F-002,F-003,F-004 | 通过真实 ResumeProbe FastAPI 应用的健康路由完成客户式只读旅程并保留证据 | E-017,E-018 |
| F-012 | AAWO Agent Tester Skill | P1 | 已完成 | F-001..F-010 | 可发现 Skill、HTTP Journey Runner、结构化断言和标准化报告通过校验并完成真实目标测试 | E-019,E-020 |
| F-013 | 两个真实 Agent 黑盒实测 | P1 | 已完成 | F-012 | 8000 真实 M8 服务和 Yunpai Orchestrator 9000 隔离启动入口均按客户式只读/安全旅程留下 pass、fail、inconclusive 证据 | E-020,E-021,E-022 |
| F-014 | AAWO 多部门 Team Tree 与 Adaptive Workflow 纵切 | P2 | 已完成 | F-003,F-004,F-007,F-010 | 真实 AAWO dev41 形成多部门测试团队和 Team Tree；Customer Journey 投影为独立 Adaptive Workflow；角色结果经 AAWO State/Transfer/Checkpoint 收束；原始失败状态保持不变 | E-025,E-026,E-028 |

## 功能变更历史

按时间倒序追加：日期、功能 ID、变化、原因、影响、证据 ID 和确认来源。

- 2026-08-08：F-009 增加真实 LLM 接入。通过 llm-api-config 管理的 `deepseek` 配置读取通用环境变量，`ReasoningProvider` 在基线客户旅程后接收 Agent 契约、旅程、证据摘要和用户纠正，最多做一次确定性校验反馈重试；Runner 将成功提案送入 AAWO，未人工批准时明确 rejected。真实模型质量仍未验收。证据：E-033..E-036。
- 2026-08-03：F-008 完成单团队 Workflow Optimizer 受控演化纵切，但整体仍为进行中。真实 dev41 Optimizer 通过 AgentServices 提案，ProductionControlPlane 在 Team Owner fencing 下审批/应用；revision-isolated TeamExecutor 真实重跑客户旅程，约束-only 修改不能伪造金丝雀，有害结果冻结并由 AAWO 回滚。尚缺跨团队 SOP、Team Optimizer 组织变更/补偿和 contract/scenario/evaluator 注册表应用。证据：E-029..E-032。
- 2026-08-03：F-014 完成；五个权责 Department、一个可执行 Adaptive Workflow 节点、TeamExecutor 七角色责任树、作用域 EvidenceRef、Checkpoint 和显式 IDLE 释放通过真实 dev41 集成与干净 wheel smoke。E-024/E-027 保留了目录契约和资源关闭的中间失败，最终证据为 E-025,E-026,E-028。
- 2026-07-31：F-006、F-009 完成 P1 实现与回归；F-001..F-005 完成 P0 验收；F-007 完成 AAWO DepartmentPool 注册桥接 smoke。证据：E-002..E-014。
- 2026-07-31：F-002 增加显式 GET HTTP 只读方法；F-011 完成 ResumeProbe 健康路由的真实应用 smoke。证据：E-017,E-018。
- 2026-08-01：F-012 Skill 化完成；F-013 完成 M8 真实 HTTP 旅程和 Yunpai Orchestrator 隔离/临时 9000 入口实测。证据：E-019..E-022。
