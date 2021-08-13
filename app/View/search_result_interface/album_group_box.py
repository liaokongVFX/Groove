# coding:utf-8
from copy import deepcopy
from typing import List

from app.components.album_card import AlbumBlurBackground
from app.components.album_card import AlbumCard as AlbumCardBase
from app.components.buttons.three_state_button import ThreeStatePushButton
from app.components.dialog_box.message_dialog import MessageDialog
from app.components.layout.h_box_layout import HBoxLayout
from app.components.menu import AddToMenu, DWMMenu
from PyQt5.QtCore import (QParallelAnimationGroup, QEasingCurve, QPoint,
                          QPropertyAnimation, QSize, Qt, pyqtSignal)
from PyQt5.QtGui import QContextMenuEvent, QIcon
from PyQt5.QtWidgets import (QAction, QApplication, QLabel, QScrollArea,
                             QToolButton, QWidget, QGraphicsOpacityEffect, QPushButton)


class AlbumGroupBox(QScrollArea):
    """ 专辑分组框 """

    playSig = pyqtSignal(list)
    nextToPlaySig = pyqtSignal(list)
    deleteAlbumSig = pyqtSignal(list)
    addAlbumToPlayingSig = pyqtSignal(list)
    switchToAlbumInterfaceSig = pyqtSignal(str, str)
    addAlbumToNewCustomPlaylistSig = pyqtSignal(list)
    addAlbumToCustomPlaylistSig = pyqtSignal(str, list)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.albumCard_list = []  # type:List[AlbumCard]
        self.albumInfo_list = []  # type:List[dict]
        self.titleButton = QPushButton('专辑', self)
        self.showAllButton = ThreeStatePushButton(
            {
                "normal": "app/resource/images/search_result_interface/ShowAll_normal.png",
                "hover": "app/resource/images/search_result_interface/ShowAll_hover.png",
                "pressed": "app/resource/images/search_result_interface/ShowAll_pressed.png",
            },
            '  显示全部',
            (14, 14),
            self,
        )
        self.scrollRightButton = QToolButton(self)
        self.scrollLeftButton = QToolButton(self)
        self.opacityAniGroup = QParallelAnimationGroup(self)
        self.leftOpacityEffect = QGraphicsOpacityEffect(self)
        self.rightOpacityEffect = QGraphicsOpacityEffect(self)
        self.leftOpacityAni = QPropertyAnimation(
            self.leftOpacityEffect, b'opacity', self)
        self.rightOpacityAni = QPropertyAnimation(
            self.rightOpacityEffect, b'opacity', self)
        self.scrollAni = QPropertyAnimation(
            self.horizontalScrollBar(), b'value', self)
        self.scrollWidget = QWidget(self)
        self.hBox = HBoxLayout(self.scrollWidget)
        self.albumBlurBackground = AlbumBlurBackground(self.scrollWidget)
        self.leftMask = QWidget(self)
        self.rightMask = QWidget(self)
        self.__initWidget()

    def __initWidget(self):
        """ 初始化小部件 """
        self.setFixedHeight(343)
        self.setWidget(self.scrollWidget)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollLeftButton.raise_()
        self.scrollRightButton.raise_()
        self.albumBlurBackground.lower()
        self.hBox.setSpacing(20)
        self.hBox.setContentsMargins(35, 47, 65, 0)
        self.__setQss()
        self.titleButton.move(37, 0)
        self.leftMask.move(0, 47)
        self.leftMask.resize(35, 296)
        self.rightMask.resize(65, 296)
        self.scrollLeftButton.move(35, 42)
        self.scrollLeftButton.setFixedSize(25, 301)
        self.scrollRightButton.setFixedSize(25, 301)
        self.scrollLeftButton.setIconSize(QSize(15, 15))
        self.scrollRightButton.setIconSize(QSize(15, 15))
        self.scrollLeftButton.setIcon(
            QIcon('app/resource/images/search_result_interface/ChevronLeft.png'))
        self.scrollRightButton.setIcon(
            QIcon('app/resource/images/search_result_interface/ChevronRight.png'))
        self.scrollLeftButton.setGraphicsEffect(self.leftOpacityEffect)
        self.scrollRightButton.setGraphicsEffect(self.rightOpacityEffect)
        self.scrollLeftButton.hide()
        self.scrollRightButton.hide()
        self.leftMask.hide()
        self.resize(1200, 343)
        # 信号连接到槽
        self.horizontalScrollBar().valueChanged.connect(self.__onScrollHorizon)
        self.scrollLeftButton.clicked.connect(self.__onScrollLeftButtonClicked)
        self.scrollRightButton.clicked.connect(
            self.__onScrollRightButtonClicked)

    def __setQss(self):
        """ 设置层叠样式 """
        self.leftMask.setObjectName('leftMask')
        self.rightMask.setObjectName('rightMask')
        self.titleButton.setObjectName('titleButton')
        self.showAllButton.setObjectName('showAllButton')
        with open('app/resource/css/album_group_box.qss', encoding='utf-8') as f:
            self.setStyleSheet(f.read())
        self.titleButton.adjustSize()
        self.showAllButton.adjustSize()

    def resizeEvent(self, e):
        self.rightMask.move(self.width()-65, 47)
        self.scrollRightButton.move(self.width()-90, 42)
        self.showAllButton.move(self.width()-self.showAllButton.width()-65, 2)
        self.scrollWidget.resize(self.scrollWidget.width(), self.height())

    def __onScrollHorizon(self, value):
        """ 水平滚动槽函数 """
        self.leftMask.setHidden(value == 0)
        self.rightMask.setHidden(value == self.horizontalScrollBar().maximum())
        self.scrollLeftButton.setHidden(value == 0)
        self.scrollRightButton.setHidden(
            value == self.horizontalScrollBar().maximum())

    def __onScrollRightButtonClicked(self):
        """ 向右滚动按钮点击槽函数 """
        v = self.horizontalScrollBar().value()
        self.scrollAni.setStartValue(v)
        self.scrollAni.setEndValue(
            min(v+868, self.horizontalScrollBar().maximum()))
        self.scrollAni.setDuration(450)
        self.scrollAni.setEasingCurve(QEasingCurve.OutQuad)
        self.scrollAni.start()

    def __onScrollLeftButtonClicked(self):
        """ 向左滚动按钮点击槽函数 """
        v = self.horizontalScrollBar().value()
        self.scrollAni.setStartValue(v)
        self.scrollAni.setEndValue(max(v-868, 0))
        self.scrollAni.setDuration(450)
        self.scrollAni.setEasingCurve(QEasingCurve.OutQuad)
        self.scrollAni.start()

    def __createOneAlbumCard(self, albumInfo: dict):
        """ 创建一个专辑卡 """
        albumCard = AlbumCard(albumInfo, self.scrollWidget)
        self.albumCard_list.append(albumCard)
        self.hBox.addWidget(albumCard)
        # 专辑卡信号连接到槽函数
        albumCard.playSignal.connect(self.playSig)
        albumCard.nextPlaySignal.connect(self.nextToPlaySig)
        albumCard.deleteCardSig.connect(self.__showDeleteOneCardDialog)
        albumCard.addToPlayingSignal.connect(self.addAlbumToPlayingSig)
        albumCard.switchToAlbumInterfaceSig.connect(
            self.switchToAlbumInterfaceSig)
        albumCard.showBlurAlbumBackgroundSig.connect(
            self.__showBlurAlbumBackground)
        albumCard.hideBlurAlbumBackgroundSig.connect(
            self.albumBlurBackground.hide)
        albumCard.addAlbumToCustomPlaylistSig.connect(
            self.addAlbumToCustomPlaylistSig)
        albumCard.addAlbumToNewCustomPlaylistSig.connect(
            self.addAlbumToNewCustomPlaylistSig)

    def __showBlurAlbumBackground(self, pos: QPoint, picPath: str):
        """ 显示磨砂背景 """
        # 将全局坐标转为窗口坐标
        pos = self.scrollWidget.mapFromGlobal(pos)
        self.albumBlurBackground.setBlurAlbum(picPath)
        self.albumBlurBackground.move(pos.x() - 31, pos.y() - 16)
        self.albumBlurBackground.show()

    def __showDeleteOneCardDialog(self, albumName: str):
        """ 显示删除一个专辑卡的对话框 """
        songPaths = [i["songPath"] for i in self.sender().songInfo_list]
        title = "是否确定要删除此项？"
        content = f"""如果删除"{albumName}"，它将不再位于此设备上。"""
        w = MessageDialog(title, content, self.window())
        w.yesSignal.connect(lambda: self.deleteAlbums([albumName]))
        w.yesSignal.connect(lambda: self.deleteAlbumSig.emit(songPaths))
        w.exec_()

    def enterEvent(self, e):
        """ 进入窗口时显示滚动按钮 """
        if self.horizontalScrollBar().maximum() == 0:
            return

        # 移除之前的动画
        if self.opacityAniGroup.indexOfAnimation(self.leftOpacityAni) >= 0:
            self.opacityAniGroup.removeAnimation(self.leftOpacityAni)
        if self.opacityAniGroup.indexOfAnimation(self.rightOpacityAni) >= 0:
            self.opacityAniGroup.removeAnimation(self.rightOpacityAni)

        v = self.horizontalScrollBar().value()
        if v != 0:
            self.scrollLeftButton.show()
            self.leftOpacityAni.setStartValue(0)
            self.leftOpacityAni.setEndValue(1)
            self.leftOpacityAni.setDuration(200)
            self.opacityAniGroup.addAnimation(self.leftOpacityAni)

        if v != self.horizontalScrollBar().maximum():
            self.scrollRightButton.show()
            self.rightOpacityAni.setStartValue(0)
            self.rightOpacityAni.setEndValue(1)
            self.rightOpacityAni.setDuration(200)
            self.opacityAniGroup.addAnimation(self.rightOpacityAni)

        self.opacityAniGroup.start()

    def leaveEvent(self, e):
        """ 离开窗口是隐藏滚动按钮 """
        if self.horizontalScrollBar().maximum() == 0:
            return

        # 移除之前的动画
        if self.opacityAniGroup.indexOfAnimation(self.leftOpacityAni) >= 0:
            self.opacityAniGroup.removeAnimation(self.leftOpacityAni)
        if self.opacityAniGroup.indexOfAnimation(self.rightOpacityAni) >= 0:
            self.opacityAniGroup.removeAnimation(self.rightOpacityAni)

        if self.scrollLeftButton.isVisible():
            self.leftOpacityAni.setStartValue(1)
            self.leftOpacityAni.setEndValue(0)
            self.leftOpacityAni.setDuration(200)
            self.opacityAniGroup.addAnimation(self.leftOpacityAni)

        if self.scrollRightButton.isVisible():
            self.rightOpacityAni.setStartValue(1)
            self.rightOpacityAni.setEndValue(0)
            self.leftOpacityAni.setDuration(200)
            self.opacityAniGroup.addAnimation(self.rightOpacityAni)

        self.opacityAniGroup.start()

    def deleteAlbums(self, albumNames: list):
        """ 删除专辑 """
        albumInfo_list = deepcopy(self.albumInfo_list)

        for albumInfo in albumInfo_list.copy():
            if albumInfo["album"] in albumNames:
                albumInfo_list.remove(albumInfo)

        self.updateWindow(albumInfo_list)


    def deleteSongs(self, songPaths: list):
        """ 删除歌曲 """
        albumInfo_list = deepcopy(self.albumInfo_list)
        for albumInfo in albumInfo_list.copy():
            songInfo_list = albumInfo["songInfo_list"]

            for songInfo in songInfo_list.copy():
                if songInfo["songPath"] in songPaths:
                    songInfo_list.remove(songInfo)

            # 如果专辑变成空专辑，就将其从专辑列表中移除
            if not songInfo_list:
                albumInfo_list.remove(albumInfo)

        # 更新窗口
        self.updateWindow(albumInfo_list)

    def updateWindow(self, albumInfo_list: list):
        """ 更新窗口 """
        if albumInfo_list == self.albumInfo_list:
            return

        # 显示遮罩
        self.horizontalScrollBar().setValue(0)
        self.leftMask.hide()
        self.rightMask.show()

        # 根据具体情况增减专辑卡
        newCardNum = len(albumInfo_list)
        oldCardNum = len(self.albumCard_list)
        if newCardNum < oldCardNum:
            # 删除部分专辑卡
            for i in range(oldCardNum - 1, newCardNum - 1, -1):
                albumCard = self.albumCard_list.pop()
                self.hBox.removeWidget(albumCard)
                albumCard.deleteLater()
        elif newCardNum > oldCardNum:
            # 新增部分专辑卡
            for albumInfo in albumInfo_list[oldCardNum:]:
                self.__createOneAlbumCard(albumInfo)
                QApplication.processEvents()

        self.scrollWidget.adjustSize()

        # 更新部分专辑卡
        self.albumInfo_list = deepcopy(albumInfo_list)
        n = oldCardNum if oldCardNum < newCardNum else newCardNum
        for i in range(n):
            albumInfo = albumInfo_list[i]
            self.albumCard_list[i].updateWindow(albumInfo)
            QApplication.processEvents()

        self.setStyle(QApplication.style())


class AlbumCard(AlbumCardBase):
    """ 专辑卡 """

    def contextMenuEvent(self, event: QContextMenuEvent):
        menu = AlbumCardContextMenu(parent=self)
        menu.playAct.triggered.connect(
            lambda: self.playSignal.emit(self.songInfo_list))
        menu.nextToPlayAct.triggered.connect(
            lambda: self.nextPlaySignal.emit(self.songInfo_list))
        menu.addToMenu.playingAct.triggered.connect(
            lambda: self.addToPlayingSignal.emit(self.songInfo_list))
        menu.addToMenu.addSongsToPlaylistSig.connect(
            lambda name: self.addAlbumToCustomPlaylistSig.emit(name, self.songInfo_list))
        menu.addToMenu.newPlaylistAct.triggered.connect(
            lambda: self.addAlbumToNewCustomPlaylistSig.emit(self.songInfo_list))
        menu.deleteAct.triggered.connect(
            lambda: self.deleteCardSig.emit(self.albumName))
        menu.exec(event.globalPos())


class AlbumCardContextMenu(DWMMenu):
    """ 专辑卡右击菜单"""

    def __init__(self, parent):
        super().__init__("", parent)
        self.__createActions()
        self.setObjectName("albumCardContextMenu")
        self.setQss()

    def __createActions(self):
        """ 创建动作 """
        # 创建动作
        self.playAct = QAction("播放", self)
        self.nextToPlayAct = QAction("下一首播放", self)
        self.pinToStartMenuAct = QAction('固定到"开始"菜单', self)
        self.deleteAct = QAction("删除", self)
        self.showSongerAct = QAction("显示歌手", self)
        self.addToMenu = AddToMenu("添加到", self)

        # 添加动作到菜单
        self.addActions([self.playAct, self.nextToPlayAct])
        # 将子菜单添加到主菜单
        self.addMenu(self.addToMenu)
        self.addActions(
            [
                self.showSongerAct,
                self.pinToStartMenuAct,
                self.deleteAct,
            ]
        )
