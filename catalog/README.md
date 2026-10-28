# 目录服务（catalog-foundation）

当前是开发中的独立后端，**尚未部署；目录 API、导入与历史代码已写成，真实数据库 / HTTP 集成尚未验证，不能作为生产可用证据**。需求与任务以 `../specs/catalog-foundation/` 为准；不改 v0。

已实现配置、只读清单与影像事实、编号解析、单元 / 备份映射、影像与写卷身份计算、谱系 / 许可 / 出处规则、共用会话认证、v0 快照 / 采样 / 链接。API 工厂已包含登录墙、受保护的文档 / OpenAPI、只读目录查询与管理员导入触发路由。国图清单 / 画布、派生白名单及导入计算阶段已完成本机测试；导入持久化、历史、报告代码以及数据库初始迁移、连接池和咨询锁均已写成，但尚未经过真实 PostgreSQL 验证。查询 / 触发 API 及 health 代码已写成，运行文件及正式验收入口仍待实现；SQL、后台线程和资源生命周期的真实集成留 T-24。阶段证据见 tasks.md，不以单元测试代替端到端验收。

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
| DH_CODE_VERSION | 导入记录中的运行代码版本；本机缺省 development，生产镜像须注入实际提交版本 |
| DH_TEST_DATABASE_URL | 仅测试用的一次性 PostgreSQL 库，库名须以 dh_catalog_test_ 开头，绝不能指向正式库 |

配置在启动入口读取，导入模块不加载运行配置或原始材料、不连接网络或数据库。API 工厂是 `dh_catalog.api:create_app`（uvicorn `--factory`）；缺少 v0 AUTH_SECRET 时，登录墙对所有请求返回 503，不退回环境中另一份 secret；每个通过的请求只验证一次 cookie、只读一次用户记录，后续路由消费 Principal。

运维 CLI 已实现 `migrate`、只读 `report [--run ID]` 与 `health`，不提供 CLI 导入。设置专用数据库连接后，在仓库根使用 `PYTHONPATH=catalog/src python -m dh_catalog <命令>`。report 在数据库只读事务中取已保存批次，不加载认证文件或调用 v0；health 校验 secret 与数据库 / 迁移可用性，不走 HTTP、不读用户表或原图、不加载扫描 / 导入器。这些命令的数据库路径尚未实测，不能作为已部署或迁移成功的证据。

## 导入器集成接口（代码已写，数据库待验）

- `prepare_import(pool, triggered_by=..., code_version=..., session_cookie=..., v0_url=...)` 同步持连接与咨询锁并创建批次，返回含 run_id 的 PreparedImport；已在跑则抛 ImportBusy。管理员 API 先完成这一段再返回 202，ImportBusy 同步转 409。
- 后台调用 `PreparedImport.execute(roots, cache_dir)`；派发失败则 `cancel()` 清理。内部复用真实 scan / nlc / derivation / identity / rules，附件读取即消费，不在内存保留全量原文。
- `compute_import(...)` 是可本机验证的真实计算阶段；持久化、唯一约束互换、失败回滚与历史读取都仍需 T-24 的真实 PostgreSQL 验证，不能用本机 DTO 状态测试代替。
- `read_report()` 读取已有批次。当前 `import_run.counts` 保存完整报告对象，其中的 `counts` 子键才是统计计数；API 将完整对象明确返回为 `report`，统计位于 `report.counts`；未来 compare 只消费这些计数，不再扫描原始材料重算业务判断。

只读 API 路径与查询参数见受保护的 `/api/v1/docs`（接口清单的设计权威在 feature plan §2.1）。编号查询只命中 current，历史 / pending 在详情展示；批次历史使用 `?run=`。GET 使用只读事务；附件返回保存的原字节。唯一写方法是管理员 `POST /api/v1/imports`，不提供目录内容修改、取消或回滚 API。

## 测试与部署边界

本机当前只验证不依赖数据库的模块。默认 pytest 会把缺少测试连接的 db 项明确列为跳过，不能宣称全部数据库测试通过。数据库测试会清空指定临时库的业务表，只接受 `dh_catalog_test_*` 库名，不读取 DH_DATABASE_URL 作为后备。

真实 PostgreSQL 与 Python 3.12 镜像测试必须另获用户许可，使用候选快照和一次性容器，不启动正式 compose、不挂正式 pgdata、真实材料或 v0 文件；流程见任务 T-24。v0 HTTP 的测试只用边界替身，没有实际连接 NAS。

当前 Starlette 的 TestClient 会对已固定版本的 httpx 发出一条弃用警告；测试仍可运行，未静默屏蔽警告或为消除警告升级依赖。

正式部署须独立 Review → Gate 2 → merge 后另获许可，不得从功能分支推送 NAS。部署只读冒烟不触发导入；正式全量导入由用户在接口文档页触发（T-26）。NAS 内存 / 耗时 / P95 与原材料只读验收尚未执行，不能以本机单元测试代替。
