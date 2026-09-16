import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import tbpro_daily as td


class MonthWindowTests(unittest.TestCase):
    def test_windows_are_contiguous_and_half_open(self):
        wins = list(td.month_windows("2026-05-04", dt.date(2026, 7, 15)))
        self.assertEqual(wins, [
            ("2026-05-04", "2026-06-01"),
            ("2026-06-01", "2026-07-01"),
            ("2026-07-01", "2026-08-01"),
        ])

    def test_window_covers_report_date_in_current_month(self):
        wins = list(td.month_windows("2026-09-01", dt.date(2026, 9, 16)))
        self.assertEqual(wins[-1][1], "2026-10-01")

    def test_year_rollover(self):
        wins = list(td.month_windows("2026-12-10", dt.date(2027, 1, 3)))
        self.assertEqual(wins, [
            ("2026-12-10", "2027-01-01"),
            ("2027-01-01", "2027-02-01"),
        ])


def _paged_zd_get(total):
    """Fake zd_get that serves `total` results 100 at a time, advertising
    next_page exactly the way Zendesk does."""
    calls = []

    def fake(path, params=None):
        calls.append(params)
        page = params["page"]
        start = (page - 1) * 100
        results = [{"id": i} for i in range(start, min(start + 100, total))]
        return {
            "results": results,
            "next_page": "..." if start + 100 < total else None,
        }

    return fake, calls


class SearchPaginationTests(unittest.TestCase):
    def test_fetches_everything_under_the_cap(self):
        fake, calls = _paged_zd_get(950)
        with patch.object(td, "zd_get", fake):
            got = td.zd_search_all("type:ticket")
        self.assertEqual(len(got), 950)
        self.assertEqual(len(calls), 10)

    def test_raises_named_error_instead_of_422_at_the_cap(self):
        # 1,500 matches: page 10 still advertises next_page, so the old code
        # requested page 11 and Zendesk answered HTTP 422.
        fake, calls = _paged_zd_get(1500)
        with patch.object(td, "zd_get", fake):
            with self.assertRaises(td.ZendeskSearchTooBroad) as ctx:
                td.zd_search_all("type:ticket")
        self.assertIn("1000", str(ctx.exception))
        self.assertEqual(max(c["page"] for c in calls), 10,
                         "must never request the page that 422s")

    def test_exactly_1000_does_not_raise(self):
        fake, _ = _paged_zd_get(1000)
        with patch.object(td, "zd_get", fake):
            got = td.zd_search_all("type:ticket")
        self.assertEqual(len(got), 1000)


class WindowedSearchTests(unittest.TestCase):
    def test_splits_a_too_broad_span_into_survivable_queries(self):
        # 800 tickets per month => 3,200 total, which no single search can page.
        queries = []

        def fake(path, params=None):
            queries.append(params["query"])
            page = params["page"]
            month = params["query"].split("created>=")[1][:7]
            start = (page - 1) * 100
            results = [{"id": f"{month}-{i}"} for i in range(start, min(start + 100, 800))]
            return {"results": results, "next_page": "..." if start + 100 < 800 else None}

        with patch.object(td, "zd_get", fake):
            got = td.zd_search_all_windowed(
                "type:ticket brand_id:1", "2026-05-04", dt.date(2026, 8, 20))

        self.assertEqual(len(got), 3200)
        spans = {q.split("created>=")[1] for q in queries}
        self.assertEqual(spans, {
            "2026-05-04 created<2026-06-01",
            "2026-06-01 created<2026-07-01",
            "2026-07-01 created<2026-08-01",
            "2026-08-01 created<2026-09-01",
        })

    def test_dedupes_ids_seen_in_more_than_one_window(self):
        def fake(path, params=None):
            return {"results": [{"id": 7}, {"id": 8}], "next_page": None}

        with patch.object(td, "zd_get", fake):
            got = td.zd_search_all_windowed(
                "type:ticket", "2026-05-01", dt.date(2026, 7, 1))

        self.assertEqual([t["id"] for t in got], [7, 8])


class AdaptiveSubdivisionTests(unittest.TestCase):
    """A calendar month can itself hold more than 1,000 tickets; the window
    must narrow until each query fits rather than failing the report."""

    @staticmethod
    def _window_of(query):
        lo = query.split("created>=")[1].split(" ")[0]
        hi = query.split("created<")[1].split(" ")[0]
        return lo, hi

    def _fake_zd_get(self, per_day, asked):
        """Serve `per_day` tickets for every day in the requested window, so a
        window's size is proportional to its span -- exactly the condition that
        makes wide windows overflow and narrow ones succeed.

        Records {(lo, hi): total} in `asked` so a test can tell which windows
        were servable (total <= the cap) rather than inferring it from span."""
        def fake(path, params=None):
            lo, hi = self._window_of(params["query"])
            span = (dt.date.fromisoformat(hi) - dt.date.fromisoformat(lo)).days
            total = span * per_day
            asked[(lo, hi)] = total
            ids = [f"{lo}:{i}" for i in range(total)]
            page = params["page"]
            start = (page - 1) * 100
            chunk = ids[start:start + 100]
            return {
                "results": [{"id": i} for i in chunk],
                "next_page": "..." if start + 100 < len(ids) else None,
            }
        return fake

    def test_splits_an_overflowing_month_and_returns_everything(self):
        # 50/day over a 31-day month = 1,550 -> one search cannot page it.
        asked = {}
        with patch.object(td, "zd_get", self._fake_zd_get(50, asked)):
            got = td.zd_search_all_windowed(
                "type:ticket", "2026-07-01", dt.date(2026, 7, 31))

        self.assertEqual(len(got), 31 * 50)
        self.assertEqual(len({t["id"] for t in got}), 31 * 50, "no duplicates")

        # The full-month attempt happened, overflowed, and then narrowed.
        self.assertIn(("2026-07-01", "2026-08-01"), asked)
        spans = [(dt.date.fromisoformat(h) - dt.date.fromisoformat(l)).days
                 for l, h in asked]
        self.assertTrue(any(s < 31 for s in spans), "window never narrowed")

    def test_subwindows_tile_the_month_without_gaps_or_overlap(self):
        asked = {}
        with patch.object(td, "zd_get", self._fake_zd_get(50, asked)):
            td.zd_search_all_windowed(
                "type:ticket", "2026-07-01", dt.date(2026, 7, 31))

        # The leaves are the windows the fake could actually serve; they must
        # tile July exactly -- no gap (lost tickets) and no overlap (double
        # counting, which only the id de-dupe would be hiding).
        leaves = sorted(w for w, total in asked.items()
                        if total <= td.ZD_SEARCH_RESULT_LIMIT)
        self.assertEqual(leaves[0][0], "2026-07-01")
        self.assertEqual(leaves[-1][1], "2026-08-01")
        for (_, prev_hi), (next_lo, _) in zip(leaves, leaves[1:]):
            self.assertEqual(prev_hi, next_lo, "gap or overlap between windows")

    def test_gives_up_with_a_clear_message_on_a_single_overflowing_day(self):
        # 1,500 tickets created on one calendar day: unreachable by search.
        def fake(path, params=None):
            page = params["page"]
            start = (page - 1) * 100
            return {
                "results": [{"id": i} for i in range(start, min(start + 100, 1500))],
                "next_page": "..." if start + 100 < 1500 else None,
            }

        with patch.object(td, "zd_get", fake):
            with self.assertRaises(td.ZendeskSearchTooBroad) as ctx:
                td.zd_search_all_windowed(
                    "type:ticket", "2026-07-01", dt.date(2026, 7, 10))
        self.assertIn("incremental", str(ctx.exception),
                      "should point at the endpoint that can actually do it")


if __name__ == "__main__":
    unittest.main()
