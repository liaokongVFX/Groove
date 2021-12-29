# coding:utf-8

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QPixmap

from common.image_process_utils import getBlurPixmap


class BlurCoverThread(QThread):
    """ 磨砂专辑封面线程 """

    blurFinished = pyqtSignal(QPixmap)

    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置磨砂标志位
        self.albumCoverPath = ""
        self.blurPixmap = None
        self.blurRadius = 7
        self.bluredPicMaxSize = (450, 450)

    def __blurAlbumCover(self):
        """ 得到磨砂后的pixmap """
        self.blurPixmap = getBlurPixmap(
            self.albumCoverPath, self.blurRadius, 0.85, self.bluredPicMaxSize)

    def run(self):
        """ 开始磨砂 """
        if self.albumCoverPath:
            self.__blurAlbumCover()
            self.blurFinished.emit(self.blurPixmap)

    def setTargetCover(self, albumCoverPath: str, blurRadius=6, bluredPicMaxSize: tuple = (450, 450)):
        """ 设置磨砂的目标图片

        Parameters
        ----------
        albumCoverPath: str
            专辑封面路径

        blurRadius: int
            磨砂半径

        blurPicMaxSize: tuple
            图片的最大尺寸，如果实际图片超过这个尺寸将被缩放以加快运算速度
        """
        self.albumCoverPath = albumCoverPath
        self.blurRadius = blurRadius
        self.bluredPicMaxSize = bluredPicMaxSize
