"""The network record: it parses the ingest address without the stream key, explains a drop in one line, and never raises."""
import socket
import threading
import time

import netwatch


def test_endpoint_never_includes_the_stream_key():
    assert netwatch.ingest_endpoint("rtmp://a.rtmp.youtube.com/live2/abcd-1234-secret") == ("a.rtmp.youtube.com", 1935)
    assert netwatch.ingest_endpoint("rtmps://a.rtmps.youtube.com:443/live2/k") == ("a.rtmps.youtube.com", 443)
    assert netwatch.ingest_endpoint("rtmps://x.example/live2/k")[1] == 443


def test_a_probe_times_a_real_connect_and_a_refusal_is_a_failed_probe_not_an_exception():
    srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1)
    port = srv.getsockname()[1]
    ok = netwatch.NetWatch("127.0.0.1", port, log=lambda m: None).probe()
    assert ok[2] is not None and ok[2] < 1000 and ok[3] is None
    srv.close()
    bad = netwatch.NetWatch("127.0.0.1", port, log=lambda m: None).probe()
    assert bad[2] is None and bad[3] and "Error" in bad[3]


def test_unusual_probes_are_logged_and_a_quiet_hour_is_not():
    logs = []
    n = netwatch.NetWatch("a.example", 1935, log=logs.append)
    now = time.time()
    n.record((now, 5.0, 3.0, None, 1000, 0)); n.record((now, 5.0, 4.0, None, 2000, 1))
    assert logs == []                                                   # healthy probes say nothing
    n.record((now, 5.0, 900.0, None, 3000, 2)); n.record((now, None, None, "gaierror: no such host", 3500, 3))
    assert any("slow connect" in l for l in logs) and any("failed" in l and "gaierror" in l for l in logs)


def test_the_summary_before_a_drop_counts_failures_and_retransmits():
    n = netwatch.NetWatch("a.example", 1935, log=lambda m: None)
    now = time.time()
    for i, (c, out, re) in enumerate([(3.0, 1000, 0), (4.0, 5000, 20), (None, 9000, 60)]):
        n.samples.append((now - 120 + i * 60, 5.0, c, None if c else "timeout", out, re))
    s = n.summary(300)
    assert "3 probes, 1 failed" in s and "connect 3-4 ms" in s and "retransmits 0.75% of 8000 segments" in s
    assert n.summary(0).endswith("no probes yet")                       # nothing that recent


def test_counters_read_from_a_proc_snmp_file(tmp_path):
    p = tmp_path / "snmp"
    p.write_text("Ip: Forwarding\nIp: 1\nTcp: RtoAlgorithm OutSegs RetransSegs\nTcp: 1 500 7\n")
    assert netwatch.tcp_counters(str(p)) == (500, 7)
    assert netwatch.tcp_counters(str(tmp_path / "missing")) is None


def test_run_stops_when_cancelled_and_survives_a_probe_error():
    logs, cancel = [], threading.Event()
    n = netwatch.NetWatch("a.example", 1935, log=logs.append, every=0.01)
    n.probe = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    t = threading.Thread(target=n.run, args=(cancel,)); t.start()
    time.sleep(0.1); cancel.set(); t.join(2)
    assert not t.is_alive() and any("network watch error" in l for l in logs)
