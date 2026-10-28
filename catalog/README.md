# 目录服务（catalog-foundation）

当前是开发中的独立后端，**尚未部署；目录 API、导入与历史代码已写成，真实数据库 / HTTP 集成尚未验证，不能作为生产可用证据**。需求与任务以 `../specs/catalog-foundation/` 为准；不改 v0。

已实现配置、只读清单与影像事实、编号解析、单元 / 备份映射、影像与写卷身份计算、谱系 / 许可 / 出处规则、共用会话认证、v0 快照 / 采样 / 链接。API 工厂已包含登录墙、受保护的文档 / OpenAPI、只读目录查询与管理员导入触发路由。国图清单 / 画布、派生白名单及导入计算阶段已完成本机测试；导入持久化、历史、报告代码以及数据库初始迁移、连接池和咨询锁均已写成，但尚未经过真实 PostgreSQL 验证。查询 / 触发 API 及 health 代码已写成；T-22 的 Dockerfile、独立 Compose、配置示例与构建排除规则现已编制，仅做本机静态契约检查，尚未校验 Compose 语法或构建镜像。正式验收入口留 T-23；SQL、后台线程和资源生命周期的真实集成留 T-24。阶段证据见 tasks.md，不以单元测试代替端到端验收。

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

## 运行文件（T-22，仅源码与静态检查）

- 构建上下文必须是 `catalog/`，不是仓库根。镜像只安装本目录固定依赖，pip 源与 v0 相同；无 apt、libvips 或图块管线。`src/` 放在 `/app/src`，迁移在 `/app/migrations`，与 `db.MIGRATIONS` 对齐。
- 同一镜像包含真实 `tests/`、`pytest.ini`、`acceptance/`，以及静态测试读取的运行配置源文件。**T-23 尚未提供 acceptance 基线 / compare 文件，目前直接构建会在 COPY acceptance 处失败；必须先完成 T-23，再做 T-24。** 不用空目录或假成功绕过这一前置。
- 启动先执行 migrate，成功后才 exec uvicorn 工厂；健康检查调用 `python -m dh_catalog health`，不签 cookie、不走 HTTP。`DH_CODE_VERSION` 同时作为构建参数与运行环境传入，不在镜像里执行 git。
- `docker-compose.yml` 只有 `catalog-db` / `catalog-api`；每次操作都指定 `-p dunhuang-catalog`。内存硬限额及 memswap、PostgreSQL 参数、外部 pgdata 和四项只读挂载以此文件为准。API 按计划以 root 读取 root:600 用户表，不增加宿主可写挂载。
- API 仅绑定 NAS 的 LAN / Tailscale 显式地址；数据库没有宿主端口。配置变量不得改为 `0.0.0.0`、`::` 或其他公网 / 通配地址。不添加 nginx / frp 公网入口，不修改真实防火墙；T-25 还须检查实际端口绑定。
- `.env.example` 只有非秘密设置和空占位。获准操作时才在对应 NAS 部署位置准备 `catalog/.env`（权限 600），**先填写新生成的数据库密码和实际提交完整 SHA**。Compose 对两项空值直接报错；不复制 v0 的 `.env`，不把 AUTH_SECRET 填入新配置。认证只读取只读 `/run/v0.env`。
- 当前 Compose 将 POSTGRES_PASSWORD 原样放进数据库 URI，故须使用 URL 安全的随机字符，建议随机十六进制；不要使用含 `@ : / % $ #`、空格等字符的密码，也不要仅把 PostgreSQL 原密码改成百分号编码（两端会不一致）。配置通过环境传值，不 source `.env`、不把密码或其他配置拼进 shell 命令。不要将真实配置 / 展开的连接串打印、提交或放进构建上下文。
- `.dockerignore` 排除凭证、Windows venv、缓存、日志和 Python 产物，保留源码、合成测试与验收文件。`tests/test_runtime.py` 仅保护这些关键文本契约，**不是 YAML / Compose 校验器，也不是构建、Python 3.12 或运行证明**。

## T-24：获准后在 NAS 隔离快照验证（未执行）

本机没有 Docker，不在本机安装或运行 Docker / Compose。以下步骤须 T-23 完成并另获用户测试许可；不推送 nas main、不启动正式 Compose，不访问正式 pgdata、真实材料、真实认证文件。先记录候选完整 SHA、隔离临时目录与资源预算，低峰且 NAS `MemAvailable >= 2GB` 才执行。

1. 从本机用 `git archive <候选完整 SHA> catalog` 导出已记录候选快照，送入获准的 NAS **隔离临时目录**（不是部署 git 工作区）。下文 `SNAPSHOT` 指解包根目录，`CANDIDATE` 指该 SHA。只在隔离位置工作，不能修改快照代码来修测试。
2. 核实目标 Docker 构建后端支持并实际落实内存与 swap 硬限制。以下命令以支持 legacy builder 的环境为前提；若禁用 BuildKit 不可用，或后端忽略 / 不支持资源参数，**停止并报告，请用户决定受限构建方式，不得删参数后无上限重试**。

   ```bash
   DOCKER_BUILDKIT=0 /usr/local/bin/docker build --memory 512m --memory-swap 512m \
     --build-arg DH_CODE_VERSION="$CANDIDATE" -t dh-catalog-test "$SNAPSHOT/catalog"
   ```

3. 正式 Compose 的 `config -q` 留 T-25。若 T-24 额外做语法检查，只能在隔离快照的 `catalog/` 里从 `.env.example` 准备权限 600 的**合成配置**，填临时随机密码与候选 SHA，再执行 `/usr/local/bin/docker-compose -p dunhuang-catalog config -q`；绝不执行 up，也不运行会打印展开凭证的 `config`。这不会证明挂载或端口在运行时成立。
4. 在隔离目录中、构建上下文之外准备权限 600 的 `db-test.env` 与 `api-test.env`，仅使用新生成的 URL 安全临时随机口令：前者设置 `POSTGRES_USER=dh_catalog_test`、`POSTGRES_DB=dh_catalog_test_runtime` 与 `POSTGRES_PASSWORD`；后者设置 `DH_TEST_DATABASE_URL` 指向 `postgresql://dh_catalog_test:<同一临时口令>@dh-catalog-test-db:5432/dh_catalog_test_runtime`，并设置 `DH_CODE_VERSION=<候选 SHA>`。尖括号是说明，不是可用默认值。不要配置正式 DH_DATABASE_URL；真实测试会自行生成合成材料 / 认证文件并清空这个专用测试库。
5. 确认下面的临时名称未被占用（若占用先调查，不删除未知资源），建立一次性网络和 PostgreSQL。不挂任何宿主数据卷，不发布端口；PG 镜像的匿名数据卷随 `--rm` 容器删除。

   ```bash
   /usr/local/bin/docker network create dh-catalog-test
   /usr/local/bin/docker run -d --rm --name dh-catalog-test-db --network dh-catalog-test \
     --memory 384m --memory-swap 384m --env-file "$SNAPSHOT/db-test.env" \
     postgres:17.4-alpine3.21 postgres \
     -c shared_buffers=64MB -c max_connections=20 -c work_mem=4MB
   /usr/local/bin/docker exec dh-catalog-test-db pg_isready -U dh_catalog_test -d dh_catalog_test_runtime
   ```

   必须等 pg_isready 成功再继续；失败时查原因，不能把无连接导致的跳过算通过。在同一候选镜像运行完整真实 pytest（含数据库、HTTP 及 T-23 对照测试），覆盖默认启动命令，不启动正式 API：

   ```bash
   /usr/local/bin/docker run --rm --name dh-catalog-test-api --network dh-catalog-test \
     --memory 512m --memory-swap 512m --env-file "$SNAPSHOT/api-test.env" \
     dh-catalog-test python -m pytest tests acceptance/test_compare.py
   ```

6. 记录实际 Python / PostgreSQL 版本、候选 SHA、镜像 ID、资源限制、退出码、通过数、警告与跳过数；**db 项须 0 跳过**。失败修复只在本机，重新形成候选快照，不在 NAS 改代码。T-24 测试不等于正式容器启动、真实只读挂载或 NAS 全量验收。
7. 无论测试成功或失败，都清理本轮一次性资源：若测试 API 容器仍在则停止它；`docker stop dh-catalog-test-db` 后等待 `--rm` 移除容器及匿名卷，再 `docker network rm dh-catalog-test`（均使用 `/usr/local/bin/docker`）。删除本轮隔离快照和两份临时凭证文件，按需移除本轮测试镜像；记录实际清理结果，不运行全局 prune，不删除其他项目的资源。

## T-25：merge 后获准正式部署与只读冒烟（未执行）

前置：T-24 证据补齐 → Converge / 独立 Review → 用户 Gate 2 → merge 到 main → **另获部署许可**。部署时低峰、`MemAvailable >= 2GB`；不重建、不重启 v0，不启动图块生成器。以下命令只用于已获准阶段，不能据此提前执行。

1. 本机依次 `git push origin main`、`git push nas main`，仅传已合并提交；文件操作走 `ssh nas`，容器操作走 `ssh nasroot`。在 NAS 核实部署工作区 HEAD 与获准 main SHA 一致，不在 NAS 修改代码。
2. 在 `/srv/example/viewer/catalog/` 准备权限 600 的 `.env`，填写实际 SHA、独立数据库随机密码及明确接口地址；只读确认 plan §4.8 的 host 路径存在、v0 `.env` / `cache/users.json` 可读。不要列目录或遍历 cache；不要改 v0 配置。确认 pgdata 为新项目专用且不在 git 工作区，首次初始化后不能只改 `.env` 密码而不更新数据库口令。
3. 进入上述 `catalog/` 目录，把 `DH_CODE_VERSION` 导出为已核实提交的完整 SHA（`export DH_CODE_VERSION="$(git rev-parse HEAD)"`），确认与 `.env` 相同；运行配置静默校验。正式构建也须沿用 T-24 已验证的受限构建方式，不用未设构建限额的 `up --build`：

   ```bash
   /usr/local/bin/docker-compose -p dunhuang-catalog config -q
   DOCKER_BUILDKIT=0 /usr/local/bin/docker build --memory 512m --memory-swap 512m \
     --build-arg DH_CODE_VERSION="$DH_CODE_VERSION" -t "dunhuang-catalog:$DH_CODE_VERSION" .
   /usr/local/bin/docker-compose -p dunhuang-catalog up -d --no-build catalog-db catalog-api
   ```

   逐条检查成功后再继续；内存限制不受支持时停止报告。始终只操作新项目，不引用根目录 compose。API 的默认命令负责先迁移后启动；失败时查日志和状态，不绕过迁移。
4. `/usr/local/bin/docker-compose -p dunhuang-catalog exec -T catalog-api python -m dh_catalog health` 应成功。用本项目 `ps -q` 取得容器 ID，通过 `docker inspect` 仅选取 `.HostConfig.Memory`、`.HostConfig.MemorySwap`、`.Mounts`、`.NetworkSettings.Ports` 与 `.State`：核实两项限额、四项只读挂载、pgdata 位置、数据库无宿主端口、API 仅绑定两个指定地址，以及健康 / OOM 状态。不要打印完整 inspect 的环境凭证。
5. 在 LAN / Tailscale 分别做只读冒烟：匿名 GET 拒绝；通过 v0 正常登录的普通账号可 GET、POST 导入被 403 拒绝；管理员只做 GET（如 `/api/v1/imports`、受保护文档）。**不执行管理员 POST，不删正式 secret，不触发任何正式导入**；缺 secret 的 fail-closed 与合成导入以 T-24 结果为证，不另签 cookie。
6. 记录实际绑定、限额、只读挂载、health 和权限结果。异常先停止验收、报告；需要回滚时只停新项目（在本目录 `/usr/local/bin/docker-compose -p dunhuang-catalog down`），保留 pgdata，不影响 v0。代码修复回本机，重新 Review → Gate 2 → merge → 获准部署。

T-26 的首次全量导入及无变化重跑只能由用户在接口文档页触发。A1～A7 的细步骤、基线与结果输出位置留 T-23 补齐；真实 SQL、镜像、原材料不变性、内存 / v0 连续健康、耗时、P95 和链接抽查在各自阶段取得证据前都仍为待验。
