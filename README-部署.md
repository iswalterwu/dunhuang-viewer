# 敦煌画卷 · NAS 高清查看器（已部署）

## 访问地址

- 局域网：**http://192.0.2.10:8503**
- Tailscale（外出/手机）：**http://192.0.2.20:8503**

部署位置：NAS `/srv/example/viewer`，容器名 `dunhuang-viewer`。

## 内存安全设计（2026-10-18 事故后加固）

> 事故原因：现场资源压力下，对 4GB 单卷做整卷解码，把 NAS 拖进交换；设备容量、容器数量与交换现场非公开。
> 现在从五个层面保证“不会再爆”：

| 措施 | 配置 |
|---|---|
| 容器硬上限 | `mem_limit = 768MB`，`memswap_limit = 768MB`（禁用额外 swap） |
| 超限结果 | cgroup 直接杀掉容器，**NAS 本身不受影响**，`restart: unless-stopped` 自动拉起 |
| 解码并发 | `VIPS_CONCURRENCY=1`，同一时间只允许一个图块生成任务 |
| 内存守卫 | 可用内存 < `MEM_GUARD_MB=900` 时直接拒绝解码，前端提示“内存紧张” |
| 超大卷降级 | 像素量 > `FULL_DZI_MAX_PIXELS=3.5亿` 或 CMYK 等特殊色彩 → 只生成**预览分辨率**（长边 1 万像素），不整卷解码 |
| 流式预览 | 未压缩 TIFF 用自写流式缩小（按行块读取 + 行/列平均），内存只与输出图大小有关 |

实测：4GB CMYK 单卷（173750×5831）生成预览图块 **68 秒、内存峰值 160MB**，容器上限 768MB；宿主现场可用内存非公开。

## 功能

- 画廊：1058 卷 / 11246 个 TIFF，按 4 大类浏览，支持搜索法藏编号、经名
- 查看器：缩略图、滚轮/双指缩放、拖拽平移、导航缩略图、全屏
- 信息：像素尺寸、DPI、文件大小、页数、色彩位深、原图下载
- 分段：按 `1.tif / 2.tif / 合并版` 切换；说明.txt 自动显示
- 缓存：图块缓存上限 50GB，自动清理最旧

## 已知限制

- **超大合并卷**（>3.5 亿像素，如 4GB 的单幅长卷）目前只显示 1 万像素长边的**预览分辨率**；同一卷若有拆分文件（1.tif、2.tif），拆分卷仍是全分辨率。
- 后续可加“局部放大镜”：点预览任意位置，直接从原图读该区域高清图（每次只读几 MB，内存安全）。
- 画廊首次加载某分类时，缩略图需要现场生成（每张 1～2 秒，2 个并发），会先显示占位、逐步出现。

## 日常维护（SSH `ssh nasroot`）

```bash
cd /srv/example/viewer
/usr/local/bin/docker-compose ps
/usr/local/bin/docker-compose logs -f --tail 100
/usr/local/bin/docker-compose restart
/usr/local/bin/docker-compose up -d --build     # 更新代码后重建
docker stats --no-stream dunhuang-viewer        # 看实时内存
rm -rf cache/pyramids/* cache/thumbs/*          # 清缓存（会重新生成）
```

## 实测记录

| 项目 | 结果 |
|---|---|
| 小卷 24MP（6881×3556） | 图块 3.0 秒，全分辨率 |
| 中卷 ~300MB | 图块 5.0 秒，全分辨率 |
| 超大 4GB CMYK 卷 | 预览 68 秒、内存峰值 160MB、无 OOM |
| 大卷缩略图（复用预览 JPEG） | 0.22 秒 |
| 普通缩略图 | 1～2.4 秒（首次生成后缓存） |
| 索引扫描 | 11246 个 TIFF / 764.6GB / 1058 卷，不到 1 秒 |

## 安全提醒

服务无登录认证，仅适合局域网 / Tailscale 内使用，**不要把 8503 直接映射公网**。

## 部署步骤（重装参考）

1. 把本目录放到 `/srv/example/viewer`
2. 确认 `docker-compose.yml` 里 `/srv/example/data` 路径正确
3. `cd /srv/example/viewer && /usr/local/bin/docker-compose up -d --build`
4. 国内网络注意：Dockerfile 已把 Debian 源换阿里云、pip 换清华源
