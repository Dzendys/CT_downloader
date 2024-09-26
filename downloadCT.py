"""CT module"""
import json
import os
import requests
from bs4 import BeautifulSoup, Tag
from downloadM3u8 import M3U8, M3U8Index
import asyncio

class CT:
    """CT downloader
    - can download video only using url (noob friendly)"""
    def __init__(self, url:str, directory:str, name:str | None = None) -> None:
        """Initializies ``CT`` class"""
        self.url:str = url
        self.directory:str = directory
        self.ct_name:str = ""
        self.id: str = self.getID()
        self.name:str = self.getName(name=name)
        self.playlist_info:dict = self.getPlaylistInfo()
        self.subtitles_url:str | None = self.trySubs()
        self.playlist_url = self.getPlaylistUrl()
        self.video: M3U8 = M3U8(playlist_url=self.playlist_url,
                                directory=self.directory,
                                name=self.name)
        print("Inicializace proběhla úsěšně!")

    def download(self, subs: bool = False) -> None:
        """Downloads video stream in best quality and converts it"""
        #loop = asyncio.get_event_loop()
        #loop.run_until_complete(self.video.asyncDownload(self.video.get_best_stream()))
        print("Začíná stahování segmentů...")
        stream:M3U8Index = self.video.get_best_stream()
        contents: str = requests.get(stream.url).text
        self.video._make_tempdir()
        os.chdir(self.video.temp_directory)
        for line in contents.split("\n"):
            if line.startswith("http"):
                with open(f"{self.video.name}{self.video.extention_in}", "ab") as f:
                    f.write(requests.get(line).content)
        self.video._convert(remove=True)
        if subs:
            self._downloadSubs()

    def _downloadSubs(self) -> None:
        """Downloads subs"""
        if self.subtitles_url is None:
            print("Titulky nejsou k dispozici!")
            return
        with open(os.path.join(self.directory, self.video.name+".srt"), "w") as f:
            f.write(self.txtToSrt(requests.get(self.subtitles_url).content.decode()))
        print("Titulky staženy!")

    def getPlaylistInfo(self) -> dict:
        """Returns dictionary full of information about video"""
        data = {
            'playlist[0][type]': 'episode',
            'playlist[0][id]': self.id,
            'requestUrl': '/ivysilani/embed/iFramePlayer.php',
            'requestSource': 'iVysilani',
            'type': 'html',
            'canPlayDRM': 'true',
            'streamingProtocol': 'dash',
        }
        r1 = requests.post('https://www.ceskatelevize.cz/ivysilani/ajax/get-client-playlist/', data=data)
        a = json.loads(r1.text)
        r2 = requests.get(a["url"])
        b = json.loads(r2.text)
        return b["playlist"][-1]

    def getPlaylistUrl(self) -> str:
        """Gets ``playlist url`` using requests"""
        return self.playlist_info["streamUrls"]["main"]

    def getID(self) -> str:
        """Gets id of the video and also changes CT name to proper name"""
        print("Zjišťuji ID videa...")
        response:requests.Response = requests.get(self.url)
        soup:BeautifulSoup = BeautifulSoup(response.text, 'html.parser')
        try:
            script:Tag = soup.find_all('script', {'type': 'application/ld+json'})[1]
        except IndexError:
            print("Nenašel jsem video!")
            return
        contents:dict = json.loads(script.contents[0])
        self.ct_name = contents["name"]
        embed_url:str = contents["video"]["embedUrl"]
        return embed_url.split("IDEC=")[1]

    def getName(self, name:str | None) -> str:
        """Gets name of the video on CT"""
        if name is not None and name != "":
            return name
        return self.ct_name

    def trySubs(self) -> str | None:
        """Tries to fetch subtitles url"""
        try:
            return self.playlist_info["subtitles"][0]["url"]
        except KeyError:
            return None

    def txtToSrt(self, source:str) -> str:
        """Converts subtitle contents into ``srt`` format"""
        def seconds(milliseconds:str) -> str:
            """Converts miliseconds to ``srt format``"""
            seconds, milliseconds = divmod(milliseconds, 1000)
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            srt_time = f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
            return srt_time
        lines = source.split("\n")
        start: bool = True
        srt_file:str = ""
        for line in lines:
            if start and line != "":
                index:str = line.strip().split(";")[0]
                start_time, end_time = line.strip().split(" ")[1:]
                # Convert start and end times to SRT format (HH:MM:SS,ms)
                start_time = seconds(int(start_time))
                end_time = seconds(int(end_time))
                srt_file+= f"{index}\n{start_time} --> {end_time}\n"
                start = False
            else:
                if line == "":
                    start = True
                    srt_file += "\n"
                    continue
                srt_file += line+"\n"
        return srt_file
