from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QWidget, QVBoxLayout
import sys

sys.path.insert(0, "e:/myProjects_Trae/RadarIdentifySystem")

from ui.components.directory_picker_card import DirectoryPickerCard


class TestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("测试窗口")
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout(self)

        card = DirectoryPickerCard(
            title="选择目录",
            subtitle="选择文件要导出的位置",
            icon_path= "",
            button_text="选择目录",
        )
        layout.addWidget(card)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec_())


