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

第 10 轮（2026-10-28，审阅提交 `private-candidate-021`；A = claude-fable-5-1 via anthropic（claude-bridge 接入不可用））：通过 10 项，不通过 2 项，本轮不评 0 项。

- [x] CHK-01：通过
- [x] CHK-02：通过
- [x] CHK-03：通过
- [ ] CHK-04：不通过
- [x] CHK-05：通过
- [x] CHK-06：通过
- [ ] CHK-07：不通过
- [x] CHK-P1：通过
- [x] CHK-P2：通过
- [x] CHK-P3：通过
- [x] CHK-P4：通过
- [x] CHK-P5：通过

<details>
<summary>审核员 A 原文</summary>

### 结论表

| 编号 | 结论 | 理由 |
|---|---|---|
| CHK-01 | 通过 | R-001～R-013 每条都有 2～8 条验收规则；独立核计 4+8+8+5+5+3+4+2+5+2+5+4+3 = 58 条 AC，每条给出可观察的结果、数量或测试数据情形 |
| CHK-02 | 通过 | spec §5 Q-001～Q-025 均有结论与融入位置。第 9 轮四项澄清（§1「国图卷」「待确认编号」、R-003 写卷第 5 条「待确认单元既不新建也不关联」、AC-010-2 旧基线说明）只补定义与说明，13 条需求、58 条 AC 的语义未变，且与 plan §4.2.3 D/E、§2.1「待确认编号不参与 resolve」一致 |
| CHK-03 | 通过 | §2 目标 / 非目标与 D-015、D-016 对齐；Q-024 新资料明确「本版不纳入、须先登记 ADR」 |
| CHK-04 | 不通过 | 两处 tasks 与 AGENTS.md §4 及 tasks 自身「Gate 2 / merge 后才部署正式服务」冲突：T-24 的临时库按 plan §6.2 建在 `catalog-db` 内，等于在 merge 前用候选 compose 起正式数据库并初始化正式 pgdata；T-25 要求在已部署的正式服务 OpenAPI 上「触发合成测试批次」且「不把合成记录写入正式库」，但正式服务只能把真实 `/data` 导入正式库，该步骤不可执行。见阻断 [B1][B2] |
| CHK-05 | 通过 | 384m + 512m、memswap 相等、`/data` `/backup` `/v0cache` 与 v0 `.env` 只读、8504 仅局域网、缺 `AUTH_SECRET` 拒绝全部请求，与 D-005、D-018 一致；不写原图目录（D-008）；原名逐字保留（D-013）；许可默认表与 D-012 逐行一致；部署经 origin → nas main（D-009）；`.gitignore` 现有 `.env` 规则已覆盖 `catalog/.env`，与 D-018「影响」等效 |
| CHK-06 | 通过 | plan §5 为 58 条 AC 各给出 pytest 测试名或 NAS A1～A7 手动项；AC-010-2、AC-011-3（P95）、AC-012-1/3/4 只能在 NAS 证明，tasks 已标为「待验」而非通过 |
| CHK-07 | 不通过 | 26 项估时均在 0.5～2 小时，各有上下文、依赖、修改范围与引用 AC 的完成标准；本机命令具体可执行，数据库项明确「T-24 执行，本机 compileall 不算通过」，T-24 要求 db 项 0 跳过。但 T-25 的验证步骤无法在正式服务上执行、T-24 未写明临时 PostgreSQL 来自何处（[B1][B2]）；另有若干 `-k` 词与 plan §5 测试名不对应（非阻断 1） |
| CHK-P1 | 通过 | 逐条核对 §5：验证方式能证明该 AC，例如 AC-003-7 同时有打乱单元顺序的单元测试与数据库端到端互换、AC-003-5 覆盖 spec 列出的五种情形并验证改回后不再列入、AC-012-2 记录导入期间打开的全部路径、AC-011-3 本机筛选 + NAS A6 P95、AC-010-2 以 NAS A2 基线对照 |
| CHK-P2 | 通过 | 13 条需求全部落到 plan §2～§4；plan 额外的 `/images/{id}`、`/images/{id}/history`、`/attachments/{id}` 分别服务 AC-013-3 与 AC-008-2，「对外策略」列来自 D-012，无其他超出；AC-005-2 读不了的 TIFF 处理已在第 8、9 轮接受 |
| CHK-P3 | 通过 | catalog-db 384m、catalog-api 512m 且 memswap 相等；三个数据根与 v0 `.env` 均 ro；pgdata 在 `/srv/example/catalog/` 而非 git 工作区；不改 v0 compose、不重建或重启 v0（T-22、T-25）；回滚只需 `down` + 删 pgdata；只读元数据不解码整幅影像 |
| CHK-P4 | 通过 | 第 9 轮建议 1～3、5 经 Gate 1 批准后写入 spec §1、R-003、AC-010-2；plan 第 8 版、tasks 未私改需求：T-04「不为拼接临时 TIFF 加排除」、T-11「不为备份目录不同步改名加规则」、T-16「不恢复暂停 / 中止」、T-19「无 CLI 导入入口」均与 spec 与 Q-025 一致 |
| CHK-P5 | 通过 | 校验只在 scan / nlc / derivation / api / v0 入口；不引入 ORM、迁移框架、任务队列、后备份；只有 v0 HTTP 用替身，T-15 按 app.py 协议生成 cookie 调真实校验函数，T-23 的 compare 只比较报告不重算业务；无 Q-025 规则回流。轻微冗余（基线对照在 importer 与 compare.py 两处）见非阻断 2 |

### 阻断问题

[B1] `specs/catalog-foundation/tasks.md` T-25「完成标准」第二句与「验证命令」末句 — T-25 是部署已 merge 的正式服务，其 `POST /api/v1/imports` 只会把挂载的真实 `/data`、`/backup` 导入正式库；「先用独立测试库 / 合成数据完成小批导入，不把合成记录写入正式库」与「管理员在 OpenAPI 触发合成测试批次」在正式服务上无法做到，照做就是在 T-26 许可与低峰窗口之外跑一次真实全量导入。「secret 缺失拒绝服务」也需要去掉 `/run/v0.env` 挂载再起一个容器变体，等于重复 T-24。 — 最小修法：删去这三处；T-25 只核验部署前提（项目独立、`docker inspect` 的只读挂载与限额、数据库无宿主端口、`python -m dh_catalog health`、未登录 401 / 普通用户 POST 被拒 / 管理员 GET 通过、v0 未重启），fail-closed 与合成导入行为以 T-24 的 test_auth / test_api / test_import 结果为证；首次导入即 T-26。

[B2] `specs/catalog-foundation/tasks.md` T-24「验证命令」与 `specs/catalog-foundation/plan.md` §6.2 — T-24 只说「设置临时库 URL」，临时 PostgreSQL 从哪来由 plan §6.2 给出：「在 `catalog-db` 中临时建的测试库」。`catalog-db` 是 `dunhuang-catalog` 项目的正式服务，挂载正式 pgdata `/srv/example/pgdata`，在 Gate 2 / merge 前用候选 compose 把它拉起来，就是部分部署未合并的配置，并用测试位置的 `.env` 口令初始化正式数据目录；T-25 再从部署目录以同一项目名 `up` 时，容器被重建而 pgdata 已按旧口令初始化，`catalog-api` 连不上，只能清 pgdata 重来。这与 T-24 自己写的「Review / Gate 2 / merge 后才部署正式服务」矛盾。 — 最小修法：plan §6.2 与 T-24 改为一次性容器：`docker run --rm --memory 384m --memory-swap 384m -e POSTGRES_PASSWORD=<随机> postgres:17.4-alpine3.21`（不挂宿主数据卷），镜像用 `docker build -t dh-catalog-test <隔离位置>/catalog` 构建（不用 `-p dunhuang-catalog`），测试容器 `docker run --rm` 只挂合成目录；候选代码经 `git push nas <分支>`（非 main）加 `git worktree add` 或 `git archive` 放到隔离位置；跑完删容器即删库。

顺序核对：除上述两点外，Gate 2 / merge / 部署 / 运行验收可按 AGENTS.md 执行——T-01～T-23（本机）→ T-24（一次性容器测试，不是部署）→ Converge → Review → Gate 2（review.md 把 AC-010-2、AC-011-3、AC-012-1～4 等 NAS 项列为待验）→ Handoff merge → T-25 `git push nas main` 并只起 `dunhuang-catalog` → T-26；T-26 发现的缺口以新提交重走 Review → Gate 2 → merge → push nas，不需要偷跑。唯一要靠偷跑才能完成的环节就是 [B2] 现写法下 T-24 对正式 `catalog-db` 的依赖。两处修法都是 tasks.md / plan.md 的文字修正，不改需求，不需重过 Gate 1。

Analyze：不可进入 Implement

### 非阻断建议

1. tasks 的若干 `-k` 词在 plan §5 中没有对应测试名，命中其他项即整条命令通过，该 AC 会被当作已验证：T-04 `names`（AC-008-1 在 plan §5 为 `test_import.py::test_raw_names_verbatim`）、T-07 `attachments`（`test_import.py::test_attachments`）、T-09 `reappearance` / `changed`、T-10 `missing`（均在 test_import.py）、T-17 `rollback` / `reimport`（后者在 test_identity.py）、T-20 `history` / `attachment`。建议二选一：在 plan §5 补上对应的本机测试名（plan §6.1 本就说影像身份测试在临时目录中真实删除与还原），或从 `-k` 与完成标准中删去，并在记录验证结果时核对 deselected 数。
2. 基线对照写在两处：plan §3 `import_run`「基线对照」列与 §4.1 第 8 步由 importer 计算，§2 / §6.3 与 T-23 又有 `acceptance/compare.py`「只比较导入报告」。保留一处即可（建议只留 compare.py 读报告比较，importer 只存计数），避免两套统计规则。
3. T-26「影响既有评审结论的再过 Gate 2」留有口子：merge 后的任何代码修复都改变了已评审的 diff，按 AGENTS.md 只能 Review → Gate 2 → merge → push nas 后再部署；建议把这句改为无条件。
4. T-15 读取 `/run/v0.env` 的 `AUTH_SECRET` 应按 compose `env_file` 语义取值（去掉首尾空白与成对引号），否则若 v0 `.env` 带引号，T-25 的登录核验会全部 401；在 test_auth 中加一个带引号的用例即可。

</details>

## 第 10 轮处理（待第 11 轮复核）

- B1：T-25 删除正式服务上的合成导入与修改 secret；只做只读冒烟，正式首次导入留 T-26。
- B2：plan §6.2 与 T-24 改为候选快照 + 一次性 PostgreSQL / 测试容器，不启动正式 compose、不挂真实材料或正式 pgdata；正式部署仍在 Gate 2 / merge 后。
- 同时采纳四条非阻断建议：去掉模糊 `-k`；基线比较只留 compare.py；部署后的代码修复无条件再过 Review / Gate 2；secret 读取支持空白与成对引号。均不改需求。
- 第 10 轮未通过结论保留如上；未获第 11 轮全项通过前不实施。

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
