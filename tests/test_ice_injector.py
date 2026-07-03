from catvnc.config import Settings
from catvnc.ice_injector import ORIGINAL_STUN_ONLY, build_ice_servers_literal, inject_turn


def _s(**kw):
    return Settings(
        turn_host="1.2.3.4",
        turn_port=3478,
        turn_username="u",
        turn_credential="p",
        stun_urls="stun:stun.chat.bilibili.com:3478,stun:stun.l.google.com:19302",
        **kw,
    )


def test_literal_contains_both_stun_entries():
    lit = build_ice_servers_literal(_s())
    assert '{urls:"stun:stun.chat.bilibili.com:3478"}' in lit
    assert '{urls:"stun:stun.l.google.com:19302"}' in lit


def test_literal_contains_turn_udp_and_tcp():
    lit = build_ice_servers_literal(_s())
    assert '{urls:"turn:1.2.3.4:3478?transport=udp",username:"u",credential:"p"}' in lit
    assert '{urls:"turn:1.2.3.4:3478?transport=tcp",username:"u",credential:"p"}' in lit


def test_inject_replaces_stun_only_literal():
    js = 'var x=1;' + ORIGINAL_STUN_ONLY + ';var y=2;'
    out, did = inject_turn(js, _s())
    assert did is True
    assert ORIGINAL_STUN_ONLY not in out
    assert 'turn:1.2.3.4' in out
    assert out.startswith('var x=1;')
    assert out.endswith(';var y=2;')


def test_inject_noop_when_literal_absent():
    js = 'var x=1; iceServers:[{urls:"stun:other"}];'
    out, did = inject_turn(js, _s())
    assert did is False
    assert out == js
