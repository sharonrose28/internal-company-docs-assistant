from uuid import uuid4

from app.core.config import Settings
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_round_trip():
    encoded = hash_password("correct horse battery staple")
    assert encoded != "correct horse battery staple"
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)


def test_access_token_round_trip():
    settings = Settings(jwt_secret="x" * 32)
    user_id = uuid4()
    token, expires_in = create_access_token(user_id, 3, settings)
    claims = decode_access_token(token, settings)
    assert claims["sub"] == str(user_id)
    assert claims["ver"] == 3
    assert expires_in > 0
