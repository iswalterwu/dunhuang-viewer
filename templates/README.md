# templates/ — spec-driven 工作流模板

每个新功能从 `specs/<feature>/` 开始，按 AGENTS.md §2 的工作流推进，产物用本目录模板起稿。

| 工作流步骤 | 产物 | 模板 |
|---|---|---|
| Spec / Clarify | `specs/<feature>/spec.md` | [spec.md](spec.md) |
| Plan | `specs/<feature>/plan.md` | [plan.md](plan.md) |
| Checklist | `specs/<feature>/checklist.md` | [checklist.md](checklist.md) |
| Tasks | `specs/<feature>/tasks.md` | [tasks.md](tasks.md) |
| Analyze | 只读报告（不落库） | — |
| Implement / Converge | 更新 tasks.md | — |
| Review | 评审结论 → 口头/会话 | — |
| Handoff | `specs/<feature>/review.md` | [review.md](review.md) |

使用规则：

- 模板只作起点，按 feature 实际情况增删小节；四个固定文件（spec / plan / tasks / review）必须齐备
- spec.md 只写 what/why 与验收规则，技术方案一律放 plan.md
- checklist.md 由审核员生成并勾选；实施者不勾选
- 新建 feature 目录后，用对应模板起稿，再走 Clarify → … → Handoff
