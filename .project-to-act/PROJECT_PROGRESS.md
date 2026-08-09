# 项目进度

> 记录当前执行状态与有效工作节点；普通查看、搜索和无状态变化的命令不写入。

## 当前任务

| 任务 | 状态 | 负责人 | 完成条件 | 证据 ID | 最后更新 |
|---|---|---|---|---|---|
| P0 内核搭建 | 已完成 | Codex | 包可导入；Callable/HTTP/CLI Adapter、场景执行、证据账本、严格失败状态和基础摩擦发现通过测试 | E-002,E-003,E-004,E-005,E-006,E-007,E-008,E-009 | 2026-07-31 |
| P1 纠正与最小回归 | 已完成 | Codex | Profile 可恢复；纠正更新 confirmed 契约并生成显式优先/保守回退的 RegressionPlan | E-010,E-011,E-012 | 2026-07-31 |
| P1 推理提案边界 | 已完成 | Codex | OpenAI-compatible Provider 可选；Proposal 解析 fail-closed；契约/评审批准需人工授权 | E-010,E-011,E-012 | 2026-07-31 |
| P1 异步 Job 与副作用门禁 | 已完成 | Codex | submit/poll Agent 可在未知时 fail-closed；FixtureEnvironment 可重置；读场景阻止写适配器 | E-015,E-016 | 2026-07-31 |
| P1 真实应用只读 smoke | 已完成 | Codex | 隔离数据目录，真实 ResumeProbe FastAPI 健康路由按客户操作员旅程通过 | E-017,E-018 | 2026-07-31 |
| P1 Skill 化与 HTTP Runner | 已完成 | Codex | Skill 通过 quick_validate；Runner 支持 GET/POST、结构化断言、JSON/SQLite 报告 | E-019,E-020 | 2026-08-01 |
| P1 M8 与 Yunpai 真实 Agent 实测 | 已完成 | Codex | 8000 四个真实场景通过；Yunpai 9000 原部署状态记录、隔离 uvicorn 健康旅程通过 | E-020,E-022 | 2026-08-01 |
| P2 AAWO Team Tree/Adaptive Workflow 纵切 | 已完成 | Codex | 真实 dev41 多部门注册、TeamExecutor 树内执行、Journey 工作流投影、作用域证据与严格失败结算通过集成测试 | E-025,E-026,E-028 | 2026-08-03 |
| P2 AAWO 受控工作流质量演化纵切 | 已完成 | Codex | Optimizer 只能提案；控制面显式审批；真实重跑灰度；有害结果冻结并由 AAWO 回滚 | E-029,E-030,E-031,E-032 | 2026-08-03 |
| P1 真实 LLM Provider 与 AAWO 提案边界 | 已完成 | Codex | 受管配置可注入；真实模型生成 Workflow 提案；Runner 接收后仍由 AAWO 控制面审批；不合规输出最多校正一次并 fail-closed | E-033,E-034,E-035,E-036,E-037 | 2026-08-08 |
| 项目账本初始化 | 已完成 | Codex | `init_project_management.py --validate` 通过 | E-001 | 2026-07-31 |

## 阻塞项

| 阻塞 | 影响 | 解除条件 | 状态 |
|---|---|---|---|
| Yunpai 原部署端口 9000 在首次检查时未监听 | 不能直接证明原 compose 实例运行状态 | 启动真实部署或提供可用 9000 服务 | 已记录；隔离 uvicorn 实测已完成 |

## 下一步

1. P1：验证真实 LLM 的领域质量、模型切换和用户纠正后的提案回归。
2. P2：将单团队 Workflow Optimizer 纵切扩展到跨团队 SOPRegistry 晋升、Team Optimizer 组织变更/补偿，以及 contract/scenario/evaluator 注册表应用。
3. P3：验证远程 Store、多租户 SecurityScope、恢复重放和真实写操作的 ToolRegistry/DurableAction 治理。

## 进度历史

按时间倒序追加：日期、完成事项、证据 ID、遗留问题、下一步和确认来源。不要覆盖旧记录。

- 2026-08-08：完成真实 LLM 到 AAWO 提案边界的接入。`deepseek-v4-flash` 真实请求成功生成 Workflow proposal；首轮非合规输出被确定性解析器拒绝，并在一次校正回合后成功；端到端 Runner 基线 PASS、LLM proposal received、无人工审批时 AAWO evolution rejected、未自动应用；新 wheel 在全新 venv 中安装并完成同样的 AAWO/LLM smoke。37 项 AAWO 源码测试、compileall 和变更文件 Ruff 通过。证据：E-033..E-037。真实模型领域质量、成本和长期回归仍待验证。
- 2026-08-03：完成 F-008 的单团队受控工作流演化纵切。真实 AAWO dev41 Optimizer/AgentServices/ProductionControlPlane/Team Owner fencing 串成审批链；基线与金丝雀使用不同 workflow revision composition，必须重新执行客户旅程；无执行节点变更时不允许伪造金丝雀；有害结果写入冻结控制事件并由 AAWO rollback 恢复基线。33 项源码测试、Ruff、compileall、wheel 构建和干净双 wheel 新旧 smoke 通过。证据：E-029..E-032。F-008 仍未覆盖跨团队 SOP、Team Optimizer 组织变更/补偿和其他注册表应用。
- 2026-08-03：完成 F-014 P2 纵切。真实 AAWO dev41 形成五个权责 Department、Workflow 招聘的 Test Director 和七角色 TeamExecutor 责任树；PASS/BLOCKED/FAIL 均保持原结论，写能力在只读旅程中零调用；7 个 EvidenceRef 均绑定同一 team/memory scope；工作流 receipt 闭合并按 9 个 Agent 后序显式释放。28 项 pytest、Ruff、compileall、项目账本校验、wheel 构建和干净双 wheel smoke 通过。证据：E-024..E-028。仍未覆盖远程 Store、生产副作用和自进化应用。
- 2026-07-31：P0 独立内核完成。13 项 pytest、Ruff、compileall、CLI/示例运行、wheel 构建与干净 wheel 安装通过；开发包 AAWO wheel 的真实 DepartmentPool 注册 smoke 通过。证据：E-002..E-009。P1 尚未开始，真实 LLM/MCP/浏览器/远程 Store/自进化仍未实现。
- 2026-07-31：P1 纠正与推理边界完成。19 项 pytest、Ruff、compileall、更新 wheel 构建和干净安装通过；没有调用外部真实 LLM Provider，推理接口使用本地 HTTP 回环验证。证据：E-010..E-014。MCP/异步 Job、Team Tree 执行和自进化应用仍待实现。
- 2026-07-31：P1 异步 Job、FixtureEnvironment 和副作用门禁完成。22 项 pytest、Ruff、compileall、更新 wheel 构建和干净安装通过。证据：E-015..E-016。MCP/浏览器、Team Tree 执行和自进化应用仍待实现。
- 2026-07-31：完成 23 项 pytest、Ruff、compileall、pip wheel、干净 venv 导入和凭据模式扫描；通过真实 ResumeProbe FastAPI `/api/health` 路由的只读客户旅程 smoke，5 条账本事件，无 findings。证据：E-017..E-018。未覆盖上传/LLM 审查、MCP/浏览器、Team Tree、生产写操作和自进化应用。
- 2026-08-01：完成 Skill、HTTP Runner 和结构化断言回归；8000 M8 真实 Agent 的健康、注册表、CAD 预留契约、破坏性动作门禁四个场景通过，错误文本断言被判 fail；Yunpai 9000 首次连接 inconclusive，随后隔离依赖配置的真实 uvicorn 入口在 9000 健康旅程通过；Yunpai 全套测试 189 passed/1 failed，失败为周末日期依赖测试。证据：E-019..E-023。
- 2026-07-31：用户确认开始搭建；采用独立包 + 可选 AAWO 适配路线。原始 AAWO 压缩包不修改。证据：E-001。
