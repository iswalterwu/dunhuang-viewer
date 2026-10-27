# dunhuang-viewer 总方案（plan.md）

> 本文档是项目方案的总入口：背景目标、决策记录、文档体系、目录结构、路线图与扩展点。
> 架构细节见 `architecture.md`，设计理念见 `designUI.md`。变更本文件内容即变更项目方案，需同步相关文档。

## 1. 背景与目标

NAS（设备实例非公开）的 `/srv/example/data` 下存放敦煌遗书高清扫描件，按一级目录分类（如 `敦煌003`、`敦煌004`、
`中国国博馆藏`）。单卷从几十 MB 到数 GB 不等，多为未压缩 TIFF，也有 CMYK、16 位、超长卷与分段扫描（`1.tif`、`2.tif`…）。
这类文件无法在普通设备上整卷打开，更无法在手机/平板上浏览；在受限内存的 NAS 上整卷解码，还曾把整台 NAS 拖进交换（2026-10-18 事故，见 D-005）。

**目标**（与 `app.py` 文档字符串一致）：

1. 直接读取 NAS 本机磁盘上的 TIFF，不拷贝、不全量转码；
2. 首次打开某卷时在 NAS 本地生成 DZI 缩放图块（进度可查），之后秒开；
3. 电脑/手机/平板通过网页缩放浏览，只下载小图块；
4. 提供元数据、`说明.txt`、原图下载、按卷分段浏览；
5. 在任何负载下都不让查看器拖垮 NAS（内存安全红线，D-005）。

## 2. 产品定位与核心循环

- **用户**：所有者本人及其授权用户（登录墙 + 用户管理后台；管理员增删用户、重置密码）
- **访问通道**：局域网 / Tailscale 地址由部署方提供；可选公网入口须有访问控制与登录墙，私人拓扑及端口非公开（architecture.md §1）
- **核心循环**：原始 TIFF（只读）→ 索引 + DZI 图块 / 缩略图（`cache/`）→ FastAPI → 浏览器（OpenSeadragon）
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
| D-008 | 原始数据写入例外：拼接输出 `合并长卷.tif` 写回卷目录（查看器以 rw 挂载原图） | `cache/stitch_out/` 输出 + 宿主机 `stitch_apply.py` 搬运（旧通道，疑似遗留） | 拼接结果需作为一段参与浏览与图块生成 |
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
├── auto_huge.sh           # 单次检查版本（未发现调用方，已被 auto_huge_daemon.sh 取代）
├── static/                # 前端：gallery / viewer / stitch 页面 + style.css + openseadragon.min.js
├── Dockerfile             # python:3.12-slim + libvips42（apt 阿里云源、pip 清华源）
├── docker-compose.yml     # 三个服务：dunhuang-viewer / pyramid-builder / pyramid-huge
└── requirements.txt
```

运行时产物（不入库，见 `.gitignore`）：`.env`、`cache/`（图块、缩略图、拼接方案与预览、用户表、生成状态与日志）、`build.log`。

## 6. 架构总览

三个容器共用一个镜像：**`dunhuang-viewer`**（FastAPI 服务，对外 8503）、**`pyramid-builder`**（全量图块）、**`pyramid-huge`**（超巨卷图块），
外加宿主机上的 **`auto_huge_daemon.sh`** 守护循环。原图目录只读挂载给两个生成器，读写挂载给查看器（仅拼接写入，D-008）；三者共享 `cache/`。
组件职责、数据流与部署细节见 `architecture.md`。

## 7. 扩展点

### 7.1 访问端

- 浏览器即客户端；900px 以下查看器侧栏改为右侧滑出抽屉、拼接工作台隐藏侧栏；触控支持双指缩放（designUI.md §5）
- 公网入口拓扑非公开；是否有 TLS 终结不在本仓库配置内（待确认，§9）

### 7.2 数据

- 新增分类 = 在 `/srv/example/data` 下新建一级目录（以 `@`、`#`、`.` 开头的目录被忽略）；画廊「重新扫描」（`POST /api/rescan`）后可见
- 新增卷的全分辨率图块：首次打开时在线生成；或手动 `docker start dunhuang-pyramid-builder` 批量补齐（生成器跑完即退出，不会自动重跑）

### 7.3 图像格式

- 流式路径（预览、缩略图、局部区域）只覆盖未压缩、CONTIG、uint8/uint16 的 TIFF；压缩格式的超大卷目前只能下载原图
- 扩展位置：`app.py` 的 `_stream_preview_plain_tiff`、`_fast_thumb_plain_tiff`、`read_region_plain_tiff`

## 8. 路线图

| 阶段 | 内容 |
|---|---|
| **Phase 0（当前）** | 文档体系与仓库骨架：AGENTS.md、docs 三件套、ADR 追认登记（D-001 ～ D-009）、spec-driven 工作流与模板（templates/、specs/） |
| **后续** | 由用户确定；候选见 §9，经用户确认后按 AGENTS.md §2 立项 |

## 9. 待确认决策

待用户确认（确认后登记 ADR）：

- **视觉统一**：登录页/管理后台（暖色纸底 + 宋体）与主界面（冷灰玻璃）两套视觉并存，是否统一、统一到哪一套（designUI.md §7）
- **公网 TLS**：公网侧是否有 HTTPS 终结与反向代理须核实（影响会话 cookie 的 `secure` 标志与登录限流的 IP 取值，§10）；私人入口拓扑非公开
- **自动化测试**：是否建立 `tests/`（pytest），作为 AGENTS.md §4「提交前跑测试」的正式载体
- **旧拼接通道**：`cache/stitch_out/` + `stitch_apply.py` 是否下线（`app.py` 已不再向 `stitch_out/` 写入）

候选功能（来自既有代码与 `README-部署.md` 的已知限制，尚未立项）：

- 超大合并卷的全分辨率查看：后端已有 `/api/region` 与 `/api/overview`，当前 `static/` 中没有调用方
- 压缩格式超大卷的流式解码（§7.3）

## 10. 风险、约束与已知问题

风险与约束：

- **内存安全**：NAS 与其他工作负载共享内存；任何新解码路径都必须经过内存守卫并受容器上限约束（D-005）；私人设备规格与容器数量非公开
- **原图可写**：查看器容器对 `/srv/example/data` 有写权限（拼接需要），代码缺陷可能波及原图（D-008）
- **公网可达**：登录墙是唯一屏障。三项 `AUTH_*` 缺一项即**全站匿名开放**（fail-open）；登录限流按 `X-Real-IP` / `X-Forwarded-For` 取 IP，若公网侧无反代覆盖这两个头，客户端可伪造它们绕过限流（待核实）
- **ID 映射重复实现**：`app.py`、`pyramid_worker.py`、`stitch_apply.py` 各写了一份 ID/缓存键映射，改一处即缓存失配
- **无自动化测试**；本机 Python 3.14 与容器 Python 3.12 不一致
- **开机钩子是拷贝**：由部署方安装的 `auto_huge_boot.sh` 副本不是链接，修改后需手动同步；安装位置非公开
- **部署目录即 git 工作区**：在 NAS 上直接改文件会让 `git push nas` 被拒（updateInstead 要求工作区干净）

已知问题（未修复，待立项）：

- **文档漂移**：`README-部署.md` 多处与现状不符，以 `docker-compose.yml` / `app.py` 为准——容器内存上限写 768MB（compose 为 2048m）、图块缓存上限写 50GB（compose 为 `CACHE_MAX_GB=600`）、写「服务无登录认证」（已有登录墙且已开通公网通道）、写「4 大类」（以实际一级目录为准）
- **拼接后缩略图不刷新**：拼接覆盖 `合并长卷.tif` 后删除的是 `thumbs/<hash>.jpg`，实际缩略图文件名为 `thumbs/v3_<hash>.jpg`（`app.py` 的 `_stitch_remove_tiles`、`stitch_apply.py` 对比 `thumb_file`）；进程内的总览/区域缓存同样不会失效
- **拼接补边与页面提示不一致**：页面提示「上下拖动……生成时补背景边」，代码竖向补边用 `extend="copy"`（复制边缘像素），横向间隙固定填白，`plan.bg` 只用于旋转后的背景
- **缓存淘汰全量遍历**：每次在线生成图块后，`evict_cache` 对 `cache/pyramids/` 做全量 `rglob` 统计体积；缓存很大时可能非常耗时（待验证）
- **总览图块尺寸假设**：`_overview_from_dzi` 按全局 `TILE_SIZE`（512）拼图，而 `pyramid_worker.py` 会为宽图自适应选用更小的图块，二者不匹配时总览会错位（当前无前端调用）
