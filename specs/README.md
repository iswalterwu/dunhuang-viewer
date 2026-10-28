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
| catalog-foundation | in-progress | 无 | 2026-10-28 | Gate 1 已批准并冻结 spec 第 7 版（13 条需求 / 58 条验收规则，含第 9 轮措辞澄清）；plan 第 8 版；Checklist 第 8、9 轮均无阻断；第 11 轮 Analyze 由 A 判定全部 12 项通过；Implement 分支 feat/catalog-foundation：已完成 T-01、04～09 的本机模块与测试，具体证据见 tasks.md；写卷归并、数据库与接口未完成，NAS 测试与部署待另获许可 |

状态取值：`in-progress` / `blocked` / `done`。feature 开始、阻塞、完成时必须更新本表；
依赖未满足的 feature 不得进入 Plan。
