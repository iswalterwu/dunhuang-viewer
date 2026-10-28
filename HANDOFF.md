# 会话交接 — catalog-foundation

> **状态：独立 CodeReview-R1 已返回「需修复后重审」；CR1-01/P1 为正常全量规模内存风险，另有CR1-02/05两项P3缺口。Converge重新打开，T-28～T-30最小修复方向待用户确认，尚未启动P8。**
> 更新：2026-10-29。尚未过Gate2、未merge main、未正式部署/全量导入；404全绿仅是已有合成验证，不代表全量512MiB已达标。

## 1. 恢复入口与当前安全点

- 唯一本机仓库：**`/srv/example/project`**；分支 `feat/catalog-foundation`，upstream `origin/feat/catalog-foundation`。2026-10-28迁移自C盘，原目录已在6,049文件SHA-256一致、新环境验证后移除；本机依赖保留，激活/17个入口已重新生成。
- 当前已审HEAD：**`private-candidate-039`**；最新实际NAS全套通过候选：**`private-candidate-038`**。两者的生产源码/测试/迁移/运行配置相同，其间仅状态/证据文档变化。
- 本轮其后的评审归档/计划/状态提交仍未改生产代码，实际最新HEAD用 `git log -1 --oneline` / `git rev-parse HEAD` 查看，不写未知的自引用SHA。
- 用户已批准普通GitHub功能分支持续同步，不重复询问push；GitHub：`origin 的 feat/catalog-foundation 分支（项目角色描述，非网址）`。没有merge、NAS git push、PR合并或部署。main/origin-main记录仍为private-candidate-023，最终以git分支/远端核对为准。

## 2. 工作流与不可混淆的结论

- spec第7版已过Gate1并冻结（13 R / 58 AC / 25决策），feature plan第8版；设计Analyze第11轮审核员A的12项通过，**不是实际实现Review结论**。不重复Gate1、不改冻结spec/plan/checklist。
- T-01～T-24对应实现/合成自动化证据已具备；Converge发现JPEG头安全异常C1/T-27，经P7最小修复并在A3真库通过。C1已关闭，不重修或关闭Pillow保护。
- 主会话的58条AC矩阵在 `specs/catalog-foundation/converge.md`，包括7处计划测试名与实际综合测试别名。软件收敛初步结论已被R1新发现重新打开；**当前不能提交Gate2通过或宣称全量收敛**。
- 有效独立评审、主会话复核、风险和后续建议在 **`specs/catalog-foundation/review.md`**；T-28～T-30已登记在tasks.md，尚未实施。T-25正式部署与T-26真实材料/性能验收未开始、未获许可。

## 3. 独立 Review-R1（已结束，不是超时或失联）

审阅HEAD全程冻结为private-candidate-039，审阅前后git工作区干净；主会话未在审核期间改代码或启动NAS资源。

| 尝试 | 实际模型/通道 | 实际起止（2026-10-29，原始时刻；时区非公开） | 结果 |
|---|---|---|---|
| 首选 | claude-bridge/claude-fable-5-1 | 00:23:13～00:35:20 | exit=1，接入不可用，stdout为空，没有审核结论 |
| 回退 | anthropic/claude-fable-5-1 | 00:37:10～01:17:20 | exit=0，正常返回完整报告，结论「需修复后重审」 |

两通道同一Claude审核模型，只换接入路径；未以Astra自测或主会话代审。桥的错误原文含接入不可用原因（账户细节非公开），原文归档；下轮按实际可用性核对/记录，若仍处于已证实的接入不可用状态可引用该不可用证据走Anthropic，不伪称桥完成审核。

审核员读全部生产模块/迁移/运行配置、关键测试全文、v0协议及实际diff；部分其余测试只看清单/部分断言。实际本机回归为362 passed /42 db skipped /1原有警告，另做24种头格式探针、单元/编号和内存规模探针。**审核员未亲跑NAS/DB，只核对A3归档**，详细局限保留在原文。

所有派发的P1～P7及两次Review进程均已结束，当前没有本会话遗留后台agent；P8/后续修复未启动。不要因等待较久把正常exit0误写成超时，也不要把首选接入失败误作审核不通过的代码结论。

## 4. 发现、复核及建议方向（下一步需拍板）

### CR1-01 / P1：正常目标规模内存

importer的每字段basis/author/at对象反复新建，重导入还同时持有S0和本批结果。审核员测量约23KiB/影像首轮保留、30KiB/影像重导峰值。

主会话在相同已审源码上独立复核：每写卷6个仅26字节PSB头（无像素），真实compute_import/build_report，丢掉旧Inventory/Units容器后再用真实结果DTO重导，不模拟SQL、不连接数据库/网络。Windows/Python3.14.2两个独立进程：

| 影像/写卷 | 基线工作集 | 首轮峰值 | 重导峰值 |
|---|---|---|---|
| 2000 / 334 | 56.38MiB | 101.28MiB | 114.86MiB |
| 6000 / 1000 | 56.43MiB | 191.29MiB | 232.25MiB |

增量线性一致；约36k影像线性估算含基线为 **865.5MiB / 1111.4MiB**，高于512MiB。**这是具体高概率的正常规模风险，但不是NAS全量实测或已发生OOM**；真实DB反序列化S0的峰值尚未在该探针测量，不能用共享DTO替代真库验证。

建议先在现有内存计算设计内做只读依据/规则作者/批次时间对象复用，预计50～120行实现及相应回归，1～2小时（估计，不含模型/构建等待），方向待用户确认：

- 必须有缓存容量/生命周期边界，版本/批次/时间/来源完整，不能跨批次污染，不能共享后就地修改；需要覆盖DB加载后的重复basis，不只优化首轮新建。
- 持久化JSON、历史/作者/置信度/原文、身份/归并、事务/锁语义完全保持；不丢字段、不抽样材料、不把计算移出受限容器。
- 不放宽API512m、DB384m或增加swap。先复测相同两点，再在目标Python3.12/临时PG/硬限额中验证合理规模和行为等价；不以小样本外推冒充全量达标。
- 若最小共享仍不足，**停止并先讨论/更新plan**；不偷偷流式重构/缩列丢历史，不自行放宽D-005/D-018。也不为OOM增加Q-025删去的恢复/中止机制。

### CR1-02 / P3：撤销候选误入历史

源码确有 `_persist_identifiers` 将所有未保留旧行（含pending）改historical，导致未持有过的候选号显示为曾用号；resolve仍只current，不受影响。T-29拟保持current/historical/pending既有设计，可移除撤销pending的当前表行，但必须用过去批次history快照保存原候选值/来源/时间，真库验证当前详情和过去批次皆正确。**不直接照抄原文建议新增withdrawn状态**；如需新状态先讨论设计。

### CR1-05 / P3：冲突说明缺参与ID

算法/回退结果正确，但说明只有编号与「其他写卷」，不满足plan注明同号写卷。T-30拟仅在现有说明中补参与ID/稳定顺序，不加新状态/表/API字段，不改归并。T-28/T-29共享importer必须串行；T-30独立文件可按需由Astra并行。

CR1-03（裸号紧邻扩展名，未证实）和CR1-04（备份散放，低概率）**当前不改代码/规则**；按工程约束留T-26实际核查，必要时先澄清/登记，不擅自改变冻结spec。

当前主会话建议 **先按最小方案修复并Review-R2，不直接风险接受后全量导入**。尚未取得此优化方向确认，也没有新生产代码改动；「继续」此次是推进Converge/Review，不是Gate2、合并或部署批准。

## 5. 真实测试证据与NAS清理

用户此前明确批准T-24隔离快照/受限构建/一次性PG/API与清理，仅合成材料/认证，无真实材料/v0/正式pgdata挂载、无宿主端口、无正式Compose。共同NAS环境Docker24.0.2、Compose v2.20.1-6047-g6817716、Python3.12.15、PG17.4。

| 轮次 | 候选 | 完整结果 | 说明 |
|---|---|---|---|
| A1 | private-candidate-034 | 400 passed /2 failed /0 skipped /1 warning，47.10秒 | 两处CLI测试用connection.info.dsn丢失口令，P6只修四行夹具/传值 |
| A2 | private-candidate-035 | 402 passed /0 skipped /1 warning，47.62秒 | P6后全通过 |
| A3 | private-candidate-038 | **404 passed /0 skipped /1 warning，48.27秒** | P7/C1两回归及全部42个db项通过；不覆盖36k规模内存 |
| 本机P7后 | 与A3相同源码 | 362 passed /42 db skipped /1 warning | 3.14.2，无本机DB，skip不算通过 |

A3快照SHA-256 `f30ca2c849ef9f359f3664c3023c9177a6933b7d081eb61746d3e42f8413ae30`，镜像ID `sha256:0b898cad5b78312eb48a8572238933d8d081e28e98326b716ea86bf379030b98`（已删除）。构建512m=memswap，实际探针验证；API512m/DB384m各自memswap相等，A3运行再次读cgroup memory=memsw=536870912，die exitCode=0/无OOM，合成.env的Compose config -q通过。不是正式挂载/默认启动证明。

三轮库（显式DROP）、API/DB/诊断容器、三匿名PG卷、三网络、四测试/探针镜像标签、三隔离目录、临时.env与远端raw均已清理；没有需重启命令，未global prune，基础镜像保留。v0 ID `cb29d6cf59e9694ce1a35ecdb2f52a8f25a3164d8fcc46e037d93a295e254ac2`、启动 `2026-10-24T23:21:23.021250776Z`、restarts=0/running=true未变；这不代替真实全量期间连续健康采样。

## 6. 证据位置、调度与恢复

- 有效独立原文/两通道meta/status/接入错误（账户细节非公开）/空输出/提示词/主会话内存探针源码与JSONL：**CodeReview-R1（非公开历史记录）**。显示文本自动转LF/去行尾空白，manifest含源/归档哈希；外部原文件保留，未改结论/严重性/数值。
- 原审阅输出在 `/srv/example/private-audit/review/code-review-R1-{bridge,anthropic}.*`，主会话探针在 `/srv/example/private-audit/converge/CR1-memory-*`。桥无输出，Anthropic原文约18KB。
- 原T24-A1/A2/A3、P1～P7、迁移及C1证据仍在 历史归档（非公开历史记录），不改旧通过数；不提交快照tar、私有raw、真实.env/users.json或认证配置。早先NAS原始抽查材料未入库。
- 实施仍用 `/srv/example/private-audit/implement/run_task.sh`：cwd D盘、固定openai/gpt-6-astra、独立pi --no-session、2400秒；不可用则请用户决定，不擅自换模型。新任务用新批次/当前HEAD新提示词，不重放历史任务。
- 审核仍为独立Claude A，旧设计r1～r11不重放。R2应核对修复差异/回归/规模证据并参考R1，不把主会话或Astra自测当独立通过；记录实际通道/切换原因。

```bash
cd /srv/example/project
git status --short
git log --oneline -8
git branch -vv
catalog/.venv/Scripts/python.exe -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests catalog/acceptance/test_compare.py
# 历史命令（非公开历史记录，不可执行）：python -I -X utf8 private-audit-record .
git diff --check
```

## 7. 后续闸门

先请用户确认T-28～T-30最小修复方向；若同意，由Astra实现、主会话复核/新候选受限复验，再独立Review-R2。**当前Gate2未批准，不合并/部署**。T-25/T-26仍要单独许可，真实全量导入由用户在受保护OpenAPI触发，不代签会话；原材料/基线/对象关系、正式ro挂载/端口/pgdata、v0连续健康、全量资源/耗时/P95/20链接均未验。related-project仓库/模板未动，仍需单独确认。
