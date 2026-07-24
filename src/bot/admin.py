from functools import wraps

from aiogram import types

from dal import DataAccessLayer


def maintainer_only(func):
    @wraps(func)
    async def wrapper(message: types.Message):
        maintainer_tg_id = await DataAccessLayer.get_setting('MAINTAINER_TG_ID')

        if maintainer_tg_id != str(message.chat.id):
            return None

        return await func(message)

    return wrapper
