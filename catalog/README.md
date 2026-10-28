# 目录服务（catalog-foundation）

当前是开发中的独立后端，**尚未部署，也尚无可运行 API**。需求与任务以 `../specs/catalog-foundation/` 为准；不改 v0。

已实现配置、只读清单、影像文件头事实、编号解析、写卷单元与备份映射、影像稳定身份计算。尚未实现写卷归并、持久化、认证与 API；不能运行真实导入。阶段证据与未完成项见 tasks.md，不以单元测试代替端到端验收。

## 本机开发

在仓库根目录，用现有 Python / pip / pytest：

```bash
python -m venv catalog/.venv
source catalog/.venv/Scripts/activate  # Windows Git Bash
python -m pip install -r catalog/requirements.txt
python -I -X utf8 -m pytest -c catalog/pytest.ini
```

依赖声明固定版本；与 v0 共有的库取 `docs/plan.md` RK-05 的运行基线。测试材料全部在临时目录生成，不含真实原图、下载清单、用户表或日志。pytest.ini 只配置源码路径、测试目录和 db 标记，不引入其他测试工具。

## 配置

| 环境变量 | 含义 |
|---|---|
| DH_DATA_DIR / DH_BACKUP_DIR | 只读原图 / 分片根，容器默认 /data、/backup |
| DH_V0_CACHE_DIR | 只读 v0 cache 根，默认 /v0cache；不能扫描此目录 |
| DH_V0_ENV_FILE | 只读 v0 .env 路径，默认 /run/v0.env；只使用 AUTH_SECRET |
| DH_V0_URL / DH_V0_PUBLIC_URL | v0 请求地址 / 查看器链接地址，后者默认同前者 |
| DH_DATABASE_URL | 目录数据库连接；没有凭证默认值 |
| DH_TEST_DATABASE_URL | 仅测试用的一次性 PostgreSQL 库，绝不能指向正式库 |

配置在启动入口读取，导入包不访问文件、网络或数据库。缺少 v0 AUTH_SECRET 保持不可服务状态，HTTP 拒绝行为由后续 API 任务实现，不退回环境中另一份 secret。

## 测试与部署边界

本机当前只验证不依赖数据库的模块。真实 PostgreSQL 与 Python 3.12 镜像测试必须另获用户许可，使用候选快照和一次性容器，不启动正式 compose、不挂正式 pgdata、真实材料或 v0 文件；流程见任务 T-24。

正式部署须独立 Review → Gate 2 → merge 后另获许可，不得从功能分支推送 NAS。部署只读冒烟不触发导入；正式全量导入由用户在接口文档页触发（T-26）。NAS 内存 / 耗时 / P95 与原材料只读验收尚未执行，不能以本机单元测试代替。
