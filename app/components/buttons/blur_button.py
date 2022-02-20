# coding:utf-8
from .tooltip_button import TooltipButton
from PIL import Image
from PIL.ImageFilter import GaussianBlur
from PyQt5.QtCore import QPoint, QPropertyAnimation, Qt, pyqtProperty
from PyQt5.QtGui import QBrush, QEnterEvent, QPainter, QPixmap
from PyQt5.QtWidgets import QToolButton


class BlurButton(TooltipButton):
    """ Blur button class """

    def __init__(self, parent, cropPos: tuple, iconPath: str, blurPicPath: str,
                 text: str, radius=35, blurRadius=40):
        """
        Parameters
        ----------
        parent:
            parent window

        cropPos: tuple
            coordinates of the image cropping position

        iconPath: str
            icon path

        blurPicPath: str
            image to be blurred

        text: str
            text of tool tip

        radius: int
            button radius

        blurRadius: int
            blur radius
        """
        super().__init__(parent=parent)
        self.__paintRadius = radius-5
        self.radius = radius
        self.resize(radius*2, radius*2)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.blurPix = None
        self.blurPicPath = blurPicPath
        self.blurRadius = blurRadius
        self.cropX, self.cropY = cropPos
        self.iconPix = QPixmap(iconPath).scaled(
            radius*2, radius*2, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.radiusAni = QPropertyAnimation(self, b'paintRadius', self)
        self.setToolTip(text)

    def showEvent(self, e):
        if not self.blurPix:
            self.__blur()

        self.__paintRadius=self.radius-5
        super().showEvent(e)

    def setBlurPic(self, blurPicPath, blurRadius=35):
        """ set the image to be blurred """
        if self.blurPicPath == blurPicPath:
            return
        self.blurPicPath = blurPicPath
        self.blurRadius = blurRadius
        self.blurPix = None

    def __blur(self):
        """ do blur action """
        if not self.blurPicPath.startswith(':'):
            img = Image.open(self.blurPicPath)
        else:
            img = Image.fromqpixmap(QPixmap(self.blurPicPath))

        img = img.convert('RGB').resize((200, 200))
        img = img.crop((self.cropX, self.cropY,
                        self.width() + self.cropX, self.height() + self.cropY))
        img = img.filter(GaussianBlur(self.blurRadius)
                         ).point(lambda x: int(x * 0.7))
        self.blurPix = img.toqpixmap()

        self.update()

    def paintEvent(self, e):
        """ paint button """
        painter = QPainter(self)
        painter.setPen(Qt.NoPen)
        painter.setRenderHints(QPainter.Antialiasing |
                               QPainter.SmoothPixmapTransform)
        # paint background
        if self.blurPix:
            r = self.__paintRadius
            dr = self.radius - r
            self.__drawCirclePic(painter, dr, dr, 2*r, 2*r, self.blurPix)

        # paint icon
        self.__drawCirclePic(painter, 5, 5, self.width()-10,
                             self.height() - 10, self.iconPix)

    def __drawCirclePic(self, painter, x, y, width, height, pixmap):
        """ paint image in circle region """
        brush = QBrush(pixmap)
        painter.setBrush(brush)
        painter.drawEllipse(x, y, width, height)

    def enterEvent(self, e: QEnterEvent):
        if self.radiusAni.state() == QPropertyAnimation.Running:
            self.radiusAni.stop()

        super().enterEvent(e)

        self.radiusAni.setStartValue(self.__paintRadius)
        self.radiusAni.setEndValue(self.radius)
        self.radiusAni.setDuration(100)
        self.radiusAni.start()

    def leaveEvent(self, e):
        if self.radiusAni.state() == QPropertyAnimation.Running:
            self.radiusAni.stop()

        super().leaveEvent(e)

        self.radiusAni.setStartValue(self.__paintRadius)
        self.radiusAni.setEndValue(self.radius-5)
        self.radiusAni.setDuration(100)
        self.radiusAni.start()

    def setPaintRadius(self, radius: int):
        """ set the smallest radius of button """
        self.__paintRadius = radius
        self.update()

    def getPaintRadius(self):
        return self.__paintRadius

    paintRadius = pyqtProperty(int, getPaintRadius, setPaintRadius)
