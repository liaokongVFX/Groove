# coding:utf-8
from typing import Dict, List

from common.database.entity import SongInfo
from common.os_utils import getCoverPath
from common.signal_bus import signalBus
from common.thread.get_lyric_thread import GetLyricThread
from common.thread.get_mv_url_thread import GetMvUrlThread
from components.buttons.three_state_button import ThreeStatePushButton
from components.dialog_box.message_dialog import MessageDialog
from components.selection_mode_interface.bar import PlayingSelectionModeBar
from components.widgets.label import BlurCoverLabel, MaskLabel
from components.widgets.lyric_widget import LyricWidget
from components.widgets.menu import AddToMenu
from PyQt5.QtCore import (QAbstractAnimation, QEasingCurve, QFile,
                          QParallelAnimationGroup, QPoint, QPropertyAnimation,
                          QSize, Qt, QTimer, pyqtSignal)
from PyQt5.QtGui import QColor
from PyQt5.QtMultimedia import QMediaPlaylist
from PyQt5.QtWidgets import QLabel, QWidget

from .play_bar import PlayBar
from .song_info_card_chute import SongInfoCardChute
from .song_list_widget import SongListWidget


def handleSelectionMode(func):
    """ 处理选择模式装饰器 """

    def wrapper(playingInterface, *args, **kwargs):
        if playingInterface.isInSelectionMode:
            playingInterface.exitSelectionMode()
        return func(playingInterface, *args, **kwargs)

    return wrapper


class PlayingInterface(QWidget):
    """ 正在播放界面 """

    removeSongSignal = pyqtSignal(int)                   # 从播放列表移除歌曲
    savePlaylistSig = pyqtSignal()                       # 保存播放列表
    currentIndexChanged = pyqtSignal(int)                # 当前歌曲改变
    selectionModeStateChanged = pyqtSignal(bool)         # 进入/退出选择模式
    switchToVideoInterfaceSig = pyqtSignal(str)          # 切换到视频界面

    def __init__(self, playlist: List[SongInfo] = None, parent=None):
        super().__init__(parent)
        self.playlist = playlist if playlist else []
        self.currentIndex = 0
        self.isPlaylistVisible = False
        self.isInSelectionMode = True
        self.isLyricVisible = True

        # 创建线程
        self.getLyricThread = GetLyricThread(self)
        self.getMvUrlThread = GetMvUrlThread(self)

        # 创建小部件
        self.albumCoverLabel = BlurCoverLabel(12, (450, 450), self)
        self.maskLabel = MaskLabel(QColor(0, 0, 0, 215), self)
        self.songInfoCardChute = SongInfoCardChute(self.playlist, self)
        self.lyricWidget = LyricWidget(self.songInfoCardChute)
        self.parallelAniGroup = QParallelAnimationGroup(self)
        self.playBar = PlayBar(self)
        self.songListWidget = SongListWidget(self.playlist, self)
        self.selectionModeBar = PlayingSelectionModeBar(self)
        self.guideLabel = QLabel(self.tr(
            "Here, you will see the song being played and the songs to be played."), self)
        self.randomPlayAllButton = ThreeStatePushButton(
            {
                "normal": ":/images/playing_interface/Shuffle_normal.png",
                "hover": ":/images/playing_interface/Shuffle_hover.png",
                "pressed": ":/images/playing_interface/Shuffle_pressed.png",
            },
            self.tr(" Shuffle all songs in your collection"),
            (30, 22),
            self
        )

        # 创建动画
        self.playBarAni = QPropertyAnimation(self.playBar, b"pos")
        self.songInfoCardChuteAni = QPropertyAnimation(
            self.songInfoCardChute, b"pos")
        self.songListWidgetAni = QPropertyAnimation(
            self.songListWidget, b"pos")

        # 创建定时器
        self.showPlaylistTimer = QTimer(self)
        self.hidePlaylistTimer = QTimer(self)

        # 初始化
        self.__initWidget()

    def __initWidget(self):
        """ 初始化小部件 """
        self.resize(1100, 870)
        self.currentSmallestModeSize = QSize(340, 340)
        self.setAttribute(Qt.WA_StyledBackground)
        self.guideLabel.move(45, 62)
        self.lyricWidget.move(0, 60)
        self.randomPlayAllButton.move(45, 117)
        self.playBar.move(0, self.height() - self.playBar.height())

        # 隐藏部件
        self.randomPlayAllButton.hide()
        self.selectionModeBar.hide()
        self.guideLabel.hide()
        self.maskLabel.hide()
        self.playBar.hide()

        # 设置层叠样式
        self.__setQss()

        # 开启磨砂线程
        if self.playlist:
            self.albumCoverLabel.setCover(
                self.songInfoCardChute.cards[1].coverPath)

        # 将信号连接到槽
        self.__connectSignalToSlot()

        # 初始化动画
        self.playBarAni.setDuration(350)
        self.songListWidgetAni.setDuration(350)
        self.songListWidgetAni.setEasingCurve(QEasingCurve.InOutQuad)
        self.playBarAni.setEasingCurve(QEasingCurve.InOutQuad)
        self.parallelAniGroup.addAnimation(self.playBarAni)
        self.parallelAniGroup.addAnimation(self.songInfoCardChuteAni)

        # 初始化定时器
        self.showPlaylistTimer.setInterval(120)
        self.hidePlaylistTimer.setInterval(120)
        self.showPlaylistTimer.timeout.connect(self.showPlayListTimerSlot)
        self.hidePlaylistTimer.timeout.connect(self.hidePlaylistTimerSlot)

    def __setQss(self):
        """ 设置层叠样式 """
        self.setObjectName("playingInterface")
        self.guideLabel.setObjectName("guideLabel")
        self.randomPlayAllButton.setObjectName("randomPlayAllButton")
        f = QFile(":/qss/playing_interface.qss")
        f.open(QFile.ReadOnly)
        self.setStyleSheet(str(f.readAll(), encoding='utf-8'))
        f.close()

    def resizeEvent(self, e):
        """ 改变尺寸时也改变小部件的大小 """
        super().resizeEvent(e)
        self.albumCoverLabel.setFixedSize(self.size())
        self.albumCoverLabel.adjustCover()
        self.maskLabel.resize(self.size())
        self.songInfoCardChute.resize(self.size())
        self.lyricWidget.resize(
            self.width(), self.height()-258-self.lyricWidget.y())
        self.playBar.resize(self.width(), self.playBar.height())
        self.songListWidget.resize(self.width(), self.height() - 382)

        self.selectionModeBar.resize(
            self.width(), self.selectionModeBar.height())
        self.selectionModeBar.move(
            0, self.height()-self.selectionModeBar.height())

        if self.isPlaylistVisible:
            self.playBar.move(0, 190)
            self.songListWidget.move(0, 382)
            self.songInfoCardChute.move(0, 258 - self.height())
        else:
            self.playBar.move(0, self.height() - self.playBar.height())
            self.songListWidget.move(0, self.height())

    def showPlayBar(self):
        """ 显示播放栏 """
        # 只在播放栏不可见的时候显示播放栏和开启动画
        if self.playBar.isVisible():
            return

        self.playBar.show()
        self.songInfoCardChuteAni.setDuration(450)
        self.songInfoCardChuteAni.setEasingCurve(QEasingCurve.OutCubic)
        self.songInfoCardChuteAni.setStartValue(self.songInfoCardChute.pos())
        self.songInfoCardChuteAni.setEndValue(
            QPoint(0, -self.playBar.height() + 68))
        self.songInfoCardChuteAni.start()

    def hidePlayBar(self):
        """ 隐藏播放栏 """
        if not self.playBar.isVisible() or self.isPlaylistVisible:
            return

        self.playBar.hide()
        self.songInfoCardChuteAni.setEasingCurve(QEasingCurve.OutCirc)
        self.songInfoCardChuteAni.setEndValue(QPoint(0, 0))
        self.songInfoCardChuteAni.setStartValue(
            QPoint(0, -self.playBar.height() + 68))
        self.songInfoCardChuteAni.start()

    def showPlaylist(self):
        """ 显示播放列表 """
        if self.songListWidgetAni.state() == QAbstractAnimation.Running:
            return

        self.playBar.showPlaylistButton.setToolTip(
            self.tr('Hide playlist'))
        self.playBar.pullUpArrowButton.setToolTip(self.tr('Hide playlist'))

        self.songInfoCardChuteAni.setDuration(350)
        self.songInfoCardChuteAni.setEasingCurve(QEasingCurve.InOutQuad)
        self.songInfoCardChuteAni.setStartValue(self.songInfoCardChute.pos())
        self.songInfoCardChuteAni.setEndValue(QPoint(0, 258 - self.height()))
        self.playBarAni.setStartValue(self.playBar.pos())
        self.playBarAni.setEndValue(QPoint(0, 190))
        self.songListWidgetAni.setStartValue(self.songListWidget.pos())
        self.songListWidgetAni.setEndValue(
            QPoint(self.songListWidget.x(), 382))

        if self.sender() == self.playBar.showPlaylistButton:
            self.playBar.pullUpArrowButton.timer.start()

        self.playBar.setVisible(len(self.playlist) > 0)
        self.parallelAniGroup.start()
        self.maskLabel.show()
        self.albumCoverLabel.setVisible(len(self.playlist) > 0)
        self.showPlaylistTimer.start()

    def showPlayListTimerSlot(self):
        """ 显示播放列表定时器溢出槽函数 """
        self.showPlaylistTimer.stop()
        self.songListWidgetAni.start()
        self.isPlaylistVisible = True

    def hidePlaylistTimerSlot(self):
        """ 显示播放列表定时器溢出槽函数 """
        self.hidePlaylistTimer.stop()
        self.parallelAniGroup.start()

    @handleSelectionMode
    def hidePlaylist(self):
        """ 隐藏播放列表 """
        if self.parallelAniGroup.state() == QAbstractAnimation.Running:
            return

        self.playBar.showPlaylistButton.setToolTip(
            self.tr('Show playlist'))
        self.playBar.pullUpArrowButton.setToolTip(self.tr('Show playlist'))

        self.songInfoCardChuteAni.setDuration(350)
        self.songInfoCardChuteAni.setEasingCurve(QEasingCurve.InOutQuad)
        self.songInfoCardChuteAni.setStartValue(self.songInfoCardChute.pos())
        self.songInfoCardChuteAni.setEndValue(
            QPoint(0, -self.playBar.height() + 68))
        self.playBarAni.setStartValue(QPoint(0, 190))
        self.playBarAni.setEndValue(
            QPoint(0, self.height() - self.playBar.height()))
        self.songListWidgetAni.setStartValue(self.songListWidget.pos())
        self.songListWidgetAni.setEndValue(
            QPoint(self.songListWidget.x(), self.height()))

        if self.sender() is self.playBar.showPlaylistButton:
            self.playBar.pullUpArrowButton.timer.start()

        # self.parallelAniGroup.start()
        self.songListWidgetAni.start()
        self.hidePlaylistTimer.start()
        self.albumCoverLabel.show()
        self.maskLabel.hide()
        self.isPlaylistVisible = False

    def __onShowPlaylistButtonClicked(self):
        """ 显示或隐藏播放列表 """
        if not self.isPlaylistVisible:
            self.showPlaylist()
        else:
            self.hidePlaylist()

    def setCurrentIndex(self, index):
        """ 更新播放列表下标 """
        if self.currentIndex == index or index <= -1:
            return

        # 在播放列表的最后一首歌被移除时不更新样式
        if index >= len(self.playlist):
            return

        self.currentIndex = index
        self.__getLyric()
        self.songListWidget.setCurrentIndex(index)
        self.songInfoCardChute.setCurrentIndex(index)

    def setPlaylist(self, playlist: List[SongInfo], isResetIndex: bool = True, index=0):
        """ 更新播放列表

        Parameters
        ----------
        playlist: List[SongInfo]
            播放列表

        isResetIndex: bool
            是否重置当前歌曲索引

        index: int
            重置后的当前歌曲索引
        """
        self.playlist = playlist.copy() if playlist else []
        self.currentIndex = index if isResetIndex else self.currentIndex
        self.songInfoCardChute.setPlaylist(self.playlist, isResetIndex, index)
        self.songListWidget.updateSongCards(self.playlist, isResetIndex, index)
        self.albumCoverLabel.setCover(
            self.songInfoCardChute.cards[1].coverPath)

        if self.playlist:
            self.__getLyric()

        # 设置提示标签可见性
        if playlist and not self.songListWidget.isVisible():
            self.__setGuideLabelHidden(True)
        else:
            self.__setGuideLabelHidden(False)

    def setPlay(self, isPlay: bool):
        """ 设置播放状态 """
        self.playBar.playButton.setPlay(isPlay)

    def __settleDownPlayBar(self):
        """ 定住播放栏 """
        self.songInfoCardChute.stopSongInfoCardTimer()

    def __startSongInfoCardTimer(self):
        """ 重新打开歌曲信息卡的定时器 """
        if not self.playBar.volumeSliderWidget.isVisible():
            self.songInfoCardChute.startSongInfoCardTimer()

    def __removeSongFromPlaylist(self, index):
        """ 从播放列表中移除选中的歌曲 """
        n = len(self.playlist)

        if self.currentIndex > index:
            self.currentIndex -= 1
            self.songInfoCardChute.currentIndex -= 1

        elif self.currentIndex == index:
            self.currentIndex -= 1
            self.songInfoCardChute.currentIndex -= 1
            if n > 0:
                name = self.playlist[self.currentIndex].get(
                    'coverName', '未知歌手_未知专辑')
                self.albumCoverLabel.setCover(getCoverPath(name, "album_big"))
                self.__getLyric()

        # 强制更新当前歌曲的信息
        if n > 0:
            self.songInfoCardChute.cards[1].updateCard(
                self.playlist[self.currentIndex])

            if self.currentIndex == n-1:
                self.songInfoCardChute.cards[-1].hide()
            else:
                self.songInfoCardChute.cards[-1].updateCard(
                    self.playlist[self.currentIndex+1])

            if self.currentIndex == 0:
                self.songInfoCardChute.cards[0].hide()
            else:
                self.songInfoCardChute.cards[0].updateCard(
                    self.playlist[self.currentIndex-1])

        self.removeSongSignal.emit(index)

        # 如果播放列表为空，隐藏小部件
        if len(self.playlist) == 0:
            self.__setGuideLabelHidden(False)

    @handleSelectionMode
    def clearPlaylist(self):
        """ 清空歌曲卡 """
        self.playlist.clear()
        self.songListWidget.clearSongCards()
        self.__setGuideLabelHidden(False)
        self.playBar.hide()
        self.currentIndex = 0

    def __setGuideLabelHidden(self, isHidden):
        """ 设置导航标签和随机播放所有按钮的可见性 """
        self.randomPlayAllButton.setHidden(isHidden)
        self.guideLabel.setHidden(isHidden)
        self.songListWidget.setHidden(not isHidden)
        self.albumCoverLabel.setHidden(not isHidden)
        self.playBar.setHidden(not isHidden)
        self.songInfoCardChute.setHidden(not isHidden)

    def updateSongInfo(self, newSongInfo: SongInfo):
        """ 更新一首歌曲信息 """
        self.songListWidget.updateOneSongCard(newSongInfo)
        self.playlist = self.songListWidget.songInfos
        self.songInfoCardChute.playlist = self.playlist

    def updateMultiSongInfos(self, songInfos: List[SongInfo]):
        """ 更新多首歌曲信息 """
        self.songListWidget.updateMultiSongCards(songInfos)
        self.playlist = self.songListWidget.songInfos
        self.songInfoCardChute.playlist = self.playlist

    @handleSelectionMode
    def __onShowSmallestPlayInterfaceButtonClicked(self):
        """ 显示最小播放模式界面 """
        signalBus.fullScreenChanged.emit(False)
        signalBus.showSmallestPlayInterfaceSig.emit()

    def setRandomPlay(self, isRandomPlay: bool):
        """ 设置随机播放 """
        self.playBar.randomPlayButton.setRandomPlay(isRandomPlay)

    def setMute(self, isMute: bool):
        """ 设置静音 """
        self.playBar.volumeButton.setMute(isMute)
        self.playBar.volumeSliderWidget.volumeButton.setMute(isMute)

    def setVolume(self, volume: int):
        """ 设置音量 """
        if self.playBar.volumeSliderWidget.volumeSlider.value() == volume:
            return

        self.playBar.volumeSliderWidget.setVolume(volume)
        self.playBar.volumeButton.setVolumeLevel(volume)

    def setCurrentTime(self, currentTime: int):
        """ 设置当前进度条时间 """
        self.playBar.setCurrentTime(currentTime)

    def setFullScreen(self, isFullScreen: int):
        """ 更新全屏按钮图标 """
        self.playBar.fullScreenButton.setFullScreen(isFullScreen)

    def setLoopMode(self, loopMode: QMediaPlaylist.PlaybackMode):
        """ 设置循环模式 """
        self.playBar.loopModeButton.setLoopMode(loopMode)

    def __onSelectionModeChanged(self, isOpenSelectionMode: bool):
        """ 选择模式状态变化槽函数 """
        self.isInSelectionMode = isOpenSelectionMode
        self.selectionModeBar.setVisible(isOpenSelectionMode)
        self.selectionModeStateChanged.emit(isOpenSelectionMode)

    def __onCancelButtonClicked(self):
        """ 选择栏取消按钮点击槽函数 """
        self.selectionModeBar.checkAllButton.setCheckedState(
            not self.songListWidget.isAllSongCardsChecked)
        self.songListWidget.unCheckAllSongCards()
        self.selectionModeBar.checkAllButton.setCheckedState(True)

    def __onCheckAllButtonClicked(self):
        """ 全选/取消全选按钮点击槽函数 """
        isChecked = not self.songListWidget.isAllSongCardsChecked
        self.songListWidget.setAllChecked(isChecked)
        self.selectionModeBar.checkAllButton.setCheckedState(isChecked)

    def __onSelectionModeBarAlbumButtonClicked(self):
        """ 选择栏显示专辑按钮点击槽函数 """
        songCard = self.songListWidget.checkedSongCards[0]
        songCard.setChecked(False)
        signalBus.switchToAlbumInterfaceSig.emit(
            songCard.singer, songCard.album)

    def __onSelectionModeBarDeleteButtonClicked(self):
        """ 选择栏播放按钮点击槽函数 """
        for songCard in self.songListWidget.checkedSongCards.copy():
            songCard.setChecked(False)
            self.songListWidget.removeSongCard(songCard.itemIndex)

    def __onSelectionModeBarPlayButtonClicked(self):
        """ 选择栏播放按钮点击槽函数 """
        songCard = self.songListWidget.checkedSongCards[0]
        songCard.setChecked(False)
        self.currentIndexChanged.emit(songCard.itemIndex)

    def __onSelectionModeBarPropertyButtonClicked(self):
        """ 选择栏播放按钮点击槽函数 """
        songCard = self.songListWidget.checkedSongCards[0]
        songCard.setChecked(False)
        self.songListWidget.showSongPropertyDialog(songCard)

    def __onSelectionModeBarAddToButtonClicked(self):
        """ 选择栏添加到按钮点击槽函数 """
        menu = AddToMenu(parent=self)
        btn = self.selectionModeBar.addToButton
        pos = self.selectionModeBar.mapToGlobal(btn.pos())
        x = pos.x()+btn.width()+5
        y = pos.y()+btn.height()//2-(13+38*menu.actionCount())//2
        songInfos = [
            i.songInfo for i in self.songListWidget.checkedSongCards]

        # 菜单信号连接到槽
        for act in menu.action_list:
            act.triggered.connect(self.exitSelectionMode)
        menu.newPlaylistAct.triggered.connect(
            lambda: signalBus.addSongsToNewCustomPlaylistSig.emit(songInfos))
        menu.addSongsToPlaylistSig.connect(
            lambda name: signalBus.addSongsToCustomPlaylistSig.emit(name, songInfos))
        menu.exec(QPoint(x, y))

    def exitSelectionMode(self):
        """ 退出选择模式 """
        self.__onCancelButtonClicked()

    def __getLyric(self):
        """ 获取歌词 """
        self.lyricWidget.setLoadingState(True)
        self.getLyricThread.setSongInfo(self.playlist[self.currentIndex])
        self.getLyricThread.start()

    def __onCrawlLyricFinished(self, lyric: Dict[str, List[str]]):
        """ 获取歌词完成槽函数 """
        if self.isLyricVisible:
            self.lyricWidget.show()

        self.lyricWidget.setLyric(lyric)
        self.lyricWidget.setCurrentTime(self.playBar.progressSlider.value())

    def __onLyricVisibleChanged(self, isVisible: bool):
        """ 更多操作菜单歌词可见性变化信号槽函数 """
        self.lyricWidget.setVisible(isVisible)
        self.isLyricVisible = isVisible

    def __searchMV(self):
        """ 搜索 MV """
        if not self.playlist:
            return

        songInfo = self.playlist[self.currentIndex]
        self.getMvUrlThread.key_word = songInfo.singer + ' ' + songInfo.title
        self.getMvUrlThread.start()

    def __onCrawlMvUrlFinished(self, url: str):
        """ 获取 MV 播放地址完成槽函数 """
        if not url:
            w = MessageDialog(self.tr('Unable to find the corresponding MV'), self.tr(
                'Sorry, there are no MVs available for the current song'), self.window())
            w.yesButton.hide()
            w.exec_()
            return

        # 显示播放界面
        self.switchToVideoInterfaceSig.emit(url)

    def __connectSignalToSlot(self):
        """ 将信号连接到槽 """
        self.getLyricThread.crawlFinished.connect(self.__onCrawlLyricFinished)
        self.getMvUrlThread.crawlFinished.connect(self.__onCrawlMvUrlFinished)
        self.randomPlayAllButton.clicked.connect(signalBus.randomPlayAllSig)

        # 歌曲信息卡滑动槽信号连接到槽
        self.songInfoCardChute.currentIndexChanged[int].connect(
            self.currentIndexChanged)
        self.songInfoCardChute.currentIndexChanged[str].connect(
            self.albumCoverLabel.setCover)
        self.songInfoCardChute.showPlayBarSignal.connect(self.showPlayBar)
        self.songInfoCardChute.hidePlayBarSignal.connect(self.hidePlayBar)

        # 将播放栏的信号连接到槽
        self.playBar.volumeSliderWidget.volumeSlider.valueChanged.connect(
            signalBus.volumeChanged)
        self.playBar.fullScreenButton.fullScreenChanged.connect(
            signalBus.fullScreenChanged)
        self.playBar.progressSlider.sliderMoved.connect(
            signalBus.progressSliderMoved)
        self.playBar.progressSlider.clicked.connect(signalBus.progressSliderMoved)
        self.playBar.lastSongButton.clicked.connect(signalBus.lastSongSig)
        self.playBar.nextSongButton.clicked.connect(signalBus.nextSongSig)
        self.playBar.playButton.clicked.connect(signalBus.togglePlayStateSig)
        self.playBar.pullUpArrowButton.clicked.connect(
            self.__onShowPlaylistButtonClicked)
        self.playBar.showPlaylistButton.clicked.connect(
            self.__onShowPlaylistButtonClicked)
        self.playBar.smallPlayModeButton.clicked.connect(
            lambda i: self.__onShowSmallestPlayInterfaceButtonClicked())
        self.playBar.enterSignal.connect(self.__settleDownPlayBar)
        self.playBar.leaveSignal.connect(self.__startSongInfoCardTimer)
        self.playBar.moreActionsMenu.clearPlayListAct.triggered.connect(
            signalBus.clearPlayingPlaylistSig)
        self.playBar.moreActionsMenu.savePlayListAct.triggered.connect(
            lambda: signalBus.addSongsToNewCustomPlaylistSig.emit(self.playlist))
        self.playBar.moreActionsMenu.lyricVisibleChanged.connect(
            self.__onLyricVisibleChanged)
        self.playBar.moreActionsMenu.movieAct.triggered.connect(
            self.__searchMV)

        # 将歌曲列表的信号连接到槽函数
        self.songListWidget.currentIndexChanged.connect(
            self.currentIndexChanged)
        self.songListWidget.removeSongSig.connect(
            self.__removeSongFromPlaylist)
        self.songListWidget.selectionModeStateChanged.connect(
            self.__onSelectionModeChanged)
        self.songListWidget.checkedNumChanged.connect(
            lambda n: self.selectionModeBar.setPartButtonHidden(n > 1))
        self.songListWidget.isAllCheckedChanged.connect(
            lambda x: self.selectionModeBar.checkAllButton.setCheckedState(not x))

        # 选择栏信号连接到槽函数
        self.selectionModeBar.cancelButton.clicked.connect(
            self.__onCancelButtonClicked)
        self.selectionModeBar.checkAllButton.clicked.connect(
            self.__onCheckAllButtonClicked)
        self.selectionModeBar.playButton.clicked.connect(
            self.__onSelectionModeBarPlayButtonClicked)
        self.selectionModeBar.deleteButton.clicked.connect(
            self.__onSelectionModeBarDeleteButtonClicked)
        self.selectionModeBar.propertyButton.clicked.connect(
            self.__onSelectionModeBarPropertyButtonClicked)
        self.selectionModeBar.albumButton.clicked.connect(
            self.__onSelectionModeBarAlbumButtonClicked)
        self.selectionModeBar.addToButton.clicked.connect(
            self.__onSelectionModeBarAddToButtonClicked)
