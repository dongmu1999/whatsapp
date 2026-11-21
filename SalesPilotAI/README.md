# SalesPilot AI V1.0

**中文名称：WhatsApp 外贸销售智能助手**

本项目是面向外贸销售人员的 Windows 本地桌面软件。软件仅提供聊天整理、销售分析和回复辅助，不自动发送消息、不读取 WhatsApp 私有数据库、不绕过登录或加密，也不进行后台持续监听。

> 当前严格交付 **阶段 1：基础项目**。后续功能页面会明确标注开发阶段，不使用静态业务数据或模拟 API 冒充已完成功能。

## 阶段 1 已完成

- PySide6 中文桌面主窗口，支持调整大小，适配 1366×768 及以上分辨率。
- 8 项主导航：工作台、AI 聊天分析、客户管理、客户历史记录、产品知识库、跟进任务、AI 模型设置、系统设置。
- 工作台真实统计：客户总数、今日分析次数、高意向客户数、待跟进客户数。
- 最近分析、最近沟通客户和待办任务查询；没有数据时显示空状态。
- 浅色/深色主题切换，主题选择保存到本地 SQLite。
- SQLite 初始化、WAL、外键、事务、索引、版本迁移和时间戳。
- 12 类基础业务表，以及客户、消息、知识文档的 FTS5 全文索引和同步触发器。
- 本地日志、数据目录隔离和中文启动错误提示。

## 尚未实现

阶段 2—9 的功能不在本次交付范围内，包括客户增删改查、WhatsApp/UIA/OCR 捕获、DeepSeek 调用、客户记忆、文档解析、跟进任务操作、备份恢复和 Windows 安装包。

## 运行环境

- Windows 10/11（目标运行平台）
- Python 3.12+
- PySide6 6.8+

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

## 项目结构

```text
SalesPilotAI/
├── main.py
├── requirements.txt
├── README.md
├── app/
│   ├── config.py
│   ├── database/
│   │   ├── connection.py
│   │   ├── migrations.py
│   │   ├── schema.py
│   │   └── repositories/
│   │       ├── dashboard_repository.py
│   │       └── settings_repository.py
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── dashboard.py
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
    ├── test_database.py
    └── test_ui.py
```

## 阶段 1 验证记录

验证日期：2026-11-21。

- Python 语法编译检查通过。
- 自动化测试：**14 passed**。
- `main.py` 完整启动与退出冒烟测试：退出码 **0**，数据库文件创建成功。
- 主窗口离屏渲染和界面预览检查通过。
- 验证环境：Linux、Python 3.14.8、PySide6 6.11.3、SQLite 3.45.1（FTS5 已启用）。

当前容器不是 Windows，因此不能声称已在真实 Windows、WhatsApp Business 或 Windows UI Automation 环境完成验收；这些验证必须在对应功能阶段和 Windows 环境中如实执行。
