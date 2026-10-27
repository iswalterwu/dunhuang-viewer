# D-006 图块生成三通道：在线按需 + 全量后台 + 超巨卷专用

- 日期：2026-10-27（追认登记；决策早于本文件）
- 状态：accepted

## 背景

只靠首次打开时在线生成，大卷要等待较久；超巨卷在常规内存上限下反复 OOM。
依据：`pyramid_worker.py` 文档字符串与 `HUGE_PIXELS` 注释（「先跳过（后续单独用低内存方式处理），避免反复 OOM」）、`docker-compose.yml`。

## 备选方案

- 仅在线按需生成

## 结论

1. **在线按需**（`app.py`）：单并发，必要时降级为预览分辨率
2. **`pyramid-builder`**：全量生成全分辨率 DZI，断点续跑；超巨卷写入 `deferred` 队列
3. **`pyramid-huge`**（`PROCESS_DEFERRED=1`）：只处理 `deferred`，内存上限更高，由宿主机 `auto_huge_daemon.sh` 按需拉起

三者共享 `cache/pyramids/` 与 `cache/pyramid_build_state.json`；后台生成的全分辨率图块会替换在线生成的预览分辨率图块。

## 取舍理由

- 后台吞吐与交互延迟解耦，多数卷可以秒开
- 超巨卷隔离在独立容器，失败只影响它自己

## 影响

- `docker-compose.yml` 三个服务；`auto_huge_daemon.sh`、`auto_huge_boot.sh`
- 细节见 `architecture.md` §4
