from os import PathLike
from selenium.webdriver.common.by import By
from selenium.webdriver import Chrome
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement

import urllib.parse
import bs4
import time
import hashlib
import sys
from html import unescape
from unittest.mock import patch
from contextlib import contextmanager
from lxml import etree


class FormatablePath(PathLike):
    def __init__(self, path: str, **format_kwargs) -> None:
        self.path = path
        self.format_kwargs = dict(**format_kwargs)

    def __str__(self) -> str:
        return self.path.format(**self.format_kwargs)

    def __repr__(self) -> str:
        return str(self)

    def __fspath__(self):
        return str(self)


def is_logged_in(driver: Chrome):
    """Function to check if user is logged in"""
    cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
    return "c_user" in cookies


def login(driver: Chrome, username: str, password: str):
    """Function to login to facebook"""
    username_box = driver.find_element(By.CSS_SELECTOR, "input[id=email]")
    username_box.send_keys(username)

    password_box = driver.find_element(By.CSS_SELECTOR, "input[id=pass]")
    password_box.send_keys(password)

    login_box = driver.find_element(By.CSS_SELECTOR, "button[name=login]")
    login_box.click()

    time.sleep(5)
    WebDriverWait(driver, timeout=10).until(
        EC.presence_of_element_located((By.ID, "facebook"))
    )


def unicode_escape_url(url: str):
    r"""
    Example: `https:\/\/scontent.fsgn5-9.fna.fbcdn.net\/o1\/v\/t2\/f2\/m366\/AQOwqM2sgT0_ryPOz\u00253D\u00253D` -> `https://scontent.fsgn5-9.fna.fbcdn.net/o1/v/t2/f2/m366/AQOwqM2sgT0_ryPO%3D%3D`
    """
    decoded_url = url.replace(r"\/", "/").encode().decode('unicode_escape')
    final_url = urllib.parse.unquote(decoded_url)
    return final_url


def ordinal(n: int):
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = ["th", "st", "nd", "rd", "th"][min(n % 10, 4)]
    return str(n) + suffix


def sha256(string: str):
    return hashlib.sha256(string.encode()).hexdigest()


def to_bs4(element: WebElement):
    return bs4.BeautifulSoup(element.get_attribute("outerHTML"), "lxml")

def to_etree(element: WebElement) -> etree.Element:
    return etree.HTML(element.get_attribute("outerHTML"))

def write_element(self, dst: str, element: WebElement):
        soup = to_bs4(element)
        try:
            with open(dst, "w") as f:
                f.write(unescape(soup.__str__()))
        except:
            print(f"Cannot write \n{soup}\n to {dst}")

@contextmanager
def tqdm_output(tqdm, write=sys.stderr.write):
    def wrapper(message):
        if message != '\n':
            tqdm.clear()
        write(message)
        if '\n' in message:
            tqdm.display()

    with patch('sys.stdout', sys.stderr), patch('sys.stderr.write', wrapper):
        yield tqdm