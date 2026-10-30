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

第16轮（2026-10-30，审阅private-candidate-059，N1新T37/T38后的Analyze；实际anthropic/claude-fable-5-1）：**12通过/0不通过/0不评，无阻断，允许仅T37/T38进入Implement**。调度meta/status实际09:48:03～09:55:40 （原始时刻；时区非公开）、exit0，前后HEAD/工作区固定干净；桥仍在已证实的接入不可用状态，引用R1原证据未重试。原文/meta/status/提示词/哈希 N1-Analyze16（非公开历史记录）。以下按审核员结论机械录入，不代实际实现、目标复验、独立CodeReview-R3或用户Gate2。

- [x] CHK-01：通过
- [x] CHK-02：通过
- [x] CHK-03：通过
- [x] CHK-04：通过
- [x] CHK-05：通过
- [x] CHK-06：通过
- [x] CHK-07：通过
- [x] CHK-P1：通过
- [x] CHK-P2：通过
- [x] CHK-P3：通过
- [x] CHK-P4：通过
- [x] CHK-P5：通过

本轮非阻断建议交派发/复验：compute S0可没有id，不以old['id']强取；保留存在的旧元数据，不改S0；只UPDATE实际改变的field_basis且复用私有Jsonb编码边界；固定新测试名与红→绿原输出留证，真库覆盖current/pending/NLC多来源与旧/新history/无变化重跑。T38不自动重跑36k，不把旧候选资源实测冒充新代码；R3据差异评证据边界，后续按实际可用性依规则先试首选通道。实施期间本清单冻结，不因测试绿另勾项。

### 第15轮历史（Plan10 Tasks后的Analyze）

第15轮（2026-10-29，审阅private-candidate-053；实际anthropic/claude-fable-5-1）：**12通过/0不通过/0不评，无阻断，允许仅T34/T35/T36进入Implement**。21:56:02～22:08:52 （原始时刻；时区非公开），exit0、工作区无修改；桥已证实的接入不可用状态引用R1原证据未调用。原文/meta/status/提示词/哈希 Plan10-R15（非公开历史记录），不代代码Review/Gate2或实际资源通过。

当时非阻断建议：固定投影输入/字节JSON；解析器code识别weakref、禁方法缓存自环；CompactMap缺key/get/contains/幂等/弱引用形状池；GC小测试finally恢复；私有Jsonb dumps与状态表同步。原12项全通过表与完整理由保留在上述原文。

### 第14轮历史（Plan→Checklist）

第14轮（2026-10-29，审阅private-candidate-052，Plan10→Checklist；实际anthropic/claude-fable-5-1）：**10通过/0不通过/2本轮不评，无阻断，可进入Tasks，尚不能Implement**。21:36:27～21:49:41 （原始时刻；时区非公开），exit0、无仓库修改。首选桥仍在已证实的接入不可用状态，本轮引用R1 bridge.err未重试，实际Anthropic。原文/提示词/meta/status/哈希 Plan10-R14（非公开历史记录），以下仅机械录入，不代CodeReview-R2/Gate2。

- [x] CHK-01：通过
- [x] CHK-02：通过
- [x] CHK-03：通过
- [ ] CHK-04：本轮不评；新Tasks/Analyze后补评
- [x] CHK-05：通过
- [x] CHK-06：通过
- [ ] CHK-07：本轮不评；新Tasks后补评
- [x] CHK-P1：通过
- [x] CHK-P2：通过
- [x] CHK-P3：通过
- [x] CHK-P4：通过
- [x] CHK-P5：通过

建议处理：采纳1补history/report消费者；2限定按对象Jsonb dumps，不全局改驱动且identifier普通dict判定不动；3解析器可weakref、只setprofile观察真实返回/下一阶段，测试可临时禁用循环GC并finally恢复以防残环假绿（非生产GC调参、不用业务monkeypatch）；4紧凑映射单测覆盖顺序/淘汰/双向相等/TypeError/JSON与未知类型失败；5公开S0 builder/规范化测试改法；6操作投影公式写入新任务。待Tasks/Analyze实际全项通过才实施。

### 旧plan9第13轮（历史结果）

第13轮（2026-10-29，审阅`private-candidate-045`，plan9/spec7，Tasks后的Analyze；A = anthropic/claude-fable-5-1）：**12通过 / 0不通过 / 0不评，无阻断，允许仅T31/T32进入Implement**。12:00:38～12:09:43 （原始时刻；时区非公开），自然exit0，工作区无修改。首选桥仍是已证实的接入不可用状态，本轮未调用；实际Anthropic。原文/提示词/meta/status/哈希在 Plan9-R13（非公开历史记录），本段仅机械记录，不代CodeReview-R2/Gate2。

- [x] CHK-01：通过
- [x] CHK-02：通过
- [x] CHK-03：通过
- [x] CHK-04：通过
- [x] CHK-05：通过
- [x] CHK-06：通过
- [x] CHK-07：通过
- [x] CHK-P1：通过
- [x] CHK-P2：通过
- [x] CHK-P3：通过
- [x] CHK-P4：通过
- [x] CHK-P5：通过

非阻断建议机械记录：1 DDL失败不用第二连接读被锁表；2 辅助上下文产出游标、不是yield from行生成器；3 FETCH上界/多批断言容纳整批后的空FETCH，trace仅临时Linux，非支持平台明确skip不冒充目标验证；4 先真实导入再UPDATE JSON null造行错误；5 T32开跑前明确放大安全条件与非tmpfs证据。已交派发/操作约束，不因此扩生产逻辑或新增需求。实施期间本清单不改；新代码仍须实际回归/资源/CodeReview-R2。

### 第12轮历史（Plan→Checklist）

第12轮（2026-10-29，审阅`private-candidate-044`，plan9；A = anthropic/claude-fable-5-1）：**10通过 / 0不通过 / 2本轮不评，无阻断，可进入Tasks，尚不能Implement**。11:42:37～11:50:51 （原始时刻；时区非公开），自然exit0/仓库无修改。首选claude-bridge仍在R1已证实的接入不可用状态，引用 CodeReview-R1 bridge.err（非公开历史记录），本轮未重试；实际Anthropic，不伪称桥审阅。

- [x] CHK-01：通过
- [x] CHK-02：通过
- [x] CHK-03：通过
- [ ] CHK-04：本轮不评；正式新Tasks/Analyze后补评
- [x] CHK-05：通过
- [x] CHK-06：通过
- [ ] CHK-07：本轮不评；正式新Tasks后补评
- [x] CHK-P1：通过
- [x] CHK-P2：通过
- [x] CHK-P3：通过
- [x] CHK-P4：通过
- [x] CHK-P5：通过

原文/提示词/meta/status/哈希：Plan9-R12（非公开历史记录）。以上仅机械录入审核员原表，不代实现Review-R2；待Tasks后独立Analyze全项通过才实施。

建议处理：采纳1补计划测试名、2按错误事务回滚销毁游标而非强断CLOSE、3 Linux临时trace不归档、5同口径S0/硬盘临时目录复验、6限importer/test_import不改db.py；4以真实DDL事务失败与必要的行处理失败测试清理，不新增生产防御规则。详细新任务在Tasks阶段补入，再审，不提前勾04/07。

### 旧plan8历史结果（不作为plan9实施许可）

第 11 轮（2026-10-28，审阅提交 `private-candidate-022`；A = claude-fable-5-1 via anthropic（claude-bridge 接入不可用））：通过 12 项，不通过 0 项，本轮不评 0 项。

- [x] CHK-01：通过
- [x] CHK-02：通过
- [x] CHK-03：通过
- [x] CHK-04：通过
- [x] CHK-05：通过
- [x] CHK-06：通过
- [x] CHK-07：通过
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
| CHK-01 | 通过 | R-001～R-013 共 58 条 AC（4+8+8+5+5+3+4+2+5+2+5+4+3），每条都给出可观察的结果、数量或测试数据情形；本轮 spec 未动 |
| CHK-02 | 通过 | spec §5 Q-001～Q-025 均有结论与融入位置；第 10 轮修订只改 plan §6.2 与 tasks（测试隔离、部署顺序），未触及冻结的 spec 第 7 版，未引入新歧义 |
| CHK-03 | 通过 | §2 目标 / 非目标与 D-015、D-016 对齐；Q-024 新资料明确本版不纳入、须先登记 ADR；tasks「仅新增 catalog/，不改 v0」与非目标一致 |
| CHK-04 | 通过 | B1 已解决：T-25 只做只读冒烟（docker inspect、health、401 / 普通用户 POST 被拒 / 管理员 GET），不删 secret、不 POST 导入，首次导入只在 T-26。B2 已解决：plan §6.2 与 T-24 改为 `git archive` 候选快照 + `docker build -t dh-catalog-test` + 一次性 PostgreSQL（`--rm`、384m=memswap、无宿主卷 / 端口、临时网络）+ `--rm` 测试容器 512m，不启动正式 compose、不碰正式 pgdata、不挂真实材料。顺序 T-01～T-23 → T-24 → Converge / Review → Gate 2（review.md 列待验 NAS 项）→ merge → T-25 push nas 并只起 dunhuang-catalog → T-26，部署后代码修复无条件重走 Review → Gate 2 → merge，无循环、无偷跑。复核 plan §4.2.3 A～E 与 R-003 写卷第 1～6 条逐条对应，AC-003-5 五种情形、AC-003-7 轮换、AC-003-8 增号 / 改写均能由 A～D 得出 spec 规定的结果；58 条 AC 全部落到至少一个任务，任务依赖为无环图。唯一残留是 plan §8 M5 的过时措辞（非阻断 3） |
| CHK-05 | 通过 | D-005 / D-018：384m + 512m、memswap 相等、`/data` `/backup` `/v0cache` 与 v0 `.env` 只读、8504 仅局域网 / Tailscale、缺 `AUTH_SECRET` 返回 503；D-008 不写原图；D-009 merge 后 origin → nas；D-012 许可默认表与 plan §4.4 逐行一致；D-013 原名逐字保留。对照 app.py：cookie 为 base64url(`用户\|过期\|HMAC-SHA256 hex`)、`session_user` 要求用户在 users.json、`/api/health` 不在免登录列表（故须用触发者 cookie 采样）、`/api/index` 的 `status=="ready"` 判定，均与 plan §4.1、§4.7 一致 |
| CHK-06 | 通过 | plan §5 为 58 条 AC 各给出 pytest 测试名或 NAS A1～A7；只能在 NAS 证明的 AC-010-2、AC-011-3（P95）、AC-012-1 / 3 / 4 在 tasks 中归 T-26，T-23 / review.md 列为待验而非通过 |
| CHK-07 | 通过 | 26 项估时 0.5～2 小时，各有上下文、依赖、修改范围、引用 AC 的完成标准与验证命令；`-k` 已全部删除（grep 0 命中）；数据库项明确「T-24 执行、本机 compileall 不算通过、db 项 0 跳过」；T-25 的命令现在可在正式服务上无副作用执行；T-24 的临时 PostgreSQL 来源已写明。T-24 容器内 pytest 依赖镜像含 tests/（非阻断 1），不影响可执行性判断 |
| CHK-P1 | 通过 | 逐 AC 验证方式与第 10 轮相同且足以证明：AC-003-2 在临时目录真实改名 / 移动 / 互换（NTFS 与 btrfs 改名均保留 inode 与 mtime，本机与容器都能跑）；AC-003-7 打乱顺序 + 数据库端到端互换；AC-012-2 记录导入期间打开的全部路径；AC-011-3 本机筛选 + A6 P95；AC-010-2 由 compare.py 读报告对照基线 |
| CHK-P2 | 通过 | 13 条需求全部落到 plan §2～§4；额外的 `/images/*`、`/attachments/{id}`、`excluded`、`v0_volume` 各服务具体 AC；基线对照已只保留 compare.py（§4.1 第 8 步、§6.3 A2、T-23），importer 只存计数；无超出、无遗漏 |
| CHK-P3 | 通过 | 正式部署：catalog-db 384m、catalog-api 512m 且 memswap 相等；三个数据根与 v0 `.env` 均 ro；pgdata 在 `/srv/example/catalog/` 而非 git 工作区；数据库无宿主端口；不改 v0 compose、不重建 / 重启 v0。T-24 一次性容器同样硬限额、不挂真实材料；回滚 down + 删 pgdata。只读文件头不解码整幅影像 |
| CHK-P4 | 通过 | 第 10 轮两处修订与四条建议均为测试隔离、部署顺序、验证命令、读 secret 的实现细节，未改需求；spec 第 7 版原样；tasks 明确不恢复 Q-025 规则（T-04、T-09、T-11、T-16） |
| CHK-P5 | 通过 | 校验只在 scan / nlc / derivation / api / v0 入口；不引入 ORM、迁移框架、任务队列、后备份；只有 v0 HTTP 用替身，文件系统、数据库、接口都测真实实现；T-15 按 app.py 协议外部生成 cookie 调真实校验函数；compare.py 只读报告不重算业务；一次性测试容器不为罕见情形加机制 |

### 阻断问题

无

Analyze：可以进入 Implement

### 非阻断建议

1. `tasks.md` T-22 / T-24 — T-24 要在 `dh-catalog-test` 容器内执行 `python -m pytest tests acceptance/test_compare.py`，前提是镜像含 `tests/`、`acceptance/`、`pytest.ini` 且 requirements.txt 含 pytest。v0 的 Dockerfile 只 COPY 单个文件，若 `catalog/Dockerfile` 照此写法，容器内会报「file or directory not found」，需改 Dockerfile、重新 archive 与 build。最小修法：T-22 完成标准加一句「镜像含 tests/、acceptance/、pytest.ini」，或 T-24 启动测试容器时 `-v <隔离目录>/catalog:/app`。不增加业务代码。
2. `tasks.md` T-22 / T-24 — `docker-compose -p dh-catalog-test config -q` 在隔离快照里会因 `catalog-api` 的 `env_file: ./.env` 不存在（`.env` 不入库）而报错。最小修法：该步前 `cp .env.example .env`，或删去这个可选步骤。
3. `plan.md` §8 M5 — 仍写「importer.py（…报告与基线对照）」，与 §4.1 第 8 步、T-19、T-23「基线对照只由 compare.py 读报告完成」不一致。删去「与基线对照」即可。
4. `tasks.md` T-26 —「cache 只核对访问记录」：plan 只在测试中记录打开路径（`test_v0_cache_access`），正式导入不产出访问记录，T-26 届时无物可核。二选一：T-26 改为「cache 部分以 docker inspect 的只读挂载与 T-24 的 test_v0_cache_access 为证」；或 derivation.py 的统一打开函数把实际打开的路径写进导入报告（约 5 行），更贴近 spec Q-019「以访问记录证明」。
5. D-018「影响」要求 Handoff 时在 architecture.md 补入目标架构，tasks 执行约定与 T-25 / T-26 都未提及；建议在 Handoff 清单中与 review.md 并列写明，纯文档，不影响实施。

</details>

## Gate 1 与建议处理（2026-10-28）

用户回复「批准，继续」，确认 spec 第 7 版、Q-009 撞号不自动合并及按建议继续：合入第 9 轮非阻断建议 1～3、5，不为其余情形增加规则。规格现已冻结。

第 10 轮两处阻断均已修复：T-24 使用一次性隔离测试容器，不碰正式数据库或原始材料；T-25 只读冒烟，不提前触发全量导入。基线比较只保留 compare.py，验证不做模糊 -k 筛选，部署后代码修复须重新过 Review / Gate 2。第 11 轮已核实这些修订。

NAS 测试与部署仍需单独许可；实现期间不改本清单，Review 阶段另评实际代码。

## 历史

第12轮为plan9的Plan/Checklist核对，10通过、2因新Tasks未拆不评；原文单独按哈希归档（见上），不重放1～11轮。随后第13轮已补评全12项通过、进入仅T31/T32的Implement；原文见上，不代实际代码Review。

| 轮次 | 审阅提交 | 审核员与通道 | 结果（通过 / 未通过） | 去向 |
|---|---|---|---|---|
| 1 | `private-candidate-008`：spec 第 1 版 + Clarify 第二轮，plan 第 1 版 | A via claude-bridge，B via openai | 共识 8 / 13 | spec、plan 第 2 版 |
| 2 | `private-candidate-009`：第 2 版 | 同上 | 共识 13 / 9 | 第 3 版 |
| 3 | `private-candidate-010`：第 3 版 | 同上 | 共识 15 / 7 | 第 4 版 |
| 4 | `private-candidate-011`：第 4 版 | 同上 | 共识 14 / 8 | 第 5 版 |
| 5 | `private-candidate-012`：第 5 版 | A 未运行（claude-bridge 接入不可用），B via openai | 未形成共识（B 15 / 7） | 第 6 版 |
| 6 | `private-candidate-014`：spec 第 6 版、plan 第 6 版 | A via anthropic（claude-bridge 接入不可用），B via openai | 共识 21 / 1 | plan 第 7 版 |
| 7 | `private-candidate-015`：spec 第 6 版、plan 第 7 版 | 同上 | A 21 / 1，B 19 / 3（整件缺失的编号被清空；v0 链接限制与 spec 不符） | 两处新增随第 8 版精简删去；第 8 轮起取消 B |
| 8 | `private-candidate-016`：spec 第 7 版、plan 第 8 版 | A via anthropic（claude-bridge 接入不可用） | 10 / 0，无阻断，2 不评 | 采纳建议 1～6、8、10 |
| 9 | `private-candidate-019`：spec 第 7 版、plan 第 8 版 | A via anthropic（claude-bridge 接入不可用） | 10 / 0，无阻断，2 不评 | Gate 1 批准，采纳四项文字澄清 |
| 10 | `private-candidate-021`：新增 26 项 tasks | A via anthropic（claude-bridge 接入不可用） | 10 / 2（CHK-04、07） | `private-candidate-022` 修复测试隔离与正式部署冒烟步骤，第 11 轮复核 |

完整原文见本文件 git 历史：第 1～7 轮截至 `private-candidate-015`，第 8 轮 `private-candidate-018`，第 9 轮 `private-candidate-020`，第 10 轮 `private-candidate-022`。第 8 轮起取消重复的 CHK-R001～R013；最终需求结论只保留于 spec §5。
