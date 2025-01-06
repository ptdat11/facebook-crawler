from crawlers import BaseCrawler
import config


from importlib import import_module
import argparse


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--chromedriver",
        "-driver",
        help="Path to executable chromedriver",
        required=True,
    )
    parser.add_argument("--crawler", "-c", help="Crawler option", required=True)
    parser.add_argument(
        "--user", "-u", help="Facebook user in secrets.json", required=True
    )
    parser.add_argument(
        "--crawler-dir",
        "-s",
        default="./data/",
        help="Crawler directory",
        dest="crawler_dir",
    )
    parser.add_argument(
        "--sleep-weibull-lambda",
        "-sleep",
        default=10.0,
        type=float,
        help="Mode of sleep time. According to https://doi.org/10.1145/1835449.1835513, user dwelling time on a page follows Weibull distribution",
        dest="sleep_weibull_lambda",
    )
    parser.add_argument(
        "--max-loading-wait",
        "-max-wait",
        default=90,
        type=int,
        help="Maximum waiting time for page loading",
        dest="max_loading_wait",
    )
    parser.add_argument(
        "--cookies-dir",
        "-cdir",
        default="./cookies/",
        help="Cookies saving directory",
        dest="cookies_dir",
    )
    parser.add_argument(
        "--secrets-json",
        "-sec",
        default="./secrets.json",
        help="Path to secrets.json",
        dest="secrets_json",
    )
    parser.add_argument(
        "--headless",
        "-hls",
        default=False,
        action="store_true",
        help="Enable headless mode (Running web browser without overtaking OS' focus)",
    )
    parser.add_argument(
        "--error-screenshot-dir",
        "-erdir",
        default="./error-screenshots/",
        help="Error screenshot saving directory",
        dest="error_screenshot_dir",
    )
    parser.add_argument(
        "--max-error-trials",
        "-max-trials",
        default=5,
        type=int,
        help="Maximum number of error trials",
        dest="max_error_trials",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    from datetime import datetime

    crawler: BaseCrawler = import_module(
        f".{args.crawler}.crawler", "crawlers"
    ).Crawler(
        chromedriver_path=args.chromedriver,
        navigate_link_extractor=config.NAVIGATE_LINK_EXTRACTOR,
        parse_link_extractor=config.PARSE_LINK_EXTRACTOR,
        crawler_dir=args.crawler_dir,
        data_pipeline=config.PIPELINE,
        user=args.user,
        secrets_file=args.secrets_json,
        cookies_save_dir=args.cookies_dir,
        headless=args.headless,
        sleep_weibull_lambda=args.sleep_weibull_lambda,
        max_loading_wait=args.max_loading_wait,
        max_error_trials=args.max_error_trials,
        **config.CRAWLER_ARGUMENTS.get(args.crawler, dict()),
    )

    crawler.start()
