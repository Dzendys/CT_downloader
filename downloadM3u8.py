import requests
import shutil
import os
import time
from aiohttp import ClientSession
import asyncio

class M3U8Index:
    """Index/stream from playlist.m3u8"""
    def __init__(self, bandwidth: int, resolution: str, url: str) -> None:
        """Initializes M3U8Index class"""
        self.bandwith: int = bandwidth
        self.resolution: str = resolution
        self.url: str = url
    
    def __str__(self) -> str:
        """If print statement is placed on M3U8Index"""
        return "STREAM"+"\n"+f"\t - resolution: {self.resolution}"+"\n"+f"\t - bandwith: {self.bandwith}"

class M3U8:
    def __init__(self, playlist_url: str, directory: str, name:str, extentiton_in: str = ".ts", extention_out: str = ".mp4", headers: dict = {}, middle_path:str | None = None) -> None:
        self.headers = headers
        self.playlist_url: str = playlist_url
        self.middle_path:str | None = middle_path
        self.streams:list[M3U8Index] = self.get_streams()
        self.directory: str = directory
        self.name: str = self._valid_name(name)
        self.temp_directory: str = os.path.join(self.directory, self.name)
        self.extention_in = extentiton_in
        self.extention_out = extention_out

    def get_streams(self) -> list[M3U8Index]:
        """Return all streams"""
        streams: list[M3U8Index] = []
        #GETTING ALL STREAMS
        content: str = requests.get(self.playlist_url, headers=self.headers).text
        for index, line in enumerate(content.split("\n")):
            if line.startswith("#EXT-X-STREAM-INF"):
                parts: list[str] = line[18:].split(",")
                url: str = str(content.split("\n")[index+1])
                bandwidth: str|None = None
                resolution: str|None = None
                for i, part in enumerate(parts):
                    if str(part).startswith("BANDWIDTH"):
                        bandwidth=int(parts[i].split("=")[1])
                    if str(part).startswith("RESOLUTION"):
                        resolution=parts[i].split("=")[1]
                if self.middle_path is not None:
                    url_parts:list[str] = url.split("/")
                    url_parts.insert(1,str(self.middle_path))
                    url:str = "/".join(url_parts)
                if not url.startswith("http"):
                    url: str = self.playlist_url.rsplit("/", 1)[0] + "/" + url
                #ADDING TO LIST
                streams.append(M3U8Index(bandwidth=bandwidth,
                                               resolution=resolution,
                                               url=url))
        return streams

    def get_best_stream(self) -> M3U8Index:
        """Returns best stream"""
        best_stream: M3U8Index = self.streams[0]
        for stream in self.streams[1:]:
            if stream.bandwith > best_stream.bandwith:
                best_stream = stream
        return best_stream

    async def asyncDownload(self, stream: M3U8Index, base_url:str = "", maxRequestsAtTime:int = 100):
        """Downloads segments asynchronously from index file"""
        if base_url != "" or base_url is not None:
            base_url: str = stream.url.rsplit("/", 1)[0] + "/"
        contents: str = requests.get(stream.url, headers=self.headers).text
        session:ClientSession = ClientSession()
        semaphore:asyncio.Semaphore = asyncio.Semaphore(maxRequestsAtTime)
        tasks: list = []
        for line in contents.split("\n"):
            if not line.startswith("#"):
                task = asyncio.create_task(self._asyncDownloadSegment(url=base_url+line, session=session, semaphore=semaphore))
                tasks.append(task)
        self._make_tempdir()
        os.chdir(self.temp_directory)
        downloaded_data:list[str] = await asyncio.gather(*tasks)
        await self._asyncWriteDownloadedData(downloaded_data)
        await session.close()

    async def _asyncDownloadSegment(self, url:str, session:ClientSession, semaphore:asyncio.Semaphore) -> str:
        """Downloads asynchronously one segment"""
        async with semaphore:
            for tries in range(1,6):
                try:
                    response = await session.get(url=url, headers=self.headers)
                    return await response.read()
                except Exception as e:
                    print(f"Connection error, trying in 5 seconds... {tries}/5")
                    time.sleep(5)
            else:
                raise Exception(e)

    async def _asyncWriteDownloadedData(self, data_list) -> None:
        """Writes down downloaded data"""
        with open(f"{self.name}{self.extention_in}", "wb") as f:
            for data in data_list:
                f.write(data)

    def download(self, stream: M3U8Index, base_url:str = ""):
        """Downloads segments from index file"""
        if base_url != "" or base_url is not None:
            base_url: str = stream.url.rsplit("/", 1)[0] + "/"
        contents: str = requests.get(stream.url, headers=self.headers).text
        segment_num: int = 1
        self._make_tempdir()
        os.chdir(self.temp_directory)
        for line in contents.split("\n"):
            if not line.startswith("#"):
                with open(f"{self.name}{self.extention_in}", "ab") as f:
                    f.write(self._downloadSegment(base_url+line))
                segment_num += 1

    def _downloadSegment(self, url:str) -> str:
        """Downloads one segment"""
        for tries in range(1,6):
            try:
                return requests.get(url=url, headers=self.headers).content
            except ConnectionError as e:
                print(f"Connection error, trying in 5 seconds... {tries}/5")
                time.sleep(5)
        else:
            raise ConnectionError(e)

    def _convert(self, remove: bool = True) -> None:
        """Converts video file from ``extention_in`` to ``extention_out``"""
        os.chdir(self.temp_directory)
        command = [
            'ffmpeg','-i',
            f"\"{os.path.join(self.temp_directory, self.name+self.extention_in)}\"",
            '-c:v', 'copy','-c:a', 'copy',
            f"\"{os.path.join(self.directory, self.name+self.extention_out)}\""
        ]
        os.system(" ".join(command))
        if remove:
            self._remove_tempdir()

    def _make_tempdir(self) -> None:
        """Makes temporary directory in ``directory``"""
        os.chdir(self.directory)
        os.makedirs(self.name, exist_ok=True)
    
    def _remove_tempdir(self) -> None:
        """Removes temporary directory from ``directory``"""
        os.chdir(self.directory)
        shutil.rmtree(self.temp_directory)
    
    def _valid_name(self, filename) -> str:
        """Returns valid name"""
        invalid_chars = [":", "/", "\\", "|", "?", "*", "<", ">", '"']
        return ''.join(char for char in filename if char not in invalid_chars)
    
    def get_playlist(self) -> None:
        """Downloads playlist"""
        with open(f'{os.path.join(self.directory,"playlist.m3u8")}', "wb") as f:
            f.write(requests.get(self.playlist_url, headers=self.headers).content)

    def get_index(self, index: M3U8Index) -> None:
        """Downloads index"""
        with open(f'{os.path.join(self.directory,f"index {index.resolution}.m3u8")}', "wb") as f:
            f.write(requests.get(index.url, headers=self.headers).content)
