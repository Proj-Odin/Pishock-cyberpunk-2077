from middleware.security import compute_signature, verify_signature


def test_signature_roundtrip() -> None:
    body = b'{"event_type":"player_damaged"}'
    sig = compute_signature("secret", body)
    assert verify_signature("secret", body, sig)
    assert not verify_signature("wrong", body, sig)
