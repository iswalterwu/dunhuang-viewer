# 会话交接 — catalog-foundation / 公开发布隐私修订

> 公开隐私修订，原件非公开保全，不是逐字原文。本文是交接导航与证据边界摘要；原提示词、命令、日志、JSON、清单和候选映射为非公开档案，不能把公开摘要称为原始报告。

## 当前本机安全点

PRIV-01～04已实施并由主会话串行集成：完整 **489 passed/61 skipped/1原有警告，550项，42.67秒**；61=58缺DB+3仅Linux，不算通过。配置/旧记录前缀/中性标签与主机模板/脚本、公开文档/归档和发布工具均有局部证明。初始集成树112文件的index+worktree检查224文本实例0命中，新增状态文件须重新复扫；旧Git历史尚未据此自动清理。

现阶段详见[隐私收敛](specs/public-release-privacy/converge.md)与[发布评审](specs/public-release-privacy/review.md)。下一步固定干净候选，在仓库外演练实际历史并完整复扫，再独立Review/必要Gate2。未更新远端/创建PR/合并或操作部署、数据库、真实材料；新目标PG与真实资源性能未验，旧446/36k不冒充新实测。

## 获准边界（不自动更新任务状态）

- 用户已批准 catalog 原软件 Gate 2，接受 R3 软件通过、N1 关闭、现行编号记录历史边界及既有待验风险。**不包含正式部署或真实材料导入许可。**
- 随后用户选择仓库保持 Public，D-019 取代 D-009 的私有可见性要求；代码权威、部署通道、许可与安全红线不变。
- `public-release-privacy` 的 7R/25AC 已获 Gate 1 批准；独立 Analyze 第2轮 **12项全通过、无阻断、B-1设计层关闭**（Anthropic / claude-fable-5-1，09:04:56Z～09:13:40Z，exit0），只允许 PRIV-01～07 按依赖实施。新差异仍须独立 Review 及必要 Gate 2。
- 用户授权清理公开历史与提交者信息、受保护更新 origin 的 main / 功能分支，不等于已执行；历史演练、租约、原子两分支更新及本机切换由主会话按冻结规格处理。其他远端、部署和新的私人主机数据库验证不在授权内。
- 本文不宣布隐私清理完成、全树无残留、历史已重写或最终审核已通过；本次文档编辑没有提交、推送或连接私人服务。

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
