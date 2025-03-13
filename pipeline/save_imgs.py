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
        id_col: str | None = None,
        img_save_dir_name: str = "imgs",
    ) -> None:
        self.img_url_col = img_url_col
        self.save_dir = FormatablePath(save_dir)
        self.id_col = id_col
        self.img_save_dir_name = img_save_dir_name

        if id_col is None:
            self.generated_id = 0

    def save_img(self, url: str):
        img_name = Path(urlparse(url).path).name
        img_dir = join(self.save_dir, self.img_save_dir_name)
        img_path = join(img_dir, img_name)

        if not os.path.exists(img_dir):
            os.makedirs(img_dir, exist_ok=True)

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

        # Create new DF for image data
        copied_cols = [self.id_col, self.img_url_col] if self.id_col is not None \
                    else [self.img_url_col]
        result_df = df[copied_cols].map(lambda v: {"": None}.get(v, v)).dropna(subset=self.img_url_col)
        if not result_df.empty:
            result_df[self.img_url_col] = result_df[self.img_url_col].map(str.split)
            result_df = result_df.explode(self.img_url_col, ignore_index=True)
            # Download images on the fly
            result_df["name"] = result_df[self.img_url_col].map(self.save_img)
            if self.id_col is None:
                result_df["id"] = range(self.generated_id, self.generated_id + result_df.shape[0])
                self.generated_id += result_df.shape[0]

            # Save DF as CSV
            os.makedirs(self.save_dir, exist_ok=True)
            csv_path = os.path.join(self.save_dir, f"{self.img_save_dir_name}.csv")
            result_df.to_csv(
                csv_path,
                index=False,
                mode="a",
                header=not os.path.exists(csv_path),
            )

        df["has_image"] = df[self.img_url_col].notna() & (df[self.img_url_col] != "")
        df.drop(columns=self.img_url_col, inplace=True)
        return df
