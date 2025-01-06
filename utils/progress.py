from collections import deque
import os
from pathlib import Path

from typing import Literal


class Progress:
    def __init__(self, dir: str = "progress") -> None:
        dir = Path(dir)
        self.set_dir(dir)
        self.load()

    def set_dir(self, dir: str):
        self.progress_dir = dir
        self.history_path = dir.joinpath("history.txt")
        self.queue_path = dir.joinpath("queue.txt")

    def load(self):
        # Prepare history
        if not self.history_path.exists():
            history = []
        else:
            with open(self.history_path, "r") as f_hist:
                history = f_hist.read().split()

        # Prepare queue
        if not self.queue_path.exists():
            queue = deque()
        else:
            with open(self.queue_path, "r") as f_queue:
                queue = f_queue.read().split()

        history, queue = set(history), deque(queue)
        self.history = history
        self.queue = queue
        return self.history, self.queue

    def save(self):
        if not self.progress_dir.is_dir():
            os.makedirs(self.progress_dir, exist_ok=True)

        with open(self.history_path, "w") as f_hist, open(
            self.queue_path, "w"
        ) as f_queue:
            f_hist.writelines("\n".join(self.history))
            f_queue.writelines("\n".join(self.queue))

    def enqueue(self, url: str, side: Literal["left", "right"] = "right"):
        if side == "right":
            self.queue.append(url)
        elif side == "left":
            self.queue.appendleft(url)

    def enqueue_list(self, urls: list[str], side: Literal["left", "right"] = "right"):
        for url in urls:
            self.enqueue(url, side)

    def selectively_enqueue(
        self,
        url: str,
        side: Literal["left", "right"] = "right",
        ignore: Literal["none", "queue", "history"] = "none",
    ):
        assert ignore in ["none", "queue", "history"]
        exclude_set = set()
        if ignore in ["none", "queue"]:
            exclude_set.update(self.history)
        if ignore in ["none", "history"]:
            exclude_set.update(self.queue)

        if url not in exclude_set:
            # Enqueue URLs that are not already in progress or history.
            self.enqueue(url, side=side)

    def selectively_enqueue_list(
        self,
        urls: list[str],
        side: Literal["left", "right"] = "right",
        ignore: Literal["none", "queue", "history"] = "none",
    ):
        assert ignore in ["none", "queue", "history"]
        exclude_set = set()
        if ignore in ["none", "queue"]:
            exclude_set.update(self.history)
        if ignore in ["none", "history"]:
            exclude_set.update(self.queue)

        # Enqueue URLs that are not already in progress or history.
        urls = list(set(urls).difference(exclude_set))
        self.enqueue_list(urls, side=side)

    def next_url(self, pop: bool = True):
        if pop:
            return self.queue.popleft()
        return self.queue[0]

    def add_history(self, url: str):
        self.history.add(url)

    def propagated(self, url: str):
        return url in self.history

    def count_remaining(self):
        return len(self.queue)
