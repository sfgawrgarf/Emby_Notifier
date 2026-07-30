import os
import unittest
from unittest.mock import patch

os.environ["WECHAT_MSG_TYPE"] = "news"
os.environ["EMBY_PUBLIC_URL"] = "https://avemby.aabbss.de"

from sender import WechatAppSender, truncate_utf8
import json
import media


class WechatNewsTest(unittest.TestCase):
    def test_utf8_truncation_preserves_limit_and_underscore(self):
        value = "Master_Piece_" + ("简介内容" * 200)
        result = truncate_utf8(value, 500)
        self.assertLessEqual(len(result.encode("utf-8")), 500)
        self.assertIn("Master_Piece_", result)

    def test_emby_primary_image_uses_public_item_image(self):
        result = media.get_emby_primary_image(
            {"Id": "20450", "ImageTags": {"Primary": "tag"}},
            "https://avemby.aabbss.de",
        )
        self.assertEqual(
            result,
            "https://avemby.aabbss.de/Items/20450/Images/Primary"
            "?maxWidth=1000&quality=90",
        )

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

    @patch("media.tmdb_api.search_media", return_value=([], None))
    @patch("media.sender.Sender")
    def test_episode_without_tmdb_match_still_sends(
        self, sender_manager, search_media
    ):
        event = {
            "Title": "新增测试剧集",
            "Event": "library.new",
            "Item": {
                "Type": "Episode",
                "Name": "第 1 集",
                "SeriesName": "TMDB 无结果的剧集",
                "PremiereDate": "2019-01-01T00:00:00.0000000Z",
                "IndexNumber": 1,
                "ParentIndexNumber": 1,
                "ProviderIds": {},
                "Id": "20450",
                "ImageTags": {"Primary": "tag"},
            },
            "Server": {
                "Name": "Emby",
                "Version": "4.9.3.0",
            },
        }

        media.process_media(json.dumps(event, ensure_ascii=False))

        payload = sender_manager.send_media_details.call_args.args[0]
        self.assertEqual(payload["media_name"], "TMDB 无结果的剧集")
        self.assertEqual(payload["tv_season"], 1)
        self.assertEqual(payload["tv_episode"], 1)
        self.assertEqual(
            payload["media_still"],
            "https://avemby.aabbss.de/Items/20450/Images/Primary"
            "?maxWidth=1000&quality=90",
        )

    @patch(
        "media.tmdb_api.get_tv_episode_still_paths",
        return_value=(None, "missing still"),
    )
    @patch(
        "media.tmdb_api.get_tv_season_poster",
        return_value=(None, "missing poster"),
    )
    @patch(
        "media.tmdb_api.get_tv_episode_details",
        return_value=(
            {
                "vote_average": 0,
                "air_date": "2019-01-01",
                "overview": "",
                "season_number": 1,
                "episode_number": 2,
                "name": "第 2 集",
            },
            None,
        ),
    )
    @patch("media.tmdb_api.get_external_ids", return_value=({}, None))
    @patch(
        "media.tmdb_api.search_media",
        return_value=(
            [
                {
                    "id": 123,
                    "original_name": "缺少图片的剧集",
                    "first_air_date": "2019-01-01",
                }
            ],
            None,
        ),
    )
    def test_missing_tmdb_artwork_uses_default(
        self, search_media, external_ids, get_details, get_poster, get_still
    ):
        episode = media.Episode()
        episode.info_["ProviderIds"] = {}
        episode.info_["Name"] = "缺少图片的剧集"
        episode.info_["Season"] = 1
        episode.info_["Series"] = 2
        episode.media_detail_["media_poster"] = media.DEFAULT_IMAGE_URL
        episode.media_detail_["media_still"] = media.DEFAULT_IMAGE_URL

        episode.get_details()

        self.assertEqual(episode.media_detail_["media_still"], media.DEFAULT_IMAGE_URL)


if __name__ == "__main__":
    unittest.main()
