"""全局处理动画对话框。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QLabel
from qfluentwidgets import IndeterminateProgressRing, MessageBoxBase


class ProcessingDialog(MessageBoxBase):
    """带遮罩的处理中进度对话框。

    功能描述：
        用于在执行后台工作流时阻塞用户交互，并显示不确定进度环（IndeterminateProgressRing）
        与文本提示。由于继承自 MessageBoxBase，自带模态遮罩。

    参数说明：
        parent (QWidget): 父级窗口。
        title (str): 进度条上方的标题文字。
        content (str): 进度条下方的详情提示文字。
    """

    def __init__(self, parent: QWidget, title: str = "处理中", content: str = "请稍候...") -> None:
        """初始化进度对话框。

        功能描述：
            设置对话框标题、描述与不确定进度条，并隐藏底部的默认按钮组。

        参数说明：
            parent (QWidget): 父级窗口。
            title (str): 对话框标题。
            content (str): 对话框描述。
        """
        super().__init__(parent)

        self.title_label = QLabel(title, self)
        self.content_label = QLabel(content, self)
        
        # 使用不确定进度环
        self.progress_ring = IndeterminateProgressRing(self)
        self.progress_ring.setFixedSize(36, 36)

        self._init_layout()
        
        # 强制隐藏 MessageBoxBase 自带的“确认/取消”按钮组（只作为动画遮罩）
        self.buttonGroup.hide()

    def _init_layout(self) -> None:
        """初始化内部布局。

        功能描述：
            将标题、进度环与内容文本水平或垂直排列以获得更好的视觉效果。
        """
        self.viewLayout.setSpacing(16)
        self.viewLayout.setContentsMargins(24, 24, 24, 24)
        
        # 设置字体样式
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.content_label.setStyleSheet("font-size: 14px; color: #666;")
        
        # 创建一个水平布局来放置环和文字
        h_layout = QHBoxLayout()
        h_layout.setSpacing(16)
        
        h_layout.addWidget(self.progress_ring, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        # 文字部分的垂直布局
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.content_label)
        
        h_layout.addLayout(text_layout)
        h_layout.addStretch(1)
        
        self.viewLayout.addLayout(h_layout)
        
        # 调整对话框最小宽度
        self.widget.setMinimumWidth(350)
