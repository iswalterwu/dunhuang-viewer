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
| catalog-foundation | in-progress | 无 | 2026-10-30 | spec7（13R/58AC）与plan10冻结。旧候选private-candidate-056/T36：目标Python3.12/PG17.4全442通过/0skip，原512m内36k差异化两轮成功，cgroup含缓存触512/无OOM，临时资源清理、v0未重启；独立R2软件通过、CR1-01代码级及02/05关闭。用户本轮「同意并继续」批准N1/P3最小修复、隔离真PG复验与独立重审，T37/T38经Analyze16全12项通过，P14已实现最小两个函数+6/-1与回归；主会话本机389通过/57skip/1原有警告（446项），A1/private-candidate-061真PG445通过/1新HTTP期望错误保留，P15仅测试一行已修；A2/private-candidate-063目标全446通过/0skip/1原有警告（73.22秒，57db实际），资源全清理/v0未重启，独立R3软件通过/N1关闭（审private-candidate-064），待用户Gate2；本轮未新36k，不沿用旧442或36k冒充新代码证据。未Gate2/merge/push nas/部署/真实导入，T25/T26与真实材料/并发/健康/性能仍待独立许可；功能分支持续同步，详情见tasks.md、review.md与HANDOFF.md |

状态取值：`in-progress` / `blocked` / `done`。feature 开始、阻塞、完成时必须更新本表；
依赖未满足的 feature 不得进入 Plan。
