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
| catalog-foundation | in-progress | 无（隐私交付阻塞已解除） | 2026-10-30 | R3软件通过/N1关闭、原软件Gate2已批；隐私R5与本轮Gate2亦通过，两分支历史已受保护更新并远端复扫、本机迁移完成。交接与PR #1正常匿名UTC合并完成；最新代码本机489通过/61跳过，合并后T-39隔离目标483通过/0跳过（含新增4个DB项）；旧446/36k仅各自候选证据；T-25已获准部署（2026-10-30，两容器健康、限额/只读挂载/绑定核验通过、匿名401，登录态冒烟完成）；T-26已获准执行（基本通过，画布 `pages` 结构发现F-1须修复后重导复验）；v0根镜像重建另议，不把软件交付当全量验收。 |
| public-release-privacy | done | 无 | 2026-10-30 | 7R/25AC实施/独立R5及用户Gate2通过，原阻断闭合；A4最终72提交/483blob/699文本及独立555记录0未处置。origin两分支一次原子精确lease更新，新取远端复扫及本机CAS迁移完成，仍Public；交接与PR #1合并完成，合并后新取两ref复扫通过。三项非阻断与未验已明示接受，平台副本/未知格式不绝对保证；其他远端/部署不动，旧引用/原件私下保全禁止回传。 |

状态取值：`in-progress` / `blocked` / `done`。feature 开始、阻塞、完成时必须更新本表；
依赖未满足的 feature 不得进入 Plan。
