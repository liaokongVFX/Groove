# coding:utf-8
import base64
from pathlib import Path
from shutil import rmtree
from typing import List, Union

from common.database.entity import SongInfo
from common.image_utils import getPicSuffix
from common.logger import Logger
from common.os_utils import getCoverName
from mutagen import File, FileType
from mutagen.aac import AAC
from mutagen.aiff import AIFF
from mutagen.apev2 import APEv2
from mutagen.asf import ASF, ASFByteArrayAttribute
from mutagen.flac import FLAC, Picture
from mutagen.flac import error as FLACError
from mutagen.id3 import ID3
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.oggflac import OggFLAC
from mutagen.oggopus import OggOpus
from mutagen.oggspeex import OggSpeex
from mutagen.oggvorbis import OggVorbis
from mutagen.trueaudio import TrueAudio
from mutagen.wave import WAVE

logger = Logger("meta_data_reader")


def exceptionHandler(func):
    """ decorator for exception handling

    Parameters
    ----------
    *default:
        the default value returned when an exception occurs
    """

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(e)
            return False

    return wrapper


class AlbumCoverReader:
    """ Read and save album cover class """

    coverFolder = Path("cache/Album_Cover")
    _readers = []

    @classmethod
    def register(cls, reader):
        """ register album cover reader

        Parameters
        ----------
        reader:
            album cover reader class
        """
        if reader not in cls._readers:
            cls._readers.append(reader)

        return reader

    @classmethod
    def getAlbumCovers(cls, songInfos: List[SongInfo]):
        """ Read and save album covers from audio files """
        cls.coverFolder.mkdir(exist_ok=True, parents=True)
        for songInfo in songInfos:
            cls.getAlbumCover(songInfo)

    @classmethod
    @exceptionHandler
    def getAlbumCover(cls, songInfo: SongInfo) -> bool:
        """ Read and save an album cover from audio file """
        cls.coverFolder.mkdir(exist_ok=True, parents=True)

        if cls.__isCoverExists(songInfo.singer, songInfo.album):
            return True

        file = songInfo.file
        for Reader in cls._readers:
            if not Reader.canRead(file):
                continue

            picData = Reader.read(file)
            if picData:
                cls.__save(songInfo.singer, songInfo.album, picData)
                return True

        return False

    @classmethod
    def __isCoverExists(cls, singer: str, album: str) -> bool:
        """ Check whether the cover exists """
        folder = cls.coverFolder / getCoverName(singer, album)

        isExists = False
        if folder.exists():
            files = list(folder.glob('*'))

            if files:
                suffix = files[0].suffix.lower()
                if suffix in [".png", ".jpg", ".jpeg", ".jiff", ".gif"]:
                    isExists = True
                else:
                    rmtree(folder)

        return isExists

    @classmethod
    def __save(cls, singer: str, album: str, picData: bytes):
        """ save album cover """
        folder = cls.coverFolder / getCoverName(singer, album)
        folder.mkdir(exist_ok=True, parents=True)

        suffix = getPicSuffix(picData)
        with open(folder/("cover" + suffix), "wb") as f:
            f.write(picData)


class CoverDataReaderBase:
    """ Album cover data reader base class """

    formats = []
    options = []

    @classmethod
    def canRead(cls, file: Union[Path, str]) -> bool:
        """ determine whether cover data of the file can be read """
        return str(file).lower().endswith(tuple(cls.formats))

    @classmethod
    def read(cls, audio: FileType) -> bytes:
        """ extract binary data of album cover from audio file

        Parameters
        ----------
        audio: FileType
            audio tag instance

        Returns
        -------
        picData: bytes
            binary data of album cover, `None` if no cover is found
        """
        raise NotImplementedError


@AlbumCoverReader.register
class ID3CoverDataReader(CoverDataReaderBase):
    """ MP3 album cover data reader """

    formats = [".mp3", ".aac", ".tta"]
    options = [MP3, AAC, TrueAudio]

    @classmethod
    def read(cls, file: Union[Path, str]) -> bytes:
        try:
            return cls._readFromTag(ID3(file))
        except:
            return None

    @classmethod
    def _readFromTag(cls, tag):
        """ read cover from tag """
        for k in tag.keys():
            if k.startswith("APIC"):
                return tag[k].data


@AlbumCoverReader.register
class FLACCoverDataReader(CoverDataReaderBase):
    """ FLAC album cover data reader """

    formats = [".flac"]
    options = [FLAC]

    @classmethod
    def read(cls, file: Union[Path, str]) -> bytes:
        audio = FLAC(file)
        if not audio.pictures:
            return None

        return audio.pictures[0].data


@AlbumCoverReader.register
class MP4CoverDataReader(CoverDataReaderBase):
    """ MP4/M4A album cover data reader """

    formats = [".m4a", ".mp4"]
    options = [MP4]

    @classmethod
    def read(cls, file: Union[Path, str]) -> bytes:
        audio = MP4(file)
        if not audio.get("covr"):
            return None

        return bytes(audio["covr"][0])


@AlbumCoverReader.register
class OGGCoverDataReader(CoverDataReaderBase):
    """ OGG album cover data reader """

    formats = [".ogg", ".opus"]
    options = [OggVorbis, OggFLAC, OggSpeex, OggOpus]

    @classmethod
    def read(cls, file: Union[Path, str]) -> bytes:
        audio = File(file, options=cls.options)
        for base64Data in audio.get("metadata_block_picture", []):
            try:
                return Picture(base64.b64decode(base64Data)).data
            except (TypeError, ValueError, FLACError):
                continue


@AlbumCoverReader.register
class SuperID3CoverDataReader(ID3CoverDataReader):
    """ Super ID3 album cover data reader """

    formats = [".aiff", ".wav"]
    options = [AIFF, WAVE]

    @classmethod
    def read(cls, file: Union[Path, str]) -> bytes:
        return cls._readFromTag(File(file, options=cls.options))


@AlbumCoverReader.register
class APECoverDataReader(CoverDataReaderBase):
    """ APEv2 album cover data reader """

    formats = [".ac3", ".ape", ".wv", ".mpc"]
    options = [APEv2]

    @classmethod
    def read(cls, file: Union[Path, str]) -> bytes:
        try:
            return cls._readFromTag(APEv2(file))
        except:
            return None

    @classmethod
    def _readFromTag(cls, tag):
        """ read cover from tag """
        picture = tag.get("Cover Art (Front)", None)
        if picture is None:
            return None

        return picture.value


@AlbumCoverReader.register
class ASFCoverDataReader(CoverDataReaderBase):
    """ ASF album cover data reader """

    formats = [".asf", ".wma"]
    options = [ASF]

    @classmethod
    def read(cls, file: Union[Path, str]) -> bytes:
        audio = ASF(file)
        picture = audio.get('WM/Picture')  # type:List[ASFByteArrayAttribute]
        if not picture:
            return None

        return picture[0].value
