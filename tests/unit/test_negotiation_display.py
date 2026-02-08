import os
import sys
from contextlib import contextmanager

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "streamlit"))

from modules import negotiation_display as nd  # noqa: E402


class _FakeColumn:
    def __init__(self):
        self.metrics = []

    def metric(self, label, value):
        self.metrics.append((label, value))


@contextmanager
def _fake_expander(*args, **kwargs):
    yield


class TestRenderChatSummary:
    @pytest.mark.unit
    def test_no_valid_agreement_displays_none_agreed_value(self, monkeypatch):
        infos = []
        columns = [_FakeColumn(), _FakeColumn(), _FakeColumn()]

        monkeypatch.setattr(nd.st, "subheader", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "write", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "info", lambda text: infos.append(text))
        monkeypatch.setattr(nd.st, "columns", lambda n: columns)
        monkeypatch.setattr(nd.st, "caption", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "text_area", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "expander", _fake_expander)

        nd.render_chat_summary(
            summary_text="Some summary",
            deal_value=-1,
            score_role1=-1,
            score_role2=-1,
            role1_label="Buyer",
            role2_label="Seller",
            transcript="chat",
        )

        assert "No valid agreement detected." in infos
        assert columns[0].metrics == [("Agreed Value", "None")]
        assert columns[1].metrics == [("Buyer Score", "0.0")]
        assert columns[2].metrics == [("Seller Score", "0.0")]

    @pytest.mark.unit
    def test_none_deal_value_keeps_unparsed_message(self, monkeypatch):
        infos = []

        monkeypatch.setattr(nd.st, "subheader", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "write", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "info", lambda text: infos.append(text))
        monkeypatch.setattr(nd.st, "columns", lambda n: [_FakeColumn() for _ in range(n)])
        monkeypatch.setattr(nd.st, "caption", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "text_area", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "expander", _fake_expander)

        nd.render_chat_summary(
            summary_text="Some summary",
            deal_value=None,
            score_role1=None,
            score_role2=None,
            role1_label="Buyer",
            role2_label="Seller",
            transcript="chat",
        )

        assert "No deal value could be parsed for scoring." in infos

    @pytest.mark.unit
    def test_valid_deal_value_displays_numeric_metric(self, monkeypatch):
        columns = [_FakeColumn(), _FakeColumn(), _FakeColumn()]

        monkeypatch.setattr(nd.st, "subheader", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "write", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "info", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "columns", lambda n: columns)
        monkeypatch.setattr(nd.st, "caption", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "text_area", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(nd.st, "expander", _fake_expander)

        nd.render_chat_summary(
            summary_text="Some summary",
            deal_value=42.0,
            score_role1=0.25,
            score_role2=0.75,
            role1_label="Buyer",
            role2_label="Seller",
            transcript="chat",
        )

        assert columns[0].metrics == [("Agreed Value", "42.00")]
        assert columns[1].metrics == [("Buyer Score", "25.0")]
        assert columns[2].metrics == [("Seller Score", "75.0")]
