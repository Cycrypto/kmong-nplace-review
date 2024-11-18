import re

import requests


class NaverMeConvertor:
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        )
    }

    def __init__(self, nme_urls: list):
        self.urls = nme_urls
        self.headers = self.HEADERS

    def to_origin(self):
        origin_urls = []
        for url in self.urls:
            print(url)
            req = requests.get(url, headers=self.HEADERS, allow_redirects=False)
            red_url = req.headers.get('Location')
            req = requests.get(red_url, headers=self.HEADERS, allow_redirects=False)
            origin_urls.append(req.headers.get('location'))
        return origin_urls

    def get_meta_info(self, url):
        # 정규 표현식 패턴을 정의하여 category와 primary_no 추출
        match = re.search(r"/entry/([^/]+)/([^?]+)", url)
        if match:
            category = match.group(1)
            primary_no = match.group(2)
            return category, primary_no

        else:
            print("해당 URL에서 category와 primary_no를 찾을 수 없습니다.")
            return None, None

    def get_meta_infos(self, urls):
        result = []
        for url in urls:
            result.append(self.get_meta_info(url))
        return result


if __name__ == "__main__":
    urls = ["https://naver.me/5KZ5TGSr",
            "https://naver.me/GyeyahkG",
            "https://naver.me/GgeUcgYa",
            "https://naver.me/G4rGjope",
            "https://naver.me/FKKOSJLi",
            "https://naver.me/5VeN4HqW",
            "https://naver.me/IFjg5ckm",
            "https://naver.me/5eGd2gHY",
            "https://naver.me/GxONSUR8",
            "https://naver.me/5mYzPAJN"]

    convertor = NaverMeConvertor(urls)
    origins = convertor.to_origin()
    meta = convertor.get_meta_infos(origins)
    print(meta)
