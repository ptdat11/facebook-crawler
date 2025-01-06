import pickle
import pathlib
import os


class Cookies:
    def __init__(self, user: str, save_dir: str = "./cookies/") -> None:
        save_dir = pathlib.Path(save_dir)
        self.save_dir = save_dir
        self.user = user
        self.cookies_path = save_dir.joinpath(f"{user}.pkl")

    def save(self, cookies: list[dict]):
        if not self.save_dir.is_dir():
            os.mkdir(self.save_dir)

        with open(self.cookies_path, "wb") as f:
            pickle.dump(cookies, f)

    def load(self):
        if not self.cookies_path.exists():
            return []

        with open(self.cookies_path, "rb") as f:
            cookies = pickle.load(f)
            return cookies

    def exists(self):
        return self.cookies_path.exists()
