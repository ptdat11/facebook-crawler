from .base_step import BaseStep

import re
from pandas import DataFrame
from typing import Any, Literal, Callable


class HandleHrefs(BaseStep):
    def __init__(
        self,
        action: Literal["ignore", "keep_content", "replace"] = "ignore",
        replace_predicate: Callable[[str, str], str] = lambda content, url: "<link>",
    ) -> None:
        super().__init__()
        self.action = action
        self.replace_predicate = replace_predicate

    @staticmethod
    def _keep_content_fn(value: Any):
        if isinstance(value, str):
            result = re.sub(r"href\(([^,]+), [^\)]+\)", r"\1", value)
            return result
        return value

    @staticmethod
    def _replace_fn(value: Any, predicate: Callable[[str, str], str]):
        if isinstance(value, str):
            hrefs = re.findall(r"href\(([^,]+), ([^\)]+)\)", value)
            replace_dict = {
                f"href({content}, {url})": predicate(content, url)
                for content, url in hrefs
            }
            result = re.sub(
                r"href\([^,]+, [^\)]+\)",
                repl=lambda m: replace_dict.get(m.group(), None),
                string=value,
            )
            return result
        return value

    def __call__(self, df: DataFrame) -> DataFrame:
        if self.action == "ignore":
            return df
        elif self.action == "keep_content":
            return df.map(HandleHrefs._keep_content_fn)
        elif self.action == "replace":
            return df.map(HandleHrefs._replace_fn, self.replace_predicate)
