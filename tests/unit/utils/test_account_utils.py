import datetime
from time import time

from app.extensions import db
from app.models.account import AccountModel
from app.utils.account_utils import get_cooldown_for_pot


def _add(type, pot_id, cooldown_until):
    db.session.add(
        AccountModel(type=type, access_token="a", refresh_token="r", pot_id=pot_id, cooldown_until=cooldown_until)
    )
    db.session.commit()


def test_active_cooldown_is_formatted_in_utc(test_client):
    cooldown_until = int(time()) + 3600
    _add("Barclaycard", "pot_1", cooldown_until)

    expected = datetime.datetime.fromtimestamp(cooldown_until, tz=datetime.timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    assert get_cooldown_for_pot("pot_1", db.session) == expected


def test_active_cooldown_known_timestamp(test_client, mocker):
    mocker.patch("app.utils.account_utils.time.time", return_value=1_700_000_000)
    _add("Barclaycard", "pot_1", 1_700_003_600)

    assert get_cooldown_for_pot("pot_1", db.session) == "2023-11-14 23:13:20"


def test_expired_cooldown_returns_none(test_client):
    _add("Barclaycard", "pot_1", int(time()) - 1)
    assert get_cooldown_for_pot("pot_1", db.session) is None


def test_no_cooldown_returns_none(test_client):
    _add("Barclaycard", "pot_1", None)
    assert get_cooldown_for_pot("pot_1", db.session) is None


def test_unknown_pot_returns_none(test_client):
    _add("Barclaycard", "pot_1", int(time()) + 3600)
    assert get_cooldown_for_pot("pot_2", db.session) is None
