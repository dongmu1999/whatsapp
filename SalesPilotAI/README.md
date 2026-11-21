# SalesPilot AI V1.0

**中文名称：WhatsApp 外贸销售智能助手**

面向外贸销售人员的 Windows 本地桌面软件。软件仅提供聊天整理、销售分析和回复辅助，不自动发送消息、不自动群发、不读取 WhatsApp 私有数据库、不绕过登录或加密，也不进行后台持续监听。

> 当前严格交付至 **阶段 3：WhatsApp 聊天捕获**。本阶段不调用 DeepSeek，不生成 AI 分析或回复建议。

## 阶段 1 已完成

- PySide6 中文桌面主窗口、8 项主导航、浅色/深色主题及本地主题设置。
- 工作台真实统计、最近分析、最近沟通客户和待办任务查询。
- SQLite 初始化、WAL、外键、显式事务、索引、版本迁移和时间戳。
- 客户、会话、消息等基础业务表，以及客户、消息和知识文档 FTS5 索引。
- 本地日志、数据目录隔离和中文启动错误提示。

## 阶段 2 已完成

- 完整本地客户档案的新增、读取、编辑、删除和详情查看。
- 姓名、公司、联系方式、WhatsApp、邮箱和感兴趣产品搜索；国家和销售阶段组合筛选。
- 意向评分或最近沟通时间升序/降序排列。
- 删除客户时通过外键级联处理聊天、分析、记忆和跟进记录。
- CSV 和 Excel（`.xlsx`/`.xlsm`）导入导出、中文/英文表头、逐行错误报告。
- 客户变更后刷新工作台统计。

## 阶段 3 已完成

### 主动捕获与安全边界

- 默认全局快捷键 `Ctrl+Shift+A`，可在“AI 聊天分析”页的捕获设置中修改并保存。
- Windows 使用 `RegisterHotKey` 等待用户快捷键；快捷键只触发一次捕获，不监听消息内容。
- 前台窗口识别支持 WhatsApp Desktop / Business；勾选后才允许 WhatsApp Web 浏览器窗口。
- 非目标窗口会提示先切换到 WhatsApp，不会继续读取。
- 不提供自动发送、自动点击、非官方协议、私有数据库读取或后台消息监听。

### UIA、OCR 与手动备用

- Windows UI Automation 只读适配：获取可访问的窗口标题、文本元素、消息顺序及可获得的聊天区域。
- UIA 无结果或失败时可降级到 OCR；也可直接使用“窗口截图 OCR”或“框选截图 OCR”。
- 使用 `mss` 截取当前窗口或用户框选区域；临时截图在识别成功或失败后均由 `finally` 流程清理。
- OCR 使用可替换接口，已提供延迟加载的 PaddleOCR 2.x 适配器；未安装 OCR 不影响程序启动及手动流程。
- 支持导入 PNG、JPG、BMP、WebP 聊天截图；用户原始图片不会被移动或删除。
- 支持剪贴板粘贴和直接输入。可解析常见 WhatsApp 导出时间前缀、带姓名消息及带时间戳消息的换行。
- 可使用“客户：”“销售：”等明确前缀标记发送方；未知姓名或仅凭 OCR 左右位置时不猜测，统一标记“未知”。

### 消息整理、预览与本地保存

- 默认整理最近 30 条，可在 20—50 条之间设置；保持原顺序，只去除相邻重复项，避免误删不同时间重复发送的正常消息。
- 保留原始英文、消息来源、识别时间、消息时间及 OCR 置信度。
- 页面始终提示“可见消息，可能不完整”，不会冒充完整聊天历史。
- 预览表格支持编辑消息内容、修改客户/销售/未知发送方、删除敏感行和重新捕获。
- 可选择已有客户或直接新建客户；确认后才在一个 SQLite 事务中写入 `conversations` 和 `messages`，并同步消息 FTS5 索引。
- 捕获只进入预览，不会自动保存；保存只写入本地，不调用 AI，也不发送 WhatsApp 消息。

## 尚未实现

阶段 4—9 不在本次交付范围内，包括 DeepSeek 调用、AI 销售分析、回复建议、客户长期记忆、知识库操作、跟进任务操作、备份恢复和 Windows 安装包。

## 运行环境

- Windows 10/11（目标运行平台）
- Python 3.12+
- PySide6 6.8+
- openpyxl 3.1+
- mss 9+
- pywinauto 0.6.8+（仅 Windows 自动安装）

### Windows 启动

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

如果 PowerShell 禁止激活虚拟环境：

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

### 可选 OCR 组件

OCR 依赖体积较大，因此没有强制加入基础依赖。需要 OCR 时，请根据 Paddle 官方 Python/平台支持矩阵安装 **PaddleOCR 2.x** 和匹配的 PaddlePaddle，例如：

```powershell
.venv\Scripts\python.exe -m pip install "paddleocr>=2.7,<3.0" paddlepaddle
```

如果当前 Python 或平台没有兼容版本，请使用手动粘贴；不要通过不兼容的强制安装替代官方支持矩阵。OCR 在本地运行，本阶段不会把聊天发送到任何 AI 服务。

### 自动化测试

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Linux 无图形环境：

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

## 阶段 3 使用流程

1. 打开 WhatsApp Desktop / Business，进入客户聊天并让需要整理的消息可见。
2. 在捕获设置中选择是否启用 UIA、OCR 和 WhatsApp Web 目标，设置消息数量和快捷键，点击“保存捕获设置”。
3. 回到 WhatsApp 后按快捷键，或在软件中点击“捕获当前聊天”。优先尝试 UIA，失败后按设置尝试 OCR。
4. 如果自动捕获不可用，使用框选截图、导入截图或手动粘贴。
5. 在预览中逐条核对文字、顺序和发送方，编辑或删除不需要的内容。
6. 选择客户并点击“确认保存到本地”。阶段 3 到此结束，不会发起 AI 请求。

## 本地数据与截图

Windows 默认数据库位置：

```text
%LOCALAPPDATA%\SalesPilotAI\salespilot.db
```

日志位于同目录的 `logs` 子目录。开发和测试可通过 `SALESPILOT_DATA_DIR` 指定隔离目录。

- 捕获截图使用系统临时目录，正常识别成功/失败路径都会立即尝试删除。
- 用户主动导入的原始截图仍由用户管理，软件不会删除。
- 客户和消息仅写入本地 SQLite；本阶段没有 AI 网络请求或遥测。

## 项目结构

```text
SalesPilotAI/
├── main.py
├── requirements.txt
├── README.md
├── app/
│   ├── capture/
│   │   ├── windows.py          # 前台窗口与 UIA 只读适配
│   │   ├── ocr.py              # mss、PaddleOCR 与 OCR 行整理
│   │   ├── hotkey.py           # Windows 全局快捷键
│   │   ├── models.py
│   │   └── errors.py
│   ├── models/
│   │   ├── customer.py
│   │   └── message.py          # 消息模型、解析、去重、数量整理
│   ├── services/
│   │   ├── customer_service.py
│   │   ├── chat_capture_service.py
│   │   └── conversation_service.py
│   ├── database/
│   └── ui/
│       ├── main_window.py
│       ├── chat_analysis_page.py
│       ├── region_selector.py
│       ├── customer_page.py
│       └── settings_page.py
└── tests/
    ├── test_capture.py
    ├── test_conversation.py
    ├── test_chat_ui.py
    ├── test_customer.py
    ├── test_customer_ui.py
    ├── test_database.py
    └── test_ui.py
```

## 阶段 1—3 验证记录

验证日期：2026-11-21。

- Python `compileall` 语法编译检查通过。
- 自动化测试：**58 passed**，覆盖数据库、客户管理、解析与去重、发送方未知原则、窗口目标判断、UIA→OCR 降级、临时截图清理调用、快捷键校验、事务保存、消息 FTS、预览编辑和主窗口集成。
- `main.py` 离屏完整启动与退出冒烟测试：退出码 **0**。
- 聊天捕获页离屏渲染成功，窗口可调整并带滚动区域。
- `pip check`：**No broken requirements found**。
- 验证环境：Linux、Python 3.14.8、PySide6 6.11.3、openpyxl 3.1.5、mss 10.1.0、SQLite FTS5。

### 真实平台验证限制

当前容器不是 Windows，且无真实 WhatsApp、屏幕会话或 PaddleOCR 环境。因此：

- **尚未**在真实 Windows 10/11 上验收前台进程识别、UIA 元素树、全局快捷键注册和框选截图。
- **尚未**在真实 WhatsApp Desktop / Business / Web 上验证消息提取准确率和界面兼容性。
- **尚未**进行 PaddleOCR 实际模型推理和中英文识别准确率验收。
- 自动化测试通过 fake 适配器验证编排、降级和清理行为，不代表上述真实平台能力已经验收。

真实 Windows 交付前仍需按使用流程逐项人工验收，尤其要检查不同 WhatsApp 版本下 UIA 文本结构、DPI/多显示器坐标和 OCR 安装兼容性。
