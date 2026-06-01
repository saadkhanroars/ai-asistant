import unittest
from unittest.mock import patch

import intent_parser
import router
from models import Candidate, RoutingDecision, ScoreBreakdown, ScoredCandidate


def _reset_router_state():
    router._pending_choices = []
    router.get_session_memory().clear()


class SemanticIntentRoutingTests(unittest.TestCase):
    def setUp(self):
        _reset_router_state()

    def test_open_calculator_remains_deterministic_fast_path(self):
        with patch.object(router, "parse_intent", side_effect=AssertionError("LLM should not run")):
            with patch.object(router, "launch_system_app", lambda app: f"MOCK system app: {app.display_name}"):
                self.assertEqual(router.handle_request("open calculator"), "MOCK system app: Calculator")

    def test_open_one_piece_episode_searches_local_first(self):
        candidate = Candidate(
            name="One Piece S01E01",
            path=r"C:\Media\One Piece S01E01.mkv",
            item_type="video",
            source="index",
            search_text="one piece s01e01",
        )
        scored = ScoredCandidate(candidate, 0.9, ScoreBreakdown(exact=0.9))
        with patch.object(router, "parse_intent", side_effect=AssertionError("LLM should not run")):
            with patch.object(router, "generate_index_candidates", return_value=([candidate], {"candidates": 1, "total_indexed": 1, "elapsed_ms": 0})):
                with patch.object(router, "score_candidates", return_value=[scored]):
                    with patch.object(router, "evaluate", return_value=RoutingDecision(action="open", chosen=scored, confidence=0.9)):
                        with patch.object(router, "launch_item", lambda item, score: f"MOCK item: {item.name}"):
                            self.assertEqual(
                                router.handle_request("open one piece season one episode one"),
                                "MOCK item: One Piece S01E01",
                            )

    def test_cat_videos_becomes_web_search(self):
        with patch.object(intent_parser, "understand_intent", return_value=None):
            with patch.object(router, "launch_url", lambda url, browser=None: f"MOCK url: {url}"):
                result = router.handle_request("cat videos")
        self.assertIn("youtube.com/results", result)
        self.assertIn("cat videos", result)

    def test_play_some_music_searches_local_then_falls_back_to_web(self):
        with patch.object(router, "generate_index_candidates", return_value=([], {"candidates": 0, "total_indexed": 0, "elapsed_ms": 0})):
            with patch.object(router, "score_candidates", return_value=[]):
                with patch.object(router, "launch_url", lambda url, browser=None: f"MOCK url: {url}"):
                    result = router.handle_request("play some music")
        self.assertIn("youtube.com/results", result)
        self.assertIn("some music", result)

    def test_asdfghjkl_does_not_open_random_local_result(self):
        with patch.object(intent_parser, "understand_intent", return_value=None):
            with patch.object(router, "generate_index_candidates", return_value=([], {"candidates": 0, "total_indexed": 0, "elapsed_ms": 0})):
                with patch.object(router, "score_candidates", return_value=[]):
                    with patch.object(router, "launch_item", side_effect=AssertionError("Should not open")):
                        with patch.object(router, "launch_url", side_effect=AssertionError("Should not search web")):
                            result = router.handle_request("asdfghjkl")
        self.assertIn("I'm not sure what to open", result)


if __name__ == "__main__":
    unittest.main()
