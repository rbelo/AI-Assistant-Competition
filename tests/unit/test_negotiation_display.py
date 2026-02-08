import os
import sys
from contextlib import contextmanager

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "streamlit"))

from modules import negotiation_display as nd  # noqa: E402


class _FakeColumn:
    def __init__(self):
        self.metrics = []
        self.markdowns = []

    def metric(self, label, value):
        self.metrics.append((label, value))

    def markdown(self, text, **_kwargs):
        self.markdowns.append(text)


@contextmanager
def _fake_expander(*args, **kwargs):
    yield


class TestRenderChatSummary:
    def _patch_streamlit(self, monkeypatch, columns, writes, infos, captions):
        monkeypatch.setattr(nd.st, "subheader", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "write", lambda text, *_args, **_kwargs: writes.append(text))
        monkeypatch.setattr(nd.st, "info", lambda text: infos.append(text))
        monkeypatch.setattr(nd.st, "columns", lambda n: columns[:n])
        monkeypatch.setattr(nd.st, "caption", lambda text, *_args, **_kwargs: captions.append(text))
        monkeypatch.setattr(nd.st, "text_area", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "expander", _fake_expander)
        monkeypatch.setattr(nd.st, "slider", lambda *_args, **_kwargs: None)

    @pytest.mark.unit
    def test_no_valid_agreement_displays_none_agreed_value(self, monkeypatch):
        infos = []
        writes = []
        captions = []
        columns = [_FakeColumn(), _FakeColumn(), _FakeColumn()]

        self._patch_streamlit(monkeypatch, columns, writes, infos, captions)

        nd.render_chat_summary(
            summary_text="Some summary",
            deal_value=None,
            score_role1=0,
            score_role2=0,
            role1_label="Buyer",
            role2_label="Seller",
            transcript="chat",
        )

        assert "No valid agreement detected." in infos
        assert columns[0].metrics == [("Buyer Score", "0")]
        assert columns[1].metrics == [("Seller Score", "0")]

    @pytest.mark.unit
    def test_none_deal_value_with_positive_margin_shows_margin_caption(self, monkeypatch):
        infos = []
        writes = []
        captions = []
        columns = [_FakeColumn(), _FakeColumn(), _FakeColumn()]

        self._patch_streamlit(monkeypatch, columns, writes, infos, captions)

        nd.render_chat_summary(
            summary_text="Some summary",
            deal_value=None,
            score_role1=None,
            score_role2=None,
            role1_label="Buyer",
            role2_label="Seller",
            transcript="chat",
            role1_reservation=10,
            role2_reservation=20,
        )

        assert "No valid agreement detected." in infos
        assert "No agreement was reached, despite a positive negotiation margin." in captions

    @pytest.mark.unit
    def test_none_deal_value_with_positive_margin_in_reverse_order(self, monkeypatch):
        infos = []
        writes = []
        captions = []
        columns = [_FakeColumn(), _FakeColumn(), _FakeColumn()]

        self._patch_streamlit(monkeypatch, columns, writes, infos, captions)

        nd.render_chat_summary(
            summary_text="Some summary",
            deal_value=None,
            score_role1=None,
            score_role2=None,
            role1_label="Seller",
            role2_label="Buyer",
            transcript="chat",
            role1_reservation=12,
            role2_reservation=11,
        )

        assert "No agreement was reached, despite a positive negotiation margin." in captions

    @pytest.mark.unit
    def test_none_deal_value_with_no_margin_shows_no_margin_caption(self, monkeypatch):
        infos = []
        writes = []
        captions = []
        columns = [_FakeColumn(), _FakeColumn(), _FakeColumn()]

        self._patch_streamlit(monkeypatch, columns, writes, infos, captions)

        nd.render_chat_summary(
            summary_text="Some summary",
            deal_value=None,
            score_role1=0,
            score_role2=0,
            role1_label="Buyer",
            role2_label="Seller",
            transcript="chat",
            role1_reservation=20,
            role2_reservation=20,
        )

        assert "There was no negotiation margin between the reservation values." in captions

    @pytest.mark.unit
    def test_in_range_deal_shows_single_extracted_caption(self, monkeypatch):
        infos = []
        writes = []
        captions = []
        columns = [_FakeColumn(), _FakeColumn(), _FakeColumn()]

        self._patch_streamlit(monkeypatch, columns, writes, infos, captions)

        nd.render_chat_summary(
            summary_text="Some summary",
            deal_value=15.0,
            score_role1=0.25,
            score_role2=0.75,
            role1_label="Buyer",
            role2_label="Seller",
            transcript="chat",
            role1_reservation=10,
            role2_reservation=20,
            viewer_label="You",
        )

        assert "**Agreed Value:** 15.00" in writes
        assert "You extracted 25% of the negotiation margin." in captions
        assert "You were able to extract more than 100% of the negotiation margin." not in captions
        assert "You extracted less than 0% of the negotiation margin." not in captions

    @pytest.mark.unit
    def test_out_of_range_high_shows_more_than_100_caption_only(self, monkeypatch):
        infos = []
        writes = []
        captions = []
        columns = [_FakeColumn(), _FakeColumn(), _FakeColumn()]

        self._patch_streamlit(monkeypatch, columns, writes, infos, captions)

        nd.render_chat_summary(
            summary_text="Some summary",
            deal_value=5.0,
            score_role1=1.2,
            score_role2=0.0,
            role1_label="Buyer",
            role2_label="Seller",
            transcript="chat",
            role1_reservation=10,
            role2_reservation=20,
            viewer_label="You",
        )

        assert "You extracted more than 100% of the negotiation margin." in captions
        assert not any("extracted " in c and "%" in c for c in captions if "more than 100%" not in c)

    @pytest.mark.unit
    def test_out_of_range_low_shows_less_than_0_caption_only(self, monkeypatch):
        infos = []
        writes = []
        captions = []
        columns = [_FakeColumn(), _FakeColumn(), _FakeColumn()]

        self._patch_streamlit(monkeypatch, columns, writes, infos, captions)

        nd.render_chat_summary(
            summary_text="Some summary",
            deal_value=25.0,
            score_role1=-0.1,
            score_role2=1.0,
            role1_label="Buyer",
            role2_label="Seller",
            transcript="chat",
            role1_reservation=10,
            role2_reservation=20,
            viewer_label="You",
        )

        assert "You extracted less than 0% of the negotiation margin." in captions
        assert not any("extracted " in c and "%" in c for c in captions if "less than 0%" not in c)

    @pytest.mark.unit
    def test_render_matchup_chats_handles_string_int_group_id_for_viewer(self, monkeypatch):
        captions = []

        monkeypatch.setattr(
            nd,
            "get_negotiation_chat_details",
            lambda *_args, **_kwargs: {"transcript": "chat", "summary": "summary", "deal_value": 14.0},
        )
        monkeypatch.setattr(
            nd,
            "get_group_values",
            lambda _game_id, _class, group_id: (
                {"minimizer_value": 7.0, "maximizer_value": 22.0}
                if str(group_id) == "3"
                else {"minimizer_value": 9.0, "maximizer_value": 24.0}
            ),
        )
        monkeypatch.setattr(nd, "extract_summary_from_transcript", lambda *_args, **_kwargs: ("summary", 14.0))
        monkeypatch.setattr(nd.st, "expander", _fake_expander)
        monkeypatch.setattr(nd.st, "subheader", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "write", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "info", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "text_area", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "slider", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "caption", lambda text, *_args, **_kwargs: captions.append(text))
        monkeypatch.setattr(nd.st, "columns", lambda n: [_FakeColumn() for _ in range(n)])

        nd.render_matchup_chats(
            game_id=1,
            round_number=2,
            class_1="T",
            team_1=1,
            class_2="T",
            team_2=3,
            score_team1_role1=0.47,
            score_team2_role2=0.53,
            score_team1_role2=0.47,
            score_team2_role1=0.53,
            name_roles_1="Buyer",
            name_roles_2="Seller",
            summary_termination_message="Agreed value:",
            transcript_key_prefix="test",
            focus_class="T",
            focus_group="3",
            viewer_label="You",
        )

        assert "You (Buyer) extracted 53% of the negotiation margin." in captions

    @pytest.mark.unit
    def test_render_matchup_chats_keeps_buyer_first_expander_order(self, monkeypatch):
        expander_labels = []

        @contextmanager
        def _capture_expander(label, **_kwargs):
            expander_labels.append(label)
            yield

        monkeypatch.setattr(
            nd,
            "get_negotiation_chat_details",
            lambda *_args, **_kwargs: {"transcript": "chat", "summary": "summary", "deal_value": 14.0},
        )
        monkeypatch.setattr(
            nd,
            "get_group_values",
            lambda *_args, **_kwargs: {"minimizer_value": 7.0, "maximizer_value": 22.0},
        )
        monkeypatch.setattr(nd, "extract_summary_from_transcript", lambda *_args, **_kwargs: ("summary", 14.0))
        monkeypatch.setattr(nd.st, "expander", _capture_expander)
        monkeypatch.setattr(nd.st, "subheader", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "write", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "info", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "text_area", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "slider", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "caption", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "columns", lambda n: [_FakeColumn() for _ in range(n)])
        monkeypatch.setattr(nd.st, "markdown", lambda *_args, **_kwargs: None)

        nd.render_matchup_chats(
            game_id=1,
            round_number=1,
            class_1="T",
            team_1=3,
            class_2="T",
            team_2=1,
            score_team1_role1=0.53,
            score_team2_role2=0.47,
            score_team1_role2=0.53,
            score_team2_role1=0.47,
            name_roles_1="Buyer",
            name_roles_2="Seller",
            summary_termination_message="Agreed value:",
            transcript_key_prefix="test_order",
            focus_class="T",
            focus_group=1,
            viewer_label="You",
        )

        assert expander_labels[0] == "**Buyer chat (vs Class T • Group 3)**"

    @pytest.mark.unit
    def test_render_matchup_chats_seller_caption_uses_seller_score(self, monkeypatch):
        captions = []

        monkeypatch.setattr(
            nd,
            "get_negotiation_chat_details",
            lambda *_args, **_kwargs: {"transcript": "chat", "summary": "summary", "deal_value": 17.0},
        )
        monkeypatch.setattr(
            nd,
            "get_group_values",
            lambda *_args, **_kwargs: {"minimizer_value": 7.0, "maximizer_value": 16.0},
        )
        monkeypatch.setattr(nd, "extract_summary_from_transcript", lambda *_args, **_kwargs: ("summary", 17.0))
        monkeypatch.setattr(nd.st, "expander", _fake_expander)
        monkeypatch.setattr(nd.st, "subheader", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "write", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "info", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "text_area", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "slider", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "caption", lambda text, *_args, **_kwargs: captions.append(text))
        monkeypatch.setattr(nd.st, "columns", lambda n: [_FakeColumn() for _ in range(n)])
        monkeypatch.setattr(nd.st, "markdown", lambda *_args, **_kwargs: None)

        nd.render_matchup_chats(
            game_id=1,
            round_number=2,
            class_1="T",
            team_1=1,
            class_2="T",
            team_2=2,
            score_team1_role1=0.0,
            score_team2_role2=1.0,
            score_team1_role2=1.0,
            score_team2_role1=0.0,
            name_roles_1="Buyer",
            name_roles_2="Seller",
            summary_termination_message="Agreed value:",
            transcript_key_prefix="seller_score",
            focus_class="T",
            focus_group=2,
            viewer_label="You",
        )

        assert "You (Seller) extracted 100% of the negotiation margin." in captions
