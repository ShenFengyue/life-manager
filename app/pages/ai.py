"""AI 对话页：会话历史 + 聊天。

只把「你输入的文字 + 本会话历史 + 设置里的系统提示词」发给模型；
不发送数据库、活动记录、日记或备份。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .. import ai, theme
from ..services import LifeManagerService
from ..widgets.ai_worker import ChatWorker
from ..widgets.common import Muted, Subtle

CHAT_WIDTH = 860      # 中间对话栏的最大宽度（整栏居中，不贴窗口两边）
BUBBLE_WIDTH = 620    # 单条消息气泡的最大宽度


class MarkdownView(QTextBrowser):
    """把一段 Markdown 渲染成自适应高度的静态视图（不滚动、不弹浏览器）。"""

    def __init__(self, text: str, max_width: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._max_width = max_width
        self._adjusting = False
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("QTextBrowser { background: transparent; border: none; }")
        self.document().setDocumentMargin(0)
        self.set_markdown(text)

    def set_markdown(self, text: str) -> None:
        document = self.document()
        document.setMarkdown(text or "")
        document.setTextWidth(-1)
        ideal = document.idealWidth()
        width = int(min(self._max_width, max(80, ideal + 6)))
        self.setFixedWidth(width)
        self._fit_height()

    def _fit_height(self) -> None:
        """按当前真实宽度量一次高度，避免刚创建时宽度还没定、内容被裁掉。"""
        if self._adjusting:
            return
        self._adjusting = True
        try:
            document = self.document()
            document.setTextWidth(max(40, self.viewport().width()))
            height = max(24, int(document.size().height()) + 2)
            if abs(self.height() - height) > 1:
                self.setFixedHeight(height)
            self.verticalScrollBar().setValue(0)
        finally:
            self._adjusting = False

    def resizeEvent(self, event) -> None:  # pragma: no cover - 需要 GUI
        super().resizeEvent(event)
        if not self._adjusting:
            self._fit_height()


class MessageBubble(QWidget):
    """一条消息：你（右侧气泡）/ AI（左侧气泡），都在居中的对话栏里。"""

    def __init__(self, role: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        user = role == "user"
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 3, 0, 3)
        row.setSpacing(0)

        bubble = QFrame()
        bubble.setObjectName("UserBubble" if user else "AIBubble")
        bubble.setMaximumWidth(BUBBLE_WIDTH)
        bubble.setStyleSheet(
            f"QFrame#UserBubble {{ background: {theme.ACCENT_SOFT}; border-radius: 12px; }}"
            f"QFrame#AIBubble {{ background: {theme.SURFACE}; border-radius: 12px; }}"
            f"QLabel {{ background: transparent; color: {theme.TEXT}; }}"
        )
        inner = QVBoxLayout(bubble)
        inner.setContentsMargins(14, 10, 14, 10)
        inner.setSpacing(4)

        who = QLabel("你" if user else "AI")
        who.setStyleSheet(f"color: {theme.TEXT_SUBTLE}; font-size: 11px; font-weight: 600;")
        inner.addWidget(who)

        body = MarkdownView(text, BUBBLE_WIDTH - 28)
        body.setStyleSheet(
            f"QTextBrowser {{ background: transparent; border: none; color: {theme.TEXT}; }}"
        )
        inner.addWidget(body)

        if user:
            row.addStretch(1)
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch(1)


class CenteredColumn(QWidget):
    """把内容限制在一个最大宽度内，并始终水平居中。"""

    def __init__(self, content: QWidget, max_width: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._content = content
        self._max_width = max_width
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addStretch(1)
        row.addWidget(content, 0)
        row.addStretch(1)

    def resizeEvent(self, event) -> None:  # pragma: no cover - 需要 GUI
        width = max(280, min(self._max_width, self.width() - 48))
        self._content.setFixedWidth(width)
        super().resizeEvent(event)


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

        # 消息区：滚动区里放一列限宽的“对话栏”，整栏水平居中（像 ChatGPT）
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.messages_column = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_column)
        self.messages_layout.setContentsMargins(0, 12, 0, 12)
        self.messages_layout.setSpacing(6)
        self.scroll.setWidget(CenteredColumn(self.messages_column, CHAT_WIDTH))
        layout.addWidget(self.scroll, 1)

        # 输入区也限制在同一个宽度里，和上面的对话栏对齐
        input_column = QWidget()
        input_layout = QVBoxLayout(input_column)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(6)

        self.input = QPlainTextEdit()
        self.input.setFixedHeight(92)
        self.input.setPlaceholderText("输入内容，Ctrl+Enter 发送")
        input_layout.addWidget(self.input)

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
        input_layout.addLayout(row)

        layout.addWidget(CenteredColumn(input_column, CHAT_WIDTH))
        return panel

    # ------------------------------------------------------------- 状态
    def reload_config(self) -> None:
        self.ai_config.load()
        self._sync_ready()

    def _sync_ready(self) -> None:
        ready = self.ai_config.ready
        # 页面随时能点：没配置时也允许打字，点发送会提示先去设置。
        self.input.setEnabled(self._worker is None)
        self.send_button.setEnabled(self._worker is None)
        if ready:
            self.notice.setText(
                "只发送本会话的文字与设置里的人设提示词；不会上传数据库、活动记录、日记或备份。"
            )
        else:
            self.notice.setText(
                "AI 还没有启用或缺少 API Key：到「设置」里填写 Key 并勾选启用（字段可以直接编辑）。"
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
            self.status.setText("还没有配置好 AI：点右下角「打开设置」填写 Key 并勾选启用。")
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
        self.input.setEnabled(True)
        self.send_button.setEnabled(True)
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
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        if not messages:
            hint = QLabel("新建一条对话，直接输入问题即可。\n历史记录只保存在本机。")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setStyleSheet(
                f"color: {theme.TEXT_SUBTLE}; font-size: 13px; padding: 70px 0;"
            )
            self.messages_layout.addWidget(hint)

        for message in messages:
            self.messages_layout.addWidget(
                MessageBubble(message["role"], message["content"])
            )

        if pending:
            self.messages_layout.addWidget(MessageBubble("assistant", "正在回答…"))

        if error:
            warn = QLabel(f"发送失败：{error}")
            warn.setWordWrap(True)
            warn.setStyleSheet(f"color: {theme.DANGER}; padding: 6px 2px;")
            self.messages_layout.addWidget(warn)

        self.messages_layout.addStretch(1)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
