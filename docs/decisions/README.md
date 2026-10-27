# ADR 决策记录

本目录存放架构决策记录（Architecture Decision Records）。规则：

- **先登记再实现**：任何影响架构/产品形态的决策，先在此写一份 ADR，再改代码
- 文件名：`YYYYMMDD-<slug>.md`，编号全局递增 `D-XXX`
- 每份 ADR 必含：背景、考虑的备选、结论、取舍理由、生效日期、相关文档
- 已确认的决策汇总表在 `docs/plan.md` §3；待确认候选在 `docs/plan.md` §9
- 决策变更 = 新 ADR（注明取代的旧编号），不修改历史文件

## 模板

```markdown
# D-XXX <标题>

- 日期：YYYY-MM-DD
- 状态：accepted / superseded by D-YYY

## 背景
## 备选方案
## 结论
## 取舍理由
## 影响
```
