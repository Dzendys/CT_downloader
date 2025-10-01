"""CT module"""

import json
import os
import re
import shutil
from prettytable import PrettyTable
import requests
from bs4 import BeautifulSoup, Tag
from datetime import datetime
from tqdm import tqdm


class CT_Error(Exception):
    """CT error"""

    def __init__(self, message: str, details: str | None = None) -> None:
        """Initializies ``CT_Error`` class"""
        super().__init__(message)
        self.details: str | None = details


class Media:
    """Media class"""

    MEDIA_NAME: str = "medium"
    MEDIA_EXT: str = "mp4"

    def __init__(self, id: str, base_url: str, segments: int) -> None:
        """Initializies ``Media`` class"""
        self.id: str = id
        self.base_url: str = base_url
        self.segments: int = segments

    def download(self, directory: str) -> str:
        """Downloads media"""
        os.makedirs(directory, exist_ok=True)
        os.chdir(directory)
        self._downloadIS()
        for i in tqdm(range(self.segments + 1), desc=self.MEDIA_NAME.capitalize()):
            self._downloadSegment(i)
        return os.path.join(directory, f"{self.MEDIA_NAME}.{self.MEDIA_EXT}")

    def _downloadIS(self) -> None:
        """Downloads IS"""
        rIS = requests.get(self.base_url + self.id + "/" + f"IS.mp4", timeout=60)
        if rIS.status_code != 200:
            raise CT_Error(f"Can't get IS. Status code: {rIS.status_code}")
        try:
            with open(f"{self.MEDIA_NAME}.{self.MEDIA_EXT}", "wb") as f:
                f.write(rIS.content)
        except:
            raise CT_Error("Can't write IS")

    def _downloadSegment(self, index: int) -> None:
        """Downloads segment"""
        rSegment = requests.get(
            f"{self.base_url}/{self.id}/{index:06d}.m4s", timeout=60
        )
        if rSegment.status_code != 200:
            raise CT_Error(
                f"Can't get segment #{index}. Status code: {rSegment.status_code}"
            )
        try:
            with open(f"{self.MEDIA_NAME}.{self.MEDIA_EXT}", "ab") as f:
                f.write(rSegment.content)
        except:
            raise CT_Error("Can't write segment")

    def mergeAudioAndVideo(video_path: str, audio_path: str, output_path: str) -> None:
        """Merges audio and video"""
        command: str = (
            f'ffmpeg -hide_banner -loglevel error -stats -i "{video_path}" -i "{audio_path}" -c copy "{output_path}"'
        )
        os.system(command)


class Video(Media):
    """Video class"""

    MEDIA_NAME: str = "video"

    def __init__(
        self,
        id: str,
        base_url: str,
        segments: int,
        codecs: str,
        width: int,
        height: int,
        bandwidth: int,
    ) -> None:
        """Initializies ``Video`` class"""
        super().__init__(id, base_url, segments)
        self.codecs: str = codecs
        self.width: int = width
        self.height: int = height
        self.bandwidth: int = bandwidth


class Audio(Media):
    MEDIA_NAME: str = "audio"

    def __init__(
        self,
        id: str,
        base_url: str,
        segments: int,
        codecs: str,
        audioSamplingRate: int,
        bandwidth: int,
    ) -> None:
        """Initializies ``Audio`` class"""
        super().__init__(id, base_url, segments)
        self.codecs: str = codecs
        self.audioSamplingRate: int = audioSamplingRate
        self.bandwidth: int = bandwidth


class Subtitle:
    """Subtitle class"""

    def __init__(self, language: str, format: str, url: str) -> None:
        """Initializies ``Subtitle`` class"""
        self.language: str = language
        self.format: str = format
        self.url: str = url

    def download(self, name: str, directory: str) -> None:
        """Downloads subtitle"""
        os.makedirs(directory, exist_ok=True)
        os.chdir(directory)
        rSub = requests.get(self.url, timeout=60)
        if rSub.status_code != 200:
            raise CT_Error(f"Can't get subtitle. Status code: {rSub.status_code}")
        try:
            with open(f"{name}_{self.language}.{self.format}", "wb") as f:
                f.write(rSub.content)
        except:
            raise CT_Error("Can't write subtitle")


class MPDParser:
    """MPD parser"""

    def __init__(self, mpd: str) -> None:
        """Initializies ``MPDParser`` class"""
        self.mpd: str = mpd
        self.base_url: str | None = None
        self.videos: list[Video] = []
        self.audios: list[Audio] = []
        self._parse()

    def _parse(self) -> None:
        """Parses MPD"""
        cur_state: str = ""
        segments: int = 0
        for line in self.mpd.split("\n"):
            # BASE URL
            if line.startswith("<BaseURL>"):
                self.base_url = line.split("<BaseURL>")[1].split("</BaseURL>")[0]
            # ADAPTATION SET
            elif line.startswith("<AdaptationSet"):
                mediaType: str = line.split('mimeType="')[1].split('/mp4"')[0]
                if mediaType == "video":
                    cur_state = "video"
                elif mediaType == "audio":
                    cur_state = "audio"
            elif line.startswith("</AdaptationSet"):
                cur_state = ""
            # NUMBER OF SEGMENTS
            elif line.startswith("<S "):
                atributes: dict[str, str] = dict(re.findall(r'(\w+)="([^"]+)"', line))
                if atributes["t"] == "0":
                    segments = int(atributes["r"])
            # REPRESENTATION
            elif line.startswith("<Representation"):
                if cur_state == "video":
                    self.videos.append(self._parseVideoRepresentation(line, segments))
                elif cur_state == "audio":
                    self.audios.append(self._parseAudioRepresentation(line, segments))

    def _parseVideoRepresentation(self, line: str, segments: int) -> Video:
        """Parses video representation"""
        attributes: dict[str, str] = dict(re.findall(r'(\w+)="([^"]+)"', line))
        return Video(
            id=attributes["id"],
            base_url=self.base_url,
            segments=segments,
            codecs=attributes["codecs"],
            width=int(attributes["width"]),
            height=int(attributes["height"]),
            bandwidth=int(attributes["bandwidth"]),
        )

    def _parseAudioRepresentation(self, line: str, segments: int) -> Audio:
        """Parses audio representation"""
        attributes: dict[str, str] = dict(re.findall(r'(\w+)="([^"]+)"', line))
        return Audio(
            id=attributes["id"],
            base_url=self.base_url,
            segments=segments,
            codecs=attributes["codecs"],
            audioSamplingRate=int(attributes["audioSamplingRate"]),
            bandwidth=int(attributes["bandwidth"]),
        )


class CT:
    """CT downloader
    - can download video only using url (noob friendly)"""

    VALID_URLS: str = [r"https://www.ceskatelevize.cz/"]
    PLAYLIST_INFO: str = (
        r"https://api.ceskatelevize.cz/video/v1/playlist-vod/v1/stream-data/media/external/"
    )

    def __init__(self, url: str, directory: str, name: str | None = None) -> None:
        """Initializies ``CT`` class"""
        self.url: str = self._getUrl(url=url)
        self.source_code: BeautifulSoup = self._getSourceCode()
        self.directory: str = self._getDirectory(directory=directory)
        self.id: str = self._getID()
        self.playlist_info: dict = self._getPlaylistInfo()
        self.drm_protection: bool = self._checkDRM()
        self.name: str = self._getName(name=name)
        self.valid_name: str = self._getValidName(self.name)
        if self.drm_protection:
            self.subtitles: list[Subtitle] = []
            self.mpd_parser: MPDParser = None
            self.audios: list[Audio] = []
            self.videos: list[Video] = []
            return
        self.subtitles: list[Subtitle] = self._getSubs()
        self.mpd_parser: MPDParser = self._getMPD()
        self.audios: list[Audio] = sorted(
            self.mpd_parser.videos, key=lambda v: (v.height, v.bandwidth), reverse=True
        )
        self.videos: list[Video] = sorted(
            self.mpd_parser.audios,
            key=lambda a: (a.bandwidth, a.audioSamplingRate),
            reverse=True,
        )

    def displayInfo(self, clear_terminal: bool = False) -> None:
        """Displays info about video"""
        t: PrettyTable = PrettyTable()
        t.align = "l"
        t.header = False
        t.add_row(["\033[1mNázev videa\033[0m", self.name])
        t.add_row(["\033[1mURL videa\033[0m", self.url])
        t.add_row(["\033[1mUmístění\033[0m", self.directory])
        if len(self.subtitles) > 0:
            languages: set[str] = set([sub.language for sub in self.subtitles])
            formats: set[str] = set([sub.format for sub in self.subtitles])
            t.add_row(
                [
                    "\033[1mTitulky\033[0m",
                    "/".join(languages) + " (" + ", ".join(formats) + ")",
                ]
            )
        else:
            t.add_row(["\033[1mTitulky\033[0m", "Nejsou k dispozici"])
        t.add_row(
            [
                "\033[1mDRM\033[0m",
                "Ano (nelze stáhnout)" if self.drm_protection else "Ne (lze stáhnout)",
            ]
        )
        if clear_terminal:
            print("\033[H\033[J", end="")
        print(t)

    def _getUrl(self, url: str) -> str:
        """Checks url and returns it if it's valid"""
        for valid_url in self.VALID_URLS:
            if url.startswith(valid_url):
                return url
        raise CT_Error("Neplatná url.")

    def _getSourceCode(self) -> BeautifulSoup:
        """Gets source code of the page"""
        response: requests.Response = requests.get(self.url, timeout=60)
        if response.status_code != 200:
            raise CT_Error(
                f"Nemohl jsem se dostat na web. Zkontroluj připojení k internetu nebo správnost url.",
                response.status_code,
            )
        return BeautifulSoup(response.text, "html.parser")

    def _getDirectory(self, directory: str) -> str:
        """Checks directory and creates it if it doesn't exist"""
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except Exception as e:
                raise CT_Error(f"Nepodařilo se mi vytvořit složku. {e}")
        return directory

    def _getID(self) -> str:
        """Gets id of the video"""
        try:
            script: Tag = self.source_code.find_all(
                "script", {"type": "application/ld+json"}
            )[1]
        except IndexError:
            raise CT_Error("Nenašel jsem ID-script v source codu.")
        except Exception as e:
            raise CT_Error(
                f"Hledání ID-scriptu selhalo. Struktura stránky se mohla změnit", e
            )
        try:
            contents: dict = json.loads(script.contents[0])
            embed_url: str = contents["video"]["embedUrl"]
            return embed_url.split("IDEC=")[1]
        except ValueError:
            raise CT_Error("Nenašel jsem id ve scriptu.")
        except Exception as e:
            raise CT_Error("Hledání ID selhalo. Struktura skriptu se mohla změnit.", e)

    def _getPlaylistInfo(self) -> dict:
        """Returns dictionary full of information about video"""
        try:
            r = requests.get(self.PLAYLIST_INFO + self.id, timeout=60)
            return json.loads(r.text)
        except Exception as e:
            raise CT_Error(f"Nepodařilo se získat adresu videa na serveru.", e)

    def _checkDRM(self) -> bool:
        """Checks if video is DRM protected"""
        try:
            return self.playlist_info["error"]["type"] == "ResourceLicenceError"
        except Exception:
            return False

    def _getName(self, name: str | None) -> str:
        """Gets name of the video on CT"""
        if name is None or name == "":
            if self.drm_protection:
                return "-"
            return self.playlist_info["title"]
        return name

    def _getValidName(self, name: str, char: str = "_") -> str:
        """Returns name of the video without special characters"""
        invalid_chars: str = r"[^a-zA-Z0-9" + re.escape(char) + "áéíóúýčďěňřšťžů" + "]+"
        return re.sub(invalid_chars, char, name)

    def _getSubs(self) -> list[Subtitle]:
        """Fetches subtitles"""
        subsList: list[Subtitle] = []
        try:
            subs: dict = self.playlist_info["streams"][-1]["subtitles"]
            for sub in subs:
                for format_ in sub["files"]:
                    subsList.append(
                        Subtitle(sub["language"], format_["format"], format_["url"])
                    )
            return subsList
        except Exception:
            return []

    def _getMPD(self) -> MPDParser:
        """Returns MPDParser object"""
        mpd_link: str = self.playlist_info["streams"][-1]["url"]
        r = requests.get(mpd_link, timeout=60)
        if r.status_code != 200:
            raise CT_Error(f"Can't get mpd file. Status code: {r.status_code}")
        return MPDParser(r.text)

    def download(self, subs: bool = False, keep_original: bool = False) -> None:
        """Downloads video stream in best quality and converts it"""
        # DRM
        if self.drm_protection:
            print("Video je zabezpečené DRM. Nelze stáhnout.")
            return

        # TEMPORARY DIRECTORY
        temp_dir: str = os.path.join(
            self.directory, "temp_" + datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        )
        os.makedirs(temp_dir, exist_ok=True)

        # DOWNLOAD
        video_path: str = self.videos[0].download(temp_dir)
        audio_path: str = self.audios[0].download(temp_dir)
        Media.mergeAudioAndVideo(
            video_path,
            audio_path,
            os.path.join(self.directory, self.valid_name + ".mp4"),
        )

        # SUBTITLES
        if subs:
            self._downloadSubs()

        # CLEANUP
        os.chdir(self.directory)
        if not keep_original:
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                raise CT_Error("Nepodařilo se smazat dočasnou složku.")

        print(f"Staženo!")
        os.startfile(os.path.realpath(self.directory))

    def _downloadSubs(self) -> None:
        """Downloads subs"""
        if len(self.subtitles) == 0:
            return
        for sub in self.subtitles:
            try:
                sub.download(self.valid_name, self.directory)
            except CT_Error as e:
                raise CT_Error(
                    f"Nemohl jsem stáhnout titulky ve formátu {sub.format}. Chyba: {e}"
                )

    def _txtToSrt(self, source: str) -> str:
        """Converts subtitle contents into ``srt`` format"""

        def seconds(milliseconds: str) -> str:
            """Converts miliseconds to ``srt format``"""
            seconds, milliseconds = divmod(milliseconds, 1000)
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            srt_time = f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
            return srt_time

        lines = source.split("\n")
        start: bool = True
        srt_file: str = ""
        for line in lines:
            if start and line != "":
                index: str = line.strip().split(";")[0]
                start_time, end_time = line.strip().split(" ")[1:]
                # Convert start and end times to SRT format (HH:MM:SS,ms)
                start_time = seconds(int(start_time))
                end_time = seconds(int(end_time))
                srt_file += f"{index}\n{start_time} --> {end_time}\n"
                start = False
            else:
                if line == "":
                    start = True
                    srt_file += "\n"
                    continue
                srt_file += line + "\n"
        return srt_file


class CT_Gold(CT):
    """CT Gold downloader
    - can download video only using url (noob friendly)"""

    VALID_URLS: str = [r"https://zlatapraha.ceskatelevize.cz/"]
    PLAYLIST_INFO: str = (
        r"https://api.ceskatelevize.cz/video/v1/playlist-vod/v1/stream-data/media/external/"
    )

    def __init__(self, url: str, directory: str, name: str | None = None) -> None:
        super().__init__(url, directory, name)

    def _getID(self):
        iframes: list[Tag] = self.source_code.find_all("iframe")
        for iframe in iframes:
            try:
                source: str = iframe["src"]
                if source.startswith("https://player.ceskatelevize.cz/?videoId="):
                    return source.split("videoId=")[1].split("&origin=zlatapraha")[0]
            except Exception:
                pass
        raise CT_Error("Can't find video ID")
