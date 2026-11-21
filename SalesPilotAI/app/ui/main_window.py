"""SalesPilot AI 主窗口与主导航。"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_NAME, APP_NAME_ZH, APP_VERSION, get_data_dir
from app.database.connection import Database
from app.database.repositories.dashboard_repository import DashboardRepository
from app.database.repositories.settings_repository import SettingsRepository
from app.ui.dashboard import DashboardPage
from app.ui.placeholder_page import PlaceholderPage
from app.ui.settings_page import SettingsPage
from app.ui.theme import DARK_THEME, LIGHT_THEME, VALID_THEMES, apply_theme


class MainWindow(QMainWindow):
    NAVIGATION = (
        "工作台",
        "AI 聊天分析",
        "客户管理",
        "客户历史记录",
        "产品知识库",
        "跟进任务",
        "AI 模型设置",
        "系统设置",
    )

    def __init__(self, database: Database, parent=None):
        super().__init__(parent)
        self.database = database
        self.settings = SettingsRepository(database)
        saved_theme = self.settings.get("theme", LIGHT_THEME)
        self.current_theme = saved_theme if saved_theme in VALID_THEMES else LIGHT_THEME

        self.setWindowTitle(f"{APP_NAME} · {APP_NAME_ZH}")
        self.setObjectName("mainWindow")
        self.setMinimumSize(1024, 640)
        self.resize(1220, 720)
        self._build_ui()

        application = QApplication.instance()
        if application is not None:
            apply_theme(application, self.current_theme)
        self._update_theme_controls()
        self.navigation.setCurrentRow(0)

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 24, 0, 18)
        sidebar_layout.setSpacing(4)

        brand = QLabel(APP_NAME)
        brand.setObjectName("brand")
        brand.setContentsMargins(22, 0, 12, 0)
        sidebar_layout.addWidget(brand)
        brand_subtitle = QLabel("外贸销售智能助手")
        brand_subtitle.setObjectName("brandSubtitle")
        brand_subtitle.setContentsMargins(22, 0, 12, 20)
        sidebar_layout.addWidget(brand_subtitle)

        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        self.navigation.setFocusPolicy(Qt.NoFocus)
        self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for title in self.NAVIGATION:
            item = QListWidgetItem(title)
            item.setSizeHint(QSize(160, 42))
            item.setTextAlignment(Qt.AlignVCenter)
            self.navigation.addItem(item)
        self.navigation.currentRowChanged.connect(self.navigate)
        sidebar_layout.addWidget(self.navigation, 1)

        safety = QLabel("仅提供销售辅助\n不会自动发送 WhatsApp 消息")
        safety.setObjectName("sidebarNotice")
        safety.setWordWrap(True)
        safety.setContentsMargins(22, 8, 16, 8)
        sidebar_layout.addWidget(safety)
        version = QLabel(f"V{APP_VERSION} · 阶段 1")
        version.setObjectName("sidebarVersion")
        version.setContentsMargins(22, 0, 12, 0)
        sidebar_layout.addWidget(version)
        root.addWidget(sidebar)

        workspace = QWidget()
        workspace.setObjectName("workspace")
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)

        topbar = QFrame()
        topbar.setObjectName("topBar")
        topbar.setFixedHeight(64)
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(28, 0, 24, 0)
        self.topbar_title = QLabel(self.NAVIGATION[0])
        self.topbar_title.setObjectName("topbarTitle")
        topbar_layout.addWidget(self.topbar_title)
        topbar_layout.addStretch(1)
        self.theme_button = QPushButton()
        self.theme_button.setObjectName("themeButton")
        self.theme_button.setCursor(Qt.PointingHandCursor)
        self.theme_button.clicked.connect(self.toggle_theme)
        topbar_layout.addWidget(self.theme_button)
        workspace_layout.addWidget(topbar)

        self.pages = QStackedWidget()
        self.pages.setObjectName("pages")
        workspace_layout.addWidget(self.pages, 1)
        root.addWidget(workspace, 1)

        self.dashboard = DashboardPage(DashboardRepository(self.database))
        self.pages.addWidget(self.dashboard)
        self.dashboard.quick_start_requested.connect(
            lambda: self.navigation.setCurrentRow(1)
        )

        self.pages.addWidget(
            PlaceholderPage(
                "AI 聊天分析",
                "将在阶段 3 和阶段 4 实现",
                "通过用户主动触发的 UI Automation、OCR 或手动粘贴获取可见聊天内容，确认后调用 DeepSeek。"
                "分析前会明确提示上传范围并提供脱敏选项。",
            )
        )
        self.pages.addWidget(
            PlaceholderPage("客户管理", "将在阶段 2 实现", "新增、编辑、搜索、筛选、导入和导出本地客户档案。")
        )
        self.pages.addWidget(
            PlaceholderPage("客户历史记录", "将在阶段 5 实现", "按客户隔离保存历史沟通、分析结果与经确认的长期记忆。")
        )
        self.pages.addWidget(
            PlaceholderPage("产品知识库", "将在阶段 6 实现", "导入产品文档并通过 SQLite FTS5 检索相关资料。")
        )
        self.pages.addWidget(
            PlaceholderPage("跟进任务", "将在阶段 7 实现", "创建本地跟进计划、记录结果并接收软件内提醒。")
        )
        self.pages.addWidget(
            PlaceholderPage("AI 模型设置", "将在阶段 4 实现", "配置 DeepSeek Base URL、模型与加密保存的 API Key，并测试连接。")
        )
        self.settings_page = SettingsPage(self.current_theme, get_data_dir())
        self.settings_page.theme_requested.connect(self.set_theme)
        self.pages.addWidget(self.settings_page)
        self.statusBar().showMessage("本地数据库已就绪", 3000)

    def navigate(self, index: int) -> None:
        if not 0 <= index < self.pages.count():
            return
        self.pages.setCurrentIndex(index)
        self.topbar_title.setText(self.NAVIGATION[index])
        if index == 0:
            self.dashboard.refresh()

    def set_theme(self, theme: str) -> None:
        if theme not in VALID_THEMES:
            return
        application = QApplication.instance()
        if application is not None:
            apply_theme(application, theme)
        self.current_theme = theme
        self.settings.set("theme", theme)
        self._update_theme_controls()
        self.statusBar().showMessage("主题设置已保存", 2500)

    def toggle_theme(self) -> None:
        self.set_theme(DARK_THEME if self.current_theme == LIGHT_THEME else LIGHT_THEME)

    def _update_theme_controls(self) -> None:
        is_dark = self.current_theme == DARK_THEME
        self.theme_button.setText("切换浅色" if is_dark else "切换深色")
        self.theme_button.setToolTip("切换界面明暗主题")
        if hasattr(self, "settings_page"):
            self.settings_page.set_theme(self.current_theme)
