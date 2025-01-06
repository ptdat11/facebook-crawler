from os import PathLike
from selenium.webdriver.common.by import By
from selenium.webdriver import Chrome
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement

import bs4
import time


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


def ordinal(n: int):
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = ["th", "st", "nd", "rd", "th"][min(n % 10, 4)]
    return str(n) + suffix


def to_bs4(element: WebElement):
    return bs4.BeautifulSoup(element.get_attribute("outerHTML"), "lxml")
