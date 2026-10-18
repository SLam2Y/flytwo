from datetime import date
from decimal import Decimal

from client import Airport, Flight
from task_notify import manual_status


def make_flight(day: int, price: int, prev_price: int | None = None) -> Flight:
    return Flight(
        from_airport=Airport(code='RMO'),
        to_airport=Airport(code='EVN'),
        travel_date=date(day=day, month=11, year=2026),
        currency='EUR',
        price=Decimal(price),
        airline='flyone',
        prev_price=None if prev_price is None else Decimal(prev_price),
    )


def test_manual_status_new_route():
    flight = make_flight(1, 100, prev_price=0)
    assert manual_status([flight], {flight}) == 'Found flights 🔎'
    assert flight.prev_price is None


def test_manual_status_price_changed():
    changed = make_flight(1, 90, prev_price=100)
    new = make_flight(2, 120, prev_price=0)
    assert manual_status([changed, new], {changed, new}) == 'Price changes 📈'


def test_manual_status_no_changes():
    assert manual_status([make_flight(1, 100)], set()) is None


def test_manual_status_nothing_found():
    assert manual_status([], set()) == 'Found flights 🔎'
