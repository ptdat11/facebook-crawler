from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.remote_connection import LOGGER
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchWindowException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains

from utils import Logger, Progress, LinkExtractor, Cookies
from utils.colors import *
from utils.utils import login, is_logged_in, ordinal, to_bs4
from EC import more_items_loaded
from pipeline import Pipeline

import json
import os
import sys
import time
import logging
from copy import deepcopy
from datetime import datetime
from bs4 import BeautifulSoup
from os.path import join
from urllib.parse import urlparse
from traceback import format_exc
from scipy.stats import weibull_min
from contextlib import contextmanager
from typing import Any, Iterable, Literal

LOGGER.setLevel(logging.CRITICAL)


class BaseCrawler:
    """
    Base class for crawlers
    """

    CRITICAL_EXCEPTIONS = [
        KeyboardInterrupt,
        NotImplementedError,
        NoSuchWindowException,
        WebDriverException,
    ]

    def __init__(
        self,
        chromedriver_path: str,
        navigate_link_extractor: LinkExtractor,
        parse_link_extractor: LinkExtractor,
        crawler_dir: str,
        data_pipeline: Pipeline,
        user: str,
        secrets_file: str,
        cookies_save_dir: str,
        error_screenshot_dir: str | None = None,
        headless: bool = True,
        sleep_weibull_lambda: float = 10.0,
        max_loading_wait: float = 90,
        max_error_trials: int = 5,
        name: str = "Crawler",
    ):
        self.logger = Logger(name)
        self.logger.info("Initializing...")
        self.navigate_link_extractor = navigate_link_extractor
        self.parse_link_extractor = parse_link_extractor
        self.set_crawler_dir(crawler_dir=crawler_dir, data_pipeline=data_pipeline)
        self.progress = Progress(dir=join(crawler_dir, "progress"))
        self.progress.load()
        self.user = user
        self.secret_file = secrets_file
        self.cookies = Cookies(user=user, save_dir=cookies_save_dir)
        self.error_screenshot_dir = error_screenshot_dir

        self.headless = headless
        self.sleep_weibull_lambda = sleep_weibull_lambda
        self.max_loading_wait = max_loading_wait
        self.max_error_trials = max_error_trials

        self.chromedriver_path = chromedriver_path
        self.driver_service = Service(chromedriver_path)
        self.driver_options = webdriver.ChromeOptions()

        # Options
        ## Disable image loading
        self.driver_options.add_argument("--blink-settings=imagesEnabled=false")
        ## Disable notifications
        self.driver_options.add_argument("--disable-notifications")
        self.driver_options.add_argument("disable-infobars")
        self.driver_options.add_argument("--disable-cache")
        ## Enable headless, or else detach mode
        if headless:
            self.driver_options.add_argument("--headless")
        else:
            self.driver_options.add_experimental_option("detach", True)
            self.driver_options.add_argument("--ignore-certificate-errors")
        
        self.no_cookie_options = deepcopy(self.driver_options)
        self.driver_options.add_argument("--incognito")

    def on_start(self):
        # raise NotImplementedError("Crawler's on_start method is not implemented")
        pass

    def on_exit(self):
        # raise NotImplementedError("Crawler's on_exit method is not implemented")
        pass

    def on_parse_error(self):
        # raise NotImplementedError("Crawler's on_parse_error method is not implemented")
        pass

    def on_parse_complete(self, data):
        return data

    def parse(self) -> Iterable[dict[str, Any]]:
        raise NotImplementedError("Crawler's parse method is not implemented")

    def new_tab(self, url: str):
        self.chrome.execute_script("window.open('about:blank', '_blank');")
        self.chrome.switch_to.window(self.chrome.window_handles[-1])
        self.chrome.get(url)
        self.logger.info(f"Opened new tab to {grey(url)}")

    def close_all_new_tabs(self):
        for handle in self.chrome.window_handles:
            if handle == self.main_tab:
                continue
            self.chrome.switch_to.window(handle)
            self.chrome.close()
        self.chrome.switch_to.window(self.main_tab)

    def set_pipeline_path_format(self, **format_kwargs):
        for step in self.data_pipeline.steps:
            step.set_path_format(**format_kwargs)

    def set_crawler_dir(self, crawler_dir: str, data_pipeline: Pipeline):
        self.crawler_dir = crawler_dir
        self.data_pipeline = data_pipeline
        self.set_pipeline_path_format(crawler_dir=crawler_dir)

    def sleep(self, _lambda: float = None):
        if _lambda is None:
            _lambda = self.sleep_weibull_lambda
        sleep_second = weibull_min.rvs(10, loc=0, scale=_lambda)
        time.sleep(sleep_second)

    def wait_DOM(self):
        self.chrome.implicitly_wait(self.max_loading_wait)

    def start_driver(self):
        self.chrome = webdriver.Chrome(
            service=self.driver_service, options=self.driver_options
        )
        self.main_tab = self.chrome.current_window_handle
        self.logger.info(f"Driver started")
        self.action = ActionChains(self.chrome)
        self.wait = WebDriverWait(self.chrome, self.max_loading_wait)

        self.no_cookie_chrome = None

    def save_cookies(self):
        self.cookies.save(self.chrome.get_cookies())

    def load_cookies(self):
        self.chrome.get("https://www.facebook.com")
        for cookie in self.cookies.load():
            self.chrome.add_cookie(cookie)

    def save_progress(self):
        self.progress.save()

    def load_progress(self):
        self.progress.load()
    
    def scroll_into_view(
        self,
        element: WebElement,
        offset: tuple | Literal["middle"] = "middle",
        sleep: float = 0,
    ):
        self.chrome.execute_script("arguments[0].scrollIntoView(true);", element)
        self.sleep(sleep)
        if offset == "middle":
            self.action.move_to_element(element).perform()
        elif isinstance(offset, tuple):
            print(offset[0], offset[1])
            self.action.move_to_element_with_offset(
                element, offset[0], offset[1]
            ).perform()
        
    def click(
        self,
        element: WebElement,
        offset: tuple | Literal["middle"] = "middle",
        sleep: float = 0,
    ):
        self.scroll_into_view(element, offset=offset, sleep=sleep)
        element.click()
    
    def remove_element(self, element: WebElement):
        self.chrome.execute_script("arguments[0].remove();", element)

    def ensure_logged_in(self):
        self.logger.info("Ensuring user logging in")
        if self.cookies.exists():
            self.logger.info("Found user's credentials cached as cookies")
            self.load_cookies()
            return

        url = urlparse(self.chrome.current_url)
        domain_name = (
            ".".join(url.hostname.split(".")[-2:]) if url.hostname is not None else None
        )
        if domain_name != "https://facebook.com":
            self.chrome.get("https://www.facebook.com")
        if is_logged_in(self.chrome):
            self.logger.info("User is already logged in inside browser")
            return

        self.logger.info(
            f"No existing credentials found, manuallly signing in for {self.user}"
        )
        with open(self.secret_file, "r") as f:
            user_info = json.load(f)[self.user]
        login(
            self.chrome, username=user_info["username"], password=user_info["password"]
        )

    def extract_urls_from_current_page(self):
        url = self.chrome.current_url
        html = self.chrome.page_source

        new_nav_urls = self.navigate_link_extractor.extract(html)
        new_parse_urls = self.parse_link_extractor.extract(html)
        try:
            new_nav_urls.remove(url)
        except:
            pass
        try:
            new_parse_urls.remove(url)
        except:
            pass

        self.logger.info(f"Enqueuing {len(new_nav_urls)} new navigation URLs")
        self.progress.selectively_enqueue_list(new_nav_urls, ignore="history")

        self.logger.info(
            f"Selectively enqueuing {len(new_parse_urls)} new parsing URLs"
        )
        self.progress.selectively_enqueue_list(new_parse_urls)
    
    def start(self, start_url: str):
        self.start_driver()
        self.on_start()

        self.ensure_logged_in()
        self.save_cookies()
        self.logger.info("Saved/Refreshed cookies")

        if len(self.progress.queue) == 0 or self.progress.queue[0] != start_url:
            self.progress.selectively_enqueue(start_url, side="left", ignore="history")
        err_trial = 0

        while (
            self.progress.count_remaining() > 0 and err_trial <= self.max_error_trials
        ):
            try:
                exc_type = None
                url = self.progress.next_url()

                # If URL is for navigation
                if self.navigate_link_extractor.match(url) or url == start_url:
                    self._handle_navigation_url(url)
                # If URL is for parsing
                if self.parse_link_extractor.match(url):
                    self._handle_parse_url(url)

                self.progress.add_history(url)
                err_trial = 0
                self.sleep()
            except:
                # Save driver's screen at the erroneous moment
                if self.error_screenshot_dir:
                    os.makedirs(self.error_screenshot_dir, exist_ok=True)
                    self.chrome.save_screenshot(
                        os.path.join(self.error_screenshot_dir, f"{datetime.now()}.png")
                    )

                err_trial += 1
                # Logging out error
                exc_type, value, tb = sys.exc_info()
                self.logger.error(
                    f"Restore {grey(url)} to queue due to error: \n{red(exc_type.__name__)}: {value}\n{format_exc()}"
                )
                # If this url hasn't been crawled successfully
                if not self.progress.propagated(url):
                    # Re-append URL to queue
                    self.progress.enqueue(url, "left")

                self.on_parse_error()
                # self.close_all_new_tabs()
                # If error due to no abstract method implementation, stop retrying
                if exc_type in BaseCrawler.CRITICAL_EXCEPTIONS:
                    break
                if err_trial <= err_trial:
                    self.logger.warning(
                        f"Attempting {bold(ordinal(err_trial))} retrial..."
                    )
                self.sleep()

        if exc_type is not None:
            self.logger.error(f"Closing driver due to an error occured...")
        elif err_trial > self.max_error_trials:
            self.logger.error(
                "Maximum number of trials upon errors exceeded, exitting..."
            )
        elif self.progress.count_remaining() == 0:
            self.logger.info("Closing driver due to no URL left in queue...")
        self.save_progress()
        self.on_exit()
        # self.chrome.quit()

    def _handle_navigation_url(self, url: str):
        self.logger.info(f"Matched as URL for {bold('navigation')}: {grey(url)}")
        self.chrome.get(url)
        self.wait_DOM()

        self.extract_urls_from_current_page()

    def _handle_parse_url(self, url: str):
        self.logger.info(f"Matched as URL for {bold('parsing')}: {grey(url)}")
        self.new_tab(url)
        self.wait_DOM()

        for data in self.parse():
            data = self.on_parse_complete(data)
            self.data_pipeline(data)

        # self.close_all_new_tabs()

    def page_source_soup(self):
        return BeautifulSoup(self.chrome.page_source, "lxml")

    def delete_all_cookies(self):
        self.chrome.execute(
            "executeCdpCommand",
            {"cmd": "Network.clearBrowserCookies", "params": {}}
        )
    
    def clean_memory(self):
        self.chrome.execute_cdp_cmd('Network.clearBrowserCache', {})
        self.chrome.execute_script("window.localStorage.clear();")
        self.chrome.execute_script("window.sessionStorage.clear();")
        self.chrome.execute_script('indexedDB.databases().then(dbs => dbs.forEach(db => indexedDB.deleteDatabase(db.name)));')
        self.chrome.execute_script("window.gc && window.gc();")
    
    @contextmanager
    def new_chrome_no_cookies(self, url: str | None = None, quit_on_done: bool = False):
        # current_tab = self.chrome.current_window_handle
        # self.chrome.switch_to.new_window("tab")
        # self.delete_all_cookies()
        # self.chrome.get(url)
        if not self.no_cookie_chrome:
            self.no_cookie_chrome = webdriver.Chrome(
                service=Service(self.chromedriver_path), options=self.no_cookie_options
            )
        if url:
            self.no_cookie_chrome.get(url)
            self.logger.info(f"Opened new Chrome driver to {grey(url)}")
            self.wait_DOM()
            self.wait.until(EC.presence_of_element_located((By.XPATH, "html")))

        try:
            yield self.no_cookie_chrome
        finally:
            self.no_cookie_chrome.execute(
                "executeCdpCommand",
                {"cmd": "Network.clearBrowserCookies", "params": {}}
            )
            self.no_cookie_chrome.execute_cdp_cmd('Network.clearBrowserCache', {})
            self.no_cookie_chrome.execute_script("window.localStorage.clear();")
            self.no_cookie_chrome.execute_script("window.sessionStorage.clear();")
            self.no_cookie_chrome.execute_script('indexedDB.databases().then(dbs => dbs.forEach(db => indexedDB.deleteDatabase(db.name)));')
            self.no_cookie_chrome.execute_script("window.gc && window.gc();")
            self.no_cookie_chrome.get("about:blank")
            
            if quit_on_done:
                self.no_cookie_chrome.quit()
                self.no_cookie_chrome = None