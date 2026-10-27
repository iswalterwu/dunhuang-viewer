# D-004 前端：原生 HTML/CSS/JS + OpenSeadragon，无构建步骤

- 日期：2026-10-27（追认登记；决策早于本文件）
- 状态：accepted

## 背景

前端只有画廊、查看器、拼接工作台三个页面。依据：`static/`、`docker-compose.yml`。

## 备选方案

未记录。

## 结论

- 原生 HTML/CSS/JS，无打包与构建步骤
- 缩放浏览使用本地托管的 OpenSeadragon（`static/openseadragon.min.js`）
- `static/` 以只读方式挂载进查看器容器（`/app/static`）

## 取舍理由

- 页面数量少，不需要框架
- 无构建链，便于在 NAS 上直接维护
- 挂载后改页面无需重建镜像

## 影响

- `docs/designUI.md`
- 页面改动推送即生效（AGENTS.md §4）
