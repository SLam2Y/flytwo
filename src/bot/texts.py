TEXTS = {
    'en': {
        'description': (
            'I track flight prices on FlyOne and Wizz Air and message you when a ticket gets cheaper '
            'or more expensive.\n\n'
            'Add a route, set your price limit and I will check it on schedule. '
            'Press Start to begin.'
        ),
        'short_description': 'Flight price tracker for FlyOne and Wizz Air. Get notified when prices change.',
        'start_created': (
            'Bot started! ✈️\n\n'
            'Add a route and I will tell you when its price changes:\n'
            '/add RMO EVN 15.10.2026 150\n\n'
            'Use the buttons below or /help for all commands.'
        ),
        'start_existing': 'Bot is already running! Use the buttons below or /help for all commands.',
        'app_prompt': 'Manage routes, charts and settings in the app:',
        'open_app': '✈️ Open app',
        'home_screen': '📲 Add to home screen',
        'stats_hint': 'Send a route to draw its price chart:\n/stats RMO EVN\n/stats RMO EVN 15.10.2026',
        'promo_hint': 'Send departure airport, date and max price to find cheap flights:\n/promo RMO 23.05.2026 150',
        'add_hint': (
            'Send airports, date and target price, or an airline link and price:\n'
            '/add RMO EVN 15.10.2026 150\n'
            '/add <link> 150'
        ),
        'remove_hint': 'Send the route to remove, or its airline link:\n/remove RMO EVN\n/remove <link>',
        'notify_hint': (
            'Choose when to notify for a route: + price up only, - price down only, nothing for any change:\n'
            '/notify RMO EVN -'
        ),
        'threshold_hint': 'Send a route and the minimum price change to notify about:\n/threshold RMO EVN 20',
        'convert_hint': 'Send an amount and two currencies:\n/convert 100 EUR MDL',
        'currency_hint': 'Send the currency code for this chat:\n/currency MDL',
        'link_hint': 'Send a route and date to get airline links:\n/link RMO EVN 23.05.2026',
        'buttons': {
            'directions': '📋 Routes',
            'go': '🔄 Check now',
            'stats': '📈 Stats',
            'promo': '🔥 Promo',
            'info': '⚙️ Settings',
            'help': '❓ Help',
            'app': '📱 Open app',
            'stop': '⏹ Stop',
        },
        'stop_confirm': 'Stop the bot? All your routes will be deleted.',
        'stop_yes': 'Yes, stop',
        'stop_no': 'Cancel',
        'stop_cancelled': 'OK, the bot keeps running.',
        'commands': {
            'start': 'Start the bot',
            'help': 'All commands',
            'directions': 'Your routes',
            'add': 'Add a route',
            'remove': 'Remove a route',
            'go': 'Check prices now',
            'stats': 'Price chart for a route',
            'promo': 'Cheap flights from an airport',
            'link': 'Airline links for a route',
            'notify': 'Notify on increase/decrease',
            'threshold': 'Minimum price change to notify',
            'schedule': 'Check schedule',
            'less': 'Silent mode',
            'currency': 'Default currency',
            'convert': 'Convert currency',
            'airports': 'Supported airports',
            'info': 'Chat settings',
            'auth': 'Login code for the app',
            'stop': 'Stop the bot',
        },
        'help': (
            'Here are the available commands:\n\n'
            '/start - Start the bot.\n\n'
            '/stop - Stop the bot.\n\n'
            '/add <src> <dst> <travel_date> <price> OR /add <link> <price> - Add a travel direction.\n'
            'Example: /add RMO EVN 15.10.2024 300\n'
            'Note: src and dst should be 3-letter airport codes. The price must be a whole number of EUR.\n\n'
            '/remove <src> <dst> OR /remove <link> - Remove a travel direction.\n'
            'Example: /remove RMO EVN\n'
            'Note: src and dst should be 3-letter airport codes.\n\n'
            '/go - Manually launch the bot.\n\n'
            '/schedule [pattern] - Toggle scheduling on/off, or set a check frequency.\n'
            'Example: /schedule to toggle, or with a pattern:\n'
            '  1h            every hour (default)\n'
            '  Nh            every N hours\n'
            '  6pm           daily at 6pm\n'
            '  8am-11pm      every hour from 8am to 11pm\n'
            '  8am-11pm 2h   every 2 hours from 8am to 11pm\n\n'
            '/less - Toggles silence mode for the chat. If ON, messages will be sent only on changes.\n\n'
            '/airports - lists all available airports by their codes.\n\n'
            '/directions - lists all directions related to the chat.\n\n'
            '/stats <src> <dst> [<date>] - draws the chart of price changes for certain direction.\n'
            'Example: /stats RMO EVN 15.10.2024\n\n'
            '/auth - returns chat id and one-time code for authorization in API.\n\n'
            '/info - returns chat specific information.\n\n'
            '/notify <src> <dst> [+|-] - Set notification preference for a direction.\n'
            'Example: /notify RMO EVN -\n'
            'Note: + for price increase only, - for price decrease only, omit for any change.\n\n'
            '/threshold <src> <dst> <value> - Set minimum price change to trigger a notification.\n'
            'Example: /threshold RMO EVN 20\n'
            'Note: value must be a non-negative whole number of EUR. Default is 0 (notify on any change).\n\n'
            '/convert <amount> <from> <to> - Convert an integer amount between currencies.\n'
            'Example: /convert 100 EUR MDL\n\n'
            '/currency <code> - Sets default currency for the chat.\n'
            'Example: /currency MDL\n\n'
            '/promo <src> <travel date> <price> - Finds cheap flights with only departure and date specified.\n'
            'Example: /promo RMO 23.05.2026 150\n\n'
            '/link <src> <dst> <travel date> - Find links for specified direction in supported airlines.\n'
            'Example: /link RMO EVN 23.05.2026\n\n'
        ),
    },
    'ru': {
        'description': (
            'Слежу за ценами на рейсы FlyOne и Wizz Air и пишу, когда билет дешевеет или дорожает.\n\n'
            'Добавь маршрут, укажи желаемую цену — я буду проверять его по расписанию. '
            'Нажми «Старт», чтобы начать.'
        ),
        'short_description': 'Следит за ценами на рейсы FlyOne и Wizz Air и сообщает, когда они меняются.',
        'start_created': (
            'Бот запущен! ✈️\n\n'
            'Добавь маршрут — и я сообщу, когда цена изменится:\n'
            '/add RMO EVN 15.10.2026 150\n\n'
            'Пользуйся кнопками ниже или /help — там все команды.'
        ),
        'start_existing': 'Бот уже запущен! Пользуйся кнопками ниже или /help — там все команды.',
        'app_prompt': 'Маршруты, графики и настройки — в приложении:',
        'open_app': '✈️ Открыть приложение',
        'home_screen': '📲 На рабочий стол',
        'stats_hint': 'Пришли маршрут, и я нарисую график цены:\n/stats RMO EVN\n/stats RMO EVN 15.10.2026',
        'promo_hint': (
            'Пришли аэропорт вылета, дату и максимальную цену — найду дешёвые рейсы:\n/promo RMO 23.05.2026 150'
        ),
        'add_hint': (
            'Пришли аэропорты, дату и желаемую цену — или ссылку авиакомпании и цену:\n'
            '/add RMO EVN 15.10.2026 150\n'
            '/add <ссылка> 150'
        ),
        'remove_hint': 'Пришли маршрут, который удалить, или его ссылку:\n/remove RMO EVN\n/remove <ссылка>',
        'notify_hint': (
            'Когда уведомлять по маршруту: + только рост цены, - только падение, без знака — любое изменение:\n'
            '/notify RMO EVN -'
        ),
        'threshold_hint': 'Пришли маршрут и минимальное изменение цены для уведомления:\n/threshold RMO EVN 20',
        'convert_hint': 'Пришли сумму и две валюты:\n/convert 100 EUR MDL',
        'currency_hint': 'Пришли код валюты для этого чата:\n/currency MDL',
        'link_hint': 'Пришли маршрут и дату — дам ссылки авиакомпаний:\n/link RMO EVN 23.05.2026',
        'buttons': {
            'directions': '📋 Маршруты',
            'go': '🔄 Проверить сейчас',
            'stats': '📈 Статистика',
            'promo': '🔥 Промо',
            'info': '⚙️ Настройки',
            'help': '❓ Помощь',
            'app': '📱 Открыть приложение',
            'stop': '⏹ Стоп',
        },
        'stop_confirm': 'Остановить бота? Все твои маршруты будут удалены.',
        'stop_yes': 'Да, остановить',
        'stop_no': 'Отмена',
        'stop_cancelled': 'Хорошо, бот продолжает работать.',
        'commands': {
            'start': 'Запустить бота',
            'help': 'Все команды',
            'directions': 'Мои маршруты',
            'add': 'Добавить маршрут',
            'remove': 'Удалить маршрут',
            'go': 'Проверить цены сейчас',
            'stats': 'График цены маршрута',
            'promo': 'Дешёвые рейсы из аэропорта',
            'link': 'Ссылки на авиакомпании',
            'notify': 'Уведомлять о росте/падении',
            'threshold': 'Минимальное изменение цены',
            'schedule': 'Расписание проверок',
            'less': 'Тихий режим',
            'currency': 'Валюта по умолчанию',
            'convert': 'Конвертер валют',
            'airports': 'Доступные аэропорты',
            'info': 'Настройки чата',
            'auth': 'Код для входа в приложение',
            'stop': 'Остановить бота',
        },
        'help': (
            'Доступные команды:\n\n'
            '/start - Запустить бота.\n\n'
            '/stop - Остановить бота.\n\n'
            '/add <откуда> <куда> <дата> <цена> ИЛИ /add <ссылка> <цена> - Добавить маршрут.\n'
            'Пример: /add RMO EVN 15.10.2024 300\n'
            'Откуда и куда — 3-буквенные коды аэропортов. Цена — целое число в EUR.\n\n'
            '/remove <откуда> <куда> ИЛИ /remove <ссылка> - Удалить маршрут.\n'
            'Пример: /remove RMO EVN\n'
            'Откуда и куда — 3-буквенные коды аэропортов.\n\n'
            '/go - Проверить цены прямо сейчас.\n\n'
            '/schedule [шаблон] - Включить/выключить расписание или задать частоту проверок.\n'
            'Пример: /schedule — переключить, или с шаблоном:\n'
            '  1h            каждый час (по умолчанию)\n'
            '  Nh            каждые N часов\n'
            '  6pm           каждый день в 18:00\n'
            '  8am-11pm      каждый час с 8:00 до 23:00\n'
            '  8am-11pm 2h   каждые 2 часа с 8:00 до 23:00\n\n'
            '/less - Тихий режим. Если включён, сообщения приходят только при изменении цены.\n\n'
            '/airports - Список доступных аэропортов с кодами.\n\n'
            '/directions - Все маршруты этого чата.\n\n'
            '/stats <откуда> <куда> [<дата>] - График изменения цены маршрута.\n'
            'Пример: /stats RMO EVN 15.10.2024\n\n'
            '/auth - ID чата и одноразовый код для входа в приложение.\n\n'
            '/info - Настройки этого чата.\n\n'
            '/notify <откуда> <куда> [+|-] - Когда уведомлять по маршруту.\n'
            'Пример: /notify RMO EVN -\n'
            '+ только при росте цены, - только при падении, без знака — при любом изменении.\n\n'
            '/threshold <откуда> <куда> <значение> - Минимальное изменение цены для уведомления.\n'
            'Пример: /threshold RMO EVN 20\n'
            'Значение — целое неотрицательное число в EUR. По умолчанию 0 (любое изменение).\n\n'
            '/convert <сумма> <из> <в> - Перевести целую сумму из одной валюты в другую.\n'
            'Пример: /convert 100 EUR MDL\n\n'
            '/currency <код> - Валюта по умолчанию для чата.\n'
            'Пример: /currency MDL\n\n'
            '/promo <откуда> <дата> <цена> - Дешёвые рейсы, когда известны только вылет и дата.\n'
            'Пример: /promo RMO 23.05.2026 150\n\n'
            '/link <откуда> <куда> <дата> - Ссылки на маршрут у поддерживаемых авиакомпаний.\n'
            'Пример: /link RMO EVN 23.05.2026\n\n'
        ),
    },
}

BUTTON_ACTIONS = {label: action for texts in TEXTS.values() for action, label in texts['buttons'].items()}


def lang(language_code: str | None) -> str:
    return 'ru' if language_code and language_code.startswith('ru') else 'en'


def t(key: str, language_code: str | None):
    return TEXTS[lang(language_code)][key]
