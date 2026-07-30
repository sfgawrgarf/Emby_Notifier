import os
import unittest
from unittest.mock import patch

os.environ["WECHAT_MSG_TYPE"] = "news"

from sender import WechatAppSender, truncate_utf8


class WechatNewsTest(unittest.TestCase):
    def test_utf8_truncation_preserves_limit_and_underscore(self):
        value = "Master_Piece_" + ("简介内容" * 200)
        result = truncate_utf8(value, 500)
        self.assertLessEqual(len(result.encode("utf-8")), 500)
        self.assertIn("Master_Piece_", result)

    @patch("sender.wxapp.send_news")
    def test_news_payload_keeps_title_characters_and_limits_description(self, send_news):
        media = {
            "server_name": "Emby",
            "server_type": "Emby",
            "server_url": "https://emby.example",
            "media_type": "Episode",
            "media_name": "Master_Piece THE ANIMATION",
            "media_rel": "2019-08-30",
            "media_intro": "剧情_" * 300,
            "media_tmdburl": "https://www.themoviedb.org/tv/97995",
            "media_still": "https://image.tmdb.org/example.jpg",
            "tv_season": 1,
            "tv_episode": 2,
        }

        WechatAppSender().send_media_details(media)

        article = send_news.call_args.args[0]
        self.assertIn("Master_Piece", article["title"])
        self.assertLessEqual(len(article["title"].encode("utf-8")), 120)
        self.assertLessEqual(len(article["description"].encode("utf-8")), 500)


if __name__ == "__main__":
    unittest.main()
