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


def _install_exception_hook(logger: logging.Logger) -> None:
    """记录未捕获异常并给出中文提示，避免界面直接退出。"""

    def handler(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical(
            "未捕获异常", exc_info=(exc_type, exc_value, exc_traceback)
        )
        try:
            QMessageBox.critical(
                None,
                "SalesPilot AI 发生错误",
                f"程序遇到未处理的错误，已记录到日志。\n\n{exc_value}",
            )
        except Exception:
            pass

    sys.excepthook = handler


def main(arguments: list[str] | None = None) -> int:
    arguments = list(sys.argv if arguments is None else arguments)
    smoke_test = "--smoke-test" in arguments
    qt_arguments = [argument for argument in arguments if argument != "--smoke-test"]
    application = create_application(qt_arguments)
    data_dir = ensure_data_dir()
    setup_logging(data_dir / "logs")
    logger = logging.getLogger("salespilot.main")
    if not smoke_test:
        _install_exception_hook(logger)

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

    try:
        window = MainWindow(database)
    except Exception as exc:
        logger.exception("主窗口初始化失败")
        QMessageBox.critical(
            None,
            "SalesPilot AI 启动失败",
            f"无法创建主窗口，已记录日志。\n\n{exc}",
        )
        database.close()
        return 1

    window.show()
    if not smoke_test:
        window.show_first_run_guide()
    application.aboutToQuit.connect(database.close)
    logger.info("SalesPilot AI 已启动")
    if smoke_test:
        application.processEvents()
        logger.info("打包冒烟测试通过")
        window.close()
        database.close()
        return 0
    try:
        return application.exec()
    except Exception:
        logger.exception("程序运行时发生未捕获异常")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
