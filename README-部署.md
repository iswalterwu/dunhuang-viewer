# 敦煌画卷 · NAS 高清查看器部署说明

> 公开隐私修订，原件非公开保全，不是逐字原文。下面是通用部署契约，不是私人主机实例；历史测量单列，不能当作当前候选复验。运行参数以 `docker-compose.yml` 为准。

## 公开边界与前置许可

代码保持公开（D-019），不代表影像已获开放许可，也不代表服务对匿名用户开放。许可未知的影像仅供登录墙内研究；对外优先链接原机构 IIIF。私人地址、账户、网关拓扑与材料接收操作不发布。

只部署经 Review、用户 Gate 2 并合并到 main 的提交：本机 `git push origin main` 后，再获准 `git push nas main`。`nas` 是部署远端角色名，由操作者非公开配置。禁止在 NAS 工作区改代码。**重建或重启前另征得用户确认，并且只操作目标服务。** 目录服务的独立部署见 [catalog/README.md](catalog/README.md)，不要混用两个 Compose 项目。

## 配置与访问

在部署方指定的 `DH_DEPLOY_DIR` 准备权限 600 的 `.env`，不入库、不打印展开配置。根模板见 `.env.example`：

| 参数 | 含义 |
|---|---|
| DH_HOST_DATA_DIR | 必填宿主原图根；查看器挂载为 `/data:rw`，生成器为 `/data:ro` |
| DH_HOST_CACHE_DIR | 必填宿主缓存根；容器内为 `/cache` |
| DH_HOST_STATIC_DIR | 宿主静态目录；按根 Compose 的明确相对项目示例或部署方显式值，只读挂载 `/app/static` |
| AUTH_USER / AUTH_PASS / AUTH_SECRET | 三项必须齐全；v0 缺任一项即关闭登录墙，不能匿名发布 |
| AUTH_SESSION_HOURS | 会话有效期；按部署配置管理 |

HOST 输入不能与容器内 `DATA_DIR` / `CACHE_DIR` 混同。三个 shell 脚本都必须显式获得 `DH_DEPLOY_DIR`；访问 data/cache 时还须相应 `DH_HOST_DATA_DIR` / `DH_HOST_CACHE_DIR`，传给 `stitch_apply.py` 的是 `DATA_DIR` / `CACHE_DIR`。当前三个脚本均要求三项在**进程环境**中非空；不会 source/eval `.env`，仅填写模板不足以运行脚本。缺必要配置必须无动作且非0退出，开机钩子不得按自身安装位置猜项目根。

访问地址由部署方提供（局域网、Tailscale 或另行获准的 v0 HTTPS 入口）；不把示例称为已部署主机。公网使用必须有 HTTPS、受控代理头及登录墙，不能仅暴露后端端口。catalog Phase 1 仅局域网 / Tailscale，缺 AUTH_SECRET 拒绝所有请求。

## 内存安全设计

历史上整卷解码 4GB 文件曾使宿主陷入交换；事故事实保留，私人设备规格与现场资源状态非公开。不得据以下机制保证绝对不会故障：

- 每个容器 `mem_limit = memswap_limit`，禁用额外 swap；当前查看器 2048m、全量生成器 1536m、超巨卷生成器 2304m。
- `VIPS_CONCURRENCY=1`，在线图块及拼接各单并发；低于 `MEM_GUARD_MB` 拒绝解码。
- 超过 `FULL_DZI_MAX_PIXELS` 或特殊色彩/位深按规则降级预览；未压缩 TIFF 以行块流式缩小，不整卷载入。
- 后台任务遵守 `BUILD_MEM_FLOOR_MB` / `BUILD_STRIP_MB`；三个上限相加仍可能争用宿主资源，不能忽略并发风险。
- 阈值只许收紧；放宽须先登记 ADR。完整红线见 [architecture.md](docs/architecture.md) §10、D-005。

## 功能与限制

画廊支持分类、搜索、懒加载；查看器支持缩放、平移、导航图、全屏、分段切换、文件信息与原图下载；拼接工作台按 D-008 仅写卷目录的 `合并长卷.tif`（临时文件 + 原子替换）。不得新增其他原图写入路径。

超大卷可能只提供预览分辨率，须明确告知用户；首次缩略图可能等待。缓存上限使用 `CACHE_MAX_GB`，当前 Compose 为 600；不能沿用早期 50GB 说明。**禁止为日常维护对 cache 全量 find/du，或无审批批量删除缓存。** 已知缓存、队列与扫描问题见 `docs/plan.md` §10。

## 获准后的日常维护

以下命令只说明目标范围，不是本轮执行授权；Docker/Compose 可执行位置由部署方确认：

```bash
: "${DH_DEPLOY_DIR:?必须配置部署目录}"
cd "$DH_DEPLOY_DIR"
docker-compose ps dunhuang-viewer
docker-compose logs -f --tail 100 dunhuang-viewer
# 下面两项须先获用户明确确认；仅目标服务，禁止无服务名启动全部项目
# docker-compose restart dunhuang-viewer
# docker-compose up -d --build dunhuang-viewer
```

`static/` 挂载，获准推送即生效；`app.py` / `pyramid_worker.py` / Dockerfile / requirements 变化须受控重建。不得运行全局 prune 或顺带启动两个图块生成器。旧拼接队列是否下线另按 PD-07 / `stitch-hardening`，本次隐私修订不改变其生命周期。

## 历史测量（脱敏摘要，非当前代码实测）

原说明的测试容器上限为 **768MB**，并非当前 2048m 配置。原记录的材料规模为 **1058 卷 / 11246 TIFF、4 类**，不是当前目录盘点；后续盘点见 `docs/plan.md` §1.3。私人主机可用内存原值仅非公开保留。

| 项目 | 原记录结果 |
|---|---|
| 小卷 24MP（6881×3556） | 图块 3.0 秒，全分辨率 |
| 中卷约300MB | 图块 5.0 秒，全分辨率 |
| 超大4GB CMYK卷（173750×5831） | 预览68秒、内存峰值160MB、无OOM；原预览长边1万像素，阈值3.5亿像素 |
| 大卷缩略图（复用预览JPEG） | 0.22秒 |
| 普通缩略图 | 1～2.4秒（首次生成后缓存） |
| 索引扫描 | 11246 TIFF / 764.6GB / 1058卷，不到1秒 |

原守卫配置 `MEM_GUARD_MB=900`、缩略图首次约1～2秒 / 2并发等属于旧记录，不是当前运行推荐或本轮新测。原文「无登录认证」已过时：现行 v0 登录墙启用条件及 fail-open 风险见上；不以删去旧错误说明掩盖既有风险。其他历史软件测试与审核边界见 [公开验证摘要](docs/verification.md)。
