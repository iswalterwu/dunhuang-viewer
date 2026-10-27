# D-001 部署形态：NAS 本机 Docker Compose 服务，直读原图

- 日期：2026-10-27（追认登记；决策早于本文件）
- 状态：accepted

## 背景

敦煌画卷原图存放在NAS（DSM 7.3.2；设备实例与容量非公开）的 `/srv/example/data`，为数百 GB 级 TIFF 扫描件。
依据：`docker-compose.yml` 头部注释、`app.py` 文档字符串。

## 备选方案

未记录。

## 结论

在 NAS 本机以 Docker Compose 运行查看服务，原图目录挂载进容器直接读取；不拷贝原图、不做全量转码；
浏览器即客户端（局域网 / Tailscale；如开放公网，由部署方配置受控入口，私人拓扑非公开）。

## 取舍理由

- 原图体量大且就在 NAS 上，搬运或整体转码代价不可接受
- 浏览器免安装，电脑、手机、平板通用
- 容器化便于用 cgroup 硬性限制内存（D-005）

## 影响

- `docker-compose.yml`、`Dockerfile`；部署目录 `/srv/example/viewer`
- 所有解码都在 NAS 上进行，受 D-005 约束
