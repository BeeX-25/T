import os
import tempfile
import time
import unittest

from smarttv.catalog import (
    Catalog,
    parse_episode,
    parse_m3u,
    parse_xmltv,
    series_title,
)

PLAYLIST = """#EXTM3U
#EXTINF:-1 tvg-id="mbc1.ae" tvg-logo="http://logo/1.png" group-title="عام",MBC 1
http://stream/mbc1.m3u8
#EXTINF:-1 tvg-id="aljazeera.qa" group-title="أخبار",Al Jazeera
http://stream/aljazeera.m3u8
#EXTGRP:أفلام
#EXTINF:-1,فيلم الاختيار
http://stream/film.mp4
http://stream/bare-url.mp4
"""


class M3UTests(unittest.TestCase):
    def test_attributes_and_names(self):
        items = parse_m3u(PLAYLIST)
        self.assertEqual(len(items), 4)
        self.assertEqual(items[0]["name"], "MBC 1")
        self.assertEqual(items[0]["tvg_id"], "mbc1.ae")
        self.assertEqual(items[0]["logo"], "http://logo/1.png")
        self.assertEqual(items[0]["group"], "عام")
        self.assertEqual(items[0]["url"], "http://stream/mbc1.m3u8")

    def test_extgrp_applies_to_following_entries(self):
        items = parse_m3u(PLAYLIST)
        self.assertEqual(items[2]["group"], "أفلام")

    def test_bare_urls_are_kept(self):
        items = parse_m3u(PLAYLIST)
        self.assertEqual(items[3]["url"], "http://stream/bare-url.mp4")
        self.assertEqual(items[3]["name"], "bare-url.mp4")

    def test_kind_is_stamped_on_every_item(self):
        items = parse_m3u(PLAYLIST, kind="movies", source="مصدري")
        self.assertTrue(all(item["kind"] == "movies" for item in items))
        self.assertTrue(all(item["source"] == "مصدري" for item in items))

    def test_empty_input(self):
        self.assertEqual(parse_m3u(""), [])
        self.assertEqual(parse_m3u(None), [])


class EpisodeTests(unittest.TestCase):
    def test_english_markers(self):
        self.assertEqual(parse_episode("Dark Matter S02E05"), (2, 5))
        self.assertEqual(parse_episode("show.s01.e12.1080p"), (1, 12))
        self.assertEqual(parse_episode("Show 3x07"), None)

    def test_arabic_marker(self):
        self.assertEqual(parse_episode("مسلسل الاختيار الحلقة 12"), (1, 12))

    def test_no_marker(self):
        self.assertIsNone(parse_episode("A Film (2019)"))

    def test_series_title_strips_the_marker(self):
        self.assertEqual(series_title("Dark Matter S02E05"), "Dark Matter")
        self.assertEqual(series_title("مسلسل الاختيار الحلقة 12"), "مسلسل الاختيار")
        self.assertEqual(series_title("A Film"), "A Film")


class XmltvTests(unittest.TestCase):
    GUIDE = (
        '<tv><programme start="20260828120000 +0000" stop="20260828130000 +0000" '
        'channel="mbc1.ae"><title>نشرة الأخبار</title><desc>تفاصيل</desc></programme>'
        '<programme start="20260828130000 +0000" stop="20260828140000 +0000" '
        'channel="mbc1.ae"><title>برنامج</title></programme></tv>'
    )

    def test_programmes_are_grouped_and_sorted(self):
        guide = parse_xmltv(self.GUIDE)
        self.assertEqual(len(guide["mbc1.ae"]), 2)
        self.assertEqual(guide["mbc1.ae"][0]["title"], "نشرة الأخبار")
        self.assertLess(guide["mbc1.ae"][0]["start"], guide["mbc1.ae"][1]["start"])

    def test_timezone_offset_is_applied(self):
        utc = parse_xmltv(self.GUIDE)["mbc1.ae"][0]["start"]
        shifted = parse_xmltv(self.GUIDE.replace("+0000", "+0300"))["mbc1.ae"][0]["start"]
        self.assertEqual(utc - shifted, 3 * 3600)

    def test_broken_xml_is_not_fatal(self):
        self.assertEqual(parse_xmltv("<tv><programme>"), {})


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.playlist = os.path.join(self.folder.name, "list.m3u")
        with open(self.playlist, "w", encoding="utf-8") as handle:
            handle.write(PLAYLIST)

    def build(self, sources=None):
        return Catalog(
            {
                "sources": sources
                if sources is not None
                else [{"name": "local", "path": self.playlist, "kind": "live"}],
                "cache_dir": os.path.join(self.folder.name, "cache"),
            }
        )

    def test_refresh_loads_local_files(self):
        catalog = self.build()
        result = catalog.refresh()
        self.assertEqual(result["items"], 4)
        self.assertEqual(catalog.status()["kinds"], {"live": 4})

    def test_search_by_name_and_group(self):
        catalog = self.build()
        self.assertEqual(catalog.search("jazeera")["total"], 1)
        self.assertEqual(catalog.search(group="أخبار")["total"], 1)
        self.assertEqual(catalog.search("لا شيء")["total"], 0)

    def test_search_paginates(self):
        catalog = self.build()
        page = catalog.search(limit=2, offset=2)
        self.assertEqual(page["total"], 4)
        self.assertEqual(len(page["items"]), 2)

    def test_groups_are_counted(self):
        catalog = self.build()
        groups = {group["name"]: group["count"] for group in catalog.groups()}
        self.assertEqual(groups["عام"], 1)
        self.assertEqual(groups["أفلام"], 2)

    def test_a_broken_source_does_not_hide_the_others(self):
        catalog = self.build(
            [
                {"name": "missing", "path": os.path.join(self.folder.name, "nope.m3u")},
                {"name": "local", "path": self.playlist},
            ]
        )
        result = catalog.refresh()
        self.assertEqual(result["items"], 4)
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(result["errors"][0]["source"], "missing")

    def test_series_are_collapsed_into_shows(self):
        path = os.path.join(self.folder.name, "series.m3u")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(
                "#EXTM3U\n"
                "#EXTINF:-1,Dark Matter S01E01\nhttp://s/1\n"
                "#EXTINF:-1,Dark Matter S01E02\nhttp://s/2\n"
                "#EXTINF:-1,Another Show S02E01\nhttp://s/3\n"
            )
        catalog = self.build([{"name": "s", "path": path, "kind": "series"}])
        shows = catalog.series()
        self.assertEqual(shows["total"], 2)
        dark = [show for show in shows["items"] if show["name"] == "Dark Matter"][0]
        self.assertEqual(dark["episode_count"], 2)
        self.assertEqual(dark["episodes"][0]["episode"], 1)

    def test_now_and_next_skips_finished_programmes(self):
        guide_path = os.path.join(self.folder.name, "guide.xml")
        now = time.time()
        with open(guide_path, "w", encoding="utf-8") as handle:
            handle.write(
                "<tv>"
                + "".join(
                    '<programme start="%s" stop="%s" channel="c1"><title>%s</title></programme>'
                    % (
                        time.strftime("%Y%m%d%H%M%S", time.localtime(now + offset)),
                        time.strftime("%Y%m%d%H%M%S", time.localtime(now + offset + 3600)),
                        label,
                    )
                    for offset, label in ((-7200, "قديم"), (-600, "الآن"), (3600, "التالي"))
                )
                + "</tv>"
            )
        catalog = self.build([{"name": "g", "type": "xmltv", "path": guide_path}])
        catalog.refresh()
        upcoming = catalog.now_and_next("c1")
        self.assertEqual([item["title"] for item in upcoming], ["الآن", "التالي"])

    def test_no_sources_means_an_empty_but_working_catalog(self):
        catalog = self.build([])
        self.assertEqual(catalog.search()["total"], 0)
        self.assertEqual(catalog.status()["sources"], 0)


if __name__ == "__main__":
    unittest.main()
