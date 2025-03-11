from utils import FormatablePath
from .base_step import BaseStep

import os
from os.path import join
from pandas import DataFrame
from pathlib import Path
from typing import Any


class SaveAsCSV(BaseStep):
    def __init__(self, save_dir: str, **csv_kwargs) -> None:
        self.save_dir = FormatablePath(save_dir)
        self.csv_path = FormatablePath(join(save_dir, "data.csv"))
        self.csv_kwargs = csv_kwargs

    def __call__(self, df: DataFrame) -> Any:
        if df.empty:
            return df

        os.makedirs(self.save_dir, exist_ok=True)
        df.to_csv(
            self.csv_path,
            index=False,
            mode="a",
            header=not os.path.exists(self.csv_path),
            **self.csv_kwargs
        )

        return df
