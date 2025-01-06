from typing import Any
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver import Chrome


class more_items_loaded:
    def __init__(self, posts_locator: tuple, current_count: int = 0) -> None:
        self.posts_locator = posts_locator
        self.orig_post_count = current_count

    def __call__(self, driver: Chrome):
        by, xpath = self.posts_locator
        current_post_count = len(driver.find_elements(by, xpath))

        return current_post_count > self.orig_post_count
