# 项目总览

> 每次新工作会话默认只读取本文件。首次维护时补充真实信息；路线变化后立即同步。
> 本目录不得记录密钥、令牌、完整个人信息或未脱敏工具输出。

## 基本信息

- 项目名称：AAWO Agent 理解与客户仿真测试器
- 项目 ID：aawo-agent-understanding-tester
- 项目负责人：用户与 Codex 协作
- 风险等级：高（测试结论、外部副作用和自进化治理）
- 当前阶段：P2 AAWO 运行时接入
- 当前状态：实施中
- 最后更新：2026-08-03

## 项目目标

- 基于 AAWO 0.6.0.dev41，搭建领域中立的 Agent 理解与客户仿真测试内核。
- 通过 Adapter、Agent Contract Profile、Customer Journey、Evidence Ledger 和 Correction Loop，形成可重放、可审计、fail-closed 的测试闭环。
- 为后续 AAWO 动态测试团队、自进化提案、人工审批和灰度回滚提供稳定接口。

## 范围

### 包含

- P0：领域中立数据模型、Callable/HTTP/CLI Adapter 协议、SQLite 证据账本、客户场景执行器、契约校验、失败状态和基础摩擦识别。
- P1：用户纠正的版本化 supersession、Profile 账本恢复、最小回归计划和可选推理提案接口。
- AAWO 蓝图/能力映射接口，不复制或修改 AAWO 原始运行时。
- P2：通过 AAWO 公共 API 接入多部门能力池、Team Tree、TeamExecutor、Adaptive Workflow、作用域证据和受控运行时状态；测试领域模型仍由独立确定性内核负责。
- 可发现的 `aawo-agent-tester` Skill、确定性 HTTP Journey Runner 和真实应用证据报告。

### 非目标

- 本阶段不实现真实 LLM Provider 的领域质量保证，不将模型自评当验收。
- 本阶段不默认连接生产系统，不实现无审批的外部写操作。
- 本阶段不声称远程 Store、容器隔离、浏览器真实环境或多租户生产安全已通过。

## 技术路线与关键约束

- 独立 Python 包 `aawo_agent_tester`；确定性内核仅依赖标准库，AAWO 编排作为显式可选依赖。
- 推理 Provider 只生成本地解析的 EvolutionProposal；不得直接修改 Profile、Journey、Evaluator 或 TestRun。
- AAWO 作为可选集成边界：Department Pool/Team Tree/Adaptive Workflow/Store 由外部安装的 AAWO 提供；测试内核可在无 AAWO 安装时独立运行。
- 失败不可静默修复；原始输入、输出、步骤和证据不可变，修复产生新 Attempt/Run。
- 证据和记忆按 scope 隔离；管理文档只记录脱敏摘要、证据 ID、哈希和受控位置。

## 数据与安全边界

- 数据分类：尚未定义。
- 敏感信息处理：只记录脱敏摘要、证据 ID 和受控位置，不粘贴原始敏感数据。

## 当前焦点

- 下一里程碑：真实 LLM 领域理解质量与提案语义回归
- 当前工作重点：让受管真实 LLM 通过 `ReasoningProvider` 进入基线客户旅程后的 Workflow 提案阶段，并保持 AAWO 控制面人工审批边界
- 主要阻塞：无已知阻塞

## 按需读取索引

| 当前任务 | 追加读取 |
|---|---|
| 规划、实施、阻塞处理 | `PROJECT_PROGRESS.md` |
| 新增、修改、删除功能 | `PROJECT_FEATURES.md`；实施时同时读进度 |
| 版本号、发布、升级、兼容性 | `PROJECT_VERSIONS.md` |
| 测试、交付、完成声明 | `PROJECT_ACCEPTANCE.md` |
| 跨领域路线变更或一致性审计 | 全部文件 |

## 路线变更记录

按时间倒序追加：决定 ID、日期、决定、原因、影响、证据 ID、确认来源和复审条件。

- D-004｜2026-08-08｜使用 llm-api-config 的受管 `deepseek` 配置接入真实 OpenAI-compatible LLM；真实模型只在基线客户旅程后生成 Workflow 提案，确定性校验失败最多自动纠正一次，提案仍必须进入 AAWO ProductionControlPlane，未人工批准不得应用｜让模型具备真实 Agent 契约/旅程/证据理解入口，同时保留 fail-closed 和 AAWO 权限事实源｜E-033..E-037｜用户明确要求使用 LLM skill 接入真实 LLM｜完成领域质量回归和模型切换前复审数据范围、成本和证据脱敏
- D-003｜2026-08-03｜F-008 先交付单团队 Workflow Optimizer 纵切：Optimizer 仅提案，ProductionControlPlane 携 Team Owner fencing 审批和应用，独立 revision composition 重跑真实客户旅程，确定性指标决定保留或调用 AAWO rollback；其余提案类型在存在真实注册表应用路径前保持 proposal-only｜防止模型自评、复用旧结果或本地影子状态伪装成 AAWO 自进化｜E-029..E-032｜用户要求严格依照 AAWO 设计继续开发｜接入跨团队 SOP/Team Optimizer 或任一新注册表应用类型前复审权限、金丝雀与补偿边界
- D-002｜2026-08-03｜保留 AgentContractProfile、CustomerJourney、Finding、Correction 等测试领域模型；能力池、Team Tree、Adaptive Workflow、作用域 EvidenceRef、Store/Checkpoint 和优化应用不得在测试包内复制，统一通过 AAWO 公共 API 接入｜避免双重事实源并严格遵守 AAWO“组织树与工作流分离、Agent 提案而控制面应用”的设计｜E-025,E-026,E-028｜用户明确要求严格按照 AAWO 设计开发｜已在 E-029..E-032 复审并通过单团队工作流纵切
- D-001｜2026-08-01｜将测试内核包装为可发现 Skill，Skill 只编排流程，确定性引擎负责执行和证据，模型推理保持可选｜降低复用门槛并保留 fail-closed 审计边界｜E-019,E-020｜用户确认增加 Skill 并测试两个真实 Agent｜P2 Team Tree 接入前复审
