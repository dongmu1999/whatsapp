# SalesPilot AI V1.0

**中文名称：WhatsApp 外贸销售智能助手**

本项目是面向外贸销售人员的 Windows 本地桌面软件。软件仅提供聊天整理、销售分析和回复辅助，不自动发送消息、不读取 WhatsApp 私有数据库、不绕过登录或加密，也不进行后台持续监听。

> 当前严格交付至 **阶段 2：客户管理**。后续功能页面会明确标注开发阶段，不使用静态业务数据或模拟 API 冒充已完成功能。

## 阶段 1 已完成

- PySide6 中文桌面主窗口，支持调整大小，适配 1366×768 及以上分辨率。
- 8 项主导航：工作台、AI 聊天分析、客户管理、客户历史记录、产品知识库、跟进任务、AI 模型设置、系统设置。
- 工作台真实统计：客户总数、今日分析次数、高意向客户数、待跟进客户数。
- 最近分析、最近沟通客户和待办任务查询；没有数据时显示空状态。
- 浅色/深色主题切换，主题选择保存到本地 SQLite。
- SQLite 初始化、WAL、外键、事务、索引、版本迁移和时间戳。
- 12 类基础业务表，以及客户、消息、知识文档的 FTS5 全文索引和同步触发器。
- 本地日志、数据目录隔离和中文启动错误提示。

## 阶段 2 已完成

- 完整本地客户档案：姓名、公司、国家、联系方式、WhatsApp、邮箱、网站、客户类型、产品需求、数量、目标价格、历史报价、采购历史、销售阶段、意向评分、核心顾虑、备注及联系/跟进时间等全部字段。
- 真实 SQLite 新增、读取、更新和删除；编辑时保留未修改字段，保存时校验必填姓名、销售阶段、0—100 意向评分和 ISO 时间格式。
- 客户列表展示姓名、公司、国家、WhatsApp、销售阶段、意向评分、最近沟通和下次跟进时间；支持全字段详情查看。
- 按姓名、公司、联系方式、WhatsApp、邮箱和感兴趣产品进行模糊搜索，并支持国家、销售阶段组合筛选。
- 支持按意向评分或最近沟通时间升序/降序排列，空沟通时间排在最后。
- 新增/编辑对话框、只读详情、删除二次确认；删除客户时通过外键级联删除其聊天、分析、记忆和跟进记录。
- CSV 和 Excel（`.xlsx`/`.xlsm`）导入导出，支持中文表头和英文字段名；逐行报告导入错误，合法行不会被其他错误行阻断。
- 导出当前搜索/筛选后的客户列表；客户变更后自动刷新工作台统计。
- 中文错误提示、操作状态消息、空列表/无结果状态，浅色和深色主题均已适配。

## 尚未实现

阶段 3—9 的功能不在本次交付范围内，包括 WhatsApp/UIA/OCR 捕获、DeepSeek 调用、客户记忆、文档解析、跟进任务操作、备份恢复和 Windows 安装包。软件仍不会自动发送 WhatsApp 消息。

## 运行环境

- Windows 10/11（目标运行平台）
- Python 3.12+
- PySide6 6.8+
- openpyxl 3.1+

### Windows 启动

在项目目录执行：

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

如果 PowerShell 禁止激活虚拟环境，可直接执行：

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

### 自动化测试

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Linux 无图形环境下可使用：

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

## 本地数据

Windows 默认数据库位置：

```text
%LOCALAPPDATA%\SalesPilotAI\salespilot.db
```

日志位于同目录的 `logs` 子目录。开发和自动化测试可通过 `SALESPILOT_DATA_DIR` 环境变量指定隔离目录。数据库文件、日志和环境变量文件均已加入 `.gitignore`。

## 客户导入导出格式

- 点击“导入客户”选择 CSV 或 Excel 文件。第一行必须是表头，“客户姓名”为必需列，其余客户字段可选。
- 表头可使用界面中文名称（如“公司名称”“意向评分”）或数据库英文字段名（如 `company_name`、`intent_score`）。
- CSV 按 UTF-8 with BOM 优先读取，并兼容 GB18030；Excel 使用第一个工作表。
- 时间可填写 ISO 文本（如 `2026-11-21T09:30:00Z`）；Excel 日期时间单元格也可读取，未带时区的时间按 UTC 处理。
- 导入结束后显示成功/失败条数及具体行号错误。导出文件包含全部客户字段，范围为当前列表显示的客户。

## 项目结构

```text
SalesPilotAI/
├── main.py
├── requirements.txt
├── README.md
├── app/
│   ├── config.py
│   ├── models/customer.py
│   ├── services/customer_service.py
│   ├── database/
│   │   ├── connection.py
│   │   ├── migrations.py
│   │   ├── schema.py
│   │   └── repositories/
│   │       ├── customer_repository.py
│   │       ├── dashboard_repository.py
│   │       └── settings_repository.py
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── dashboard.py
│   │   ├── customer_page.py
│   │   ├── customer_detail.py
│   │   ├── placeholder_page.py
│   │   ├── settings_page.py
│   │   └── theme.py
│   └── utils/logger.py
├── assets/styles/
│   ├── light.qss
│   └── dark.qss
└── tests/
    ├── conftest.py
    ├── test_config.py
    ├── test_customer.py
    ├── test_customer_ui.py
    ├── test_database.py
    └── test_ui.py
```

## 阶段 1—2 验证记录

验证日期：2026-11-21。

- Python `compileall` 语法编译检查通过。
- 自动化测试：**31 passed**，覆盖数据库、客户 CRUD、校验、搜索筛选排序、关联删除、CSV/Excel 往返导入导出、错误行报告、客户 UI 和主窗口集成。
- `main.py` 完整启动与退出冒烟测试：退出码 **0**，隔离数据库文件创建成功。
- 客户管理主窗口离屏渲染和界面预览检查通过。
- `pip check` 依赖一致性检查通过。
- 验证环境：Linux、Python 3.14.8、PySide6 6.11.3、openpyxl 3.1.5、SQLite FTS5 已启用。

当前容器不是 Windows，因此不能声称已在真实 Windows、WhatsApp Business 或 Windows UI Automation 环境完成验收；这些验证必须在对应功能阶段和 Windows 环境中如实执行。
