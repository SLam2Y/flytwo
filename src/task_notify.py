import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from itertools import chain

from dateutil.rrule import rrulestr

from bot.notifier import TgBotNotifier
from cache import redis_client
from change_detector import FlightsChangeDetector
from client import Airport, Flight
from dal import DataAccessLayer
from dispatcher import dispatcher
from fetcher import FlightsFetcher


def manual_status(flights: list[Flight], changed_flights: set[Flight]) -> str | None:
    changed = [flight for flight in flights if flight in changed_flights]

    for flight in changed:
        if flight.prev_price == 0:
            flight.prev_price = None

    if any(flight.prev_price is not None for flight in changed):
        return 'Price changes 📈'
    if changed or not flights:
        return 'Found flights 🔎'
    return None


def is_due(rrule_str: str, last_notified: datetime | None) -> bool:
    if last_notified is None:
        return True
    rule = rrulestr(rrule_str, dtstart=last_notified)
    next_dt = rule.after(last_notified)
    return next_dt is not None and next_dt <= datetime.now(UTC)


async def main(chat_id: int | None = None, manual: bool = False):
    callee_chat_ids = None
    display_all = False

    if chat_id is not None:
        callee_chat_ids = [chat_id]
        chat = await DataAccessLayer.get_chat(tg_id=chat_id)

        if chat:
            display_all = not chat.less

    airport_by_code: dict[str, Airport] = await dispatcher.get_airport_by_code()

    directions_by_chats = await DataAccessLayer.get_directions_by_chats(callee_chat_ids)

    due_tg_ids: list[int] = []

    if manual and not any(directions_by_chats.values()):
        await TgBotNotifier(chat_id=chat_id).send_msgs(['No routes yet. Add one with /add'])
        return

    if chat_id is None:
        directions_by_chats = {
            chat: directions
            for chat, directions in directions_by_chats.items()
            if is_due(chat.schedule, chat.last_notified)
        }
        due_tg_ids = [chat.tg_id for chat in directions_by_chats]

    to_fetch = []
    notifiers: list[TgBotNotifier] = []
    clients = [client_cls() for client_cls in dispatcher.get_client_classes()]

    async with redis_client() as cache:
        for chat, directions in directions_by_chats.items():
            for direction in directions:
                msg_header = await TgBotNotifier.form_direction_info(direction, airport_by_code, chat.currency)

                notifier = TgBotNotifier(
                    chat_id=chat.tg_id,
                    price_limit=Decimal(direction.price),
                    msg_header=msg_header,
                    notify_on_decrease=direction.notify_on_decrease,
                    threshold=direction.threshold,
                    currency=chat.currency,
                )
                notifiers.append(notifier)

                for client in clients:
                    to_fetch.append(FlightsFetcher.fetch_flights(direction, notifier, cache, client))

    results = await asyncio.gather(*to_fetch)
    results = [result for result in results if result is not None]

    fetched_flights: list[Flight] = []

    for result in results:
        forwards, backwards, _ = result

        fetched_flights.extend(forwards)
        fetched_flights.extend(backwards)

    changed_flights: set[Flight] = set(await FlightsChangeDetector.get_changed_flights(fetched_flights, manual))

    flights_by_notifier: dict[TgBotNotifier, tuple[list[Flight], list[Flight]]] = {}

    for result in results:
        forwards, backwards, notifier = result
        if notifier not in flights_by_notifier:
            flights_by_notifier[notifier] = ([], [])

        fwd, bwd = flights_by_notifier[notifier]
        fwd.extend(forwards)
        bwd.extend(backwards)

    msgs_by_notifier: dict[TgBotNotifier, list[str]] = defaultdict(list)

    if manual:
        for notifier in notifiers:
            if notifier not in flights_by_notifier:
                msgs_by_notifier[notifier].append('Could not check prices right now, try again later ⚠️')

    for notifier, (forwards, backwards) in flights_by_notifier.items():
        forwards.sort()
        backwards.sort()

        flights = [
            flight
            for flight in chain(forwards, backwards)
            if notifier.price_limit is None or flight.price <= notifier.price_limit
        ]

        if manual:
            title = manual_status([*forwards, *backwards], changed_flights)

            if title is None:
                msgs_by_notifier[notifier].append('No price changes since the last check ✅')
                continue

            forward_msg, backward_msg = await asyncio.gather(notifier.form_msg(forwards), notifier.form_msg(backwards))
            msgs_by_notifier[notifier].append(
                f'{title}\n\nForward flights 🛫:\n{forward_msg}\n\nBackward flights 🛬:\n{backward_msg}'
            )
            continue

        if display_all or any(
            flight in changed_flights
            and abs(flight.price - flight.prev_price) >= notifier.threshold
            and (
                notifier.notify_on_decrease is None or (flight.price < flight.prev_price) == notifier.notify_on_decrease
            )
            for flight in flights
        ):
            forward_msg, backward_msg = await asyncio.gather(notifier.form_msg(forwards), notifier.form_msg(backwards))

            msg = f'Forward flights 🛫:\n{forward_msg}\n\nBackward flights 🛬:\n{backward_msg}'

            msgs_by_notifier[notifier].append(msg)

    await asyncio.gather(*[notifier.send_msgs(msgs) for notifier, msgs in msgs_by_notifier.items()])

    if due_tg_ids:
        await DataAccessLayer.update_last_notified(due_tg_ids)


if __name__ == '__main__':
    asyncio.run(main())
