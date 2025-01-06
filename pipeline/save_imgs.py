from .base_step import BaseStep
from utils.utils import FormatablePath

import os
from urllib.parse import urlparse
from os.path import join
import requests
from pandas import DataFrame
from pathlib import Path
from typing import Any


class SaveImages(BaseStep):
    def __init__(
        self,
        save_dir: str,
        img_url_col: str,
    ) -> None:
        self.img_url_col = img_url_col
        self.save_dir = FormatablePath(save_dir)

    def save_img(self, url: str):
        img_name = Path(urlparse(url).path).name
        img_path = join(self.save_dir, img_name)

        if not os.path.exists(img_path):
            img_data = requests.get(url).content
            with open(img_path, "wb") as f:
                f.write(img_data)

        return img_name

    def __call__(
        self,
        df: DataFrame,
    ) -> Any:
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir, exist_ok=True)

        for row in df.itertuples():
            img_files = []
            imgs = getattr(row, self.img_url_col).split()
            for i, url in enumerate(imgs):
                img_file = self.save_img(url=url)
                img_files.append(img_file)

            df.loc[row.Index, "image_names"] = "   ".join(img_files)

        return df
