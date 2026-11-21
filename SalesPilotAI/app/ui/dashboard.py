"""工作台：展示数据库中的真实汇总和最近记录。"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database.repositories.dashboard_repository import DashboardRepository


def _format_time(value: str | None) -> str:
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone()
        return parsed.strftime("%m-%d %H:%M")
    except ValueError:
        return value


class MetricCard(QFrame):
    def __init__(self, title: str, note: str, object_name: str, parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setMinimumHeight(104)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("metricTitle")
        layout.addWidget(title_label)

        self.value_label = QLabel("0")
        self.value_label.setObjectName(object_name)
        self.value_label.setProperty("metricValue", True)
        layout.addWidget(self.value_label)

        note_label = QLabel(note)
        note_label.setObjectName("metricNote")
        layout.addWidget(note_label)

    def set_value(self, value: int) -> None:
        self.value_label.setText(str(value))


class DataCard(QFrame):
    def __init__(self, title: str, headers: list[str], empty_text: str, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        heading = QLabel(title)
        heading.setObjectName("sectionHeading")
        layout.addWidget(heading)

        self.stack = QStackedWidget()
        self.table = QTableWidget(0, len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setMinimumHeight(150)
        self.stack.addWidget(self.table)

        empty = QLabel(empty_text)
        empty.setObjectName("emptyState")
        empty.setAlignment(Qt.AlignCenter)
        empty.setMinimumHeight(150)
        self.stack.addWidget(empty)
        layout.addWidget(self.stack)

    def set_rows(self, rows: list[list[str]]) -> None:
        self.table.clearContents()
        self.table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                self.table.setItem(row_index, column, item)
        self.stack.setCurrentWidget(self.table if rows else self.stack.widget(1))


class DashboardPage(QWidget):
    quick_start_requested = Signal()

    def __init__(self, repository: DashboardRepository, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.setObjectName("dashboardPage")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer_layout.addWidget(scroll)

        content = QWidget()
        content.setObjectName("pageContent")
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title_group = QVBoxLayout()
        title_group.setSpacing(4)
        title = QLabel("工作台")
        title.setObjectName("pageHeading")
        title_group.addWidget(title)
        subtitle = QLabel("查看本地销售进展，或开始一次由你确认的聊天分析。")
        subtitle.setObjectName("pageSubtitle")
        title_group.addWidget(subtitle)
        header.addLayout(title_group)
        header.addStretch(1)

        quick_start = QPushButton("开始聊天分析")
        quick_start.setObjectName("primaryButton")
        quick_start.setCursor(Qt.PointingHandCursor)
        quick_start.setMinimumSize(130, 38)
        quick_start.clicked.connect(self.quick_start_requested)
        header.addWidget(quick_start, 0, Qt.AlignTop)
        layout.addLayout(header)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(12)
        self.cards = {
            "total_customers": MetricCard("客户总数", "本地客户档案", "metricTotalCustomers"),
            "today_analyses": MetricCard("今日分析", "当天 AI 分析次数", "metricTodayAnalyses"),
            "high_intent_customers": MetricCard("高意向客户", "意向评分 ≥ 70", "metricHighIntent"),
            "pending_followup_customers": MetricCard("待跟进客户", "存在未完成任务", "metricPendingFollowups"),
        }
        for index, card in enumerate(self.cards.values()):
            metrics.addWidget(card, 0, index)
        layout.addLayout(metrics)

        recent_layout = QHBoxLayout()
        recent_layout.setSpacing(12)
        self.analysis_card = DataCard(
            "最近分析记录",
            ["客户", "客户意图", "评分", "时间"],
            "暂无分析记录",
        )
        self.analysis_card.table.setObjectName("recentAnalysesTable")
        recent_layout.addWidget(self.analysis_card, 3)

        self.customer_card = DataCard(
            "最近沟通客户",
            ["客户", "国家", "销售阶段", "意向评分"],
            "暂无客户记录",
        )
        self.customer_card.table.setObjectName("recentCustomersTable")
        recent_layout.addWidget(self.customer_card, 2)
        layout.addLayout(recent_layout)

        self.followup_card = DataCard(
            "待办跟进任务",
            ["客户", "跟进内容", "优先级", "计划时间"],
            "暂无待办任务",
        )
        self.followup_card.table.setObjectName("followupsTable")
        layout.addWidget(self.followup_card)
        self.refresh()

    def refresh(self) -> None:
        summary = self.repository.get_summary()
        self.cards["total_customers"].set_value(summary.total_customers)
        self.cards["today_analyses"].set_value(summary.today_analyses)
        self.cards["high_intent_customers"].set_value(summary.high_intent_customers)
        self.cards["pending_followup_customers"].set_value(summary.pending_followup_customers)

        analyses = self.repository.get_recent_analyses()
        self.analysis_card.set_rows(
            [
                [
                    row["customer_name"],
                    row["customer_intent"] or "未完成",
                    "—" if row["purchase_intent_score"] is None else str(row["purchase_intent_score"]),
                    _format_time(row["created_at"]),
                ]
                for row in analyses
            ]
        )

        customers = self.repository.get_recent_customers()
        self.customer_card.set_rows(
            [
                [
                    row["name"],
                    row["country"] or "—",
                    row["sales_stage"],
                    str(row["intent_score"]),
                ]
                for row in customers
            ]
        )

        priority_names = {"low": "低", "medium": "中", "high": "高"}
        followups = self.repository.get_upcoming_followups()
        self.followup_card.set_rows(
            [
                [
                    row["customer_name"],
                    row["content"],
                    priority_names.get(row["priority"], row["priority"]),
                    _format_time(row["due_at"]),
                ]
                for row in followups
            ]
        )
