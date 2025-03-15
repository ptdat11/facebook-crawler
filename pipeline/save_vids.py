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
        id_col: str | None = None,
        vid_save_dir_name: str = "vids",
    ) -> None:
        self.vid_url_col = vid_url_col
        self.audio_url_col = audio_url_col
        self.save_dir = FormatablePath(save_dir)
        self.id_col = id_col
        self.vid_save_dir_name = vid_save_dir_name

        if id_col is None:
            self.generated_id = 0

    def save_vid(self, vid_url: str, audio_url: str):
        vid_name = Path(urlparse(vid_url).path).name.strip(".mp4")

        vid_dir = join(self.save_dir, self.vid_save_dir_name, vid_name)
        vid_path = join(vid_dir, "video.mp4")

        if not os.path.exists(vid_dir):
            os.makedirs(vid_dir, exist_ok=True)

        if not os.path.exists(vid_path):
            vid_data = requests.get(vid_url).content
            with open(vid_path, "wb") as f:
                f.write(vid_data)
        
        if audio_url != "<not_found>":
            audio_path = join(vid_dir, "audio.mp3")
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

        # Create new DF for video data
        copied_cols = [self.id_col, self.vid_url_col, self.audio_url_col] if self.id_col is not None \
                    else [self.vid_url_col, self.audio_url_col]
        result_df = df[copied_cols].map(lambda v: {"": None}.get(v, v)).dropna(subset=[self.vid_url_col, self.audio_url_col])
        if not result_df.empty:
            result_df[[self.vid_url_col, self.audio_url_col]] = result_df[[self.vid_url_col, self.audio_url_col]].map(str.split)
            result_df = result_df.explode([self.vid_url_col, self.audio_url_col], ignore_index=True)
            # Download videos on the fly
            result_df["name"] = [
                self.save_vid(vid_url, audio_url) 
                for vid_url, audio_url in result_df[[self.vid_url_col, self.audio_url_col]].values
            ]
            result_df[self.audio_url_col] = result_df[self.audio_url_col].map(lambda url: {"<not_found>": None}.get(url, url))
            
            if self.id_col is None:
                result_df["id"] = range(self.generated_id, self.generated_id + result_df.shape[0])
                self.generated_id += result_df.shape[0]

            # Save DF as CSV
            os.makedirs(self.save_dir, exist_ok=True)
            csv_path = os.path.join(self.save_dir, f"{self.vid_save_dir_name}.csv")
            result_df.to_csv(
                csv_path,
                index=False,
                mode="a",
                header=not os.path.exists(csv_path),
            )

        df["has_video"] = df[self.vid_url_col].notna() & (df[self.vid_url_col] != "")
        df.drop(columns=[self.vid_url_col, self.audio_url_col], inplace=True)
        return df
