# dunhuang-viewer 系统架构（architecture.md）

> 与 `plan.md` 配套。本文档定义组件职责、ID 与缓存布局、图块管线、拼接工作台、认证、部署拓扑与内存安全红线。变更需同步 ADR。
> 运行参数以 `docker-compose.yml`（环境变量）与代码默认值为准；本文只引用参数名，必要处注明 compose 当前值。

## 1. 总体架构

```
浏览器（电脑 / 手机 / 平板）
  │  局域网 http://192.0.2.10:8503 · Tailscale http://192.0.2.20:8503
  │  公网：部署方配置受控入口，私人网关组件链与端口非公开
  │       （私人入口实例与配置不属于本仓库，不公开）
  ▼
┌──────────────────────────────────────────────────────────────┐
│ dunhuang-viewer 容器（FastAPI + uvicorn :8000 → 宿主 :8503）       │
│  登录墙中间件 → 页面 gallery / viewer / stitch · /api · /tiles    │
│  索引（内存）· 在线图块（单并发）· 缩略图（THUMB_WORKERS 并发）       │
│  局部区域 / 总览 · 拼接工作台（单并发，写回原图目录）· 用户管理        │
└───────────────┬──────────────────────────────┬───────────────┘
                │ /data（rw）                   │ /cache（rw）
                ▼                               ▼
     /srv/example/data（原始 TIFF）       /srv/example/cache
                ▲ /data（ro）                   ▲ /cache（rw）
┌───────────────┴──────────────────────────────┴───────────────┐
│ pyramid-builder 容器：全量 DZI（跑完退出，restart: on-failure）     │
│ pyramid-huge 容器：PROCESS_DEFERRED=1，只处理被延后的超巨卷          │
└──────────────────────────────────────────────────────────────┘
宿主机：部署方安装的开机钩子 → auto_huge_daemon.sh（每 20 秒）
        ├─ python3 stitch_apply.py（旧拼接输出队列）
        └─ 延后队列非空且 pyramid-huge 未运行 → docker-compose up -d pyramid-huge
```

三个容器共用镜像 `dunhuang-viewer:latest`。`app.py`、`pyramid_worker.py` 打进镜像；`static/` 在查看器容器里以只读方式挂载到 `/app/static`。

## 2. 组件职责

| 组件 | 职责 | 位置 |
|---|---|---|
| 画廊页 | 分类筛选、搜索、分批渲染、懒加载缩略图、重新扫描入口 | `static/gallery.html` |
| 查看器页 | OpenSeadragon 缩放浏览、分段切换、元数据/说明面板、图块生成进度、原图下载 | `static/viewer.html` |
| 拼接工作台页 | 分片排列/旋转/裁切、自动建议重叠、保存方案、生成整卷 | `static/stitch.html` |
| 索引 | 启动时与 `POST /api/rescan` 时扫描 `DATA_DIR`，构建分类/卷/文件索引（只在内存） | `app.py` `scan_index` |
| 在线图块 | 按需生成 DZI（单并发、内存守卫、超大卷降级预览），`/tiles` 静态服务 | `app.py` `build_pyramid` / `generate_worker` |
| 缩略图 | 中心 4:3 裁切缩略图，优先复用预览 JPEG 与已有图块 | `app.py` `ensure_thumb` |
| 局部区域 / 总览 | 原图矩形区域、整卷总览小图（当前 `static/` 无调用方） | `app.py` `api_region` / `api_overview` |
| 认证与用户管理 | 登录墙、会话、限流、管理后台 | `app.py`（§7） |
| 拼接工作台后端 | 方案存取、分片预览、整卷生成、写回、触发图块重建 | `app.py`（§6） |
| 后台生成器 | 全量 DZI 与超巨卷 DZI，断点续跑 | `pyramid_worker.py`（§4.3） |
| 宿主机脚本 | 守护循环、开机钩子、旧拼接队列搬运 | `auto_huge_daemon.sh` / `auto_huge_boot.sh` / `auto_huge.sh` / `stitch_apply.py` |

## 3. 数据模型、ID 与缓存布局

### 3.1 原图目录约定

```
/srv/example/data/
└── <分类>/                 # 一级目录 = 分类（@、#、. 开头的目录被忽略，含 #recycle、@eaDir）
    └── …/<卷目录>/          # 任意层级中含 TIFF 的目录 = 一卷；目录名即卷标题
        ├── 1.tif, 2.tif …   # 分段；扩展名 .tif/.tiff/.btf；纯数字文件名按数值排在最前
        ├── 合并长卷.tif      # 可选：拼接工作台输出（D-008）
        └── *.txt            # 可选：说明文字（依次尝试 utf-8-sig / gb18030 / utf-16 / latin-1，最多 8000 字）
```

卷封面取该卷体积最小的文件。

### 3.2 ID 与缓存键

- 卷 ID = `base64url(卷目录相对路径)`，文件 ID（fid）= `base64url(文件相对路径)`，均去掉 `=` 填充
- 缓存键 `h = sha1(fid)[:16]`（十六进制）
- 同一映射在三处各实现一份，必须保持一致：`app.py`（`encode_id` / `file_hash` / `pyramid_files`）、
  `pyramid_worker.py`（`encode_id` / `file_hash` / `pyramid_paths`）、`stitch_apply.py`（内联）

### 3.3 缓存布局（`/srv/example/cache`，容器内 `/cache`）

```
cache/
├── pyramids/<h>/
│   ├── <h>.dzi                       # DZI 描述（Width / Height / TileSize）
│   ├── <h>_files/<level>/<col>_<row>.jpg
│   └── <h>_preview.jpg               # 仅降级生成时存在：预览底图，复用为缩略图/总览
├── thumbs/v3_<h>.jpg                 # 缩略图（v3_ 为版本前缀）
├── stitch_plans/<sha1("stitch:"+卷ID)[:16]>.json
├── stitch_previews/<key>_<w>.jpg     # 拼接工作台分片预览
├── stitch_out/                       # 旧拼接输出队列（§6.3）
├── users.json                        # 用户表（权限 600）
├── pyramid_build_state.json          # 后台生成状态：done / failed / attempts / deferred / current
├── pyramid_build.log · pyramid_build.stop（暂停信号）
└── auto_huge.log · stitch_apply.log
```

`/tiles` 挂载 `cache/pyramids/`，查看器加载 `/tiles/<h>/<h>.dzi`。

## 4. 图块管线

### 4.1 在线按需（`app.py`）

- `POST /api/pyramid/{fid}` 幂等：`.dzi` 已存在 → 直接 `ready`；否则起后台线程，状态 `queued → generating → ready | error`
- 全局信号量 `PYR_GENERATE_LOCK` 保证同一时间只生成一个；入队前、开始解码前、预览底图生成后各检查一次内存守卫
- libvips 不回报进度，用平滑的假进度（最高 90%）；前端轮询 `GET /api/pyramid/{fid}/status`
- 状态只在内存（`PYR_STATE`），进程重启后以磁盘上的 `.dzi` 为准；成功后触发 `evict_cache`（超过 `CACHE_MAX_GB` 时按目录修改时间删到 80%）

### 4.2 降级规则（`_build_pyramid_vips`）

满足任一条件即走「预览分辨率」：像素数 > `FULL_DZI_MAX_PIXELS`、色彩不是 RGB / MINISBLACK / MINISWHITE（如 CMYK）、位深不是 uint8。

1. 未压缩 TIFF：自写流式缩小到长边 `PREVIEW_LONG_EDGE`、总像素不超过 `PREVIEW_MAX_PIXELS`（按行块读取，内存只与输出尺寸相关）
2. 否则若像素数 ≤ `PREVIEW_VIPS_MAX_PIXELS`：libvips `thumbnail`
3. 否则拒绝（压缩格式的超大卷，提示下载原图）

预览 JPEG 再经 `dzsave` 切成图块，`preview_only` 标记传给前端。无 libvips 时退回 Pillow，超过 1.5 亿像素直接拒绝。

### 4.3 后台全量与超巨卷（`pyramid_worker.py`）

- 扫描全部 TIFF，跳过已有全分辨率 DZI 的文件（DZI 宽高 = 原图宽高）
- 超巨卷（像素 > `HUGE_PIXELS`，或宽/高 > `HUGE_WIDTH`）写入 `deferred` 队列，留给 `pyramid-huge`
- 每文件最多 3 轮、每轮重试 2 次；可用内存低于 `BUILD_MEM_FLOOR_MB` 时每 60 秒等待
- 图块尺寸自适应：从 512 起降，直到「宽 × 通道 × 图块高」≤ `BUILD_STRIP_MB`；16 位按 /257 转 8 位，CMYK 转 sRGB
- 生成后校验 DZI 宽度等于原图宽度；状态每步原子写入 `pyramid_build_state.json`，重启即断点续跑
- 暂停：创建 `cache/pyramid_build.stop`，当前文件完成后退出
- `pyramid-huge`（`PROCESS_DEFERRED=1`）只处理 `deferred`，由宿主机守护循环按需拉起

## 5. 缩略图、总览与局部区域

- **缩略图**（`ensure_thumb`）依次尝试：磁盘缓存 → 预览 JPEG → 已有图块的中间层中心块 → 像素数 > `THUMB_VIPS_MAX_PIXELS` 时从未压缩原图直接读中心 2400×1800 区域（压缩格式返回 503）→ libvips 整卷缩略 → Pillow；并发上限 `THUMB_WORKERS`，内存守卫不通过返回 503
- **总览**（`/api/overview/{fid}`）：预览 JPEG → DZI 低层图块拼接 → 原图抽样；进程内缓存 20 张
- **局部区域**（`/api/region/{fid}`）：区域限 64～4000 像素边长、≤ 1200 万像素；有全分辨率 DZI 时用最高层图块拼，否则直读未压缩原图；并发 2，进程内 LRU（24 张 / 24MB）

## 6. 拼接工作台

### 6.1 方案

页面 `/stitch/{卷ID}`。方案 JSON：`pieces[]`（`id`、`x`、`y`、`angle`（±45°）、`trimr`（右裁）、`enabled`）+ `bg`（背景色），
保存在 `cache/stitch_plans/`；前端每 5 秒把草稿写入 `localStorage`。「自动建议重叠」在预览图上对相邻分片做灰度归一化互相关估计重叠。

### 6.2 生成（`POST /api/stitch/{卷ID}/build`）

1. 单并发（`STITCH_SEMAPHORE`）；校验分片都属于本卷
2. 横向排列：与左侧重叠的部分自动裁掉，留出的间隙填白；按 `y` 计算高度差后补边；旋转用 `bg` 作背景
3. 先写 `<卷目录>/.合并长卷_building_<ts>.tif`（BigTIFF、不压缩），再原子替换为 `<卷目录>/合并长卷.tif`（D-008）
4. 删除旧图块，写入 `deferred` 队列 → 等待 `pyramid-huge` 完成（最多 40 分钟）→ 重扫索引
5. 进度经 `GET /api/stitch/{卷ID}/build/status` 查询

### 6.3 旧通道（疑似遗留）

`cache/stitch_out/*.tif` + 同名 `*.json`（`target` 指明目标路径）由宿主机 `stitch_apply.py` 复制入卷目录（临时文件 + 原子替换）并加入 `deferred`。
`app.py` 只创建 `stitch_out/` 目录、不再写入；守护循环每 20 秒仍会运行一次 `stitch_apply.py`（队列为空时无动作）。

## 7. 认证与用户管理

- **启用条件**：`AUTH_USER`、`AUTH_PASS`、`AUTH_SECRET` 三项均非空；**任一缺失即关闭登录墙，全站匿名可访问**
- **初始管理员**：启动时若用户表里没有 `AUTH_USER`，用 `AUTH_PASS` 创建（admin、bootstrap）；之后 `.env` 的密码不再覆盖已存在账号，改密走后台
- **密码**：pbkdf2_sha256，20 万次迭代，16 字节随机盐；用户名不存在时也做一次等价哈希（防枚举）
- **会话**：cookie `dh_session` = base64url(`用户|过期时间|HMAC-SHA256(AUTH_SECRET)`)，有效期 `AUTH_SESSION_HOURS`；httponly、samesite=lax，`secure` 取决于 `X-Forwarded-Proto`；每次校验都确认用户仍在用户表里（删除用户即刻失效）
- **未登录**：页面 303 跳 `/login?next=…`；`/api/`、`/tiles/`、`/thumb/`、`/file/` 返回 401 JSON；`/static/`、`/login`、`/logout` 放行
- **限流**：同一 IP 10 分钟内失败 10 次 → 429；IP 依次取 `X-Real-IP`、`X-Forwarded-For` 最后一段、连接地址
- **管理后台** `/admin`：新增用户（用户名 2～32 位字母数字 `_.-`，密码 ≥ 8 位）、设/取消管理员（至少保留一个）、删除、重置密码；表单带 CSRF（`HMAC(AUTH_SECRET, "csrf|"+会话)`）

## 8. 接口清单

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` · `/view/{卷ID}` · `/stitch/{卷ID}` | 画廊 / 查看器 / 拼接工作台页面 |
| GET/POST | `/login` · GET `/logout` | 登录、登出 |
| GET | `/admin` · POST `/admin/add` `/admin/toggle_admin` `/admin/delete` `/admin/reset` | 用户管理（仅管理员） |
| GET | `/api/health` | 健康检查：数据目录、libvips、可用内存与关键阈值 |
| GET | `/api/me` | 当前用户与是否管理员 |
| GET | `/api/index` · POST `/api/rescan` | 索引、重新扫描 |
| GET | `/api/item/{卷ID}` | 单卷详情：每段尺寸/DPI/压缩/位深、说明文字 |
| GET | `/thumb/{fid}` | 缩略图（浏览器缓存 7 天） |
| POST | `/api/pyramid/{fid}` · GET `/api/pyramid/{fid}/status` | 触发图块生成（幂等）、查询进度 |
| GET | `/tiles/<h>/…` | DZI 描述与图块（静态） |
| GET | `/file/{fid}` | 原图下载 |
| GET | `/api/overview/{fid}` · `/api/region/{fid}` | 总览小图、局部高清区域 |
| GET | `/api/stitch/{卷ID}/info` · `/api/stitch/piece/{fid}` | 拼接信息与已存方案、分片预览 |
| POST | `/api/stitch/{卷ID}/plan` · `/api/stitch/{卷ID}/build` | 保存方案、生成整卷 |
| GET | `/api/stitch/{卷ID}/build/status` | 生成进度 |

`app.py` 顶部文档字符串里的接口表早于认证、拼接、区域等功能，已不完整，以本表为准。

## 9. 部署与运行

| 服务（容器名） | 重启策略 | 内存上限（= memswap） | 原图挂载 | 要点 |
|---|---|---|---|---|
| `dunhuang-viewer` | unless-stopped | 2048m | rw | 端口 8503→8000；`env_file: .env`；`static/` 只读挂载 |
| `pyramid-builder` | on-failure | 1536m | ro | `python -u pyramid_worker.py`；跑完正常退出不再重启 |
| `pyramid-huge` | on-failure | 2304m | ro | 同上 + `PROCESS_DEFERRED=1` |

- **镜像**：`python:3.12-slim` + `libvips42`；apt / pip 软件源镜像用于构建网络兼容，不表示私人主机联网状态
- **开机**：由部署方安装的 `auto_huge_boot.sh` **拷贝**拉起 `auto_huge_daemon.sh`，安装位置非公开
- **代码同步**（D-009）：本机工作副本 → `git push origin main`（GitHub）→ `git push nas main`（NAS 部署目录，updateInstead 直接更新工作区）
- **生效方式**：`static/` 推送即生效；`app.py` / `pyramid_worker.py` / `Dockerfile` / `requirements.txt` 需在 NAS 上
  `cd /srv/example/viewer && /usr/local/bin/docker-compose up -d --build dunhuang-viewer`（经用户确认；不带服务名会同时拉起两个生成器）
- **运维入口**：`ssh nas`（operator，文件）、`ssh nasroot`（root，`/usr/local/bin/docker`、`/usr/local/bin/docker-compose`）

## 10. 内存安全红线（D-005）

背景：2026-10-18，对 4GB 单卷整卷解码，把 NAS 拖进交换；设备规格、容器数量与交换现场非公开。

| 层面 | 机制 | 参数 |
|---|---|---|
| 容器 | 硬上限且禁用额外 swap，超限由 cgroup 杀容器，NAS 不受影响 | `mem_limit` = `memswap_limit`（§9） |
| 解码并发 | libvips 单线程；在线图块单并发；拼接单并发 | `VIPS_CONCURRENCY=1`、`PYR_GENERATE_LOCK`、`STITCH_SEMAPHORE` |
| 内存守卫 | 可用内存低于阈值即拒绝解码（在线图块、缩略图、区域、分片预览） | `MEM_GUARD_MB` |
| 超大卷 | 只生成预览分辨率，不整卷解码 | `FULL_DZI_MAX_PIXELS`、`PREVIEW_LONG_EDGE`、`PREVIEW_MAX_PIXELS` |
| 整卷解码上限 | 缩略图/预览允许 libvips 整卷处理的像素上限 | `THUMB_VIPS_MAX_PIXELS`、`PREVIEW_VIPS_MAX_PIXELS` |
| 后台生成 | 内存低于下限时等待；条带内存预算决定图块尺寸；libvips 缓存 16MB | `BUILD_MEM_FLOOR_MB`、`BUILD_STRIP_MB` |

注意：三个容器上限合计 5888m（约 5.75 GiB）；守护循环只检查 `pyramid-huge` 是否在跑，不检查 `pyramid-builder`，两个生成器可能并发，此时只靠各自的 `BUILD_MEM_FLOOR_MB` 等待兜底。

## 11. 隔离与安全

- **原图**：两个生成器只读挂载；查看器读写挂载，唯一写入路径是拼接输出（D-008）
- **凭证**：`.env`（权限 600，不入库）；用户表 `cache/users.json`（权限 600）
- **公网**：入口拓扑非公开，本仓库内没有 TLS 配置；登录墙 fail-open（§7）；限流信任 `X-Real-IP` / `X-Forwarded-For`（风险见 plan.md §10）
- **下载**：任何已登录用户都可经 `/file/{fid}` 下载 GB 级原图
