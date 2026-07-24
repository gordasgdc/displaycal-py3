from DisplayCAL import network


def test_get_network_addr():
    addr = network.get_network_addr()
    assert isinstance(addr, str)
    parts = addr.split(".")
    assert len(parts) == 4
    for part in parts:
        assert part.isdigit()
        num = int(part)
        assert 0 <= num <= 255


def test_dns_server_addr():
    assert network.DNS_SERVER_IP_ADDR == "8.8.8.8"


def test_dns_server_port():
    assert network.DNS_SERVER_PORT == 53
