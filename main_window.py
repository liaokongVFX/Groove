# coding:utf-8

import sys
from ctypes.wintypes import HWND
from PyQt5.QtCore import QPoint, QRect, QSize, Qt
from PyQt5.QtGui import QIcon, QResizeEvent,QPixmap
from PyQt5.QtWidgets import QAction, QApplication, QWidget, QGraphicsDropShadowEffect

from effects.window_effect import WindowEffect
from my_music_interface import MyMusicInterface
from my_title_bar.title_bar import TitleBar
from navigation.navigation_bar import NavigationBar
from navigation.navigation_menu import NavigationMenu
from my_play_bar.play_bar import PlayBar


class MainWindow(QWidget):
    """ 主窗口 """
    def __init__(self, songs_folder, parent=None):
        super().__init__(parent)
        
        # 实例化窗口特效
        self.windowEffect = WindowEffect()
        # 实例化小部件
        self.titleBar = TitleBar(self)
        self.navigationBar = NavigationBar(self)
        self.navigationMenu = NavigationMenu(self)
        self.currentNavigation = self.navigationBar
        self.myMusicInterface = MyMusicInterface(songs_folder, self)
        songInfo = {
            'songName': 'オーダーメイド (定制品)', 'songer': 'RADWIMPS',
            'album': [r'resource\Album Cover\オーダーメイド\オーダーメイド.jpg']}
        self.currentRightWindow = self.myMusicInterface
        self.titleBar = TitleBar(self)
        self.playBar = PlayBar(songInfo,self)
        # 初始化界面
        self.initWidget()

    def initWidget(self):
        """ 初始化小部件 """
        self.resize(1360, 970)
        self.setObjectName('mainWindow')
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setStyleSheet('QWidget#mainWindow{background:transparent}')
        self.setAttribute(Qt.WA_TranslucentBackground|Qt.WA_StyledBackground)
        # 居中显示
        desktop = QApplication.desktop()
        self.move(int(desktop.width() / 2 - self.width() / 2),
                  int((desktop.height()-120) / 2 - self.height() / 2))
        # 标题栏置顶
        self.titleBar.raise_()
        # 隐藏导航菜单
        self.navigationMenu.hide()
        # 设置窗口特效
        self.setWindowEffect()
        # 设置右边子窗口的位置
        self.setWidgetGeometry()
        # 将按钮点击信号连接到槽函数
        self.navigationBar.showMenuButton.clicked.connect(
            self.showNavigationMenu)
        self.navigationBar.searchButton.clicked.connect(
            self.showNavigationMenu)
        self.navigationMenu.showBarButton.clicked.connect(
            self.showNavigationBar)


    def setWindowEffect(self):
        """ 设置窗口特效 """
        # 开启亚克力效果和阴影效果
        self.hWnd = HWND(int(self.winId()))
        self.windowEffect.setAcrylicEffect(self.hWnd, 'F2F2F250', True)


    def setWidgetGeometry(self):
        """ 调整小部件的geometry """
        self.titleBar.resize(self.width(), 40)
        self.navigationBar.resize(60, self.height())
        self.navigationMenu.resize(400, self.height())
        self.currentRightWindow.move(self.currentNavigation.width(), 0)
        self.currentRightWindow.resize(self.width() - self.currentNavigation.width(), self.height())
        self.playBar.resize(self.width(),self.playBar.height())

    def resizeEvent(self, e: QResizeEvent):
        """ 调整尺寸时同时调整子窗口的尺寸 """
        self.setWidgetGeometry()

    def showNavigationMenu(self):
        """ 显示导航菜单和抬头 """
        self.currentNavigation = self.navigationMenu
        self.navigationBar.hide()
        self.navigationMenu.show()
        self.titleBar.title.show()
        self.setWidgetGeometry()
        if self.sender() == self.navigationBar.searchButton:
            self.navigationMenu.searchLineEdit.setFocus()

    def showNavigationBar(self):
        """ 显示导航栏 """
        self.currentNavigation = self.navigationBar
        self.navigationMenu.hide()
        self.titleBar.title.hide()
        self.navigationBar.show()
        self.setWidgetGeometry()

    def moveEvent(self, e):
        if hasattr(self,'playBar'):
            self.playBar.move(self.x()+1, self.y() + self.height() - self.playBar.height()+40)

    def closeEvent(self, e):
        self.playBar.deleteLater()
        e.accept()
        

if __name__ == "__main__":
    app = QApplication(sys.argv)
    demo = MainWindow('D:\\KuGou\\')
    demo.show()
    demo.playBar.show()
    sys.exit(app.exec_())
