# Feature: catalog-foundation 质量检查清单（checklist.md）

> Checklist 阶段产物，由审核员生成并勾选。仅当审核员认为某项检查标准得到满足时才标记为通过；
> 通过只代表需求质量达标，不代表实施完成。实施者不勾选本文件。
> 审核员 A（claude-fable-5-1）在独立会话中审核，规则见 AGENTS.md §2 第 5 步。第 7 轮及以前另有审核员 B（gpt-6.1-sol），按两人共识勾选。

## 检查项

| 编号 | 检查项 |
|---|---|
| CHK-01 | 每条需求都有至少一条可验证的验收规则 |
| CHK-02 | 无未澄清歧义（spec §5 已闭环） |
| CHK-03 | 目标与非目标边界清晰 |
| CHK-04 | spec / plan / tasks 之间无冲突（Analyze 报告无遗留问题；tasks.md 写成后评） |
| CHK-05 | spec 与 plan 都与 docs/ 决策和 ADR 无冲突 |
| CHK-06 | 每条验收规则可映射到单元测试或手动验收步骤 |
| CHK-07 | 任务粒度与验证命令满足 tasks.md 模板要求（tasks.md 写成后评） |
| CHK-P1 | plan.md §5 为每条 AC 给出实现位置与能证明该 AC 的验证方式 |
| CHK-P2 | plan 与 spec 需求一一对应，无超出、无遗漏 |
| CHK-P3 | 部署满足 D-005 内存红线与 R-012 只读要求，不改动 v0 |
| CHK-P4 | Plan 与 Checklist 阶段发现的需求问题已回到 Clarify 闭环 |
| CHK-P5 | spec 与 plan 遵守 AGENTS.md §2 工程约束：不为臆测的边界情况加复杂度，只在系统边界校验，测试测真实实现 |

第 1～7 轮另有按需求展开的 CHK-R001～R013，与 CHK-01、02、06 重复，第 8 轮起取消。

## 当前结果

<!-- R9_RESULT -->

## 历史

| 轮次 | 审阅提交 | 审核员与通道 | 结果（通过 / 未通过） | 去向 |
|---|---|---|---|---|
| 1 | `private-candidate-008`：spec 第 1 版 + Clarify 第二轮，plan 第 1 版 | A via claude-bridge，B via openai | 共识 8 / 13 | spec、plan 第 2 版 |
| 2 | `private-candidate-009`：第 2 版 | 同上 | 共识 13 / 9 | 第 3 版 |
| 3 | `private-candidate-010`：第 3 版 | 同上 | 共识 15 / 7 | 第 4 版 |
| 4 | `private-candidate-011`：第 4 版 | 同上 | 共识 14 / 8 | 第 5 版 |
| 5 | `private-candidate-012`：第 5 版 | A 未运行（claude-bridge 接入不可用），B via openai | 未形成共识（B 15 / 7） | 第 6 版 |
| 6 | `private-candidate-014`：spec 第 6 版、plan 第 6 版 | A via anthropic（claude-bridge 接入不可用），B via openai | 共识 21 / 1（CHK-P2：读不了的 TIFF 会被判为 BnF 原图） | plan 第 7 版 |
| 7 | `private-candidate-015`：spec 第 6 版、plan 第 7 版 | 同上 | A 21 / 1，B 19 / 3（plan 第 7 版新增的「其余编号每次重新解析」会清空整件缺失写卷的编号；v0 链接改为只用成功导入的快照，与 spec 不符） | 两处新增随第 8 版精简删去；审核员 B 自第 8 轮起取消 |
| 8 | `private-candidate-016`：spec 第 7 版（精简）、plan 第 8 版 | A via anthropic（claude-bridge 接入不可用） | 10 / 0，无阻断 | 采纳非阻断建议 1～6、8、10（措辞澄清；待确认编号的定义；v0 快照单独提交；附件边读边写；派生来源不明的原因）；7、9、11 属罕见或无害情形，不采纳 |

各轮的完整意见见 git 历史中的本文件（第 1～7 轮截至提交 `private-candidate-015`，第 8 轮见 `private-candidate-018`）；问题的最终结论已并入 spec §5。
