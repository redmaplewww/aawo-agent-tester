# Codex Agent Tester 技术方案

## 1. 产品目标

系统替真实客户操作陌生 Agent，并回答两个问题：

- 客户能否按照自然使用方式完成目标？
- Agent 声称提供的能力是否有输入、输出、错误和恢复证据，而不是只有接口存在或模型自评？

系统服务任意领域，但不把“任意领域”解释成一套固定业务断言。领域语义由 Codex 从客户目标、Agent 声明、样例和实际响应中提出，实际结论由确定性执行器和证据账本约束。

## 2. 分层架构

```text
Codex SDK thread
  ├─ contract discovery
  ├─ customer journey planning
  └─ evidence review / completeness hypothesis
          ↓ validated JSON
Deterministic tester kernel
  ├─ Adapter: callable / HTTP / CLI / async job
  ├─ CustomerSimulationRunner
  ├─ schema + business assertions
  ├─ friction and hostile-workflow detection
  └─ append-only SQLite EvidenceLedger
          ↓ immutable observations
Settled report
  ├─ PASS / FAIL / BLOCKED / INCONCLUSIVE
  ├─ implementation coverage: covered / missing / inconclusive
  └─ customer-visible findings and limitations
```

Codex 是理解和复核能力，不是执行权威；没有 AAWO、工作流注册表或外部编排运行时依赖。
真实 Codex SDK 使用五个有界的维度发现回合再合并计划，避免一个超大结构化回合卡住；每个回合仍经过同一严格解析器，冲突契约保持未确认。

## 3. 客户仿真协议

每条 Codex 旅程必须包含：

- 客户目标和角色；
- 至少一个真实 `user_input`；
- 至少一个 `expect` 或 `observe`；
- `observe` 必须调用适配器的真实观察边界，并把观察结果写入账本；不能把上一次响应的副本冒充观察；
- 正常、异常或不完整输入中的明确覆盖维度；
- 输入/输出契约检查；
- 适配器副作用策略。

支持的断言只有 `contains_keys`、`text_contains`、`status_is`、`path_equals` 和 `no_error`。未知断言直接阻塞，避免测试器替模型“猜”如何通过。任意领域的 payload、schema 和 path value 以 JSON 字符串跨 SDK schema 传递，再由本地解析器还原，避免把领域字段硬编码进测试器。

## 4. 实现完整性检查

默认要求 Codex 映射以下最低覆盖维度：

1. 正常成功；
2. 不完整或非法输入；
3. 输出契约；
4. 失败恢复；
5. 重复输入或用户纠正。

用户声明的能力还必须映射到一个或多个场景。场景未执行、被阻塞或结果未知时，能力不能标为已实现。对写操作只接受隔离 fixture 或明确人工批准；未知副作用保持 `INCONCLUSIVE`。

## 5. 用户纠正与演进

用户纠正通过现有 `UnderstandingEngine` 写入新的 Profile revision，旧假设标记为 superseded；`CorrectionImpactAnalyzer` 生成最小回归计划，新的 Run 使用新的 revision 和新证据。Codex 可以提出修改，但不能直接应用，也不能删除失败记录。

## 6. 关键验收

- Codex SDK 未登录时报告 blocked，不伪造测试结果；
- Codex 输出结构不完整、引用不存在的证据或产生未知断言时阻塞；
- 客户旅程的真实输入/响应进入账本，失败不会变成 pass；
- 缺少实现覆盖时报告 incomplete；
- 用户纠正后旧 Profile、证据和回归范围仍可追溯；
- 同一确定性内核可在无 Codex 的离线 fixture 中运行；
- 所有写操作和未知副作用都有明确门禁。
