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
| catalog-foundation | in-progress | 无 | 2026-10-29 | Gate 1 已批准并冻结 spec 第 7 版（13 R / 58 AC）、plan 第 8 版；第 11 轮 Analyze 全部 12 项通过。feat/catalog-foundation 的 T-01～T-24 实现与对应自动化验证完成；T-24 经许可在 Python 3.12.15 / PostgreSQL 17.4 一次性容器实测，Astra 最小修复两处 CLI 测试后，A2 为 402 passed / 0 skipped / 1 warning，临时资源全部清理，v0 未重启。Converge发现C1后由P7 Astra最小修复，A3新候选404 passed/0 skipped/1 warning且资源清理完成；58条AC证据矩阵在converge.md，独立R1结论仍为「需修复后重审」。用户批准后P8/P9最小修复候选private-candidate-042已在NAS/3.12/真PG全412项通过、0跳过，两项P3实现/真库回归完成；但6k真PG重导RSS175.71MiB、两点36k趋势668.83MiB仅外推，P1未闭。已按停止条件暂停扩大/实施，待用户是否批准T31回Plan/Analyze讨论S0读取；未启动R2、未过Gate2，本轮临时资源也已清理、v0未重启；未 merge main、未部署，T-25/T-26 与真实材料/全量/性能验收仍待许可。GitHub 功能分支持续同步，证据见 tasks.md 与 HANDOFF.md |

状态取值：`in-progress` / `blocked` / `done`。feature 开始、阻塞、完成时必须更新本表；
依赖未满足的 feature 不得进入 Plan。
