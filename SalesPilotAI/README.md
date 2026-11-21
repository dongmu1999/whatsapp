# SalesPilot AI V1.0

**中文名称：WhatsApp 外贸销售智能助手**

面向外贸销售人员的 Windows 本地桌面软件。软件仅提供聊天整理、销售分析和回复辅助，不自动发送消息、不自动群发、不读取 WhatsApp 私有数据库、不绕过登录或加密，也不进行后台持续监听。

> 当前严格交付至 **阶段 5：客户记忆**。已实现安全配置与销售分析、客户历史聊天、长期记忆、AI 记忆建议人工确认和历史检索；阶段 6 产品知识库尚未开始。

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

## 阶段 4 已完成

### DeepSeek 配置与安全凭据

- 使用 OpenAI Python SDK 兼容模式调用 DeepSeek，默认 Base URL 为 `https://api.deepseek.com`。
- 默认模型 `deepseek-flash`、高级模型 `deepseek-v4-pro` 来自任务规范，二者均可编辑；实际可用名称以用户账户和 DeepSeek 官方当前列表为准。
- 可配置 Temperature、最大输出 Token 和 1—600 秒请求超时。
- API Key 通过 `keyring` 写入系统安全凭据库；Windows 目标环境使用系统凭据管理器，不回退到源码、SQLite 或明文配置。
- 设置页不回显已保存 Key；留空保存会保留原 Key，也可主动删除系统凭据。
- 连接测试在后台线程执行，显示模型、Token 和耗时；认证、余额、超时、网络、限流和服务错误均转换为中文提示。

### 销售分析与 JSON 安全

- `SalesAdvisorService` 使用外贸销售顾问提示词，分析最新消息翻译、真实意图及依据、情绪、采购需求、意向评分及证据、置信度、销售阶段、顾虑、价格敏感度、风险、机会、策略、下一步问题和跟进建议。
- 明确要求区分事实、合理推测和未知信息，不因询价直接判高意向，不把未知发送方猜成客户或销售，不擅自承诺价格、库存、MOQ、交期、认证、售后或付款条件。
- 使用 Pydantic 严格校验结构和字段范围；支持从代码围栏或夹杂说明文字的响应中安全提取 JSON。
- 首次结果无法解析或校验时仅进行一次修复重试；第二次仍失败则保留首次和重试原始响应，并记录失败分析。
- 每次 API 请求分别保存输入/输出/总 Token、耗时、模型、状态和错误类型；聊天网络请求不访问 SQLite，结果回到主线程后保存。

### 上传确认、三种回复与复制

- 点击分析后、任何聊天上传前，明确显示本次消息数、接口地址、所选模型和脱敏状态；取消时不新增会话、不调用 API。
- 默认启用手机号、邮箱和公司名脱敏，也可由用户明确关闭；分析范围仅限当前预览的可见消息。
- 确认后先在本地保存会话，相同预览再次分析会复用该会话；修改预览后再次分析则保存新版本。
- 每次成功分析必须包含 `professional`、`sales_driven`、`relationship_building` 三种且仅三种回复。
- 每条回复显示英文、中文翻译、策略和适用场景；英文可编辑并一键复制到剪贴板，软件不会代替用户发送。
- 可再次点击分析按钮重新生成，但仍需再次确认上传范围；不包含任何自动 WhatsApp 操作。

## 阶段 5 已完成

### 客户长期记忆与严格隔离

- 客户记忆保存在本地 `customer_memories` 表，按 `customer_id` 严格隔离；读取、修改、确认和删除都会同时校验客户，不能跨客户访问。
- 支持 15 类记忆：公司背景、业务范围、感兴趣产品、采购数量、目标价格、历史报价、价格敏感度、关键异议、核心顾虑、采购计划、沟通偏好、合作结果、重要承诺、后续机会和其他。
- 手动添加的记忆默认标记为“已确认”；支持修改分类与内容、删除，以及按客户查看记忆摘要。
- 客户记忆摘要只包含“已确认”记录，并按分类分组；待确认和已忽略内容不会进入摘要。

### AI 记忆建议必须人工确认

- 每次 AI 分析可在 `memory_suggestions` 中返回 0—5 条有证据的长期记忆建议；提示词明确禁止把推测、临时情绪或未经确认的承诺写入记忆。
- 建议以 `ai_suggested` + `pending` 状态写入本地，**不会自动成为正式记忆**；必须在客户历史页逐条“确认”或“忽略”。
- 确认后才进入正式记忆摘要；忽略记录保留状态用于审计，但不会出现在摘要中。
- 相同或仅大小写、空白不同的建议会去重；已忽略的内容仍可在后续分析中重新提出。
- 分析结果保存与记忆建议写入分开处理：记忆建议写入失败不会隐藏已经成功的分析结果。

### 客户历史聊天与检索

- 客户历史记录页按客户展示所有本地会话及消息数量，支持按会话标题或消息内容搜索。
- 搜索与消息查看都由 SQL 强制限定 `customer_id`，不会返回其他客户的历史。
- 历史聊天只读展示，不包含自动发送、批量发送或后台监听 WhatsApp 消息。

## 尚未实现

阶段 6—9 不在本次交付范围内，包括产品知识库导入与检索、跟进任务操作、备份恢复和 Windows 安装包。

## 运行环境

- Windows 10/11（目标运行平台）
- Python 3.12+
- PySide6 6.8+
- openpyxl 3.1+
- mss 9+
- pywinauto 0.6.8+（仅 Windows 自动安装）
- openai 1.50+（当前兼容约束为 `<3.0`）
- pydantic 2.9+
- keyring 25+

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

如果当前 Python 或平台没有兼容版本，请使用手动粘贴；不要通过不兼容的强制安装替代官方支持矩阵。OCR 本身在本地运行；只有用户在阶段 4 分析确认框中明确同意后，所选预览消息才会发送到配置的 DeepSeek 接口。

### 自动化测试

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Linux 无图形环境：

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

## 阶段 3—5 使用流程

1. 打开“AI 模型设置”，填写自己的 DeepSeek API Key，核对 Base URL 和账户可用模型，点击“安全保存设置”，再点击“测试连接”。测试会发送一条极短测试消息。
2. 打开 WhatsApp Desktop / Business，进入客户聊天并让需要整理的消息可见。
3. 在捕获设置中选择是否启用 UIA、OCR 和 WhatsApp Web 目标，设置消息数量和快捷键，点击“保存捕获设置”。
4. 回到 WhatsApp 后按快捷键，或在软件中点击“捕获当前聊天”。优先尝试 UIA，失败后按设置尝试 OCR。
5. 如果自动捕获不可用，使用框选截图、导入截图或手动粘贴。
6. 在预览中逐条核对文字、顺序和发送方，编辑或删除不需要的内容，并选择关联客户。
7. 仅需本地存档时点击“确认保存到本地”，此操作本身不会调用 AI。
8. 需要 AI 时保持或修改脱敏、模型选项，点击“确认范围并进行 AI 分析”。仔细阅读上传确认框；选择“No”不会上传，选择“Yes”才保存并发起请求。
9. 查看销售分析和三种回复，可直接修改英文后点击“复制英文回复”，再自行回到 WhatsApp 核对并发送。软件不会自动点击或发送。
10. 打开“客户历史记录”，选择客户查看记忆摘要、历史会话和搜索；AI 生成的记忆建议必须逐条“确认”或“忽略”。也可手动添加、修改和删除已确认记忆。

## 本地数据、截图与网络边界

Windows 默认数据库位置：

```text
%LOCALAPPDATA%\SalesPilotAI\salespilot.db
```

日志位于同目录的 `logs` 子目录。开发和测试可通过 `SALESPILOT_DATA_DIR` 指定隔离目录。

- 捕获截图使用系统临时目录，正常识别成功/失败路径都会立即尝试删除。
- 用户主动导入的原始截图仍由用户管理，软件不会删除。
- 客户、会话、分析、回复、客户记忆和 API 用量写入本地 SQLite；API Key 不写入该数据库。
- 客户记忆与历史检索完全在本地完成，不会因为打开该页面而调用 DeepSeek 或产生网络请求。
- 除用户主动执行的连接测试和明确确认的分析请求外，软件没有 AI 网络请求或遥测。
- 分析确认框会列出实际上传范围；脱敏只能降低部分敏感信息风险，用户仍应在确认前逐条检查预览。

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
│   │   ├── message.py          # 消息模型、解析、去重、数量整理
│   │   ├── analysis.py         # Pydantic 分析结构与 JSON 校验
│   │   ├── memory.py           # 记忆分类、结构与校验
│   │   └── history.py          # 客户历史会话与消息
│   ├── services/
│   │   ├── customer_service.py
│   │   ├── chat_capture_service.py
│   │   ├── conversation_service.py
│   │   ├── ai_settings_service.py
│   │   ├── deepseek_service.py
│   │   ├── sales_advisor_service.py
│   │   ├── memory_service.py
│   │   └── privacy.py
│   ├── database/
│   │   └── repositories/
│   │       ├── analysis_repository.py
│   │       ├── memory_repository.py
│   │       └── history_repository.py
│   └── ui/
│       ├── main_window.py
│       ├── chat_analysis_page.py
│       ├── ai_settings_page.py
│       ├── analysis_result.py
│       ├── customer_history_page.py
│       ├── workers.py          # 无 SQLite 操作的后台网络任务
│       ├── region_selector.py
│       ├── customer_page.py
│       └── settings_page.py
└── tests/
    ├── test_capture.py
    ├── test_conversation.py
    ├── test_chat_ui.py
    ├── test_ai_settings.py
    ├── test_deepseek.py
    ├── test_analysis.py
    ├── test_ai_ui.py
    ├── test_memory.py
    ├── test_memory_ui.py
    ├── test_customer.py
    ├── test_customer_ui.py
    ├── test_database.py
    └── test_ui.py
```

## 阶段 1—5 验证记录

验证日期：2026-11-21。

- Python `compileall` 语法编译检查通过。
- 自动化测试：**103 passed**，覆盖数据库、客户管理、聊天捕获、预览编辑、DeepSeek 参数与中文错误、安全凭据、脱敏、JSON 校验及一次修复重试、三种回复、分析成功/失败事务、逐请求用量、上传确认/取消、后台线程、客户记忆隔离、AI 建议待确认、去重、摘要分组、历史检索和主窗口集成。
- `main.py` 离屏完整启动与退出冒烟测试：退出码 **0**。
- 1366×768 离屏窗口中，8 项导航、聊天分析页、客户历史记录页、AI 模型设置页、阶段 5 标识和客户未选择时的空状态检查通过。
- `pip check`：**No broken requirements found**。
- 验证环境：Linux、Python 3.14.8、PySide6 6.11.3、openpyxl 3.1.5、mss 10.1.0、OpenAI SDK 2.54.0、Pydantic 2.13.4、keyring 25.7.0、SQLite FTS5。

### 真实平台与 API 验证限制

当前容器不是 Windows，没有真实 DeepSeek 凭据，也无真实 WhatsApp、屏幕会话或 PaddleOCR 环境。因此：

- **尚未**使用真实 DeepSeek 账户生成真实客户记忆建议；fake 测试只验证结构、去重和待确认流程，不证明线上模型会稳定输出有证据的建议。
- 客户记忆与历史检索的隔离、确认和去重已由自动化测试覆盖，但**尚未**在真实长期数据量和真实 Windows 界面下进行人工验收。
- **尚未**使用真实 DeepSeek 账户发起连接或聊天分析请求；fake SDK 测试不证明网络、账户余额、模型可用性或线上 JSON 兼容性已经验收。
- 规范给出的 `deepseek-flash` 和 `deepseek-v4-pro` 未在本环境独立验证；必须在设置页按账户实际可用模型修改。
- **尚未**在真实 Windows 凭据管理器中验证 API Key 的写入、读取和删除；自动化测试使用 fake 凭据库，生产代码不回退到明文。
- **尚未**在真实 Windows 10/11 上验收前台进程识别、UIA 元素树、全局快捷键注册和框选截图。
- **尚未**在真实 WhatsApp Desktop / Business / Web 上验证消息提取准确率和界面兼容性。
- **尚未**进行 PaddleOCR 实际模型推理和中英文识别准确率验收。
- 自动化测试通过 fake 适配器验证编排、降级、清理、请求参数和界面行为，不代表上述真实平台或云端能力已经验收。

真实 Windows 交付前仍需按使用流程逐项人工验收，尤其要检查系统凭据后端、DeepSeek 实际模型与 JSON 输出、不同 WhatsApp 版本的 UIA 文本结构、DPI/多显示器坐标和 OCR 安装兼容性。
