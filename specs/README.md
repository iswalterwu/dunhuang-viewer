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
| catalog-foundation | blocked | public-release-privacy（仅交付依赖） | 2026-10-30 | 原软件Gate2已批、R3软件通过/N1关闭；既有目标446全通过属于原候选，不代表后续脱敏代码已验。用户已选择保持Public并全面清理隐私，D-019已登记；交接/PR/合并等待公开发布清理与历史处置决定。未推送/创建PR/合并/部署/真实导入，T25/T26仍另许可，当前变化仅本机。 |
| public-release-privacy | in-progress | 无 | 2026-10-30 | 全树457已跟踪文件+1本机记录、历史730文件对象已只读盘点；7R/25AC已获用户Gate1批准；最小必要源码/配置/脚本及两分支历史/提交者清理、受保护更新origin授权已明确。Tasks后独立Analyze12项全通过、B-1设计层关闭，准备按PRIV-01～07派发Astra；尚未批量脱敏/历史改写或推送；其他远端、部署与新的私人主机测试不在授权内，原值与备份仅仓库外保留。 |

状态取值：`in-progress` / `blocked` / `done`。feature 开始、阻塞、完成时必须更新本表；
依赖未满足的 feature 不得进入 Plan。
