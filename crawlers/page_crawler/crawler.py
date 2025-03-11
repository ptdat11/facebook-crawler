from typing import Any, Sequence
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver import Chrome
from selenium.webdriver.support import expected_conditions as EC

import re
import traceback
import sys
import bs4
from pathlib import Path
from ..base_crawler import BaseCrawler
from EC import more_items_loaded
from utils.parsing import parse_post_date, parse_text_from_element, get_video_url_from_source
from utils.utils import to_bs4, ordinal, sha256, tqdm_output
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
                self.wait.until(
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

    def get_loaded_posts(self, start: int = 1, stop: int = -1):
        if stop < 0:
            stop = f"last(){stop}"
        # print(f"Start: {start}; Stop: {stop}")
        return self.chrome.find_elements(
            By.XPATH,
            f"({Crawler.posts_xpath})[position() >= {start} and position() <= {stop}]",
        )

    def parse(self):
        self.remove_header()
        n_scraped_posts = 0
        current_post_idx = 1

        with tqdm_output(
            tqdm(total=round(virtual_memory().total / 1024**3, ndigits=2), desc="RAM Usage (GB)")
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
                self.wait.until(
                    more_items_loaded(
                        posts_locator=(By.XPATH, Crawler.posts_xpath),
                        current_count=len(self.get_loaded_posts()),
                    )
                )
                self.post_collect_criteria.update_progress(self.chrome)

                for post_div in self.get_loaded_posts(start=current_post_idx, stop=current_post_idx):
                    scraped = False
                    self.scroll_into_view(post_div, sleep=1)

                    try:
                        # Check if reel
                        if to_bs4(post_div).find("a")["href"].startswith("/reel"):
                            yield self.parse_reel(post_div)
                            scraped = True

                        # Check if update avatar
                        elif to_bs4(post_div).find(
                            "img", {"data-imgperflogname": "feedCoverPhoto"}
                        ):
                            self.logger.info(f"Found {ordinal(current_post_idx)} post as avatar, skipping...")
                            
                        # Normal post
                        else:
                            post = self.parse_post(post_div)
                            yield post
                            scraped = True
                    except Exception as e:
                        exc_type, value, tb = sys.exc_info()
                        self.logger.warning(
                            f"Skipping {ordinal(current_post_idx)} post: {red(exc_type.__name__)}: {value}\n{traceback.format_exc()}"
                        )
                        continue
                    finally:
                        current_post_idx += 1

                    n_scraped_posts += scraped
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
            self.remove_element(to_be_removed)
    
    def parse_reel(self, reel_div: WebElement):
        reel_a = reel_div.find_element(By.XPATH, ".//a[starts-with(@href, '/reel')]")
        reel_id = re.search(r"reel/(\d+)", reel_a.get_attribute("href")).group(1)
        reel_url = f"https://www.facebook.com/{reel_id}"

        with self.new_tab_no_cookies(reel_url):
            # Close login modal
            close_modal_text = {"vi": "Đóng", "en": "Close"}
            close_modal_btn = self.chrome.find_element(By.XPATH, f"//div[@aria-label='{close_modal_text[self.language]}']")
            close_modal_btn.click()

            # Extract video
            reel_video_urls = get_video_url_from_source(self.chrome.page_source)

            # Show full caption
            see_more_text = {"vi": "Xem thêm", "en": "See more"}
            if self.page_source_soup().find("div", attrs={"role": "button"}, string=see_more_text[self.language]):
                see_more_btn = self.chrome.find_element(By.XPATH, f"//div[@role='button' and text()='{see_more_text[self.language]}']")
                see_more_btn.click()

                see_less_text = {"vi": "Ẩn bớt", "en": "See less"}
                self.remove_element(self.chrome.find_element(By.XPATH, f"//div[text()='{see_less_text[self.language]}']"))
            
            # Extract caption
            caption_div = self.chrome.find_element(By.XPATH, "//div[starts-with(@class, 'xyamay9 x1pi30zi x1swvt13 xjkvuk6')]/span/div")
            caption = parse_text_from_element(caption_div)

        return {
            "post_id": sha256(reel_id),
            "post_url": reel_url,
            "caption": caption,
            "img_urls": None,
            "video_urls": reel_video_urls["video_url"],
            "video_audio_urls": reel_video_urls["audio_url"],
            "crawl_time": datetime.now(),
            "is_reel": True,
        }


    def parse_post(self, post_div: WebElement):
        hover_content_div = self.chrome.find_element(
            By.XPATH, Crawler.content_on_hover_xpath
        )

        post_content_divs = post_div.find_element(
            By.XPATH, "./descendant::div[@class='html-div xdj266r x11i5rnm xat24cr x1mh8g0r xexx8yu x4uap5 x18d9i69 xkhd6sd']"
        ).find_elements(By.XPATH, f"./div/div/div")

        # Get profile div
        profile_div = post_div.find_element(By.XPATH, "./descendant::div[@data-ad-rendering-role='profile_name']")

        # Get content (caption + image/video) div
        content_div = post_content_divs[2]
        num_content_modalities = 0
        for content in content_div.find_elements(By.XPATH, "div"):
            trans_text = {"vi": "Dịch bài viết này", "en": "See translation"}
            if content.text != trans_text[self.language]:
                num_content_modalities += 1

        text_content_div = content_div.find_elements(By.XPATH, "./descendant::div[@data-ad-comet-preview='message']")
        text_content_div = text_content_div[0] if len(text_content_div) > 0 else None

        if (
            num_content_modalities == 2
            and text_content_div is not None
            or num_content_modalities == 1
            and text_content_div is None
        ):
            visual_content_div = post_content_divs[2].find_element(By.XPATH, "(./div)[last()]")
        else:
            visual_content_div = None

        # Ensure post's text content showing full version
        see_more_text = {"vi": "Xem thêm", "en": "See more"}
        if (
            to_bs4(content_div).find("div", attrs={"role": "button"}, string=see_more_text[self.language]) is not None
        ):
            show_more_btn = content_div.find_element(By.XPATH, f"./descendant::div[@role='button' and text()='{see_more_text[self.language]}']")
            self.action.move_to_element(show_more_btn).click(show_more_btn).pause(0.5).move_to_element(post_div).perform()

        # Get post's datetime a element
        post_datetime_a = profile_div.find_element(By.XPATH, "(../../../div)[2]//a")
        self.scroll_into_view(post_datetime_a, sleep=0.5)

        # Get post's raw URL
        post_raw_url = post_datetime_a.get_attribute("href")
        # Get post's ID
        post_id = Path(urlparse(post_raw_url).path).name
        # Get post's link
        post_link = f"https://www.facebook.com/{post_id}"

        # Get post's caption
        caption = (
            parse_text_from_element(text_content_div)
            if text_content_div is not None
            else ""
        )
        caption = unescape(re.sub(r"href\(, [^\)]+\)", "", caption).strip())

        # Get post's visual content
        visual_urls = self.get_visual_content(visual_content_div)

        return {
            "post_id": sha256(post_id),
            "post_url": post_link,
            "caption": caption,
            "img_urls": "   ".join(visual_urls["img_urls"]),
            "video_urls": "   ".join(visual_urls["video_urls"]),
            "video_audio_urls": "   ".join(visual_urls["video_audio_urls"]),
            "crawl_time": datetime.now(),
            "is_reel": False,
        }
    
    def get_visual_content_id(self, url: str, content_type: Literal["img", "video"]):
        if content_type == "img":
            return re.search(r"photo/?\?fbid=((\d)+)", url).group(1)
        elif content_type == "video":
            return re.search(r"(\d+)[^\d]*$", url).group(0)

    def get_visual_content(self, visual_content_div: WebElement | None):
        visual_urls = {"img_urls": [], "video_urls": [], "video_audio_urls": []}
        if visual_content_div is None:
            return visual_urls
        # Get post's visual soup (BeautifulSoup object)
        visual_soup = to_bs4(visual_content_div) if visual_content_div is not None else None
        # Check first content's type
        first_is_image = (
            visual_soup.find("img") is not None
            and "data-visualcompletion" not in visual_soup.find("img").parent.attrs
            if visual_soup is not None
            else False
        )
        first_is_video = (
            visual_soup.find("div", {"role": "presentation"}) is not None
            if visual_soup is not None
            else False
        )

        first_content = visual_content_div.find_element(By.XPATH, ".//img")
        # If the post has clickable telephone call
        if first_is_image:
            anchor = first_content.find_element(By.XPATH, "./ancestor::a")
            self.scroll_into_view(anchor, sleep=0.1)
            if to_bs4(anchor).find("a", {"href": re.compile(r"^tel")}):
                img_url = first_content.get_attribute("src")
                visual_urls["img_urls"].append(img_url)
                return visual_urls
        
        # Else, click the first content to view all contents
        if first_is_video:
            # Double click
            self.action.move_to_element(first_content).click(first_content).pause(2).perform()
            updated_el = visual_content_div.find_element(By.XPATH, ".//div[@class='x1lliihq x5yr21d x1n2onr6 xh8yej3 x1ja2u2z']")
            self.action.move_to_element(updated_el).click(updated_el).pause(2).perform()
        elif first_is_image:
            self.action.move_to_element(first_content).click(first_content).perform()

        first_content_id = self.get_visual_content_id(self.chrome.current_url, "img" if first_is_image else "video")
        orig_post_id = self.get_post_id_from_dialog()

        iter = 0
        while True:
            post_id = self.get_post_id_from_dialog()
            
            is_video = self.page_source_soup().find("img", {"data-visualcompletion": "media-vc-image"}) is None
            if is_video:
                content_id = self.get_visual_content_id(self.chrome.current_url, "video")
                with self.new_tab_no_cookies(f"https://www.facebook.com/{content_id}"):
                    video_result = get_video_url_from_source(self.chrome.page_source)
                    visual_urls["video_urls"].append(video_result["video_url"])
                    visual_urls["video_audio_urls"].append(video_result["audio_url"])

            else:
                content_id = self.get_visual_content_id(self.chrome.current_url, "img")
                img_el = self.chrome.find_element(By.XPATH, f"//img[@data-visualcompletion='media-vc-image']")
                img_url = img_el.get_attribute("src")
                visual_urls["img_urls"].append(img_url)

            # Check if came back to first content or jumped to other post
            if iter > 0 and (content_id == first_content_id or orig_post_id != post_id):
                self.exit_dialog()
                break
            
            # Move to next content, if there is any
            next_img_text = {"vi": "Ảnh tiếp theo", "en": "Next photo"}
            next_btn_exist = self.page_source_soup().find("div", {"aria-label": next_img_text[self.language]}) is not None
            if next_btn_exist:
                next_img_btn = self.chrome.find_element(By.XPATH, f"//div[@aria-label='{next_img_text[self.language]}']")
                self.action.move_to_element(next_img_btn).click(next_img_btn).pause(3).perform()

            # If no next image
            else:
                self.exit_dialog()
                break

            iter += 1
        return visual_urls

    def exit_dialog(self):
        close_text = {"vi": "Đóng", "en": "Close"}
        close_btn = self.chrome.find_element(By.XPATH, f"//div[@aria-label='{close_text[self.language]}']")
        self.action.click(close_btn).pause(0.2).perform()

    def get_post_id_from_dialog(self):
        post_id = self.chrome.find_element(By.XPATH, "(//div[@role='dialog'])[last()]//div[@class='xu06os2 x1ok221b'][last()]//a")
        self.action.move_to_element(post_id).pause(0.1).perform()

        post_id = self.chrome.find_element(By.XPATH, "(//div[@role='dialog'])[last()]//div[@class='xu06os2 x1ok221b'][last()]//a")
        post_id = Path(urlparse(post_id.get_attribute("href")).path).name

        return post_id

    def start(self):
        super().start(start_url=f"https://www.facebook.com/{self.page_id}")
