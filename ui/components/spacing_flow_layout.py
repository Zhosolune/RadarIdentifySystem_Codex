"""行末剩余空间均分到间距的流式布局。

基于 FlowLayout 扩展，以卡片数最多的行为基准计算间距，
所有行共用同一间距，实现类似 CSS ``justify-content: space-between`` 的效果。
支持可配置的边缘内边距，为控件阴影等溢出绘制区域预留空间。
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QSize
from qfluentwidgets import FlowLayout


class SpacingFlowLayout(FlowLayout):
    """行末剩余空间自动均分到间距的流式布局。

    第一遍按默认间距分行并找出卡片最多的行作为基准行，
    以该行均摊剩余空间后得到的间距作为全布局统一间距。

    Attributes:
        edge_padding: 右侧底部额外预留空间（px），用于避免控件阴影
            等 QGraphicsEffect 溢出绘制被父容器裁剪。
    """

    def __init__(self, parent=None, needAni=False, isTight=False, edge_padding=0):
        """
        Args:
            parent: 父容器。
            needAni: 是否启用移动动画。
            isTight: 隐藏控件时是否紧贴排列。
            edge_padding: 右侧和底部为阴影等效果预留的额外像素。
        """
        super().__init__(parent, needAni, isTight)
        self.edge_padding = edge_padding

    def _doLayout(self, rect: QRect, move: bool) -> int:
        """先分行→以最多卡片行为基准算统一间距→统一放置所有行。"""
        ani_restart = False
        margin = self.contentsMargins()
        space_y = self.verticalSpacing()
        default_space_x = self.horizontalSpacing()

        # 收集可见项，附带原始索引和卡片宽度。
        visible_items: list[tuple[int, object, int]] = []
        for i, item in enumerate(self._items):
            w = item.widget()
            if w and not w.isVisible() and self.isTight:
                continue
            visible_items.append((i, item, item.sizeHint().width()))

        if not visible_items:
            return margin.top() + margin.bottom()

        # 预留边缘空间，避免阴影等效果被裁剪。
        available_width = (rect.width() - margin.left() - margin.right()
                           - self.edge_padding * 2)

        # 第一遍：按默认间距分行，记录每行累计宽度（含默认间距）。
        rows: list[tuple[list[tuple[int, object, int]], int]] = []
        current_row: list[tuple[int, object, int]] = []
        current_width = 0

        for orig_idx, item, card_w in visible_items:
            if not current_row:
                current_row.append((orig_idx, item, card_w))
                current_width = card_w
            elif current_width + default_space_x + card_w > available_width:
                rows.append((current_row, current_width))
                current_row = [(orig_idx, item, card_w)]
                current_width = card_w
            else:
                current_row.append((orig_idx, item, card_w))
                current_width += default_space_x + card_w

        if current_row:
            rows.append((current_row, current_width))

        # 以卡片数最多的行作为基准计算统一间距。
        max_cards = max(len(r[0]) for r in rows)
        if max_cards > 1:
            for row_items, row_cards_width in rows:
                if len(row_items) == max_cards:
                    remaining = available_width - row_cards_width
                    if remaining > 0:
                        space_x = default_space_x + remaining / (max_cards - 1)
                    else:
                        space_x = default_space_x
                    break
            else:
                space_x = default_space_x
        else:
            space_x = default_space_x

        # 第二遍：所有行用统一间距放置控件。
        x_base = rect.x() + margin.left() + self.edge_padding
        y = rect.y() + margin.top() + self.edge_padding
        row_height = 0

        for row_items, _row_cards_width in rows:
            x = x_base
            for orig_idx, item, card_w in row_items:
                if move:
                    target = QRect(
                        QPoint(int(x), y),
                        QSize(card_w, item.sizeHint().height()),
                    )
                    if not self.needAni:
                        item.setGeometry(target)
                    elif (
                        orig_idx < len(self._anis)
                        and target != self._anis[orig_idx].endValue()
                    ):
                        self._anis[orig_idx].stop()
                        self._anis[orig_idx].setEndValue(target)
                        ani_restart = True

                x += card_w + int(space_x)
                row_height = max(row_height, item.sizeHint().height())

            y += row_height + space_y
            row_height = 0

        if self.needAni and ani_restart:
            self._aniGroup.stop()
            self._aniGroup.start()

        return (y - space_y + row_height + margin.bottom()
                + self.edge_padding - rect.y())
