# 目录服务（catalog-foundation）

> 公开隐私修订：私人部署实例与原件非公开保全；历史验证为脱敏衍生记录，不是逐字原文。配置占位不代表真实主机。

**当前交付（2026-10-31）**：目录底座R3与隐私R5均独立通过，原软件及本轮隐私Gate2均获用户确认；当前运行实现已就绪，origin两分支历史按原租约受保护更新并实际远端复扫、本机迁移完成，交接与PR #1正常匿名UTC合并完成。交接本机489通过/61跳过/1原警告（48.99秒）；合并后T-39隔离目标回归483通过/0跳过（61个db项含新增4项实际通过）。**T-25 已获准执行（2026-10-30）**：部署远端首次同步与 v0 宿主配置迁移完成，目录服务两容器健康，限额、只读挂载、端口绑定核验通过，匿名访问均得 401；登录态冒烟经用户完成并核对，T-25 完成。v0 未重建、未重启。T-26 已获准执行：导入、只读、性能与链接验收达标，画布对应发现 F-1；F-1 已经 T-40 修复，并于 T-41（2026-10-31）部署、重导复验，A4 为 99.68%，详见 tasks T-26/T-41；v0 根镜像重建另议。新前端/标注工作台不在本feature，v0继续原状；不宣称真实材料或生产验收通过。

当前是独立后端。以下开头两段为隐私实施前的软件历史状态，后续公开发布进度以 `specs/public-release-privacy/` 为准，不把旧证据当新验证。**2026-10-30 N1修复候选private-candidate-063在NAS隔离Python3.12.15/PostgreSQL17.4全446项通过、0跳过；独立CodeReview-R3已软件通过、N1关闭，原软件Gate2已获用户批准；用户随后确认保持Public，D-019已登记。交接/PR/合并等待public-release-privacy脱敏规格批准、实施与验证，当前尚未批量清理；未部署或真实材料验收**。需求与任务以 `../specs/catalog-foundation/` 为准；不改 v0。

已实现配置、只读材料与影像事实、编号解析、单元/备份映射、稳定身份、谱系/许可/出处、共用认证、v0快照/采样/链接、只读API与管理员导入。R2已软件通过并关闭原主要问题；本轮用户批准的N1最小修复保留依据升级时未变编号的id/持有起点，当前依据更新、过去历史保留，同版本无变化重导不制造曾用号或无条件更新。具体实现/测试矩阵、失败与清理证据见feature的tasks.md/converge.md/review.md，不把主会话回归当独立审核。

旧候选private-candidate-056/T36已在原512m硬限完成36k差异化合成首轮/真实PG重导，cgroup含页缓存触512但无OOM；**本轮未重做规模，旧36k不是新候选直接实测**，独立R3据差异认可旧证据支持新候选首轮/同版本无变化重导，不要求为本次修复重跑；规则升级足规模仍未验。当前编号记录的边界：同号但来源/路径/主号来源变化仍可能生成同号historical；记录历史不保证编号值曾变，展示语义如需改变须先澄清，不在本轮扩修。真实材料/并发/v0连续健康/性能、正式挂载/端口/默认服务启动仍T25/T26待许可。T23固定基线、比较器与下文A1～A7入口已提供，不以合成集成测试代生产验收。

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
| DH_V0_URL / DH_V0_PUBLIC_URL | v0 请求地址 / 查看器链接地址；正式 Compose 的 DH_V0_URL 必填，PUBLIC_URL 由可选 env_file 进入配置入口，空值等同缺省并回退前者；不依赖 Compose 嵌套插值 |
| DH_DATABASE_URL | 目录数据库连接；没有凭证默认值 |
| DH_CODE_VERSION | 导入记录中的运行代码版本；本机缺省 development，生产镜像须注入实际提交版本 |
| DH_TEST_DATABASE_URL | 仅测试用的一次性 PostgreSQL 库，库名须以 dh_catalog_test_ 开头，绝不能指向正式库 |
| DH_HOST_DATA_DIR / DH_HOST_BACKUP_DIR / DH_HOST_CACHE_DIR | Compose 必填的宿主原图 / 备份 / v0缓存根；只读挂载到 /data、/backup、/v0cache，不是容器 DH_DATA_DIR / DH_BACKUP_DIR |
| DH_HOST_V0_ENV_FILE / DH_HOST_PGDATA_DIR | Compose 必填的宿主 v0环境文件 / 外部专用PG目录；前者只读挂载，不复制凭证；后者不得置于git工作区 |
| CATALOG_LAN_IP / CATALOG_TAILSCALE_IP | Compose 必填的局域网 / Tailscale 绑定地址，不可用公网或通配地址。若 Tailscale 以用户态网络模式运行（Tailscale 地址不在本机网卡上），后者填 `127.0.0.1`：tailscaled 把连入 Tailscale 地址的连接转发到本机回环 |
| DH_RECORD_DATA_ROOT / DH_RECORD_BACKUP_ROOT | 可选的旧记录绝对路径字符串前缀；为空仅识别 /data/、/backup/ 与相对记录，不从 HOST 输入推断，不访问所填路径 |

`load_settings` 的开发后备仅为 `http://localhost:8503`，不代表生产入口。旧记录前缀在配置入口去首尾空白、要求绝对且不等于 `/` 并补尾斜杠；例如中性字符串 `/legacy/data` 与 `/legacy/backup` 仅示意记录格式，不是实际主机路径。未配置的绝对记录不能悄悄猜测其来源。

公开隐私修订使用 `第三方资料接收（接收事件 A）` 和 `RULE_VERSION=2026-10-30.1`；机构下载、本地派生标签及许可严格度不变，旧库和过去批次不被覆写。后续部署前须填写上述必填参数；本次文档修订不操作任何已部署配置。

配置在启动入口读取，导入模块不加载运行配置或原始材料、不连接网络或数据库。上述配置契约已按公开隐私方案修订；下面的旧候选测试数字仍是历史证据，不能代本轮源码/配置新验证。API 工厂是 `dh_catalog.api:create_app`（uvicorn `--factory`）；缺少 v0 AUTH_SECRET 时，登录墙对所有请求返回 503，不退回环境中另一份 secret；每个通过的请求只验证一次 cookie、只读一次用户记录，后续路由消费 Principal。

运维 CLI 已实现 `migrate`、只读 `report [--run ID]` 与 `health`，不提供 CLI 导入。设置专用数据库连接后，在仓库根使用 `PYTHONPATH=catalog/src python -m dh_catalog <命令>`。report 在数据库只读事务中取已保存批次，不加载认证文件或调用 v0；health 校验 secret 与数据库 / 迁移可用性，不走 HTTP、不读用户表或原图、不加载扫描 / 导入器。三个 CLI 的合成 PostgreSQL 路径均已由 T-24 验证（含失败/只读约束），不据此宣称生产部署成功。

## 导入器集成接口（实现与数据库集成已验证，真实材料待验）

- `prepare_import(pool, triggered_by=..., code_version=..., session_cookie=..., v0_url=...)` 同步持连接与咨询锁并创建批次，返回含 run_id 的 PreparedImport；已在跑则抛 ImportBusy。管理员 API 先完成这一段再返回 202，ImportBusy 同步转 409。
- 后台调用 `PreparedImport.execute(roots, cache_dir, record_roots=...)`；配置入口解析的可选旧记录前缀随 API → execute → compute → derivation 传递，默认空映射。派发失败则 `cancel()` 清理。内部复用真实 scan / nlc / derivation / identity / rules，附件读取即消费，不在内存保留全量原文。
- `compute_import(...)` 是可本机验证的真实计算阶段；持久化、唯一约束互换、失败回滚与历史读取已在 T-24 真实 PostgreSQL 通过。仍区分本机 DTO/计算测试与真库证据，不把合成集成测试代替真实材料验收。
- `read_report()` 读取已有批次。当前 `import_run.counts` 保存完整报告对象，其中的 `counts` 子键才是统计计数；API 将完整对象明确返回为 `report`，统计位于 `report.counts`；`acceptance/compare.py` 只消费这些计数，不再扫描原始材料重算业务判断。

只读 API 路径与查询参数见受保护的 `/api/v1/docs`（接口清单的设计权威在 feature plan §2.1）。编号查询只命中 current，历史 / pending 在详情展示；批次历史使用 `?run=`。GET 使用只读事务；附件返回保存的原字节。唯一写方法是管理员 `POST /api/v1/imports`，不提供目录内容修改、取消或回滚 API。

## 测试与部署边界

本机当前只验证不依赖数据库的模块。默认 pytest 会把缺少测试连接的 db 项明确列为跳过，不能宣称全部数据库测试通过。数据库测试会清空指定临时库的业务表，只接受 `dh_catalog_test_*` 库名，不读取 DH_DATABASE_URL 作为后备。

以下历史真实 PostgreSQL 与 Python 3.12 镜像测试使用当时用户批准的候选快照与一次性容器，不启动正式Compose、不挂正式pgdata、真实材料或v0文件。本轮T38-A2/private-candidate-063为446项全通过/0skip（73.22秒），含57个实际db项；首轮A1的445通过/1新增HTTP请求元数据期望错误及Astra一行修正均保留原件，见任务T37/T38及[公开验证摘要](../docs/verification.md)（原件非公开）。T24旧402/404和T36旧442仍是各自候选的历史证据。测试中的v0 HTTP仅边界替身，不代实际v0健康；隔离测试许可不等于正式部署许可。

当前 Starlette 的 TestClient 会对已固定版本的 httpx 发出一条弃用警告；测试仍可运行，未静默屏蔽警告或为消除警告升级依赖。

正式部署须独立 Review → Gate 2 → merge 后另获许可，不得从功能分支推送 NAS。部署只读冒烟不触发导入；正式全量导入由用户在接口文档页触发（T-26）。NAS 内存 / 耗时 / P95 与原材料只读验收尚未执行，不能以本机单元测试代替。

## 运行文件（T-22，隔离构建已验证，正式运行待验）

- 构建上下文必须是 `catalog/`，不是仓库根。镜像只安装本目录固定依赖，pip 源与 v0 相同；无 apt、libvips 或图块管线。`src/` 放在 `/app/src`，迁移在 `/app/migrations`，与 `db.MIGRATIONS` 对齐。
- 同一镜像包含真实 `tests/`、`pytest.ini`、`acceptance/`，以及静态测试读取的运行配置源文件。**T-24 两个候选均完成受限构建；修复后的 A2 全部测试实际通过，并已清理测试资源。** 镜像构建不代替正式启动、挂载或部署验证。
- 启动先执行 migrate，成功后才 exec uvicorn 工厂；健康检查调用 `python -m dh_catalog health`，不签 cookie、不走 HTTP。`DH_CODE_VERSION` 同时作为构建参数与运行环境传入，不在镜像里执行 git。
- `docker-compose.yml` 只有 `catalog-db` / `catalog-api`；每次操作都指定 `-p dunhuang-catalog`。内存硬限额及 memswap、PostgreSQL 参数、外部 pgdata 和四项只读挂载以此文件为准。API 按计划以 root 读取 root:600 用户表，不增加宿主可写挂载。
- API 仅绑定 NAS 的 LAN / Tailscale 显式地址；数据库没有宿主端口。配置变量不得改为 `0.0.0.0`、`::` 或其他公网 / 通配地址。不添加 nginx / frp 公网入口，不修改真实防火墙；T-25 还须检查实际端口绑定。
- `.env.example` 只有非秘密设置和空占位。获准操作时才在对应 NAS 部署位置准备 `catalog/.env`（权限 600），**先填写新生成的数据库密码、实际提交完整 SHA、显式 DH_V0_URL、两项绑定地址及五项 DH_HOST 输入**。Compose 对必要空值直接报错；不复制 v0 的 `.env`，不把 AUTH_SECRET 填入新配置。认证只读取只读 `/run/v0.env`。
- 当前 Compose 将 POSTGRES_PASSWORD 原样放进数据库 URI，故须使用 URL 安全的随机字符，建议随机十六进制；不要使用含 `@ : / % $ #`、空格等字符的密码，也不要仅把 PostgreSQL 原密码改成百分号编码（两端会不一致）。配置通过环境传值，不 source `.env`、不把密码或其他配置拼进 shell 命令。不要将真实配置 / 展开的连接串打印、提交或放进构建上下文。
- `.dockerignore` 排除凭证、Windows venv、缓存、日志和 Python 产物，保留源码、合成测试与验收文件。`tests/test_runtime.py` 仅保护这些关键文本契约，**不是 YAML / Compose 校验器，也不是构建、Python 3.12 或运行证明**。

## T-24：在 NAS 隔离快照验证（已完成，保留执行方法）

本机没有 Docker，本轮未在本机安装 Docker/Compose。经用户批准，主会话已按下列范围完成测试与清理，实际候选/命令/输出在 tasks.md 与 [公开验证摘要](../docs/verification.md)（详细原件非公开）、非公开 T24-A2 阶段记录、非公开 T24-A3 阶段记录。下面是执行方法，不是要求再次启动资源：只在唯一隔离目录工作，不推送 nas main、不起正式 Compose、不访问正式 pgdata、真实材料或认证文件。测试前记录候选完整 SHA、目录与预算，低峰且 NAS `MemAvailable >= 2GB` 才执行；构建限额不生效则停止报告。

1. 从本机用 `git archive <候选完整 SHA> catalog` 导出已记录候选快照，送入获准的 NAS **隔离临时目录**（不是部署 git 工作区）。下文 `SNAPSHOT` 指解包根目录，`CANDIDATE` 指该 SHA。只在隔离位置工作，不能修改快照代码来修测试。
2. 核实目标 Docker 构建后端支持并实际落实内存与 swap 硬限制。以下命令以支持 legacy builder 的环境为前提；若禁用 BuildKit 不可用，或后端忽略 / 不支持资源参数，**停止并报告，请用户决定受限构建方式，不得删参数后无上限重试**。

   ```bash
   DOCKER_BUILDKIT=0 /usr/local/bin/docker build --memory 512m --memory-swap 512m \
     --build-arg DH_CODE_VERSION="$CANDIDATE" -t dh-catalog-test "$SNAPSHOT/catalog"
   ```

3. 正式 Compose 的 `config -q` 留 T-25。若 T-24 额外做语法检查，只能在隔离快照的 `catalog/` 里从 `.env.example` 准备权限 600 的**合成配置**，填临时随机密码、候选 SHA、合成的显式 URL/两项绑定地址和五项 HOST 输入，再执行 `/usr/local/bin/docker-compose -p dunhuang-catalog config -q`；绝不执行 up，也不运行会打印展开凭证的 `config`。这不会证明挂载或端口在运行时成立。
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

1. 本机先 `git push origin main`。公开历史重写后的**首次**部署同步按 `specs/catalog-foundation/tasks.md` T-25 部署前置执行：先迁移 v0 的 `.env` 与开机钩子宿主配置，再以单 ref 精确租约替换部署远端 main。此后恢复普通 `git push nas main`，仅传已合并提交；文件操作走 `ssh nas`，容器操作走 `ssh nasroot`。在 NAS 核实部署工作区 HEAD 与获准 main SHA 一致，不在 NAS 修改代码。
2. 在 `${DH_DEPLOY_DIR}/catalog/` 准备权限 600 的 `.env`，填写实际 SHA、独立数据库随机密码及明确接口地址；只读确认 plan §4.8 的 host 路径存在、v0 `.env` / `cache/users.json` 可读。不要列目录或遍历 cache；不要改 v0 配置。确认 pgdata 为新项目专用且不在 git 工作区，首次初始化后不能只改 `.env` 密码而不更新数据库口令。
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

T-26 的首次全量导入及无变化重跑只能由用户在接口文档页触发。下文 A1～A7 已提供入口；真实 SQL、镜像、原材料不变性、内存 / v0 连续健康、耗时、P95 和链接抽查在各自阶段取得证据前都仍为待验。

## T-23：本机只读基线比较

文件：`acceptance/baseline-2026-10-27.json`（34 项）、`acceptance/compare.py`、`acceptance/test_compare.py`。
基线固定为 2026-10-27；6,096 是影像目录，不是写卷数。Q-024 新 A077 资料六个 txt 只能解释 477 → 483 的差异，不能改基线抵数。

比较器只用标准库读取本地 JSON，向 stdout 输出 JSON，不连接服务、不加载 dh_catalog / 配置、不扫描材料、不写文件。接受：

| 输入 | 统计路径 | 批次成功证据 |
|---|---|---|
| `python -m dh_catalog report --run ID` 导出的单批次整行 | `counts.counts` | 外层 `status == "succeeded"` |
| `GET /api/v1/imports/{id}` 导出的单批次整行 | `report.counts` | 外层 `status == "succeeded"` |
| `build_report` 的直接报告 | `counts` | 没有 status，只能比较，不能称完成验收 |

不接受 `/imports` 的分页列表（应再 GET 指定批次）。逐项输出 `expected`、`actual`、`delta`、`result`、计数来源、后续核查入口和人工说明。`match` 只表示计数相同。标量缺失不填零；仅 `attachments_by_kind`、`anomalies_by_category`、`parts_by_parent`、`items_by_doubtful_number`、`directories_by_lineage` 这五个真实 Counter，在**容器存在且全部值为非负整数**时，缺键才表示零（输出 `sparse_zero`）。容器缺失为 `missing`，类型错误为无效输入。

报告的 `excluded_jpg` 不能证明全是图块；比较器仅展示 observed，不冒充图块实际数。母号查询返回 5 件、12 个长卷逐条有派生或异常也不能由计数直接证明：这三项固定为 `unverified`。P.0901 件数、开宝藏/题名线索等虽有计数，仍须 A2 核对对象关系；不会把统计相同称为完整 AC 通过。

在仓库根（`EVIDENCE` 是已批准的**外部**本机证据目录，不在本仓库内）：

```bash
python -I -X utf8 catalog/acceptance/compare.py "$EVIDENCE/A1-run.json" > "$EVIDENCE/A2-compare.json"
# 查看并记录上一条退出码，不因非零就删除输出
printf '%s\n' "$?" > "$EVIDENCE/A2-compare.exit"
# 可选：人工在证据目录写 notes.json，例如 {"txt":"Q-024 六个新增附件，逐条证据见 A2-attachments.json"}
python -I -X utf8 catalog/acceptance/compare.py "$EVIDENCE/A1-run.json" \
  --notes "$EVIDENCE/notes.json" > "$EVIDENCE/A2-compare-with-notes.json"
printf '%s\n' "$?" > "$EVIDENCE/A2-compare-with-notes.exit"
```

退出码：**0** 所选基线计数全部相同、状态成功且无缺证据（不表示完整 AC）；**1** 存在差异（可同时有缺证据）；**2** 无已知差异但缺计数/不可证明/直接报告无批次状态；**3** JSON 文件、字段类型或基线/说明无效；**4** 批次 running/failed（优先于差异）。命令行参数用法错误由 argparse 返回 2 并显示用法。默认完整基线有三项人工核查，因此不会得到 0；不要删指标求 0。`--baseline PATH` 只用于明确标注范围的其他对照/合成测试，不替换正式基线。说明只附加，不改变差异与退出码。

本机完整非 DB 验证（现有 venv，不安装依赖）：

```bash
catalog/.venv/Scripts/python.exe -I -X utf8 -m pytest -c catalog/pytest.ini -m 'not db' catalog/tests catalog/acceptance/test_compare.py
python -m py_compile app.py pyramid_worker.py stitch_apply.py
python -I -X utf8 tools/check_docs.py .
git diff --check
```

`-m 'not db'` 的 db 项是 deselected，不是通过；默认全套没有测试连接时才是 skipped。两者都不是数据库证据。

## T-26：A1～A7 可执行验收入口（均未在 NAS 执行）

### 前置与证据位置

- T-24 测试许可、T-25 部署许可、T-26 全量验收许可分别取得；Gate 2 / merge 不能替代许可。低峰且宿主 `MemAvailable >= 2GB`，先保存 `grep '^MemAvailable:' /proc/meminfo`。不关闭或重启 v0，不恢复 Q-025 删除的暂停/中止、内容指纹等机制。
- 宿主证据目录 `E` 与本机对应 `EVIDENCE` 均由用户在非公开配置中批准指定；本说明不提供私人路径。两者均必须在部署 git 工作区、pgdata、原材料与 cache **之外**，权限仅供验收人员；先 `umask 077` 再创建。不要将这些变量设为仓库子目录。所有真实报告、元数据、差异与截图不入库，不进入构建上下文。
- 浏览器启用“每次下载询问保存位置”，以下 `save` 下载均存入本机 `EVIDENCE`；catalog 与 v0 走局域网 HTTP，浏览器可能拦截这些下载，须在下载列表点“保留”。只用用户正常登录 v0 的真实会话；在同一 NAS 主机名的 catalog 受保护文档页操作。不能读取/复制 `.env` 或 users.json 来签发会话；不复制 cookie 到代码、脚本、命令、日志或 HAR，不使用“Copy as cURL”。
- 先做 A5 前快照并启动资源采样，再由用户在 `/api/v1/docs` 手动触发 POST，记录返回批次 ID。本节没有 CLI 导入或自动 POST。无变化重跑也由用户自行触发，分别记录两批 ID。
- 若文档页前端渲染失败（2026-10-31 曾出现 Swagger UI “Could not render responses”），先从服务端访问日志与 `import_run` 确认没有 POST 到达，再由用户在同源已登录页面的控制台只执行一次 `fetch('/api/v1/imports', {method: 'POST', credentials: 'same-origin', redirect: 'error'}).then(async r => console.log(r.status, await r.text()))`；返回非 202 时不重试，先核查服务端。

以下浏览器辅助片段均仅 GET，置于已登录 catalog 页控制台；没有会话字面量。定义一次后供 A1～A4、A6、A7 使用。任何非 200、重定向、非 JSON 均拒绝，不把登录页当结果：

```javascript
function save(name, data) {
  const a = document.createElement('a');
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type:'application/json'}));
  a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 10000);
}
async function getJSON(path) {
  const r = await fetch(path, {credentials:'same-origin', cache:'no-store', redirect:'error'});
  if (r.status !== 200 || !r.headers.get('content-type')?.includes('application/json'))
    throw new Error(`GET 未成功：${r.status}`);
  return await r.json(); // 等待完整响应
}
async function allPages(path) {
  const rows = []; let total;
  for (let page=1; ; page++) {
    const r = await getJSON(`${path}${path.includes('?')?'&':'?'}page=${page}&page_size=200`);
    if (!Array.isArray(r.items) || !Number.isInteger(r.total) || r.page !== page)
      throw new Error('分页响应无效');
    if (total !== undefined && total !== r.total) throw new Error('分页期间数据变化，须重新取证');
    total = r.total; rows.push(...r.items);
    if (rows.length === total) return rows;
    if (!r.items.length || rows.length > total) throw new Error('分页缺失或溢出');
  }
}
```

### A1：成功批次与本批 v0 覆盖（AC-001-1）

在文档页 GET `/api/v1/imports` 选择用户刚触发的批次（不是随意找旧成功批次），输入该 ID：

```javascript
var runId = Number(prompt('刚完成的导入批次 ID'));
if (!Number.isInteger(runId) || runId < 1) throw new Error('ID 无效');
var run = await getJSON(`/api/v1/imports/${runId}`);
save('A1-run.json', run);
if (run.status !== 'succeeded' || !run.ended_at) throw new Error('批次未完成成功，待验');
var report = run.report;
save('A1-coverage.json', {run:run.id, started_at:run.started_at, ended_at:run.ended_at,
  v0_snapshot_status:run.v0_snapshot_status, coverage:report.coverage});
if (report.coverage?.status !== 'valid' || report.coverage.unmapped_existing_count !== 0)
  throw new Error('本批覆盖不可验证或存在未对应目录');
```

分别保存 `coverage.disk_not_indexed`（磁盘已有、索引未收录）、`coverage.index_directory_absent`（索引有、磁盘无）及 `unmapped_existing`；前两项不是同一集合。无有效索引只能待验，`latest_valid_snapshot_available=true` 只是链接可用旧快照，不能冒充本批覆盖。另一种导出入口是获准后在 NAS catalog 工作目录执行只读 CLI：

```bash
# RUN_ID 填已经确认成功的本次批次 ID；不得省略而误取最新 running 批次
/usr/local/bin/docker-compose -p dunhuang-catalog exec -T catalog-api \
  python -m dh_catalog report --run "$RUN_ID" > "$E/A1-run-cli.json"
```

CLI 导出为整行，须保留 status。导出命令连接目录库，但不会导入；**当前本机任务不执行该命令**。

### A2：全部基线与对象对应关系（AC-010-2 等）

运行上节 compare，保存逐项比较与退出码；人工用 `id` 为键记录原因及证据文件，所有差异、缺指标和未验证项逐项处理，不以解释抹除差异。确认所用 `code_version` / `rule_version` 与候选一致，报告批次与 API 核查期间没有新导入；API 列表/详情是当前状态，不是指定批次快照，发生新导入须重新取证。

```javascript
var checks = {};
for (const q of ['P.2002','P2002','Pelliot chinois 2002','P.2504','P.0901','WB 29']) {
  const r = await getJSON('/api/v1/resolve?q='+encodeURIComponent(q));
  checks[q] = {resolve:r, details:[]};
  for (const item of r.items) checks[q].details.push(await getJSON('/api/v1/items/'+item.id));
}
save('A2-resolve-details.json', checks);
save('A2-anomalies.json', await allPages(`/api/v1/anomalies?run=${run.id}`));
save('A2-report-evidence.json', {excluded:report.excluded, unassigned_attachments:report.unassigned_attachments,
  suggestion_unit_evidence:report.suggestion_unit_evidence});
```

人工核查并写 `A2-object-checks.json`（每项含期望、实际、对象 ID/路径、证据文件、结论/原因）：

- P.2002 三种写法同一件，详情 `images[].lineage` 与 `relationship.source_directory` 包含 BnF 原图及第三方加工图两套；不能只看 resolve 的 total。
- P.2504 `total=5` 且五个不同 ID；逐件详情 `identifiers` 的 current 主号/母号/分件、`parent` / `parts` 是母件加四分件。P.0901 `total=3`、三 ID 各对应绢画/梵文写经/坐佛像的原始位置，主号为空、不自动合并；WB 29 返回两件。
- `report.excluded` 对照图块缓存 JPG 98 的逐项路径/原因；`counts.excluded_jpg` 还可能包含其他排除 JPG，不能直接当图块数。Q-024 六个 txt 核对 `unassigned_attachments` 的路径，必要时 GET `/api/v1/attachments/{id}` 取已保存原文；只有附件目录产生的缺少影像单列，与旧基线 0 的差异保留。
- 目录计数/单元计数与基线单位不同或材料新增时，记录逐条对象证据，不发明名称解析规则。在 `A2-anomalies.json` 核查隐藏同目录 10、词表外 1、疑似 2、号段外两号码及备份分片对不上等异常；异常类别计数不是所有对象关系的证明。
- 开宝藏 18、题名线索 6：按 `suggestion_unit_evidence` 既有目录证据标签定位列表/详情（`/items?category=...&batch=...` 可筛选，需遍历分页），确认每个对应写卷 `provenance.status=待核`、`suggestion=非敦煌`、依据齐全，不能直接定非敦煌。
- 合并长卷 12：从实际列表逐页 GET `/items/{id}`，按影像 ID 去重，选 **已有** `relationship.role == '合并长卷'`（不要自行匹配文件名重做规则）。对每个 ID GET `/images/{id}`，逐条保存 `derivations` 中源 ID/方式/证据文件行号；没有派生的，须在本批 `派生来源不明` 异常中找到该根/路径。保存 `A2-merged-scrolls.json` 的 12 行对应表，不能把 `outputs_with_derivation` 与异常总数相加抵数。白名单文件本身读失败的全局异常不等于某个长卷已被逐条解释。

### A3：目录谱系（AC-005-2）

```javascript
save('A3-lineages.json', {run:run.id, counts:report.counts.directories_by_lineage,
  directories:report.directory_lineages});
```

对照基线 BnF 447 / 第三方 499 / 本地 12 / 国图 5,138；只读既有目录级汇总和 `directory_lineages`（含 root，基线只计 data），逐项记录混合、未判定与差异目录。不要以 `images_by_lineage` 文件数替代目录数，也不再读取文件头重算谱系。

### A4：国图 TIFF 画布对应（AC-005-4）

```javascript
var n = report.counts.nlc_tiff, matched = report.counts.nlc_tiff_with_canvas;
var rate = Number.isInteger(n) && n > 0 && Number.isInteger(matched) && matched >= 0 && matched <= n
  ? matched/n : null;
save('A4-canvas.json', {run:run.id, nlc_tiff:n, nlc_tiff_with_canvas:matched, rate,
  anomalies:await allPages(`/api/v1/anomalies?run=${run.id}&category=${encodeURIComponent('画布对不上')}`)});
```

分母 0、字段缺失或不合法时不能算 100%。不是 100% 时逐个 TIFF 根/路径关联本批画布异常，并经 `/images/{id}` 保存 canvas_number / canvas_id；无对应异常的缺口不通过。允许列明异常，不伪造全部对应。

### A5：只读、不影响 v0、内存与耗时（AC-012-1～4）

**只有取得 T-26 许可后**，宿主原图/备份前后各一次只读元数据清单（路径、大小、mtime_ns），不读全文件/内容指纹，不遍历或列出 cache。先在导入前执行 `STAGE=before`，全量与无变化重跑完成后再执行 `STAGE=after`；中间不另扫描。若其他写入方活动导致重跑数据变化，则不把它称为无变化重跑，记录后另请用户安排。以下使用宿主已有 `python3`，若不可用先报告，不安装新依赖：

```bash
# 在已批准的 NAS 证据目录上下文；E 预先设为外部证据目录
# 显式导出获准原图/备份根；缺配置在创建证据前失败，不猜测路径
: "${DH_HOST_DATA_DIR:?必须配置原图根}" "${DH_HOST_BACKUP_DIR:?必须配置备份根}"
export DH_HOST_DATA_DIR DH_HOST_BACKUP_DIR
STAGE=before  # 完成两批导入后改为 after，再执行同一段
python3 - "$E/$STAGE-metadata.jsonl" <<'PY'
import json, os, pathlib, sys

def fail(error):
    raise error

with open(sys.argv[1], 'x', encoding='utf-8', newline='\n') as out:
    for root in (os.environ['DH_HOST_DATA_DIR'], os.environ['DH_HOST_BACKUP_DIR']):
        for directory, _, files in os.walk(root, followlinks=False, onerror=fail):
            for name in sorted(files):
                path = pathlib.Path(directory) / name
                st = os.lstat(path)  # 等价于 stat(follow_symlinks=False)，兼容宿主 Python 3.8
                out.write(json.dumps([root, str(path.relative_to(root)), st.st_size, st.st_mtime_ns], ensure_ascii=False)+'\n')
PY
```

任何读取错误都使本次清单无效，不能拿半份清单验收。两次清单比较只读证据，不再扫描材料：

```bash
python3 - "$E" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
def load(name):
    with (p/name).open(encoding='utf-8') as f:
        return {tuple(r[:2]): r[2:] for r in map(json.loads, f)}
a, b = load('before-metadata.jsonl'), load('after-metadata.jsonl')
changes = [{'root':k[0], 'path':k[1], 'before':a.get(k), 'after':b.get(k), 'attribution':''}
           for k in sorted(a.keys() | b.keys()) if a.get(k) != b.get(k)]
with (p/'A5-metadata-differences.json').open('x', encoding='utf-8') as f:
    json.dump(changes, f, ensure_ascii=False, indent=2)
PY
```

每个变化另写归因及证据（v0 拼接/下载器等），不明变化不通过。`mtime` 不是内容不变的强证明，本验收不增加内容指纹。

在 catalog 部署目录，用实际服务 ID 选择 inspect 字段，输出不含 Env：

```bash
API=$(/usr/local/bin/docker-compose -p dunhuang-catalog ps -q catalog-api)
DB=$(/usr/local/bin/docker-compose -p dunhuang-catalog ps -q catalog-db)
for C in "$API" "$DB"; do
  /usr/local/bin/docker inspect --format '{{json .Id}} {{json .HostConfig.Memory}} {{json .HostConfig.MemorySwap}} {{json .Mounts}} {{json .NetworkSettings.Ports}} {{json .State.Status}} {{json .State.Running}} {{json .State.OOMKilled}} {{json .State.ExitCode}} {{json .State.FinishedAt}} {{json .RestartCount}}' "$C"
done > "$E/A5-inspect-before.txt"
```

核实 API=536870912、DB=402653184 字节且各自 MemorySwap 相等；`/data`、`/backup`、`/v0cache`、`/run/v0.env` 的 RW=false；pgdata 在外部专用目录；DB 无宿主端口、API 仅 LAN/Tailscale。两批完成后重复同一限定 inspect 存 `A5-inspect-after.txt`，记录 OOMKilled、退出状态、RestartCount（重启可能掩盖前次 OOM，须核对本时段事件/运维记录）。不打印整份 inspect。

导入前在**宿主另一个终端**运行以下采样，覆盖全量和重跑，完成后 Ctrl+C 只结束采样器，不停服务：

```bash
python3 - "$E/A5-stats.jsonl" "$API" "$DB" <<'PY'
import datetime, json, subprocess, sys, time
with open(sys.argv[1], 'x', encoding='utf-8') as out:
    tick = time.monotonic()
    try:
        while True:
            try:  # 单次 docker stats 超时只记一条，不能让采样器整体退出
                r = subprocess.run(['/usr/local/bin/docker', 'stats', '--no-stream', '--format', '{{json .}}', *sys.argv[2:]],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=5)
                rc, lines = r.returncode, r.stdout.splitlines()
            except subprocess.TimeoutExpired:
                rc, lines = 'timeout', []
            out.write(json.dumps({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                  'returncode':rc, 'stats':lines})+'\n')
            out.flush()
            tick += 5
            time.sleep(max(0, tick-time.monotonic()))
    except KeyboardInterrupt:
        pass
PY
```

记录每 5 秒的样本、异常/超时与覆盖时间；样本缺口不能当“全部正常”。容器无 OOM/异常终止，API 在 512 MB 硬限内成功完成。停止/重启记录有疑问时保留待验，不通过重启 v0 来取得漂亮样本。

报告核查：保存两批 A1 整行到 `A5-full-run.json` / `A5-repeat-run.json`；用 ended_at-started_at 计算耗时（全量 ≤3600 秒，无变化重跑 ≤600 秒），检查重跑 `counts.changes` 与实际数据变化。`report.health` 的真实字段是 **count / failures / max_seconds / samples**：count>0、samples 数与 count 一致、failures=0、max_seconds≤2、每条 sample.ok=true 且 seconds≤2，时间覆盖导入过程。任何零样本、失败或缺字段不得判通过。导入没有自动暂停/中止机制。在 catalog 浏览器页面保存并检查两批（`run` 是 A1 全量批次，重跑由用户另外触发）：

```javascript
var repeatId=Number(prompt('已完成的无变化重跑批次 ID'));
if (!Number.isInteger(repeatId) || repeatId<1 || repeatId===run.id) throw new Error('重跑批次 ID 无效');
var repeatRun=await getJSON('/api/v1/imports/'+repeatId);
save('A5-full-run.json', run); save('A5-repeat-run.json', repeatRun);
var resources=[];
for (const [label, row, limit] of [['full',run,3600],['repeat',repeatRun,600]]) {
  const seconds=(Date.parse(row.ended_at)-Date.parse(row.started_at))/1000, h=row.report?.health;
  const healthOK=Number.isInteger(h?.count) && h.count>0 && h.failures===0 &&
    typeof h.max_seconds==='number' && h.max_seconds>=0 && h.max_seconds<=2 &&
    Array.isArray(h.samples) && h.samples.length===h.count &&
    h.samples.every(s=>s.ok===true && typeof s.seconds==='number' && s.seconds>=0 && s.seconds<=2);
  resources.push({label, run:row.id, seconds, limit, health:h, changes:row.report?.counts?.changes,
    timingAndHealthOK:row.status==='succeeded' && Number.isFinite(seconds) && seconds>=0 && seconds<=limit && healthOK});
}
save('A5-timing-health.json', resources);
save('A5-cache-access.json', {full:run.report.cache_access, repeat:repeatRun.report?.cache_access});
```

`timingAndHealthOK` 只表示耗时与健康字段检查；仍须查看原始样本时间是否覆盖导入、重跑变化是否为零，以及宿主采样/挂载/前后元数据，不能独自代表 A5 通过。

`report.cache_access` 留为 `A5-cache-access.json`：与 feature plan §4.5 的 13 个白名单文件逐条核对（导入不得出现 users.json，也不得有列目录操作）；缺失/读失败同时保留异常。结合只读挂载和 T-24 `test_v0_cache_access` 的真实打开审计证明；接口请求另外只读 users.json 做认证。**不为验证 cache 不变而做 find/du/ls 或清单扫描**。

### A6：列表与详情各自 P95（AC-011-3）

全量数据成功导入后，catalog 浏览器同源真实登录态，先从列表取得一个真实 ID。列表与详情分别预热 10 次，再分别单并发顺序请求 100 次；等到完整响应和 JSON 读取完成才计时，保存全部原始耗时及结果。下列只读片段不打印凭证：

```javascript
var first = await getJSON('/api/v1/items?page=1&page_size=50');
if (!first.items?.length) throw new Error('没有真实详情样本，待验');
var detailId = first.items[0].id;
var performanceEvidence = {};
for (const [label, path] of Object.entries({list:'/api/v1/items?page=1&page_size=50', detail:'/api/v1/items/'+detailId})) {
  const warmup=[], samples=[];
  for (let i=0; i<110; i++) {
    const start=performance.now(); let ok=false, error=null;
    try {
      const body=await getJSON(path);
      ok=label==='list' ? Array.isArray(body.items) && body.total>0 : body.id===detailId && Array.isArray(body.images);
      if (!ok) error='响应结构/对象不匹配';
    } catch (_) { error='请求失败（非200、认证、重定向或响应无效）'; }
    (i<10?warmup:samples).push({seconds:(performance.now()-start)/1000, ok, error});
  }
  const valid=warmup.length===10 && samples.length===100 && [...warmup,...samples].every(s=>s.ok);
  const p95=valid ? samples.map(s=>s.seconds).sort((a,b)=>a-b)[94] : null;
  performanceEvidence[label]={path, warmup, samples, p95, passed:valid && p95<=1};
}
save('A6-performance.json', {run:run.id, at:new Date().toISOString(), detailId, results:performanceEvidence});
```

P95 用 100 个成功样本排序后的第 95 个值（nearest-rank）；两类各自 ≤1 秒。失败/401/403/非200/样本不足不排除后再算通过；本段已将任一失败使 p95=null、passed=false。环境中有其他导入或异常活动时记录，不把测试夹具或小数据性能当全量证据。

### A7：随机 20 个可用 v0 卷链接（AC-011-4）

在 catalog 页枚举**已有 API 响应**中的链接，不扫描磁盘、不调用 v0 rescan、不加载影像图块。按卷 URL（去 query 的 origin+pathname）去重后随机抽 20；同时保存不能给链接的原因。遍历详情为单并发，只在获准低峰执行；不足 20 明确待验。

```javascript
var candidates=new Map(), noLinks=[];
for (const item of await allPages('/api/v1/items')) {
  const detail=await getJSON('/api/v1/items/'+item.id);
  for (const image of detail.images) {
    const link=image.v0_link;
    if (!link.url) { noLinks.push({image:image.id, root:image.root, kind:image.kind, reason:link.reason}); continue; }
    const url=new URL(link.url), key=url.origin+url.pathname;
    if (!candidates.has(key)) candidates.set(key, {url:link.url, item:item.id, image:image.id,
      directory:image.relative_path.slice(0,image.relative_path.lastIndexOf('/')),
      filename:image.relative_path.slice(image.relative_path.lastIndexOf('/')+1)});
  }
}
var pool=[...candidates.values()];
// Fisher-Yates，仅随机抽样验收对象，不重做任何编目规则。
for (let i=pool.length-1; i>0; i--) { const j=Math.floor(Math.random()*(i+1)); [pool[i],pool[j]]=[pool[j],pool[i]]; }
save('A7-candidates.json', {run:run.id, available:pool.length, pending:pool.length<20, selected:pool.slice(0,20)});
save('A7-no-links.json', noLinks);
```

由于 8503 与 8504 不同源，**不要从 catalog 页跨源 fetch 或绕过 CORS**。在同一主机已正常登录的 v0 页另开控制台，重新定义上文 `save` / `getJSON`（仍同源 GET），通过文件选择器读取刚保存的候选文件（不读取 cookie）：

```javascript
var selection=await new Promise(resolve=>{
  const input=document.createElement('input'); input.type='file'; input.accept='.json';
  input.onchange=async()=>resolve(JSON.parse(await input.files[0].text())); input.click();
});
var linkResults=[];
for (const candidate of selection.selected) {
  const url=new URL(candidate.url); let passed=false, response=null, error=null;
  try {
    if (url.origin!==location.origin) throw new Error('请在链接对应的同源 v0 页面执行');
    const id=url.pathname.split('/').pop();
    const page=await fetch(url.href, {credentials:'same-origin', cache:'no-store', redirect:'error'});
    await page.text(); // 完整页面响应；单有200不够
    if (page.status!==200) throw new Error('查看器页面失败');
    response=await getJSON('/api/item/'+encodeURIComponent(id));
    const encoded=response.id.replace(/-/g,'+').replace(/_/g,'/');
    const directory=new TextDecoder().decode(Uint8Array.from(atob(encoded+'='.repeat((4-encoded.length%4)%4)),c=>c.charCodeAt(0)));
    passed=response.id===id && directory===candidate.directory &&
      response.category===candidate.directory.split('/')[0] &&
      response.title===candidate.directory.split('/').pop() &&
      response.files.some(f=>f.name===candidate.filename);
  } catch (_) { error='页面/认证/同源/卷响应核查失败，人工调查'; }
  linkResults.push({candidate, passed, response, error});
}
save('A7-link-checks.json', {run:selection.run, available:selection.available, results:linkResults,
  passed:selection.available>=20 && linkResults.length===20 && linkResults.every(r=>r.passed)});
```

实际 v0 `/api/item/{id}` 返回 `id/title/category/files/notes`，没有 catalog 的 `images` 字段。核对 ID 解码出的相对目录及真实文件名，不能只见 HTTP 200（登录页也可能 200）就通过。散放链接 `?file=文件名` 仅提示，不会定位该文件；这里只核对该文件在卷内，不声称自动定位成功。备份、JPG、PSB、未收录、影像缺失/目录不存在、从未有有效索引均应无 URL 且有具体 reason，逐类在 `A7-no-links.json` 留证。

### 证据汇总与待验状态

在外部证据目录写 `A1-A7-summary.json`：每项记录批次、代码版本、开始/结束时间、证据文件、通过/差异/待验及原因；记录人工对象核查结论，不把 compare 的退出码替代全套验收。API 核查结束后重新 GET `/imports` 确认期间没有新批次影响对象状态。所有已解释差异仍保留 expected/actual；未覆盖项明确待验。任何业务缺口回主会话登记任务，修复须重新 Analyze/Converge → 独立 Review → Gate 2 → merge → 获准部署；本机 T-23 完成不代表 T-24～T-26、Gate 2 或 feature 验收完成。
