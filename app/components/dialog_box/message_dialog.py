# coding:utf-8
from common.auto_wrap import autoWrap
from common.style_sheet import setStyleSheet
from components.buttons.perspective_button import PerspectivePushButton
from PyQt5.QtCore import QFile, pyqtSignal
from PyQt5.QtWidgets import QLabel

from .mask_dialog_base import MaskDialogBase


class MessageDialog(MaskDialogBase):
    """ Message dialog box with a mask """

    yesSignal = pyqtSignal()
    cancelSignal = pyqtSignal()

    def __init__(self, title: str, content: str, parent):
        super().__init__(parent=parent)
        self.content = content
        self.titleLabel = QLabel(title, self.widget)
        self.contentLabel = QLabel(content, self.widget)
        self.yesButton = PerspectivePushButton(self.tr('OK'), self.widget)
        self.cancelButton = PerspectivePushButton(
            self.tr('Cancel'), self.widget)
        self.__initWidget()

    def __initWidget(self):
        """ initialize widgets """
        self.windowMask.resize(self.size())
        self.widget.setMaximumWidth(675)
        self.titleLabel.move(30, 30)
        self.contentLabel.move(30, 70)
        self.contentLabel.setText(autoWrap(self.content, 71)[0])

        self.__setQss()
        self.__initLayout()

        # connect signal to slot
        self.yesButton.clicked.connect(self.__onYesButtonClicked)
        self.cancelButton.clicked.connect(self.__onCancelButtonClicked)

    def __initLayout(self):
        """ initialize layout """
        self.contentLabel.adjustSize()
        self.widget.setFixedSize(60+self.contentLabel.width(),
                                 self.contentLabel.y() + self.contentLabel.height()+115)
        self.yesButton.resize((self.widget.width() - 68) // 2, 40)
        self.cancelButton.resize(self.yesButton.width(), 40)
        self.yesButton.move(30, self.widget.height()-70)
        self.cancelButton.move(
            self.widget.width()-30-self.cancelButton.width(), self.widget.height()-70)

    def __onCancelButtonClicked(self):
        self.cancelSignal.emit()
        self.close()

    def __onYesButtonClicked(self):
        self.setEnabled(False)
        self.yesSignal.emit()
        self.close()

    def __setQss(self):
        """ set style sheet """
        self.windowMask.setObjectName('windowMask')
        self.titleLabel.setObjectName('titleLabel')
        self.contentLabel.setObjectName('contentLabel')
        setStyleSheet(self, 'message_dialog')