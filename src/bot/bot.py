import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from random import randint

import aiohttp
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command
from aiogram.types import (
    BotCommand,
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from bot.admin import maintainer_only
from bot.notifier import TgBotNotifier
from bot.texts import BUTTON_ACTIONS, TEXTS, t
from cache import redis_client
from client import Airport, DestinationFare, FareStats
from conf import API_URL, BOT_SECRET, BOT_TOKEN, WEBAPP_URL
from currency_converter import CurrencyConverter
from dal import DataAccessLayer
from dispatcher import dispatcher
from logs import logger
from parser import ScheduleParser
from plotter import MissingPriceHistoryError, Plotter
from price import Price

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()


def _language_code(message: types.Message) -> str | None:
    return message.from_user.language_code if message.from_user else None


def main_keyboard(language_code: str | None) -> ReplyKeyboardMarkup:
    labels = t('buttons', language_code)
    rows = [['directions', 'go'], ['stats', 'promo'], ['info', 'help'], ['app', 'stop']]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=labels[action]) for action in row] for row in rows],
        resize_keyboard=True,
        is_persistent=True,
    )


async def app_keyboard(message: types.Message) -> InlineKeyboardMarkup | None:
    if message.chat.type != 'private':
        return None

    language_code = _language_code(message)
    me = await message.bot.me()
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t('open_app', language_code), web_app=WebAppInfo(url=WEBAPP_URL))],
            [
                InlineKeyboardButton(
                    text=t('home_screen', language_code), url=f'https://t.me/{me.username}?startapp=install'
                )
            ],
        ]
    )


@router.message(Command(commands=['help']))
async def cmd_help(message: types.Message):
    await message.reply(t('help', _language_code(message)), reply_markup=await app_keyboard(message))


@router.message(Command(commands=['start']))
async def cmd_start(message: types.Message):
    _, created = await DataAccessLayer.create_chat(tg_id=message.chat.id)
    language_code = _language_code(message)

    await message.reply(
        t('start_created' if created else 'start_existing', language_code),
        reply_markup=main_keyboard(language_code),
    )

    if inline_keyboard := await app_keyboard(message):
        await message.answer(t('app_prompt', language_code), reply_markup=inline_keyboard)


@router.message(F.text.in_(BUTTON_ACTIONS))
async def on_keyboard_button(message: types.Message):
    match BUTTON_ACTIONS[message.text]:
        case 'directions':
            await cmd_directions(message)
        case 'go':
            await cmd_go(message)
        case 'info':
            await cmd_info(message)
        case 'help':
            await cmd_help(message)
        case 'app':
            await message.reply(t('app_prompt', _language_code(message)), reply_markup=await app_keyboard(message))
        case 'stop':
            language_code = _language_code(message)
            await message.reply(
                t('stop_confirm', language_code),
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(text=t('stop_yes', language_code), callback_data='stop:yes'),
                            InlineKeyboardButton(text=t('stop_no', language_code), callback_data='stop:no'),
                        ]
                    ]
                ),
            )
        case action:
            await message.reply(t(f'{action}_hint', _language_code(message)))


@router.callback_query(F.data.in_({'stop:yes', 'stop:no'}))
async def on_stop_confirm(callback: types.CallbackQuery):
    if callback.data == 'stop:no':
        text = t('stop_cancelled', callback.from_user.language_code)
    else:
        deleted = await DataAccessLayer.remove_chat(tg_id=callback.message.chat.id)
        text = 'Bot stopped!' if deleted else 'Bot is already stopped.'

    await callback.message.edit_text(text)
    await callback.answer()


@router.message(Command(commands=['stop']))
async def cmd_stop(message: types.Message):
    deleted = await DataAccessLayer.remove_chat(tg_id=message.chat.id)

    if deleted:
        await message.reply('Bot stopped!')
    else:
        await message.reply('Bot is already stopped.')


@router.message(Command(commands=['add']))
async def cmd_add(message: types.Message):
    command_parts = message.text.split()

    if len(command_parts) == 3:
        parser = dispatcher.pick_parser(command_parts[1])
        if parser is None:
            await message.reply('Unrecognized link. Please use a supported airline URL or enter airports manually.')
            return
        src, dst, travel_date_str = parser.parse()
        command_parts = [command_parts[0], src, dst, travel_date_str, command_parts[2]]

    if len(command_parts) != 5:
        await message.reply(t('add_hint', _language_code(message)))
        return

    _, src, dst, travel_date_str, price_str = command_parts

    src = src.upper()
    dst = dst.upper()

    if src == dst:
        await message.reply('Source cannot be the same as destination.')
        return

    try:
        travel_date = datetime.strptime(travel_date_str, '%d.%m.%Y').date()
    except ValueError:
        await message.reply('Invalid travel date format. Please use DD.MM.YYYY')
        return

    try:
        price = Price(price_str)
    except ValueError:
        await message.reply('Invalid price. Please provide a whole positive number.')
        return

    if any(filter(lambda elem: len(elem) != 3, (src, dst))):
        await message.reply('Invalid airport code! Should be 3 letters.')
        return

    airport_by_code: dict[str, Airport] = await dispatcher.get_airport_by_code()

    if src not in airport_by_code or dst not in airport_by_code:
        await message.reply('Airport not supported. Find supported airports using /airports')
        return

    chat = await DataAccessLayer.get_chat(tg_id=message.chat.id)

    if chat is None:
        await message.reply('Bot was not started yet!')
        return

    directions_by_chats = await DataAccessLayer.get_directions_by_chats([message.chat.id])
    _, directions = next(iter(directions_by_chats.items()))

    is_new_direction = not any(direction.src == src and direction.dst == dst for direction in directions)
    limit = 10 if chat.premium else 5

    if is_new_direction and len(directions) >= limit:
        err_msg = f'You have reached the limit of {limit} active directions. Use /remove'
        if not chat.premium:
            err_msg += ' or upgrade to premium.'

        await message.reply(err_msg)
        return

    _, created = await DataAccessLayer.create_direction(
        chat_id=chat.id, src=src, dst=dst, travel_date=travel_date, price=price
    )

    if created:
        await message.reply('New direction has been added.')
    else:
        await message.reply('Direction has been updated.')


@router.message(Command(commands=['remove']))
async def cmd_remove(message: types.Message):
    command_parts = message.text.split()

    if len(command_parts) == 2:
        parser = dispatcher.pick_parser(command_parts[1])
        if parser is None:
            await message.reply('Unrecognized link. Please use a supported airline URL or enter airports manually.')
            return
        src, dst, _ = parser.parse()
        command_parts = [command_parts[0], src, dst]

    if len(command_parts) != 3:
        await message.reply(t('remove_hint', _language_code(message)))
        return

    _, src, dst = command_parts

    src = src.upper()
    dst = dst.upper()

    if src == dst:
        await message.reply('Source cannot be the same as destination.')
        return

    if any(filter(lambda elem: len(elem) != 3, (src, dst))):
        await message.reply('Invalid airport code! Should be 3 letters.')

    chat = await DataAccessLayer.get_chat(tg_id=message.chat.id)

    if chat is None:
        await message.reply('Bot was not started yet!')
        return

    deleted = await DataAccessLayer.remove_direction(chat_id=chat.id, src=src, dst=dst)

    if deleted:
        await message.reply('Direction has been removed.')
    else:
        await message.reply('Direction was not found.')


@router.message(Command(commands=['go']))
async def cmd_go(message: types.Message):
    await message.reply('Manual launch started ...')
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f'{API_URL}/notify',
            json={'chat_id': message.chat.id, 'manual': True},
            headers={'x-notify-secret': BOT_SECRET},
        ),
    ):
        ...
    await message.reply('Manual launch finished!')


@router.message(Command(commands=['schedule']))
async def cmd_schedule(message: types.Message):
    command_parts = message.text.split(maxsplit=1)

    if len(command_parts) == 1:
        schedule = await DataAccessLayer.toggle_schedule(tg_id=message.chat.id)

        if schedule is None:
            await message.reply('Bot was not started yet!')
            return

        await message.reply(f'Schedule: {schedule or "OFF"}')
        return

    rrule = ScheduleParser.parse(command_parts[1])

    if rrule is None:
        await message.reply(
            'Invalid format. Examples:\n'
            '  1h          every hour\n'
            '  4h          every 4 hours\n'
            '  6pm         daily at 6pm\n'
            '  8am-11pm    every hour from 8am to 11pm\n'
            '  8am-11pm 2h every 2 hours from 8am to 11pm'
        )
        return

    updated = await DataAccessLayer.set_schedule(tg_id=message.chat.id, rrule=rrule)

    if not updated:
        await message.reply('Bot was not started yet!')
        return

    await message.reply(f'Schedule enabled: {command_parts[1].strip()}')


@router.message(Command(commands=['less']))
async def cmd_less(message: types.Message):
    schedule = await DataAccessLayer.toggle_less(tg_id=message.chat.id)

    if schedule is None:
        await message.reply('Bot was not started yet!')
        return

    await message.reply(f'Silent mode: {"ON" if schedule else "OFF"}')


@router.message(Command(commands=['auth']))
async def cmd_auth(message: types.Message):
    otp = randint(100000, 999999)  # 6-digit code - one time password

    async with redis_client() as cache:
        await cache.set(f'otp:{message.chat.id}', otp, ex=180)  # code expires in 3 minutes

    await message.reply(f"Chat ID: {message.chat.id}\nCode: {otp}\n\nDon't share this information with anyone!")


@router.message(Command(commands=['info']))
async def cmd_info(message: types.Message):
    directions_by_chats = await DataAccessLayer.get_directions_by_chats([message.chat.id])

    if not directions_by_chats:
        await message.reply('Bot was not started yet!')
        return

    chat, directions = next(iter(directions_by_chats.items()))

    await message.reply(
        f'Chat ID: {chat.tg_id}\n'
        f'Schedule: {chat.schedule or "OFF"}\n'
        f'Silent mode: {"ON" if chat.less else "OFF"}\n'
        f'Last notified: {chat.last_notified.strftime("%Y-%m-%d %H:%M:%S") if chat.last_notified else "never"}\n'
        f'Directions: {len(directions)}\n'
        f'Premium: {"ON" if chat.premium else "OFF"}\n'
    )


@router.message(Command(commands=['directions']))
async def cmd_directions(message: types.Message):
    directions_by_chats = await DataAccessLayer.get_directions_by_chats([message.chat.id])

    if not directions_by_chats:
        await message.reply('Bot was not started yet!')
        return

    chat, directions = next(iter(directions_by_chats.items()))

    if not directions:
        await message.reply('No directions found.')

    airport_by_code: dict[str, Airport] = await dispatcher.get_airport_by_code()

    msgs = []

    for direction in directions:
        msg = await TgBotNotifier.form_direction_info(direction, airport_by_code, chat.currency)
        msgs.append(msg)

    notifier = TgBotNotifier(chat_id=message.chat.id)
    await notifier.send_msgs(msgs)


@router.message(Command(commands=['airports']))
async def cmd_airports(message: types.Message):
    airport_by_code: dict[str, Airport] = await dispatcher.get_airport_by_code()

    msgs = [
        f'{code} [{airport.name}] |{airport.country}|'
        for code in sorted(iter(airport_by_code.keys()))
        if (airport := airport_by_code[code])
    ]

    chunk_size = 50  # tg api holds connection until timeout if message is too long
    chunks = ['\n'.join(msgs[i : i + chunk_size]) for i in range(0, len(msgs), chunk_size)]

    notifier = TgBotNotifier(chat_id=message.chat.id)
    for chunk in chunks:
        # deliberately send sequentially to keep the alphabetical order of airport codes
        await notifier.send_msgs([chunk])


@router.message(Command(commands=['stats']))
async def cmd_stats(message: types.Message):
    command_parts = message.text.split()

    dt_fmt = '%d.%m.%Y'

    dt = None

    match len(command_parts):
        case 3:
            _, src, dst = command_parts

        case 4:
            _, src, dst, dt = command_parts

        case _:
            await message.reply(t('stats_hint', _language_code(message)))
            return

    src = src.upper()
    dst = dst.upper()

    if dt:
        try:
            dt = datetime.strptime(dt, dt_fmt).date()
        except ValueError:
            await message.reply('Invalid date format. Please use DD.MM.YYYY')
            return

    if src == dst:
        await message.reply('Source cannot be the same as destination.')
        return

    chat = await DataAccessLayer.get_chat(tg_id=message.chat.id)

    if chat is None:
        await message.reply('Bot was not started yet!')
        return

    price_history = await DataAccessLayer.get_direction_price_history(src, dst, dt)

    async with aiohttp.ClientSession() as session, redis_client() as cache:
        converter = CurrencyConverter(session, cache)

        try:
            buffer = await Plotter.plot_price_history(src, dst, price_history, chat.currency, converter)
        except MissingPriceHistoryError as e:
            tg_notifier = TgBotNotifier(chat_id=message.chat.id)
            await tg_notifier.send_err(f'{e}')
            return

    chart_image = BufferedInputFile(buffer.read(), filename='price_chart.png')
    buffer.close()

    on_dt = f'on {dt.strftime(dt_fmt)}' if dt else ''

    await message.answer_photo(photo=chart_image, caption=f'Price History for {src} → {dst} {on_dt}'.strip())


@router.message(Command(commands=['notify']))
async def cmd_notify(message: types.Message):
    command_parts = message.text.split()

    if len(command_parts) not in (3, 4):
        await message.reply(t('notify_hint', _language_code(message)))
        return

    notify_on_decrease: bool | None = None

    if len(command_parts) == 4:
        _, src, dst, symbol = command_parts
        if symbol == '+':
            notify_on_decrease = False
        elif symbol == '-':
            notify_on_decrease = True
        else:
            await message.reply('Invalid symbol. Use + for increase, - for decrease, or omit for any change.')
            return
    else:
        _, src, dst = command_parts

    src = src.upper()
    dst = dst.upper()

    if src == dst:
        await message.reply('Source cannot be the same as destination.')
        return

    if any(filter(lambda elem: len(elem) != 3, (src, dst))):
        await message.reply('Invalid airport code! Should be 3 letters.')
        return

    chat = await DataAccessLayer.get_chat(tg_id=message.chat.id)

    if chat is None:
        await message.reply('Bot was not started yet!')
        return

    updated = await DataAccessLayer.set_notify_on_decrease(
        chat_id=chat.id, src=src, dst=dst, notify_on_decrease=notify_on_decrease
    )

    if not updated:
        await message.reply('Direction not found. Add it first with /add')
        return

    labels = {None: 'any change', False: 'price increase only', True: 'price decrease only'}
    await message.reply(f'Notification preference updated: {labels[notify_on_decrease]}')


@router.message(Command(commands=['threshold']))
async def cmd_threshold(message: types.Message):
    command_parts = message.text.split()

    if len(command_parts) != 4:
        await message.reply(t('threshold_hint', _language_code(message)))
        return

    _, src, dst, value_str = command_parts

    src = src.upper()
    dst = dst.upper()

    if src == dst:
        await message.reply('Source cannot be the same as destination.')
        return

    if any(filter(lambda elem: len(elem) != 3, (src, dst))):
        await message.reply('Invalid airport code! Should be 3 letters.')
        return

    try:
        threshold = Price(value_str)
    except ValueError as e:
        await message.reply(str(e))
        return

    chat = await DataAccessLayer.get_chat(tg_id=message.chat.id)

    if chat is None:
        await message.reply('Bot was not started yet!')
        return

    updated = await DataAccessLayer.set_threshold(chat_id=chat.id, src=src, dst=dst, threshold=threshold)

    if not updated:
        await message.reply('Direction not found. Add it first with /add')
        return

    await message.reply(f'Threshold updated: {threshold} {chat.currency}')


@router.message(Command(commands=['convert']))
async def cmd_convert(message: types.Message):
    args = message.text.split()[1:]

    if len(args) != 3:
        await message.reply(t('convert_hint', _language_code(message)))
        return

    amount_str, from_cur, to_cur = args
    from_cur = from_cur.upper()
    to_cur = to_cur.upper()

    if not amount_str.isdigit():
        await message.reply('Amount must be a positive integer.')
        return

    if from_cur not in CurrencyConverter.SUPPORTED_CURRENCIES:
        await message.reply(f'Unsupported currency: {from_cur}')
        return

    if to_cur not in CurrencyConverter.SUPPORTED_CURRENCIES:
        await message.reply(f'Unsupported currency: {to_cur}')
        return
    async with aiohttp.ClientSession() as session, redis_client() as cache:
        currency_converter = CurrencyConverter(session, cache)
        result = await currency_converter.convert(Decimal(amount_str), from_cur, to_cur)

    await message.reply(f'{amount_str} {from_cur} = {round(result)} {to_cur}')


@router.message(Command(commands=['currency']))
async def cmd_currency(message: types.Message):
    args = message.text.split()[1:]

    if len(args) != 1:
        await message.reply(t('currency_hint', _language_code(message)))
        return

    currency = args[0].upper()

    if currency not in CurrencyConverter.SUPPORTED_CURRENCIES:
        await message.reply(f'Unsupported currency: {currency}')
        return

    directions_by_chats = await DataAccessLayer.get_directions_by_chats([message.chat.id])

    if not directions_by_chats:
        await message.reply('Bot was not started yet!')
        return

    _, directions = next(iter(directions_by_chats.items()))

    if directions:
        await message.reply('Please /remove active directions before changing currency.')
        return

    try:
        await DataAccessLayer.set_currency(currency, tg_id=message.chat.id)
    except ValueError as e:
        await message.reply(str(e))
        return

    await message.reply(f'Currency updated: {currency}')


@router.message(Command(commands=['promo']))
async def cmd_promo(message: types.Message):
    args = message.text.split()[1:]

    if len(args) != 3:
        await message.reply(t('promo_hint', _language_code(message)))
        return

    src, travel_date_str, price_str = args

    try:
        price = Price(price_str)
    except ValueError as e:
        await message.reply(str(e))
        return

    try:
        travel_date = datetime.strptime(travel_date_str, '%d.%m.%Y').date()
    except ValueError:
        await message.reply('Invalid travel date format. Please use DD.MM.YYYY')
        return

    chat = await DataAccessLayer.get_chat(tg_id=message.chat.id)

    if chat is None:
        await message.reply('Bot was not started yet!')
        return

    airport_by_code: dict[str, Airport] = await dispatcher.get_airport_by_code()
    src = src.upper().strip()
    if src not in airport_by_code:
        await message.reply(f'Unsupported airport: {src}')
        return

    limit = 10 if chat.premium else 5

    async def process_client(client_cls) -> FareStats:
        try:
            fare = await client_cls().get_fare_stats(
                dep=src, travel_date=f'{travel_date:%Y-%m-%d}', currency=chat.currency
            )
        except Exception:
            logging.exception('%s failed to fetch fare stats', client_cls.__name__)
            raise
        return fare

    tasks = [process_client(cls) for cls in dispatcher.get_client_classes()]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    responses: list[FareStats] = [result for result in results if not isinstance(result, Exception)]

    notifier = TgBotNotifier(chat_id=message.chat.id)

    async with aiohttp.ClientSession() as session, redis_client() as cache:
        converter = CurrencyConverter(session, cache)

        fares: list[tuple[Decimal, DestinationFare]] = []

        for response in responses:
            for fare in response.destinationFares:
                converted_price = Decimal(round(await converter.convert(fare.price, fare.currency, chat.currency)))
                if price is None or converted_price <= price:
                    fares.append((converted_price, fare))

        for n, (converted_price, fare) in enumerate(sorted(fares, key=lambda x: x[0]), start=1):
            if n > limit:
                break

            msg = await notifier.form_fare_info(
                src,
                fare,
                airport_by_code,
                chat.currency,
                travel_date,
                converted_price,
            )
            await notifier.send_msgs([msg])  # sync to keep order


@router.message(Command(commands=['link']))
async def cmd_link(message: types.Message):
    args = message.text.split()[1:]

    if len(args) != 3:
        await message.reply(t('link_hint', _language_code(message)))
        return

    src, dst, travel_date_str = args
    src, dst = src.upper(), dst.upper()

    try:
        travel_date = datetime.strptime(travel_date_str, '%d.%m.%Y').date()
    except ValueError:
        await message.reply('Invalid travel date format. Please use DD.MM.YYYY')
        return

    airports_by_airline = await dispatcher.get_airports_by_airline()

    links = []

    for airline, airport_by_code in airports_by_airline.items():
        if src in airport_by_code and dst in airport_by_code:
            link_constructor = dispatcher.pick_constructor(airline, src, dst, travel_date)

            if not link_constructor:
                logger.warning('No constructor for %s', airline)
                continue

            links.append(link_constructor.construct())

    if not links:
        await message.reply('No links found!')
    else:
        await message.reply('\n\n'.join(links))


@router.message(Command(commands=['set']))
@maintainer_only
async def cmd_set(message: types.Message):
    args = message.text.split()[1:]

    if len(args) != 2:
        await message.reply('Usage: /set <name> <value>')
        return

    name, value = args

    await DataAccessLayer.set_setting(name, value)
    await message.reply('Success!')


@router.message(Command(commands=['get']))
@maintainer_only
async def cmd_get(message: types.Message):
    args = message.text.split()[1:]

    if len(args) != 1:
        await message.reply('Usage: /get <name>')
        return

    name = args[0]

    try:
        value = await DataAccessLayer.get_setting(name)
    except KeyError:
        await message.reply('No setting found for %s', name)
        return

    await message.reply(value)


dp.include_router(router)


async def setup_profile():
    for code, texts in TEXTS.items():
        language_code = None if code == 'en' else code
        await bot.set_my_commands(
            [BotCommand(command=command, description=text) for command, text in texts['commands'].items()],
            language_code=language_code,
        )
        await bot.set_my_description(texts['description'], language_code=language_code)
        await bot.set_my_short_description(texts['short_description'], language_code=language_code)


async def main():
    await setup_profile()
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
