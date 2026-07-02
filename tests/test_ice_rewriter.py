from catvnc.ice_rewriter import rewrite_candidate, rewrite_ips_in_text, rewrite_sdp

PUB = "123.124.217.250"


def test_rewrite_10_range():
    assert rewrite_ips_in_text("10.213.240.81", PUB) == PUB


def test_rewrite_192_168():
    assert rewrite_ips_in_text("192.168.1.124", PUB) == PUB


def test_rewrite_172_16_31():
    for octet in [16, 20, 31]:
        assert rewrite_ips_in_text(f"172.{octet}.5.9", PUB) == PUB


def test_do_not_rewrite_172_15_or_32():
    # 172.15 and 172.32 are NOT in the private range
    assert rewrite_ips_in_text("172.15.5.9", PUB) == "172.15.5.9"
    assert rewrite_ips_in_text("172.32.5.9", PUB) == "172.32.5.9"


def test_do_not_rewrite_public_ip():
    assert rewrite_ips_in_text("8.8.8.8", PUB) == "8.8.8.8"
    assert rewrite_ips_in_text("39.106.125.238", PUB) == "39.106.125.238"


def test_rewrite_link_local():
    assert rewrite_ips_in_text("169.254.1.2", PUB) == PUB


def test_rewrite_cgnat():
    assert rewrite_ips_in_text("100.64.0.1", PUB) == PUB
    assert rewrite_ips_in_text("100.127.255.255", PUB) == PUB
    # 100.63 and 100.128 are NOT CGNAT
    assert rewrite_ips_in_text("100.63.0.1", PUB) == "100.63.0.1"
    assert rewrite_ips_in_text("100.128.0.1", PUB) == "100.128.0.1"


def test_rewrite_candidate_line():
    original = (
        "candidate:842163049 1 udp 1677729535 192.168.1.124 55321 "
        "typ srflx raddr 10.213.240.81 rport 55321 generation 0"
    )
    expected = (
        f"candidate:842163049 1 udp 1677729535 {PUB} 55321 "
        f"typ srflx raddr {PUB} rport 55321 generation 0"
    )
    assert rewrite_candidate(original, PUB) == expected


def test_rewrite_sdp_blob():
    sdp = (
        "v=0\r\n"
        "o=- 1 2 IN IP4 10.213.240.81\r\n"
        "c=IN IP4 10.213.240.81\r\n"
        "a=candidate:1 1 udp 2130706431 192.168.1.124 5000 typ host\r\n"
        "a=candidate:2 1 udp 1694498815 10.213.240.81 5001 typ srflx\r\n"
    )
    out = rewrite_sdp(sdp, PUB)
    assert "10.213.240.81" not in out
    assert "192.168.1.124" not in out
    assert out.count(PUB) == 4


def test_multiple_matches_in_one_string():
    text = "peer 10.0.0.1 talking to 192.168.1.1 via 172.20.0.5"
    out = rewrite_ips_in_text(text, PUB)
    assert out == f"peer {PUB} talking to {PUB} via {PUB}"


def test_port_numbers_not_matched():
    # Ports and other numbers should be untouched
    text = "candidate 10.0.0.1 55321 typ host"
    out = rewrite_ips_in_text(text, PUB)
    assert "55321" in out
    assert out == f"candidate {PUB} 55321 typ host"
