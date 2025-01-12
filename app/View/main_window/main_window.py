# coding:utf-8
import sys
from copy import deepcopy
from pathlib import Path
from random import shuffle
from typing import List

from common import resource
from common.config import config
from common.crawler import CrawlerBase
from common.database import DBInitializer
from common.database.entity import AlbumInfo, Playlist, SongInfo
from common.hotkey_manager import HotkeyManager
from common.library import Directory, Library
from common.os_utils import getWindowsVersion
from common.signal_bus import signalBus
from common.style_sheet import setStyleSheet
from common.thread.get_online_song_url_thread import GetOnlineSongUrlThread
from common.thread.get_song_details_url_thread import GetSongDetailsUrlThread
from common.thread.get_album_details_url_thread import GetAlbumDetailsUrlThread
from common.thread.get_singer_details_url_thread import GetSingerDetailsUrlThread
from common.thread.library_thread import LibraryThread
from components.dialog_box.create_playlist_dialog import CreatePlaylistDialog
from components.dialog_box.message_dialog import MessageDialog
from components.frameless_window import AcrylicWindow
from components.label_navigation_interface import LabelNavigationInterface
from components.media_player import MediaPlaylist, PlaylistType
from components.system_tray_icon import SystemTrayIcon
from components.thumbnail_tool_bar import ThumbnailToolBar
from components.title_bar import TitleBar
from components.widgets.label import PixmapLabel
from components.widgets.stacked_widget import (OpacityAniStackedWidget,
                                               PopUpAniStackedWidget)
from components.widgets.tooltip import StateTooltip
from PyQt5.QtCore import (QEasingCurve, QEvent, QEventLoop, QFile, QFileInfo,
                          Qt, QTimer, QUrl)
from PyQt5.QtGui import (QColor, QDesktopServices, QDragEnterEvent, QDropEvent,
                         QIcon, QPixmap)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaPlaylist
from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtWidgets import QAction, QApplication, QHBoxLayout, QWidget, qApp
from View.album_interface import AlbumInterface
from View.more_search_result_interface import MoreSearchResultInterface
from View.my_music_interface import MyMusicInterface
from View.navigation_interface import NavigationInterface
from View.play_bar import PlayBar
from View.playing_interface import PlayingInterface
from View.playlist_card_interface import PlaylistCardInterface
from View.playlist_interface import PlaylistInterface
from View.recent_play_interface import RecentPlayInterface
from View.search_result_interface import SearchResultInterface
from View.setting_interface import SettingInterface
from View.singer_interface import SingerInterface
from View.smallest_play_interface import SmallestPlayInterface
from View.video_interface import VideoInterface


class MainWindow(AcrylicWindow):
    """ Main window """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.isInSelectionMode = False
        self.navigationHistories = [("myMusicInterfaceStackWidget", 0)]
        self.setObjectName("mainWindow")
        self.createWidgets()
        self.initWidget()
        self.initHotkey()

    def createWidgets(self):
        """ create widgets """
        # main window contains totalStackWidget, playBar and titleBar
        # totalStackWidget contanins subMainWindow, playingInterface and videoWindow
        self.totalStackWidget = OpacityAniStackedWidget(self)

        # subMainWindow is used to put navigation interface and subStackWidget
        self.subMainWindow = QWidget(self)

        # create splash screen
        self.splashScreen = SplashScreen(self)

        # create title bar
        self.titleBar = TitleBar(self)

        # display the window on the desktop first
        self.initWindow()

        # subStackWidget contains myMusicInterface, albumInterface and other interface
        # that need to be displayed on the right side of navigationInterface
        self.subStackWidget = PopUpAniStackedWidget(self.subMainWindow)

        # get online music url thread
        self.getOnlineSongUrlThread = GetOnlineSongUrlThread(self)

        # get song details url thread
        self.getSongDetailsUrlThread = GetSongDetailsUrlThread(self)

        # get album details url thread
        self.getAlbumDetailsUrlThread = GetAlbumDetailsUrlThread(self)

        # get album details url thread
        self.getSingerDetailsUrlThread = GetSingerDetailsUrlThread(self)

        # create setting interface
        self.settingInterface = SettingInterface(self.subMainWindow)

        # create song library
        self.initLibrary()

        # create player and playlist
        self.player = QMediaPlayer(self)
        self.mediaPlaylist = MediaPlaylist(self.library, self)

        # create my music interface
        self.myMusicInterface = MyMusicInterface(
            self.library, self.subMainWindow)

        # create timer to update the position of lyrics
        self.updateLyricPosTimer = QTimer(self)

        # crete thumbnail bar
        self.thumbnailToolBar = ThumbnailToolBar(self)
        self.thumbnailToolBar.setWindow(self.windowHandle())

        # create play bar
        self.playBar = PlayBar(
            self.mediaPlaylist.lastSongInfo, QColor(*config['playBar-color']), self)

        # create playing interface
        self.playingInterface = PlayingInterface(parent=self)

        # create video interface
        self.videoInterface = VideoInterface(self)

        # create album interface
        self.albumInterface = AlbumInterface(
            self.library, parent=self.subMainWindow)

        # create singer interface
        self.singerInterface = SingerInterface(
            self.library, parent=self.subMainWindow)

        # create playlist card interface and playlist interface
        self.playlistCardInterface = PlaylistCardInterface(
            self.library, self.subMainWindow)
        self.playlistInterface = PlaylistInterface(self.library, parent=self)

        # create recent play interface
        self.recentPlayInterface = RecentPlayInterface(
            self.library, self.subMainWindow)

        # create navigation interface
        self.navigationInterface = NavigationInterface(self.subMainWindow)

        # create label navigation interface
        self.labelNavigationInterface = LabelNavigationInterface(
            self.subMainWindow)

        # create smallest play interface
        self.smallestPlayInterface = SmallestPlayInterface(
            self.mediaPlaylist.playlist, parent=self)

        # create system tray icon
        self.systemTrayIcon = SystemTrayIcon(self)

        # create search result interface
        self.searchResultInterface = SearchResultInterface(
            self.library, self.subMainWindow)

        # create more search result interface
        self.moreSearchResultInterface = MoreSearchResultInterface(
            self.library, self.subMainWindow)

        # create state tooltip
        self.scanInfoTooltip = None

        self.songTabSongListWidget = self.myMusicInterface.songListWidget

    def initHotkey(self):
        self.hotkeyManager = HotkeyManager()
        self.hotkeyManager.register(
            self.winId(), Qt.Key_MediaPlay, self.togglePlayState)
        self.hotkeyManager.register(
            self.winId(), Qt.Key_MediaNext, self.mediaPlaylist.next)
        self.hotkeyManager.register(
            self.winId(), Qt.Key_MediaPrevious, self.mediaPlaylist.previous)

        self.addActions([
            QAction(self, shortcut=Qt.Key_Escape,
                    triggered=self.exitFullScreen),
            QAction(self, shortcut=Qt.Key_Space,
                    triggered=self.togglePlayState),
        ])

    def initLibrary(self):
        """ initialize song library """
        DBInitializer.init()

        self.library = Library(
            config["selected-folders"],
            QSqlDatabase.database(DBInitializer.connectionName)
        )
        self.libraryThread = LibraryThread(config["selected-folders"], self)

        eventLoop = QEventLoop(self)
        self.libraryThread.finished.connect(eventLoop.quit)
        self.libraryThread.start()
        eventLoop.exec()

        self.libraryThread.library.copyTo(self.library)

    def initWindow(self):
        """ initialize window """
        r = self.devicePixelRatioF()
        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.resize(w*1240/1920, h*970/1080)
        self.setMinimumSize(w*r*1030/1920, h*r*780/1080)

        self.setWindowTitle(self.tr("Groove Music"))
        self.setWindowIcon(QIcon(":/images/logo/logo.ico"))

        self.move(w//2 - self.width()//2, h//2 - self.height()//2)
        self.show()
        QApplication.processEvents()

    def initWidget(self):
        """ initialize widgets """
        self.setAcceptDrops(True)
        QApplication.setQuitOnLastWindowClosed(not config['minimize-to-tray'])

        desktop = QApplication.desktop().availableGeometry()
        self.smallestPlayInterface.move(desktop.width() - 390, 40)

        self.titleBar.raise_()

        # add sub interface to stacked Widget
        self.subStackWidget.addWidget(self.myMusicInterface, 0, 70)
        self.subStackWidget.addWidget(self.recentPlayInterface, 0, 120)
        self.subStackWidget.addWidget(self.playlistCardInterface, 0, 120)
        self.subStackWidget.addWidget(self.settingInterface, 0, 120)
        self.subStackWidget.addWidget(self.albumInterface, 0, 70)
        self.subStackWidget.addWidget(self.singerInterface, 0, 70)
        self.subStackWidget.addWidget(self.playlistInterface, 0, 70)
        self.subStackWidget.addWidget(self.labelNavigationInterface, 0, 100)
        self.subStackWidget.addWidget(self.searchResultInterface, 0, 120)
        self.subStackWidget.addWidget(self.moreSearchResultInterface, 0, 120)
        self.totalStackWidget.addWidget(self.subMainWindow)
        self.totalStackWidget.addWidget(self.playingInterface)
        self.totalStackWidget.addWidget(self.videoInterface)
        self.subMainWindow.setGraphicsEffect(None)

        self.adjustWidgetGeometry()
        self.setQss()

        # Set the interval that the player sends update position signal
        self.player.setNotifyInterval(1000)
        self.updateLyricPosTimer.setInterval(200)

        self.initPlaylist()
        self.connectSignalToSlot()
        self.initPlayBar()

        self.setPlayButtonEnabled(self.songTabSongListWidget.songCardNum > 0)

        self.navigationInterface.navigationMenu.installEventFilter(self)
        self.updateLyricPosTimer.start()
        self.onInitFinished()

    def onInitFinished(self):
        """ initialize finished slot """
        self.splashScreen.hide()
        self.subStackWidget.show()
        self.navigationInterface.show()
        self.playBar.show()
        self.systemTrayIcon.show()
        self.setWindowEffect(config["enable-acrylic-background"])

        if len(sys.argv) > 1:
            self.play()

    def setWindowEffect(self, enableAcrylic: bool):
        """ set window effect """
        self.setProperty('useAcrylic', enableAcrylic)
        self.setStyle(QApplication.style())
        if enableAcrylic:
            c = '2B2B2B' if config.theme == 'dark' else 'F2F2F2'
            self.windowEffect.setAcrylicEffect(self.winId(), c+"99")
            if getWindowsVersion() != 10:
                self.windowEffect.addShadowEffect(self.winId())
        else:
            self.windowEffect.addShadowEffect(self.winId())
            self.windowEffect.removeBackgroundEffect(self.winId())

    def adjustWidgetGeometry(self):
        """ adjust the geometry of widgets """
        self.titleBar.resize(self.width(), 40)
        self.splashScreen.resize(self.size())

        if not hasattr(self, 'playBar'):
            return

        self.subMainWindow.resize(self.size())
        self.totalStackWidget.resize(self.size())
        self.playBar.resize(self.width(), self.playBar.height())
        self.playBar.move(0, self.height()-self.playBar.height())

        if not hasattr(self, "navigationInterface"):
            return

        self.navigationInterface.setOverlay(self.width() < 1280)
        self.subStackWidget.move(self.navigationInterface.width(), 0)
        self.subStackWidget.resize(
            self.width() - self.navigationInterface.width(), self.height())
        self.navigationInterface.resize(
            self.navigationInterface.width(), self.height())

    def setQss(self):
        """ set style sheet """
        self.setObjectName("mainWindow")
        self.setProperty('useAcrylic', True)
        self.subMainWindow.setObjectName("subMainWindow")
        self.subStackWidget.setObjectName("subStackWidget")
        self.totalStackWidget.setObjectName('totalStackWidget')
        self.playingInterface.setObjectName("playingInterface")
        self.myMusicInterface.setObjectName('myMusicInterface')
        setStyleSheet(self, 'main_window')

    def eventFilter(self, obj, e: QEvent):
        if hasattr(self, "navigationInterface") and obj is self.navigationInterface.navigationMenu:
            # 显示导航菜单时更改标题栏返回按钮和标题的父级为导航菜单
            isVisible = self.titleBar.returnButton.isVisible()

            if e.type() == QEvent.Show:
                self.titleBar.returnButton.setParent(obj)

                # show title
                self.titleBar.titleLabel.setParent(obj)
                self.titleBar.titleLabel.setText(self.tr('Groove Music'))
                self.titleBar.titleLabel.move(60*isVisible, 0)
                self.titleBar.titleLabel.show()

                # shorten the navigation menu if the play bar is visible
                isScaled = self.playBar.isVisible()
                height = self.height() - isScaled * self.playBar.height()
                self.navigationInterface.navigationMenu.setBottomSpacingVisible(
                    not isScaled)
                self.navigationInterface.navigationMenu.resize(
                    self.navigationInterface.navigationMenu.width(), height)
            elif e.type() == QEvent.Hide:
                # hide title
                self.titleBar.titleLabel.setParent(self.titleBar)
                self.titleBar.returnButton.setParent(self.titleBar)
                self.titleBar.titleLabel.hide()

            self.titleBar.returnButton.setVisible(isVisible)

        return super().eventFilter(obj, e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.adjustWidgetGeometry()

    def showEvent(self, e):
        if hasattr(self, 'smallestPlayInterface'):
            self.smallestPlayInterface.hide()

        super().showEvent(e)

    def dragEnterEvent(self, e: QDragEnterEvent):
        if not e.mimeData().hasUrls():
            return e.ignore()

        e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent):
        files = []
        formats = tuple(Directory.audio_formats)

        for url in e.mimeData().urls():
            fileInfo = QFileInfo(url.toLocalFile())
            path = fileInfo.absoluteFilePath()

            if fileInfo.isFile() and path.endswith(formats):
                files.append(path)
            elif fileInfo.isDir():
                files.extend(Directory(path).glob())

        if not files:
            return

        if len(files) > 10:
            self.showScanInfoTooltip()

        self.libraryThread.setTask(
            self.libraryThread.library.loadFromFiles, files=files)
        self.libraryThread.start()

    def initPlaylist(self):
        """ initialize playlist """
        self.player.setPlaylist(self.mediaPlaylist)

        if len(sys.argv) > 1:
            songInfos = self.library.loadFromFiles([sys.argv[1]])
            self.setPlaylist(songInfos)
            self.updateWindow(self.mediaPlaylist.currentIndex())
            self.pause()
            return

        if not self.mediaPlaylist.playlist:
            songInfos = self.songTabSongListWidget.songInfos
            self.setPlaylist(songInfos)
            self.mediaPlaylist.playlistType = PlaylistType.ALL_SONG_PLAYLIST
        else:
            songInfos = self.mediaPlaylist.playlist
            self.setPlaylist(self.mediaPlaylist.playlist)

        self.songTabSongListWidget.setPlay(0)
        if songInfos:
            self.systemTrayIcon.updateWindow(songInfos[0])

        if self.mediaPlaylist.lastSongInfo in self.mediaPlaylist.playlist:
            self.mediaPlaylist.setCurrentSong(self.mediaPlaylist.lastSongInfo)
            self.updateWindow(self.mediaPlaylist.currentIndex())

        # pause player
        self.pause()

    def initPlayBar(self):
        """ initialize play bar """
        self.playBar.setVolume(config["volume"])

        if self.mediaPlaylist.playlist:
            self.playBar.updateWindow(self.mediaPlaylist.getCurrentSong())
            self.playBar.songInfoCard.albumCoverLabel.setOpacity(1)

    def setFullScreen(self, isFullScreen: bool):
        """ set full screen """
        if isFullScreen == self.isFullScreen():
            return

        if not isFullScreen:
            self.exitFullScreen()
            return

        # update title bar
        self.playBar.hide()
        self.titleBar.titleLabel.hide()
        self.titleBar.setWhiteIcon(True)
        self.titleBar.hide()

        # switch to playing interface
        self.totalStackWidget.setCurrentIndex(1)
        self.navigationHistories.append(("totalStackWidget", 1))

        self.showFullScreen()
        self.videoInterface.playBar.fullScreenButton.setFullScreen(True)
        self.videoInterface.playBar.fullScreenButton.setToolTip(
            self.tr('Exit fullscreen'))
        self.playingInterface.setFullScreen(True)
        if self.playingInterface.isPlaylistVisible:
            self.playingInterface.songInfoCardChute.move(
                0, 258 - self.height())

    def setVideoFullScreen(self, isFullScreen: bool):
        """ set video interface full screen """
        self.titleBar.setVisible(not isFullScreen)
        self.titleBar.maxButton.setMaxState(isFullScreen)
        self.titleBar.returnButton.show()
        if isFullScreen:
            self.showFullScreen()
        else:
            self.showNormal()

    def setMute(self, isMute: bool):
        """ set whether to mute """
        self.player.setMuted(isMute)
        self.playBar.setMute(isMute)
        self.playingInterface.setMute(isMute)

    def onVolumeChanged(self, volume: int):
        """ volume changed slot """
        self.player.setVolume(volume)
        self.playBar.setVolume(volume)
        self.playingInterface.setVolume(volume)

    def setRandomPlay(self, isRandomPlay: bool):
        """ set whether to play randomly """
        self.mediaPlaylist.setRandomPlay(isRandomPlay)
        self.playingInterface.setRandomPlay(isRandomPlay)
        self.playBar.randomPlayButton.setRandomPlay(isRandomPlay)

    def play(self):
        """ play songs """
        if not self.mediaPlaylist.playlist:
            self.playBar.songInfoCard.hide()
            self.setPlayButtonState(False)
            self.setPlayButtonEnabled(False)
            self.playBar.setTotalTime(0)
            self.playBar.progressSlider.setRange(0, 0)
        else:
            self.player.play()
            self.setPlayButtonState(True)
            self.setPlayButtonEnabled(True)
            self.playBar.songInfoCard.show()

    def pause(self):
        """ pause audio player """
        self.player.pause()
        self.setPlayButtonState(False)

    def setPlaylist(self, playlist: list, index=0):
        """ set playing playlist """
        self.playingInterface.setPlaylist(playlist, index=index)
        self.smallestPlayInterface.setPlaylist(playlist)
        self.mediaPlaylist.setPlaylist(playlist, index)
        self.play()

    def setPlayButtonEnabled(self, isEnabled: bool):
        """ set the enabled state of play buttons """
        self.playBar.playButton.setEnabled(isEnabled)
        self.playBar.nextSongButton.setEnabled(isEnabled)
        self.playBar.lastSongButton.setEnabled(isEnabled)
        self.playingInterface.playBar.playButton.setEnabled(isEnabled)
        self.playingInterface.playBar.nextSongButton.setEnabled(isEnabled)
        self.playingInterface.playBar.lastSongButton.setEnabled(isEnabled)
        self.thumbnailToolBar.setButtonsEnabled(isEnabled)
        self.smallestPlayInterface.playButton.setEnabled(isEnabled)
        self.smallestPlayInterface.lastSongButton.setEnabled(isEnabled)
        self.smallestPlayInterface.nextSongButton.setEnabled(isEnabled)
        self.systemTrayIcon.menu.songAct.setEnabled(isEnabled)
        self.systemTrayIcon.menu.playAct.setEnabled(isEnabled)
        self.systemTrayIcon.menu.lastSongAct.setEnabled(isEnabled)
        self.systemTrayIcon.menu.nextSongAct.setEnabled(isEnabled)

    def setPlayButtonState(self, isPlay: bool):
        """ set the play state of play buttons """
        self.playBar.setPlay(isPlay)
        self.systemTrayIcon.setPlay(isPlay)
        self.playingInterface.setPlay(isPlay)
        self.thumbnailToolBar.setPlay(isPlay)
        self.smallestPlayInterface.setPlay(isPlay)

    def togglePlayState(self):
        """ toggle play state """
        if self.totalStackWidget.currentWidget() is self.videoInterface:
            self.videoInterface.togglePlayState()
            return

        if self.player.state() == QMediaPlayer.PlayingState:
            self.pause()
            self.thumbnailToolBar.setButtonsEnabled(True)
        else:
            self.play()

    def onPlayerPositionChanged(self, position):
        """ player position changed slot """
        self.playBar.setCurrentTime(position)
        self.playBar.progressSlider.setValue(position)
        self.playingInterface.setCurrentTime(position)
        self.playingInterface.playBar.progressSlider.setValue(position)
        self.smallestPlayInterface.progressBar.setValue(position)

    def onPlayerDurationChanged(self):
        """ player duration changed slot """
        # the duration is 0 when just switching songs
        duration = self.player.duration()
        if duration < 1:
            return

        self.playBar.setTotalTime(duration)
        self.playBar.progressSlider.setRange(0, duration)
        self.playingInterface.playBar.setTotalTime(duration)
        self.playingInterface.playBar.progressSlider.setRange(0, duration)
        self.smallestPlayInterface.progressBar.setRange(0, duration)

    def onMediaStatusChanged(self, status: QMediaPlayer.MediaStatus):
        """ media status changed slot """
        if status != QMediaPlayer.NoMedia:
            return

        self.setPlayButtonState(False)

    def onPlayerError(self, error: QMediaPlayer.Error):
        """ media player error slot """
        if error == QMediaPlayer.NoError:
            return

        self.pause()

        decoder = "LAV filters" if sys.platform == "win32" else "GStreamer"
        hint = self.tr("please check if") + \
            f" {decoder} " + self.tr("is installed.")

        messageMap = {
            QMediaPlayer.ResourceError: self.tr(
                "The media resource couldn't be resolved") + ", " + hint,
            QMediaPlayer.FormatError: self.tr(
                "The format of a media resource isn't supported."),
            QMediaPlayer.NetworkError: self.tr("A network error occurred."),
            QMediaPlayer.AccessDeniedError: self.tr(
                "There are not the appropriate permissions to play the media resource."),
            QMediaPlayer.ServiceMissingError: self.tr(
                "A valid playback service was not found") + ", " + hint
        }
        self.showMessageBox(self.tr('An error occurred'), messageMap[error])

    def onProgressSliderMoved(self, position):
        """ progress slider moved slot """
        self.player.setPosition(position)
        self.playBar.setCurrentTime(position)
        self.playingInterface.setCurrentTime(position)
        self.smallestPlayInterface.progressBar.setValue(position)

    def switchLoopMode(self, loopMode):
        """ switch loop mode of player """
        self.mediaPlaylist.prePlayMode = loopMode

        self.playBar.setLoopMode(loopMode)
        self.playingInterface.setLoopMode(loopMode)

        if not self.mediaPlaylist.randPlayBtPressed:
            self.mediaPlaylist.setPlaybackMode(loopMode)
        else:
            if self.playBar.loopModeButton.loopMode == QMediaPlaylist.CurrentItemInLoop:
                self.mediaPlaylist.setPlaybackMode(
                    QMediaPlaylist.CurrentItemInLoop)
            else:
                self.mediaPlaylist.setPlaybackMode(QMediaPlaylist.Random)

    def getOnlineSongUrl(self, index: int):
        """ get the play url of online music """
        if index < 0 or not self.mediaPlaylist.playlist:
            return

        songInfo = self.mediaPlaylist.playlist[index]
        if songInfo.file != CrawlerBase.song_url_mark:
            return

        i = self.searchResultInterface.onlineSongInfos.index(songInfo)
        songCard = self.searchResultInterface.onlineSongListWidget.songCards[i]

        # get play url and cover
        eventLoop = QEventLoop(self)
        self.getOnlineSongUrlThread.finished.connect(eventLoop.quit)
        self.getOnlineSongUrlThread.songInfo = songInfo
        self.getOnlineSongUrlThread.start()
        eventLoop.exec()

        # TODO：更优雅地更新在线媒体
        songInfo.file = self.getOnlineSongUrlThread.playUrl
        songInfo['coverPath'] = self.getOnlineSongUrlThread.coverPath
        songCard.setSongInfo(songInfo)
        self.mediaPlaylist.insertSong(index, songInfo)
        self.playingInterface.updateSongInfoByIndex(index, songInfo)
        self.smallestPlayInterface.playlist[index] = songInfo
        self.searchResultInterface.onlineSongInfos[i] = songInfo
        self.mediaPlaylist.removeOnlineSong(index+1)
        self.mediaPlaylist.setCurrentIndex(index)

    def updateWindow(self, index: int):
        """ update main window after switching songs """
        if not self.mediaPlaylist.playlist:
            self.playBar.songInfoCard.hide()
            self.setPlayButtonState(False)
            self.setPlayButtonEnabled(False)
            return

        self.setPlayButtonEnabled(True)

        # handling the situation that song does not exist
        if index < 0:
            return

        songInfo = self.mediaPlaylist.playlist[index]

        # update sub interfaces
        self.playBar.updateWindow(songInfo)
        self.playingInterface.setCurrentIndex(index)
        self.systemTrayIcon.updateWindow(songInfo)

        if self.smallestPlayInterface.isVisible():
            self.smallestPlayInterface.setCurrentIndex(index)

        signalBus.playBySongInfoSig.emit(songInfo)

        self.checkMediaAvailable()

    def checkMediaAvailable(self):
        """ check the availability of media """
        if not self.mediaPlaylist.playlist:
            return

        # determin the availability
        songPath = self.mediaPlaylist.getCurrentSong().file
        if songPath.startswith('http') or Path(songPath).exists():
            return

        # pause player when the media is not available
        self.pause()

        # pop up message dialog
        self.showMessageBox(
            self.tr("Can't play this song"),
            self.tr("It's not on this device or somewhere we can stream from.")
        )

    def showMessageBox(self, title: str, content: str):
        """ show message box """
        w = MessageDialog(title, content, self)
        w.cancelButton.setText(self.tr('Close'))
        w.yesButton.hide()
        w.exec()

    def onMinimizeToTrayChanged(self, isMinimize: bool):
        """ minimize to tray slot """
        QApplication.setQuitOnLastWindowClosed(not isMinimize)

    def onReturnButtonClicked(self):
        """ return button clicked slot """
        if self.isInSelectionMode:
            return

        self.playingInterface.playBar.volumeSliderWidget.hide()

        history = self.navigationHistories.pop()
        if history == ("totalStackWidget", 2):
            self.videoInterface.pause()
            self.totalStackWidget.setCurrentIndex(1)
            return

        # should not return to the playingInterface
        if self.navigationHistories[-1] == ("totalStackWidget", 1):
            self.navigationHistories.pop()

        stackWidget, index = self.navigationHistories[-1]
        if stackWidget == "myMusicInterfaceStackWidget":
            self.myMusicInterface.stackedWidget.setCurrentIndex(index)
            self.subStackWidget.setCurrentIndex(
                0, True, False, 200, QEasingCurve.InCubic)
            self.navigationInterface.setCurrentIndex(0)
            self.myMusicInterface.setSelectedButton(index)
            self.titleBar.setWhiteIcon(False)
        elif stackWidget == "subStackWidget":
            isShowNextWidgetDirectly = self.subStackWidget.currentWidget() is not self.settingInterface
            self.subStackWidget.setCurrentIndex(
                index, True, isShowNextWidgetDirectly, 200, QEasingCurve.InCubic)
            self.navigationInterface.setCurrentIndex(index)

            # update icon color of title bar
            whiteIndexes = [self.subStackWidget.indexOf(
                i) for i in [self.albumInterface, self.playlistInterface, self.singerInterface]]
            self.titleBar.setWhiteIcon(index in whiteIndexes)
            self.titleBar.returnButton.setWhiteIcon(False)

        self.hidePlayingInterface()

        if len(self.navigationHistories) == 1:
            self.titleBar.returnButton.hide()

    def showLabelNavigationInterface(self, labels: list, layout: str):
        """ show label navigation interface """
        self.labelNavigationInterface.setLabels(labels, layout)
        self.switchToSubInterface(self.labelNavigationInterface)

    def showSmallestPlayInterface(self):
        """ show smallest play interface """
        self.smallestPlayInterface.setCurrentIndex(
            self.mediaPlaylist.currentIndex())
        self.hide()
        self.smallestPlayInterface.show()

    def showVideoWindow(self, url: str):
        """ show video window """
        self.pause()

        songInfo = self.mediaPlaylist.getCurrentSong()
        self.totalStackWidget.setCurrentIndex(2)
        self.videoInterface.setVideo(url, songInfo.singer+' - '+songInfo.title)

        self.navigationHistories.append(("totalStackWidget", 2))
        self.titleBar.returnButton.show()

    def exitSmallestPlayInterface(self):
        """ exit smallest play interface """
        self.smallestPlayInterface.hide()
        self.show()

    def hidePlayingInterface(self):
        """ hide playing interface """
        if not self.playingInterface.isVisible():
            return

        self.playBar.show()
        self.totalStackWidget.setCurrentIndex(0)

        # set the icon color of title bar
        whiteInterface = [self.albumInterface,
                          self.playlistInterface, self.singerInterface]
        if self.subStackWidget.currentWidget() in whiteInterface:
            self.titleBar.returnButton.setWhiteIcon(False)
        else:
            self.titleBar.setWhiteIcon(False)

        # hide return button
        cond = self.subStackWidget.currentWidget() not in [
            self.labelNavigationInterface, self.albumInterface]
        if len(self.navigationHistories) == 1 and cond:
            self.titleBar.returnButton.hide()

        self.titleBar.titleLabel.setVisible(
            self.navigationInterface.isExpanded)

    def showPlayingInterface(self):
        """ show playing interface """
        self.show()

        if self.playingInterface.isVisible():
            return

        self.exitSelectionMode()
        self.playBar.hide()
        self.titleBar.titleLabel.hide()
        self.titleBar.returnButton.show()

        if not self.playingInterface.isPlaylistVisible and len(self.playingInterface.playlist) > 0:
            self.playingInterface.songInfoCardChute.move(
                0, -self.playingInterface.playBar.height() + 68)
            self.playingInterface.playBar.show()

        self.totalStackWidget.setCurrentIndex(1)
        self.titleBar.setWhiteIcon(True)

        self.navigationHistories.append(("totalStackWidget", 1))

    def showPlayingPlaylist(self):
        """ show playing playlist """
        self.playingInterface.showPlaylist()
        self.playingInterface.playBar.pullUpArrowButton.setArrowDirection(
            "down")
        if self.playingInterface.isPlaylistVisible:
            self.showPlayingInterface()

    def clearPlaylist(self):
        """ clear playlist """
        self.mediaPlaylist.playlistType = PlaylistType.NO_PLAYLIST
        self.mediaPlaylist.clear()
        self.playingInterface.clearPlaylist()
        self.smallestPlayInterface.clearPlaylist()
        self.systemTrayIcon.clearPlaylist()
        self.playBar.songInfoCard.hide()
        self.playBar.setTotalTime(0)
        self.playBar.progressSlider.setRange(0, 0)
        self.setPlayButtonState(False)
        self.setPlayButtonEnabled(False)

    def onNavigationDisplayModeChanged(self, disPlayMode: int):
        """ navigation interface display mode changed slot """
        self.titleBar.titleLabel.setVisible(
            self.navigationInterface.isExpanded)
        self.adjustWidgetGeometry()
        self.navigationInterface.navigationMenu.stackUnder(self.playBar)
        # 如果现在显示的是字母导航界面就将其隐藏
        if self.subStackWidget.currentWidget() is self.labelNavigationInterface:
            self.subStackWidget.setCurrentIndex(0)

    def onSelectionModeStateChanged(self, isOpen: bool):
        """ selection mode state changed slot """
        self.isInSelectionMode = isOpen
        if not self.playingInterface.isVisible():
            self.playBar.setHidden(isOpen)

    def exitSelectionMode(self):
        """ exit selection mode """
        if not self.isInSelectionMode:
            return

        self.myMusicInterface.exitSelectionMode()
        self.albumInterface.exitSelectionMode()
        self.playlistCardInterface.exitSelectionMode()
        self.playlistInterface.exitSelectionMode()
        self.playingInterface.exitSelectionMode()
        self.singerInterface.exitSelectionMode()

    def exitFullScreen(self):
        """ exit full screen """
        if not self.isFullScreen():
            return

        self.showNormal()

        # 更新最大化按钮图标
        self.titleBar.maxButton.setMaxState(False)
        self.titleBar.returnButton.show()
        self.titleBar.show()

        self.videoInterface.playBar.fullScreenButton.setFullScreen(False)
        self.playingInterface.setFullScreen(False)
        if self.playingInterface.isPlaylistVisible:
            self.playingInterface.songInfoCardChute.move(
                0, 258 - self.height())

    def appendSubStackWidgetHistory(self, widget: QWidget):
        """ push the switching history of sub interface """
        index = self.subStackWidget.indexOf(widget)
        if self.navigationHistories[-1] == ("subStackWidget", index):
            return

        self.navigationHistories.append(('subStackWidget', index))

    def switchToSubInterface(self, widget: QWidget, whiteIcon=False, whiteReturn=False):
        """ switch to sub interface in `subStackWidget`

        Parameters
        ----------
        widget: QWidget
            the interface to be displayed

        whiteIcon: bool
            whether to set the icon color of title bar to white

        whiteReturn: bool
            Whether to set the return button to a white button
        """
        self.titleBar.returnButton.show()
        self.titleBar.setWhiteIcon(whiteIcon)
        self.titleBar.returnButton.setWhiteIcon(whiteReturn)

        # switch interface
        self.exitSelectionMode()
        self.playBar.show()
        self.totalStackWidget.setCurrentIndex(0)
        self.subStackWidget.setCurrentWidget(widget)
        self.appendSubStackWidgetHistory(widget)

    def switchToSettingInterface(self):
        """ switch to setting interface """
        self.show()

        # TODO: 从视频界面直接切换回设置界面
        if self.videoInterface.isVisible():
            return

        if self.playingInterface.isVisible():
            self.titleBar.returnButton.click()

        self.switchToSubInterface(self.settingInterface)

    def switchToMyMusicInterface(self):
        """ switch to my music interface """
        self.exitSelectionMode()
        self.subStackWidget.setCurrentWidget(self.myMusicInterface)
        self.appendSubStackWidgetHistory(self.myMusicInterface)

    def switchToPlaylistInterface(self, name: str):
        """ switch to playlist interface """
        if self.isInSelectionMode:
            return

        playlist = self.library.playlistController.getPlaylist(name)
        if not playlist:
            return

        self.playlistInterface.updateWindow(playlist)
        self.switchToSubInterface(self.playlistInterface, True)
        self.playlistInterface.songListWidget.setPlayBySongInfo(
            self.mediaPlaylist.getCurrentSong())

    def switchToPlaylistCardInterface(self):
        """ switch to playlist card interface """
        self.switchToSubInterface(self.playlistCardInterface)

    def switchToRecentPlayInterface(self):
        """ switch to recent play interface """
        self.switchToSubInterface(self.recentPlayInterface)

    def switchToSearchResultInterface(self, keyWord: str):
        """ switch to search result interface """
        self.searchResultInterface.search(keyWord)
        self.switchToSubInterface(self.searchResultInterface)
        self.searchResultInterface.localSongListWidget.setPlayBySongInfo(
            self.mediaPlaylist.getCurrentSong())

    def switchToMoreSearchResultInterface(self, keyWord: str, viewType, data: list):
        """ switch to more search result interface """
        self.moreSearchResultInterface.updateWindow(keyWord, viewType, data)
        self.switchToSubInterface(self.moreSearchResultInterface)
        self.moreSearchResultInterface.localSongListWidget.setPlayBySongInfo(
            self.mediaPlaylist.getCurrentSong())

    def switchToSingerInterface(self, singer: str):
        """ switch to singer interface """
        if self.isInSelectionMode:
            return

        singerInfo = self.library.singerInfoController.getSingerInfoByName(
            singer)
        if not singerInfo:
            return

        self.exitFullScreen()
        self.singerInterface.updateWindow(singerInfo)
        self.switchToSubInterface(self.singerInterface, True)
        self.singerInterface.albumBlurBackground.hide()

    def switchToAlbumInterface(self, singer: str, album: str):
        """ switch to album interface """
        if self.isInSelectionMode:
            return

        albumInfo = self.library.albumInfoController.getAlbumInfo(
            singer, album)
        if not albumInfo:
            return

        self.exitFullScreen()
        self.albumInterface.updateWindow(albumInfo)
        self.switchToSubInterface(self.albumInterface, True)
        self.albumInterface.songListWidget.setPlayBySongInfo(
            self.mediaPlaylist.getCurrentSong())

    def switchToAlbumCardInterface(self):
        """ switch to album card interface """
        self.subStackWidget.setCurrentWidget(self.myMusicInterface)
        self.titleBar.setWhiteIcon(False)
        self.titleBar.returnButton.show()
        self.myMusicInterface.setCurrentTab(2)
        self.navigationInterface.setCurrentIndex(0)

        # add navigation history
        index = self.myMusicInterface.stackedWidget.indexOf(
            self.myMusicInterface.albumTabInterface)
        self.navigationHistories.append(('myMusicInterfaceStackWidget', index))

    def onMyMusicInterfaceStackWidgetIndexChanged(self, index):
        """ my music interface tab index changed slot """
        self.navigationHistories.append(("myMusicInterfaceStackWidget", index))
        self.titleBar.returnButton.show()

    def onSongTabSongCardPlay(self, songInfo: SongInfo):
        """ song tab interface play song card slot """
        songInfos = self.songTabSongListWidget.songInfos

        if self.mediaPlaylist.playlistType != PlaylistType.ALL_SONG_PLAYLIST \
                or songInfos != self.mediaPlaylist.playlist:
            self.mediaPlaylist.playlistType = PlaylistType.ALL_SONG_PLAYLIST
            songInfos = self.songTabSongListWidget.songInfos
            index = songInfos.index(songInfo)
            playlist = songInfos[index:] + songInfos[:index]
            self.setPlaylist(playlist)

        self.mediaPlaylist.setCurrentSong(songInfo)

    def onPlaylistInterfaceSongCardPlay(self, index):
        """ playlist interface song card play slot """
        songInfos = self.playlistInterface.songInfos
        self.playCustomPlaylistSong(songInfos, index)

    def playOneSongCard(self, songInfo: SongInfo):
        """ reset the playing playlist to one song """
        self.mediaPlaylist.playlistType = PlaylistType.SONG_CARD_PLAYLIST
        self.setPlaylist([songInfo])

    def updatePlaylist(self, reset=False):
        """ update playing playlist """
        playlist = self.mediaPlaylist.playlist
        self.playingInterface.setPlaylist(playlist, reset)
        self.smallestPlayInterface.setPlaylist(playlist, reset)
        self.play()

    def onSongsNextToPlay(self, songInfos: List[SongInfo]):
        """ songs next to play slot """
        reset = not self.mediaPlaylist.playlist
        index = self.mediaPlaylist.currentIndex()
        self.mediaPlaylist.insertSongs(index + 1, songInfos)
        self.updatePlaylist(reset)

    def addSongsToPlayingPlaylist(self, songInfos: list):
        """ add songs to playing playlist """
        reset = not self.mediaPlaylist.playlist
        self.mediaPlaylist.addSongs(songInfos)
        self.updatePlaylist(reset)

    def addSongsToCustomPlaylist(self, name: str, songInfos: List[SongInfo]):
        """ add songs to custom playlist """

        def resetSongInfo(songInfos: list, diffSongInfos):
            songInfos.clear()
            songInfos.extend(diffSongInfos)

        songInfos = deepcopy(
            [i for i in songInfos if not i.file.startswith('http')])

        # find new songs
        oldPlaylist = self.library.playlistController.getPlaylist(name)
        oldFiles = [i.file for i in oldPlaylist.songInfos]
        diffSongInfos = [i for i in songInfos if i.file not in oldFiles]

        planToAddNum = len(songInfos)
        repeatNum = planToAddNum-len(diffSongInfos)

        # show dialog box if there are duplicate songs
        if repeatNum > 0:
            if planToAddNum == 1:
                content = self.tr(
                    "This song is already in your playlist. Do you want to add?")
            elif repeatNum < planToAddNum:
                content = self.tr(
                    "Some songs are already in your playlist. Do you want to add?")
            else:
                content = self.tr(
                    "All these songs are already in your playlist. Do you want to add?")

            w = MessageDialog(self.tr("Song duplication"), content, self)
            w.cancelSignal.connect(
                lambda: resetSongInfo(songInfos, diffSongInfos))
            w.exec_()

        success = self.library.playlistController.addSongs(name, songInfos)
        if not success:
            return

        self.playlistCardInterface.addSongsToPlaylist(name, songInfos)
        self.searchResultInterface.playlistGroupBox.playlistCardView.addSongsToPlaylistCard(
            name, songInfos)
        self.moreSearchResultInterface.playlistInterface.playlistCardView.addSongsToPlaylistCard(
            name, songInfos)

    def removeSongsFromCustomPlaylist(self, name: str, songInfos: List[SongInfo]):
        """ remove songs from custom playlist """
        success = self.library.playlistController.removeSongs(name, songInfos)
        if not success:
            return

        self.playlistCardInterface.removeSongsFromPlaylist(name, songInfos)
        self.searchResultInterface.playlistGroupBox.playlistCardView.removeSongsFromPlaylistCard(
            name, songInfos)
        self.moreSearchResultInterface.playlistInterface.playlistCardView.removeSongsFromPlaylistCard(
            name, songInfos)

    def playAlbum(self, singer: str, album: str, index=0):
        """ play songs in an album """
        albumInfo = self.library.albumInfoController.getAlbumInfo(
            singer, album)
        if not albumInfo:
            return

        playlist = albumInfo.songInfos
        self.playingInterface.setPlaylist(playlist, index=index)
        self.smallestPlayInterface.setPlaylist(playlist)
        self.mediaPlaylist.playAlbum(playlist, index)
        self.play()

    def playAbumSong(self, index: int):
        """ play the song in an album """
        if self.mediaPlaylist.playlistType != PlaylistType.ALBUM_CARD_PLAYLIST or \
                self.mediaPlaylist.playlist != self.albumInterface.songInfos:
            self.playAlbum(self.albumInterface.singer,
                           self.albumInterface.album, index)

        self.mediaPlaylist.setCurrentIndex(index)

    def playCustomPlaylist(self, songInfos: list, index=0):
        """ play songs in custom playlist """
        self.mediaPlaylist.playlistType = PlaylistType.CUSTOM_PLAYLIST
        self.setPlaylist(songInfos, index)

    def playCustomPlaylistSong(self, songInfos: List[SongInfo], index: int):
        """ play the song in a custom playlist  """
        if self.mediaPlaylist.playlistType != PlaylistType.CUSTOM_PLAYLIST or \
                self.mediaPlaylist.playlist != songInfos:
            self.playCustomPlaylist(songInfos, index)

        self.mediaPlaylist.setCurrentIndex(index)

    def playLocalSearchedSong(self, index: int):
        """ play selected local searched song """
        songInfos = self.searchResultInterface.localSongListWidget.songInfos
        self.playCustomPlaylistSong(songInfos, index)

    def playOnlineSearchedSong(self, index: int):
        """ play selected online searched song """
        songInfos = self.searchResultInterface.onlineSongListWidget.songInfos
        self.playCustomPlaylistSong(songInfos, index)

    def playLocalMoreSearchedSong(self, songInfo: SongInfo):
        """ play selected local more searched song """
        songInfos = self.moreSearchResultInterface.localSongListWidget.songInfos
        index = songInfos.index(songInfo)
        self.playCustomPlaylistSong(songInfos, index)

    def playRecentPlaySong(self, songInfo: SongInfo):
        """ play recent played song """
        songInfos = self.recentPlayInterface.songListWidget.songInfos
        index = songInfos.index(songInfo)
        self.playCustomPlaylistSong(songInfos, index)

    def randomPlayAll(self):
        """ play all songs randomly """
        self.mediaPlaylist.playlistType = PlaylistType.ALL_SONG_PLAYLIST
        playlist = self.songTabSongListWidget.songInfos.copy()
        shuffle(playlist)
        self.setPlaylist(playlist)

    def onEditSongInfo(self, oldSongInfo: SongInfo, newSongInfo: SongInfo):
        """ edit song information slot """
        self.library.updateSongInfo(oldSongInfo, newSongInfo)
        self.mediaPlaylist.updateSongInfo(newSongInfo)
        self.playingInterface.updateSongInfo(newSongInfo)
        self.myMusicInterface.updateSongInfo(newSongInfo)
        self.playlistInterface.updateSongInfo(newSongInfo)
        self.albumInterface.updateSongInfo(newSongInfo)
        self.searchResultInterface.localSongListWidget.updateOneSongCard(
            newSongInfo)

    def onEditAlbumInfo(self, oldAlbumInfo: AlbumInfo, newAlbumInfo: AlbumInfo, coverPath: str):
        """ edit album information slot """
        songInfos = newAlbumInfo.songInfos
        self.library.updateMultiSongInfos(oldAlbumInfo.songInfos, songInfos)
        self.mediaPlaylist.updateMultiSongInfos(songInfos)
        self.myMusicInterface.updateMultiSongInfos(songInfos)
        self.playingInterface.updateMultiSongInfos(songInfos)
        self.playlistInterface.updateMultiSongInfos(songInfos)
        self.albumInterface.updateMultiSongInfos(songInfos)
        self.searchResultInterface.localSongListWidget.updateMultiSongCards(
            songInfos)

    def deleteSongs(self, songPaths: List[str]):
        """ delete songs from local """
        for songPath in songPaths:
            QFile.moveToTrash(songPath)

    def onUpdateLyricPosTimeOut(self):
        """ update lyric postion timer time out """
        if self.player.state() != QMediaPlayer.PlayingState:
            return

        t = self.player.position()
        self.playingInterface.lyricWidget.setCurrentTime(t)

    def onPlayingInterfaceCurrentIndexChanged(self, index):
        """ playing interface current index changed slot """
        self.mediaPlaylist.setCurrentIndex(index)
        self.play()

    def onExit(self):
        """ exit main window """
        config.update({
            "volume": self.playBar.volumeSlider.value(),
            "playBar-color": list(self.playBar.getColor().getRgb()[:3])
        })
        self.mediaPlaylist.save()
        self.systemTrayIcon.hide()
        self.hotkeyManager.clear(self.winId())

        # close database
        QSqlDatabase.database(DBInitializer.connectionName).close()
        QSqlDatabase.removeDatabase(DBInitializer.connectionName)

    def onNavigationLabelClicked(self, label: str):
        """ navigation label clicked slot """
        self.myMusicInterface.scrollToLabel(label)
        self.subStackWidget.setCurrentWidget(
            self.subStackWidget.previousWidget)
        self.navigationHistories.pop()

    def showScanInfoTooltip(self):
        title = self.tr("Scanning song information")
        content = self.tr("Please wait patiently")
        self.scanInfoTooltip = StateTooltip(title, content, self.window())
        self.scanInfoTooltip.show()

    def onSelectedFolderChanged(self, directories: List[str]):
        """ selected music folders changed slot """
        self.showScanInfoTooltip()
        self.libraryThread.setTask(
            self.libraryThread.library.setDirectories, directories=directories)
        self.libraryThread.start()

    def onReloadFinished(self):
        """ reload library finished slot """
        self.libraryThread.library.copyTo(self.library)
        self.myMusicInterface.updateWindow()

        if self.scanInfoTooltip:
            self.scanInfoTooltip.setState(True)

        self.scanInfoTooltip = None

    def onLoadFromFilesFinished(self, songInfos: List[SongInfo]):
        """ load song information form files finished slot """
        self.setPlaylist(songInfos)
        if self.scanInfoTooltip:
            self.scanInfoTooltip.setState(True)

        self.scanInfoTooltip = None

    def showCreatePlaylistDialog(self, songInfos: List[SongInfo] = None):
        """ show create playlist dialog box """
        songInfos = songInfos or []
        songInfos = [i for i in songInfos if not i.file.startswith('http')]
        w = CreatePlaylistDialog(self.library, songInfos, self)
        w.createPlaylistSig.connect(self.onCreatePlaylist)
        w.exec_()

    def onCreatePlaylist(self, name: str, playlist: Playlist):
        """ create a playlist """
        self.playlistCardInterface.addPlaylistCard(name, playlist)
        self.navigationInterface.updateWindow()

    def onRenamePlaylist(self, old: str, new: str):
        """ rename a playlist """
        success = self.library.playlistController.rename(old, new)
        if not success:
            return

        self.navigationInterface.updateWindow()
        self.playlistCardInterface.renamePlaylist(old, new)
        self.searchResultInterface.playlistGroupBox.playlistCardView.renamePlaylistCard(
            old, new)
        self.moreSearchResultInterface.playlistInterface.playlistCardView.renamePlaylistCard(
            old, new)

    def onDeleteCustomPlaylist(self, name: str):
        """ delete a playlist """
        success = self.library.playlistController.delete(name)
        if not success:
            return

        self.navigationInterface.updateWindow()
        self.playlistCardInterface.deletePlaylistCard(name)
        self.searchResultInterface.deletePlaylistCard(name)
        self.moreSearchResultInterface.playlistInterface.playlistCardView.deletePlaylistCard(
            name)

        if self.playlistInterface.isVisible():
            self.titleBar.returnButton.click()

        N = len(self.moreSearchResultInterface.playlistInterface.playlistCards)
        if self.moreSearchResultInterface.playlistInterface.isVisible() and N == 0:
            self.titleBar.returnButton.click()

    def onFileRemoved(self, files: List[str]):
        """ files removed slot """
        self.myMusicInterface.deleteSongs(files)
        self.albumInterface.songListWidget.removeSongCards(files)
        self.searchResultInterface.localSongListWidget.removeSongCards(files)
        self.moreSearchResultInterface.localSongListWidget.removeSongCards(
            files)

    def onFileAdded(self, songInfos: List[SongInfo]):
        """ files add slot """
        self.myMusicInterface.updateWindow()

    def onCrawMetaDataFinished(self):
        """ craw meta data finished slot """
        self.library.load()
        self.myMusicInterface.updateWindow()

    def onAppMessage(self, message: str):
        if message == "show":
            if self.windowState() & Qt.WindowMinimized:
                self.showNormal()
            else:
                self.show()
        else:
            self.setPlaylist(self.library.loadFromFiles([message]))
            self.show()

    def onCrawlDetailsUrlFinished(self, url: str):
        """ crawl song details url finished thread """
        if url:
            QDesktopServices.openUrl(QUrl(url))
            return

        contentMap = {
            self.getSongDetailsUrlThread: self.tr(
                'Unable to find a matching online song.'),
            self.getAlbumDetailsUrlThread: self.tr(
                'Unable to find a matching online album.'),
            self.getSingerDetailsUrlThread: self.tr(
                'Unable to find a matching online singer.'),
        }
        content = contentMap[self.sender()]
        self.showMessageBox(self.tr("Can't view online"), content)

    def connectSignalToSlot(self):
        """ connect signal to slot """

        # player signal
        self.player.error.connect(self.onPlayerError)
        self.player.positionChanged.connect(self.onPlayerPositionChanged)
        self.player.durationChanged.connect(self.onPlayerDurationChanged)
        self.player.mediaStatusChanged.connect(self.onMediaStatusChanged)

        # media playlist signal
        self.mediaPlaylist.currentIndexChanged.connect(self.getOnlineSongUrl)
        self.mediaPlaylist.currentIndexChanged.connect(self.updateWindow)

        # setting interface signal
        self.settingInterface.acrylicEnableChanged.connect(
            self.setWindowEffect)
        self.settingInterface.selectedMusicFoldersChanged.connect(
            self.onSelectedFolderChanged)
        self.settingInterface.minimizeToTrayChanged.connect(
            self.onMinimizeToTrayChanged)
        self.settingInterface.crawlFinished.connect(
            self.onCrawMetaDataFinished)

        # title signal
        self.titleBar.returnButton.clicked.connect(self.onReturnButtonClicked)

        # navigation interface signal
        self.navigationInterface.displayModeChanged.connect(
            self.onNavigationDisplayModeChanged)
        self.navigationInterface.showCreatePlaylistDialogSig.connect(
            self.showCreatePlaylistDialog)
        self.navigationInterface.searchSig.connect(
            self.switchToSearchResultInterface)

        # play bar signal
        self.playBar.savePlaylistSig.connect(
            lambda: self.showCreatePlaylistDialog(self.mediaPlaylist.playlist))

        # signal bus signal
        signalBus.appMessageSig.connect(self.onAppMessage)

        signalBus.nextSongSig.connect(self.mediaPlaylist.next)
        signalBus.lastSongSig.connect(self.mediaPlaylist.previous)
        signalBus.togglePlayStateSig.connect(self.togglePlayState)
        signalBus.progressSliderMoved.connect(self.onProgressSliderMoved)

        signalBus.muteStateChanged.connect(self.setMute)
        signalBus.volumeChanged.connect(self.onVolumeChanged)

        signalBus.loopModeChanged.connect(self.switchLoopMode)
        signalBus.randomPlayChanged.connect(self.setRandomPlay)

        signalBus.fullScreenChanged.connect(self.setFullScreen)

        signalBus.playAlbumSig.connect(self.playAlbum)
        signalBus.randomPlayAllSig.connect(self.randomPlayAll)
        signalBus.playCheckedSig.connect(self.playCustomPlaylist)
        signalBus.playOneSongCardSig.connect(self.playOneSongCard)
        signalBus.nextToPlaySig.connect(self.onSongsNextToPlay)

        signalBus.editSongInfoSig.connect(self.onEditSongInfo)
        signalBus.editAlbumInfoSig.connect(self.onEditAlbumInfo)
        signalBus.getSongDetailsUrlSig.connect(
            self.getSongDetailsUrlThread.get)
        signalBus.getAlbumDetailsUrlSig.connect(
            self.getAlbumDetailsUrlThread.get)
        signalBus.getSingerDetailsUrlSig.connect(
            self.getSingerDetailsUrlThread.get)

        signalBus.addSongsToPlayingPlaylistSig.connect(
            self.addSongsToPlayingPlaylist)
        signalBus.addSongsToCustomPlaylistSig.connect(
            self.addSongsToCustomPlaylist)
        signalBus.addSongsToNewCustomPlaylistSig.connect(
            self.showCreatePlaylistDialog)
        signalBus.selectionModeStateChanged.connect(
            self.onSelectionModeStateChanged)

        signalBus.removeSongSig.connect(self.deleteSongs)
        signalBus.clearPlayingPlaylistSig.connect(self.clearPlaylist)
        signalBus.deletePlaylistSig.connect(self.onDeleteCustomPlaylist)
        signalBus.renamePlaylistSig.connect(self.onRenamePlaylist)

        signalBus.showPlayingPlaylistSig.connect(self.showPlayingPlaylist)
        signalBus.showPlayingInterfaceSig.connect(self.showPlayingInterface)
        signalBus.switchToSingerInterfaceSig.connect(
            self.switchToSingerInterface)
        signalBus.switchToAlbumInterfaceSig.connect(
            self.switchToAlbumInterface)
        signalBus.switchToMyMusicInterfaceSig.connect(
            self.switchToMyMusicInterface)
        signalBus.switchToPlaylistInterfaceSig.connect(
            self.switchToPlaylistInterface)
        signalBus.switchToRecentPlayInterfaceSig.connect(
            self.switchToRecentPlayInterface)
        signalBus.switchToPlaylistCardInterfaceSig.connect(
            self.switchToPlaylistCardInterface)
        signalBus.switchToSettingInterfaceSig.connect(
            self.switchToSettingInterface)
        signalBus.switchToMoreSearchResultInterfaceSig.connect(
            self.switchToMoreSearchResultInterface)
        signalBus.showSmallestPlayInterfaceSig.connect(
            self.showSmallestPlayInterface)
        signalBus.showLabelNavigationInterfaceSig.connect(
            self.showLabelNavigationInterface)

        # playing interface signal
        self.playingInterface.currentIndexChanged.connect(
            self.onPlayingInterfaceCurrentIndexChanged)
        self.playingInterface.removeSongSignal.connect(
            self.mediaPlaylist.removeSong)
        self.playingInterface.selectionModeStateChanged.connect(
            self.onSelectionModeStateChanged)
        self.playingInterface.switchToVideoInterfaceSig.connect(
            self.showVideoWindow)

        # song tab interface song list widget signal
        self.songTabSongListWidget.playSignal.connect(
            self.onSongTabSongCardPlay)

        # my music interface signal
        self.myMusicInterface.currentIndexChanged.connect(
            self.onMyMusicInterfaceStackWidgetIndexChanged)

        # update lyrics position timer signal
        self.updateLyricPosTimer.timeout.connect(self.onUpdateLyricPosTimeOut)

        # album interface signal
        self.albumInterface.songCardPlaySig.connect(
            self.playAbumSong)

        # recent play signal
        self.recentPlayInterface.playSongCardSig.connect(
            self.playRecentPlaySong)

        # playlist interface signal
        self.playlistInterface.songCardPlaySig.connect(
            self.onPlaylistInterfaceSongCardPlay)
        self.playlistInterface.removeSongSig.connect(
            self.removeSongsFromCustomPlaylist)
        self.playlistInterface.switchToAlbumCardInterfaceSig.connect(
            self.switchToAlbumCardInterface)

        # playlist card interface signal
        self.playlistCardInterface.createPlaylistSig.connect(
            self.showCreatePlaylistDialog)

        # smallest play interface signal
        self.smallestPlayInterface.exitSmallestPlayInterfaceSig.connect(
            self.exitSmallestPlayInterface)

        # label navigation interface signal
        self.labelNavigationInterface.labelClicked.connect(
            self.onNavigationLabelClicked)

        # search result interface signal
        self.searchResultInterface.playLocalSongSig.connect(
            self.playLocalSearchedSong)
        self.searchResultInterface.playOnlineSongSig.connect(
            self.playOnlineSearchedSong)

        # more search result interface signal
        self.moreSearchResultInterface.playLocalSongSig.connect(
            self.playLocalMoreSearchedSong)

        # system tray icon signal
        qApp.aboutToQuit.connect(self.onExit)
        self.systemTrayIcon.exitSignal.connect(qApp.quit)
        self.systemTrayIcon.showMainWindowSig.connect(self.show)

        # video window signal
        self.videoInterface.fullScreenChanged.connect(self.setVideoFullScreen)

        # library thread signal
        self.libraryThread.reloadFinished.connect(self.onReloadFinished)
        self.libraryThread.loadFromFilesFinished.connect(
            self.onLoadFromFilesFinished)

        # library signal
        self.library.fileAdded.connect(self.onFileAdded)
        self.library.fileRemoved.connect(self.onFileRemoved)

        # get details url thread signal
        self.getSongDetailsUrlThread.crawlFinished.connect(
            self.onCrawlDetailsUrlFinished)
        self.getAlbumDetailsUrlThread.crawlFinished.connect(
            self.onCrawlDetailsUrlFinished)
        self.getSingerDetailsUrlThread.crawlFinished.connect(
            self.onCrawlDetailsUrlFinished)


class SplashScreen(QWidget):
    """ Splash screen """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.hBoxLayout = QHBoxLayout(self)
        self.logo = PixmapLabel(self)
        self.logo.setPixmap(QPixmap(":/images/logo/splash_screen_logo.png"))
        self.hBoxLayout.addWidget(self.logo, 0, Qt.AlignCenter)
        self.setAttribute(Qt.WA_StyledBackground)
        color = '2b2b2b' if config.theme == 'dark' else 'ffffff'
        self.setStyleSheet(f'background:#{color}')
