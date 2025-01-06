from utils import FormatablePath
from .base_step import BaseStep

import os
from os.path import join
from pandas import DataFrame
from pathlib import Path
from typing import Any


class SaveAsExcel(BaseStep):
    def __init__(self, dst_dir: str, **excel_kwargs) -> None:
        self.dst_dir = FormatablePath(dst_dir)
        self.dst_csv = FormatablePath(join(dst_dir, "data.xlsx"))
        self.excel_kwargs = excel_kwargs

    def __call__(self, df: DataFrame) -> Any:
        if df.empty:
            return df

        os.makedirs(self.dst_dir, exist_ok=True)
        df.to_excel(
            self.dst_csv, header=not os.path.exists(self.dst_csv), **self.excel_kwargs
        )

        return df
