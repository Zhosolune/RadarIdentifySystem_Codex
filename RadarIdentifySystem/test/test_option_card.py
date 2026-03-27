from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QWidget, QVBoxLayout
import sys

sys.path.insert(0, "e:/myProjects_Trae/RadarIdentifySystem")

from ui.components.option_setting_card import OptionSettingCard


class TestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("测试窗口")
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout(self)

        card = OptionSettingCard(
            title="切分方式",
            subtitle="当文件过大时，选择导出文件时切分文件的方式",
        )
        card.add_option("按数量平均切分", checked=True)
        card.add_option("按预设大小切分", checked=False)
        # card.set_enabled(False)
        layout.addWidget(card)
        layout.addStretch()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec_())


