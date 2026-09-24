from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


@dataclass(frozen=True)
class Column:
    key: str
    title: str
    formatter: Callable[[Any, dict], str] | None = None
    alignment: Qt.AlignmentFlag | None = None


class DictTableModel(QAbstractTableModel):
    def __init__(self, columns: list[Column], rows: list[dict] | None = None, parent=None):
        super().__init__(parent)
        self.columns = columns
        self.rows: list[dict] = rows or []

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.columns)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.rows)):
            return None
        column = self.columns[index.column()]
        row = self.rows[index.row()]
        value = row.get(column.key)

        if role == Qt.ItemDataRole.DisplayRole:
            if column.formatter:
                try:
                    return column.formatter(value, row)
                except Exception:
                    return str(value or "")
            return "" if value is None else str(value)

        if role == Qt.ItemDataRole.UserRole:
            return value

        if role == Qt.ItemDataRole.TextAlignmentRole and column.alignment is not None:
            return int(column.alignment)

        if role == Qt.ItemDataRole.ToolTipRole:
            text = "" if value is None else str(value)
            return text if len(text) > 40 else None

        return None

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.columns):
            return self.columns[section].title
        if orientation == Qt.Orientation.Vertical:
            return section + 1
        return None

    def replace(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()

    def row_dict(self, row: int) -> dict | None:
        if 0 <= row < len(self.rows):
            return self.rows[row]
        return None

    def row_id(self, row: int) -> int | None:
        item = self.row_dict(row)
        if not item:
            return None
        value = item.get("id")
        return int(value) if value is not None else None

    def sort(self, column: int, order=Qt.SortOrder.AscendingOrder) -> None:
        if not (0 <= column < len(self.columns)):
            return
        key = self.columns[column].key

        def normalized(row: dict):
            value = row.get(key)
            if value is None:
                return (1, "")
            if isinstance(value, (int, float)):
                return (0, value)
            return (0, str(value).casefold())

        self.layoutAboutToBeChanged.emit()
        self.rows.sort(
            key=normalized,
            reverse=order == Qt.SortOrder.DescendingOrder,
        )
        self.layoutChanged.emit()
