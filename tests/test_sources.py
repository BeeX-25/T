import json
import unittest

from smarttv import sources


class FakeProvider:
    """Answers Xtream/OpenWebif URLs from a table, and records the calls."""

    def __init__(self, replies):
        self.replies = replies
        self.requests = []

    def __call__(self, url):
        self.requests.append(url)
        # Longest fragment first: "get_series_info" must win over
        # "get_series", which is a prefix of it.
        for fragment in sorted(self.replies, key=len, reverse=True):
            if fragment in url:
                reply = self.replies[fragment]
                return reply if isinstance(reply, str) else json.dumps(reply)
        raise AssertionError("unexpected request: %s" % url)


XTREAM = {
    "url": "http://provider:8080",
    "username": "user",
    "password": "pass",
    "name": "اشتراكي",
    "type": "xtream",
}


class XtreamUrlTests(unittest.TestCase):
    def test_api_url_carries_the_credentials(self):
        url = sources.xtream_api_url(XTREAM, "get_live_streams")
        self.assertIn("player_api.php", url)
        self.assertIn("username=user", url)
        self.assertIn("action=get_live_streams", url)

    def test_extra_parameters_are_appended(self):
        url = sources.xtream_api_url(XTREAM, "get_series_info", series_id=12)
        self.assertIn("series_id=12", url)

    def test_stream_urls_per_section(self):
        self.assertEqual(
            sources.xtream_stream_url(XTREAM, "live", 5),
            "http://provider:8080/live/user/pass/5.ts",
        )
        self.assertEqual(
            sources.xtream_stream_url(XTREAM, "movie", 7, "mkv"),
            "http://provider:8080/movie/user/pass/7.mkv",
        )

    def test_trailing_slash_does_not_double_up(self):
        source = dict(XTREAM, url="http://provider:8080/")
        self.assertNotIn("//live", sources.xtream_stream_url(source, "live", 1)[7:])


class XtreamLoadTests(unittest.TestCase):
    def setUp(self):
        self.provider = FakeProvider(
            {
                "get_live_categories": [{"category_id": "1", "category_name": "عربية"}],
                "get_live_streams": [
                    {
                        "stream_id": 11,
                        "name": "MBC 1",
                        "stream_icon": "http://logo/1.png",
                        "category_id": "1",
                        "epg_channel_id": "mbc1",
                    }
                ],
                "get_vod_categories": [{"category_id": "2", "category_name": "أفلام"}],
                "get_vod_streams": [
                    {
                        "stream_id": 22,
                        "name": "فيلم",
                        "category_id": "2",
                        "container_extension": "mkv",
                    }
                ],
                "get_series_categories": [{"category_id": "3", "category_name": "دراما"}],
                "get_series": [
                    {"series_id": 33, "name": "مسلسل", "category_id": "3", "cover": "c.png"}
                ],
                "get_series_info": {
                    "episodes": {
                        "1": [
                            {
                                "id": 101,
                                "title": "الحلقة 1",
                                "episode_num": 1,
                                "season": 1,
                                "container_extension": "mp4",
                            },
                            {
                                "id": 102,
                                "title": "الحلقة 2",
                                "episode_num": 2,
                                "season": 1,
                                "container_extension": "mp4",
                            },
                        ]
                    }
                },
            }
        )

    def test_all_three_kinds_are_loaded(self):
        items = sources.load_xtream(XTREAM, self.provider)
        kinds = {}
        for item in items:
            kinds[item["kind"]] = kinds.get(item["kind"], 0) + 1
        self.assertEqual(kinds, {"live": 1, "movies": 1, "series": 1})

    def test_categories_become_groups(self):
        items = sources.load_xtream(XTREAM, self.provider)
        self.assertEqual(items[0]["group"], "عربية")
        self.assertEqual(items[0]["tvg_id"], "mbc1")
        self.assertEqual(items[0]["url"], "http://provider:8080/live/user/pass/11.ts")

    def test_vod_keeps_its_container_extension(self):
        movie = [i for i in sources.load_xtream(XTREAM, self.provider) if i["kind"] == "movies"][0]
        self.assertTrue(movie["url"].endswith("/22.mkv"))

    def test_a_series_carries_an_id_instead_of_a_stream(self):
        show = [i for i in sources.load_xtream(XTREAM, self.provider) if i["kind"] == "series"][0]
        self.assertEqual(show["series_id"], 33)
        self.assertEqual(show["url"], "")

    def test_kinds_can_be_restricted(self):
        items = sources.load_xtream(dict(XTREAM, kinds=["live"]), self.provider)
        self.assertEqual({item["kind"] for item in items}, {"live"})

    def test_live_extension_is_configurable(self):
        items = sources.load_xtream(dict(XTREAM, kinds=["live"], live_extension="m3u8"), self.provider)
        self.assertTrue(items[0]["url"].endswith(".m3u8"))

    def test_episodes_are_sorted_and_addressable(self):
        episodes = sources.load_xtream_episodes(XTREAM, self.provider, 33)
        self.assertEqual([e["episode"] for e in episodes], [1, 2])
        self.assertEqual(episodes[0]["url"], "http://provider:8080/series/user/pass/101.mp4")

    def test_bad_credentials_are_reported(self):
        provider = FakeProvider({"player_api": {"user_info": {"auth": 0}}})
        with self.assertRaises(ValueError):
            sources.load_xtream(XTREAM, provider)

    def test_a_non_json_reply_is_reported(self):
        provider = FakeProvider({"player_api": "<html>blocked</html>"})
        with self.assertRaises(ValueError):
            sources.load_xtream(XTREAM, provider)


class Enigma2SourceTests(unittest.TestCase):
    SERVICES = {
        "services": [
            {
                "servicename": "باقة عربية",
                "subservices": [
                    {"servicereference": "1:0:19:283D:3FB:1:C00000:0:0:0:", "servicename": "MBC 1"},
                    {"servicereference": "1:64:0:0:0:0:0:0:0:0:", "servicename": "--- فاصل ---"},
                    {"servicereference": "1:0:19:283E:3FB:1:C00000:0:0:0:", "servicename": "MBC 2"},
                ],
            }
        ]
    }

    def setUp(self):
        self.provider = FakeProvider({"api/getallservices": self.SERVICES})
        self.source = {"type": "enigma2", "name": "الرسيفر", "host": "10.0.0.5"}

    def test_channels_become_items_with_a_streamable_url(self):
        items = sources.load_enigma2(self.source, self.provider)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["name"], "MBC 1")
        self.assertEqual(items[0]["group"], "باقة عربية")
        self.assertEqual(
            items[0]["url"], "http://10.0.0.5:8001/1:0:19:283D:3FB:1:C00000:0:0:0:"
        )
        self.assertEqual(items[0]["sref"], "1:0:19:283D:3FB:1:C00000:0:0:0:")

    def test_bouquet_separators_are_skipped(self):
        names = [item["name"] for item in sources.load_enigma2(self.source, self.provider)]
        self.assertNotIn("--- فاصل ---", names)

    def test_streaming_port_is_configurable(self):
        source = dict(self.source, stream_port=8002)
        items = sources.load_enigma2(source, self.provider)
        self.assertIn(":8002/", items[0]["url"])


class ChannelListTests(unittest.TestCase):
    def test_inline_items_become_dialled_channels(self):
        items = sources.load_channels(
            {"name": "رسيفري", "items": [{"name": "MBC 1", "number": 103}]}, None
        )
        self.assertEqual(items[0]["url"], "macro:key:num1,key:num0,key:num3,key:select")
        self.assertEqual(items[0]["number"], "103")
        self.assertEqual(items[0]["kind"], "live")

    def test_confirm_key_can_be_turned_off(self):
        items = sources.load_channels(
            {"items": [{"name": "x", "number": 7}], "confirm": ""}, None
        )
        self.assertEqual(items[0]["url"], "macro:key:num7")

    def test_csv_files_are_accepted(self):
        items = sources.load_channels(
            {"path": "channels.csv"},
            FakeProvider({"channels.csv": "MBC 1,103,عام\n# note\nالجزيرة,7,أخبار\n"}),
        )
        self.assertEqual([item["name"] for item in items], ["MBC 1", "الجزيرة"])
        self.assertEqual(items[1]["group"], "أخبار")

    def test_json_files_are_accepted(self):
        items = sources.load_channels(
            {"path": "channels.json"},
            FakeProvider({"channels.json": '[{"name": "MBC 1", "number": 103}]'}),
        )
        self.assertEqual(items[0]["name"], "MBC 1")

    def test_entries_without_a_number_are_skipped(self):
        items = sources.load_channels(
            {"items": [{"name": "بلا رقم"}, {"name": "ok", "number": "5"}]}, None
        )
        self.assertEqual([item["name"] for item in items], ["ok"])

    def test_dispatch_and_validation(self):
        loaded = sources.load_source(
            {"type": "channels", "items": [{"name": "a", "number": 1}]}, None
        )
        self.assertEqual(len(loaded["items"]), 1)
        with self.assertRaises(ValueError):
            sources.load_source({"type": "channels"}, None)


class DispatchTests(unittest.TestCase):
    def test_m3u_source(self):
        provider = FakeProvider({"list.m3u": "#EXTM3U\n#EXTINF:-1,A\nhttp://a\n"})
        loaded = sources.load_source(
            {"type": "m3u", "url": "http://host/list.m3u", "kind": "movies"}, provider
        )
        self.assertEqual(loaded["items"][0]["kind"], "movies")
        self.assertEqual(loaded["guide"], {})

    def test_xmltv_source(self):
        guide = '<tv><programme start="20260828120000 +0000" stop="20260828130000 +0000" channel="c"><title>t</title></programme></tv>'
        loaded = sources.load_source(
            {"type": "xmltv", "url": "http://host/guide.xml"}, FakeProvider({"guide.xml": guide})
        )
        self.assertIn("c", loaded["guide"])
        self.assertEqual(loaded["items"], [])

    def test_unknown_type(self):
        with self.assertRaises(ValueError):
            sources.load_source({"type": "carrier-pigeon"}, lambda target: "")

    def test_missing_target(self):
        with self.assertRaises(ValueError):
            sources.load_source({"type": "m3u"}, FakeProvider({}))


if __name__ == "__main__":
    unittest.main()
