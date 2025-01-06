from typing import Any, Sequence
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver import Chrome
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import re
import traceback
import sys
import bs4
from pathlib import Path
from ..base_crawler import BaseCrawler
from EC import more_items_loaded
from utils.parsing import parse_post_date, parse_text_from_element
from utils.utils import to_bs4, ordinal
from utils.colors import *

from urllib.parse import urlparse, parse_qs
from html import unescape
from datetime import datetime
from typing import Literal
from psutil import virtual_memory
from tqdm import tqdm


class Crawler(BaseCrawler):
    posts_xpath = "(//div[@class='x9f619 x1n2onr6 x1ja2u2z xeuugli xs83m0k xjl7jj x1xmf6yo x1emribx x1e56ztr x1i64zmx x19h7ccj xu9j1y6 x7ep2pv']/div)[last()]/div//div[@class='x1yztbdb x1n2onr6 xh8yej3 x1ja2u2z']"
    content_on_hover_xpath = (
        "(//div[@class='x78zum5 xdt5ytf x1n2onr6 xat3117 xxzkxad']/div)[2]/div"
    )

    class PostCollectCriterion:
        def __init__(
            self,
            criterion: Literal["elapsed_minutes", "n_posts", "post_time"],
            threshold: float | int | datetime,
        ) -> None:
            self.criterion = criterion
            self.threshold = threshold
            self.reset()

        def reset(self):
            if self.criterion == "elapsed_minutes":
                self.start = datetime.now()
                self.progress = 0.0
            elif self.criterion == "n_posts":
                self.progress = 0
            elif self.criterion == "post_time":
                self.progress = datetime.now()

        def update_progress(self, driver: Chrome):
            if self.criterion == "elapsed_minutes":
                self.progress = (datetime.now() - self.start).total_seconds() / 60
            elif self.criterion == "n_posts":
                self.progress = len(driver.find_elements(By.XPATH, Crawler.posts_xpath))
            elif self.criterion == "post_time":
                datetime_div = driver.find_element(
                    By.XPATH, Crawler.content_on_hover_xpath
                )
                last_post_datetime_a = driver.find_element(
                    By.XPATH,
                    f"(({Crawler.posts_xpath})[last()]//h2/../../../../div)[2]//a",
                )
                self.action.move_to_element(last_post_datetime_a).perform()
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (
                            By.XPATH,
                            "(//div[@class='x78zum5 xdt5ytf x1n2onr6 xat3117 xxzkxad']/div)[2]/div/div",
                        )
                    )
                )
                soup = to_bs4(datetime_div)
                raw_datetime = soup.text
                self.progress = parse_post_date(raw_datetime, lang=self.language)

        def condition_met(self):
            if self.criterion == "elapsed_minutes":
                return self.progress >= self.threshold
            elif self.criterion == "n_posts":
                return self.progress >= self.threshold
            elif self.criterion == "post_time":
                return self.progress <= self.threshold

    def __init__(
        self,
        page_id: str,
        post_collect_threshold: float | int | datetime,
        post_collect_criterion: Literal[
            "elapsed_minutes", "n_posts", "post_time"
        ] = "n_posts",
        max_ram_percentage: float = 0.8,
        language: Literal["vi", "en"] = "vi",
        theme: Literal["light", "dark"] = "light",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs, name="Page Crawler")

        self.post_collect_criteria = Crawler.PostCollectCriterion(
            criterion=post_collect_criterion,
            threshold=post_collect_threshold,
        )
        self.max_ram_percentage = max_ram_percentage
        self.page_id = page_id
        self.language = language
        self.theme = theme
        self.set_pipeline_path_format(page_id=page_id)

    def on_parse_error(self):
        self.post_collect_criteria.reset()

    def parse(self):
        self.remove_header()
        n_scraped_posts = 0

        with tqdm(
            total=round(virtual_memory().total / 1024**3, ndigits=2),
            desc="RAM Usage (GB)",
        ) as bar:
            # Scroll though page's feed
            while (
                ram_usage := virtual_memory()
            ).percent / 100 < self.max_ram_percentage and not (
                met := self.post_collect_criteria.condition_met()
            ):
                bar.n = round(ram_usage.used / 1024**3, ndigits=2)
                bar.refresh()

                self.chrome.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight)"
                )
                WebDriverWait(self.chrome, self.max_loading_wait).until(
                    more_items_loaded(
                        posts_locator=(By.XPATH, Crawler.posts_xpath),
                        current_count=len(self.get_loaded_posts()),
                    )
                )
                self.post_collect_criteria.update_progress(self.chrome)

                for i, post_div in enumerate(
                    self.get_loaded_posts(start=n_scraped_posts + 1, stop=-1),
                    start=n_scraped_posts + 1,
                ):
                    self.scroll_into_view(post_div, point_cursor=False, sleep=1)
                    # Check if story
                    # profile_div = to_bs4(
                    #     self.chrome.find_element(
                    #         By.XPATH,
                    #         f"({Crawler.posts_xpath})[{i}]",
                    #     )
                    # )
                    # if (
                    #     len(profile_div.find_all("a")) > 0
                    #     and "aria-label" in profile_div.find("a").attrs
                    # ):
                    #     self.logger.info(
                    #         f"Found {ordinal(i)} post as story, skipping..."
                    #     )
                    #     continue
                    if to_bs4(post_div).find("a")["href"].startswith("/reel"):
                        continue
                    # Check if update avatar
                    if to_bs4(post_div).find(
                        "img", {"data-imgperflogname": "feedCoverPhoto"}
                    ):
                        self.logger.info(
                            f"Found {ordinal(i)} post as avatar, skipping..."
                        )
                        continue

                    try:
                        post = self.parse_post(i, post_div)
                        yield post
                    except Exception as e:
                        exc_type, value, tb = sys.exc_info()
                        self.logger.warning(
                            f"Skipping {ordinal(i)} post: {red(exc_type.__name__)}: {value}\n{traceback.format_exc()}"
                        )
                        continue

                    n_scraped_posts += 1
                    bar.set_postfix_str(f"# Scraped posts: {n_scraped_posts}")
                self.sleep()

        if met:
            self.logger.info(
                f"Post collect stopping criteria has met with threshold of {self.post_collect_criteria.threshold}"
            )

    def remove_header(self):
        for rm_xpath in [
            "(//div[@class='x9f619 x1n2onr6 x1ja2u2z x78zum5 xdt5ytf xeuugli x1r8uery x1iyjqo2 xs83m0k x1swvt13 x1pi30zi xqdwrps x16i7wwg x1y5dvz6'])[3]",
            "//div[@role='banner']",
            "//div[@class='x9f619 x1ja2u2z x1xzczws x7wzq59']",
        ]:
            to_be_removed = self.chrome.find_element(By.XPATH, rm_xpath)
            self.chrome.execute_script("arguments[0].remove();", to_be_removed)

    def get_loaded_posts(self, start: int = 1, stop: int = -1):
        if stop < 0:
            stop = f"last(){stop}"
        return self.chrome.find_elements(
            By.XPATH,
            f"({Crawler.posts_xpath})[position() >= {start} and position() <= {stop}]",
        )

    def parse_post(self, i: int, post_div: WebElement):
        hover_content_div = self.chrome.find_element(
            By.XPATH, Crawler.content_on_hover_xpath
        )

        post_content_divs = self.chrome.find_element(
            By.XPATH,
            f"({Crawler.posts_xpath})[{i}]/descendant::div[@class='html-div xdj266r x11i5rnm xat24cr x1mh8g0r xexx8yu x4uap5 x18d9i69 xkhd6sd']",
        ).find_elements(By.XPATH, f"./div/div/div")

        # Profile
        profile_div = post_content_divs[1].find_element(
            By.XPATH,
            f"({Crawler.posts_xpath})[{i}]/descendant::div[@data-ad-rendering-role='profile_name']",
        )

        # Content
        content_div = post_content_divs[2]
        num_content_modalities = 0
        for content in content_div.find_elements(By.XPATH, "div"):
            trans_text = {"vi": "Dịch bài viết này", "en": "See translation"}
            if content.text != trans_text[self.language]:
                num_content_modalities += 1

        text_content_div = content_div.find_elements(
            By.XPATH, "./descendant::div[@data-ad-comet-preview='message']"
        )
        text_content_div = text_content_div[0] if len(text_content_div) > 0 else None

        if (
            num_content_modalities == 2
            and text_content_div is not None
            or num_content_modalities == 1
            and text_content_div is None
        ):
            visual_content_div = post_content_divs[2].find_element(
                By.XPATH, "(./div)[last()]"
            )
        else:
            visual_content_div = None

        # Ensure date element appears

        # Ensure post's text content showing full version
        see_more_text = {"vi": "Xem thêm", "en": "See more"}
        if (
            to_bs4(content_div).find(
                "div", attrs={"role": "button"}, string=see_more_text[self.language]
            )
            is not None
        ):
            show_more_btn = content_div.find_element(
                By.XPATH,
                f"./descendant::div[@role='button' and text()='{see_more_text[self.language]}']",
            )
            self.action.move_to_element(show_more_btn).click(show_more_btn).pause(
                0.5
            ).move_to_element(post_div).perform()

        post_datetime_a = profile_div.find_element(By.XPATH, "(../../../div)[2]//a")
        self.scroll_into_view(post_datetime_a, point_cursor=True, sleep=0.5)

        post_raw_url = post_datetime_a.get_attribute("href")
        if "videos" in post_raw_url:
            post_id = re.search(r"videos/(\d+)", post_raw_url).group(1)
        else:
            post_id = parse_qs(urlparse(post_raw_url).query)["story_fbid"][0]

        post_link = f"https://www.facebook.com/{post_id}"
        # post_link = (
        #     re.search(
        #         r"^https://www\.facebook\.com/[^/]+/[^/]+/[^\?\s]+\?",
        #         post_datetime_a.get_attribute("href"),
        #     )
        #     .group(0)
        #     .strip("/?")
        # )

        caption = (
            parse_text_from_element(text_content_div)
            if text_content_div is not None
            else ""
        )
        caption = unescape(re.sub(r"href\(, [^\)]+\)", "", caption).strip())
        visual_soup = (
            to_bs4(visual_content_div) if visual_content_div is not None else None
        )
        is_post_image = (
            visual_soup.find("img") is not None
            and "data-visualcompletion" not in visual_soup.find("img").parent.attrs
            if visual_soup is not None
            else False
        )
        is_post_video = (
            visual_soup.find("div", {"role": "presentation"}) is not None
            if visual_soup is not None
            else False
        )

        if is_post_image:
            img_urls = self.get_image_urls(visual_content_div=visual_content_div)
        else:
            img_urls = []

        return {
            "post_url": post_link,
            "caption": caption,
            "img_urls": "   ".join(img_urls),
            "has_video": is_post_video,
            "crawl_time": datetime.now(),
        }

    def get_image_urls(self, visual_content_div: WebElement):
        first_img = visual_content_div.find_element(By.XPATH, ".//img")
        # If the post has clickable telephone
        anchor = first_img.find_element(By.XPATH, "./ancestor::a")
        self.scroll_into_view(anchor, point_cursor=True, sleep=0.1)
        if to_bs4(anchor).find("a", {"href": re.compile(r"^tel")}):
            return [first_img.get_attribute("src")]

        # Else
        self.action.move_to_element(first_img).click(first_img).perform()
        WebDriverWait(self.chrome, self.max_loading_wait).until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    f"//div[@class='__fb-{self.theme}-mode x1n2onr6 x1vjfegm']",
                )
            )
        )

        img_urls = []
        first_img_id = re.search(
            r"https://www\.facebook\.com/photo/?\?fbid=((\d)+)", self.chrome.current_url
        ).group(1)

        orig_post_url = self.chrome.find_element(
            By.XPATH,
            "(//div[@class='x1cy8zhl x2bj2ny x78zum5 x1q0g3np']//div[@class='xu06os2 x1ok221b'])[last()]//a",
        )
        self.action.move_to_element(orig_post_url).pause(0.1).perform()
        orig_post_url = Path(urlparse(orig_post_url.get_attribute("href")).path).name

        iter = 0
        while True:
            post_url = self.chrome.find_element(
                By.XPATH,
                "(//div[@class='x1cy8zhl x2bj2ny x78zum5 x1q0g3np']//div[@class='xu06os2 x1ok221b'])[last()]//a",
            )
            self.action.move_to_element(post_url).pause(0.1).perform()
            post_url = Path(urlparse(post_url.get_attribute("href")).path).name

            if iter > 0 and (img_id == first_img_id or orig_post_url != post_url):
                close_text = {"vi": "Đóng", "en": "Close"}
                close_btn = self.chrome.find_element(
                    By.XPATH, f"//div[@aria-label='{close_text[self.language]}']"
                )
                self.action.click(close_btn).pause(0.2).perform()
                break

            img_el = self.chrome.find_element(
                By.XPATH,
                f"//img[@data-visualcompletion='media-vc-image']",
            )
            img_url = img_el.get_attribute("src")
            # img_url = re.search(r"^.+\.jpg", img_url).group(0)
            img_urls.append(img_url)

            next_img_text = {"vi": "Ảnh tiếp theo", "en": "Next photo"}
            next_img_btn = self.chrome.find_element(
                By.XPATH,
                f"//div[@aria-label='{next_img_text[self.language]}']",
            )

            self.action.move_to_element(next_img_btn)
            if (
                next_img_btn.find_element(By.XPATH, "./div").get_attribute("class")
                == "x6s0dn4 x78zum5 x197sbye xyamay9 x1pi30zi x1l90r2v x1swvt13 x1n2onr6 x1k90msu x6o7n8i x9lcvmn x6my1t9 xiwuv7k"
            ):
                close_text = {"vi": "Đóng", "en": "Close"}
                close_btn = self.chrome.find_element(
                    By.XPATH, f"//div[@aria-label='{close_text[self.language]}']"
                )
                self.action.click(close_btn).pause(0.2).perform()
                break

            self.action.click(next_img_btn).pause(3).perform()
            img_id = re.search(
                r"https://www\.facebook\.com/photo/?\?fbid=((\d)+)",
                self.chrome.current_url,
            ).group(1)

            iter += 1

        return img_urls

    def start(self):
        super().start(start_url=f"https://www.facebook.com/{self.page_id}")
