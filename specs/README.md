# specs/ — 功能规格目录

每个功能性 feature 一个独立规格目录，例如 `catalog-foundation`、`name-normalization`、`annotation-workbench`（Phase 1 候选，见 `docs/plan.md` §8）。

```
specs/<feature>/
├── spec.md       # 需求：what/why + 验收规则（Spec / Clarify 阶段）
├── plan.md       # 实施设计（Plan 阶段）
├── tasks.md      # 任务分解（Tasks 阶段；Implement/Converge 更新）
├── review.md     # 评审与交接（Handoff 阶段）
└── checklist.md  # 质量检查清单（Checklist 阶段，审核员生成并勾选）
```

- 工作流与各阶段规则见根目录 `AGENTS.md` §2
- 模板在 `templates/`
- 本目录是功能实施的唯一入口：先有规格、后有代码

## 状态表（多 feature 并行时必维护）

| feature | 状态 | 依赖 | 最近更新 | 备注 |
|---|---|---|---|---|
| catalog-foundation | in-progress | 无 | 2026-10-28 | Gate 1 已批准第 1 版 → Plan 与 7 轮 Checklist（结果见 checklist.md）→ spec 第 7 版（按 AGENTS.md 工程约束精简：13 条需求 / 58 条验收规则）与 plan 第 8 版；Checklist 第 8 轮（只设审核员 A）进行中；之后待 Gate 1 再批准 |

状态取值：`in-progress` / `blocked` / `done`。feature 开始、阻塞、完成时必须更新本表；
依赖未满足的 feature 不得进入 Plan。
