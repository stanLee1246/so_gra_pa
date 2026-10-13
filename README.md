# 网络购物消费者投诉特征分析与 Web 可视化

按 [项目方案](docs/project_plan.md) 搭建的可运行研究原型。使用 **2023—2025 年模拟数据**，演示平台 A/B/C 为虚构名称，所有图表只描述当前样本，不能用作真实市场结论或平台风险评级。

技术栈：Python 3.12、Pandas、NumPy、SQLite、FastAPI、Uvicorn、Apache ECharts 5.6.0。首页使用本地图表资源，运行不需要 Node.js、外部数据库、API 密钥或 CDN。

## 快速开始

在项目根目录执行，Linux / macOS：

```bash
bash scripts/setup.sh
bash scripts/start.sh
```

安装脚本使用锁定依赖；首次生成数据，之后保留现有演示数据并验证。启动默认监听端口 8000，可通过 `PORT` 调整。云环境通过其支持的访问方式使用服务；浏览器测试使用内部 HTTP 请求。

Windows PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe generate_demo.py --seed 42 --scenario baseline
.\.venv\Scripts\python.exe prepare_data.py
.\.venv\Scripts\python.exe verify.py
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Windows 数据生成命令会覆盖已有演示产物；首次初始化时运行，已有数据请先备份。本机浏览器访问端口 8000 的首页。开发时可在 Uvicorn 命令后加 `--reload`，停止服务使用 Ctrl+C。

## 已实现功能

- 固定种子生成 baseline / promotion 两种演示场景；记录参数与输入 SHA256。
- 字段与范围校验、隔离错误、缺失品类归为“未知”、来源与 ID 联合去重；同 ID 内容冲突阻止导入。
- SQLite 明细表、来源表、约束、索引与月度聚合视图。
- 年份／平台／品类／类型联动筛选、四项指标卡与七组 ECharts 图表。
- 类型／品类条形图点击下钻；交叉热力图数量／行占比切换。
- SQL 分页、当前子集 UTF-8 BOM CSV 导出、空样本与请求错误提示、移动布局。
- 六项自动化测试、全规模验证、六组可复现实验与可选浏览器交互检查。

金额是模拟争议金额，办结占比不是满意度；平台堆叠图是平台内部投诉类型结构，不能解释为投诉发生率。月频数补零仅适用于本演示源的完整覆盖。

## 目录与数据产物

```text
config.py              路径、观察范围与分类字典
generate_demo.py       可复现生成器
prepare_data.py        校验、隔离、去重与数据库装载
analysis.py            统一筛选、SQL 分页与统计指标
app.py                 HTTP API 与静态页面
verify.py              全规模统计／SQL／接口一致性验证
requirements.txt       方案规定的直接依赖
requirements.lock      本环境验证过的完整固定版本
static/                页面、样式、交互与本地 ECharts
scripts/               安装、启动、实验与浏览器检查
tests/                 临时数据目录中的自动化测试
docs/                  原始方案与验证记录
data/                  默认演示产物（生成文件，不纳入 Git）
results/               实验及截图（生成文件，不纳入 Git）
```

默认数据：原始 12,040 行 = 清洗后 12,010 + 隔离 10 + 重复 20；清洗后包含 10 条未知品类。产物包括 `raw_demo.csv`、`clean_demo.csv`、`rejected.csv`、`generation.json`、`quality.json` 和 `complaints.db`。

可用 `COMPLAINT_DATA_DIR` 指定独立数据目录，生成器、清洗器和服务都读取该变量。真实数据应使用单独适配器和目录，当前清洗器仅接受 `demo-v1` 模拟消费者投诉，不接受真实汇总或真实明细。

## API

| 路径 | 功能 |
| --- | --- |
| `/` | 可视化首页 |
| `/api/meta` | 来源、覆盖范围、字典、生成参数、质量日志 |
| `/api/dashboard` | 同一筛选子集的指标与七组图表数据 |
| `/api/records` | SQL 分页明细，默认每页 10 条、最多 100 条 |
| `/api/export` | 当前子集 CSV |
| `/docs` | 自动接口文档（其界面资源可能需要外网） |

三个数据查询接口共用 `year`、`platform`、`category`、`issue_type` 筛选参数；明细增加 `page` 与 `page_size`。非法参数返回 422，数据未初始化返回 503。SQL 使用绑定参数。

## 验证与实验

```bash
.venv/bin/python verify.py
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/experiments.py
```

实验脚本在 `results/` 分别保存种子 42／43／44 × baseline／promotion 的原始、清洗、数据库、质量日志及统计 JSON；每组重新生成核对哈希，再测量 20 次后端 `elapsed_ms` 的中位数与 P95。它不修改默认 `data/`。promotion 是人为增加 7 月、12 月抽样权重的场景，不提供促销因果证据。

可选浏览器检查需要另行提供 Playwright 和 Chromium，在服务启动后运行 `node scripts/browser_smoke.cjs`。支持 `APP_BASE_URL`、`CHROMIUM_PATH`、`SCREENSHOT_DIR`；这些工具仅用于网页验证，非运行依赖。

## 范围与后续工作

当前实现方案中的入门版本。真实数据授权与导入审核、多来源批次、真实汇总背景页、同比／百分点／日均量、卡方与效应量分析列为后续扩展。未实现在线投诉受理、爬虫、登录或线上托管。统计接口用 Pandas 处理筛选明细，适用于当前约 1.2 万条教学数据；SQL 分页已避免读取全部明细再切片。

云环境使用已有隔离 checkout，无需建立额外 Git worktree。安装与启动说明保存在环境配置草稿中，保存草稿不等于发布环境。仓库初始为空；生成的数据、实验结果与虚拟环境不纳入 Git，克隆后按快速开始步骤重新生成。
