"""FastMCP server that mirrors the flytwo API.

Every tool is a thin proxy over the FastAPI service (see ``api/api.py``), so all
validation and business logic stays in one place. Endpoints that require a user
(JWT protected) accept a ``token`` argument; when omitted the bearer token is
read from the incoming ``Authorization`` header instead, so a client configured
with a static bearer token works without passing it on every call.
"""

from datetime import date
from typing import Annotated, Any, Literal

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers
from pydantic import Field

from api.models import (
    ChatInfo,
    ConvertResponse,
    CurrencyInfo,
    LinkResponse,
    MessageResponse,
    PromoFare,
    ScheduleResponse,
    SilentResponse,
    UserDirection,
)
from conf import MCP_API_BASE, MCP_HOST, MCP_PATH, MCP_PORT

INSTRUCTIONS = """\
Tools for the flytwo flight price tracker, mirroring its HTTP API.

Public tools need no auth: price_history, list_airports, list_currencies, get_link.
All other tools act on a specific user and require a bearer token, either passed
as the `token` argument or sent as an `Authorization: Bearer <jwt>` header.
Airport codes are 3-letter IATA codes; dates are ISO `YYYY-MM-DD`.
"""

mcp = FastMCP(name='flytwo', instructions=INSTRUCTIONS)


def _bearer(token: str | None) -> str:
    """Resolve the bearer token from the explicit arg or the request header."""
    if not token:
        header = get_http_headers().get('authorization', '')
        token = header[7:] if header.lower().startswith('bearer ') else header
    if not token:
        raise ToolError('Authentication required: pass `token` or send an Authorization: Bearer header.')
    return token


async def _call(
    method: str,
    path: str,
    *,
    token: str | None = None,
    auth: bool = False,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> Any:
    """Proxy a request to the API and return its JSON body (or None for empty responses)."""
    headers = {'Authorization': f'Bearer {_bearer(token)}'} if auth else {}
    clean_params = {k: v for k, v in (params or {}).items() if v is not None}

    try:
        async with httpx.AsyncClient(base_url=MCP_API_BASE, timeout=60) as client:
            resp = await client.request(method, path, headers=headers, params=clean_params, json=json)
    except httpx.RequestError as e:
        raise ToolError(f'Could not reach the flytwo API: {e}')

    if resp.is_success:
        return resp.json() if resp.content else None

    try:
        detail = resp.json().get('detail', resp.text)
    except ValueError:
        detail = resp.text
    raise ToolError(f'API error {resp.status_code}: {detail}')


# --- Public tools (no auth) ------------------------------------------------


@mcp.tool
async def price_history(
    src: Annotated[str, Field(description='3-letter origin airport code, e.g. RMO')],
    dst: Annotated[str, Field(description='3-letter destination airport code, e.g. EVN')],
    dt: Annotated[date | None, Field(description='Optional specific travel date to filter by')] = None,
    currency: Annotated[str | None, Field(description='Optional currency code to convert prices into')] = None,
) -> dict:
    """Price history for a src/dst direction, grouped by airline and travel date."""
    params = {'dt': dt.isoformat() if dt else None, 'currency': currency}
    return await _call('GET', f'/price-history/{src}/{dst}', params=params)


@mcp.tool
async def list_airports() -> list[dict]:
    """List every airport supported across all tracked airlines."""
    return await _call('GET', '/airports')


@mcp.tool
async def list_currencies() -> list[CurrencyInfo]:
    """List supported currencies with their symbols."""
    return [CurrencyInfo.model_validate(c) for c in await _call('GET', '/currencies')]


@mcp.tool
async def get_link(
    src: Annotated[str, Field(description='3-letter origin airport code')],
    dst: Annotated[str, Field(description='3-letter destination airport code')],
    travel_date: Annotated[date, Field(description='Travel date (YYYY-MM-DD)')],
) -> LinkResponse:
    """Build booking links for a route on every airline that serves it."""
    return LinkResponse.model_validate(await _call('GET', f'/link/{src}/{dst}/{travel_date.isoformat()}'))


# --- User tools (bearer token) ---------------------------------------------


@mcp.tool
async def list_directions(token: str | None = None) -> list[UserDirection]:
    """List the authenticated user's tracked directions."""
    return [UserDirection.model_validate(d) for d in await _call('GET', '/directions', token=token, auth=True)]


@mcp.tool
async def chat_info(token: str | None = None) -> ChatInfo:
    """Get the user's chat settings: schedule, silent mode, currency, direction count, etc."""
    return ChatInfo.model_validate(await _call('GET', '/info', token=token, auth=True))


@mcp.tool
async def add_direction(
    price: Annotated[int, Field(description='Target price threshold for notifications')],
    src: Annotated[str | None, Field(description='Origin airport code (omit if `link` is given)')] = None,
    dst: Annotated[str | None, Field(description='Destination airport code (omit if `link` is given)')] = None,
    travel_date: Annotated[date | None, Field(description='Travel date; required unless derivable from `link`')] = None,
    link: Annotated[str | None, Field(description='Supported airline URL to derive src/dst/date from')] = None,
    token: str | None = None,
) -> MessageResponse:
    """Add (or update) a tracked direction, either via explicit src/dst/date or a supported airline link."""
    body = {'price': price, 'src': src, 'dst': dst, 'link': link}
    if travel_date is not None:
        body['travel_date'] = travel_date.isoformat()
    return MessageResponse.model_validate(await _call('POST', '/directions', token=token, auth=True, json=body))


@mcp.tool
async def remove_direction(
    src: Annotated[str, Field(description='Origin airport code')],
    dst: Annotated[str, Field(description='Destination airport code')],
    token: str | None = None,
) -> MessageResponse:
    """Stop tracking a direction."""
    return MessageResponse.model_validate(await _call('DELETE', f'/directions/{src}/{dst}', token=token, auth=True))


@mcp.tool
async def update_direction(
    src: Annotated[str, Field(description='Origin airport code')],
    dst: Annotated[str, Field(description='Destination airport code')],
    notify: Annotated[
        Literal['any', 'increase', 'decrease'] | None,
        Field(description='Which price movements to notify on'),
    ] = None,
    threshold: Annotated[int | None, Field(description='New target price threshold')] = None,
    token: str | None = None,
) -> MessageResponse:
    """Update a tracked direction's notify mode and/or price threshold."""
    data = await _call(
        'PATCH', f'/directions/{src}/{dst}', token=token, auth=True, json={'notify': notify, 'threshold': threshold}
    )
    return MessageResponse.model_validate(data)


@mcp.tool
async def notify_now(token: str | None = None) -> MessageResponse:
    """Trigger an immediate price check for the user (equivalent to /go)."""
    return MessageResponse.model_validate(await _call('POST', '/go', token=token, auth=True))


@mcp.tool
async def get_schedule(token: str | None = None) -> ScheduleResponse:
    """Get the user's automatic-check schedule (rrule string, empty when disabled)."""
    return ScheduleResponse.model_validate(await _call('GET', '/schedule', token=token, auth=True))


@mcp.tool
async def set_schedule(
    pattern: Annotated[str, Field(description="Human-friendly pattern, e.g. '4h', '6pm', '8am-11pm 2h'")],
    token: str | None = None,
) -> ScheduleResponse:
    """Set the user's automatic-check schedule from a human-friendly pattern."""
    data = await _call('PUT', '/schedule', token=token, auth=True, json={'pattern': pattern})
    return ScheduleResponse.model_validate(data)


@mcp.tool
async def toggle_schedule(token: str | None = None) -> ScheduleResponse:
    """Enable/disable the user's automatic-check schedule."""
    return ScheduleResponse.model_validate(await _call('POST', '/schedule/toggle', token=token, auth=True))


@mcp.tool
async def toggle_silent(token: str | None = None) -> SilentResponse:
    """Toggles silence mode for the chat. If ON, messages will be sent only on changes."""
    return SilentResponse.model_validate(await _call('POST', '/silent/toggle', token=token, auth=True))


@mcp.tool
async def set_currency(
    currency: Annotated[str, Field(description='Currency code, e.g. EUR')],
    token: str | None = None,
) -> MessageResponse:
    """Set the user's preferred currency (only allowed with no active directions)."""
    data = await _call('PUT', '/currency', token=token, auth=True, json={'currency': currency})
    return MessageResponse.model_validate(data)


@mcp.tool
async def convert_currency(
    amount: Annotated[int, Field(description='Non-negative amount to convert', ge=0)],
    from_currency: Annotated[str, Field(description='Source currency code')],
    to_currency: Annotated[str, Field(description='Target currency code')],
    token: str | None = None,
) -> ConvertResponse:
    """Convert an amount between two currencies."""
    params = {'amount': amount, 'from_currency': from_currency, 'to_currency': to_currency}
    return ConvertResponse.model_validate(await _call('GET', '/convert', token=token, auth=True, params=params))


@mcp.tool
async def list_promo(
    src: Annotated[str, Field(description='Origin airport code')],
    travel_date: Annotated[date, Field(description='Travel date (YYYY-MM-DD)')],
    price: Annotated[int, Field(description='Maximum price to include in results')],
    token: str | None = None,
) -> list[PromoFare]:
    """Find promo fares from an origin under a max price for a given date."""
    body = {'src': src, 'travel_date': travel_date.isoformat(), 'price': price}
    return [PromoFare.model_validate(f) for f in await _call('POST', '/promo', token=token, auth=True, json=body)]


def main() -> None:
    mcp.run(transport='http', host=MCP_HOST, port=MCP_PORT, path=MCP_PATH)


if __name__ == '__main__':
    main()
