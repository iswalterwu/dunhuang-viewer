# 会话交接 — catalog-foundation / 公开发布隐私修订

> 公开隐私修订，原件非公开保全，不是逐字原文。本文是交接导航与证据边界摘要；原提示词、命令、日志、JSON、清单和候选映射为非公开档案，不能把公开摘要称为原始报告。

## 当前本机安全点

**交付完成**：PR #1 已由本机匿名/UTC正常no-ff合并，并普通fast-forward推main；GitHub确认MERGED，合并后新取两分支全历史/独立语境零未处置。合并时本机main与origin一致，功能分支保留、不删除；隐私feature完成，目录软件已合并；T-25/T-26 及 F-1 修复复验（T-40/T-41）均已获准执行，见下。

**正式部署（T-25，2026-10-30T20:25Z～20:34Z）**：经用户批准，部署远端以单 ref 精确租约替换为获准 main，v0 的 `.env` 与开机钩子宿主配置已迁移，守护循环已按新钩子重启；v0 未重建、未重启。目录服务两容器健康，限额、只读挂载、端口绑定（局域网 + 用户态 Tailscale 所用回环）与正式依赖清单核验通过，匿名访问三路均得 401；登录态冒烟由用户完成并经访问日志核对（读 200、普通账号导入 403、管理员读 200，无导入被受理），T-25 完成。**T-26 已执行**：全量 771 秒、重跑 412 秒（零变化）、原图零变化、P95 与 20 链接达标；画布对应 84.5%，发现 F-1（`report.json` 的 `pages` 结构未支持）须另立修复任务后重导复验，重跑 API 内存峰值 95.2% 列为风险。详见[catalog任务T-25/T-26](specs/catalog-foundation/tasks.md)。

**F-1 修复与复验（T-40/T-41，2026-10-31）**：`report.json` 的 `pages` 结构支持经独立 Analyze19、CodeReview-F1 与用户 Gate2 后由 PR #2 合并（`db64233f4b91`）。合并后隔离目标测试 498 通过/0 跳过；部署远端普通快进，只重建 `catalog-api`，复核通过，v0 未动；用户触发批次 3 重导，427 秒成功，原图零变化。A4 由 84.5% 升至 99.68%，剩余 70 个整卷拼长图列为异常，其余结论不回退，F-1 关闭；API 内存峰值 94.0% 仍列风险。详见[catalog任务T-40/T-41](specs/catalog-foundation/tasks.md)。

**命名变体（T-42/T-43）**：用户澄清 `2019年新增1` 中 3 个 `native (1).tif`（括号前一个空格、无软件标签）视同 BnF 命名。T-42 只改 `NATIVE_TIFF` 正则并补测试，规则版本按用户确认不提升；独立 Analyze20 与 CodeReview-N2 通过，用户 Gate2 后由 PR #3 合并（`a5b1a21d15c8`）。T-43 经用户批准执行：合并后隔离目标测试 503 通过/0 跳过；部署远端普通快进、只重建 `catalog-api`；批次 4 重导 529 秒成功，原图零变化；3 张影像改判 BnF 原图、2 件写卷展示策略随之放宽，没有其他对象变化，「谱系未判定」归零，其余结论不回退。详见[catalog任务T-42/T-43](specs/catalog-foundation/tasks.md)。

**合并后隔离目标回归（T-39）**：经用户另行批准，以main `646a29ee64ba` 快照在隔离目录受限构建并用一次性PG运行完整目标测试：**483 passed/0 failed/0 skipped/1原有警告，84.45秒**，61个db项（含新增4项）全部实际执行通过。首批因操作就绪探针过早而在pytest前停止并清理；两批临时资源均已清理，v0未变。详见[catalog任务T-39](specs/catalog-foundation/tasks.md)。

初期PRIV-01～04集成记录：完整 **489 passed/61 skipped/1原有警告，550项，42.67秒**；61=58缺DB+3仅Linux，不算通过。配置/旧记录前缀/中性标签与主机模板/脚本、公开文档/归档和发布工具均有局部证明。初始集成树112文件的index+worktree检查224文本实例0命中，新增状态文件须重新复扫；旧Git历史尚未据此自动清理。

A1/A2原阻断保留，P21已补私有规则及根Dockerfile两注释，公开业务/工具不改。**R5复审通过，R4历史隐私P1-1关闭，无P0/P1/P2；用户已确认隐私Gate2并要求继续，三项非阻断及未验已接受。** 实际A3涵71提交/477输出blob/690文本，5644路径/mode、92历史Python/6Shell与全部消息/匿名身份/UTC等机械验证通过；独立全类别语境548记录零未处置，R5独立复现并人工通读529保留行/171中性化文本。最新交接本机489通过/61跳过/1警告，48.99秒（此前A3为43.08秒）；61不算通过。3项非阻断历史编辑/推断边界及4新增DB未验、镜像未重建已在Gate2明示；其中4新增DB随后已由T-39补验，v0根镜像仍未重建。审后仅补治理记录的A4最终72提交/483blob/699文本及独立555记录复扫全过；不将R5范围偷扩。所有新提交/merge显式TZ=UTC。现阶段详见[隐私收敛](specs/public-release-privacy/converge.md)与[发布评审](specs/public-release-privacy/review.md)。origin两分支已按原精确租约一次原子受保护更新，新取远端完整复扫/核OID通过，本机两分支CAS迁移完成且工作树相同；旧私有引用/reflog仅保全并禁止回传。交接/PR #1/合并已完成，未操作部署、数据库、真实材料；新目标PG已由T-39隔离补验，真实资源性能未验，旧446/36k不冒充新实测。

## 获准边界（不自动更新任务状态）

- 用户已批准 catalog 原软件 Gate 2，接受 R3 软件通过、N1 关闭、现行编号记录历史边界及既有待验风险。**不包含正式部署或真实材料导入许可。**
- 随后用户选择仓库保持 Public，D-019 取代 D-009 的私有可见性要求；代码权威、部署通道、许可与安全红线不变。
- `public-release-privacy` 的 7R/25AC 已获 Gate 1 批准；独立 Analyze 第2轮 **12项全通过、无阻断、B-1设计层关闭**（Anthropic / claude-fable-5-1，09:04:56Z～09:13:40Z，exit0），只允许 PRIV-01～07 按依赖实施。新差异仍须独立 Review 及必要 Gate 2。
- 用户授权清理公开历史与提交者信息、受保护更新 origin 的 main / 功能分支，不等于已执行；历史演练、租约、原子两分支更新及本机切换由主会话按冻结规格处理。其他远端、部署和新的私人主机数据库验证不在授权内。
- 本轮仅对实际验证的当前树及origin两分支可达历史报告清理结果；平台旧对象/缓存、分叉、第三方副本与固有发布者身份不能保证撤回，未知秘密格式不作绝对保证。部署远端及私有恢复引用保留旧历史，不得回传origin；未连接私人服务。

## 阅读顺序

1. [AGENTS.md](AGENTS.md)：七项工程约束、模型分工、人工闸门与部署许可。
2. [总方案](docs/plan.md)、[架构](docs/architecture.md)、[D-019](docs/decisions/20261030-public-code-and-privacy.md)。
3. [公开发布规格](specs/public-release-privacy/spec.md)及同目录 plan / checklist / tasks：本轮实施权威，冻结文件由主会话维护。
4. [公开验证摘要](docs/verification.md)：分阶段模型、候选别名、真实结果、失败与未验边界。
5. catalog 的 [spec](specs/catalog-foundation/spec.md)、[plan](specs/catalog-foundation/plan.md)、[tasks](specs/catalog-foundation/tasks.md)、[converge](specs/catalog-foundation/converge.md)、[review](specs/catalog-foundation/review.md)与[内存诊断](specs/catalog-foundation/memory-diagnosis.md)：保留需求、数字、历史审核结论和停止记录的公开隐私修订。
6. [catalog运行说明](catalog/README.md)、[v0部署说明](README-部署.md)：配置角色与未来获准操作，不代表真实部署已验。

## 不可混淆的证据

- T24 首轮 **400 passed / 2 failed / 0 skipped（47.10秒）**，修夹具后 **402 / 0 / 0（47.62秒）**；C1修复后 **404 / 0 / 0（48.27秒）**。
- R1 独立结论为 **需修复后重审**。P8/P9后目标 **412 / 0 / 0（46.08秒）**，但36k内存趋势不足，按约定停止；P10后 **423 / 0 / 0（59.66秒）**，仍未过放大条件，停止后先做T33诊断，不把估算当OOM实测。
- Plan10 A+C / T36目标 **442 / 0 / 0（64.37秒，55db实际）**；原512m硬限内36k差异化首轮 / 真PG重导实际成功，RSS **341.98 / 435.05MiB**、**343.115 / 307.414秒**，cgroup含页缓存达到512MiB、exit0、无OOM。不能据RSS差称有77MiB总余量。独立R2软件通过，CR1-01代码级/02/05关闭；N1当时另列P3待用户决定。
- N1修复经Analyze16与P14/P15 Astra实施：T38-A1 **445 / 1 / 0（72.66秒，exit1）**；新增HTTP断言遗漏请求元数据变化，P15仅修一行期望。A2 **446 / 0 / 0（73.22秒，57db实际，exit0）**。原失败和清理初检失败没有被覆盖。
- R3（Anthropic / claude-fable-5-1）软件通过、N1关闭；亲跑本机 **389 passed / 57 skipped / 1警告（10.14秒）**，只核对目标原件、未亲跑目标PG。本机57跳过为54缺DB+3仅Linux，不算通过。
- **旧446与旧36k不是隐私修订后代码的新实测。** R3只据当时两函数差异认可旧T36支持当时新候选首轮 / 同版本无变化重导；规则升级足规模、真实材料/并发/v0连续健康/耗时/P95/正式挂载仍未验。不能自动把此支持边界扩到后续配置或标签改动。

## 后续集成与待验

PRIV-01～04 文件边界并行后由主会话复核、复跑与记录，不以子agent自报代独立Claude审核。共享变量须全名一致：`DH_HOST_DATA_DIR`、`DH_HOST_BACKUP_DIR`、`DH_HOST_CACHE_DIR`、`DH_HOST_V0_ENV_FILE`、`DH_HOST_PGDATA_DIR`、`DH_HOST_STATIC_DIR`、`DH_DEPLOY_DIR`、`DH_RECORD_DATA_ROOT`、`DH_RECORD_BACKUP_ROOT`；HOST、容器路径与旧记录字符串前缀不是同一概念。

T25正式只读挂载、外部PG、绑定、默认启动与认证，T26真实A1～A7仍须单独许可。编号 historical 表示完整编号记录历史，不保证编号值曾改变；同号但来源/路径/主号来源变化的原行为保留，改语义须先Clarify。

## 本机检查入口

在本机仓库根目录执行；不使用私人调度脚本作为公开入口：

```bash
git status --short
python -I -X utf8 tools/check_docs.py .
git diff --check
# 完整软件回归由主会话在并行任务集成后执行，并如实记录DB/Linux跳过
catalog/.venv/Scripts/python.exe -B -I -X utf8 -m pytest -p no:cacheprovider -c catalog/pytest.ini catalog/tests catalog/acceptance
```
