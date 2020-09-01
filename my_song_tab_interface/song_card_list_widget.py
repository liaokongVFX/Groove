# coding:utf-8

from copy import deepcopy
from json import dump
from time import time

from PyQt5.QtCore import QEvent, QPoint, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QIcon, QPainter
from PyQt5.QtWidgets import QAction, QLabel, QListWidgetItem

from get_info.get_song_info import SongInfo
from my_dialog_box import PropertyPanel, SongInfoEditPanel
from my_widget.my_listWidget import ListWidget

from .song_card import SongCard
from .song_card_list_context_menu import SongCardListContextMenu


class SongCardListWidget(ListWidget):
    """ 定义一个歌曲卡列表视图 """

    playSignal = pyqtSignal(dict)
    nextPlaySignal = pyqtSignal(dict)
    removeItemSignal = pyqtSignal(int)
    addSongToPlaylistSignal = pyqtSignal(dict)
    editSongCardSignal = pyqtSignal(dict, dict)
    checkedSongCardNumChanged = pyqtSignal(int)
    selectionModeStateChanged = pyqtSignal(bool)
    switchToAlbumInterfaceSig = pyqtSignal(str, str)

    def __init__(self, target_path_list: list, parent=None):
        super().__init__(parent)
        self.target_path_list = target_path_list
        self.songInfo = SongInfo(self.target_path_list)
        self.currentIndex = 0
        self.previousIndex = 0
        self.playingIndex = 0  # 正在播放的歌曲卡下标
        self.playingSongInfo = None
        self.isInSelectionMode = False
        self.isAllSongCardsChecked = False
        if self.songInfo.songInfo_list:
            self.playingSongInfo = self.songInfo.songInfo_list[0]
        self.sortMode = '添加时间'
        self.resize(1150, 758)
        # 初始化列表
        self.item_list = []
        self.songCard_list = []
        self.checkedSongCard_list = []
        # 创建右击菜单
        self.contextMenu = SongCardListContextMenu(self)
        # 创建歌曲卡
        self.createSongCards()
        # 初始化
        self.__initWidget()

    def __initWidget(self):
        """ 初始化小部件 """
        self.update()
        self.setAlternatingRowColors(True)
        # 将滚动模式改为以像素计算
        self.setVerticalScrollMode(self.ScrollPerPixel)
        # 设置层叠样式
        self.__setQss()
        # 信号连接到槽
        self.__connectSignalToSlot()

    def createSongCards(self):
        """ 清空列表并创建新歌曲卡 """
        for songCard in self.songCard_list:
            SongCard.deleteLater()
        self.songCard_list.clear()
        self.item_list.clear()
        self.clear()
        # 对歌曲进行排序
        self.songInfo.sortByCreateTime()
        for i in range(len(self.songInfo.songInfo_list)):
            # 添加空项目
            songInfo_dict = self.songInfo.songInfo_list[i]
            item = QListWidgetItem()
            # 将项目的内容重置为自定义类
            songCard = SongCard(songInfo_dict)
            songCard.itemIndex = i
            songCard.resize(1150, 60)
            item.setSizeHint(QSize(songCard.width(), 60))
            self.addItem(item)
            self.setItemWidget(item, songCard)
            # 将项目添加到项目列表中
            self.songCard_list.append(songCard)
            self.item_list.append(item)
            # 歌曲卡信号连接到槽
            self.__connectSongCardSignalToSlot(songCard)
        # 添加一个空白item来填补playBar所占高度
        self.placeholderItem = QListWidgetItem(self)
        self.placeholderItem.setSizeHint(QSize(1150, 145))
        self.addItem(self.placeholderItem)

    def __playButtonSlot(self, index):
        """ 歌曲卡播放按钮槽函数 """
        self.playSignal.emit(self.songCard_list[index].songInfo)
        self.setCurrentIndex(index)
        self.setPlay(index)

    def setCurrentIndex(self, index):
        """ 设置当前下标 """
        if not self.isInSelectionMode:
            # 不处于选择模式时将先前选中的歌曲卡设置为非选中状态
            if index != self.currentIndex:
                self.songCard_list[self.currentIndex].setSelected(False)
                self.songCard_list[index].setSelected(True)
        else:
            # 如果处于选中模式下点击了歌曲卡则取反选中的卡的选中状态
            songCard = self.songCard_list[index]  # type:SongCard
            songCard.setChecked(not songCard.isChecked)
        self.currentIndex = index

    def contextMenuEvent(self, e: QContextMenuEvent):
        """ 重写鼠标右击时间的响应函数 """
        hitIndex = self.indexAt(e.pos()).column()
        # 显示右击菜单
        if hitIndex > -1:
            self.contextMenu.exec(self.cursor().pos())

    def __removeSongCard(self, index):
        """ 删除选中的歌曲卡 """
        songCard = self.songCard_list.pop(index)
        songCard.deleteLater()
        self.item_list.pop(index)
        self.takeItem(index)
        # 更新下标
        for i in range(index, len(self.songCard_list)):
            self.songCard_list[i].itemIndex = i
        if self.currentIndex > index:
            self.currentIndex -= 1
        # 发送信号
        self.removeItemSignal.emit(index)
        self.update()

    def __emitCurrentChangedSignal(self, index):
        """ 发送当前播放的歌曲卡变化信号，同时更新样式和歌曲信息卡 """
        # 处于选择模式时不发送信号
        if self.isInSelectionMode:
            return
        self.setPlay(index)
        # 发送歌曲信息更新信号
        self.playSignal.emit(self.songCard_list[index].songInfo)

    def setPlay(self, index):
        """ 设置播放状态 """
        if self.songCard_list:
            self.songCard_list[self.playingIndex].setPlay(False)
            self.songCard_list[self.currentIndex].setSelected(False)
            self.songCard_list[index].setPlay(True)
            self.currentIndex = index
            self.playingIndex = index  # 更新正在播放的下标
            self.playingSongInfo = self.songInfo.songInfo_list[index]

    def showPropertyPanel(self, songInfo: dict = None):
        """ 显示selected的歌曲卡的属性 """
        songInfo = self.songCard_list[self.currentRow(
        )].songInfo if not songInfo else songInfo
        propertyPanel = PropertyPanel(songInfo, self.window())
        propertyPanel.exec_()

    def showSongInfoEditPanel(self, songCard: SongCard = None):
        """ 显示编辑歌曲信息面板 """
        if not songCard:
            # 歌曲卡默认为当前右键点击的歌曲卡
            songCard = self.songCard_list[self.currentRow()]
        # 获取歌曲卡下标和歌曲信息
        index = self.songCard_list.index(songCard)
        current_dict = songCard.songInfo
        oldSongInfo = deepcopy(current_dict)
        songInfoEditPanel = SongInfoEditPanel(current_dict, self.window())
        songInfoEditPanel.exec_()
        # 更新歌曲卡和歌曲信息列表
        songCard.updateSongCard(current_dict)
        self.songInfo.songInfo_list[index] = current_dict
        # 将修改的信息存入json文件
        with open('Data\\songInfo.json', 'w', encoding='utf-8') as f:
            dump(self.songInfo.songInfo_list, f)
        # 发出编辑歌曲信息完成信号
        self.editSongCardSignal.emit(oldSongInfo, current_dict)

    def __setQss(self):
        """ 设置层叠样式 """
        with open('resource\\css\\songTabInterfaceSongListWidget.qss', encoding='utf-8') as f:
            self.setStyleSheet(f.read())

    def resizeEvent(self, e):
        """ 更新item的尺寸 """
        super().resizeEvent(e)
        for item in self.item_list:
            item.setSizeHint(QSize(self.width(), 60))
        self.placeholderItem.setSizeHint(QSize(self.width(), 145))

    def updateSongCardInfo(self):
        """ 重新扫描歌曲文件夹并更新歌曲卡信息 """
        self.songInfo = SongInfo(self.target_path_list)
        self.setSortMode(self.sortMode)

    def setSortMode(self, sortMode: str):
        """ 根据当前的排序模式来排序歌曲开 """
        self.sortMode = sortMode
        if self.sortMode == '添加时间':
            self.songInfo.sortByCreateTime()
        elif self.sortMode == 'A到Z':
            self.songInfo.sortByDictOrder()
        elif self.sortMode == '歌手':
            self.songInfo.sortBySonger()
        self.updateSongCards(self.songInfo.songInfo_list)
        if self.playingSongInfo in self.songInfo.songInfo_list:
            self.setPlay(self.songInfo.songInfo_list.index(
                self.playingSongInfo))

    def updateSongCards(self, songInfoDict_list: list):
        """ 更新所有歌曲卡的信息 """
        for i in range(len(songInfoDict_list)):
            songInfo_dict = songInfoDict_list[i]
            self.songCard_list[i].updateSongCard(songInfo_dict)

    def paintEvent(self, e):
        """ 绘制白色背景 """
        super().paintEvent(e)
        painter = QPainter(self.viewport())
        painter.setPen(Qt.white)
        painter.setBrush(Qt.white)
        painter.drawRect(0, 60 * len(self.songCard_list),
                         self.width(), self.height())

    def updateOneSongCard(self, oldSongInfo: dict, newSongInfo, isNeedWriteToFile=True):
        """ 更新一个歌曲卡 """
        if oldSongInfo in self.songInfo.songInfo_list:
            index = self.songInfo.songInfo_list.index(
                oldSongInfo)
            self.songInfo.songInfo_list[index] = newSongInfo
            self.songCard_list[index].updateSongCard(
                newSongInfo)
            if isNeedWriteToFile:
                # 将修改的信息存入json文件
                with open('Data\\songInfo.json', 'w', encoding='utf-8') as f:
                    dump(self.songInfo.songInfo_list, f)

    def updateMultiSongCards(self, oldSongInfo_list: list, newSongInfo_list: list):
        """ 更新多个歌曲卡 """
        for oldSongInfo, newSongInfo in zip(oldSongInfo_list, newSongInfo_list):
            self.updateOneSongCard(oldSongInfo, newSongInfo, False)
        # 将修改的信息存入json文件
        with open('Data\\songInfo.json', 'w', encoding='utf-8') as f:
            dump(self.songInfo.songInfo_list, f)

    def __songCardCheckedStateChanedSlot(self, itemIndex: int, isChecked: bool):
        """ 歌曲卡选中状态改变对应的槽函数 """
        songCard = self.songCard_list[itemIndex]
        # 如果歌曲卡不在选中的歌曲列表中且该歌曲卡变为选中状态就将其添加到列表中
        if songCard not in self.checkedSongCard_list and isChecked:
            self.checkedSongCard_list.append(songCard)
            self.checkedSongCardNumChanged.emit(
                len(self.checkedSongCard_list))
        # 如果歌曲卡已经在列表中且该歌曲卡变为非选中状态就弹出该歌曲卡
        elif songCard in self.checkedSongCard_list and not isChecked:
            self.checkedSongCard_list.pop(
                self.checkedSongCard_list.index(songCard))
            self.checkedSongCardNumChanged.emit(
                len(self.checkedSongCard_list))
        # 如果先前不处于选择模式那么这次发生选中状态改变就进入选择模式
        if not self.isInSelectionMode:
            # 更新当前下标
            self.setCurrentIndex(itemIndex)
            # 所有歌曲卡进入选择模式
            self.__setAllSongCardSelectionModeOpen(True)
            # 发送信号要求主窗口隐藏播放栏
            self.selectionModeStateChanged.emit(True)
            # 更新标志位
            self.isInSelectionMode = True
        else:
            if not self.checkedSongCard_list:
                # 所有歌曲卡退出选择模式
                self.__setAllSongCardSelectionModeOpen(False)
                # 发送信号要求主窗口显示播放栏
                self.selectionModeStateChanged.emit(False)
                # 更新标志位
                self.isInSelectionMode = False

    def __setAllSongCardSelectionModeOpen(self, isOpenSelectionMode: bool):
        """ 设置所有歌曲卡是否进入选择模式 """
        cursor = [Qt.PointingHandCursor, Qt.ArrowCursor][isOpenSelectionMode]
        for songCard in self.songCard_list:
            songCard.setSelectionModeOpen(isOpenSelectionMode)
            songCard.songerLabel.setCursor(cursor)
            songCard.albumLabel.setCursor(cursor)

    def setAllSongCardCheckedState(self, isAllChecked: bool):
        """ 设置所有的歌曲卡checked状态 """
        if self.isAllSongCardsChecked == isAllChecked:
            return
        self.isAllSongCardsChecked = isAllChecked
        for songCard in self.songCard_list:
            songCard.setChecked(isAllChecked)

    def unCheckSongCards(self):
        """ 取消所有已处于选中状态的歌曲卡的选中状态 """
        checkedSongCard_list_copy = self.checkedSongCard_list.copy()
        for songCard in checkedSongCard_list_copy:
            songCard.setChecked(False)

    def __connectSignalToSlot(self):
        """ 信号连接到槽 """
        self.contextMenu.playAct.triggered.connect(
            lambda: self.playSignal.emit(self.songCard_list[self.currentRow()].songInfo))
        self.contextMenu.nextSongAct.triggered.connect(
            lambda: self.nextPlaySignal.emit(self.songCard_list[self.currentRow()].songInfo))
        self.contextMenu.editInfoAct.triggered.connect(
            self.showSongInfoEditPanel)
        self.contextMenu.showPropertyAct.triggered.connect(
            self.showPropertyPanel)
        self.contextMenu.showAlbumAct.triggered.connect(
            lambda: self.switchToAlbumInterfaceSig.emit(
                self.songCard_list[self.currentRow()].album,
                self.songCard_list[self.currentRow()].songer))
        self.contextMenu.deleteAct.triggered.connect(
            lambda: self.__removeSongCard(self.currentRow()))
        self.contextMenu.addToMenu.playingAct.triggered.connect(
            lambda: self.addSongToPlaylistSignal.emit(self.songCard_list[self.currentRow()].songInfo))
        self.contextMenu.selectAct.triggered.connect(
            lambda: self.songCard_list[self.currentRow()].setChecked(True))

    def __connectSongCardSignalToSlot(self, songCard: SongCard):
        """ 将歌曲卡信号连接到槽 """
        songCard.doubleClicked.connect(self.__emitCurrentChangedSignal)
        songCard.playButtonClicked.connect(self.__playButtonSlot)
        songCard.clicked.connect(self.setCurrentIndex)
        songCard.switchToAlbumInterfaceSig.connect(
            self.switchToAlbumInterfaceSig)
        songCard.checkedStateChanged.connect(
            self.__songCardCheckedStateChanedSlot)
