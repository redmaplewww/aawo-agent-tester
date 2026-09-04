# 项目总览

> 每次新工作会话默认只读取本文件。首次维护时补充真实信息；路线变化后立即同步。
> 本目录不得记录密钥、令牌、完整个人信息或未脱敏工具输出。

## 基本信息

- 项目名称：Codex Agent 理解与客户仿真测试器
- 项目 ID：codex-agent-understanding-tester
- 项目负责人：用户与 Codex 协作
- 风险等级：高（测试结论、外部副作用和自进化治理）
- 当前阶段：P2 Codex SDK 测试智能化
- 当前状态：实施中
- 最后更新：2026-09-05

## 项目目标

- 基于官方 `openai-codex` SDK，搭建领域中立的 Agent 理解与客户仿真测试内核。
- 通过 Codex 规划/复核、Adapter、Agent Contract Profile、Customer Journey、Evidence Ledger 和 Correction Loop，形成可重放、可审计、fail-closed 的测试闭环。
- 核心目标是替客户操作 Agent：发现真实输入/输出契约、识别反人类流程和实现缺口；模型只负责理解与审查，确定性执行器负责真实调用和结算。

## 范围

### 包含

- P0：领域中立数据模型、Callable/HTTP/CLI Adapter 协议、SQLite 证据账本、客户场景执行器、契约校验、失败状态和基础摩擦识别。
- P1：用户纠正的版本化 supersession、Profile 账本恢复、最小回归计划和可选推理提案接口。
- Codex SDK 只读推理边界；Codex 生成的计划和复核必须经过本地 schema、支持矩阵和证据范围校验。
- P2：Codex Customer Tester 自动生成五类最低客户旅程，执行后检查实现完整性；用户纠正会进入 supersession 和最小回归。
- 可发现的 `codex-agent-tester` Skill、确定性 HTTP/CLI/Callable Journey Runner 和真实应用证据报告。

### 非目标

- 本阶段不把 Codex 自评当验收；模型输出不具备执行或改写结果的权限。
- 本阶段不默认连接生产系统，不实现无审批的外部写操作。
- 本阶段不声称远程 Store、容器隔离、浏览器真实环境或多租户生产安全已通过。

## 技术路线与关键约束

- 独立 Python 包 `codex_agent_tester`；唯一模型运行时依赖为 `openai-codex==0.147.0`，不读取项目 API Key、不拼接 Chat Completions URL。
- CodexReasoner 只生成本地解析的测试计划、复核和受治理提案；不得直接修改 Profile、Journey、Evaluator 或 TestRun。
- 确定性 CustomerSimulationRunner 是执行和结算事实源；模型不可把 FAIL、BLOCKED、UNKNOWN 或缺失覆盖改写为 PASS。
- 失败不可静默修复；原始输入、输出、步骤和证据不可变，修复产生新 Attempt/Run。
- 证据和记忆按 scope 隔离；管理文档只记录脱敏摘要、证据 ID、哈希和受控位置。

## 数据与安全边界

- 数据分类：尚未定义。
- 敏感信息处理：只记录脱敏摘要、证据 ID 和受控位置，不粘贴原始敏感数据。

## 当前焦点

- 下一里程碑：真实 Codex 登录态下的任意领域 Agent 旅程质量回归
- 当前工作重点：让 Codex Customer Tester 在真实 Agent 边界上完成契约发现、客户式测试、完整性审查和纠正后的最小回归
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

- D-006｜2026-09-05｜删除旧架构命名、配置、入口、远程地址和遗留分支；GitHub 仓库统一命名为 `codex-agent-tester` 并设为 public｜避免已废弃路线继续被误认为当前实现；当前产品只以 Codex SDK 为模型运行时｜E-041｜用户明确要求完全舍弃旧架构｜继续保持 Codex SDK、客户式测试和完整性检查边界
- D-004｜2026-08-08｜使用受管 Provider 配置接入外部 LLM；真实模型只在基线客户旅程后生成 Workflow 提案，确定性校验失败最多自动纠正一次，提案仍必须经过人工控制面，未人工批准不得应用｜让模型具备真实 Agent 契约/旅程/证据理解入口，同时保留 fail-closed 权限边界｜E-033..E-037｜用户明确要求使用 LLM skill 接入真实 LLM｜完成领域质量回归和模型切换前复审数据范围、成本和证据脱敏
- D-005｜2026-08-25｜全面切换到官方 `openai-codex` SDK；移除旧编排运行时、旧 Provider URL 和旧集成入口，保留客户式模拟测试、反人类操作识别、实现完整性检查、用户纠正和证据账本｜用户明确要求不再使用旧架构，核心价值是替客户测试 Agent 并找出真实问题；Codex 仅做理解/规划/复核，确定性 Runner 仍是事实源｜E-038..E-040｜用户最新指令｜接入真实目标 Agent 前复审 Codex 计划质量、拒绝写操作和证据脱敏
- D-003｜2026-08-03｜F-008 先交付单团队 Workflow Optimizer 纵切：Optimizer 仅提案，控制面携 Owner fencing 审批和应用，独立 revision composition 重跑真实客户旅程，确定性指标决定保留或回滚；其余提案类型在存在真实注册表应用路径前保持 proposal-only｜防止模型自评、复用旧结果或本地影子状态伪装成自动演化｜E-029..E-032｜用户当时要求受控演化｜接入跨团队 SOP/Team Optimizer 或任一新注册表应用类型前复审权限、金丝雀与补偿边界
- D-002｜2026-08-03｜保留 AgentContractProfile、CustomerJourney、Finding、Correction 等测试领域模型；组织树、工作流、Store/Checkpoint 和优化应用不在测试包内复制｜避免双重事实源并保持执行、证据和控制面边界｜E-025,E-026,E-028｜用户当时要求分层架构｜已由 D-005 统一切换为 Codex SDK
- D-001｜2026-08-01｜将测试内核包装为可发现 Skill，Skill 只编排流程，确定性引擎负责执行和证据，模型推理保持可选｜降低复用门槛并保留 fail-closed 审计边界｜E-019,E-020｜用户确认增加 Skill 并测试两个真实 Agent｜P2 Team Tree 接入前复审
