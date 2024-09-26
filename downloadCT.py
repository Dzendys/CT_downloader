"""CT module"""
import json
import os
import requests
from bs4 import BeautifulSoup, Tag
from downloadM3u8 import M3U8, M3U8Index

class CT_Error(Exception):
    """CT error"""
    def __init__(self, message:str, details:str | None = None) -> None:
        """Initializies ``CT_Error`` class"""
        super().__init__(message)
        self.details:str | None = details

class CT:
    """CT downloader
    - can download video only using url (noob friendly)"""

    VALID_URLS:str = ["https://www.ceskatelevize.cz/"]

    def __init__(self, url:str, directory:str, name:str | None = None) -> None:
        """Initializies ``CT`` class"""
        self.url:str = self._getUrl(url=url)
        self.source_code: BeautifulSoup = self._getSourceCode()
        self.directory:str = self._getDirectory(directory=directory)
        self.id: str = self._getID()
        self.playlist_info:dict = self._getPlaylistInfo()
        self.playlist_url = self._getPlaylistUrl()
        self.name:str = self._getName(name=name)
        self.subtitles_urls: list[str,str] | list[None] = self._getSubs()
        
        self.video: M3U8 = M3U8(playlist_url=self.playlist_url,
                                directory=self.directory,
                                name=self.name)
        print("Inicializace proběhla úsěšně!")

    def _getUrl(self, url:str) -> str:
        """Checks url and returns it if it's valid"""
        print("Kontrola url...")
        for valid_url in self.VALID_URLS:
            if url.startswith(valid_url):
                return url
        raise CT_Error("Neplatná url.")

    def _getSourceCode(self) -> BeautifulSoup:
        """Gets source code of the page"""
        print("Stahování informací z webu...")
        response:requests.Response = requests.get(self.url)
        if response.status_code != 200:
            raise CT_Error(f"Nemohl jsem se dostat na web. Zkontroluj připojení k internetu nebo správnost url.",response.status_code)
        return BeautifulSoup(response.text, 'html.parser')
    
    def _getDirectory(self, directory:str) -> str:
        """Checks directory and creates it if it doesn't exist"""
        print("Kontrola existence složky...")
        if not os.path.exists(directory):
            print("Složka neexistuje, vytvářím novou...")
            try:
                os.makedirs(directory)
            except Exception as e:
                raise CT_Error(f"Nepodařilo se mi vytvořit složku. {e}")
        return directory

    def _getID(self) -> str:
        """Gets id of the video"""
        print("Zjišťuji ID videa...")
        try:
            script:Tag = self.source_code.find_all('script', {'type': 'application/ld+json'})[1]
        except IndexError:
            raise CT_Error("Nenašel jsem ID-script v source codu.")
        except Exception as e:
            raise CT_Error(f"Hledání ID-scriptu selhalo. Struktura stránky se mohla změnit", e)
        try:
            contents:dict = json.loads(script.contents[0])
            embed_url:str = contents["video"]["embedUrl"]
            return embed_url.split("IDEC=")[1]
        except ValueError:
            raise CT_Error("Nenašel jsem id ve scriptu.")
        except Exception as e:
            raise CT_Error("Hledání ID selhalo. Struktura skriptu se mohla změnit.", e) 

    def _getPlaylistInfo(self) -> dict:
        """Returns dictionary full of information about video"""
        print("Zjišťuji klíč k lokaci playlistu...")
        data = {
            'playlist[0][type]': 'episode',
            'playlist[0][id]': self.id,
            'requestUrl': '/ivysilani/embed/iFramePlayer.php',
            'requestSource': 'iVysilani',
            'type': 'html',
            'canPlayDRM': 'true',
            'streamingProtocol': 'dash',
        }
        try:
            r1 = requests.post('https://www.ceskatelevize.cz/ivysilani/ajax/get-client-playlist/', data=data)
            a = json.loads(r1.text)
            r2 = requests.get(a["url"])
            b = json.loads(r2.text)
            return b["playlist"][-1]
        except Exception as e:
            raise CT_Error(f"Nepodařilo se získat adresu videa na serveru.", e)

    def _getPlaylistUrl(self) -> str:
        """Gets ``playlist url``"""
        print("Zjišťuji url adresu playlistu...")
        try:
            return self.playlist_info["streamUrls"]["main"]
        except ValueError:
            raise CT_Error("Nepodařilo se proparsovat url adresu videa z playlistu.")
        except Exception as e:
            raise CT_Error(f"Parsování url adresy playlistu selhalo. Struktura playlistu se mohla změnit", e)

    def _getName(self, name:str | None) -> str:
        """Gets name of the video on CT"""
        if name is None or name == "":
            try:
                return self._getNameFromPlaylistInfo()
            except CT_Error as e:
                return self._getNameFromSourceCode()
        return name

    def _getNameFromPlaylistInfo(self) -> str:
        """Gets name of the video from playlist"""
        print("Hledám název videa v playlistu...")
        try:
            return self.playlist_info["title"]
        except Exception as e:
            raise CT_Error("Nepodařilo se najít jméno videa v playlistu.", e)
    
    def _getNameFromSourceCode (self) -> str:
        """Gets name of the video from web"""
        print("Hledám název videa na webu...")
        try:
            script:Tag = self.source_code.find_all('script', {'type': 'application/ld+json'})[1]
        except IndexError:
            raise CT_Error("Nenašel jsem jméno videa.")
        except Exception as e:
            raise CT_Error(f"Hledání jména selhalo. Struktura stránky se mohla změnit", e)
        contents:dict = json.loads(script.contents[0])
        return contents["name"]

    def _getSubs(self) -> list[str,str] | list[None]:
        """Fetches subtitles urls"""
        try:
            return [[sub["title"], sub["url"]] for sub in self.playlist_info["subtitles"]]
        except Exception:
            return []
    
    def download(self, subs: bool = False, convert: bool = True) -> None:
        """Downloads video stream in best quality and converts it"""
        print("Začíná stahování segmentů...")
        stream:M3U8Index = self.video.get_best_stream()
        contents: str = requests.get(stream.url).text
        self.video._make_tempdir()
        os.chdir(self.video.temp_directory)
        for line in contents.split("\n"):
            if line.startswith("http"):
                with open(f"{self.video.name}{self.video.extention_in}", "ab") as f:
                    f.write(self.video._downloadSegment(line))
        if convert:
            print("Začíní konvertování segmentů...")
            self.video._convert(remove=True)
        if subs:
            self._downloadSubs()

    def _downloadSubs(self) -> None:
        """Downloads subs"""
        print("Stahování titulků...")
        if len(self.subtitles_urls) ==0:
            print("Titulky nejsou k dispozici!")
            return
        for sub_name, sub_url in self.subtitles_urls:
            with open(os.path.join(self.directory, self.video.name + f" ({sub_name})" + ".srt"), "w") as f:
                f.write(self._txtToSrt(requests.get(sub_url).content.decode()))
            print(f"Stažené titulky: {sub_name}.")   

    def _txtToSrt(self, source:str) -> str:
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


class CT_Gold(CT):
    """CT Gold downloader
    - can download video only using url (noob friendly)"""

    VALID_URLS:str = ["https://zlatapraha.ceskatelevize.cz/"]

    def __init__(self, url: str, directory: str, name: str | None = None) -> None:
        super().__init__(url, directory, name)

    def _getPlaylistInfo(self) -> dict:
        """Returns dictionary full of information about video"""
        print("Zjišťuji klíč k lokaci playlistu...")
        data = {
            'playlist[0][type]': 'bonus',
            'playlist[0][id]': self.id,
            'requestUrl': '/ivysilani/embed/iFramePlayer.php',
            'requestSource': 'iVysilani',
            'type': 'html',
            'canPlayDRM': 'true',
        }
        try:
            r1 = requests.post('https://www.ceskatelevize.cz/ivysilani/ajax/get-client-playlist/', data=data)
            a = json.loads(r1.text)
            r2 = requests.get(a["url"])
            b = json.loads(r2.text)
            return b["playlist"][-1]
        except Exception as e:
            raise CT_Error(f"Nepodařilo se získat adresu videa na serveru.", e)

    def _getNameFromSourceCode(self) -> str:
        """Gets name of the video from web"""
        print("Hledám název videa na webu...")
        try:
            title:Tag = self.source_code.find('title')
            self.ct_name = title.text.split("|")[0].strip()
        except ValueError:
            raise CT_Error("Nedokázal jsem proparsovat název videa ze source codu.")
        except Exception as e:
            raise CT_Error("Hledání jména ze source codu selhalo. Struktura stránky se mohla změnit.", e)
    
    def _getID(self) -> str:
        """Gets id of the video"""
        print("Zjišťuji ID videa...")
        try:
            iframes:Tag = self.source_code.find_all('iframe')
            for iframe in iframes:
                if iframe['src'].startswith("https://www.ceskatelevize.cz/ivysilani/embed/iFramePlayer.php?"):
                    return iframe['src'].split("bonus=")[1][:5]
        except ValueError:
            raise CT_Error("Nedokázal jsem proparsovat ID videa ze source codu.")
        except Exception as e:
            raise CT_Error("Hledání ID videa selhalo. Struktura stránky se mohla změnit.", e)
