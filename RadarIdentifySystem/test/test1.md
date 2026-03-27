```python
class OptionsSettingCard(ExpandSettingCard):
    """ setting card with a group of options """

    optionChanged = pyqtSignal(OptionsConfigItem)

    def __init__(self, configItem, icon: Union[str, QIcon, FluentIconBase], title, content=None, texts=None, parent=None):
        """
        Parameters
        ----------
        configItem: OptionsConfigItem
            options config item

        icon: str | QIcon | FluentIconBase
            the icon to be drawn

        title: str
            the title of setting card

        content: str
            the content of setting card

        texts: List[str]
            the texts of radio buttons

        parent: QWidget
            parent window
        """
        super().__init__(icon, title, content, parent)
        self.texts = texts or []
        self.configItem = configItem
        self.configName = configItem.name
        self.choiceLabel = QLabel(self)
        self.buttonGroup = QButtonGroup(self)

        self.choiceLabel.setObjectName("titleLabel")
        self.addWidget(self.choiceLabel)

        # create buttons
        self.viewLayout.setSpacing(19)
        self.viewLayout.setContentsMargins(48, 18, 0, 18)
        for text, option in zip(texts, configItem.options):
            button = RadioButton(text, self.view)
            self.buttonGroup.addButton(button)
            self.viewLayout.addWidget(button)
            button.setProperty(self.configName, option)

        self._adjustViewSize()
        self.setValue(qconfig.get(self.configItem))
        configItem.valueChanged.connect(self.setValue)
        self.buttonGroup.buttonClicked.connect(self.__onButtonClicked)

    def __onButtonClicked(self, button: RadioButton):
        """ button clicked slot """
        if button.text() == self.choiceLabel.text():
            return

        value = button.property(self.configName)
        qconfig.set(self.configItem, value)

        self.choiceLabel.setText(button.text())
        self.choiceLabel.adjustSize()
        self.optionChanged.emit(self.configItem)

    def setValue(self, value):
        """ select button according to the value """
        qconfig.set(self.configItem, value)

        for button in self.buttonGroup.buttons():
            isChecked = button.property(self.configName) == value
            button.setChecked(isChecked)

            if isChecked:
                self.choiceLabel.setText(button.text())
                self.choiceLabel.adjustSize()


class ExpandSettingCard(QScrollArea):
    """ Expandable setting card """

    def __init__(self, icon: Union[str, QIcon, FIF], title: str, content: str = None, parent=None):
        super().__init__(parent=parent)
        self.isExpand = False

        self.scrollWidget = QFrame(self)
        self.view = QFrame(self.scrollWidget)
        self.card = HeaderSettingCard(icon, title, content, self)

        self.scrollLayout = QVBoxLayout(self.scrollWidget)
        self.viewLayout = QVBoxLayout(self.view)
        self.spaceWidget = SpaceWidget(self.scrollWidget)
        self.borderWidget = ExpandBorderWidget(self)

        # expand animation
        self.expandAni = QPropertyAnimation(self.verticalScrollBar(), b'value', self)

        self.__initWidget()

    def __initWidget(self):
        """ initialize widgets """
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setFixedHeight(self.card.height())
        self.setViewportMargins(0, self.card.height(), 0, 0)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # initialize layout
        self.scrollLayout.setContentsMargins(0, 0, 0, 0)
        self.scrollLayout.setSpacing(0)
        self.scrollLayout.addWidget(self.view)
        self.scrollLayout.addWidget(self.spaceWidget)

        # initialize expand animation
        self.expandAni.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.expandAni.setDuration(200)

        # initialize style sheet
        self.view.setObjectName('view')
        self.scrollWidget.setObjectName('scrollWidget')
        self.setProperty('isExpand', False)
        FluentStyleSheet.EXPAND_SETTING_CARD.apply(self.card)
        FluentStyleSheet.EXPAND_SETTING_CARD.apply(self)

        self.card.installEventFilter(self)
        self.expandAni.valueChanged.connect(self._onExpandValueChanged)
        self.card.expandButton.clicked.connect(self.toggleExpand)

    def addWidget(self, widget: QWidget):
        """ add widget to tail """
        self.card.addWidget(widget)
        self._adjustViewSize()

    def wheelEvent(self, e):
        pass

    def setExpand(self, isExpand: bool):
        """ set the expand status of card """
        if self.isExpand == isExpand:
            return

        self._adjustViewSize()

        # update style sheet
        self.isExpand = isExpand
        self.setProperty('isExpand', isExpand)
        self.setStyle(QApplication.style())

        # start expand animation
        if isExpand:
            h = self.viewLayout.sizeHint().height()
            self.verticalScrollBar().setValue(h)
            self.expandAni.setStartValue(h)
            self.expandAni.setEndValue(0)
        else:
            self.expandAni.setStartValue(0)
            self.expandAni.setEndValue(self.verticalScrollBar().maximum())

        self.expandAni.start()
        self.card.expandButton.setExpand(isExpand)

    def toggleExpand(self):
        """ toggle expand status """
        self.setExpand(not self.isExpand)

    def resizeEvent(self, e):
        self.card.resize(self.width(), self.card.height())
        self.scrollWidget.resize(self.width(), self.scrollWidget.height())

    def _onExpandValueChanged(self):
        vh = self.viewLayout.sizeHint().height()
        h = self.viewportMargins().top()
        self.setFixedHeight(max(h + vh - self.verticalScrollBar().value(), h))

    def _adjustViewSize(self):
        """ adjust view size """
        h = self.viewLayout.sizeHint().height()
        self.spaceWidget.setFixedHeight(h)

        if self.isExpand:
            self.setFixedHeight(self.card.height()+h)

    def setValue(self, value):
        """ set the value of config item """
        pass

class SettingCardGroup(QWidget):
    """ Setting card group """

    def __init__(self, title, parent=None):
        super().__init__(parent=parent)
        self.titleLabel = QLabel(title, self)
        self.vBoxLayout = QVBoxLayout(self)
        self.cardLayout = ExpandLayout()

        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.vBoxLayout.setSpacing(0)
        self.cardLayout.setContentsMargins(0, 0, 0, 0)
        self.cardLayout.setSpacing(2)

        self.vBoxLayout.addWidget(self.titleLabel)
        self.vBoxLayout.addSpacing(12)
        self.vBoxLayout.addLayout(self.cardLayout, 1)

        FluentStyleSheet.SETTING_CARD_GROUP.apply(self)
        setFont(self.titleLabel, 20)
        self.titleLabel.adjustSize()

    def addSettingCard(self, card):
        """ add setting card to group """
        card.setParent(self)
        self.cardLayout.addWidget(card)
        self.adjustSize()

    def addSettingCards(self, cards):
        """ add setting cards to group """
        for card in cards:
            self.addSettingCard(card)

    def adjustSize(self):
        h = self.cardLayout.heightForWidth(self.width()) + 46
        return self.resize(self.width(), h)

class HeaderSettingCard(SettingCard):
    """ Header setting card """

    def __init__(self, icon, title, content=None, parent=None):
        super().__init__(icon, title, content, parent)
        self.expandButton = ExpandButton(self)

        self.hBoxLayout.addWidget(self.expandButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(8)

        self.titleLabel.setObjectName("titleLabel")
        self.installEventFilter(self)

    def eventFilter(self, obj, e):
        if obj is self:
            if e.type() == QEvent.Type.Enter:
                self.expandButton.setHover(True)
            elif e.type() == QEvent.Type.Leave:
                self.expandButton.setHover(False)
            elif e.type() == QEvent.Type.MouseButtonPress and e.button() == Qt.MouseButton.LeftButton:
                self.expandButton.setPressed(True)
            elif e.type() == QEvent.Type.MouseButtonRelease and e.button() == Qt.MouseButton.LeftButton:
                self.expandButton.setPressed(False)
                self.expandButton.click()

        return super().eventFilter(obj, e)

    def addWidget(self, widget: QWidget):
        """ add widget to tail """
        N = self.hBoxLayout.count()
        self.hBoxLayout.removeItem(self.hBoxLayout.itemAt(N - 1))
        self.hBoxLayout.addWidget(widget, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(19)
        self.hBoxLayout.addWidget(self.expandButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(8)

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        if isDarkTheme():
            painter.setBrush(QColor(255, 255, 255, 13))
        else:
            painter.setBrush(QColor(255, 255, 255, 170))

        p = self.parent()  # type: ExpandSettingCard
        path = QPainterPath()
        path.setFillRule(Qt.FillRule.WindingFill)
        path.addRoundedRect(QRectF(self.rect().adjusted(1, 1, -1, -1)), 6, 6)

        # set the bottom border radius to 0 if parent is expanded
        if hasattr(p, 'isExpand') and p.isExpand:
            path.addRect(1, self.height() - 8, self.width() - 2, 8)

        painter.drawPath(path.simplified())

class ExpandBorderWidget(QWidget):
    """ Expand setting card border widget """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        parent.installEventFilter(self)

    def eventFilter(self, obj, e):
        if obj is self.parent() and e.type() == QEvent.Type.Resize:
            self.resize(e.size())

        return super().eventFilter(obj, e)

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if isDarkTheme():
            painter.setPen(QColor(0, 0, 0, 50))
        else:
            painter.setPen(QColor(0, 0, 0, 19))

        p = self.parent()  # type: ExpandSettingCard
        r, d = 6, 12
        ch, h, w = p.card.height(), self.height(), self.width()

        # only draw rounded rect if parent is not expanded
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), r, r)

        # draw the seperator line under card widget
        if ch < h:
            painter.drawLine(1, ch, w - 1, ch)
```

用法：
```python
self.zoomCard = OptionsSettingCard(
        cfg.dpiScale,
        FIF.ZOOM,
        self.tr("Interface zoom"),
        self.tr("Change the size of widgets and fonts"),
        texts=[
            "100%", "125%", "150%", "175%", "200%",
            self.tr("Use system setting")
        ],
        parent=self.personalGroup
    )
    
self.personalGroup.addSettingCard(self.zoomCard)
```