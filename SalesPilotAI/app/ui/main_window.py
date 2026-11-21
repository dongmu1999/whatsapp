"""SalesPilot AI 主窗口与主导航。"""

from __future__ import annotations

import logging
import sys

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

from app.capture.hotkey import GlobalHotkeyManager
from app.config import APP_NAME, APP_NAME_ZH, APP_VERSION, get_data_dir
from app.database.connection import Database
from app.database.repositories.analysis_repository import (
    AnalysisRepository,
    APIUsageRepository,
)
from app.database.repositories.customer_repository import CustomerRepository
from app.database.repositories.dashboard_repository import DashboardRepository
from app.database.repositories.history_repository import HistoryRepository
from app.database.repositories.knowledge_repository import KnowledgeRepository
from app.database.repositories.memory_repository import MemoryRepository
from app.database.repositories.settings_repository import SettingsRepository
from app.services.ai_settings_service import AISettingsService
from app.services.conversation_service import ConversationService
from app.services.customer_service import CustomerService
from app.services.deepseek_service import DeepSeekClient
from app.services.knowledge_service import KnowledgeService
from app.services.memory_service import MemoryService
from app.services.sales_advisor_service import SalesAdvisorService
from app.ui.ai_settings_page import AISettingsPage
from app.ui.chat_analysis_page import ChatAnalysisPage
from app.ui.customer_history_page import CustomerHistoryPage
from app.ui.customer_page import CustomerPage
from app.ui.dashboard import DashboardPage
from app.ui.knowledge_page import KnowledgePage
from app.ui.placeholder_page import PlaceholderPage
from app.ui.settings_page import SettingsPage
from app.ui.theme import DARK_THEME, LIGHT_THEME, VALID_THEMES, apply_theme

logger = logging.getLogger(__name__)


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
        version = QLabel(f"V{APP_VERSION} · 阶段 6")
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

        customer_service = CustomerService(CustomerRepository(self.database))
        ai_settings_service = AISettingsService(self.settings)
        deepseek_client = DeepSeekClient(ai_settings_service)
        usage_repository = APIUsageRepository(self.database)
        memory_service = MemoryService(
            MemoryRepository(self.database), HistoryRepository(self.database)
        )
        knowledge_service = KnowledgeService(KnowledgeRepository(self.database))
        self.chat_analysis_page = ChatAnalysisPage(
            ConversationService(self.database),
            customer_service,
            self.settings,
            analysis_service=SalesAdvisorService(deepseek_client),
            analysis_repository=AnalysisRepository(self.database),
            usage_repository=usage_repository,
            ai_settings_service=ai_settings_service,
            memory_service=memory_service,
            knowledge_service=knowledge_service,
        )
        self.pages.addWidget(self.chat_analysis_page)
        self.customer_page = CustomerPage(customer_service)
        self.customer_page.customers_changed.connect(self.dashboard.refresh)
        self.customer_page.status_message.connect(
            lambda message: self.statusBar().showMessage(message, 5000)
        )
        self.pages.addWidget(self.customer_page)
        self.customer_history_page = CustomerHistoryPage(customer_service, memory_service)
        self.customer_history_page.status_message.connect(
            lambda message: self.statusBar().showMessage(message, 5000)
        )
        self.pages.addWidget(self.customer_history_page)
        self.knowledge_page = KnowledgePage(knowledge_service)
        self.knowledge_page.status_message.connect(
            lambda message: self.statusBar().showMessage(message, 6000)
        )
        self.pages.addWidget(self.knowledge_page)
        self.pages.addWidget(
            PlaceholderPage("跟进任务", "将在阶段 7 实现", "创建本地跟进计划、记录结果并接收软件内提醒。")
        )
        self.ai_settings_page = AISettingsPage(
            ai_settings_service, deepseek_client, usage_repository
        )
        self.pages.addWidget(self.ai_settings_page)
        self.settings_page = SettingsPage(self.current_theme, get_data_dir())
        self.settings_page.theme_requested.connect(self.set_theme)
        self.pages.addWidget(self.settings_page)

        self.chat_analysis_page.customers_changed.connect(self.dashboard.refresh)
        self.chat_analysis_page.customers_changed.connect(self.customer_page.refresh)
        self.chat_analysis_page.status_message.connect(
            lambda message: self.statusBar().showMessage(message, 6000)
        )
        self.chat_analysis_page.result_ready.connect(
            lambda: self.navigation.setCurrentRow(1)
        )
        self.chat_analysis_page.analysis_completed.connect(self.dashboard.refresh)
        self.chat_analysis_page.analysis_completed.connect(
            self.customer_history_page.refresh_customers
        )
        self.customer_page.customers_changed.connect(
            self.customer_history_page.refresh_customers
        )
        self.hotkey_manager = GlobalHotkeyManager(self)
        self.hotkey_manager.triggered.connect(
            lambda _sequence: self.chat_analysis_page.capture_current_chat()
        )
        self.hotkey_manager.error.connect(self._show_hotkey_error)
        self.chat_analysis_page.hotkey_changed.connect(self.set_capture_hotkey)
        if sys.platform == "win32":
            self.set_capture_hotkey(self.settings.get("capture_hotkey", "Ctrl+Shift+A"))
        self.statusBar().showMessage("本地数据库已就绪", 3000)

    def navigate(self, index: int) -> None:
        if not 0 <= index < self.pages.count():
            return
        self.pages.setCurrentIndex(index)
        self.topbar_title.setText(self.NAVIGATION[index])
        if index == 0:
            self.dashboard.refresh()
        elif index == 1:
            self.chat_analysis_page.refresh_customers()
        elif index == 2:
            self.customer_page.refresh()
        elif index == 3:
            self.customer_history_page.refresh_customers()
        elif index == 4:
            self.knowledge_page.refresh()

    def set_capture_hotkey(self, sequence: str) -> None:
        if sys.platform != "win32":
            return
        try:
            self.hotkey_manager.start(sequence)
        except Exception as exc:
            self._show_hotkey_error(str(exc))

    def _show_hotkey_error(self, message: str) -> None:
        logger.error("全局快捷键：%s", message)
        self.statusBar().showMessage(message, 8000)
        self.chat_analysis_page.status_label.setText(message)

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

    def closeEvent(self, event) -> None:
        if hasattr(self, "hotkey_manager"):
            self.hotkey_manager.stop()
        super().closeEvent(event)
