from app.runtime_config import (
    DEFAULT_ALLOWED_ORIGINS,
    get_allowed_origins,
    get_private_lan_origin_regex,
    is_private_lan_origin,
)


def test_default_origins_are_local_only(
    monkeypatch,
):
    monkeypatch.delenv(
        "TRUSTSCOPE_ALLOWED_ORIGINS",
        raising=False,
    )

    assert get_allowed_origins() == list(
        DEFAULT_ALLOWED_ORIGINS
    )


def test_configured_origins_are_trimmed_and_deduplicated(
    monkeypatch,
):
    monkeypatch.setenv(
        "TRUSTSCOPE_ALLOWED_ORIGINS",
        (
            "https://app.example.com/, "
            "https://app.example.com,"
            "https://review.example.com"
        ),
    )

    assert get_allowed_origins() == [
        "https://app.example.com",
        "https://review.example.com",
    ]


def test_private_lan_contract_accepts_only_private_hosts():
    assert is_private_lan_origin(
        "http://192.168.1.42:5173"
    )
    assert is_private_lan_origin(
        "http://10.0.0.8:4173"
    )
    assert is_private_lan_origin(
        "https://172.20.2.3"
    )
    assert not is_private_lan_origin(
        "https://example.com"
    )
    assert not is_private_lan_origin(
        "http://192.168.example.com"
    )


def test_private_lan_access_can_be_disabled(
    monkeypatch,
):
    monkeypatch.setenv(
        "TRUSTSCOPE_ALLOW_PRIVATE_LAN",
        "false",
    )

    assert get_private_lan_origin_regex() is None
