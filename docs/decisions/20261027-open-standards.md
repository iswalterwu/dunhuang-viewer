# D-017 开放标准：IIIF 与 W3C Web Annotation

- 日期：2026-10-27
- 状态：accepted（plan.md PD-18，用户按建议确认）

## 背景

项目长期要与各收藏机构的平台互相链接（D-010）。IDP 与 Gallica 都以 IIIF 发布影像；本地国图卷附带 IDP 发布的 IIIF 清单（plan.md §1.3）。

## 备选方案

- 自定义的影像与标注格式

## 结论

1. 影像与清单向 IIIF（Image API、Presentation API）靠拢；本地影像记录与外部 IIIF 清单、画布的对应关系
2. 标注采用 W3C Web Annotation 数据模型
3. 对外交换数据时优先使用这两种标准格式

## 取舍理由

- 原机构已经使用 IIIF，按标准对接成本最低
- W3C Web Annotation 是 IIIF 生态的标注标准，便于与其他平台、查看器（如 Mirador）互通

## 影响

- `catalog-foundation`：影像与 IIIF 清单、画布的对应
- `annotation-workbench`：标注的存储与导出格式
