from .base_step import BaseStep
from utils.utils import FormatablePath

import os
from urllib.parse import urlparse
from os.path import join
import requests
from pandas import DataFrame
from pathlib import Path
from typing import Any


class SaveVideos(BaseStep):
    def __init__(
        self,
        save_dir: str,
        vid_url_col: str,
        audio_url_col: str,
    ) -> None:
        self.vid_url_col = vid_url_col
        self.audio_url_col = audio_url_col
        self.save_dir = FormatablePath(save_dir)

    def save_vid(self, vid_url: str, audio_url: str):
        vid_name = Path(urlparse(vid_url).path).name
        vid_path = join(self.save_dir, vid_name, "video.mp4")
        audio_path = join(self.save_dir, vid_name, "audio.mp3")

        if not os.path.exists(join(self.save_dir, vid_name)):
            os.makedirs(join(self.save_dir, vid_name), exist_ok=True)

        if not os.path.exists(vid_path):
            vid_data = requests.get(vid_url).content
            with open(vid_path, "wb") as f:
                f.write(vid_data)
        
        if not os.path.exists(audio_path):
            audio_data = requests.get(audio_url).content
            with open(audio_path, "wb") as f:
                f.write(audio_data)

        return vid_name

    def __call__(
        self,
        df: DataFrame,
    ) -> Any:
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir, exist_ok=True)

        for row in df.itertuples():
            vid_names = []
            vids = getattr(row, self.vid_url_col).split()
            audios = getattr(row, self.audio_url_col).split()
            for i, (vid_url, audio_url) in enumerate(zip(vids, audios)):
                vid_name = self.save_vid(vid_url, audio_url)
                vid_names.append(vid_name)

            df.loc[row.Index, "video_names"] = "   ".join(vid_names)

        return df
