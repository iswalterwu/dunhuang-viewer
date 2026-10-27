# dunhuang-viewer 总方案（plan.md）

> 本文档是项目方案的总入口：背景目标、数据现状、决策记录、文档体系、目录结构、路线图、待确认决策、风险与已知问题。
> 架构细节见 `architecture.md`，设计理念见 `designUI.md`。变更本文件内容即变更项目方案，需同步相关文档。
> 2026-10-27 全面梳理：逐条对照代码、部署配置与 部署环境 实况核实，证据来源写在各条目里。

## 1. 背景与目标

### 1.1 背景

NAS（设备实例非公开）的 `/srv/example/data` 下存放敦煌遗书高清扫描件，按一级目录分为 5 类（§1.3）。单卷从几十 MB 到数 GB 不等，
多为未压缩 TIFF，也有 CMYK、16 位、超长卷与分段扫描（`1.tif`、`2.tif`…）。这类文件在普通设备上无法整卷打开，在手机/平板上更不可能；
在受限内存的 NAS 上整卷解码，还曾把整台 NAS 拖进交换（2026-10-18 事故，D-005）。

### 1.2 目标

与 `app.py` 文档字符串一致：

1. 直接读取 NAS 本机磁盘上的 TIFF，不拷贝、不全量转码；
2. 首次打开某卷时在 NAS 本地生成 DZI 缩放图块（进度可查），之后秒开；
3. 电脑/手机/平板通过网页缩放浏览，只下载小图块；
4. 提供元数据、`说明.txt`、原图下载、按卷分段浏览；
5. 在任何负载下都不让查看器拖垮 NAS（D-005）。

### 1.3 数据现状（2026-10-27 盘点；数值会变化，以 `/api/index` 为准）

| 分类 | TIFF | 体积 | 说明 |
|---|---|---|---|
| `188敦煌001` | 9,747 | 437.4 GB | 含 12 个 `合并长卷.tif`（各 3.3–4.5 GB，均在 `2018年/` 下）与 16 个 PSB |
| `188 敦煌002` | 171 | 61.4 GB | |
| `敦煌003` | 291 | 68.9 GB | |
| `敦煌004` | 124 | 20.6 GB | |
| `中国国博馆藏` | 21,788 | 287.0 GB | 5,140 个卷目录，每卷附 `manifest.json` / `report.json`；由外部下载器写入（§1.4） |
| **合计** | **32,121** | **875.3 GB** | `README-部署.md` 记录的 11,246 个 / 4 类是 2026-10-20 的状态 |

查看器只索引 `.tif` / `.tiff` / `.btf`，由此带来三点：

- `中国国博馆藏` 有 79 个卷目录只有 JPG 页图（`pages/*.jpg`、`*_scroll_preview.jpg`），在画廊里看不到；该分类共 2,997 个 JPG
- 16 个 PSB（0.7–4.9 GB）不被读取：12 个已转为所在卷的 `合并长卷.tif`，另 4 个所在卷只展示分段 TIFF
- 以 `.` 开头的**目录**被跳过，以 `.` 开头的**文件**不会：40 个隐藏 TIFF 文件照常索引展示

### 1.4 数据沿革与写入方

原图目录不是一份只读的原始数据，而是经过整理、仍在增长的工作集。已知写入方：

| 时间 | 写入方 | 内容 | 记录位置 |
|---|---|---|---|
| 2026-10-21 | 宿主机一次性脚本（root 执行） | ① 父目录已有整卷主图的 91 个分片目录、同目录分片 204 个文件（43.5 GB）、补充 11 个目录 / 15 个文件，迁出到 `/srv/example/backup`（现有 925 个 TIFF、260 GB）；② 按 PSB 参考图确定分片顺序拼接 `合并长卷.tif`，其中 7 个随后被 PSB 直接转换的结果替换；③ 另有原地修补 BigTIFF 头 BitsPerSample 标签的脚本 `fix_bigtiff.py`（无执行记录） | `cache/` 根目录的脚本、`*_plan.json`、`*_log.txt`、`*.log`（未入库） |
| 2026-10-21 起 | IDP 下载器（不属本仓库） | `中国国博馆藏` 的卷目录；最近一次写入 2026-10-26；机构下载标签与日期保留，私人下载任务与现场运行状态非公开 | 下载执行记录非公开保全 |
| 持续 | 本仓库拼接工作台（D-008） | 卷目录下的 `合并长卷.tif` | `cache/stitch_plans/`（当前为空）；旧通道日志 `cache/stitch_apply.log` |

10-21 测试用的 `_stitch_test/` 卷已从原图目录删除，但图块仍在缓存（KI-06）。原图目录的写入如何治理，见 PD-02。

## 2. 产品定位与核心循环

- **用户**：所有者本人及其授权用户（登录墙 + 用户管理后台；账户实例与数量非公开）
- **访问通道**：局域网 / Tailscale 地址由部署方提供；可选公网入口须有访问控制与登录墙，私人拓扑及端口非公开（architecture.md §1）
- **核心循环**：原图 TIFF → 索引 + DZI 图块 / 缩略图（`cache/`）→ FastAPI → 浏览器（OpenSeadragon）
- **功能面**：画廊（分类、搜索、懒加载缩略图）· 查看器（缩放、分段切换、元数据与说明、原图下载）· 拼接工作台（分段手动拼成整卷）· 用户管理

## 3. 决策记录（含取舍）

D-001 ～ D-008 为 2026-10-27 追认登记的既有决策（决策本身早于登记日，依据为当时的代码、部署与注释）；D-009 为当日新决策。

| 编号 | 决策 | 备选 | 取舍理由 |
|---|---|---|---|
| D-001 | 部署形态：NAS 本机 Docker Compose 服务，直读原图 | 未记录 | 原图为数百 GB 级且就在 NAS 上，拷贝/转码代价不可接受；浏览器即客户端 |
| D-002 | 后端：Python + FastAPI + uvicorn，单文件 `app.py` | 未记录 | 图像生态（pyvips/tifffile/Pillow/numpy）在 Python；单体便于在 NAS 上维护 |
| D-003 | 图像管线：libvips 流式 + DZI 图块；tifffile 流式读；Pillow 兜底 | Pillow 整卷解码（保留为兜底） | 受限内存下只有流式解码可行；DZI 让浏览器只拉需要的图块 |
| D-004 | 前端：原生 HTML/CSS/JS + OpenSeadragon，无构建步骤；`static/` 运行时挂载 | 未记录 | 页面少、无需框架；挂载后改页面无需重建镜像 |
| D-005 | 内存安全红线：容器硬上限禁 swap、单线程解码、内存守卫、超大卷降级预览 | 不设限整卷解码（导致 2026-10-18 事故） | NAS 与其他工作负载共享内存，超限只能杀查看器，不能拖垮 NAS |
| D-006 | 图块生成三通道：在线按需 + `pyramid-builder` 全量 + `pyramid-huge` 超巨卷 | 仅在线按需（首次打开慢） | 预先生成让大部分卷秒开；超巨卷隔离到更高内存上限的独立容器 |
| D-007 | 认证：环境变量引导管理员 + `users.json`（pbkdf2）+ HMAC 会话 cookie + CSRF + 登录限流 | 无认证、仅内网（旧状态） | 自公网通道开通后，登录墙是唯一屏障 |
| D-008 | 本仓库代码写原图目录的唯一途径：拼接输出 `合并长卷.tif` 写回卷目录（查看器以 rw 挂载原图） | `cache/stitch_out/` 输出 + 宿主机 `stitch_apply.py` 搬运（旧通道，疑似遗留） | 拼接结果需作为一段参与浏览与图块生成 |
| D-009 | 代码与部署通道：GitHub 私有仓库为权威；NAS 部署目录为 git 仓库（updateInstead）；本机工作副本推送两端 | NAS 直推 GitHub（NAS 无该仓库的 deploy key） | 部署目录原无版本管理；本机已有 GitHub 凭据 |

## 4. 文档体系规划

原则：**单一作者、机读优先、决策留痕**。

```
docs/
├── plan.md            # 本文档：总方案与路线图（唯一"当前状态"入口）
├── architecture.md    # 系统架构：组件、ID/缓存布局、图块管线、拼接、认证、部署、内存红线
├── designUI.md        # 全局设计理念：配色令牌、页面形态、查看器交互约定
└── decisions/         # ADR：YYYYMMDD-<slug>.md，编号 D-XXX；先登记再实现
specs/<feature>/       # 功能规格目录：每功能一份 spec/plan/tasks/review（唯一实施入口）
templates/             # spec-driven 工作流模板（spec/plan/tasks/checklist/review 的模板权威）
README-部署.md          # 部署与日常运维操作手册（人读）
```

文档纪律：

- 每份规范只有一个权威作者位置；README 只导航不复制数值（防双份漂移）
- 所有"为什么"写进 ADR 或规范条目，不散落在会话里
- 方案变更先改 docs 再改代码；实现与 docs 冲突以 docs 为准
- **功能开发一律走 spec-driven 工作流**（AGENTS.md §2）：Constitution → Spec → Clarify → 【Gate 1】 → Plan → Checklist → Tasks → Analyze → Implement → Converge → Review → 【Gate 2】 → Handoff；规格与实施产物在 `specs/<feature>/`
- 运行参数的权威是 `docker-compose.yml`（环境变量）与 `app.py` / `pyramid_worker.py`（默认值）；文档引用参数名，不另抄数值
- 本文的盘点数字（§1.3、§1.4、§10）都标明日期，只作为当日快照

## 5. 目录结构

```
dunhuang-viewer/
├── AGENTS.md              # agent 工作手册（本仓库上下文入口）
├── README.md              # 项目简介（人读）
├── README-部署.md          # 部署与日常运维（人读）
├── docs/                  # 设计文档（见 §4）
├── specs/                 # 功能规格目录（每 feature 一份：spec/plan/tasks/review）
├── templates/             # spec-driven 工作流模板
├── app.py                 # FastAPI 单体：索引、图块、缩略图、局部区域、认证、用户管理、拼接工作台
├── pyramid_worker.py      # 后台 DZI 生成器（pyramid-builder / pyramid-huge 两个容器共用）
├── stitch_apply.py        # 宿主机脚本：处理 cache/stitch_out/ 旧拼接输出队列
├── auto_huge_daemon.sh    # 宿主机守护循环（每 20 秒：stitch_apply.py + 按需拉起 pyramid-huge）
├── auto_huge_boot.sh      # 开机钩子（部署方安装拷贝；位置非公开）
├── auto_huge.sh           # 单次检查版本（当时现场未发现调用，已被 auto_huge_daemon.sh 取代；钩子现场非公开）
├── static/                # 前端：gallery / viewer / stitch 页面 + style.css + openseadragon.min.js
├── Dockerfile             # python:3.12-slim + libvips42（apt 阿里云源、pip 清华源）
├── docker-compose.yml     # 三个服务：dunhuang-viewer / pyramid-builder / pyramid-huge
└── requirements.txt
```

运行时产物（不入库，见 `.gitignore`）：`.env`、`build.log`、`cache/`（图块、缩略图、拼接方案与预览、用户表、生成状态与日志；
根目录另有 2026-10-21 数据整理的脚本与记录，§1.4）。

## 6. 架构总览

三个容器共用一个镜像：**`dunhuang-viewer`**（FastAPI 服务，对外 8503）、**`pyramid-builder`**（全量图块）、**`pyramid-huge`**（超巨卷图块），
外加宿主机上的 **`auto_huge_daemon.sh`** 守护循环。原图目录只读挂载给两个生成器，读写挂载给查看器（仅拼接写入，D-008）；三者共享 `cache/`。
公网入口须提供 HTTPS 与可信代理头；私人网关组件链非公开。组件职责与数据流见 `architecture.md`。

## 7. 扩展点

### 7.1 访问端

- 浏览器即客户端；900px 以下查看器侧栏改为右侧滑出抽屉、拼接工作台隐藏侧栏；触控支持双指缩放（designUI.md §5）
- 公网入口与 TLS 配置由部署方非公开管理，不在本仓库（RK-07）

### 7.2 数据

- 新增分类 = 在 `/srv/example/data` 下新建一级目录（以 `@`、`#`、`.` 开头的目录被忽略）；画廊「重新扫描」（`POST /api/rescan`）后可见
- 新增卷的图块：首次打开时在线生成（超大卷只有预览分辨率）；或手动 `docker start dunhuang-pyramid-builder` 批量补齐（生成器跑完即退出，不会自动重跑）。
  `中国国博馆藏` 基本没有预生成图块（生成器最后一次全量是 2026-10-21，见 PD-04）
- 只有 JPG 页图的卷需要新的数据模型（PD-03）

### 7.3 图像格式

- 流式路径（预览、缩略图、局部区域）只覆盖未压缩、CONTIG、uint8/uint16 的 TIFF；压缩格式的超大卷目前只能下载原图
- 扩展位置：`app.py` 的 `_stream_preview_plain_tiff`、`_fast_thumb_plain_tiff`、`read_region_plain_tiff`

## 8. 路线图

| 阶段 | 内容 | 状态 |
|---|---|---|
| **Phase 0** | 文档体系与仓库骨架：AGENTS.md、docs 三件套、ADR 追认登记（D-001 ～ D-009）、spec-driven 工作流与模板（templates/、specs/）；2026-10-27 全面梳理本文 | 已完成（GitHub 与 NAS 均已推送）。基线：运行中的 `app.py`、`pyramid_worker.py` 与仓库逐字节一致 |
| **Phase 1 起** | 按 §9.2 的建议顺序，经 §9.1 决策确认后逐个立项 | 待确认 |

## 9. 待确认决策

### 9.1 决策项（确认后登记 ADR）

| 编号 | 问题 | 选项 | 建议 |
|---|---|---|---|
| PD-01 | 拼接工作台权限：任何已登录用户都能生成整卷（覆盖原图目录里的 `合并长卷.tif`），也能触发重新扫描 | A 仅管理员 · B 维持现状 | A |
| PD-02 | 原图目录写入治理：实际有三类写入方（§1.4） | A 承认是整理中的工作集：批量整理一律走「备份 → 计划文件 → 执行日志」，脚本与记录入库 · B 原图目录只读，整理改在副本上做 | A |
| PD-03 | 看不到的数据：79 个只有 JPG 页图的卷；40 个隐藏 TIFF 文件该不该展示 | JPG 卷：A 页图作为分段展示 · B 转成 TIFF · C 维持不展示；隐藏文件：展示 / 跳过 | 需你决定（产品范围） |
| PD-04 | `中国国博馆藏` 21,788 个 TIFF 的图块：预生成还是按需 | A 先修 KI-01，再在低峰跑 `pyramid-builder`（估算 2–6 小时、约 18 GB、约 160 万个图块文件¹）· B 维持按需 | A |
| PD-05 | 自动化测试 | A 建 `tests/`（pytest + 合成小 TIFF），作为工作流各任务的验证命令 · B 维持 `py_compile` | A |
| PD-06 | 依赖锁定：`requirements.txt` 只有范围约束，重建镜像会顺带升级依赖 | A 以当前运行版本（RK-05）精确锁定 · B 维持范围 | A，且须在第一次重建镜像之前完成 |
| PD-07 | 旧拼接通道：`cache/stitch_out/` 已空，`app.py` 不再写入 | A 下线（守护循环不再调用 `stitch_apply.py`）· B 保留 | A |
| PD-08 | 视觉统一（designUI.md §7） | A 统一到主界面玻璃风 · B 统一到暖色纸底 · C 维持 | 需你决定（审美） |
| PD-09 | 容器与宿主日志时区不一致（KI-08）；私人时区非公开 | A 容器与 NAS 一致 · B 维持 | A |

¹ 依据 10-21 全量一轮：3.07 小时处理 535.5 GB / 10,463 个文件，产出 32.87 GB；按体积折算约 1.6 小时，按文件数约 6.4 小时；图块按现有缓存平均每 GB 约 8.6 万个文件。

### 9.2 建议顺序与 feature 拆分（待确认）

| 顺序 | feature（`specs/<feature>/`） | 覆盖 | 理由 |
|---|---|---|---|
| 0 | 不立项（纯文档修订） | KI-04 | 现文档会误导运维，例如部署命令会同时拉起两个生成器 |
| 1 | `deps-lock` | PD-06、PD-09 | 之后凡是改 `app.py` 的 feature 都要重建镜像，必须先锁依赖；时区随同一次重建生效 |
| 2 | `tests-foundation` | PD-05、RK-04、KI-07 | 为后续 feature 提供验证命令；抽出共享的 ID 映射与扫描规则 |
| 3 | `cache-maintenance` | KI-01、KI-06 | 消除每次在线生成后的全量遍历；完成后执行 PD-04 的批量预生成（运维操作，不立项） |
| 4 | `stitch-hardening` | PD-01、KI-02、KI-03、KI-05 | 拼接是本仓库唯一写原图的代码路径：权限、并发与缓存失效一起修 |
| 5 | `data-governance` | PD-02、PD-07 | 固化整理流程、10-21 脚本与记录入库、下线旧通道 |
| 6 | 产品功能（逐个立项） | PD-03、超大卷局部高清（接入 `/api/region`，KI-09）、压缩超大卷流式解码（§7.3）、PD-08 | 先确认产品范围 |

## 10. 风险、约束与已知问题

### 10.1 风险与约束

| 编号 | 风险 / 约束 | 现状与证据（2026-10-27） | 应对 |
|---|---|---|---|
| RK-01 | 内存紧张 | 现场资源压力及历史交换事故已确认；设备规格、容器数量与即时资源值非公开 | D-005 红线；新解码路径必须过内存守卫；批量生成放低峰 |
| RK-02 | 原图可写且有多个写入方 | 查看器 `/data:rw`；§1.4 | PD-02；本仓库代码只允许 D-008 一条写入路径 |
| RK-03 | 公网暴露 | 登录墙是唯一屏障，三项 `AUTH_*` 缺一即全站匿名（实际配置非公开）。公网链路上 nginx 用 `$remote_addr` 覆盖 `X-Real-IP` 并设置 `X-Forwarded-Proto`，限流拿到真实 IP，会话 cookie 带 `secure`；直连 8503（局域网 / Tailscale）时这两个头可被伪造 | 改动 `.env` 后立即验证登录墙；由部署方限制后端直连，私人端口与防火墙现场非公开 |
| RK-04 | ID 映射与扫描规则多处重复 | `app.py`、`pyramid_worker.py`、`stitch_apply.py` 各一份；扫描规则已出现分歧（KI-07） | 抽成共享模块（`tests-foundation`） |
| RK-05 | 依赖未锁定 | 运行基线（镜像 2026-10-21 构建）：Python 3.12.15、libvips 8.16.1、fastapi 0.144.0、starlette 1.8.0、uvicorn 0.54.0、pydantic 2.14.1、tifffile 2026.10.15、imagecodecs 2026.10.10、numpy 2.5.4、Pillow 13.0.0、pyvips 3.2.0 | PD-06 |
| RK-06 | 无自动化测试 | 只能靠 `py_compile` 与手动冒烟；本机 Python 3.14 与容器 3.12.15 不一致 | PD-05 |
| RK-07 | 运行依赖不在本仓库 | 部署 `.env`、开机钩子（`auto_huge_boot.sh` 的拷贝）、可选入口与 TLS 配置由部署方非公开管理 | 改动时手动同步，并更新 architecture.md §9 |
| RK-08 | 部署目录即 git 工作区 | 在 NAS 上直接改文件会让 `git push nas` 被拒 | AGENTS.md §4 |

### 10.2 已知问题（未修复）

级别：**高** = 影响 NAS 稳定或数据安全；**中** = 功能结果错误或误导；**低** = 体验、整洁或潜在问题。

| 编号 | 级别 | 问题 | 证据 | 归属 |
|---|---|---|---|---|
| KI-01 | 高 | 每次在线生成图块后，`evict_cache` 都逐个统计 `cache/pyramids/` 下的全部文件（约 517 万个；一次 `du` 遍历 4 分钟未完成），多个生成还可能并发触发；`中国国博馆藏` 的卷首次打开大多会走在线生成 | `app.py` `evict_cache`、`generate_worker`；状态文件图块数合计 | `cache-maintenance` |
| KI-02 | 中 | `pyramid_build_state.json` 多写者无锁：查看器非原子写入，生成器用内存中的整份状态覆盖。生成器运行期间发起的拼接，其重建请求可能丢失，拼接页仍报告「已生成」 | `_stitch_queue_pyramid`、`save_state`、`run_deferred_mode` | `stitch-hardening` |
| KI-03 | 中 | 拼接覆盖 `合并长卷.tif` 后缩略图不刷新：删的是 `thumbs/<hash>.jpg`，实际文件是 `thumbs/v3_<hash>.jpg`；进程内的总览/区域缓存也不失效 | `_stitch_remove_tiles`、`stitch_apply.py` 对比 `thumb_file` | `stitch-hardening` |
| KI-04 | 中 | `README-部署.md` 过时：数据规模（11,246 → 32,121 个 TIFF，4 → 5 类）、容器内存上限（768MB → 2048m）、缓存上限（50GB → `CACHE_MAX_GB=600`）、「无登录认证、勿映射公网」（已有登录墙且经 HTTPS 公网发布）；其中 `docker-compose up -d --build` 不带服务名，会同时拉起两个生成器 | §1.3；`docker-compose.yml`；nginx 站点 | 文档修订 |
| KI-05 | 低 | 拼接补边与页面提示不符：竖向补边复制边缘像素、横向间隙固定填白，`plan.bg` 只用作旋转背景 | `_stitch_build_worker`；`stitch.html` 提示文字 | `stitch-hardening` |
| KI-06 | 低 | 孤儿图块：926 条已完成记录的源文件已不存在（10-21 迁出的分片与 `_stitch_test` 测试卷），约 15 GB | 状态文件对照磁盘 | `cache-maintenance` |
| KI-07 | 低 | 生成器扫描不跳过 `#` / `@` / `.` 开头的目录（查看器会跳过）。现有 `中国国博馆藏/BD00081/.pages`（下载器的隐藏工作目录，63 个 TIFF），下次跑生成器会被切图但永远不展示 | `pyramid_worker.py` `scan_files` 对比 `app.py` `scan_index` | `tests-foundation` |
| KI-08 | 低 | 容器日志与宿主时间不一致，可能误导排障；私人偏移与原时刻非公开，问题未修复 | `docker-compose.yml` 的 `TZ` 与宿主时区配置 | PD-09 |
| KI-09 | 低 | `/api/region`、`/api/overview` 没有前端调用；`_overview_from_dzi` 按全局 `TILE_SIZE` 拼图，而生成器为 103 个宽图用了 256/128 的图块 | `static/` 无引用；状态文件图块尺寸分布 | 产品功能（超大卷局部高清）或删除 |
| KI-10 | 低 | `app.py` 顶部的接口表过时 | architecture.md §8 | 下次修改 `app.py` 时更新 |
