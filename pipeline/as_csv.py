from utils import FormatablePath
from .base_step import BaseStep

import os
from os.path import join
from pandas import DataFrame
from pathlib import Path
from typing import Any


class SaveAsCSV(BaseStep):
    def __init__(self, dst_dir: str, **csv_kwargs) -> None:
        self.dst_dir = FormatablePath(dst_dir)
        self.dst_csv = FormatablePath(join(dst_dir, "data.csv"))
        self.csv_kwargs = csv_kwargs

    def __call__(self, df: DataFrame) -> Any:
        if df.empty:
            return df

        os.makedirs(self.dst_dir, exist_ok=True)
        df.to_csv(
            self.dst_csv,
            index=False,
            mode="a",
            header=not os.path.exists(self.dst_csv),
            **self.csv_kwargs
        )

        return df
