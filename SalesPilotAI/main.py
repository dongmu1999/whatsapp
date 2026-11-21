"""SalesPilot AI 桌面程序入口。"""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app.config import APP_NAME, APP_VERSION, ORGANIZATION_NAME, ensure_data_dir, get_database_path
from app.database import Database
from app.ui.main_window import MainWindow
from app.utils.logger import setup_logging


def create_application(arguments: list[str] | None = None) -> QApplication:
    application = QApplication.instance()
    if application is None:
        application = QApplication(arguments if arguments is not None else sys.argv)
    application.setApplicationName(APP_NAME)
    application.setApplicationVersion(APP_VERSION)
    application.setOrganizationName(ORGANIZATION_NAME)
    application.setStyle("Fusion")
    return application


def main() -> int:
    application = create_application()
    data_dir = ensure_data_dir()
    setup_logging(data_dir / "logs")
    logger = logging.getLogger("salespilot.main")

    try:
        database = Database(get_database_path())
        applied = database.initialize()
        if applied:
            logger.info("数据库迁移完成：%s", applied)
    except Exception as exc:
        logger.exception("数据库初始化失败")
        QMessageBox.critical(
            None,
            "SalesPilot AI 启动失败",
            f"无法初始化本地数据库。请检查数据目录权限或磁盘空间。\n\n{exc}",
        )
        return 1

    window = MainWindow(database)
    window.show()
    application.aboutToQuit.connect(database.close)
    logger.info("SalesPilot AI 已启动")
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
