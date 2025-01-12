# coding:utf-8
from .config import config
from PyQt5.QtCore import QFile
from PyQt5.QtWidgets import QWidget


def getStyleSheet(file: str):
    """ get style sheet

    Parameters
    ----------
    file: str
        qss file name, without `.qss` suffix
    """
    f = QFile(f":/qss/{config.theme}/{file}.qss")
    f.open(QFile.ReadOnly)
    qss = str(f.readAll(), encoding='utf-8')
    f.close()
    return qss


def setStyleSheet(widget: QWidget, file: str):
    """ set the style sheet of widget

    Parameters
    ----------
    widget: QWidget
        the widget to set style sheet

    file: str
        qss file name, without `.qss` suffix
    """
    widget.setStyleSheet(getStyleSheet(file))