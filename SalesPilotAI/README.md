# SalesPilot AI V1.0

**中文名称：WhatsApp 外贸销售智能助手**

面向外贸销售人员的 Windows 本地桌面软件。软件仅提供聊天整理、销售分析和回复辅助，不自动发送消息、不自动群发、不读取 WhatsApp 私有数据库、不绕过登录或加密，也不进行后台持续监听。

> 当前严格交付至 **阶段 9：Windows 打包**。已提供 PyInstaller onedir 打包配置、Inno Setup 与 NSIS 简体中文安装/卸载脚本、首次启动引导、打包后自检模式和 Windows 一键构建脚本；当前工作区已生成 Windows x64 EXE（`dist/SalesPilotAI/SalesPilotAI.exe`）和安装包（`dist/installer/SalesPilotAI-Setup-1.0.0.exe`）。

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
- 支持 15 类记忆：客户公司背景、客户经营业务、感兴趣产品、采购数量、目标价格、历史报价、价格敏感度、重要异议、核心顾虑、采购计划、沟通偏好、历史合作结果、重要承诺、下一步销售机会和其他。
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

## 阶段 6 已完成

### 文档导入、解析与本地来源追踪

- 支持导入 PDF、Word（`.docx`）、Excel（`.xlsx`）、CSV、TXT 和 Markdown，单文件限制 20 MB。
- PDF 使用 `pypdf` 逐页提取文本；Word 使用 `python-docx` 读取段落和表格；Excel 使用 `openpyxl` 读取工作表和单元格；CSV 自动识别常见分隔符和 UTF-8/GB18030 编码。
- 扫描版 PDF 或图片型 PDF 未提取到文字时给出中文提示；本阶段不集成 PDF OCR，用户需先提供文本版文件。
- 导入文件会复制到本地数据目录的 `knowledge` 子目录，并以 SHA-256 校验值命名；原始文件不会被修改、移动或删除。
- 相同内容文件默认拒绝重复导入；更新文件会重新解析正文、替换校验值并重建检索索引，同时清理旧的本地副本。
- 删除文档只删除数据库记录、全文索引和本地知识库副本，不影响用户原始文件。
- 每份文档保留来源文件名、标题、分类、文件类型、校验值和导入时间，可在界面中预览全文。
- 支持自定义分类、按分类筛选，以及结构化产品资料的名称、型号、分类、规格、功能、价格、MOQ、包装、交期、认证、付款、物流、售后、OEM/ODM 和 FAQ 维护。

### 本地全文检索与相关性控制

- 阶段 6 数据库迁移将知识库索引替换为 SQLite FTS5 `trigram` 分词，支持中文和英文关键词检索，并按 BM25 排序；短关键词自动回退到本地 `LIKE` 检索。
- 可搜索文件名、标题、分类和正文，并可叠加分类筛选；所有检索均在本地完成，打开知识库页面不产生网络请求。
- AI 分析前仅从**客户消息**中提取关键词，检索最多 5 条相关知识片段；不会上传整个知识库。
- 上传确认框会显示本次检索到的知识片段数量；传入模型的只有这些片段及其来源文件，不包含其他资料。
- 提示词要求模型区分“知识库确认的信息”“客户提供的信息”和“AI 推测的信息”，不得把客户说法或推测描述成知识库内容，也不得扩写资料未写明的价格、MOQ、交期、认证或售后条件。
- 分析结果新增“知识库引用”，列出本次实际引用的来源文件和事实；未引用时明确提示客户说法与 AI 推测不能视为已确认资料。

## 阶段 7 已完成

### 本地跟进任务

- 可为每个客户创建跟进任务，填写计划日期、时间、跟进原因、优先级（低/中/高）和跟进内容。
- 时间由本地时区选择，数据库统一保存为 UTC，界面按本机时区显示，避免夏令时和时区切换后顺序错乱。
- 任务状态严格为待办、已完成、已取消；已完成和已取消任务不能重复完成、记录结果或再次取消。
- 支持在待办状态记录阶段性跟进结果，任务仍保持待办；完成时可一并保存最终结果。
- 支持按客户和状态筛选，逾期任务在列表中标记为“逾期”，并按待办优先、计划时间升序排列。
- 任务、结果和状态全部保存在本地 SQLite，不写入聊天记录，也不会触发 WhatsApp 操作。

### AI 跟进建议

- 分析结果新增建议跟进天数（0—30 天）；分析结果页显示跟进建议，并提供“根据建议创建跟进任务”按钮。
- 点击按钮只会把客户、建议时间和内容填入跟进表单，仍需用户核对并手动创建；软件不会自动创建任务或发送消息。
- 没有 AI 建议时也可手动创建任务；AI 建议为空或未给出天数时默认按 3 天填写。

### 本地提醒

- 软件运行期间每 60 秒检查一次逾期和今日到期任务，并在状态栏显示“X 项已逾期，Y 项今日到期”。
- 提醒只在软件界面内展示，不调用系统通知、不常驻后台、不监控 WhatsApp。
- 工作台同时展示待办和即将到期的跟进任务；关闭软件后不会提醒，重新打开后会重新计算。

## 阶段 8 已完成

### 数据备份与校验恢复

- “系统设置”页新增“备份与恢复”卡片，可选择并持久化备份目录；默认目录为数据目录下的 `backups` 子目录。
- 备份为 ZIP 文件，命名如 `salespilot-backup-20261121-153000.zip`，包含 `manifest.json`、`salespilot.db` 和 `knowledge/*` 知识库文件副本；同一秒内重复备份会自动追加序号。
- 备份使用 SQLite 在线备份接口生成一致快照，再写入 SHA-256、数据库大小、格式版本、软件版本、数据库结构版本和知识库文件数，避免直接复制正在写入的 WAL 数据库。
- 恢复前先校验 ZIP 是否合法、是否包含清单和数据库、是否含绝对路径或 `..` 路径、解压后总体积是否超限、数据库哈希是否一致、`PRAGMA integrity_check` 是否通过，以及核心数据表是否齐全。
- 备份格式版本或数据库结构版本高于当前软件时拒绝恢复，并给出中文原因，避免新版本数据被旧软件破坏。
- 校验通过后先自动创建一份 `salespilot-pre-restore-*.zip` 安全备份，再替换数据库和知识库文件；数据库替换完成后重新建立连接并执行迁移检查。
- 恢复过程中任一步失败会回滚恢复前的数据库和知识库目录，并保持软件可用；错误写入本地日志，界面显示中文提示，不会直接崩溃。
- 备份包不包含系统安全凭据库中的 API Key，也不包含用户导入的原始文件；ZIP 本身**未加密**，其中含客户数据，需由用户自行保护备份文件。

### 隐私设置与数据保留

- 可设置聊天保留期限（0 天表示永久保留，最大 3650 天）；启动软件时会自动清理超过期限的会话及其消息，客户档案、分析和客户记忆不会因此删除。
- 可在设置页立即清理过期聊天，或清理系统临时目录中超过 24 小时的 `salespilot-capture-*.png` 截图；用户自己导入的原始图片不会被删除。
- “清空全部数据”会删除客户、聊天、消息、分析、回复建议、客户记忆、知识库文档与文件副本、产品资料、跟进任务和 API 用量记录，保留系统设置、主题和数据库迁移记录。
- 清理、恢复和清空操作均有中文确认提示；取消确认不会修改任何数据。测试可直接调用无确认参数的方法，避免自动化测试弹出模态框。

### 日志与异常处理

- 本地日志统一写入数据目录的 `logs/salespilot.log`，使用 2 MB 轮转、保留 3 个历史文件；只记录应用日志，不记录聊天正文、API Key 或备份内容。
- 备份成功、恢复成功、恢复失败与回滚、按期限清理聊天、清理临时截图和清空数据都会写入日志。
- 主程序安装全局未捕获异常钩子：记录完整堆栈并显示中文错误提示；主窗口创建失败或数据库初始化失败时给出中文说明并返回非零退出码。

### 设置页与界面

- 设置页改为可滚动布局，1366×768 及更小窗口下仍可访问全部卡片。
- 版本标识更新为“阶段 8”，恢复或清空数据后自动刷新工作台、聊天分析、客户、历史、知识库、跟进和设置页，避免继续显示旧数据。

## 阶段 9 已完成

### Windows EXE 与安装程序

- 提供 PyInstaller **onedir** 配置 `packaging/SalesPilotAI.spec`，入口为 `main.py`，输出 `dist/SalesPilotAI/SalesPilotAI.exe` 及 `_internal` 运行时目录。
- 当前工作区已用 Wine64 + Windows Python 3.12.10 + PySide6 6.8.3 实际生成 Windows x64 EXE：PE32+ GUI、约 11 MB，完整目录约 120 MB，版本资源 1.0.0 和应用图标已核验。
- 打包时包含 `assets`（主题 QSS 与图标），使用 `sys._MEIPASS` 定位只读资源；用户数据库、日志、备份和知识库仍写入独立数据目录，不写入安装目录。
- 排除 PaddleOCR/PaddlePaddle、PyTorch、pytest、其他 Qt 绑定等可选或开发组件；OCR 仍按需延迟导入，未安装时不影响手动粘贴与本地保存。
- 提供 Inno Setup 6.5+ 简体中文安装脚本 `packaging/installer.iss`，以及可由 Linux 直接交叉编译的 NSIS 脚本 `packaging/installer.nsi`：两者均按当前用户安装、无需管理员权限，创建开始菜单快捷方式、可选桌面快捷方式和卸载程序。
- 当前安装包由 Linux 原生 `makensis` 3.09 编译 `packaging/installer.nsi` 生成；NSIS 安装器本身是 32 位引导程序，但可在 64 位 Windows 10/11 的 WOW64 子系统中正常运行。
- 卸载程序删除安装目录中的应用文件，但**不删除** `%LOCALAPPDATA%\SalesPilotAI` 下的客户数据库、日志、备份、知识库副本和凭据；需要彻底删除时应先在软件内使用“清空全部数据”并手动处理数据目录。
- 安装包已生成至 `dist/installer/SalesPilotAI-Setup-1.0.0.exe`（约 39 MB），包含 EXE 版本信息、应用图标、主程序、`_internal` 运行时和卸载程序。
- Inno Setup 的 `ISCC.exe` 是 32 位程序，当前 Linux 内核未启用 32 位执行，无法运行；因此本次使用 Linux 原生 NSIS 生成安装包，Inno 配置保留给 Windows 构建机。
- 新增 `scripts/build_windows.ps1` 与 `scripts/build_windows.bat`：创建独立构建虚拟环境、安装依赖、运行测试、执行 PyInstaller、以 `--smoke-test` 启动打包后的 EXE 并检查数据库初始化，最后调用 ISCC 生成安装包。
- Linux 交叉构建命令：`makensis -DMyAppVersion=1.0.0 -DSourceDir=dist/SalesPilotAI -DOutputFile=dist/installer/SalesPilotAI-Setup-1.0.0.exe -DIconFile=assets/salespilot.ico packaging/installer.nsi`。

### 首次启动与本地数据库

- 主程序启动时继续自动创建数据目录、初始化 SQLite、执行迁移并记录日志；打包后首次启动无需预置数据库。
- 首次启动显示非模态中文引导，说明配置 DeepSeek API Key、WhatsApp 捕获快捷键 `Ctrl+Shift+A`、分析确认和本地备份；点击“开始配置 API Key”会跳转到“AI 模型设置”，点击“稍后设置”可在下次启动再次查看。
- 完成引导后写入 `onboarding_completed` 设置；备份恢复会保留或恢复该设置，不会反复打扰用户。
- 新增 `--smoke-test` 启动参数：创建窗口、初始化数据库并处理事件后自动退出，供打包脚本在真实 Windows 上验证 EXE 可启动；该模式不显示首次引导和全局异常弹窗。

### 构建与验证边界

- 本次在 Linux 环境完成了 PyInstaller onedir 实际构建，并用打包产物执行 `--smoke-test`，验证入口、Qt 依赖、资源定位和数据库初始化。
- 另外通过 Wine64 + Windows Python 3.12.10 + PySide6 6.8.3 + PyInstaller 6.17.0 生成了 Windows x64 EXE；PySide6 6.8.3 不依赖 Wine 缺失的 `icuuc.dll`，打包产物的 `--smoke-test` 在 Wine 中返回 0，并成功创建 `salespilot.db` 与日志。**尚未在真实 Windows 上运行。**
- PyInstaller **不能跨平台直接生成 Windows EXE**，本次通过 Wine64 运行 Windows Python 实现；安装包则由 Linux 原生 `makensis` 编译 `packaging/installer.nsi` 生成，不依赖 Wine32。
- 当前 NSIS 安装器是 32 位引导程序，而本机内核未启用 32 位执行，因此**没有在本环境运行安装/卸载流程**；需在真实 Windows 10/11 上双击安装、检查快捷方式和卸载程序。
- 源码测试覆盖打包文件存在性、版本一致性、安装器中文/按用户/保留用户数据、spec 资源与排除项、冻结资源路径、`--smoke-test` 数据库初始化及首次引导流程；168 项测试通过。Windows 安装/卸载本身仍需真实 Windows 人工验收。

## 尚未实现

- 仓库当前附带已生成的 Windows x64 EXE 目录（`dist/SalesPilotAI`）和 NSIS 安装包（`dist/installer/SalesPilotAI-Setup-1.0.0.exe`）；安装/卸载流程仍需在 Windows 10/11 上人工验收。
- 代码签名、自动更新、崩溃上报、系统托盘常驻和安装包多语言尚未实现；未签名的 EXE 可能触发 Windows SmartScreen 提示。

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
- pypdf 5.0+（当前兼容约束为 `<7.0`）
- python-docx 1.1+

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

PyInstaller 安装包默认在 `packaging/SalesPilotAI.spec` 中排除 PaddleOCR/PaddlePaddle 以控制体积。若需要安装版支持 OCR，必须在 Windows 构建机安装匹配的 OCR 依赖，并从 `excludes` 中移除相应模块后重新打包；否则安装版仍可使用手动粘贴和本地保存。

### 自动化测试

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Linux 无图形环境：

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

## Windows 打包与安装

### 构建环境

- Windows 10/11 x64
- Python 3.12 或更高版本
- Inno Setup 6.5 或更高版本（安装后提供 `ISCC.exe`）
- 构建机可访问 Python 包源，用于安装 `requirements.txt` 与 `requirements-build.txt`

### 一键构建

在项目根目录打开 PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

也可双击或运行：

```powershell
scripts\build_windows.bat
```

脚本会依次创建 `.venv-build` 构建环境、安装运行与打包依赖、执行全部自动化测试、调用 PyInstaller、用 `--smoke-test` 启动打包后的 EXE 并检查数据库初始化，最后调用 Inno Setup 生成安装包。

产物：

```text
dist\SalesPilotAI\SalesPilotAI.exe          # 绿色版 EXE（需同目录 _internal）
dist\installer\SalesPilotAI-Setup-1.0.0.exe # 简体中文安装程序
```

常用参数：

```powershell
# 只构建 EXE，不生成安装包
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -SkipInstaller

# 调试时复用已有构建环境
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -ReuseVenv
```

`-SkipTests` 仅用于本地调试打包配置，正式交付不应跳过测试。若构建失败，脚本返回非零退出码，不会把旧安装包误报为成功。

### 手动构建（排查问题）

```powershell
py -3.12 -m venv .venv-build
.venv-build\Scripts\python.exe -m pip install -r requirements.txt -r requirements-build.txt
.venv-build\Scripts\python.exe -m pytest -q
.venv-build\Scripts\python.exe -m PyInstaller --noconfirm --clean packaging\SalesPilotAI.spec

$env:SALESPILOT_DATA_DIR = "$env:TEMP\SalesPilotAI-smoke"
dist\SalesPilotAI\SalesPilotAI.exe --smoke-test

& "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe" `
  /DMyAppVersion=1.0.0 `
  /DSourceDir="$PWD\dist\SalesPilotAI" `
  /DOutputDir="$PWD\dist\installer" `
  packaging\installer.iss
```

### 安装与卸载

- 安装程序为当前用户安装，默认目录为 `%LOCALAPPDATA%\Programs\SalesPilotAI`，无需管理员权限。
- 安装器创建开始菜单快捷方式，桌面快捷方式为可选任务；卸载入口位于开始菜单。
- 卸载只删除安装目录中的程序文件，不删除 `%LOCALAPPDATA%\SalesPilotAI` 下的数据库、日志、备份、知识库副本和 Windows 凭据。
- 如需彻底清除，先在软件“系统设置”中使用“清空全部数据”，再手动删除数据目录。
- 安装包和 EXE 当前**未做代码签名**，Windows SmartScreen 可能提示“未知发布者”；正式分发前建议购买代码签名证书。

## 阶段 3—9 使用流程

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
11. 打开“产品知识库”，填写可选分类后导入 PDF、DOCX、XLSX、CSV、TXT 或 Markdown；选中文档可预览全文和来源信息。相同内容不会重复导入，更新文件需选择新版本。
12. 可维护结构化产品资料（价格、MOQ、交期、认证等）并按名称、型号或分类搜索。知识库页面只做本地检索，不会自动上传资料。
13. 再次进行 AI 分析时，软件会从客户消息中检索最多 5 条相关片段，并在上传确认框中显示数量。模型只会收到这些片段；分析结果的“知识库引用”列出实际使用的来源。若资料不足，模型必须标为未知，不能编造。
14. 打开“跟进任务”，选择客户、日期、时间和优先级，填写原因与内容后创建。任务只在本地保存，不会发送 WhatsApp 消息。
15. 在任务列表中按客户或状态筛选；待办任务可“记录跟进结果”或“完成并保存结果”，不需要的任务可取消。逾期任务会标红并计入软件内提醒。
16. AI 分析提示需要跟进时，结果页可出现“根据建议创建跟进任务”。点击只会预填表单，必须由你核对时间并手动创建。
17. 打开“系统设置”，在“备份与恢复”中选择备份目录并点击“立即备份”。备份包含数据库和知识库文件副本，但不包含 API Key；ZIP 未加密，请自行保管。
18. 需要恢复时点击“从备份恢复”并选择 ZIP。仔细阅读确认提示；软件会先创建 `salespilot-pre-restore-*.zip` 安全备份，再校验和替换数据。恢复失败会回滚并显示中文原因。
19. 在“隐私与数据保留”中设置聊天保留期限，0 天表示永久保留。启动软件时会自动清理超过期限的会话及消息，客户档案、分析和客户记忆不受影响。
20. 可点击“立即清理过期聊天”或“清理临时截图”手动清理；需要彻底删除业务数据时使用“清空全部数据”。该操作保留主题、系统设置和数据库迁移记录，且不可撤销。
21. 首次启动会显示中文引导：可点击“开始配置 API Key”直接进入“AI 模型设置”，或点击“稍后设置”在下次启动再次查看。完成引导后不再重复弹出。
22. 安装版从开始菜单启动；卸载程序不会删除本地客户数据。打包后的 EXE 可用 `--smoke-test` 做启动自检，该模式不会显示首次引导。

## 本地数据、截图与网络边界

Windows 默认数据库位置：

```text
%LOCALAPPDATA%\SalesPilotAI\salespilot.db
```

日志位于同目录的 `logs` 子目录。开发和测试可通过 `SALESPILOT_DATA_DIR` 指定隔离目录。

安装版默认安装到 `%LOCALAPPDATA%\Programs\SalesPilotAI`，首次启动时自动创建上述数据目录；卸载程序不会删除数据目录，也不会删除 Windows 凭据库中的 API Key。

- 捕获截图使用系统临时目录，正常识别成功/失败路径都会立即尝试删除。
- 用户主动导入的原始截图仍由用户管理，软件不会删除。
- 客户、会话、分析、回复、客户记忆、知识库文档、结构化产品资料、跟进任务和 API 用量写入本地 SQLite；API Key 不写入该数据库。
- 导入的知识库文件副本保存在数据目录的 `knowledge` 子目录；用户原始文件不被移动或删除。
- 客户记忆与历史检索完全在本地完成，不会因为打开该页面而调用 DeepSeek 或产生网络请求。
- 知识库导入、解析、全文检索和预览完全在本地完成；打开知识库页面不会上传任何资料。
- 跟进任务、结果记录、完成/取消和到期提醒完全在本地完成；提醒只显示在软件状态栏，不调用系统通知，也不会触发 WhatsApp 操作。
- 备份目录默认位于数据目录的 `backups` 子目录，可在设置页修改并持久化。备份 ZIP 含客户数据但未加密，不包含系统安全凭据库中的 API Key。
- 恢复前会自动创建安全备份；恢复失败时软件尝试回滚数据库和知识库目录，并将错误写入本地日志。
- 聊天保留期限会在启动时自动执行；清空全部数据只删除业务数据和知识库文件副本，保留系统设置、主题和数据库迁移记录。
- 临时截图清理只删除系统临时目录中超过 24 小时的 `salespilot-capture-*.png`，不会删除用户导入的截图或原始知识库文件。
- 只有用户明确确认分析后，才会把聊天消息以及本次检索出的最多 5 条知识片段发送到配置的 DeepSeek 接口；不会上传整个知识库或未命中的文件。
- 除用户主动执行的连接测试和明确确认的分析请求外，软件没有 AI 网络请求或遥测。
- 分析确认框会列出实际上传范围；脱敏只能降低部分敏感信息风险，用户仍应在确认前逐条检查预览。

## 项目结构

```text
SalesPilotAI/
├── main.py
├── requirements.txt
├── requirements-build.txt      # Windows 打包工具（PyInstaller）
├── README.md
├── assets/
│   ├── salespilot.ico          # EXE 与安装程序图标
│   └── styles/
├── packaging/
│   ├── SalesPilotAI.spec       # PyInstaller onedir 配置
│   ├── installer.iss           # Inno Setup 6.5+ 中文安装脚本
│   ├── installer.nsi           # NSIS 中文安装脚本（可在 Linux 交叉编译）
│   ├── version_info.txt        # Windows EXE 版本资源
│   └── ChineseSimplified.isl   # 安装界面简体中文
├── scripts/
│   ├── build_windows.ps1       # 测试 → EXE → 自检 → 安装包
│   └── build_windows.bat
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
│   │   ├── knowledge.py        # 知识库文档、产品与片段模型
│   │   ├── followup.py         # 跟进任务、状态、优先级与时间转换
│   │   └── history.py          # 客户历史会话与消息
│   ├── services/
│   │   ├── customer_service.py
│   │   ├── chat_capture_service.py
│   │   ├── conversation_service.py
│   │   ├── ai_settings_service.py
│   │   ├── deepseek_service.py
│   │   ├── sales_advisor_service.py
│   │   ├── memory_service.py
│   │   ├── knowledge_parser.py  # PDF/Word/Excel/CSV/文本提取
│   │   ├── knowledge_service.py # 导入、去重、检索与产品维护
│   │   ├── followup_service.py  # 校验、状态流转与提醒查询
│   │   ├── backup_service.py    # ZIP 备份、校验、恢复与回滚
│   │   ├── data_maintenance_service.py # 保留期限、临时截图与清空数据
│   │   └── privacy.py
│   ├── database/
│   │   └── repositories/
│   │       ├── analysis_repository.py
│   │       ├── memory_repository.py
│   │       ├── knowledge_repository.py
│   │       ├── followup_repository.py
│   │       └── history_repository.py
│   └── ui/
│       ├── main_window.py
│       ├── chat_analysis_page.py
│       ├── ai_settings_page.py
│       ├── analysis_result.py
│       ├── customer_history_page.py
│       ├── knowledge_page.py   # 知识库导入、搜索、预览与产品维护
│       ├── followup_page.py    # 跟进创建、筛选与结果记录
│       ├── onboarding_dialog.py # 首次启动中文引导
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
    ├── test_knowledge.py
    ├── test_knowledge_ui.py
    ├── test_followup.py
    ├── test_followup_ui.py
    ├── test_customer.py
    ├── test_customer_ui.py
    ├── test_backup.py
    ├── test_maintenance.py
    ├── test_settings_ui.py
    ├── test_onboarding.py
    ├── test_packaging.py
    ├── test_database.py
    └── test_ui.py
```

## 阶段 1—9 验证记录

验证日期：2026-11-21。

- Python `compileall` 语法编译检查通过。
- 自动化测试：**167 passed**，覆盖数据库、客户管理、聊天捕获、预览编辑、DeepSeek 参数与中文错误、安全凭据、脱敏、JSON 校验及一次修复重试、三种回复、分析成功/失败事务、逐请求用量、上传确认/取消、后台线程、客户记忆隔离、AI 建议待确认、去重、摘要分组、历史检索、六类知识文件解析、重复/空文件/扫描 PDF 错误、全文与分类检索、更新/删除索引、旧库升级、相关知识检索、产品资料维护、知识库引用、跟进时间转换、状态流转、逾期/今日查询、AI 跟进草稿不自动创建、本地提醒、ZIP 备份清单与哈希、唯一命名、文件数据库与内存数据库恢复、知识库替换、恢复前安全备份、不安全路径/非法 ZIP/缺失清单/哈希不一致/过高版本拒绝、失败不改数据、数据库重连、保留期限校验与过期会话清理、临时截图清理、清空全部业务数据保留设置、设置页备份/恢复/清理交互、启动时自动执行聊天保留期限、首次启动引导只完成一次/稍后再次显示、打包文件与版本一致性、安装器中文/按用户/不删用户数据、spec 资源与排除项、冻结资源路径、`--smoke-test` 数据库初始化，以及关闭窗口停止提醒定时器。
- `main.py --smoke-test` 离屏启动冒烟：退出码 **0**，自动创建 `salespilot.db`（200,704 字节）。
- 阶段 8 离屏端到端冒烟：创建客户和知识库文件 → 备份 → 新增客户 → 恢复 → 客户数据与知识库回退、工作台刷新 → 清空全部数据，退出码 **0**。
- PyInstaller 6.17.0 在 Linux 上按 `packaging/SalesPilotAI.spec` 实际完成 **onedir** 构建（约 246 MB），打包产物执行 `--smoke-test` 退出码 **0**，并确认 `_internal/assets/salespilot.ico` 被正确打入。
- 另用 Wine64 9.0 + Windows Python 3.12.10 + PySide6 6.12.0 + PyInstaller 6.22.3 实际生成 Windows x64 EXE：`dist/SalesPilotAI/SalesPilotAI.exe` 为 PE32+ GUI、Machine `0x8664`、13 MB，完整目录约 90 MB；`FileVersion`/`ProductVersion` 为 1.0.0，应用图标已打入。
- Windows EXE 在 Wine 中执行 `--smoke-test` 失败：Wine 缺少 Qt 6.12 依赖的 `icuuc.dll`，报错 `DLL load failed while importing QtWidgets: Module not found`；因此 Windows 运行时尚未验收。
- 1366×768 离屏窗口中，8 项导航、设置页可滚动布局、备份/恢复/隐私控件、阶段 9 标识、首次启动引导、原有聊天分析页、客户历史、产品知识库、跟进任务、AI 模型设置和空状态检查通过。
- `pip check`：**No broken requirements found**。
- 验证环境：Linux、Python 3.14.8、PySide6 6.11.3、PyInstaller 6.17.0、openpyxl 3.1.5、mss 10.1.0、OpenAI SDK 2.54.0、Pydantic 2.13.4、keyring 25.7.0、pypdf 6.16.2、python-docx 1.2.0、SQLite FTS5（trigram）。Windows EXE 交叉构建使用 Wine 9.0、Windows Python 3.12.10、PySide6 6.12.0、PyInstaller 6.22.3。

### 真实平台与 API 验证限制

当前容器不是 Windows，没有真实 DeepSeek 凭据，也无真实 WhatsApp、屏幕会话、PaddleOCR 或真实企业产品资料。因此：

- 恢复流程在 Linux 上通过自动化与离屏冒烟验证，**尚未**在真实 Windows 10/11 上验证数据库关闭后的文件替换、WAL/`-shm` 清理、防病毒或备份软件占用文件、网络盘/同步盘以及磁盘空间不足时的表现。
- **尚未**进行跨机器、跨 Windows 用户目录或跨软件版本的实际恢复验收；测试只覆盖同一代码版本生成的 ZIP 以及内存/文件数据库。
- **尚未**验证恢复过程中断电、任务管理器强制结束进程或系统崩溃后的半完成状态；应用内异常会回滚，但无法提供断电级事务保证。
- 备份 ZIP **未加密**，也没有数字签名或密码保护；其中含客户数据，需用户自行限制访问。**尚未**验证 GB 级数据库的备份/恢复耗时、内存占用和进度提示。
- 聊天保留期限使用 UTC 文本比较，已由固定时间测试覆盖，但**尚未**在真实长期数据、系统时区变更、夏令时和跨年数据下验收自动清理。
- 临时截图清理基于系统临时目录和文件修改时间，**尚未**验证文件被其他程序占用、权限不足或临时目录被安全软件重定向时的行为。
- 清空全部数据会删除知识库记录和文件副本，已由测试覆盖；**尚未**在真实用户数据上执行人工验收，也未提供回收站式恢复。
- **Windows EXE 已完成 Wine 冒烟，但未在真实 Windows 运行**：EXE 由 Wine64 + Windows Python + PySide6 6.8.3 生成，已核验 PE 架构、版本资源和图标；`--smoke-test` 在 Wine 中返回 0 并创建数据库。仍必须在真实 Windows 10/11 上运行 `dist/SalesPilotAI/SalesPilotAI.exe --smoke-test` 并人工验收。
- **安装包已由 NSIS 生成，但未执行安装/卸载**：当前 Linux 内核无法运行 32 位 NSIS 引导程序，因此只完成 PE 结构、压缩内容和文件清单核验；需在真实 Windows 上双击 `dist/installer/SalesPilotAI-Setup-1.0.0.exe` 验收。
- **尚未**在真实 Windows 上验证安装目录、开始菜单/桌面快捷方式、按用户安装、覆盖升级、卸载、SmartScreen 提示、文件占用导致升级失败，以及 `%LOCALAPPDATA%\Programs` 权限策略；安装器与卸载器也未做数字签名。
- `--smoke-test` 在 Linux 产物和 Wine 中的 Windows EXE 上均通过；**尚未**在真实 Windows 上执行，首次启动引导与 `--smoke-test` 的交互也只由离屏测试覆盖。
- **尚未**验证 Windows 打包产物中的 pywinauto/UIA、keyring Windows 凭据后端、mss 截图、全局快捷键和 PaddleOCR；打包时已排除 OCR 可选组件，若这些平台能力不可用，应回退到手动粘贴和本地保存。
- 全局未捕获异常钩子与统一日志**尚未**在真实 Windows 桌面中验证；代码签名、自动更新、崩溃上报和系统托盘尚未实现。
- **尚未**使用真实 DeepSeek 账户验证 AI 给出的跟进天数是否合理，也未验证真实模型在“是否需要跟进”上的稳定性；fake 测试只验证字段范围、草稿转换和人工创建流程。
- 跟进提醒仅在软件运行期间每 60 秒检查一次；**尚未**验证系统休眠唤醒、跨时区/夏令时切换、长时间运行或大量逾期任务下的提醒体验，也未实现系统通知或托盘常驻。
- 跟进状态流转、逾期判断和本地时区转换已由自动化测试覆盖，但**尚未**在真实 Windows 环境中进行人工验收。
- **尚未**使用真实 DeepSeek 账户验证知识片段引用质量、引用字段遵循度和模型对“知识库/客户/推测”的区分稳定性；fake 测试只验证请求注入、结构解析和界面展示。
- **尚未**使用真实客户长文档、复杂 PDF 排版、加密 PDF、超大 Excel 或企业实际 Word 模板验收解析效果；自动化测试使用生成的小型样本。
- 中文全文检索已验证 trigram 索引、短词回退、分类过滤和相关性过滤，但**尚未**在大量真实产品资料下评估召回率和排序质量。
- 扫描版 PDF 目前不集成 OCR，会明确提示需要文本版文件；**尚未**验证图片型资料的替代流程。
- **尚未**使用真实 DeepSeek 账户生成真实客户记忆建议；fake 测试只验证结构、去重和待确认流程，不证明线上模型会稳定输出有证据的建议。
- 客户记忆与历史检索的隔离、确认和去重已由自动化测试覆盖，但**尚未**在真实长期数据量和真实 Windows 界面下进行人工验收。
- **尚未**使用真实 DeepSeek 账户发起连接或聊天分析请求；fake SDK 测试不证明网络、账户余额、模型可用性或线上 JSON 兼容性已经验收。
- 规范给出的 `deepseek-flash` 和 `deepseek-v4-pro` 未在本环境独立验证；必须在设置页按账户实际可用模型修改。
- **尚未**在真实 Windows 凭据管理器中验证 API Key 的写入、读取和删除；自动化测试使用 fake 凭据库，生产代码不回退到明文。
- **尚未**在真实 Windows 10/11 上验收前台进程识别、UIA 元素树、全局快捷键注册和框选截图。
- **尚未**在真实 WhatsApp Desktop / Business / Web 上验证消息提取准确率和界面兼容性。
- **尚未**进行 PaddleOCR 实际模型推理和中英文识别准确率验收。
- 自动化测试通过 fake 适配器验证编排、降级、清理、请求参数和界面行为，不代表上述真实平台或云端能力已经验收。

真实 Windows 交付前仍需按使用流程逐项人工验收，尤其要检查系统凭据后端、DeepSeek 实际模型与 JSON 输出、真实产品资料解析与检索质量、不同 WhatsApp 版本的 UIA 文本结构、DPI/多显示器坐标、OCR 安装兼容性、跟进提醒在休眠/跨时区场景下的表现，以及备份恢复在真实 Windows 文件系统上的文件锁、磁盘空间和备份文件保护；同时需在 Windows 构建机生成 EXE/安装包并完成安装、升级、卸载和 SmartScreen 验收。
