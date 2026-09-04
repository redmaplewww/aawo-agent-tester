# 项目进度

> 记录当前执行状态与有效工作节点；普通查看、搜索和无状态变化的命令不写入。

## 当前任务

| 任务 | 状态 | 负责人 | 完成条件 | 证据 ID | 最后更新 |
|---|---|---|---|---|---|
| P0 内核搭建 | 已完成 | Codex | 包可导入；Callable/HTTP/CLI Adapter、场景执行、证据账本、严格失败状态和基础摩擦发现通过测试 | E-002,E-003,E-004,E-005,E-006,E-007,E-008,E-009 | 2026-07-31 |
| P1 纠正与最小回归 | 已完成 | Codex | Profile 可恢复；纠正更新 confirmed 契约并生成显式优先/保守回退的 RegressionPlan | E-010,E-011,E-012 | 2026-07-31 |
| P1 历史 Provider 推理提案边界 | 已取消 | Codex | 旧 Provider URL 路线已退出；其 fail-closed 解析经验保留并由 CodexReasoner 替代 | E-010,E-039 | 2026-08-25 |
| P1 异步 Job 与副作用门禁 | 已完成 | Codex | submit/poll Agent 可在未知时 fail-closed；FixtureEnvironment 可重置；读场景阻止写适配器 | E-015,E-016 | 2026-07-31 |
| P1 真实应用只读 smoke | 已完成 | Codex | 隔离数据目录，真实 ResumeProbe FastAPI 健康路由按客户操作员旅程通过 | E-017,E-018 | 2026-07-31 |
| P1 Skill 化与 HTTP Runner | 已完成 | Codex | Skill 通过 quick_validate；Runner 支持 GET/POST、结构化断言、JSON/SQLite 报告 | E-019,E-020 | 2026-08-01 |
| P1 M8 与 Yunpai 真实 Agent 实测 | 已完成 | Codex | 8000 四个真实场景通过；Yunpai 9000 原部署状态记录、隔离 uvicorn 健康旅程通过 | E-020,E-022 | 2026-08-01 |
| P2 历史 Team Tree/Adaptive Workflow 纵切 | 已取消 | Codex | 旧编排集成已退出；历史证据不作为当前产品依赖 | E-025,E-026,E-028,E-038 | 2026-08-25 |
| P2 历史受控工作流质量演化纵切 | 已取消 | Codex | 旧控制面已退出；保留通用 EvolutionGovernor、用户纠正和人工门禁 | E-029,E-030,E-031,E-032,E-039 | 2026-08-25 |
| P1 历史真实 LLM Provider 边界 | 已取消 | Codex | 旧 OpenAI-compatible/控制面路线已退出；当前由官方 Codex SDK 负责理解/复核 | E-033,E-034,E-035,E-036,E-037,E-038 | 2026-08-25 |
| P2 Codex SDK 架构迁移 | 已完成 | Codex | 移除旧编排运行时和 Provider URL；`openai-codex==0.147.0` 作为唯一模型运行时；新包、CLI、Skill 和文档可独立安装 | E-038,E-039,E-040 | 2026-08-25 |
| P2 Codex 客户式测试与完整性检查 | 已完成 | Codex | Codex 生成并复核五类最低客户旅程；确定性 Runner 执行真实适配器；缺覆盖、失败、未知、无证据均不静默通过 | E-038,E-039 | 2026-08-25 |
| 项目账本初始化 | 已完成 | Codex | `init_project_management.py --validate` 通过 | E-001 | 2026-07-31 |

## 阻塞项

| 阻塞 | 影响 | 解除条件 | 状态 |
|---|---|---|---|
| Yunpai 原部署端口 9000 在首次检查时未监听 | 不能直接证明原 compose 实例运行状态 | 启动真实部署或提供可用 9000 服务 | 已记录；隔离 uvicorn 实测已完成 |

## 下一步

1. P1：在用户提供真实目标 Agent 和安全边界后，运行 Codex SDK 的客户式回归并审查页面/流程/契约缺陷。
2. P1：用用户纠正和投喂数据驱动最小回归，验证 supersession、重复输入和失败恢复路径。
3. P2：在明确授权后再扩展浏览器视觉/真实写操作适配器；任何副作用仍需显式审批和可恢复证据。

## 进度历史

按时间倒序追加：日期、完成事项、证据 ID、遗留问题、下一步和确认来源。不要覆盖旧记录。

- 2026-08-08：完成真实 LLM 到人工控制面提案边界的接入。`deepseek-v4-flash` 真实请求成功生成 Workflow proposal；首轮非合规输出被确定性解析器拒绝，并在一次校正回合后成功；端到端 Runner 基线 PASS、LLM proposal received、无人工审批时 evolution rejected、未自动应用；新 wheel 在全新 venv 中安装并完成同样的 LLM smoke。37 项旧路线源码测试、compileall 和变更文件 Ruff 通过。证据：E-033..E-037。真实模型领域质量、成本和长期回归仍待验证。
- 2026-08-25：按用户最新要求切换到官方 Codex SDK。新 `CodexReasoner` 使用本地 Codex 登录态、只读沙箱和 deny-all approval；真实 SDK 采用五个有界维度回合生成客户旅程，经过本地 schema/支持矩阵和浅层语义校验后由 Callable/HTTP/CLI Runner 执行，并对五个最低维度做实现完整性检查。增加真实交互 request/response/observation event evidence ID、Codex review evidence scope、越权 finding 拦截和缺覆盖/inconclusive/fail-closed 结算。22 项测试、Ruff、compileall、Skill quick_validate、CLI smoke 和真实 Codex fixture smoke 通过；fixture 的五条失败均如实保留，没有伪造 PASS。无真实目标 Agent 业务结论。证据：E-038..E-040。
- 2026-08-03：完成 F-008 的单团队受控工作流演化纵切。旧 Optimizer/AgentServices/ProductionControlPlane/Owner fencing 串成审批链；基线与金丝雀使用不同 workflow revision composition，必须重新执行客户旅程；无执行节点变更时不允许伪造金丝雀；有害结果写入冻结控制事件并回滚恢复基线。33 项旧路线源码测试、Ruff、compileall、wheel 构建和干净双 wheel 新旧 smoke 通过。证据：E-029..E-032。F-008 后续不再属于当前产品。
- 2026-08-03：完成 F-014 P2 纵切。旧运行时形成五个权责 Department、Workflow 招聘的 Test Director 和七角色执行树；PASS/BLOCKED/FAIL 均保持原结论，写能力在只读旅程中零调用；7 个 EvidenceRef 均绑定同一 scope；工作流 receipt 闭合并按 9 个 Agent 后序显式释放。28 项旧路线 pytest、Ruff、compileall、项目账本校验、wheel 构建和干净双 wheel smoke 通过。证据：E-024..E-028。该纵切已退出当前产品。
- 2026-07-31：P0 独立内核完成。13 项 pytest、Ruff、compileall、CLI/示例运行、wheel 构建与干净 wheel 安装通过；旧外部编排 wheel 的注册 smoke 通过。证据：E-002..E-009。P1 尚未开始，真实 LLM/MCP/浏览器/远程 Store/自进化仍未实现。
- 2026-07-31：P1 纠正与推理边界完成。19 项 pytest、Ruff、compileall、更新 wheel 构建和干净安装通过；没有调用外部真实 LLM Provider，推理接口使用本地 HTTP 回环验证。证据：E-010..E-014。MCP/异步 Job、Team Tree 执行和自进化应用仍待实现。
- 2026-07-31：P1 异步 Job、FixtureEnvironment 和副作用门禁完成。22 项 pytest、Ruff、compileall、更新 wheel 构建和干净安装通过。证据：E-015..E-016。MCP/浏览器、Team Tree 执行和自进化应用仍待实现。
- 2026-07-31：完成 23 项 pytest、Ruff、compileall、pip wheel、干净 venv 导入和凭据模式扫描；通过真实 ResumeProbe FastAPI `/api/health` 路由的只读客户旅程 smoke，5 条账本事件，无 findings。证据：E-017..E-018。未覆盖上传/LLM 审查、MCP/浏览器、Team Tree、生产写操作和自进化应用。
- 2026-08-01：完成 Skill、HTTP Runner 和结构化断言回归；8000 M8 真实 Agent 的健康、注册表、CAD 预留契约、破坏性动作门禁四个场景通过，错误文本断言被判 fail；Yunpai 9000 首次连接 inconclusive，随后隔离依赖配置的真实 uvicorn 入口在 9000 健康旅程通过；Yunpai 全套测试 189 passed/1 failed，失败为周末日期依赖测试。证据：E-019..E-023。
- 2026-07-31：用户确认开始搭建；采用独立包 + 可选外部编排适配路线。原始外部编排压缩包不修改。证据：E-001。
