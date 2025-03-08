from .as_csv import SaveAsCSV
from .as_excel import SaveAsExcel
from .save_imgs import SaveImages
from .save_vids import SaveVideos
from .handle_hrefs import HandleHrefs
from .base_step import BaseStep
from pandas import DataFrame
from typing import Sequence, Callable, Any


class Pipeline:
    def __init__(self, *steps: BaseStep) -> None:
        self.steps: list[BaseStep] = [AsDataFrame(), *steps]

    def __call__(self, input: Any) -> Any:
        result = input
        for step in self.steps:
            result = step(result)
        return result

    def add(self, step: Callable[[Any], Any]):
        self.steps.append(step)


class AsDataFrame(BaseStep):
    def __call__(self, data: dict[str, Any]) -> Any:
        try:
            df = DataFrame(data)
        except ValueError:
            df = DataFrame([data])
        return df
