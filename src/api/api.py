from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

from aiogram import types
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache

from api import auth
from api.auth import User
from api.cache_utils import airports_key_builder, price_history_key_builder
from api.common import get_chat_or_404
from api.converters import convert_currency, convert_price_history
from api.models import (
    AirlineLink,
    ChatInfo,
    ConvertResponse,
    CreateDirectionRequest,
    CurrencyInfo,
    CurrencyRequest,
    LinkResponse,
    MessageResponse,
    NotifyMode,
    NotifyRequest,
    Ping,
    PromoFare,
    PromoRequest,
    ScheduleRequest,
    ScheduleResponse,
    SilentResponse,
    UpdateDirectionRequest,
    UserDirection,
)
from api.parsers import parse_price, parse_schedule
from api.services import DirectionManager
from api.validators import validate_airport_code, validate_currency
from bot.bot import bot, dp
from cache import redis_client
from client import Airport
from conf import BOT_SECRET, CORS_ORIGINS, DEBUG
from currency_converter import CurrencyConverter
from dal import DataAccessLayer
from dispatcher import dispatcher
from logs import logger
from plotter import PriceHistory, PricePoint
from task_notify import main as notify_main


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with redis_client() as redis_cache:
            FastAPICache.init(RedisBackend(redis_cache), prefix='api-cache')
            yield
    except Exception as e:
        logger.error(f'Error during lifespan setup: {e}')
        raise


docs_url = '/docs' if DEBUG else None
redoc_url = '/redoc' if DEBUG else None

app = FastAPI(lifespan=lifespan, docs_url=docs_url, redoc_url=redoc_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(auth.router)


@app.get('/')
async def index(user: Annotated[User, Depends(auth.get_current_user)]) -> User:
    return user


@app.get('/ping')
async def ping() -> Ping:
    return Ping(ping='pong', pong='ping')


@app.get('/directions')
async def directions(user: Annotated[User, Depends(auth.get_current_user)]) -> list[UserDirection]:
    directions_by_chats = await DataAccessLayer.get_directions_by_chats([user.chat_id])
    _, directions = next(iter(directions_by_chats.items()))

    return [UserDirection.model_validate(direction) for direction in directions]


@app.get('/price-history/{src}/{dst}', response_model=PriceHistory)
@cache(expire=300, key_builder=price_history_key_builder)
async def price_history(
    src: str,
    dst: str,
    dt: date | None = None,
    currency: str | None = None,
) -> PriceHistory:
    direction_price_history = await DataAccessLayer.get_direction_price_history(src.upper(), dst.upper(), dt)

    if currency:
        direction_price_history = await convert_price_history(direction_price_history, validate_currency(currency))

    grouped: dict[str, dict[date, list[PricePoint]]] = {}
    for key, price_points in direction_price_history.items():
        grouped.setdefault(key.airline, {})[key.travel_date] = price_points

    return PriceHistory.model_validate(grouped)


@app.get('/airports', response_model=list[Airport])
@cache(expire=3600, key_builder=airports_key_builder)  # Cache for 1 hour
async def airports() -> list[Airport]:
    """Proxy endpoint to fetch airports from all registered airlines."""
    logger.info('Fetching airports')
    airport_by_code: dict[str, Airport] = await dispatcher.get_airport_by_code()
    return list(airport_by_code.values())


@app.get('/info')
async def info(user: Annotated[User, Depends(auth.get_current_user)]) -> ChatInfo:
    directions_by_chats = await DataAccessLayer.get_directions_by_chats([user.chat_id])
    chat, directions = next(iter(directions_by_chats.items()))

    return ChatInfo(
        chat_id=str(chat.tg_id),
        schedule=chat.schedule or '',
        less=chat.less,
        last_notified=chat.last_notified,
        premium=chat.premium,
        currency=chat.currency,
        directions_count=len(directions),
    )


@app.post('/directions', status_code=status.HTTP_201_CREATED)
async def add_direction(
    request: CreateDirectionRequest,
    user: Annotated[User, Depends(auth.get_current_user)],
) -> MessageResponse:
    chat = await get_chat_or_404(user.chat_id)
    dm = DirectionManager(chat)

    resolved = await dm.resolve(link=request.link, src=request.src, dst=request.dst, travel_date=request.travel_date)
    if resolved.travel_date is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='travel_date is required.')

    price = parse_price(request.price)
    created = await dm.add(src=resolved.src, dst=resolved.dst, travel_date=resolved.travel_date, price=price)

    return MessageResponse(detail='Direction added.' if created else 'Direction updated.', created=created)


@app.delete('/directions/{src}/{dst}')
async def remove_direction(
    src: str,
    dst: str,
    user: Annotated[User, Depends(auth.get_current_user)],
) -> MessageResponse:
    chat = await get_chat_or_404(user.chat_id)
    src = validate_airport_code(src)
    dst = validate_airport_code(dst)

    deleted = await DataAccessLayer.remove_direction(chat_id=chat.id, src=src, dst=dst)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Direction not found.')

    return MessageResponse(detail='Direction removed.')


@app.patch('/directions/{src}/{dst}')
async def update_direction(
    src: str,
    dst: str,
    request: UpdateDirectionRequest,
    user: Annotated[User, Depends(auth.get_current_user)],
) -> MessageResponse:
    chat = await get_chat_or_404(user.chat_id)
    src = validate_airport_code(src)
    dst = validate_airport_code(dst)

    if request.notify is not None:
        updated = await DataAccessLayer.set_notify_on_decrease(
            chat_id=chat.id,
            src=src,
            dst=dst,
            notify_on_decrease={NotifyMode.ANY: None, NotifyMode.INCREASE: False, NotifyMode.DECREASE: True}[
                request.notify
            ],
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Direction not found.')

    if request.threshold is not None:
        threshold = parse_price(request.threshold)
        updated = await DataAccessLayer.set_threshold(chat_id=chat.id, src=src, dst=dst, threshold=threshold)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Direction not found.')

    return MessageResponse(detail='Direction updated.')


@app.post('/go', status_code=status.HTTP_202_ACCEPTED)
async def go(
    user: Annotated[User, Depends(auth.get_current_user)],
    background_tasks: BackgroundTasks,
) -> MessageResponse:
    chat = await get_chat_or_404(user.chat_id)
    background_tasks.add_task(notify_main, chat_id=chat.tg_id, manual=True)
    return MessageResponse(detail='Manual check started.')


@app.get('/schedule')
async def get_schedule(user: Annotated[User, Depends(auth.get_current_user)]) -> ScheduleResponse:
    chat = await get_chat_or_404(user.chat_id)
    return ScheduleResponse(schedule=chat.schedule or '')


@app.put('/schedule')
async def set_schedule(
    request: ScheduleRequest,
    user: Annotated[User, Depends(auth.get_current_user)],
) -> ScheduleResponse:
    chat = await get_chat_or_404(user.chat_id)
    rrule = parse_schedule(request.pattern)
    await DataAccessLayer.set_schedule(tg_id=chat.tg_id, rrule=rrule)
    return ScheduleResponse(schedule=rrule)


@app.post('/schedule/toggle')
async def toggle_schedule(user: Annotated[User, Depends(auth.get_current_user)]) -> ScheduleResponse:
    await get_chat_or_404(user.chat_id)
    schedule = await DataAccessLayer.toggle_schedule(tg_id=user.chat_id)
    return ScheduleResponse(schedule=schedule or '')


@app.post('/silent/toggle')
async def toggle_silent(user: Annotated[User, Depends(auth.get_current_user)]) -> SilentResponse:
    await get_chat_or_404(user.chat_id)
    less = await DataAccessLayer.toggle_less(tg_id=user.chat_id)
    return SilentResponse(less=bool(less))


@app.get('/currencies')
async def currencies() -> list[CurrencyInfo]:
    return [
        CurrencyInfo(code=code, symbol=CurrencyConverter.CURRENCY_SYMBOLS.get(code))
        for code in sorted(CurrencyConverter.SUPPORTED_CURRENCIES)
    ]


@app.put('/currency')
async def set_currency(
    request: CurrencyRequest,
    user: Annotated[User, Depends(auth.get_current_user)],
) -> MessageResponse:
    chat = await get_chat_or_404(user.chat_id)
    currency = validate_currency(request.currency)

    directions_by_chats = await DataAccessLayer.get_directions_by_chats([chat.tg_id])
    _, directions = next(iter(directions_by_chats.items()))
    if directions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Remove active directions before changing currency.',
        )

    await DataAccessLayer.set_currency(currency, tg_id=chat.tg_id)
    return MessageResponse(detail=f'Currency updated: {currency}')


@app.get('/convert')
async def convert(
    amount: int,
    from_currency: str,
    to_currency: str,
) -> ConvertResponse:
    if amount < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Amount must be non-negative.')
    result = await convert_currency(amount, from_currency, to_currency)
    return ConvertResponse(
        amount=amount,
        from_currency=from_currency.upper(),
        to_currency=to_currency.upper(),
        result=result,
    )


@app.post('/promo')
async def promo(
    request: PromoRequest,
    user: Annotated[User, Depends(auth.get_current_user)],
) -> list[PromoFare]:
    chat = await get_chat_or_404(user.chat_id)
    price = parse_price(request.price)
    return await DirectionManager(chat).find_promo_fares(src=request.src, travel_date=request.travel_date, price=price)


@app.get('/link/{src}/{dst}/{travel_date}')
async def link(src: str, dst: str, travel_date: date):
    airports_by_airline = await dispatcher.get_airports_by_airline()
    src, dst = src.upper(), dst.upper()

    links = {}

    for airline, airport_by_code in airports_by_airline.items():
        if src in airport_by_code and dst in airport_by_code:
            link_constructor = dispatcher.pick_constructor(airline, src, dst, travel_date)

            if not link_constructor:
                logger.warning('No constructor for %s', airline)
                continue

            links[airline] = link_constructor.construct()

    return LinkResponse(links=[AirlineLink(airline=airline, url=url) for airline, url in links.items()])


@app.post('/webhook', include_in_schema=False)
async def webhook(request: Request) -> None:
    body = await request.json()
    update = types.Update(**body)
    await dp.feed_update(bot, update)


@app.post('/notify', status_code=status.HTTP_202_ACCEPTED, include_in_schema=False)
async def notify(
    request: NotifyRequest,
    background_tasks: BackgroundTasks,
    x_notify_secret: Annotated[str, Header()],
) -> None:
    if x_notify_secret != BOT_SECRET:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid secret')
    background_tasks.add_task(notify_main, chat_id=request.chat_id, manual=request.manual)
