"""AI 对话页：会话历史 + 聊天。

只把「你输入的文字 + 本会话历史 + 设置里的系统提示词」发给模型；
不发送数据库、活动记录、日记或备份。
"""

from __future__ import annotations

import html

from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .. import ai, theme
from ..services import LifeManagerService
from ..widgets.ai_worker import ChatWorker
from ..widgets.common import Muted, Subtle


class AIPage(QWidget):
    openSettingsRequested = Signal()

    def __init__(
        self,
        service: LifeManagerService,
        parent: QWidget | None = None,
        *,
        ai_config: ai.AIConfig | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.ai_config = ai_config or ai.AIConfig()
        self._pool = QThreadPool.globalInstance()
        self._worker: ChatWorker | None = None
        self.current_id: str | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 14)
        outer.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_chat())
        splitter.setSizes([240, 900])
        splitter.setChildrenCollapsible(False)
        outer.addWidget(splitter, 1)

        self.notice = Subtle("")
        self.notice.setWordWrap(True)
        outer.addWidget(self.notice)

        shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self.send)

        self.reload_config()
        self.refresh()

    # ------------------------------------------------------------- 构建
    def _build_sidebar(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 10, 0)
        layout.setSpacing(8)

        layout.addWidget(QLabel("对话历史"))
        self.conversation_list = QListWidget()
        self.conversation_list.currentItemChanged.connect(self._on_conversation_selected)
        layout.addWidget(self.conversation_list, 1)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.new_button = QPushButton("新建对话")
        self.new_button.clicked.connect(self.new_chat)
        self.delete_button = QPushButton("删除")
        self.delete_button.clicked.connect(self.delete_conversation)
        row.addWidget(self.new_button)
        row.addWidget(self.delete_button)
        layout.addLayout(row)
        return panel

    def _build_chat(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(8)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(False)
        layout.addWidget(self.view, 1)

        self.input = QPlainTextEdit()
        self.input.setFixedHeight(92)
        self.input.setPlaceholderText("输入内容，Ctrl+Enter 发送")
        layout.addWidget(self.input)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.status = Muted("")
        row.addWidget(self.status, 1)
        self.settings_button = QPushButton("打开设置")
        self.settings_button.clicked.connect(self.openSettingsRequested.emit)
        row.addWidget(self.settings_button)
        self.send_button = QPushButton("发送")
        self.send_button.setObjectName("PrimaryButton")
        self.send_button.clicked.connect(self.send)
        row.addWidget(self.send_button)
        layout.addLayout(row)
        return panel

    # ------------------------------------------------------------- 状态
    def reload_config(self) -> None:
        self.ai_config.load()
        self._sync_ready()

    def _sync_ready(self) -> None:
        ready = self.ai_config.ready
        self.input.setEnabled(ready)
        self.send_button.setEnabled(ready and self._worker is None)
        if ready:
            self.notice.setText(
                "只发送本会话的文字与设置里的人设提示词；不会上传数据库、活动记录、日记或备份。"
            )
        else:
            self.notice.setText(
                "AI 还没有启用或缺少 API Key：到「设置」里填好并打开开关即可。"
                "在此之前应用完全离线，其它功能不受影响。"
            )

    def refresh(self) -> None:
        self._fill_conversations()
        if self.current_id is None:
            self._render_messages([])
        elif not any(
            item["id"] == self.current_id for item in self.service.ai_conversations()
        ):
            self.current_id = None
            self._render_messages([])

    def _fill_conversations(self) -> None:
        self.conversation_list.blockSignals(True)
        self.conversation_list.clear()
        current_row = -1
        for row, conversation in enumerate(self.service.ai_conversations()):
            item = QListWidgetItem(conversation["title"])
            item.setData(Qt.ItemDataRole.UserRole, conversation["id"])
            item.setToolTip(
                f"{conversation['message_count']} 条消息 · 最后更新 {conversation['updated_at']}"
            )
            self.conversation_list.addItem(item)
            if conversation["id"] == self.current_id:
                current_row = row
        if current_row >= 0:
            self.conversation_list.setCurrentRow(current_row)
        self.conversation_list.blockSignals(False)
        self.delete_button.setEnabled(self.current_id is not None)

    # ------------------------------------------------------------- 交互
    def new_chat(self) -> None:
        self.current_id = None
        self.conversation_list.blockSignals(True)
        self.conversation_list.setCurrentRow(-1)
        self.conversation_list.blockSignals(False)
        self._render_messages([])
        self.input.setFocus()
        self.status.setText("")
        self.delete_button.setEnabled(False)

    def _on_conversation_selected(self, current, _previous) -> None:
        if current is None:
            self.current_id = None
            self._render_messages([])
            return
        self.current_id = current.data(Qt.ItemDataRole.UserRole)
        self._render_messages(self.service.ai_messages(self.current_id))
        self.delete_button.setEnabled(True)

    def delete_conversation(self) -> None:
        if not self.current_id:
            return
        title = self.conversation_list.currentItem()
        name = title.text() if title is not None else "这条对话"
        confirm = QMessageBox.question(
            self,
            "删除对话",
            f"删除「{name}」以及它的全部消息？删除后无法恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.service.delete_ai_conversation(self.current_id)
        self.current_id = None
        self._render_messages([])
        self._fill_conversations()

    def send(self) -> None:
        if self._worker is not None:
            return
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.reload_config()
        if not self.ai_config.ready:
            self.status.setText("还没有配置好 AI：请到「设置」里填写并启用。")
            return

        if self.current_id is None:
            self.current_id = self.service.create_ai_conversation()
        self.service.append_ai_message(self.current_id, "user", text)
        self.input.clear()
        messages = [
            {"role": message["role"], "content": message["content"]}
            for message in self.service.ai_messages(self.current_id)
        ]
        self._render_messages(self.service.ai_messages(self.current_id), pending=True)
        self._fill_conversations()

        worker = ChatWorker(self.ai_config, messages)
        self._worker = worker
        worker.signals.done.connect(self._on_reply)
        worker.signals.failed.connect(self._on_error)
        self.send_button.setEnabled(False)
        self.input.setEnabled(False)
        self.status.setText("正在回答…")
        self._pool.start(worker)

    # ------------------------------------------------------------- 回调
    def _finish(self) -> None:
        self._worker = None
        self.input.setEnabled(self.ai_config.ready)
        self.send_button.setEnabled(self.ai_config.ready)
        self.status.setText("")
        self.input.setFocus()

    def _on_reply(self, reply: str) -> None:
        if self.current_id:
            if reply.strip():
                self.service.append_ai_message(self.current_id, "assistant", reply)
            else:
                self.status.setText("模型返回了空内容。")
        self._finish()
        if self.current_id:
            self._render_messages(self.service.ai_messages(self.current_id))
        self._fill_conversations()

    def _on_error(self, message: str) -> None:
        self._finish()
        if self.current_id:
            self._render_messages(
                self.service.ai_messages(self.current_id), error=message
            )
        self.status.setText(f"发送失败：{message}")

    # ------------------------------------------------------------- 渲染
    def _render_messages(
        self, messages: list[dict[str, str]], *, pending: bool = False, error: str = ""
    ) -> None:
        parts: list[str] = [
            "<style>"
            f".m{{margin:10px 0;padding:10px 12px;border-radius:8px;color:{theme.TEXT};}}"
            f".u{{background:{theme.ACCENT_SOFT};}}"
            f".a{{background:{theme.SURFACE};}}"
            ".r{font-weight:600;margin-bottom:4px;}"
            f".err{{color:{theme.DANGER};}}"
            f".muted{{color:{theme.TEXT_SUBTLE};}}"
            "</style>"
        ]
        if not messages:
            parts.append(
                "<p class='muted'>新建一条对话，直接输入问题即可。"
                "历史记录只保存在本机。</p>"
            )
        for message in messages:
            role = message["role"]
            label = "你" if role == "user" else "AI"
            css = "u" if role == "user" else "a"
            body = html.escape(message["content"]).replace("\n", "<br>")
            parts.append(
                f"<div class='m {css}'><div class='r'>{label}</div><div>{body}</div></div>"
            )
        if pending:
            parts.append("<div class='m a'><div class='r'>AI</div><div>正在回答…</div></div>")
        if error:
            parts.append(f"<p class='err'>发送失败：{html.escape(error)}</p>")
        self.view.setHtml("".join(parts))
        bar = self.view.verticalScrollBar()
        bar.setValue(bar.maximum())
