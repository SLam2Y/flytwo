from functools import wraps

from aiogram import types

from dal import DataAccessLayer
from logs import logger


def maintainer_only(func):
    @wraps(func)
    async def wrapper(message: types.Message):
        maintainer_tg_id = await DataAccessLayer.get_setting('MAINTAINER_TG_ID')

        logger.debug(
            'maintainer_tg_id: |%s|, message.chat.id: |%s|, %s',
            maintainer_tg_id,
            str(message.chat.id),
            maintainer_tg_id != str(message.chat.id),
        )
        if maintainer_tg_id != str(message.chat.id):
            return None

        return await func(message)

    return wrapper
