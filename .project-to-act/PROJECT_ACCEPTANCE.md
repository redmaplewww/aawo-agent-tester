# 项目验收

> 执行测试、交付或声明完成前必须读取本文件。没有新鲜证据时不得写成通过。
> 不粘贴密钥、完整个人信息、原始顾客对话或未脱敏工具输出。

## 当前验收结论

- 结论：Codex SDK 架构迁移、真实 Codex fixture 客户式旅程生成、确定性执行、实现完整性检查、纠正/最小回归和 Skill 校验通过；没有真实目标 Agent 的业务结论，不能把本次结果写成领域质量或生产验收
- 验收范围：`openai-codex==0.147.0` 只读 CodexReasoner、Callable/HTTP/CLI Adapter、CustomerSimulationRunner、SQLite Evidence Ledger、五个最低覆盖维度、失败/阻塞/未知/缺证据结算、Codex review evidence scope、用户纠正和最小回归
- 最后检查：2026-08-25
- 遗留问题：真实目标 Agent 仍需在用户提供边界和安全许可后实测；浏览器视觉、真实写操作、跨进程恢复和长期模型质量未验收；Codex SDK 本机登录态可用性因运行环境而异；本次只验证本地 fixture 与 SDK 边界，不代表任意领域普适质量

## 验收标准

| 标准 ID | 标准 | 状态 | 验证方法 | 证据 ID |
|---|---|---|---|---|
| A-001 | 包可导入且核心模型可序列化 | 通过 | `py -3.12 -m pytest -q`、clean wheel import | E-002,E-008 |
| A-002 | 客户旅程按真实步骤执行并保存原始证据 | 通过 | Callable/HTTP/CLI deterministic journey | E-002,E-005,E-006 |
| A-003 | 失败、阻塞和未知结果不能被静默转为通过 | 通过 | fail/blocked/unknown regression | E-002 |
| A-004 | 证据账本可重开、哈希稳定且不覆盖历史 | 通过 | SQLite ledger append-only regression | E-002 |
| A-005 | 基础反人类操作被识别并绑定步骤证据 | 通过 | repeated input and non-actionable error fixture | E-002 |
| A-006 | 代码质量门禁通过 | 通过 | pytest/compileall/ruff | E-002,E-003,E-004 |
| A-007 | 用户纠正可恢复并生成最小回归计划 | 通过 | P1 correction/profile/regression tests | E-010 |
| A-008 | 推理输出只能形成受治理提案 | 通过 | proposal parser and governor tests | E-010 |
| A-009 | 异步 Job 和副作用门禁 fail-closed | 通过 | AsyncJobAdapter, FixtureEnvironment and side-effect tests | E-015,E-016 |
| A-010 | 真实应用健康只读旅程通过且保留原始响应 | 通过 | ResumeProbe FastAPI TestClient + CallableAdapter + CustomerSimulationRunner | E-017,E-018 |
| A-011 | Skill 可发现、可校验并能生成结构化 HTTP 证据报告 | 通过 | `quick_validate.py`、Skill Runner GET/POST、pytest/Ruff/compileall | E-019,E-020 |
| A-012 | 两个指定真实 Agent 的目标状态被如实记录 | 通过 | M8 8000 HTTP 旅程；Yunpai 9000 连接状态与隔离 uvicorn HTTP 旅程 | E-020,E-021,E-022 |
| A-013 | 旧组织树与工作流分离并形成可执行闭环 | 历史通过 | 五 Department、Workflow receipt、TeamExecutor 七角色和 9 Agent release smoke | E-025,E-028 |
| A-014 | 旧编排不改变被测 Agent 的 PASS/BLOCKED/FAIL，写边界 fail-closed | 历史通过 | 三条旧集成路径；BLOCKED 场景适配器调用数为 0 | E-025 |
| A-015 | 旧运行时证据绑定 scope 且运行时显式收束 | 历史通过 | 7 个 SHA-256 EvidenceRef、Checkpoint/Store、后序 IDLE release | E-025,E-028 |
| A-016 | 旧 Optimizer 只产生提案，控制面携有效 Owner fencing 并显式人工审批 | 历史通过 | 拒绝审批、批准审批和 owner epoch 集成回归；检查持久化 ApprovalRecord/control ledger | E-029,E-030 |
| A-017 | 金丝雀必须以独立 workflow revision composition 重新执行客户旅程，不能复用基线或以非执行变更伪造 | 通过 | adapter 两次调用、不同 TestRun ID；constraints-only 修改仅一次调用并冻结 | E-030,E-032 |
| A-018 | 有害金丝雀不会晋升，且由旧控制面 rollback 恢复已知基线并留下冻结记录 | 历史通过 | canary FAIL、control status frozen、workflow history rollback、active baseline restored | E-030 |
| A-019 | 真实 LLM 能理解受限 Agent 上下文并只生成受治理 Workflow 提案 | 历史通过 | 受管 deepseek 配置真实调用；一次校正回合；Runner 基线 PASS 后 proposal received；无人工批准时 rejected，`applied=false`；wheel 全新 venv 回归 | E-033..E-037 |
| A-020 | 官方 Codex SDK 是唯一模型运行时边界 | 通过 | `openai-codex==0.147.0` 安装/导入；CodexReasoner 只读沙箱、deny-all approval、ephemeral thread；无 Provider URL/API Key 入口 | E-038,E-039 |
| A-021 | Codex 生成的客户旅程必须经过本地支持矩阵和 schema 校验 | 通过 | 缺步骤、缺覆盖、未知 step/assertion 和错误 JSON 均 blocked；合法计划才进入 Deterministic Runner | E-039 |
| A-022 | 模拟真人测试覆盖真实客户路径而非无意义 ping/fuzz | 通过 | 五个最低维度：正常成功、无效/不完整输入、输出契约、失败恢复、重复输入/纠正；每个旅程包含 user_input 与 expect/observe | E-039 |
| A-023 | 实现完整性检查不能静默补齐缺口 | 通过 | 缺覆盖为 incomplete，失败为 fail，blocked/unknown 或 Codex review 不确定为 inconclusive；无 evidence 的 finding 被拒绝 | E-039 |
| A-024 | 用户纠正可驱动最小回归和受治理自校正 | 通过 | Correction supersession、CorrectionImpactAnalyzer、RegressionPlan 和 Codex proposal parser/governor 回归 | E-039 |
| A-025 | 新 Skill 可校验、可安装并暴露 Codex 客户式测试工作流 | 通过 | `quick_validate.py`、wheel 构建、CLI demo/codex-status、17 项 pytest、Ruff、compileall | E-040 |

## 证据索引

| 证据 ID | 时间 | 方法或命令 | 退出状态 | 版本或文件哈希 | 结果摘要 | 证据位置 | 有效期 |
|---|---|---|---|---|---|---|---|
| E-000 | 未记录 | 未执行 | 未记录 | 未记录 | 无 | 无 | 未定义 |
| E-001 | 2026-07-31 | `init_project_management.py --validate` | 0 | 项目账本配置有效 | `F:\Codex\杂项Agent\.project-to-act` | 当前会话 |
| E-002 | 2026-07-31 | `PYTHONPATH=src; py -3.12 -m pytest -q` | 0 | 13 passed | `tests/` | 当前源码版本 |
| E-003 | 2026-07-31 | `PYTHONPATH=src; py -3.12 -m ruff check src tests examples` | 0 | All checks passed | `src/ tests/ examples/` | 当前源码版本 |
| E-004 | 2026-07-31 | `PYTHONPATH=src; py -3.12 -m compileall -q src tests examples` | 0 | 编译通过 | `src/ tests/ examples/` | 当前源码版本 |
| E-005 | 2026-07-31 | `PYTHONPATH=src; py -3.12 -m legacy_tester.cli demo` | 0 | demo status `pass` | 旧源码入口 | 历史证据 |
| E-006 | 2026-07-31 | `PYTHONPATH=src; py -3.12 examples\p0_demo.py` | 0 | demo status `pass`; ledger records emitted | `examples/p0_demo.py` | 当前源码版本 |
| E-007 | 2026-07-31 | `.venv\Scripts\python.exe -m build --wheel --no-isolation` | 0 | wheel built | 旧测试器 wheel；SHA256 `E41E9D68F6A1A38BFFE5472DFD90B3A8FA030D95626FA21AA4BFC812756BB352` | 历史构建 |
| E-008 | 2026-07-31 | fresh temp venv; `pip install --no-index --no-deps <wheel>` then import smoke | 0 | installed package imported; 10 blueprints and `CustomerJourney` resolved | temporary environment | 当前构建 |
| E-009 | 2026-07-31 | fresh temp venv; install external orchestration wheel + tester wheel; registration bridge smoke | 0 | `agent_testing`, 1 department, 10 blueprints | 外部编排 wheel from supplied archive | 历史构建 |
| E-010 | 2026-07-31 | `PYTHONPATH=src; py -3.12 -m pytest -q` | 0 | 22 passed | `tests/`；覆盖 Profile reload、CorrectionImpactAnalyzer、RegressionPlan、Proposal parser/governor、本地 OpenAI-compatible 回环、AsyncJobAdapter、Fixture 和副作用门禁 | 当前源码版本 |
| E-011 | 2026-07-31 | `PYTHONPATH=src; py -3.12 -m ruff check src tests examples` | 0 | All checks passed | `src/ tests/ examples/` | 当前源码版本 |
| E-012 | 2026-07-31 | `PYTHONPATH=src; py -3.12 -m compileall -q src tests examples` | 0 | 编译通过 | `src/ tests/ examples/` | 当前源码版本 |
| E-013 | 2026-07-31 | `.venv\Scripts\python.exe -m build --wheel --no-isolation` | 0 | wheel built | 旧测试器 wheel；SHA256 `F0ACDF9BD55B5FF2865A6BD607F607162EB126147936EF476B4DFE5E1F58A031` | 历史构建 |
| E-014 | 2026-07-31 | fresh temp venv; install updated wheel then import P1 symbols | 0 | `CorrectionImpactAnalyzer`, `proposal_from_response`, `AsyncJobAdapter`, `FixtureEnvironment` imported | temporary environment | 当前构建 |
| E-015 | 2026-07-31 | 22-test subset includes async submit/poll, unknown bound and no-implicit-cancel assertions | 0 | AsyncJobAdapter regression passed | `tests/test_p1_correction_reasoning.py` | 当前源码版本 |
| E-016 | 2026-07-31 | 22-test subset includes read-only journey vs sandbox-write adapter | 0 | execution blocked before adapter invocation | `tests/test_p1_correction_reasoning.py` | 当前源码版本 |
| E-017 | 2026-07-31 | `PYTHONPATH=src; py -3.12 -m pytest -q` + Ruff + compileall + pip wheel | 0 | 23 passed; All checks passed; wheel SHA256 `E81F8C2A5B4806D4E281744757C0BB090E29A4CC8898E2AFFA2AEA10937B2C3A`; clean venv import passed; secret scan clean | `tests/`, 旧测试器 wheel | 历史源码版本 |
| E-018 | 2026-07-31 | `examples/real_app_resumeprobe_smoke.py` with isolated `RESUME_WEB_DATA` | 0 | real ResumeProbe `/api/health` returned HTTP 200/status ok; journey `pass`; 3 settled steps; 5 ledger records; no findings | `examples/real_app_resumeprobe_smoke.py`; local TestClient boundary | 仅健康只读路径 |
| E-019 | 2026-08-01 | Skill Creator `quick_validate.py` + source/lint/compile regression + pip wheel | 0 | Skill valid; 24 package tests passed; Ruff and compileall passed；wheel SHA256 `2BB5CBC5C3395ED9306BE86F3B97E42F3FD8C177E7ED306BF1CB040339E1FD72`；SKILL SHA256 `AF04FBDD5F35C93DE883C9A537611E2779EB0D63F673D20E66BBA49CB76158A7`；Runner SHA256 `7D8823B9FB9D117859C0DD892E9DDFC8AEC3D97DE04814EB89D695B2E0ADFBE7` | 旧 Skill、`tests/`、旧 `dist/` | 历史源码版本 |
| E-020 | 2026-08-01 | Skill Runner against `http://127.0.0.1:8000` | 0 per run | Health, enterprise agent registry, CAD reserved contract, and destructive gate all `pass`; deliberate text-format assertion `fail` and was not promoted | `artifacts/agent-tests/m8-*.json` and `.sqlite3` | 当前 M8 进程；未做业务写入 |
| E-021 | 2026-08-01 | `examples/real_app_yunpai_orchestrator_smoke.py` | 0 | Real Yunpai FastAPI lifecycle with temp SQLite, memory/Feishu disabled: health and authentication journeys `pass`; 2 runs, each 5 ledger records | `examples/real_app_yunpai_orchestrator_smoke.py`; `artifacts/agent-tests/yunpai-orchestrator-isolated.json` | 隔离应用实例 |
| E-022 | 2026-08-01 | Skill Runner against temporary uvicorn on requested `127.0.0.1:9000` | 0 | `/health` HTTP 200, `status=ok`, `module=orchestrator`, required fields passed; process stopped after test; temp DB and memory disabled | `artifacts/agent-tests/yunpai-orchestrator-live-health.json` and `.sqlite3` | 隔离配置临时进程；不等于原 compose |
| E-023 | 2026-08-01 | Yunpai Orchestrator `.venv\Scripts\python.exe -m pytest -q` | 1 | `189 passed, 1 failed`; `test_llm_records_freeform_nightly_report_without_interrupting_task_context` expected 2 on Saturday while production code correctly returns weekend skip | `F:\opencode\云湃智算\云湃一体机\Yunpai_Project\yunpai-orchestrator\orchestrator\tests\test_team_executor.py:562` | 目标源码未修改 |
| E-024 | 2026-08-03 | 旧集成测试的两轮目录契约调试 | 1 | 第一轮 1 passed/2 failed：未声明 task class；第二轮 1 passed/2 failed：Workflow/TeamRole tags 未绑定 Blueprint routing_tags；均由旧运行时 fail-closed 拒绝招聘 | 旧集成测试与候选路由检查 | 已修复且保留失败原因 |
| E-025 | 2026-08-03 | 旧运行时源码 + pytest + Ruff + compileall + project ledger validate | 0 | 28 passed；PASS/BLOCKED/FAIL 三条旧运行时路径；All checks passed；账本 valid；runtime SHA256 `B441DD7BDBF48E5181B019FD594A719E66C5BCB043841B545F7F0B423742A487`；integration test SHA256 `46B8D969C0A6B2712F2F84FD4C475418FEE91BFA538A3989A55759B8572EA969` | 旧运行时与集成测试 | 历史源码基线；已由 E-030 替代 |
| E-026 | 2026-08-03 | `.venv\Scripts\python.exe -m build --wheel --no-isolation` | 0 | 旧测试器 wheel SHA256 `799BA0F476A27B6C39ECE6554DF6480C56200CFFD39D63E1FA99665293638E01` | 旧 `dist/` 构建 | 历史构建；已由 E-031 替代 |
| E-027 | 2026-08-03 | 干净 venv 双 wheel 首次 smoke | 1 | 旧 Team Tree 本身输出 pass/7 scoped evidence/9 releases，但示例未关闭调用方拥有的 EvidenceLedger，Windows 临时目录清理因 SQLite 句柄占用失败 | 旧团队 smoke | 已修复资源关闭 |
| E-028 | 2026-08-03 | 干净 venv 安装旧编排 wheel + tester wheel；运行团队 smoke | 0 | `status=pass`、`workflow_completed=true`、7 个 team members、7 个 scoped evidence、9 个显式 release | 干净隔离 venv；旧团队 smoke | 历史构建基线；已由 E-032 回归 |
| E-029 | 2026-08-03 | 受控演化集成调试的 fail-closed 失败 | 1 | 首轮控制面因缺少 Owner fencing 拒绝写入；后续金丝雀因复用稳定 composition/work key 跳过真实执行并导致 handoff 未闭合。修复为公共 owner token 与按 workflow revision 隔离的执行 composition | 旧运行时与集成测试 | 失败原因已保留并由 E-030 回归覆盖 |
| E-030 | 2026-08-03 | 旧运行时源码 + pytest + Ruff + compileall + controlled evolution smoke；另执行 standalone suite | 0 | 旧路线 source-backed 33 passed；standalone 25 passed/8 old-only skipped；Ruff All checks passed；compileall 通过；smoke 为 baseline/canary 均 pass、adapter_calls=2、promoted、final revision=2、15 scoped evidence。runtime SHA256 `DDF740A91D3D74E55E8B631A1AE260DC467CAFB6359FF49577D13D8BED1A761F`；evolution SHA256 `0F2D6463BF27AF8FDB63DFBAB66BE3D8BD4C4115D0E6DD46B048A690697331C0`；integration test SHA256 `8610AAFF8D8F688C1276B03CFD1E99F0D01937C6E49D87F60D1A759E8E7265A3` | 旧 `src/`、`tests/`、旧演化 smoke | 历史源码版本；已退出当前产品 |
| E-031 | 2026-08-03 | `.venv\Scripts\python.exe -m build --wheel --no-isolation` | 0 | 旧测试器 wheel SHA256 `4385D119CFEFBD27A5E1A0206B338E6A292EFE6988F040E12066E0CA7BC4F56C` | 旧 `dist/` 构建 | 历史构建 |
| E-032 | 2026-08-03 | 全新 venv 安装旧编排 wheel + tester wheel；运行演化与团队 smoke；安装元数据导入检查 | 0 | 旧演化 smoke adapter_calls=2/promoted/revision=2；旧团队 smoke pass/7 team members/7 evidence/9 releases | 旧隔离 venv | 历史构建；不再作为当前依赖 |
| E-033 | 2026-08-08 | 受管 `deepseek` 真实请求的首次 fail-closed 调试 | 1 | 模型可达但返回的 `proposed_change` 非对象/非 JSON 字符串；本地解析器拒绝，未生成或应用提案；未输出鉴权信息或原始响应 | 旧 LLM proposal smoke 与 reasoning 模块 | 失败原因保留；由有界校正回合修复 |
| E-034 | 2026-08-08 | `llm-api-config Inject(deepseek)` 后运行 `PYTHONPATH=src; Python310 examples/real_llm_proposal_smoke.py` | 0 | `status=proposal_received`、model `deepseek-v4-flash`、kind `workflow`、base_revision `1`、2 条受限 evidence、`applied=false`；reasoning SHA256 `C799CE3B4BE6E56A6EDD931ED3EC2819449375A65017023A46F66E9620E790AF`；example SHA256 `043BCC58CF029AF7FA710A6FA81C81BC14E415B5F5A2E57D45F9E8F182E64C3F` | `examples/real_llm_proposal_smoke.py`、受管 `.env.local`（不纳入版本控制） | 当前本机配置；模型协议已通，领域质量未验收 |
| E-035 | 2026-08-08 | 旧运行时 source-backed real LLM proposal smoke，Python 3.10 | 0 | baseline `pass`、LLM proposal `received`、evolution `rejected`、`applied=false`、4 条 proposal evidence；Runner SHA256 `B34E3DFFF0EC0F0C03157FA87036360694C9AFB0F069CEE95E685D51DE59CA57`；example SHA256 `6FF16A6A643F28CD8B13D2C0BE068399D11370B7500E65FE5DB6FD68C1D4737E` | 旧 LLM proposal smoke 与旧运行时 | 无人工批准；只验证提案边界 |
| E-036 | 2026-08-08 | 旧运行时 source-backed `pytest -q`、compileall；变更文件 Ruff | 0 | 37 passed；compileall 通过；变更文件 Ruff All checks passed；runtime integration test SHA256 `D7958CB158E08E8518BC8E87D2701E19D49D1C721FFD32C7781C0E0E34214184`；P1 reasoning test SHA256 `9757BF45D38346C9EBB7E995D7CF19C27E6B1C88CEF65E798BF4361FCFA9DAFE` | 旧 `tests/`、旧运行时、旧 `examples/` | 历史源码版本；全仓最新 Ruff 仍有历史基线规则差异 |
| E-037 | 2026-08-08 | 旧 LLM proposal wheel smoke；全新 Python 3.10 venv | 0 | wheel SHA256 `2BA05D7BAC6A5F61E181274B596E5BBABD89F4F0A86476B6B810935C07D7CA1E`；baseline `pass`、proposal `received`、evolution `rejected`、`applied=false` | 旧 wheel；旧隔离 venv | 历史构建；不再作为当前依赖 |
| E-038 | 2026-08-25 | `openai-codex==0.147.0` 安装；`PYTHONPATH=src; py -3.12 -m pytest -q`；Ruff；compileall；`codex-agent-tester demo`；`codex-status`；`pip wheel --no-deps --no-build-isolation` | 0 | 22 passed；Ruff All checks passed；compileall 通过；demo PASS；SDK status `ready/thread_started=true`；wheel `codex_agent_tester-0.1.0.dev0-py3-none-any.whl` SHA256 `79b225d694aab5a600ff6ef6732f7bf4f24a5be376934c2892c6f68e6b81b13e`，无 legacy package entries；新包命名 `codex_agent_tester`；旧编排源模块和入口已移除 | `src/codex_agent_tester/`、`dist-codex-20260825/`、`pyproject.toml`、`README.md` | 当前源码版本；不代表真实目标 Agent 质量 |
| E-039 | 2026-08-25 | `tests/test_p1_correction_reasoning.py` CodexReasoner/CodexCustomerTester 回归 | 0 | 官方 SDK boundary fake、五维客户式旅程、事件 evidence ID、缺 failure_recovery 的完整性 `incomplete`、review 证据范围和纠正回归通过 | `tests/`、`src/codex_agent_tester/codex_tester.py`、`src/codex_agent_tester/reasoning.py` | 本地 deterministic fixture；无真实目标 Agent |
| E-040 | 2026-08-25 | Skill Creator `quick_validate.py`（UTF-8）+ `examples/codex_customer_tester_smoke.py` 真实 Codex SDK fixture 回合 | 0 | Skill valid；5 个维度发现回合 + 5 个 Callable 客户旅程 + Codex review 完成；fixture 故意只返回 `processed:`，报告如实为 `fail`，保留 request/response evidence 和 5 条客户可见 finding；无外部写操作；SQLite 安全关闭 | `skills/codex-agent-tester/`、`examples/codex_customer_tester_smoke.py`、临时 SQLite | 真实 Codex 本机登录态；fixture 结果不代表任意领域 Agent |

## Gate 记录

| Gate ID | 日期 | Gate | 对象 | 结果 | 证据 ID | 豁免与确认人 |
|---|---|---|---|---|---|---|
| G-001 | 2026-07-31 | P0 standalone kernel | source package + local fixtures | 通过 | E-002..E-008 | 不覆盖生产与真实 LLM |
| G-002 | 2026-07-31 | 旧外部编排 registration bridge | supplied external orchestration wheel | 历史通过 | E-009 | 不覆盖团队执行 |
| G-003 | 2026-07-31 | P1 correction and minimum regression | source package + deterministic fixtures | 通过 | E-010..E-012 | 不覆盖 real domain expert confirmation |
| G-004 | 2026-07-31 | proposal-only reasoning boundary | source package + deterministic malformed payloads | 通过 | E-010..E-014 | 未调用真实 Provider，不代表模型质量 |
| G-005 | 2026-08-03 | P2 旧 Team Tree/Adaptive Workflow vertical slice | supplied external orchestration + tester source/wheel | 历史通过 | E-025,E-026,E-028 | 仅本地 SQLite 参考 Store；不覆盖自进化应用和生产写操作 |
| G-006 | 2026-08-03 | P2 single-team controlled workflow evolution vertical slice | supplied dev41 + tester source/wheel | 通过 | E-029..E-032 | 仅单团队 Workflow Optimizer；不覆盖跨团队 SOP、Team Optimizer 组织变化、其他注册表应用、远程 Store 或生产写操作 |
| G-007 | 2026-08-08 | real LLM proposal-only integration | managed deepseek profile + supplied dev41 source/wheel | 通过 | E-033..E-037 | 仅证明协议连接、受限上下文和拒绝边界；不证明领域质量，不自动应用模型输出 |
| G-008 | 2026-08-25 | Codex SDK customer simulation and completeness gate | `codex_agent_tester` source + `openai-codex==0.147.0` + local fixtures | 通过 | E-038..E-040 | 仅证明 SDK 边界、客户式计划/执行/完整性结算和纠正回归；不证明真实目标 Agent 或生产副作用 |

## 验收记录

按时间倒序追加：日期、检查范围、证据 ID、结果、遗留问题和结论。失败、跳过与过期证据也必须如实记录。

- 2026-08-25：Codex SDK 架构迁移和核心能力验收通过。旧编排运行时、旧 Provider URL 和旧示例入口移除；`CodexReasoner` 只读、deny-all、ephemeral；`CodexCustomerTester` 以五个有界维度回合生成并校验客户旅程，确定性 Runner 记录 request/response/observation event evidence，浅层计划、缺覆盖、失败、未知、无证据和越权 review finding 均不判通过；22 项测试、Ruff、compileall、Skill quick_validate、CLI 和真实 Codex fixture smoke 通过。没有真实目标 Agent 业务结论，待用户提供目标后执行 F-017。证据：E-038..E-040。
- 2026-08-08：旧路线真实 LLM 接入验收通过。受管 `deepseek` 配置完成真实 OpenAI-compatible 请求；首轮不合规字段被拒绝，单次校正回合后生成 Workflow 提案；旧 Runner 在基线 PASS 后接收 proposal，无人工批准时记录控制边界并 rejected，`applied=false`；构建 wheel 在全新 Python 3.10 venv 中完成同样回归。证据 E-033..E-037；仅协议和治理边界通过，领域质量未验收。
- 2026-08-03：P2 单团队受控工作流演化纵切验收通过。旧 Optimizer 通过 AgentServices 生成 WorkflowRevisionProposal；旧 ProductionControlPlane 携 Owner token 完成人工审批/应用；不同 revision composition 重新执行客户旅程；非执行变更不能伪造金丝雀；有害结果冻结并回滚。权限 fencing 与 composition 复用暴露的失败记录为 E-029，成功证据为 E-030..E-032。该路线已退出当前产品。
- 2026-08-03：P2 旧运行时纵切验收通过。完成五 Department 注册、Workflow 招聘、七角色执行树、scope-bound EvidenceRef、Checkpoint 和 9 Agent 后序释放；被测结果 PASS/BLOCKED/FAIL 未被编排层改写。目录路由和 SQLite 句柄的中间失败记录为 E-024/E-027。该纵切已退出当前产品。
- 2026-07-31：P0 独立内核验收通过。13 项测试、Ruff、compileall、CLI/示例、wheel 构建、干净安装和旧外部编排注册 smoke 均通过。P1/P2 未实现，不能将本结果写成完整 Agent 测试产品或生产验收。
- 2026-07-31：P1 纠正与推理提案边界验收通过。19 项测试、Ruff、compileall、更新 wheel 构建和干净安装均通过。外部真实 LLM Provider 未调用；本地 HTTP 回环只验证协议与治理边界，不代表模型质量。
- 2026-07-31：P1 异步 Job、FixtureEnvironment 和副作用门禁验收通过。22 项测试、Ruff、compileall、更新 wheel 构建和干净安装均通过；异步未知结果保持 `INCONCLUSIVE`，读场景对写适配器保持 `BLOCKED`。
- 2026-07-31：完整性检查通过：23 项测试、Ruff、compileall、pip wheel、干净 venv 导入和凭据模式扫描通过。真实 ResumeProbe FastAPI 健康只读旅程通过，5 条账本事件且无 findings；不扩展为上传/LLM/生产验收。
- 2026-08-01：Skill 通过校验并完成两个指定 Agent 实测。M8 8000 的四个真实 HTTP 场景通过，错误断言明确失败；Yunpai 9000 原部署首次拒绝连接，隔离临时 uvicorn 入口健康通过；Yunpai 测试套件发现 1 个周末日期依赖失败，未修改目标源码。
- 2026-07-31：项目账本初始化完成，证据 E-001。
