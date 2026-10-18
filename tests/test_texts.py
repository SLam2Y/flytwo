from bot.texts import BUTTON_ACTIONS, TEXTS, lang


def test_languages_have_same_keys():
    en, ru = TEXTS['en'], TEXTS['ru']
    assert en.keys() == ru.keys()
    assert en['buttons'].keys() == ru['buttons'].keys()
    assert en['commands'].keys() == ru['commands'].keys()


def test_button_labels_are_unique():
    assert len(BUTTON_ACTIONS) == sum(len(texts['buttons']) for texts in TEXTS.values())


def test_lang():
    assert lang('ru') == 'ru'
    assert lang('ru-RU') == 'ru'
    assert lang('en') == 'en'
    assert lang('ro') == 'en'
    assert lang(None) == 'en'
