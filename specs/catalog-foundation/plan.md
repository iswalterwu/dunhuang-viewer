# Feature: catalog-foundation 目录底座 实施计划（plan.md）

> Plan 阶段产物：由 spec.md 生成的设计成果，包含具体实施细节。需求本身在 spec.md，此处不复制。
> 状态（2026-10-27）：第 1 版。配套的 spec 修订（Q-011～Q-014）待 Gate 1 再批准；Checklist 结果见 `checklist.md`。

## 1. 技术方案

- **架构落点**：前后端分离后的第一个后端服务「目录服务」（D-011、D-016、D-018），与 v0 并存、互不依赖；影像查看仍由 v0 提供
- **技术栈**：
  - Python 3.12 + FastAPI + uvicorn（D-018）
  - PostgreSQL 17.4（NAS 已有镜像 `postgres:17.4-alpine3.21`，D-016），驱动 psycopg 3（连接池）
  - 影像事实：tifffile 读 TIFF 标签，Pillow 读 JPEG 尺寸，PSB 头自行解析（只读 26 字节）
  - 测试：pytest + httpx
- **依赖锁定**：`catalog/requirements.lock` 精确锁定；与 v0 共有的库取 v0 当前运行版本（plan.md RK-05：fastapi 0.144.0、starlette 1.8.0、uvicorn 0.54.0、pydantic 2.14.1、tifffile 2026.10.15、numpy 2.5.4、Pillow 13.0.0）；psycopg 在 T-01 取当时的稳定版并锁定
- **对 spec 的落地约定**（Analyze 时复核）：
  1. **v0 卷的对照**（AC-001-1）按 v0 `scan_index` 的同一规则计算：直接含 `.tif` / `.tiff` / `.btf` 的目录为一卷，跳过以 `@`、`#`、`.` 开头的目录，隐藏文件计入
  2. **批次目录**：`188敦煌001`、`188 敦煌002` 两个分类的一级子目录是批次目录，其余分类的一级子目录就是写卷目录；登记在规则表中。新分类没有登记时，按「一级子目录即写卷目录」处理，并在报告中提示
  3. **写卷目录**：批次目录（或分类）下一级的目录；它下面更深的目录按 R-002 规则 2 的词表处理
  4. **v0 `cache/` 的只读白名单**：导入只打开 §4.5 列出的 2026-10-21 执行记录；接口只读取 `users.json` 做认证

## 2. 模块设计

```
catalog/
├── README.md                  # 职责、入口、运行与验证
├── Dockerfile                 # python:3.12-slim + requirements.lock（pip 用清华源，与 v0 一致）
├── requirements.lock
├── docker-compose.yml         # 项目 dunhuang-catalog：catalog-db、catalog-api
├── docker-compose.test.yml    # 测试：tmpfs 上的 PostgreSQL + 测试运行器，跑完即删
├── .env.example               # POSTGRES_PASSWORD 等（catalog/.env 不入库）
├── migrations/                # 0001_init.sql …，按序执行，记入 schema_migrations
├── src/dh_catalog/
│   ├── config.py              # 环境变量与路径
│   ├── db.py                  # 连接池、迁移、事务、咨询锁
│   ├── rules.py               # 规则数据（带版本号）：分类与批次层、子目录词表、编号体系与号段、谱系、许可默认表、出处线索
│   ├── identifiers.py         # 编号解析、规范化、号段校验
│   ├── scan.py                # 只读扫描：目录树、文件清单、附件、未导入清单
│   ├── facts.py               # 影像事实：TIFF 标签、PSB 头、JPEG 尺寸、指纹
│   ├── grouping.py            # 影像 → 写卷（R-002）、合并建议、身份延续（R-003）
│   ├── nlc.py                 # 国图清单：Pressmark、IDP 条目 ID、署名、strips / pages → 画布
│   ├── derivation.py          # 2026-10-21 执行记录 → 合并长卷的派生来源
│   ├── licensing.py           # D-012 默认规则
│   ├── provenance.py          # 出处认定初值与建议
│   ├── importer.py            # 一次导入：暂存 → 计算差异 → 单事务应用 → 报告
│   ├── report.py              # 导入报告、异常清单、基线对照
│   ├── auth.py                # 校验 v0 会话 cookie 与用户表
│   ├── api.py                 # FastAPI：只读接口 + 管理员触发导入
│   └── __main__.py            # 命令行：migrate / import / report / health
├── acceptance/                # NAS 验收脚本 A1–A7（§6.3）与基线 baseline-2026-10-27.json
└── tests/                     # pytest；fixtures/ 生成合成目录树
```

### 2.1 接口

全部接口都要求登录（AC-011-1）；容器健康检查用命令行 `python -m dh_catalog health`，不走 HTTP。

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/v1/items` | 写卷列表；筛选 `system`、`lineage`、`provenance`、`has_anomaly`、`category`、`batch`；分页 `page`、`page_size`（≤ 200） | 登录 |
| GET | `/api/v1/items/{id}` | 写卷详情：编号、影像（事实、谱系、角色、来源目录、派生、IIIF 画布、v0 链接）、来源与许可、出处认定及历史、原始记录、路径历史、母号与分件；已合并的旧 ID 以 308 跳到新 ID | 登录 |
| GET | `/api/v1/resolve?q=` | 按编号查（任一写法、不区分大小写）；母号返回全部分件 | 登录 |
| GET | `/api/v1/images/{id}` | 影像详情：事实、许可、路径历史、变化历史 | 登录 |
| GET | `/api/v1/attachments/{id}` | 附件原文，原样字节 | 登录 |
| GET | `/api/v1/anomalies` | 异常清单；筛选 `run`、`category`；分页 | 登录 |
| GET | `/api/v1/imports`、`/api/v1/imports/{id}` | 导入记录与报告 | 登录 |
| POST | `/api/v1/imports` | 触发一次导入，后台执行；已有导入在跑时返回 409 | 管理员 |

接口文档（OpenAPI）在 `/api/v1/docs`，同样需要登录。

## 3. 数据与存储

PostgreSQL 数据目录在 `/srv/example/pgdata`，不在 v0 的部署目录（git 工作区）里。

| 表 | 主要字段 | 说明 |
|---|---|---|
| `import_run` | id、起止时间、状态、触发方式与人、规则版本、代码版本、各类数量（jsonb）、基线对照（jsonb）、错误 | 每次导入一条（AC-009-4） |
| `item` | id（UUIDv4）、grouping_key、parent_id、状态（active / merged）、merged_into、原始位置、展示策略、出处认定（状态、依据、判定者、时间、建议、建议依据）、线索（jsonb，如「名称所示合装」） | 写卷；`grouping_key` 只给有馆藏号的写卷（如 `pelliot:2504:1`、`nlc:BD00023a`），在 active 写卷中唯一 |
| `identifier` | item_id、体系、原文、规范写法、母号、分件、出处、出处位置、是否主编号、状态（ok / doubtful）、说明 | 编号（R-004）；规范写法与母号建索引 |
| `image` | id（UUIDv4）、根（data / backup）、相对路径、原始文件名、是否隐藏、种类（tiff / psb / jpg）、大小、mtime_ns、指纹、宽、高、通道、色彩模式、位深、dpi、压缩、软件标签、谱系及依据、收藏机构、获取渠道、许可条款、署名、展示策略、对外策略、许可依据、IIIF 画布序号与 ID、v0 卷 ID、状态（present / missing）、首见 / 末见批次、缺失时间 | 影像（R-005、R-006）；present 影像的（根，相对路径）唯一 |
| `image_path_history` | image_id、根、相对路径、起止批次 | 路径历史（AC-003-2） |
| `image_change` | image_id、批次、变化前后（jsonb） | 变化历史（AC-009-3） |
| `item_image` | item_id、image_id、角色、来源目录（set_key）、说明 | 写卷与影像的多对多关系：多编号目录的影像关联多件（AC-002-4），一件写卷可有多套影像（AC-005-5） |
| `derivation` | 派生影像、源影像、方式（拼接 / PSB 转换）、证据（日志文件与行号） | 合并长卷的来源（AC-005-3） |
| `attachment` | item_id、根、相对路径、种类（说明 / manifest / report / index）、原始字节、sha256、解码文本、编码 | 原始附件（AC-001-3、AC-008-2） |
| `provenance_history` | item_id、状态、依据、判定者、时间、批次 | 出处认定历史；判定者以 `rule:` 或 `user:` 开头（AC-007-4） |
| `anomaly` | 批次、类别、对象种类与 ID、路径、原文、说明 | 异常清单（AC-010-1） |
| `excluded` | 批次、根、相对路径、文件或目录、原因 | 未导入清单（AC-001-4） |
| `item_redirect` | 旧 ID、新 ID、批次、原因 | 写卷合并后旧 ID 的去向（R-003） |
| `stage_file` | 批次、根、相对路径、大小、mtime_ns、是否隐藏、种类、事实（jsonb）、指纹 | 暂存表（UNLOGGED），每次导入前清空 |

数据量：影像约 3.6 万行、写卷约 6,000 行，全部在 PostgreSQL 的轻量范围内。

## 4. 关键流程

### 4.1 一次导入

1. 取得咨询锁，没取到就返回「已有导入在跑」；写入 `import_run`（running）
2. **扫描**（只读）：遍历原图目录的 5 个分类与备份目录，跳过以 `@`、`#`、`.` 开头的目录，并把它们记入 `excluded`（`#recycle`、`@eaDir`、国图 `BD00081/.pages` 等）；按扩展名分类文件：`.tif` / `.tiff` / `.btf` / `.psb` 为影像，国图 `pages/*.jpg` 为页图，`*_preview.jpg` 为预览图，`.txt` 与国图三种 JSON 为附件；国图 `tiles/`、`.npy` 及其他文件记入 `excluded`
3. **事实**：（根，相对路径，大小，mtime_ns）与库中记录相同的，沿用已有事实与指纹；否则读取 TIFF 标签 / PSB 头 / JPEG 尺寸，并计算指纹 = 文件大小 + sha256（头 64 KiB + 尾 64 KiB）。读不了的记入异常，继续下一个。结果流式写入 `stage_file`
4. **国图清单与 10-21 执行记录**：解析 `manifest.json` / `report.json` / `index.json`（§4.6），解析白名单内的执行记录（§4.5）
5. **计算差异**：新路径先按指纹匹配本次没出现的旧影像，匹配上的视为改名或移动（写路径历史），否则为新影像；旧影像本次没出现的标为缺失；大小或 mtime 变化的写变化历史
6. **归并**（§4.2）、**规则**（§4.4）：写卷、编号、影像关系、谱系、许可、出处认定初值、合并建议、异常
7. **应用**：以上结果在一个事务中写入正式表；任何一步失败则整批回滚，`import_run` 记为 failed，正式表保持上一次的状态
8. 生成报告与基线对照（`report.py`），写回 `import_run`，释放锁

### 4.2 写卷归并与身份延续（R-002、R-003）

1. **定位写卷目录**：影像所在路径中，批次目录（或分类）下一级的目录就是它的写卷目录；直接放在批次目录里的影像，每个文件自成一个「写卷单元」（AC-002-3）
2. **子目录**：写卷目录下更深的目录按词表处理——分段类 → 角色「分段」，版本类（`HD`，或「本写卷编号 + HD」）→「另一版本」，国图 `pages/` →「页图」；词表外的子目录自成一个写卷单元，并记一条「未知子目录」异常（AC-002-2）
3. **备份分片**：备份目录中的相对路径映射回原图目录，归入对应的写卷单元，角色「已迁出的分片」，记录原位置（AC-002-7）
4. **编号**：每个写卷单元从目录名（散放文件取文件名，国图另取清单 Pressmark）解析出编号（§4.3）
5. **按馆藏号归并**：有馆藏号的写卷单元，按 grouping_key 找到或新建写卷；多个馆藏号的单元关联到每一件，并在写卷上记下合装 / 缀合线索（AC-002-4）；分件写卷记录母号，母号自己也有写卷单元时把 parent_id 指向它（AC-002-5）
6. **没有馆藏号的单元**：沿用身份——它的影像（经指纹延续后）多数已属于哪件写卷，就用那件写卷；否则新建。不自动合并，按以下线索生成合并建议：名称只差「上部 / 下部」「上卷 / 下卷」「紙背」、同一分享者自编号、同一《开宝藏》帙号（AC-002-6）
7. **合并与拆分**：规则版本变化导致两件写卷的影像归到一起时，保留较早的 ID，另一件标为 merged 并写入 `item_redirect`；拆分时原 ID 留给影像较多的一侧。ID 从不复用或删除（R-003）

### 4.3 编号解析与校验（R-004）

| 体系 | 识别的写法（例） | 规范写法 | 校验与用途 |
|---|---|---|---|
| 伯希和汉文写卷号 | `P2602`、`P.2033`、`P. 0901`、`p.2731`、`Pelliot chinois 2002` | `P.2602` | 号段 2001–4099、4500–5043、5522–6038，号段外标 doubtful 并记异常；馆藏号，可作主编号、可归并 |
| 伯希和分件 | `-1`、`-1Pièce`、`-P2`、`A` / `B` / `a` | `P.2504-1`、`P.2842-2`、`P.2222A` | 母号 = 不带分件的号 |
| 多号 | `P3012+5564`、`P2661(+3735)` | 各成一号 | 第二个号省略「P」也识别 |
| 国图 BD 号 | `BD00001`、`BD00023a` | 以清单 Pressmark 的写法为准 | 与 Pressmark 不一致记异常；查询不区分大小写；馆藏号 |
| 分享者自编号 | `WB 15`、`WB15`、`WA9` | `WB 15`、`WA 9` | 不作主编号，不作归并依据，只提合并建议 |
| 《开宝藏》帙号 | 「令字」「存字」「李字」等 | `令` 等 | 只在目录名或同目录 PSB 文件名含「開寶藏 / 开宝藏」，或目录名以「敦煌藏經洞 + 序号」开头时识别（避免把「小字法华经」的「小字」误认作帙号）；不作主编号与归并依据 |
| IDP 条目 ID | 清单 `id` 末段 | 原样 | 外部编号 |

主编号：每件写卷最多一个，只取 ok 状态的馆藏号；母号与分件各自为主编号（AC-004-5）。

### 4.4 规则表（`rules.py`，带版本号，写入各条依据）

**角色**：写卷单元只有一个影像 →「单幅整卷」；多个 → 各为「分段」；文件名以「合并长卷」开头 →「合并长卷」；`.psb` →「PSB 源文件」；子目录与备份按 §4.2。

**谱系**（逐个文件，AC-005-2）：

| 条件（按顺序） | 谱系 |
|---|---|
| 属于国图分类 | 国图 IDP 下载 |
| 文件名以「合并长卷」开头，或出现在 10-21 执行记录的输出中 | 本地合成 |
| 文件名为 `native.tif` / `native(n).tif`，且没有软件标签 | BnF 原图 |
| 有软件标签（Photoshop 等） | 第三方加工图 |
| 其他 | 未判定（记异常） |

**来源与许可**（D-012，AC-006-1～3）：

| 谱系 | 收藏机构 | 获取渠道 | 许可 | 署名 | 展示策略 | 对外策略 |
|---|---|---|---|---|---|---|
| 国图 IDP 下载 | 中国国家图书馆 | IDP IIIF 下载（2026-10-21 起） | IDP：个人或非商业复用 | 清单 requiredStatement（The National Library of China） | 登录墙内可展示 | 链接 IDP |
| BnF 原图 | 法国国家图书馆 | 第三方资料接收（接收事件 A） | Gallica：非商业免费复用，注明出处 | Source gallica.bnf.fr / BnF | 登录墙内可展示 | 链接 Gallica / IDP |
| 第三方加工图 | 有伯希和号时为「法国国家图书馆（第三方加工）」，否则未知 | 第三方资料接收（接收事件 A） | 未知（第三方衍生） | — | 仅供研究使用 | 不对外 |
| 本地合成 | 继承源影像 | 本地生成（2026-10-21 脚本或拼接工作台） | 源影像中最严格的一项；来源不明时为未知 | 同源影像 | 同源影像中最严格的一项 | 同左 |
| 未判定 | 未知 | 按所在目录推断（转存或下载） | 未知 | — | 仅供研究使用 | 不对外 |

展示策略从严到宽：仅供研究使用 → 登录墙内可展示；写卷取其全部影像中最严格的一项（AC-006-2）。

**出处认定**（AC-007-1～4）：

1. 已有判定者为 `user:` 的结论 → 保留不动
2. 有 ok 状态的伯希和号或 BD 号 →「已确认」，依据写明编号体系
3. 其他 →「待核」；命中以下线索时附「建议：非敦煌」与依据：目录名或同目录 PSB 名含「開寶藏 / 开宝藏」或以「敦煌藏經洞 + 序号」开头、识别出《开宝藏》帙号；题名含「清光绪 / 清光緒」「尖山刻经 / 尖山刻經」「室町」「竹生島経 / 竹生岛经」「紫紙金字 / 紫纸金字」「大橋家来翰集」
4. 规则永远不直接给出「非敦煌」

### 4.5 合并长卷的派生来源（AC-005-3）

只打开 v0 `cache/` 根目录下的这些文件（按名字直接打开，不列目录）：`merge_all.log`、`merge_smart_all.log`、`merge_extra.log`、`psb_convert.log`、`psb_convert_all.log`、`psb_convert_7.log`、`psb_conv_wb5back.log`、`seg_move_log.txt`、`samefolder_move_log.txt`、`extra_move_log.txt`、`seg_move_plan.json`、`samefolder_plan.json`、`validated_moves.json`。

- 拼接日志：「开始: <相对目录>」之后列出的分片名 → 源分片（迁出后在备份目录的镜像位置），「完成: …/合并长卷.tif」→ 派生影像
- PSB 转换日志：「转换: <相对目录>」与「PSBNAME」→ 源 PSB，「已替换合并长卷.tif」→ 覆盖之前的拼接结果
- 同一个合并长卷以时间上最后一次成功的操作为准；证据记录日志文件名与行号；对不上的记「派生来源不明」异常

### 4.6 国图清单（AC-004-3、AC-005-4）

- `manifest.json`：Pressmark → BD 号校验；`id` 末段 → IDP 条目 ID；`requiredStatement` → 署名；`items[n].id` → 画布 ID
- `report.json`：`strips[i].file` → 本地 TIFF 与画布序号 `strips[i].index`；`strips` 不是列表（如 0）时没有分段
- `pages/NNNN_WxH.jpg`：文件名前缀 NNNN → 画布序号
- 三份 JSON 都原样存为附件

### 4.7 认证（AC-011-1）

- 读取 cookie `dh_session`，按 v0 的格式校验：base64url(`用户|过期时间|HMAC-SHA256(AUTH_SECRET, "用户|过期时间")`)，未过期，且用户在 `users.json` 中（architecture.md §7）
- 管理员 = `users.json` 中 `admin: true` 的用户
- `users.json` 按修改时间缓存；`AUTH_SECRET` 缺失时所有请求返回 503（fail-closed）
- cookie 不区分端口，在 8503 登录 v0 后即可访问 8504

### 4.8 部署与运行（D-018）

| 服务（容器） | 镜像 | 内存（= memswap） | 挂载 | 其他 |
|---|---|---|---|---|
| `catalog-db` | `postgres:17.4-alpine3.21` | 384m | pgdata → `/srv/example/pgdata` | 不对外暴露端口；`shared_buffers=64MB`、`max_connections=20`、`work_mem=4MB`；healthcheck `pg_isready` |
| `catalog-api` | 本仓库 `catalog/Dockerfile` | 512m | `/srv/example/data:/data:ro`、`/srv/example/backup:/backup:ro`、`/srv/example/cache:/v0cache:ro` | 端口 8504→8000；`env_file`：`../.env`（`AUTH_SECRET`）与 `./.env`（数据库密码）；以 root 运行（`users.json` 为 root 600）；导入在本容器的后台线程中执行，受 512m 上限约束 |

- 启动：`cd /srv/example/viewer/catalog && /usr/local/bin/docker-compose -p dunhuang-catalog up -d --build`（只作用于本项目，不影响 v0）
- 首次导入：管理员 `POST /api/v1/imports`，或 `docker-compose -p dunhuang-catalog exec catalog-api python -m dh_catalog import`
- 备份：每次导入成功后 `pg_dump` 到 `/srv/example/catalog-backups/`，保留最近 7 份（保护以后的人工结论）
- 上线前置：NAS `MemAvailable` ≥ 2 GB；首次全量导入放在低峰时段

## 5. 验收对应

| AC | 实现位置 | 验证方式 |
|---|---|---|
| AC-001-1 | `scan.py`（v0 卷规则）、`report.py` | `tests/test_import.py::test_every_v0_volume_maps_to_item`；NAS A1 |
| AC-001-2 | `scan.py`、`importer.py` | `test_scan.py::test_image_inventory_complete`；NAS A2（磁盘计数对照） |
| AC-001-3 | `scan.py`、`nlc.py`、`attachment` 表 | `test_import.py::test_attachments_imported` |
| AC-001-4 | `scan.py`、`excluded` 表 | `test_scan.py::test_excluded_listed_with_reason` |
| AC-002-1 | `grouping.py` §4.2.5 | `test_grouping.py::test_catalog_number_merged_across_lineages` |
| AC-002-2 | `grouping.py` §4.2.2、`rules.py` 词表 | `test_grouping.py::test_subdir_vocabulary_and_unknown_subdir` |
| AC-002-3 | `grouping.py` §4.2.1 | `test_grouping.py::test_loose_files_are_items` |
| AC-002-4 | `identifiers.py`、`grouping.py` | `test_grouping.py::test_multi_number_dirs_share_images` |
| AC-002-5 | `identifiers.py`、`grouping.py` | `test_grouping.py::test_parts_and_parent` |
| AC-002-6 | `grouping.py` §4.2.6 | `test_grouping.py::test_no_catalog_number_suggestions_only` |
| AC-002-7 | `grouping.py` §4.2.3 | `test_grouping.py::test_backup_fragments_linked`；NAS A2 |
| AC-003-1 | `importer.py` | `test_identity.py::test_reimport_keeps_ids` |
| AC-003-2 | `importer.py` 指纹延续、`image_path_history` | `test_identity.py::test_rename_and_move_keep_ids` |
| AC-003-3 | UUIDv4 生成 | `test_identity.py::test_ids_not_path_derived` |
| AC-004-1 | `identifiers.py` | `test_identifiers.py::test_pelliot_variants` |
| AC-004-2 | `identifiers.py`、`rules.py` 号段 | `test_identifiers.py::test_pelliot_ranges` |
| AC-004-3 | `nlc.py` | `test_nlc.py::test_pressmark_and_idp_id` |
| AC-004-4 | `identifiers.py` | `test_identifiers.py::test_sharer_and_zhihao_systems` |
| AC-004-5 | `identifiers.py` | `test_identifiers.py::test_primary_only_catalog_numbers` |
| AC-005-1 | `facts.py` | `test_facts.py::test_tiff_facts_and_unreadable` |
| AC-005-2 | `rules.py` 谱系、`report.py` 目录级汇总 | `test_lineage.py::test_lineage_rules`；NAS A3（447 / 499 / 12 对照） |
| AC-005-3 | `derivation.py` | `test_derivation.py::test_stitch_and_psb_logs`（用真实日志片段做夹具） |
| AC-005-4 | `nlc.py` | `test_nlc.py::test_strip_canvas_mapping`；NAS A4 |
| AC-005-5 | `item_image.set_key` | `test_grouping.py::test_image_sets_distinguishable` |
| AC-006-1 | `licensing.py` | `test_licensing.py::test_default_rules_table` |
| AC-006-2 | `licensing.py` | `test_licensing.py::test_item_policy_most_restrictive` |
| AC-006-3 | `licensing.py` | `test_licensing.py::test_channel_is_specific_event` |
| AC-007-1 | `provenance.py` | `test_provenance.py::test_every_item_has_provenance` |
| AC-007-2 | `provenance.py` | `test_provenance.py::test_confirmed_by_catalog_number` |
| AC-007-3 | `provenance.py`、`rules.py` 线索 | `test_provenance.py::test_non_dunhuang_suggestions_only` |
| AC-007-4 | `provenance.py` 第 1 条 | `test_provenance.py::test_human_conclusion_survives_reimport` |
| AC-008-1 | `scan.py`（原样保存名称） | `test_import.py::test_raw_names_verbatim` |
| AC-008-2 | `attachment` 表 | `test_import.py::test_attachment_raw_roundtrip` |
| AC-009-1 | `importer.py` §4.1.5 | `test_changes.py::test_new_files_appear` |
| AC-009-2 | `importer.py` §4.1.5 | `test_changes.py::test_missing_marked_not_deleted` |
| AC-009-3 | `importer.py`、`image_change` | `test_changes.py::test_changed_file_history` |
| AC-009-4 | `importer.py`、`import_run` | `test_changes.py::test_import_run_record` |
| AC-010-1 | `report.py`、`anomaly` 表 | `test_report.py::test_anomaly_categories` |
| AC-010-2 | `report.py`、`acceptance/baseline-2026-10-27.json` | NAS A2（基线对照表，差异逐项说明写入 review.md） |
| AC-011-1 | `auth.py`、`api.py` | `test_api.py::test_auth_required_and_admin_import` |
| AC-011-2 | `api.py` `/resolve`、`identifiers.py` | `test_api.py::test_resolve_variants` |
| AC-011-3 | `api.py`、索引 | `test_api.py::test_filters_and_pagination`；NAS A6（P95） |
| AC-011-4 | `api.py`（v0 卷 ID = base64url(相对目录)） | `test_api.py::test_v0_links`；NAS A7（抽查链接） |
| AC-011-5 | `api.py` | `test_api.py::test_no_mutating_routes`（检查路由表） |
| AC-012-1 | 只读挂载、`scan.py` | NAS A5：挂载均为只读（`docker inspect`），原图与备份目录前后快照一致 |
| AC-012-2 | `derivation.py` 白名单 | `test_scan.py::test_v0_cache_not_traversed`（记录文件访问，确认只打开白名单文件） |
| AC-012-3 | 容器 512m 上限、流式处理 | NAS A5：导入完成且内存峰值 ≤ 512 MiB；期间 v0 `/api/health` 全部正常 |
| AC-012-4 | 增量事实与指纹 | NAS A5：全量 ≤ 1 小时、无变化重跑 ≤ 10 分钟 |

## 6. 测试与验证

### 6.1 本机（Windows，Python 3.14）

不依赖数据库的单元测试：编号、规则、扫描、影像事实、派生解析、许可、出处、认证签名。用于快速反馈；运行时以容器内的 Python 3.12 为准。

### 6.2 NAS 临时测试环境（需你许可后才运行）

`docker-compose.test.yml`：tmpfs 上的 PostgreSQL（256m）+ 测试运行器（512m），运行完整的 pytest（含数据库与接口测试），结束后 `down -v` 删除。不挂载原图目录，只用合成数据。

### 6.3 NAS 验收（部署后，需你许可）

| 编号 | 内容 |
|---|---|
| A1 | v0 卷与写卷的对照（差为 0） |
| A2 | 基线对照：各类数量与 spec AC-010-2 的 2026-10-27 数字逐项比较 |
| A3 | 谱系目录级汇总与 447 / 499 / 12 比较 |
| A4 | 国图 TIFF → 画布对应率 |
| A5 | 安全与资源：挂载只读、原图与备份目录前后快照（路径、大小、mtime）、导入期间每 5 秒采样内存与 v0 健康、导入耗时 |
| A6 | 200 次随机列表与详情查询的 P95 |
| A7 | 随机抽 20 个 v0 链接，确认 v0 返回对应的卷 |

## 7. 风险与回滚

| 风险 | 应对 |
|---|---|
| NAS 内存紧张（plan.md RK-01） | 两个容器硬上限合计 896m；上线前确认可用内存 ≥ 2 GB；必要时下调 `shared_buffers` |
| 首次全量导入与 v0 争用磁盘 | 指纹只读头尾各 64 KiB；增量跳过未变文件；导入期间轮询 v0 健康，连续失败即暂停导入 |
| 2026-10-21 执行记录格式不规整 | 解析不到的记异常（AC-005-3 允许），不臆测 |
| v0 会话格式变化导致认证失效 | 测试锁定 v0 的签名格式；v0 修改 cookie 时同步（D-018） |
| 规则误判（谱系、出处、归并） | 规则带版本号写入依据；人工结论不被覆盖；异常与合并建议交人工复核 |
| 数据库损坏或丢失 | 目录可由原始材料重新导入；每次导入后 `pg_dump`，保留 7 份 |
| 回滚 | `docker-compose -p dunhuang-catalog down`；删除 `pgdata` 即完全移除；v0 没有任何改动 |

## 8. 实施里程碑（供 Tasks 拆分）

| 里程碑 | 内容 |
|---|---|
| M1 骨架 | 目录与锁定依赖、配置、数据库连接与迁移、测试夹具生成器 |
| M2 扫描与事实 | `scan.py`、`facts.py`、暂存 |
| M3 编号与归并 | `identifiers.py`、`grouping.py`、身份延续与重定向 |
| M4 规则与外部记录 | `nlc.py`、`derivation.py`、`licensing.py`、`provenance.py` |
| M5 导入与报告 | `importer.py`、`report.py`、异常与基线对照 |
| M6 接口 | `auth.py`、`api.py` |
| M7 部署与验收 | compose、NAS 测试、部署、A1–A7、备份 |
