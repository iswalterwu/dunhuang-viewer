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
| catalog-foundation | in-progress | 无 | 2026-10-28 | Gate 1 已批准并冻结 spec 第 7 版（13 条需求 / 58 条验收规则，含第 9 轮措辞澄清）；plan 第 8 版；Checklist 第 8、9 轮均无阻断；第 11 轮 Analyze 由 A 判定全部 12 项通过；Implement 分支 feat/catalog-foundation：T-01、04～16 的本机模块完成，T-13/14 已由 GPT 6 Astra 子 agent 并行实现并经主会话复验；T-02、03 数据库代码待真实验证。T-17～19 导入器 / 历史 / 报告代码及本机计算回归已写成，真实数据库路径待验；T-20/21 查询 / 触发 API 与 health 已写成，真实 DB / HTTP 集成待验；运行文件和验收入口仍待实现。测试证据见 tasks.md，NAS 测试与部署待另获许可 |

状态取值：`in-progress` / `blocked` / `done`。feature 开始、阻塞、完成时必须更新本表；
依赖未满足的 feature 不得进入 Plan。
