# 患者服务部数据分析工具

基于 Streamlit 的药品购买数据分析 Web 应用，支持复购率、脱落率、DOT、新患率四项指标。

## 功能特性

- **四种分析**：复购率、脱落率、DOT（治疗持续时间）、新患率
- **趋势折线图**：每个「品种 · 药房」组合一条折线，X 轴为月份、Y 轴为该分析核心指标；
  可按品种 / 药房多选筛选（组合数 ≤ 10 时默认全选，超过则默认不选并给出提示，避免首屏过于拥挤）
- **点选高亮**：单击某条曲线或图例中的某一项，即高亮该曲线、其余淡化；
  按住 Shift 可同时高亮多条；双击图表空白处复位
- **图例不截断**：图例标签不做长度截断，并把品种名压缩为易读短名
  （`替雷利珠单抗注射液(百泽安)` → `百泽安`），保证药房名完整可见；
  悬停 tooltip 仍显示品种 / 药房全称
- **一键下载全部结果**：把本次选中的各分析结果写入**同一个 Excel 的不同 Sheet**，
  另保留每个分析单独下载的按钮
- **可选分组维度**：可自由开启/关闭「按药店(Store)」与「按药品(Medic)」分组。缺少对应列时自动合并
- **数据模板下载**：内置模板，降低新用户误传格式风险
- **单次多结果**：一次运算可同时获得多种分析结果，分别下载互不干扰
- **日历月推算**：T-2 / T-1 严格按日历月定位，数据存在断档也能正确计算
- **负数销量保留**：退货/冲红等负数量计入统计

## 数据格式

必需字段（列名兼容中英文）：

| 标准列名 | 中文表头 | 说明 |
|----------|----------|------|
| TIME | 销售时间 | 日期时间，必填 |
| ID | 患者ID | 患者标识，必填 |
| Quantity | 数量 | 购买数量，可为负，必填 |

可选字段：

| 标准列名 | 中文表头 | 说明 |
|----------|----------|------|
| Store | 药店 | 可选；无则整体合并 |
| Medic | 药品名称 | 可选；无则整体合并 |

可在应用首页点击「下载数据模板」获取示例文件。

## 指标定义

| 指标 | 定义 |
|------|------|
| 复购率 | T-2 月购药患者中，在 T-1 或 T 月再次购药的比例 |
| 脱落率 | T-2 月购药患者中，在 T-1 和 T 月均未购药的比例 |
| DOT | 倒推 12 个月销量总和 ÷ 倒推 12 个月去重患者数 |
| 新患率 | 当月购药患者中，历史首次购药者的比例 |

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 部署（Streamlit Community Cloud）

- 入口文件填 `app.py`（不是 `streamlit_app.py`），分支 `main`
- `requirements.txt` 已锁定版本，且**必须选用在目标 Python 上带预编译 wheel 的版本**：
  当前为 `streamlit==1.59.2 / pandas==3.0.3 / numpy==2.5.1 / openpyxl==3.1.5`
  （实测在 Python 3.12 / 3.13 / 3.14 均有 wheel；老版本 pandas/numpy 在 3.14 无 wheel，
  会被迫源码编译并因缺 `pkg_resources` 而失败）
- `runtime.txt` 写 `python-3.12`。注意：Streamlit Cloud 可能忽略此文件而使用其默认 Python，
  因此依赖版本必须按「上下兼容」选取（见上）
- `altair` 由 Streamlit 自带，无需单独声明

## 项目结构

```
app.py                 # Streamlit 主界面（上传 / 参数 / 调用分析）
views.py               # 结果视图：筛选、折线图、数据表、下载按钮
charts.py              # 折线图数据准备与 Altair 图表构建
export_utils.py        # 多 Sheet Excel 导出
data_loader.py         # 共享数据加载与清洗
dot_logic.py           # DOT 计算
dropout_logic.py       # 脱落率计算
new_patient_logic.py   # 新患率计算
repurchase_analysis.py # 复购率计算
tests/                 # 单元测试与 AppTest 冒烟测试
```

## 测试

```bash
python tests/test_logic.py       # 四项指标计算逻辑
python tests/test_features.py    # 多 Sheet 导出 + 折线图数据/构建
python tests/smoke_app.py        # AppTest 冒烟：首屏 + 结果视图（筛选/图表/下载）
```
