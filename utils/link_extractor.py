import bs4
import re


class LinkExtractor:
    def __init__(self, allow_regex: str, deny_regex: str):
        # Empty string means rejecting all possible strings
        if allow_regex == r"":
            allow_regex = r"^[^a-zA-Z0-9]$"
        if deny_regex == r"":
            deny_regex = r"^[a-zA-Z0-9]$"

        self.allow_re = re.compile(allow_regex)
        self.deny_re = re.compile(deny_regex)

    def match(self, link: str):
        return self.allow_re.search(link) and not self.deny_re.search(link)

    def extract(self, html: str):
        soup = bs4.BeautifulSoup(html, features="lxml")
        anchors = soup.find_all("a")
        links = [anchor.get("href", "") for anchor in anchors]
        links = [link for link in links if self.match(link)]
        return links
