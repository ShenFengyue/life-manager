"""页面 C：热力图 Heatmaps。

按 Area 分组展示：每张 Area 热力图下面列出该 Area 的每个 Process 热力图。
Thread 不单独生成热力图。所有热力图按发生时的归属快照统计。
"""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import clock, heatmap as heatmap_stats
from ..models import NodeType
from ..services import LifeManagerService
from ..services import ValidationError
from ..widgets.common import (
    CollapsibleSection,
    Muted,
    Subtle,
    clear_layout,
    open_activity_dialog,
    warn,
)
from ..widgets.heatmap_calendar import HeatmapCalendar, HeatmapLegend


class HeatmapBlock(QWidget):
    """一张热力图（Area 或 Process 作用域）及其统计信息。"""

    def __init__(
        self,
        service: LifeManagerService,
        scope_kind: str,
        scope_id: str,
        parent: QWidget | None = None,
        title: str | None = None,
        note: str = "",
        on_changed=None,
        show_legend: bool = False,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.scope_kind = scope_kind
        self.scope_id = scope_id
        self._note_base = note
        self._on_changed = on_changed

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        if title:
            title_label = QLabel(title)
            title_label.setStyleSheet("font-size: 13px; font-weight: 600;")
            layout.addWidget(title_label)

        self.note_label = Subtle(note)
        self.note_label.setVisible(bool(note))
        layout.addWidget(self.note_label)

        self.calendar = HeatmapCalendar()
        self.calendar.dateClicked.connect(self._on_date_clicked)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.calendar)
        row.addStretch(1)
        layout.addLayout(row)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        self.stats_label = Subtle("")
        bottom.addWidget(self.stats_label)
        bottom.addStretch(1)
        if show_legend:
            bottom.addWidget(HeatmapLegend())
        layout.addLayout(bottom)

    def apply_window(self, grid: heatmap_stats.CalendarGrid) -> None:
        self.calendar.set_window(grid)
        scope = "area_id" if self.scope_kind == "area" else "process_id"
        query = (
            heatmap_stats.counts_for_area if self.scope_kind == "area"
            else heatmap_stats.counts_for_process
        )
        counts = query(self.service.db.conn, self.scope_id, grid.date_from, grid.date_to)
        summaries = heatmap_stats.summaries(
            self.service.db.conn, scope, self.scope_id, grid.date_from, grid.date_to
        )
        self.calendar.set_data(counts, summaries)
        total, active_days = heatmap_stats.window_totals(counts)
        level_text = "、".join(
            f"{level} 次 {count} 天"
            for level, count in sorted(self._level_histogram(counts).items())
            if level
        )
        self.stats_label.setText(
            f"窗口内 {total} 次活动 · {active_days} 天有记录" + (f"（{level_text}）" if level_text else "")
        )
        notes = [self._note_base] if self._note_base else []
        if self.scope_kind == "area":
            annotation = self._deleted_children_annotation(grid)
            if annotation:
                notes.append(annotation)
        self.note_label.setText("　".join(notes))
        self.note_label.setVisible(bool(notes))

    def _deleted_children_annotation(self, grid: heatmap_stats.CalendarGrid) -> str:
        """标注领域热力图中来自已删除进程的次数（数据保留，不是丢数据）。"""
        parts: list[str] = []
        for process in self.service.deleted_children(self.scope_id, NodeType.PROCESS):
            counts = heatmap_stats.counts_for_process(
                self.service.db.conn, process.id, grid.date_from, grid.date_to
            )
            total = sum(counts.values())
            if total:
                parts.append(f"{process.name} {total} 次")
        return f"含已删除进程：{'、'.join(parts)}" if parts else ""

    @staticmethod
    def _level_histogram(counts: dict[str, int]) -> dict[int, int]:
        histogram: dict[int, int] = {}
        for value in counts.values():
            level = heatmap_stats.level_for(value)
            histogram[level] = histogram.get(level, 0) + 1
        return histogram

    def _on_date_clicked(self, day: str) -> None:
        node = self.service.require_node(self.scope_id)
        if self.scope_kind == "area":
            subtitle = f"{node.name} 领域当天的活动（含其下全部进程与线程，按发生时的归属快照）"
            loader = lambda: self.service.list_activities(  # noqa: E731
                area_id=self.scope_id, date_from=day, date_to=day
            )
        else:
            subtitle = f"{node.name} 进程当天的活动（按发生时的归属快照）"
            loader = lambda: self.service.list_activities(  # noqa: E731
                process_id=self.scope_id, date_from=day, date_to=day
            )
        open_activity_dialog(
            self.service,
            self,
            title=f"{day} · {node.name}",
            subtitle=subtitle,
            loader=loader,
            on_changed=self._on_changed,
        )


class HeatmapsPage(QWidget):
    changed = Signal()

    def __init__(self, service: LifeManagerService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        # 距最近的周数：0 表示"最近 52 周"（终点永远是今天，跨午夜也自动跟上）
        self._window_offset_weeks = 0
        self._signature: tuple = ()
        self._area_blocks: dict[str, HeatmapBlock] = {}
        self._process_blocks: dict[str, HeatmapBlock] = {}
        self._area_sections: dict[str, CollapsibleSection] = {}
        self._process_sections: dict[str, CollapsibleSection] = {}
        self._deleted_blocks: dict[str, HeatmapBlock] = {}
        self._deleted_sections: list[CollapsibleSection] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(self._build_toolbar())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll, 1)
        self.container = QWidget()
        scroll.setWidget(self.container)
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 8, 0)
        self.container_layout.setSpacing(10)
        self.container_layout.addStretch(1)
        self.refresh()

    # -------------------------------------------------------------- 工具栏
    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        earlier = QPushButton("← 更早")
        earlier.clicked.connect(lambda: self._shift_window(52))
        later = QPushButton("更近 →")
        later.clicked.connect(lambda: self._shift_window(-52))
        self.later_button = later
        recent = QPushButton("回到最近")
        recent.clicked.connect(self._reset_window)

        row.addWidget(earlier)
        row.addWidget(later)
        row.addWidget(recent)
        self.window_label = Subtle("")
        row.addWidget(self.window_label)
        row.addStretch(1)
        # 整页只留一个图例，放在工具栏右侧，不再每张图重复一遍
        row.addWidget(HeatmapLegend())
        row.addSpacing(10)

        expand = QPushButton("全部展开")
        expand.clicked.connect(lambda: self._set_all_expanded(True))
        collapse = QPushButton("全部折叠")
        collapse.clicked.connect(lambda: self._set_all_expanded(False))
        row.addWidget(expand)
        row.addWidget(collapse)
        return bar

    def _grid(self) -> heatmap_stats.CalendarGrid:
        end = clock.today() - timedelta(weeks=self._window_offset_weeks)
        return heatmap_stats.build_calendar(end_date=end)

    def _shift_window(self, weeks: int) -> None:
        self._window_offset_weeks = max(0, self._window_offset_weeks + weeks)
        self._refresh_data()

    def _reset_window(self) -> None:
        self._window_offset_weeks = 0
        self._refresh_data()

    def _set_all_expanded(self, expanded: bool) -> None:
        sections = (
            list(self._area_sections.values())
            + list(self._process_sections.values())
            + list(self._deleted_sections)
        )
        for section in sections:
            section.set_expanded(expanded, emit=False)

    # ---------------------------------------------------------------- 结构
    def _structure_signature(self) -> tuple:
        signature = []
        for area in self.service.areas():
            processes = tuple(
                (process.id, process.name) for process in self.service.processes(area.id)
            )
            signature.append((area.id, area.name, processes))
        deleted = tuple(
            (node.id, node.name, node.type.value)
            for node in self.service.all_nodes(include_deleted=True)
            if node.is_deleted
        )
        return (tuple(signature), deleted)

    def refresh(self) -> None:
        signature = self._structure_signature()
        if signature != self._signature:
            self._rebuild(signature)
        self._refresh_data()

    def _rebuild(self, signature: tuple) -> None:
        self._signature = signature
        clear_layout(self.container_layout)
        self._area_blocks.clear()
        self._process_blocks.clear()
        self._area_sections.clear()
        self._process_sections.clear()
        self._deleted_blocks.clear()
        self._deleted_sections.clear()

        for area in self.service.areas():
            section = CollapsibleSection(area.name, expanded=True, indent=0)
            area_block = HeatmapBlock(
                self.service, "area", area.id, on_changed=self._on_activities_changed
            )
            self._area_blocks[area.id] = area_block
            self._area_sections[area.id] = section
            section.body.addWidget(area_block)

            for process in self.service.processes(area.id):
                process_section = CollapsibleSection(process.name, expanded=True, indent=16)
                process_section.headerContextRequested.connect(
                    lambda _pos, pid=process.id: self._edit_process_note(pid)
                )
                block = HeatmapBlock(
                    self.service, "process", process.id, on_changed=self._on_activities_changed
                )
                self._process_blocks[process.id] = block
                self._process_sections[process.id] = process_section
                process_section.body.addWidget(block)
                section.body.addWidget(process_section)

            self.container_layout.addWidget(section)

        self._append_deleted_section()

        note = Muted(
            "Thread 不单独生成热力图：它的活动按发生时的主要归属汇总到对应 Process 与 Area，"
            "线程详情里仍可查看自己的完整活动记录。"
        )
        self.container_layout.addWidget(note)
        self.container_layout.addStretch(1)

    def _append_deleted_section(self) -> None:
        """已删除的领域与进程：数据保留，热力图仍然可见，并标注原来属于哪里。"""
        deleted_areas = self.service.deleted_children(None, NodeType.AREA)
        deleted_processes = [
            node
            for node in self.service.all_nodes(include_deleted=True)
            if node.is_deleted and node.type is NodeType.PROCESS
        ]
        if not deleted_areas and not deleted_processes:
            return
        section = CollapsibleSection("已删除（数据保留）", expanded=False, indent=0)
        section.set_subtitle("活动与热力图数据都还在，可从「进程树 → 已删除…」恢复")
        for node in deleted_areas:
            block = HeatmapBlock(
                self.service,
                "area",
                node.id,
                title=f"{node.name}（已删除的领域）",
                note="该领域下的记录仍计入这张热力图",
                on_changed=self._on_activities_changed,
            )
            self._deleted_blocks[node.id] = block
            section.body.addWidget(block)
        for node in deleted_processes:
            parent = self.service.get_node(node.parent_id) if node.parent_id else None
            original = " → ".join(step.name for step in self.service.path_of(node.id)[:-1])
            suffix = "（它所在的领域也已删除）" if parent is not None and parent.is_deleted else ""
            block = HeatmapBlock(
                self.service,
                "process",
                node.id,
                title=f"{node.name}（已删除的进程）",
                note=f"原来归属：{original}{suffix}",
                on_changed=self._on_activities_changed,
            )
            self._deleted_blocks[node.id] = block
            section.body.addWidget(block)
        self._deleted_sections.append(section)
        self.container_layout.addWidget(section)

    def _refresh_data(self) -> None:
        grid = self._grid()
        self.window_label.setText(
            f"最近 {grid.weeks} 周（{grid.date_from} 至 {grid.date_to}）"
        )
        self.later_button.setEnabled(self._window_offset_weeks > 0)
        # 进程注释：有就显示一行小字，没有就完全隐藏
        notes = {
            row["id"]: row["description"]
            for row in self.service.db.conn.execute(
                "SELECT id, description FROM nodes WHERE description <> ''"
            ).fetchall()
        }
        for process_id, section in self._process_sections.items():
            section.set_note(notes.get(process_id, ""))
        for area_id, block in self._area_blocks.items():
            block.apply_window(grid)
            total = block.calendar.totals()[0]
            self._area_sections[area_id].set_subtitle(f"窗口内 {total} 次活动")
        for process_id, block in self._process_blocks.items():
            block.apply_window(grid)
            total = block.calendar.totals()[0]
            self._process_sections[process_id].set_subtitle(f"窗口内 {total} 次活动")
        for block in self._deleted_blocks.values():
            block.apply_window(grid)

    # ---------------------------------------------------------------- 注释
    def _on_activities_changed(self) -> None:
        """弹窗里改了/删了活动：立刻重画本页，并通知主窗口（其它页面切回时自动刷新）。"""
        self.refresh()
        self.changed.emit()

    def _edit_process_note(self, process_id: str) -> None:
        """右键进程热力图标题：写一句注释（显示在标题下面）。"""
        node = self.service.require_node(process_id)
        text, ok = QInputDialog.getMultiLineText(
            self,
            "进程注释",
            f"给「{node.name}」的热力图写一句注释（显示在标题下面；留空则不显示）：",
            node.description,
        )
        if not ok:
            return
        try:
            self.service.set_description(process_id, text)
        except ValidationError as exc:
            warn(self, "无法保存注释", str(exc))
            return
        self.changed.emit()
