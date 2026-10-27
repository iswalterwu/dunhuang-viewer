# D-002 后端：Python + FastAPI + uvicorn 单体

- 日期：2026-10-27（追认登记；决策早于本文件）
- 状态：accepted

## 背景

服务需要同时完成 TIFF 解码、DZI 切片、缩略图生成与 HTTP 服务。依据：`requirements.txt`、`app.py`、`Dockerfile`。

## 备选方案

未记录。

## 结论

Python（镜像 `python:3.12-slim`）+ FastAPI + uvicorn；业务集中在单文件 `app.py`，后台图块生成器 `pyramid_worker.py` 为独立脚本。

## 取舍理由

- 图像处理生态（pyvips、tifffile、Pillow、numpy）在 Python
- 单体便于在 NAS 上部署与排障

## 影响

- `app.py`、`requirements.txt`、`Dockerfile` 的启动命令
- `app.py` 已超过 2000 行；是否拆分模块属后续决策
