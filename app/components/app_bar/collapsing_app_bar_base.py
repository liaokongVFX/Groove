# coding:utf-8
from typing import List, Union

from common.image_utils import DominantColor
from components.widgets.label import AvatarLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QColor, QPainter, QFont, QFontMetrics, QResizeEvent, QPalette
from PyQt5.QtWidgets import QWidget, QLabel

from .app_bar_button import AppBarButton


class CollapsingAppBarBase(QWidget):
    """ Collapsing app bar base class """

    def __init__(self, title: str, content: str, coverPath: str, coverType='album', parent=None):
        """
        Parameters
        ----------
        title: str
            title of bar

        content: str
            content of bar

        coverPath: str
            cover path

        coverType: str
            cover type, including `album`, `playlist` and `singer`

        parent:
            父级窗口
        """
        if coverType not in ['album', 'playlist', 'singer']:
            raise ValueError(f"Cover type `{coverType}` is illegal")

        super().__init__(parent=parent)
        self.title = title
        self.content = content
        self.coverPath = coverPath
        self.coverType = coverType
        self.needWhiteBar = coverType == 'playlist'

        self.contentLabel = QLabel(content, self)
        self.titleLabel = QLabel(title, self)
        self.coverLabel = QLabel(
            self) if coverType != 'singer' else AvatarLabel(self.coverPath, self)

        self.titleFontSize = 43
        self.contentFontSize = 16
        self.__buttons = []         # type:List[AppBarButton]
        self.__nButtons = len(self.__buttons)
        self.hiddenButtonNum = 0
        self.moreActionsButton = AppBarButton(
            ":/images/album_interface/More.png", "", self)
        self.__initWidget()

    def __initWidget(self):
        """ initialize widgets """
        # self.moreActionsButton.hide()
        self.moreActionsButton.clicked.connect(self.onMoreActionsButtonClicked)

        self.setMinimumHeight(155)
        self.setMaximumHeight(385)
        self.setBackgroundColor()
        self.setAutoFillBackground(True)
        self.coverLabel.setPixmap(QPixmap(self.coverPath).scaled(
            275, 275, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        self.coverLabel.setScaledContents(True)

        self.resize(1300, 385)

    def setButtons(self, buttons: List[AppBarButton]):
        """ set buttons on app bar """
        self.__buttons = buttons.copy()
        self.__nButtons = len(self.__buttons)
        for button in buttons:
            button.setParent(self)

    def setBackgroundColor(self):
        """ set the background color of app bar """
        r, g, b = DominantColor.getDominantColor(self.coverPath)
        palette = QPalette()
        palette.setColor(self.backgroundRole(), QColor(r, g, b))
        self.setPalette(palette)

    def resizeEvent(self, e: QResizeEvent):
        h = self.height()
        needWhiteBar = self.needWhiteBar

        # adjust geometry of cover
        coverWidth = 275 - \
            int((385-h)/230*192) if needWhiteBar else 295-int((385-h)/230*206)
        self.coverLabel.resize(coverWidth, coverWidth)
        y = 65-int((385-h)/230*17) if needWhiteBar else 45-int((385-h)/230*4)
        self.coverLabel.move(45, y)

        # adjust geometry of labels
        self.titleFontSize = int(40/43*(43-(385-h)/230*12))
        self.contentFontSize = int(16-(385-h)/147*3)
        self.__adjustText()
        self.titleLabel.setStyleSheet(self.__getLabelStyleSheet(
            ['Segoe UI Semilight', 'Microsoft YaHei Light'], self.titleFontSize))
        self.contentLabel.setStyleSheet(
            self.__getLabelStyleSheet(['Segoe UI', 'Microsoft YaHei'], self.contentFontSize))
        self.titleLabel.adjustSize()
        self.contentLabel.adjustSize()

        x = 45 + coverWidth + 44
        y1 = int(71/81*(71-(385-h)/230*25)) if needWhiteBar else y
        y2 = int(132-(385-h)/147*15) if needWhiteBar else y+56
        self.titleLabel.move(x, y1)
        self.contentLabel.move(x, y2)
        self.contentLabel.setVisible(h >= 238)

        # adjust position of buttons
        if not self.__buttons:
            return

        x = 45 + coverWidth + 22
        y = 288 - int((385-h)/230*206) if needWhiteBar else 308 - \
            int((385-h)/230*220)

        for button in self.__buttons:
            button.move(x, y)
            x += button.width()+10

        # Hide part of the button
        index = self.__getLastVisibleButtonIndex()
        self.hiddenButtonNum = self.__nButtons-(index+1)
        self.moreActionsButton.setVisible(index + 1 < self.__nButtons)
        for i, button in enumerate(self.__buttons):
            button.setHidden(i > index)

        self.moreActionsButton.move(
            self.__buttons[index].geometry().right()+10, y)

        # according to the position of the button and the width to decide whether to hide the button again.
        if self.moreActionsButton.isVisible() and self.width() < self.moreActionsButton.geometry().right()+10:
            self.hiddenButtonNum += 1
            self.__buttons[index].hide()
            self.moreActionsButton.move(
                self.__buttons[index-1].geometry().right()+10, y)

    def paintEvent(self, e):
        """ paint the white lines of cover """
        super().paintEvent(e)
        if not self.needWhiteBar:
            return

        painter = QPainter(self)
        painter.setPen(Qt.NoPen)
        painter.setRenderHint(QPainter.Antialiasing)
        h = self.height()
        y = self.coverLabel.y()
        x = self.coverLabel.x()
        w1 = 255 - int((385-h)/230*178)
        w2 = 235 - int((385-h)/230*164)
        h_ = (self.coverLabel.width()-w1)//2

        # paint first white line
        painter.setBrush(QColor(255, 255, 255, 255*0.4))
        painter.drawRect(x+h_, y-h_, w1, h_)

        # paint second white line
        painter.setBrush(QColor(255, 255, 255, 255*0.2))
        painter.drawRect(x+2*h_, y-2*h_, w2, h_)

    @staticmethod
    def __getLabelStyleSheet(fontFamily: Union[str, List[str]], fontSize: int, fontWeight=400):
        """ get the style sheet of label

        Parameters
        ----------
        fontFamily: str
            font family

        fontSize: int
            font size in pt

        fontWeight: int or str
            font weight
        """
        if isinstance(fontFamily, str):
            fontFamily = f"'{fontFamily}'"
        elif isinstance(fontFamily, list):
            fontFamily = ', '.join([f"'{i}'" for i in fontFamily])

        styleSheet = f"""
            color: white;
            margin: 0;
            padding: 0;
            font-family: {fontFamily};
            font-size: {fontSize}px;
            font-weight: {fontWeight};
        """
        return styleSheet

    def __adjustText(self):
        """ 调整过长的文本 """
        maxWidth = self.width()-40-self.coverLabel.rect().right()-45

        # adjust title
        fontMetrics = QFontMetrics(
            QFont('Microsoft YaHei', round(self.titleFontSize*27/43)))
        title = fontMetrics.elidedText(self.title, Qt.ElideRight, maxWidth)
        self.titleLabel.setText(title)
        self.titleLabel.adjustSize()

        # adjust content
        fontMetrics = QFontMetrics(
            QFont('Microsoft YaHei', round(self.contentFontSize*27/43)))
        content = fontMetrics.elidedText(self.content, Qt.ElideRight, maxWidth)
        self.contentLabel.setText(content)
        self.contentLabel.adjustSize()

    def __getLastVisibleButtonIndex(self):
        """ get the index of last visible button """
        for i, button in enumerate(self.__buttons):
            if button.geometry().right() + 10 > self.width():
                return i-1

        return i

    def onMoreActionsButtonClicked(self):
        """ show more action menu """
        raise NotImplementedError

    def updateWindow(self, title: str, content: str, coverPath: str):
        """ update app bar """
        self.title = title
        self.content = content
        self.coverPath = coverPath
        self.coverLabel.setPixmap(QPixmap(self.coverPath))
        self.setBackgroundColor()
        self.__adjustText()
        self.update()

    @property
    def buttons(self):
        return self.__buttons
