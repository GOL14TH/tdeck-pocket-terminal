from tdeck_companion.protocol import *

def test_roundtrip_and_reassembly():
    p = encode_command_request("uptime", "--pretty")
    assert decode_command_request(p) == ("uptime", "--pretty")
    frames = chunk_payload(Kind.COMMAND_RESULT, 3, 99, b"x" * 777, 100)
    r = Reassembler()
    out = None
    for raw in reversed(frames):
        out = r.ingest(decode_frame(raw)) or out
    assert out == b"x" * 777

def test_crc_reject():
    b = bytearray(chunk_payload(Kind.COMMAND_ACK, 1, 5, b"abc")[0])
    b[-1] ^= 1
    try:
        decode_frame(bytes(b))
        assert False
    except ValueError:
        pass
