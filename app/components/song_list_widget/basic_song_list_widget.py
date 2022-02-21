# coding:utf-8
from typing import List

from common.database.entity import SongInfo
from common.signal_bus import signalBus
from components.dialog_box.song_info_edit_dialog import SongInfoEditDialog
from components.dialog_box.song_property_dialog import SongPropertyDialog
from components.widgets.list_widget import ListWidget
from PyQt5.QtCore import QMargins, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QResizeEvent
from PyQt5.QtWidgets import QApplication, QListWidgetItem, QWidget

from .song_card import BasicSongCard, SongCardFactory
from .song_card_type import SongCardType


class BasicSongListWidget(ListWidget):
    """ song list widget base class """

    emptyChangedSig = pyqtSignal(bool)           # 歌曲卡是否为空
    removeSongSignal = pyqtSignal(SongInfo)      # 刪除歌曲列表中的一首歌
    songCardNumChanged = pyqtSignal(int)         # 歌曲数量发生改变
    checkedNumChanged = pyqtSignal(int, bool)    # 选中的歌曲卡数量发生改变

    def __init__(self, songInfos: List[SongInfo], songCardType: SongCardType, parent=None,
                 viewportMargins=QMargins(30, 0, 30, 0), paddingBottomHeight: int = 116):
        """
        Parameters
        ----------
        songInfos: List[SongInfo]
            song information list

        songCardType: SongCardType
            song card type

        parent:
            parent window

        viewportMargins: QMargins
            viewport margins

        paddingBottomHeight: int
            leave a blank at the bottom. If it is `0` or `None`, it will not be added.
        """
        super().__init__(parent)
        self.__songCardType = songCardType
        self.paddingBottomHeight = paddingBottomHeight
        self.songInfos = songInfos if songInfos else []
        self.currentIndex = 0
        self.playingIndex = 0  # the index of playing song card
        self.playingSongInfo = self.songInfos[0] if songInfos else None

        self.isInSelectionMode = False

        self.item_list = []
        self.songCards = []
        self.checkedSongCards = []

        self.setAlternatingRowColors(True)
        self.setViewportMargins(viewportMargins)

        signalBus.playBySongInfoSig.connect(self.setPlayBySongInfo)

    def createSongCards(self):
        """ 清空列表并创建新歌曲卡 """
        self.clearSongCards()
        for songInfo in self.songInfos:
            self.appendOneSongCard(songInfo)
            QApplication.processEvents()

        self.__createPaddingBottomItem()

    def appendOneSongCard(self, songInfo: SongInfo):
        """ append a song card to list widget, this does not change `songInfos` property

        Parameters
        ----------
        songInfo: SongInfo
            song information
        """
        item = QListWidgetItem()
        songCard = SongCardFactory.create(self.songCardType, songInfo)
        songCard.itemIndex = len(self.songCards)

        # adjust song card width
        margin = self.viewportMargins()
        size = QSize(self.width()-margin.left()-margin.right(), 60)
        QApplication.sendEvent(songCard, QResizeEvent(size, songCard.size()))
        QApplication.processEvents()
        songCard.resize(size)

        item.setSizeHint(QSize(songCard.width(), 60))

        self.addItem(item)
        self.setItemWidget(item, songCard)
        self.songCards.append(songCard)
        self.item_list.append(item)

        self._connectSongCardSignalToSlot(songCard)

    def appendSongCards(self, songInfos: List[SongInfo]):
        """ append song cards to list widget, this does not change `songInfos` property

        Parameters
        ----------
        songInfos: List[SongInfo]
            song information list
        """
        self.__removePaddingBottomItem()

        for songInfo in songInfos:
            self.appendOneSongCard(songInfo)

        self.__createPaddingBottomItem()

    def setCurrentIndex(self, index):
        """ set currently selected song card """
        if not self.isInSelectionMode:
            if index != self.currentIndex:
                self.songCards[self.currentIndex].setSelected(False)
                self.songCards[index].setSelected(True)
        else:
            songCard = self.songCards[index]
            songCard.setChecked(not songCard.isChecked)

        self.currentIndex = index

    def removeSongCard(self, index: int):
        """ remove a song card """
        songCard = self.songCards.pop(index)
        songCard.deleteLater()
        self.item_list.pop(index)
        self.songInfos.pop(index)
        self.takeItem(index)

        # update item index
        for i in range(index, len(self.songCards)):
            self.songCards[i].itemIndex = i

        if self.currentIndex >= index:
            self.currentIndex -= 1
            self.playingIndex -= 1

        self.songCardNumChanged.emit(len(self.songCards))
        self.update()

    def removeSongCards(self, songPaths: List[str]):
        """ remove multi song cards """
        for songCard in self.songCards.copy():
            if songCard.songPath in songPaths:
                self.removeSongCard(songCard.itemIndex)

    def setPlay(self, index: int):
        """ set the playing song card """
        if not self.songCards:
            return

        self.songCards[self.currentIndex].setSelected(False)
        self.currentIndex = index
        self.songCards[self.playingIndex].setPlay(False)
        self.playingIndex = index

        if index >= 0:
            self.songCards[index].setPlay(True)
            self.playingSongInfo = self.songInfos[index]

    def setPlayBySongInfo(self, songInfo: SongInfo):
        """ set the song card playback status. If the song is not in current song list,
            the song card being played will be canceled play status.
        """
        index = self.index(songInfo)
        if index is not None:
            self.setPlay(index)
        else:
            self.cancelPlayState()

    def cancelPlayState(self):
        """ cancel the playback status of the song card which is playing """
        if not self.songCards or self.playingIndex is None:
            return

        self.songCards[self.playingIndex].setPlay(False)
        self.currentIndex = 0
        self.playingIndex = 0
        self.playingSongInfo = None

    def showSongPropertyDialog(self, songInfo: SongInfo = None):
        """ show song property dialog box """
        if not songInfo:
            songInfo = self.currentSongInfo

        w = SongPropertyDialog(songInfo, self.window())
        w.exec_()

    def showSongInfoEditDialog(self, songInfo: SongInfo = None):
        """ show song information edit dialog box """
        if not songInfo:
            songInfo = self.currentSongInfo

        w = SongInfoEditDialog(songInfo, self.window())
        w.saveInfoSig.connect(signalBus.editSongInfoSig)
        w.exec_()

    def updateOneSongCard(self, newSongInfo: SongInfo):
        """ update a song card """
        for i, songInfo in enumerate(self.songInfos):
            if songInfo.file == newSongInfo.file:
                self.songInfos[i] = newSongInfo
                self.songCards[i].updateSongCard(newSongInfo)

    def updateMultiSongCards(self, songInfos: list):
        """ update multi song cards """
        for songInfo in songInfos:
            self.updateOneSongCard(songInfo)

    def resizeEvent(self, e):
        super().resizeEvent(e)

        margins = self.viewportMargins()  # type:QMargins
        size = QSize(self.width() - margins.left() - margins.right(), 60)
        for item in self.item_list:
            item.setSizeHint(size)

        if self.paddingBottomHeight:
            self.paddingBottomItem.setSizeHint(
                QSize(size.width(), self.paddingBottomHeight))

    def onSongCardCheckedStateChanged(self, itemIndex: int, isChecked: bool):
        """ song card checked state changed slot """
        songCard = self.songCards[itemIndex]

        N0 = len(self.checkedSongCards)

        if songCard not in self.checkedSongCards and isChecked:
            self.checkedSongCards.append(songCard)
        elif songCard in self.checkedSongCards and not isChecked:
            self.checkedSongCards.remove(songCard)
        else:
            return

        N1 = len(self.checkedSongCards)

        if N0 == 0 and N1 > 0:
            self.setCurrentIndex(itemIndex)
            self.__setAllSongCardSelectionModeOpen(True)
            self.isInSelectionMode = True
        elif N1 == 0:
            self.__setAllSongCardSelectionModeOpen(False)
            self.isInSelectionMode = False

        isAllChecked = N1 == len(self.songCards)
        self.checkedNumChanged.emit(N1, isAllChecked)

    def __setAllSongCardSelectionModeOpen(self, isOpen: bool):
        """ set whether all song cards enter selection mode """
        cursor = Qt.ArrowCursor if isOpen else Qt.PointingHandCursor

        for songCard in self.songCards:
            songCard.setSelectionModeOpen(isOpen)
            songCard.setClickableLabelCursor(cursor)

    def setAllChecked(self, isChecked: bool):
        """ set the checked state of all song cards """
        for songCard in self.songCards:
            songCard.setChecked(isChecked)

    def uncheckAll(self):
        """ uncheck all song cards """
        for songCard in self.checkedSongCards.copy():
            songCard.setChecked(False)

    def updateAllSongCards(self, songInfos: List[SongInfo]):
        """ update all song cards

        Parameters
        ----------
        songInfos: List[SongInfo]
            song information list
        """
        self.__removePaddingBottomItem()

        # cancel the current song card playback status
        if self.songCards:
            self.songCards[self.currentIndex].setPlay(False)

        newSongNum = len(songInfos)
        oldSongNum = len(self.songCards)
        if newSongNum > oldSongNum:
            # create new song cards
            for songInfo in songInfos[oldSongNum:]:
                self.appendOneSongCard(songInfo)
                QApplication.processEvents()

        elif newSongNum < oldSongNum:
            # delete song cards
            for i in range(oldSongNum - 1, newSongNum - 1, -1):
                self.item_list.pop()
                songCard = self.songCards.pop()
                songCard.deleteLater()
                self.takeItem(i)
                QApplication.processEvents()

        if not (bool(self.songInfos) and bool(songInfos)):
            self.emptyChangedSig.emit(not bool(songInfos))

        # update part of song cards
        self.songInfos = songInfos
        n = min(oldSongNum, newSongNum)
        for songInfo, songCard in zip(songInfos[:n], self.songCards[:n]):
            songCard.updateSongCard(songInfo)

        self.currentIndex = 0
        self.playingIndex = 0
        self.playingSongInfo = None
        for songCard in self.songCards:
            songCard.setPlay(False)

        self.__createPaddingBottomItem()

        if oldSongNum != newSongNum:
            self.songCardNumChanged.emit(len(self.songInfos))

    def clearSongCards(self):
        """ clear song cards """
        self.item_list.clear()
        self.clear()

        for songCard in self.songCards:
            songCard.deleteLater()

        self.songCards.clear()
        self.currentIndex = 0
        self.playingIndex = 0

    def sortSongInfo(self, key: str, reverse=True):
        """ sort song information list

        Parameters
        ----------
        key: str
            sorting basis, including `createTime`, `title`, `singer` and `track`

        reverse: bool
            Is it descending, only valid for the first three sorting keys
        """
        if key != "track":
            songInfo = sorted(
                self.songInfos,
                key=lambda songInfo: songInfo[key],
                reverse=reverse
            )
        else:
            songInfo = sorted(
                self.songInfos,
                key=lambda songInfo: songInfo.track
            )

        return songInfo

    def __createPaddingBottomItem(self):
        """ create padding item in bottom """
        if not self.paddingBottomHeight:
            return

        self.paddingBottomItem = QListWidgetItem(self)

        # create padding widget
        self.paddingBottomWidget = QWidget(self)
        self.paddingBottomWidget.setStyleSheet("background:white")
        self.paddingBottomWidget.setFixedHeight(self.paddingBottomHeight)

        margins = self.viewportMargins()  # type:QMargins
        width = self.width() - margins.left() - margins.right()
        self.paddingBottomWidget.resize(width, self.paddingBottomHeight)
        self.paddingBottomItem.setSizeHint(
            QSize(width, self.paddingBottomHeight))
        self.setItemWidget(self.paddingBottomItem, self.paddingBottomWidget)
        self.addItem(self.paddingBottomItem)

    def __removePaddingBottomItem(self):
        """ create the padding item in bottom """
        if self.paddingBottomHeight:
            self.removeItemWidget(self.paddingBottomItem)
            self.takeItem(len(self.songCards))

    @property
    def songCardType(self) -> SongCardType:
        return self.__songCardType

    def _connectSongCardSignalToSlot(self, songCard):
        """ connect song card signal to slot """
        raise NotImplementedError

    def songCardNum(self) -> int:
        return len(self.songCards)

    def index(self, songInfo: SongInfo):
        """ get the index of song information, return `None` if it's not in the list """
        if songInfo in self.songInfos:
            return self.songInfos.index(songInfo)

        return None

    @property
    def currentSongCard(self) -> BasicSongCard:
        return self.songCards[self.currentRow()]

    @property
    def currentSongInfo(self) -> SongInfo:
        return self.currentSongCard.songInfo
