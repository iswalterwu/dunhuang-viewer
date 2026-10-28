# Feature: catalog-foundation 质量检查清单（checklist.md）

> 由审核员 A（claude-fable-5-1）在独立只读会话审核；规则见 AGENTS.md §2。实施者只机械记录审核员结论，不自行勾选。
> 检查通过只代表规格与方案 / 任务质量达标，不代表实现或 NAS 验收完成。第 7 轮及以前另有审核员 B，按双人共识判断。

## 检查项

| 编号 | 检查项 |
|---|---|
| CHK-01 | 每条需求都有至少一条可验证的验收规则 |
| CHK-02 | 无未澄清歧义（spec §5 已闭环） |
| CHK-03 | 目标与非目标边界清晰 |
| CHK-04 | spec / plan / tasks 之间无冲突，Analyze 无遗留阻断问题 |
| CHK-05 | spec 与 plan 都与 docs/ 决策和 ADR 无冲突 |
| CHK-06 | 每条验收规则可映射到单元测试或手动验收步骤 |
| CHK-07 | 任务粒度与验证命令满足 tasks.md 模板要求 |
| CHK-P1 | plan.md §5 为每条 AC 给出实现位置与能证明该 AC 的验证方式 |
| CHK-P2 | plan 与 spec 需求一一对应，无超出、无遗漏 |
| CHK-P3 | 部署满足 D-005 内存红线与 R-012 只读要求，不改动 v0 |
| CHK-P4 | Plan 与 Checklist 阶段发现的需求问题已回到 Clarify 闭环 |
| CHK-P5 | spec / plan / tasks 遵守 AGENTS.md §2 工程约束 |

## 当前结果

<!-- R10_RESULT -->

## Gate 1 与建议处理（2026-10-28）

用户回复「批准，继续」，确认 spec 第 7 版、Q-009 撞号不自动合并及按建议继续：合入第 9 轮非阻断建议 1～3、5（待确认单元不另行关联、两项术语、旧基线与新增资料的差异说明），不为其余情形增加规则。规格现已冻结；本轮检查包含新建 tasks.md，CHK-04、CHK-07 不再豁免。NAS 测试与部署仍需单独许可。

## 历史

| 轮次 | 审阅提交 | 审核员与通道 | 结果（通过 / 未通过） | 去向 |
|---|---|---|---|---|
| 1 | `private-candidate-008`：spec 第 1 版 + Clarify 第二轮，plan 第 1 版 | A via claude-bridge，B via openai | 共识 8 / 13 | spec、plan 第 2 版 |
| 2 | `private-candidate-009`：第 2 版 | 同上 | 共识 13 / 9 | 第 3 版 |
| 3 | `private-candidate-010`：第 3 版 | 同上 | 共识 15 / 7 | 第 4 版 |
| 4 | `private-candidate-011`：第 4 版 | 同上 | 共识 14 / 8 | 第 5 版 |
| 5 | `private-candidate-012`：第 5 版 | A 未运行（claude-bridge 接入不可用），B via openai | 未形成共识（B 15 / 7） | 第 6 版 |
| 6 | `private-candidate-014`：spec 第 6 版、plan 第 6 版 | A via anthropic（claude-bridge 接入不可用），B via openai | 共识 21 / 1（CHK-P2：读不了的 TIFF 会被判为 BnF 原图） | plan 第 7 版 |
| 7 | `private-candidate-015`：spec 第 6 版、plan 第 7 版 | 同上 | A 21 / 1，B 19 / 3（整件缺失的编号被清空；v0 链接限制与 spec 不符） | 两处新增随第 8 版精简删去；第 8 轮起取消 B |
| 8 | `private-candidate-016`：spec 第 7 版、plan 第 8 版 | A via anthropic（claude-bridge 接入不可用） | 10 / 0，无阻断，2 不评 | 采纳建议 1～6、8、10；其余不增规则 |
| 9 | `private-candidate-019`：spec 第 7 版、plan 第 8 版 | A via anthropic（claude-bridge 接入不可用） | 10 / 0，无阻断，2 不评 | Gate 1 批准；建议处理见上 |

第 1～7 轮的完整意见见本文件截至 `private-candidate-015` 的 git 历史，第 8 轮见 `private-candidate-018`，第 9 轮见 `private-candidate-020`。第 8 轮起取消与 CHK-01、02、06 重复的 CHK-R001～R013；最终需求结论只保留于 spec §5。
