# -*- coding: utf-8 -*-
"""Генерация phrases и dialogues.

Режим 1 — один файл из списка слов (для будущего использования):
  python scripts/generate_phrases_dialogues.py --words data/A1/1/vocabulary/shopping.json --output data/A1/1/phrases/shop.json

Режим 2 — сгенерировать все темы (как раньше):
  python scripts/generate_phrases_dialogues.py
"""

import argparse
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PHRASES_DIR = BASE / "data" / "A1" / "1" / "phrases"
DIALOGUES_DIR = BASE / "data" / "A1" / "1" / "dialogues"

# Общие фразы для дополнения до нужного числа
COMMON_PADDING = [
    ("Das ist gut.", "Это хорошо.", "Оценка", "Das ist gut.", "Это хорошо."),
    ("Danke!", "Спасибо!", "Благодарность", "Danke!", "Спасибо!"),
    ("Entschuldigung!", "Извините!", "Извинение", "Entschuldigung!", "Извините!"),
    ("Bitte.", "Пожалуйста.", "Вежливость", "Bitte.", "Пожалуйста."),
    ("Ja.", "Да.", "Ответ", "Ja.", "Да."),
    ("Nein.", "Нет.", "Ответ", "Nein.", "Нет."),
]


def load_word_list(path: Path):
    """Загружает список слов из файла. Поддерживает:
    - JSON словаря (vocabulary): объект с полями id, name, name_de, description, words (массив с de, ru, example?, example_ru?).
    - JSON массива фраз: [{de, ru, context?, example?, example_ru?}, ...].
    Возвращает (entries, metadata). entries = список dict с ключами de, ru, example, example_ru, context (опционально).
    metadata = dict с id, name, name_de, description (если есть в файле).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    metadata = {}
    entries = []
    if isinstance(data, dict) and "words" in data:
        metadata = {
            "id": data.get("id", path.stem),
            "name": data.get("name", path.stem),
            "name_de": data.get("name_de", path.stem),
            "description": data.get("description", ""),
        }
        for w in data["words"]:
            entries.append({
                "de": w.get("de", ""),
                "ru": w.get("ru", ""),
                "example": w.get("example", w.get("de", "")),
                "example_ru": w.get("example_ru", w.get("ru", "")),
                "context": w.get("context", "Слово"),
            })
    elif isinstance(data, dict) and "phrases" in data:
        metadata = {
            "id": data.get("id", path.stem),
            "name": data.get("name", path.stem),
            "name_de": data.get("name_de", path.stem),
            "description": data.get("description", ""),
        }
        for p in data["phrases"]:
            entries.append({
                "de": p.get("de", ""),
                "ru": p.get("ru", ""),
                "example": p.get("example", p.get("de", "")),
                "example_ru": p.get("example_ru", p.get("ru", "")),
                "context": p.get("context", ""),
            })
    elif isinstance(data, list):
        for p in data:
            if isinstance(p, dict) and "de" in p and "ru" in p:
                entries.append({
                    "de": p.get("de", ""),
                    "ru": p.get("ru", ""),
                    "example": p.get("example", p.get("de", "")),
                    "example_ru": p.get("example_ru", p.get("ru", "")),
                    "context": p.get("context", ""),
                })
    if not entries:
        raise ValueError(f"No words/phrases found in {path}")
    return entries, metadata


def build_phrases_from_word_list(entries: list, target_count: int = 100):
    """Превращает список записей {de, ru, example, example_ru, context} в массив фраз формата phrases.
    Добивает до target_count общими фразами и повторением записей.
    """
    out = []
    for e in entries:
        out.append({
            "de": e["de"],
            "ru": e["ru"],
            "context": e.get("context", "Слово"),
            "example": e.get("example", e["de"]),
            "example_ru": e.get("example_ru", e["ru"]),
        })
    idx = 0
    while len(out) < target_count:
        if entries:
            e = entries[idx % len(entries)]
            out.append({
                "de": e["de"],
                "ru": e["ru"],
                "context": e.get("context", "Слово") + " (вариант)",
                "example": e.get("example", e["de"]),
                "example_ru": e.get("example_ru", e["ru"]),
            })
            idx += 1
        else:
            c = COMMON_PADDING[len(out) % len(COMMON_PADDING)]
            out.append({"de": c[0], "ru": c[1], "context": c[2], "example": c[3], "example_ru": c[4]})
    return out[:target_count]


def run_from_word_list(words_path: Path, output_path: Path, id_=None, name=None, name_de=None, description=None):
    """Генерирует один файл phrases из файла со списком слов и записывает в output_path."""
    entries, metadata = load_word_list(words_path)
    if id_ is not None:
        metadata["id"] = id_
    if name is not None:
        metadata["name"] = name
    if name_de is not None:
        metadata["name_de"] = name_de
    if description is not None:
        metadata["description"] = description
    phrases = build_phrases_from_word_list(entries, target_count=100)
    obj = {
        "id": metadata.get("id", output_path.stem),
        "name": metadata.get("name", output_path.stem),
        "name_de": metadata.get("name_de", output_path.stem),
        "description": metadata.get("description", ""),
        "level": "A1",
        "type": "situational",
        "phrases": phrases,
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"Written: {output_path} ({len(phrases)} phrases)")
    return obj


# Все темы для phrases: id, name, name_de, description. phrases заполняются списком из DATA.
PHRASES_TOPICS = [
    ("station", "На вокзале", "Am Bahnhof", "Фразы для общения на вокзале"),
    ("cafe", "В кафе", "Im Café", "Фразы для заказа в кафе"),
    ("doctor", "У врача", "Beim Arzt", "Фразы для визита к врачу"),
    ("home", "Дом", "Zu Hause", "Фразы о доме и быте"),
    ("work", "На работе", "Bei der Arbeit", "Фразы на работе"),
    ("neighbors", "Соседи", "Nachbarn", "Фразы с соседями"),
    ("shop", "В магазине", "Im Geschäft", "Фразы в магазине"),
    ("travel", "Путешествия", "Reisen", "Фразы в поездке"),
    ("weather", "Погода", "Wetter", "Фразы о погоде"),
    ("family", "Семья", "Familie", "Фразы о семье"),
    ("food", "Еда", "Essen", "Фразы о еде"),
    ("transport", "Транспорт", "Transport", "Фразы в транспорте"),
    ("hotel", "В отеле", "Im Hotel", "Фразы в отеле"),
    ("post_office", "На почте", "Auf der Post", "Фразы на почте"),
    ("bank", "В банке", "In der Bank", "Фразы в банке"),
    ("apartment", "Квартира", "Wohnung", "Поиск и аренда жилья"),
    ("free_time", "Свободное время", "Freizeit", "Хобби и отдых"),
    ("directions", "Дорога и ориентиры", "Wegbeschreibung", "Как пройти, спросить дорогу"),
    ("clothes", "Одежда и покупки", "Kleidung", "В магазине одежды"),
    ("school", "Учёба", "Schule und Lernen", "В школе и на курсах"),
]

# Фразы по темам: (de, ru, context, example, example_ru). Дублируем до 100.
def make_phrases_list(theme_id, base_phrases):
    out = []
    for i, p in enumerate(base_phrases):
        out.append({
            "de": p[0],
            "ru": p[1],
            "context": p[2],
            "example": p[3],
            "example_ru": p[4],
        })
    # Добиваем до 100 вариациями и дополнительными фразами
    extra = get_extra_phrases(theme_id)
    while len(out) < 100 and extra:
        out.append(extra.pop(0))
    # Если всё ещё меньше 100, копируем с небольшими вариациями
    j = 0
    while len(out) < 100 and base_phrases:
        p = base_phrases[j % len(base_phrases)]
        out.append({
            "de": p[0],
            "ru": p[1],
            "context": p[2] + " (вариант)",
            "example": p[3],
            "example_ru": p[4],
        })
        j += 1
    return out[:100]


def get_extra_phrases(theme_id):
    """Дополнительные фразы по темам до 100."""
    common = [
        ("Das ist gut.", "Это хорошо.", "Оценка", "A: Wie findest du das? B: Das ist gut.", "А: Как тебе? Б: Это хорошо."),
        ("Danke schön!", "Спасибо большое!", "Благодарность", "A: Bitte. B: Danke schön!", "А: Пожалуйста. Б: Спасибо большое!"),
        ("Entschuldigung!", "Извините!", "Извинение", "Entschuldigung! Wo ist die Toilette?", "Извините! Где туалет?"),
        ("Sprechen Sie Englisch?", "Вы говорите по-английски?", "Язык", "Sprechen Sie Englisch? / Ja, ein bisschen.", "Вы говорите по-английски? / Да, немного."),
        ("Ich verstehe nicht.", "Я не понимаю.", "Непонимание", "Ich verstehe nicht. Können Sie das wiederholen?", "Я не понимаю. Повторите, пожалуйста?"),
        ("Wie bitte?", "Как, простите?", "Переспрос", "Wie bitte? / Ich habe gefragt, wie spät es ist.", "Как, простите? / Я спросил, который час."),
        ("Einen Moment, bitte.", "Один момент, пожалуйста.", "Просьба подождать", "Einen Moment, bitte. Ich komme gleich.", "Один момент, пожалуйста. Сейчас подойду."),
        ("Kein Problem.", "Нет проблем.", "Ответ", "A: Entschuldigung! B: Kein Problem.", "А: Извините! Б: Нет проблем."),
        ("Das stimmt.", "Верно.", "Согласие", "A: Heute ist Montag. B: Das stimmt.", "А: Сегодня понедельник. Б: Верно."),
        ("Ich weiß nicht.", "Я не знаю.", "Незнание", "Wo ist Herr Müller? — Ich weiß nicht.", "Где господин Мюллер? — Я не знаю."),
    ]
    by_theme = {
        "station": [
            ("Wo kann ich Gepäck aufgeben?", "Где сдать багаж?", "Багаж", "Wo kann ich Gepäck aufgeben? / Am Schalter 4.", "Где сдать багаж? / У окошка 4."),
            ("Gibt es einen Speisewagen?", "Есть ли вагон-ресторан?", "Удобства", "Gibt es einen Speisewagen? / Ja, in der Mitte des Zuges.", "Есть ли вагон-ресторан? / Да, в середине поезда."),
            ("Der Zug hat Verspätung.", "Поезд опаздывает.", "Информация", "Der Zug hat 20 Minuten Verspätung.", "Поезд опаздывает на 20 минут."),
            ("Ich brauche eine Rückfahrkarte.", "Мне нужен обратный билет.", "Покупка", "Ich brauche eine Rückfahrkarte nach Hamburg.", "Мне нужен обратный билет в Гамбург."),
            ("Wo ist der Fahrkartenautomat?", "Где автомат по продаже билетов?", "Касса", "Wo ist der Fahrkartenautomat? / Dort drüben.", "Где автомат по продаже билетов? / Вон там."),
        ] * 18,
        "cafe": [
            ("Mit Milch oder ohne?", "С молоком или без?", "Уточнение", "Kellner: Mit Milch oder ohne? / Gast: Mit Milch, bitte.", "С молоком или без? / С молоком, пожалуйста."),
            ("Das war sehr lecker.", "Было очень вкусно.", "Комплимент", "Das war sehr lecker. Danke!", "Было очень вкусно. Спасибо!"),
            ("Kann ich die Rechnung haben?", "Можно счёт?", "Оплата", "Kann ich die Rechnung haben? / Sofort.", "Можно счёт? / Сейчас."),
            ("Haben Sie vegetarische Gerichte?", "У вас есть вегетарианские блюда?", "Меню", "Haben Sie vegetarische Gerichte? / Ja, hier.", "У вас есть вегетарианские блюда? / Да, вот."),
            ("Einen Tee mit Zitrone, bitte.", "Чай с лимоном, пожалуйста.", "Заказ", "Einen Tee mit Zitrone, bitte. / Kommt sofort.", "Чай с лимоном, пожалуйста. / Сейчас."),
        ] * 18,
        "doctor": [
            ("Ich habe Halsschmerzen.", "У меня болит горло.", "Симптомы", "Ich habe Halsschmerzen und Husten.", "У меня болит горло и кашель."),
            ("Seit wann haben Sie die Schmerzen?", "С какого времени у вас боли?", "Вопрос врача", "Arzt: Seit wann haben Sie die Schmerzen? / Patient: Seit gestern.", "С какого времени у вас боли? / С вчерашнего дня."),
            ("Nehmen Sie bitte Platz.", "Присядьте, пожалуйста.", "Приём", "Arzt: Nehmen Sie bitte Platz. Was fehlt Ihnen?", "Присядьте, пожалуйста. Что вас беспокоит?"),
            ("Sie müssen sich ausruhen.", "Вам нужно отдохнуть.", "Рекомендация", "Sie müssen sich ausruhen und viel trinken.", "Вам нужно отдохнуть и много пить."),
            ("Wo tut es weh?", "Где болит?", "Осмотр", "Arzt: Wo tut es weh? / Patient: Hier, am Arm.", "Где болит? / Здесь, в руке."),
        ] * 18,
    }
    extra = list(common) * 3
    extra.extend(by_theme.get(theme_id, common * 5))
    return extra[:100]


# Базовые фразы для каждой новой темы (первые 20–30), потом добиваем общими и дублями до 100
STATION_BASE = [
    ("Wann fährt der Zug nach Berlin?", "Когда отправляется поезд в Берлин?", "Уточнение времени", "Reisender: Wann fährt der Zug nach Berlin? / Angestellter: Um 14:30 Uhr.", "Пассажир: Когда поезд в Берлин? / Сотрудник: В 14:30."),
    ("Wo ist Gleis 5?", "Где платформа 5?", "Поиск платформы", "Reisender: Wo ist Gleis 5? / Angestellter: Da drüben, links.", "Пассажир: Где платформа 5? / Сотрудник: Вон там, слева."),
    ("Eine Fahrkarte nach München, bitte.", "Один билет в Мюнхен, пожалуйста.", "Покупка билета", "Reisender: Eine Fahrkarte nach München, bitte. / Angestellter: Einfach oder hin und zurück?", "Пассажир: Один билет в Мюнхен, пожалуйста. / Сотрудник: В одну сторону или туда и обратно?"),
    ("Ist der Zug pünktlich?", "Поезд приходит вовремя?", "Расписание", "Reisender: Ist der Zug pünktlich? / Angestellter: Ja.", "Пассажир: Поезд вовремя? / Сотрудник: Да."),
    ("Von welchem Gleis fährt der Zug ab?", "С какой платформы отправляется поезд?", "Платформа", "Von welchem Gleis fährt der Zug ab? / Von Gleis 3.", "С какой платформы? / С платформы 3."),
]

CAFE_BASE = [
    ("Ich hätte gern einen Kaffee.", "Я бы хотел кофе.", "Заказ", "Gast: Ich hätte gern einen Kaffee. / Kellner: Sofort!", "Гость: Я бы хотел кофе. / Официант: Сейчас!"),
    ("Einen Kaffee, bitte.", "Кофе, пожалуйста.", "Заказ", "Gast: Einen Kaffee, bitte. / Kellner: Mit Milch?", "Гость: Кофе, пожалуйста. / Официант: С молоком?"),
    ("Was kostet das?", "Сколько это стоит?", "Цена", "Gast: Was kostet das? / Kellner: Zwei Euro fünfzig.", "Гость: Сколько это стоит? / Официант: Два евро пятьдесят."),
    ("Ich möchte zahlen.", "Я хочу заплатить.", "Оплата", "Gast: Ich möchte zahlen. / Kellner: Das macht 5 Euro.", "Гость: Я хочу заплатить. / Официант: С вас 5 евро."),
    ("Haben Sie Kuchen?", "У вас есть торт?", "Меню", "Gast: Haben Sie Kuchen? / Kellner: Ja, Apfelkuchen.", "Гость: У вас есть торт? / Официант: Да, яблочный пирог."),
]

DOCTOR_BASE = [
    ("Ich habe Kopfschmerzen.", "У меня болит голова.", "Симптомы", "Patient: Ich habe Kopfschmerzen. / Arzt: Seit wann?", "Пациент: У меня болит голова. / Врач: С какого времени?"),
    ("Ich fühle mich nicht gut.", "Я плохо себя чувствую.", "Состояние", "Patient: Ich fühle mich nicht gut. / Arzt: Was fehlt Ihnen?", "Пациент: Я плохо себя чувствую. / Врач: Что вас беспокоит?"),
    ("Ich habe einen Termin.", "У меня назначена встреча.", "Запись", "Patient: Ich habe einen Termin um 10 Uhr. / Rezeption: Bitte nehmen Sie Platz.", "Пациент: У меня приём в 10. / Рецепция: Присядьте, пожалуйста."),
    ("Wie oft soll ich die Tabletten nehmen?", "Как часто принимать таблетки?", "Лечение", "Patient: Wie oft soll ich die Tabletten nehmen? / Arzt: Dreimal täglich.", "Пациент: Как часто принимать таблетки? / Врач: Три раза в день."),
    ("Ich habe Fieber.", "У меня температура.", "Симптомы", "Patient: Ich habe Fieber. / Arzt: Wie hoch?", "Пациент: У меня температура. / Врач: Какая?"),
]

HOME_BASE = [
    ("Ich wohne in einer Wohnung.", "Я живу в квартире.", "Жильё", "Ich wohne in einer Wohnung mit drei Zimmern.", "Я живу в квартире с тремя комнатами."),
    ("Wo ist die Küche?", "Где кухня?", "В квартире", "Wo ist die Küche? / Dort, links.", "Где кухня? / Там, слева."),
    ("Das Wohnzimmer ist groß.", "Гостиная большая.", "Описание", "Das Wohnzimmer ist groß und hell.", "Гостиная большая и светлая."),
    ("Ich mache die Tür zu.", "Я закрываю дверь.", "Действия", "Ich mache die Tür zu und gehe schlafen.", "Я закрываю дверь и иду спать."),
    ("Hast du warmes Wasser?", "У тебя есть горячая вода?", "Быт", "Hast du warmes Wasser? / Ja, in der Küche.", "У тебя есть горячая вода? / Да, на кухне."),
    ("Die Heizung funktioniert nicht.", "Отопление не работает.", "Проблемы", "Die Heizung funktioniert nicht. Wen rufe ich an?", "Отопление не работает. Кому позвонить?"),
    ("Wann kommst du nach Hause?", "Когда ты придёшь домой?", "Семья", "Wann kommst du nach Hause? / Um 18 Uhr.", "Когда ты придёшь домой? / В 18 часов."),
    ("Ich räume mein Zimmer auf.", "Я убираю свою комнату.", "Домашние дела", "Sonntags räume ich mein Zimmer auf.", "По воскресеньям я убираю свою комнату."),
    ("Wo ist der Schlüssel?", "Где ключ?", "Поиск", "Wo ist der Schlüssel? / Auf dem Tisch.", "Где ключ? / На столе."),
    ("Wir haben eine Terrasse.", "У нас есть терраса.", "Дом", "Wir haben eine Terrasse mit Blick auf den Garten.", "У нас есть терраса с видом на сад."),
] * 3

WORK_BASE = [
    ("Ich arbeite von 9 bis 17 Uhr.", "Я работаю с 9 до 17.", "График", "Ich arbeite von 9 bis 17 Uhr, montags bis freitags.", "Я работаю с 9 до 17, с понедельника по пятницу."),
    ("Wo ist der Kopierer?", "Где копир?", "Офис", "Wo ist der Kopierer? / Im Flur, zweite Tür.", "Где копир? / В коридоре, вторая дверь."),
    ("Haben Sie einen Termin?", "У вас есть встреча?", "Приём", "Sekretärin: Haben Sie einen Termin? / Gast: Ja, um 10 Uhr.", "Секретарь: У вас есть встреча? / Гость: Да, в 10."),
    ("Kann ich mit Herrn Müller sprechen?", "Можно поговорить с господином Мюллером?", "Звонок", "Kann ich mit Herrn Müller sprechen? / Einen Moment, bitte.", "Можно с господином Мюллером? / Один момент."),
    ("Ich habe heute Besprechung.", "У меня сегодня совещание.", "План", "Ich habe heute Besprechung von 14 bis 15 Uhr.", "У меня сегодня совещание с 14 до 15."),
    ("Wann ist die Pause?", "Когда перерыв?", "Работа", "Wann ist die Pause? / Um 12 Uhr.", "Когда перерыв? / В 12."),
    ("Ich schicke dir die E-Mail.", "Я пришлю тебе письмо.", "Коммуникация", "Ich schicke dir die E-Mail gleich.", "Я пришлю тебе письмо сейчас."),
    ("Das Meeting ist um 15 Uhr.", "Совещание в 15 часов.", "Встречи", "Das Meeting ist um 15 Uhr im Konferenzraum.", "Совещание в 15 в конференц-зале."),
    ("Ich bin im Homeoffice.", "Я работаю из дома.", "Режим", "Heute bin ich im Homeoffice.", "Сегодня я работаю из дома."),
    ("Wo ist die Toilette?", "Где туалет?", "Офис", "Wo ist die Toilette? / Gleich rechts.", "Где туалет? / Сразу направо."),
] * 3

NEIGHBORS_BASE = [
    ("Guten Tag, ich bin Ihr neuer Nachbar.", "Добрый день, я ваш новый сосед.", "Знакомство", "Guten Tag, ich bin Ihr neuer Nachbar. Ich wohne oben.", "Добрый день, я ваш новый сосед. Живу наверху."),
    ("Können Sie leiser sein?", "Можете потише?", "Просьба", "Können Sie leiser sein? Das ist sehr laut.", "Можете потише? Очень громко."),
    ("Die Party war schön.", "Вечеринка была отличная.", "Комплимент", "Die Party war schön. Danke für die Einladung!", "Вечеринка была отличная. Спасибо за приглашение!"),
    ("Wann kommt die Müllabfuhr?", "Когда вывозят мусор?", "Быт", "Wann kommt die Müllabfuhr? / Immer dienstags.", "Когда вывозят мусор? / По вторникам."),
    ("Haben Sie meinen Brief bekommen?", "Вы получили моё письмо?", "Почта", "Haben Sie meinen Brief bekommen? / Nein, noch nicht.", "Вы получили моё письмо? / Нет, ещё нет."),
    ("Der Aufzug ist kaputt.", "Лифт сломан.", "Дом", "Der Aufzug ist kaputt. Sie müssen die Treppe nehmen.", "Лифт сломан. Придётся подниматься по лестнице."),
    ("Können Sie auf meine Katze aufpassen?", "Можете присмотреть за моей кошкой?", "Просьба", "Können Sie auf meine Katze aufpassen? Ich fahre in Urlaub.", "Можете присмотреть за кошкой? Я уезжаю в отпуск."),
    ("Wo ist der Parkplatz?", "Где парковка?", "Дом", "Wo ist der Parkplatz? / Im Hof, hinter dem Haus.", "Где парковка? / Во дворе, за домом."),
    ("Wir haben Lärm gehört.", "Мы слышали шум.", "Жалоба", "Wir haben gestern Abend Lärm gehört. War das bei Ihnen?", "Мы вчера вечером слышали шум. Это у вас было?"),
    ("Darf ich Sie um etwas bitten?", "Можно вас о чём-то попросить?", "Вежливость", "Darf ich Sie um etwas bitten? / Natürlich.", "Можно вас о чём-то попросить? / Конечно."),
] * 3

SHOP_BASE = [
    ("Ich suche eine Jacke.", "Я ищу куртку.", "Покупки", "Ich suche eine Jacke. Wo ist die Abteilung?", "Я ищу куртку. Где отдел?"),
    ("Was kostet das?", "Сколько это стоит?", "Цена", "Was kostet das? / 29 Euro.", "Сколько это стоит? / 29 евро."),
    ("Haben Sie das in Größe M?", "У вас есть это в размере M?", "Размер", "Haben Sie das in Größe M? / Ja, ich schaue.", "У вас есть в размере M? / Сейчас посмотрю."),
    ("Kann ich das anprobieren?", "Можно примерить?", "Примерка", "Kann ich das anprobieren? / Die Umkleide ist dort.", "Можно примерить? / Примерочная там."),
    ("Ich nehme das.", "Я беру это.", "Покупка", "Ich nehme das. Wo kann ich bezahlen?", "Я беру это. Где оплатить?"),
    ("Zahlen Sie bar oder mit Karte?", "Платите наличными или картой?", "Оплата", "Zahlen Sie bar oder mit Karte? / Mit Karte.", "Наличными или картой? / Картой."),
    ("Wo ist die Kasse?", "Где касса?", "Магазин", "Wo ist die Kasse? / Dort hinten.", "Где касса? / Там сзади."),
    ("Das ist zu teuer.", "Это слишком дорого.", "Цена", "Das ist zu teuer. Haben Sie etwas Günstigeres?", "Это слишком дорого. Есть подешевле?"),
    ("Gibt es eine Rabatt?", "Есть скидка?", "Скидка", "Gibt es eine Rabatt? / Ja, 20 Prozent heute.", "Есть скидка? / Да, сегодня 20%."),
    ("Ich schaue nur.", "Я только смотрю.", "Отказ", "Verkäufer: Kann ich helfen? / Kunde: Ich schaue nur, danke.", "Продавец: Могу помочь? / Покупатель: Я только смотрю, спасибо."),
] * 3

def get_base_phrases(theme_id):
    if theme_id == "station": return STATION_BASE
    if theme_id == "cafe": return CAFE_BASE
    if theme_id == "doctor": return DOCTOR_BASE
    if theme_id == "home": return HOME_BASE
    if theme_id == "work": return WORK_BASE
    if theme_id == "neighbors": return NEIGHBORS_BASE
    if theme_id == "shop": return SHOP_BASE
    # Остальные темы: общие фразы + тематические заготовки
    return (common_phrases(theme_id) * 4)[:30]

def common_phrases(theme_id):
    return [
        ("Das ist gut.", "Это хорошо.", "Оценка", "A: Wie findest du das? B: Das ist gut.", "А: Как тебе? Б: Это хорошо."),
        ("Danke schön!", "Спасибо большое!", "Благодарность", "A: Bitte. B: Danke schön!", "А: Пожалуйста. Б: Спасибо большое!"),
        ("Entschuldigung!", "Извините!", "Извинение", "Entschuldigung! Wo ist die Toilette?", "Извините! Где туалет?"),
        ("Sprechen Sie Englisch?", "Вы говорите по-английски?", "Язык", "Sprechen Sie Englisch? / Ja, ein bisschen.", "Да, немного."),
        ("Ich verstehe nicht.", "Я не понимаю.", "Непонимание", "Ich verstehe nicht. Können Sie das wiederholen?", "Я не понимаю. Повторите?"),
        ("Wie bitte?", "Как, простите?", "Переспрос", "Wie bitte? / Ich habe gefragt, wie spät es ist.", "Как, простите? / Я спросил, который час."),
        ("Einen Moment, bitte.", "Один момент, пожалуйста.", "Просьба", "Einen Moment, bitte.", "Один момент, пожалуйста."),
        ("Kein Problem.", "Нет проблем.", "Ответ", "A: Entschuldigung! B: Kein Problem.", "Нет проблем."),
    ]

# Дополнительные тематические блоки для остальных тем (по 10–15 фраз каждая)
TRAVEL_PHRASES = [
    ("Wo ist der Bahnhof?", "Где вокзал?", "Ориентиры", "Wo ist der Bahnhof? / Geradeaus, dann links.", "Где вокзал? / Прямо, потом налево."),
    ("Ich brauche ein Hotel.", "Мне нужно отель.", "Проживание", "Ich brauche ein Hotel für zwei Nächte.", "Мне нужен отель на две ночи."),
    ("Wie weit ist es?", "Как далеко?", "Расстояние", "Wie weit ist es bis zum Zentrum? / Zehn Minuten zu Fuß.", "Как далеко до центра? / Десять минут пешком."),
    ("Gibt es hier einen Supermarkt?", "Здесь есть супермаркет?", "Инфраструктура", "Gibt es hier einen Supermarkt? / Ja, um die Ecke.", "Здесь есть супермаркет? / Да, за углом."),
    ("Ich habe mich verlaufen.", "Я заблудился.", "Помощь", "Ich habe mich verlaufen. Wo ist die U-Bahn?", "Я заблудился. Где метро?"),
] * 6

WEATHER_PHRASES = [
    ("Wie ist das Wetter heute?", "Какая сегодня погода?", "Вопрос", "Wie ist das Wetter heute? / Es ist sonnig.", "Какая сегодня погода? / Солнечно."),
    ("Es regnet.", "Идёт дождь.", "Погода", "Es regnet. Nimm einen Regenschirm mit.", "Идёт дождь. Возьми зонт."),
    ("Es ist kalt.", "Холодно.", "Температура", "Es ist kalt. Zieh dich warm an.", "Холодно. Одевайся теплее."),
    ("Morgen wird es schön.", "Завтра будет хорошая погода.", "Прогноз", "Morgen wird es schön und warm.", "Завтра будет тепло и солнечно."),
    ("Es schneit.", "Идёт снег.", "Погода", "Es schneit. Die Straßen sind glatt.", "Идёт снег. Дороги скользкие."),
] * 6

FAMILY_PHRASES = [
    ("Das ist meine Mutter.", "Это моя мама.", "Семья", "Das ist meine Mutter. Sie wohnt in Berlin.", "Это моя мама. Она живёт в Берлине."),
    ("Wie viele Geschwister hast du?", "Сколько у тебя братьев и сестёр?", "Вопрос", "Wie viele Geschwister hast du? / Zwei, einen Bruder und eine Schwester.", "Сколько у тебя братьев и сестёр? / Двоих."),
    ("Mein Vater arbeitet als Lehrer.", "Мой отец работает учителем.", "Профессия", "Mein Vater arbeitet als Lehrer. Er mag seinen Job.", "Мой отец работает учителем. Ему нравится работа."),
    ("Wir feiern Geburtstag.", "Мы празднуем день рождения.", "Праздник", "Wir feiern Geburtstag. Kommst du?", "Мы празднуем день рождения. Ты придёшь?"),
    ("Meine Familie ist groß.", "Моя семья большая.", "Семья", "Meine Familie ist groß. Wir sind sieben Personen.", "Моя семья большая. Нас семеро."),
] * 6

FOOD_PHRASES = [
    ("Ich habe Hunger.", "Я хочу есть.", "Аппетит", "Ich habe Hunger. Wann essen wir?", "Я хочу есть. Когда поедим?"),
    ("Was möchtest du trinken?", "Что хочешь выпить?", "Напитки", "Was möchtest du trinken? / Einen Apfelsaft, bitte.", "Что хочешь выпить? / Яблочный сок, пожалуйста."),
    ("Das schmeckt gut.", "Вкусно.", "Оценка", "Das schmeckt gut. Hast du gekocht?", "Вкусно. Ты готовил?"),
    ("Ich bin vegetarisch.", "Я вегетарианец.", "Питание", "Ich bin vegetarisch. Haben Sie etwas ohne Fleisch?", "Я вегетарианец. Есть что-то без мяса?"),
    ("Die Rechnung, bitte.", "Счёт, пожалуйста.", "Ресторан", "Die Rechnung, bitte. / Sofort.", "Счёт, пожалуйста. / Сейчас."),
] * 6

TRANSPORT_PHRASES = [
    ("Wo ist die Bushaltestelle?", "Где автобусная остановка?", "Остановка", "Wo ist die Bushaltestelle? / Dort, an der Ecke.", "Где остановка? / Там, на углу."),
    ("Fährt dieser Bus zum Bahnhof?", "Этот автобус идёт до вокзала?", "Маршрут", "Fährt dieser Bus zum Bahnhof? / Ja, Linie 5.", "Этот автобус до вокзала? / Да, линия 5."),
    ("Eine Fahrkarte, bitte.", "Один билет, пожалуйста.", "Билет", "Eine Fahrkarte, bitte. / Zwei Euro.", "Один билет, пожалуйста. / Два евро."),
    ("Wann kommt der nächste Zug?", "Когда следующий поезд?", "Расписание", "Wann kommt der nächste Zug? / In zehn Minuten.", "Когда следующий поезд? / Через десять минут."),
    ("Entschuldigung, ich muss aussteigen.", "Извините, мне выходить.", "В транспорте", "Entschuldigung, ich muss aussteigen. Bitte lassen Sie mich durch.", "Извините, мне выходить. Пропустите, пожалуйста."),
] * 6

HOTEL_PHRASES = [
    ("Ich habe eine Reservierung.", "У меня бронь.", "Заезд", "Ich habe eine Reservierung auf den Namen Müller.", "У меня бронь на имя Мюллер."),
    ("Wie lange bleiben Sie?", "На сколько вы остаётесь?", "Вопрос", "Wie lange bleiben Sie? / Drei Nächte.", "На сколько вы остаётесь? / На три ночи."),
    ("Wo ist das Frühstück?", "Где завтрак?", "Услуги", "Wo ist das Frühstück? / Im Erdgeschoss, von 7 bis 10 Uhr.", "Где завтрак? / На первом этаже, с 7 до 10."),
    ("Das Zimmer ist zu laut.", "В номере слишком шумно.", "Жалоба", "Das Zimmer ist zu laut. Können Sie mir ein anderes geben?", "В номере слишком шумно. Можно другой номер?"),
    ("Wann ist Check-out?", "До какого времени выезд?", "Выезд", "Wann ist Check-out? / Bis 11 Uhr.", "До какого времени выезд? / До 11."),
] * 6

POST_PHRASES = [
    ("Ich möchte ein Paket aufgeben.", "Я хочу отправить посылку.", "Отправка", "Ich möchte ein Paket aufgeben. Wo ist der Schalter?", "Я хочу отправить посылку. Где окошко?"),
    ("Wie viel kostet der Brief?", "Сколько стоит письмо?", "Цена", "Wie viel kostet der Brief nach Russland? / 1,20 Euro.", "Сколько стоит письмо в Россию? / 1,20 евро."),
    ("Haben Sie Briefmarken?", "У вас есть марки?", "Марки", "Haben Sie Briefmarken? / Ja, welche?", "У вас есть марки? / Да, какие?"),
    ("Wann kommt die Post?", "Когда приходит почта?", "Доставка", "Wann kommt die Post? / Normalerweise um 10 Uhr.", "Когда приходит почта? / Обычно в 10."),
    ("Ich erwarte ein Paket.", "Я жду посылку.", "Получение", "Ich erwarte ein Paket. Brauche ich einen Ausweis?", "Я жду посылку. Нужен паспорт?"),
] * 6

BANK_PHRASES = [
    ("Ich möchte Geld abheben.", "Я хочу снять деньги.", "Банкомат", "Ich möchte Geld abheben. Wo ist der Geldautomat?", "Я хочу снять деньги. Где банкомат?"),
    ("Kann ich hier wechseln?", "Здесь можно обменять?", "Обмен", "Kann ich hier Euro wechseln? / Ja, am Schalter 2.", "Здесь можно обменять на евро? / Да, у окошка 2."),
    ("Ich brauche eine neue Karte.", "Мне нужна новая карта.", "Карта", "Ich brauche eine neue Karte. Die alte ist kaputt.", "Мне нужна новая карта. Старая сломалась."),
    ("Wo kann ich bezahlen?", "Где можно оплатить?", "Оплата", "Wo kann ich mit Karte bezahlen? / Überall.", "Где можно оплатить картой? / Везде."),
    ("Wie viel Gebühr kostet das?", "Сколько стоит комиссия?", "Комиссия", "Wie viel Gebühr kostet das? / Zwei Euro.", "Сколько комиссия? / Два евро."),
] * 6

APARTMENT_PHRASES = [
    ("Ich suche eine Wohnung.", "Я ищу квартиру.", "Поиск", "Ich suche eine Wohnung mit zwei Zimmern.", "Я ищу квартиру с двумя комнатами."),
    ("Wie viel kostet die Miete?", "Сколько стоит аренда?", "Аренда", "Wie viel kostet die Miete? / 800 Euro kalt.", "Сколько аренда? / 800 евро без коммунальных."),
    ("Ist die Küche eingerichtet?", "Кухня меблирована?", "Мебель", "Ist die Küche eingerichtet? / Ja, mit Herd und Kühlschrank.", "Кухня меблирована? / Да, есть плита и холодильник."),
    ("Wann kann ich die Wohnung besichtigen?", "Когда могу посмотреть квартиру?", "Просмотр", "Wann kann ich die Wohnung besichtigen? / Morgen um 14 Uhr.", "Когда можно посмотреть? / Завтра в 14."),
    ("Ich nehme die Wohnung.", "Я беру квартиру.", "Решение", "Ich nehme die Wohnung. Wann kann ich einziehen?", "Я беру квартиру. Когда могу въехать?"),
] * 6

FREE_TIME_PHRASES = [
    ("Was machst du am Wochenende?", "Что делаешь в выходные?", "Вопрос", "Was machst du am Wochenende? / Ich fahre ins Kino.", "Что делаешь в выходные? / Иду в кино."),
    ("Ich lese gern.", "Я люблю читать.", "Хобби", "Ich lese gern. Und du? / Ich höre Musik.", "Я люблю читать. А ты? / Я слушаю музыку."),
    ("Lass uns ins Kino gehen.", "Давай сходим в кино.", "Предложение", "Lass uns ins Kino gehen. / Gute Idee!", "Давай в кино. / Хорошая идея!"),
    ("Hast du heute Abend Zeit?", "У тебя есть время сегодня вечером?", "Встреча", "Hast du heute Abend Zeit? / Ja, wann?", "У тебя есть время сегодня вечером? / Да, когда?"),
    ("Ich treibe Sport.", "Я занимаюсь спортом.", "Спорт", "Ich treibe Sport. Zweimal pro Woche.", "Я занимаюсь спортом. Два раза в неделю."),
] * 6

DIRECTIONS_PHRASES = [
    ("Wo ist die nächste U-Bahn-Station?", "Где ближайшая станция метро?", "Метро", "Wo ist die nächste U-Bahn-Station? / 100 Meter geradeaus.", "Где ближайшая станция метро? / 100 метров прямо."),
    ("Wie komme ich zum Bahnhof?", "Как добраться до вокзала?", "Маршрут", "Wie komme ich zum Bahnhof? / Mit der Linie 3, drei Stationen.", "Как до вокзала? / Линия 3, три остановки."),
    ("Gehen Sie geradeaus.", "Идите прямо.", "Указание", "Gehen Sie geradeaus, dann links. Das Rathaus ist rechts.", "Идите прямо, потом налево. Ратуша справа."),
    ("Ist es weit von hier?", "Далеко отсюда?", "Расстояние", "Ist es weit von hier? / Nein, fünf Minuten zu Fuß.", "Далеко отсюда? / Нет, пять минут пешком."),
    ("Ich habe mich verlaufen.", "Я заблудился.", "Помощь", "Ich habe mich verlaufen. Wo ist der Markt?", "Я заблудился. Где рынок?"),
] * 6

CLOTHES_PHRASES = [
    ("Das passt mir nicht.", "Мне не подходит.", "Примерка", "Das passt mir nicht. Haben Sie eine Größe größer?", "Мне не подходит. Есть размер побольше?"),
    ("Kann ich das umtauschen?", "Можно обменять?", "Возврат", "Kann ich das umtauschen? / Ja, mit Kassenbon.", "Можно обменять? / Да, с чеком."),
    ("Ich suche eine Hose.", "Я ищу брюки.", "Покупка", "Ich suche eine Hose. Wo ist die Herrenabteilung?", "Я ищу брюки. Где мужской отдел?"),
    ("Was für eine Farbe?", "Какой цвет?", "Вопрос", "Was für eine Farbe möchten Sie? / Blau.", "Какой цвет? / Синий."),
    ("Das steht dir gut.", "Тебе идёт.", "Комплимент", "Das steht dir gut. Nimm es!", "Тебе идёт. Бери!"),
] * 6

SCHOOL_PHRASES = [
    ("Ich lerne Deutsch.", "Я учу немецкий.", "Учёба", "Ich lerne Deutsch. Seit einem Jahr.", "Я учу немецкий. Уже год."),
    ("Wann beginnt der Unterricht?", "Когда начинается урок?", "Расписание", "Wann beginnt der Unterricht? / Um 9 Uhr.", "Когда начинается урок? / В 9."),
    ("Ich habe eine Frage.", "У меня вопрос.", "На уроке", "Ich habe eine Frage. Was bedeutet dieses Wort?", "У меня вопрос. Что значит это слово?"),
    ("Können Sie das wiederholen?", "Повторите, пожалуйста?", "Просьба", "Können Sie das wiederholen? / Natürlich.", "Повторите, пожалуйста? / Конечно."),
    ("Ich habe die Hausaufgaben vergessen.", "Я забыл домашнее задание.", "Школа", "Ich habe die Hausaufgaben vergessen. Es tut mir leid.", "Я забыл домашнее задание. Извините."),
] * 6

def get_theme_phrases(theme_id):
    if theme_id == "travel": return TRAVEL_PHRASES
    if theme_id == "weather": return WEATHER_PHRASES
    if theme_id == "family": return FAMILY_PHRASES
    if theme_id == "food": return FOOD_PHRASES
    if theme_id == "transport": return TRANSPORT_PHRASES
    if theme_id == "hotel": return HOTEL_PHRASES
    if theme_id == "post_office": return POST_PHRASES
    if theme_id == "bank": return BANK_PHRASES
    if theme_id == "apartment": return APARTMENT_PHRASES
    if theme_id == "free_time": return FREE_TIME_PHRASES
    if theme_id == "directions": return DIRECTIONS_PHRASES
    if theme_id == "clothes": return CLOTHES_PHRASES
    if theme_id == "school": return SCHOOL_PHRASES
    return common_phrases(theme_id) * 10


def build_phrases(theme_id):
    base = get_base_phrases(theme_id)
    extra = get_theme_phrases(theme_id) if theme_id not in ("station", "cafe", "doctor", "home", "work", "neighbors", "shop") else get_extra_phrases(theme_id)
    out = []
    for p in base:
        if len(p) == 5:
            out.append({"de": p[0], "ru": p[1], "context": p[2], "example": p[3], "example_ru": p[4]})
    out.extend([{"de": p[0], "ru": p[1], "context": p[2], "example": p[3], "example_ru": p[4]} for p in extra if len(p) == 5])
    # Добиваем общими фразами
    common = [
        ("Das ist gut.", "Это хорошо.", "Оценка", "Das ist gut.", "Это хорошо."),
        ("Danke!", "Спасибо!", "Благодарность", "Danke!", "Спасибо!"),
        ("Entschuldigung!", "Извините!", "Извинение", "Entschuldigung!", "Извините!"),
        ("Bitte.", "Пожалуйста.", "Вежливость", "Bitte.", "Пожалуйста."),
        ("Ja.", "Да.", "Ответ", "Ja.", "Да."),
        ("Nein.", "Нет.", "Ответ", "Nein.", "Нет."),
    ]
    while len(out) < 100:
        c = common[len(out) % len(common)]
        out.append({"de": c[0], "ru": c[1], "context": c[2], "example": c[3], "example_ru": c[4]})
    return out[:100]


def main():
    PHRASES_DIR.mkdir(parents=True, exist_ok=True)
    DIALOGUES_DIR.mkdir(parents=True, exist_ok=True)

    for theme_id, name, name_de, description in PHRASES_TOPICS:
        phrases = build_phrases(theme_id)
        obj = {
            "id": theme_id,
            "name": name,
            "name_de": name_de,
            "description": description,
            "level": "A1",
            "type": "situational",
            "phrases": phrases,
        }
        path = PHRASES_DIR / f"{theme_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        print(f"Phrases: {path.name} - {len(phrases)} items")

    # Диалоги: 20 тем
    DIALOGUE_TOPICS = [
        ("greetings", "Приветствия", "Begrüßungen", "Базовые диалоги приветствия"),
        ("restaurant", "В ресторане", "Im Restaurant", "Заказ в ресторане"),
        ("home", "Дома", "Zu Hause", "Разговор дома"),
        ("work", "На работе", "Bei der Arbeit", "В офисе"),
        ("neighbors", "Соседи", "Nachbarn", "Знакомство с соседом"),
        ("shop", "В магазине", "Im Geschäft", "Покупки"),
        ("station", "На вокзале", "Am Bahnhof", "Покупка билета"),
        ("cafe", "В кафе", "Im Café", "Заказ в кафе"),
        ("doctor", "У врача", "Beim Arzt", "Визит к врачу"),
        ("travel", "В поездке", "Unterwegs", "В путешествии"),
        ("weather", "Погода", "Wetter", "Разговор о погоде"),
        ("family", "Семья", "Familie", "О семье"),
        ("hotel", "В отеле", "Im Hotel", "Регистрация в отеле"),
        ("post_office", "На почте", "Auf der Post", "Отправка письма"),
        ("bank", "В банке", "In der Bank", "В банке"),
        ("apartment", "Квартира", "Wohnung", "Просмотр квартиры"),
        ("free_time", "Свободное время", "Freizeit", "Планы на выходные"),
        ("directions", "Дорога", "Wegbeschreibung", "Спросить дорогу"),
        ("clothes", "Магазин одежды", "Im Bekleidungsgeschäft", "Примерка"),
        ("school", "В школе", "In der Schule", "На уроке"),
    ]

    # Читаем существующие диалоги, чтобы не перезаписать
    existing = {}
    for jf in DIALOGUES_DIR.glob("*.json"):
        if jf.name == ".gitkeep":
            continue
        try:
            with open(jf, encoding="utf-8") as f:
                data = json.load(f)
                existing[data["id"]] = data
        except Exception as e:
            print(f"Skip {jf}: {e}")

    for theme_id, name, name_de, description in DIALOGUE_TOPICS:
        if theme_id in existing:
            print(f"Dialogues: {theme_id}.json - kept existing")
            continue
        dialogue = make_dialogue(theme_id)
        obj = {
            "id": theme_id,
            "name": name,
            "name_de": name_de,
            "description": description,
            "level": "A1",
            "dialogue": dialogue["lines"],
            "exercises": dialogue["exercises"],
        }
        path = DIALOGUES_DIR / f"{theme_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        print(f"Dialogues: {path.name} - {len(dialogue['lines'])} lines")

    print("Done.")


def make_dialogue(theme_id):
    """Генерирует диалог и упражнения по теме."""
    templates = {
        "home": (
            [("Anna", "Анна", "Hallo! Ich bin zu Hause.", "Привет! Я дома."), ("Tom", "Том", "Willkommen! Wie war der Tag?", "Добро пожаловать! Как прошёл день?"), ("Anna", "Анна", "Gut, aber ich bin müde.", "Хорошо, но я устала."), ("Tom", "Том", "Möchtest du etwas trinken?", "Хочешь что-нибудь выпить?"), ("Anna", "Анна", "Ja, gern. Einen Tee, bitte.", "Да, с удовольствием. Чай, пожалуйста."), ("Tom", "Том", "Komm, setz dich. Ich mache den Tee.", "Иди, садись. Я сделаю чай.")],
            [("Gut, aber ich ___ müde.", ["bin", "bist", "sind"], 0, "bin — с ich"), ("Möchtest du etwas ___?", ["trinken", "trinkt", "trinke"], 0, "trinken — инфинитив после möchtest")],
        ),
        "work": (
            [("Kollege", "Коллега", "Guten Morgen! Hast du die E-Mail bekommen?", "Доброе утро! Ты получил письмо?"), ("Maria", "Мария", "Ja, danke. Ich antworte gleich.", "Да, спасибо. Отвечу сейчас."), ("Kollege", "Коллега", "Wann ist das Meeting?", "Когда совещание?"), ("Maria", "Мария", "Um 14 Uhr im Konferenzraum.", "В 14 в конференц-зале."), ("Kollege", "Коллега", "Alles klar. Bis gleich!", "Понятно. До скорого!")],
            [("Hast du die E-Mail ___?", ["bekommen", "bekommt", "bekomme"], 0, "bekommen — Partizip II с haben"), ("Wann ___ das Meeting?", ["ist", "sind", "bin"], 0, "ist — Meeting в ед. ч.")],
        ),
        "neighbors": (
            [("Herr Schmidt", "Господин Шмидт", "Guten Tag! Ich bin Ihr neuer Nachbar.", "Добрый день! Я ваш новый сосед."), ("Lisa", "Лиза", "Oh, willkommen! Wo wohnen Sie?", "О, добро пожаловать! Где вы живёте?"), ("Herr Schmidt", "Господин Шмидт", "Im dritten Stock, neben der Treppe.", "На третьем этаже, рядом с лестницей."), ("Lisa", "Лиза", "Sehr schön! Bei Fragen kommen Sie gern.", "Очень хорошо! Если будут вопросы — обращайтесь."), ("Herr Schmidt", "Господин Шмидт", "Danke! Das ist nett.", "Спасибо! Очень мило.")],
            [("Ich bin Ihr ___ Nachbar.", ["neuer", "neue", "neues"], 0, "neuer — муж. род"), ("Wo ___ Sie?", ["wohnen", "wohnt", "wohne"], 0, "wohnen — с Sie")],
        ),
        "shop": (
            [("Verkäufer", "Продавец", "Guten Tag! Kann ich helfen?", "Добрый день! Могу помочь?"), ("Kunde", "Покупатель", "Ich suche eine Jacke.", "Я ищу куртку."), ("Verkäufer", "Продавец", "Welche Größe haben Sie?", "Какой у вас размер?"), ("Kunde", "Покупатель", "Größe M. Und welche Farbe haben Sie?", "Размер M. И какие цвета есть?"), ("Verkäufer", "Продавец", "Blau, schwarz und grau. Probieren Sie an!", "Синий, чёрный и серый. Примерьте!"), ("Kunde", "Покупатель", "Danke. Wo ist die Umkleide?", "Спасибо. Где примерочная?")],
            [("Ich ___ eine Jacke.", ["suche", "suchst", "sucht"], 0, "suche — с ich"), ("Welche ___ haben Sie?", ["Größe", "Größen", "Größer"], 0, "Größe — ед. ч.")],
        ),
        "station": (
            [("Reisender", "Пассажир", "Guten Tag. Eine Fahrkarte nach Hamburg, bitte.", "Добрый день. Один билет в Гамбург, пожалуйста."), ("Angestellter", "Сотрудник", "Einfach oder hin und zurück?", "В одну сторону или туда и обратно?"), ("Reisender", "Пассажир", "Hin und zurück, bitte.", "Туда и обратно, пожалуйста."), ("Angestellter", "Сотрудник", "Das macht 89 Euro. Von Gleis 7, in 20 Minuten.", "С вас 89 евро. Платформа 7, через 20 минут."), ("Reisender", "Пассажир", "Danke! Wo ist Gleis 7?", "Спасибо! Где платформа 7?"), ("Angestellter", "Сотрудник", "Da drüben, links. Gute Fahrt!", "Вон там, слева. Счастливого пути!")],
            [("Eine Fahrkarte ___ Hamburg.", ["nach", "in", "zu"], 0, "nach — город без артикля"), ("Das ___ 89 Euro.", ["macht", "machen", "machst"], 0, "macht — безличное")],
        ),
        "cafe": (
            [("Gast", "Гость", "Guten Tag. Ich hätte gern einen Kaffee und ein Stück Kuchen.", "Добрый день. Мне кофе и кусок пирога, пожалуйста."), ("Kellner", "Официант", "Mit Milch? Wir haben Apfelkuchen und Schokoladenkuchen.", "С молоком? Есть яблочный и шоколадный."), ("Gast", "Гость", "Mit Milch, bitte. Und Apfelkuchen.", "С молоком. И яблочный пирог."), ("Kellner", "Официант", "Sehr gut. Das macht 6 Euro 50.", "Хорошо. С вас 6 евро 50."), ("Gast", "Гость", "Hier bitte. Danke!", "Вот, пожалуйста. Спасибо!")],
            [("Ich hätte gern ___ Kaffee.", ["einen", "eine", "ein"], 0, "einen — Kaffee м.р."), ("Wir ___ Apfelkuchen.", ["haben", "hat", "hast"], 0, "haben — мы")],
        ),
        "doctor": (
            [("Patient", "Пациент", "Guten Tag. Ich habe einen Termin um 10 Uhr.", "Добрый день. У меня приём в 10."), ("Rezeption", "Рецепция", "Name bitte? Ah, hier. Bitte nehmen Sie Platz. Der Arzt kommt gleich.", "Фамилия? Вот. Присядьте, пожалуйста. Врач скоро придёт."), ("Arzt", "Врач", "Guten Tag. Was fehlt Ihnen?", "Добрый день. Что вас беспокоит?"), ("Patient", "Пациент", "Ich habe Kopfschmerzen und Halsweh.", "У меня болит голова и горло."), ("Arzt", "Врач", "Seit wann? Nehmen Sie bitte diese Tabletten, dreimal täglich.", "С какого времени? Принимайте эти таблетки три раза в день."), ("Patient", "Пациент", "Danke, Herr Doktor. Auf Wiedersehen.", "Спасибо, доктор. До свидания.")],
            [("Ich habe einen ___ um 10 Uhr.", ["Termin", "Termine", "Termins"], 0, "Termin — встреча"), ("Was ___ Ihnen?", ["fehlt", "fehlen", "fehle"], 0, "fehlt — что недостаёт")],
        ),
        "travel": (
            [("Tourist", "Турист", "Entschuldigung, wo ist das Museum?", "Извините, где музей?"), ("Passant", "Прохожий", "Geradeaus, dann rechts. Etwa 5 Minuten.", "Прямо, потом направо. Минут 5."), ("Tourist", "Турист", "Danke! Und hat es heute geöffnet?", "Спасибо! А сегодня открыто?"), ("Passant", "Прохожий", "Ja, bis 18 Uhr. Viel Spaß!", "Да, до 18. Приятно провести время!")],
            [("Wo ___ das Museum?", ["ist", "sind", "bin"], 0, "ist — место"), ("Hat es heute ___?", ["geöffnet", "öffnen", "öffnet"], 0, "geöffnet — открыто")],
        ),
        "weather": (
            [("Person A", "Человек А", "Wie ist das Wetter morgen?", "Какая завтра погода?"), ("Person B", "Человек Б", "Laut Wetterbericht wird es sonnig. 22 Grad.", "По прогнозу будет солнечно. 22 градуса."), ("Person A", "Человек А", "Super! Dann gehen wir in den Park.", "Отлично! Тогда пойдём в парк."), ("Person B", "Человек Б", "Gute Idee! Nimm eine Jacke mit, es wird abends kühl.", "Хорошая идея! Возьми куртку, вечером будет прохладно.")],
            [("Wie ___ das Wetter?", ["ist", "sind", "bin"], 0, "ist — погода"), ("Es ___ sonnig.", ["wird", "werden", "werde"], 0, "wird — безличное")],
        ),
        "family": (
            [("Emma", "Эмма", "Das ist ein Foto von meiner Familie.", "Это фото моей семьи."), ("Max", "Макс", "Oh, wer ist das? Deine Mutter?", "О, кто это? Твоя мама?"), ("Emma", "Эмма", "Ja, und das ist mein Vater. Und meine Schwester.", "Да, а это мой отец. И моя сестра."), ("Max", "Макс", "Sie wohnen in Berlin, oder?", "Они живут в Берлине, да?"), ("Emma", "Эмма", "Ja, aber ich wohne hier in München.", "Да, но я живу здесь, в Мюнхене.")],
            [("Das ist ein Foto ___ meiner Familie.", ["von", "aus", "bei"], 0, "von — принадлежность"), ("Wer ___ das?", ["ist", "sind", "bin"], 0, "ist — кто это")],
        ),
        "hotel": (
            [("Gast", "Гость", "Guten Tag. Ich habe eine Reservierung.", "Добрый день. У меня бронь."), ("Rezeption", "Рецепция", "Name bitte? Müller? Ja. Für zwei Nächte. Hier ist Ihr Schlüssel, Zimmer 305.", "Фамилия? Мюллер? Да. На две ночи. Вот ключ, номер 305."), ("Gast", "Гость", "Danke. Wo ist der Aufzug? Und wann ist das Frühstück?", "Спасибо. Где лифт? И когда завтрак?"), ("Rezeption", "Рецепция", "Aufzug links. Frühstück von 7 bis 10 im Erdgeschoss.", "Лифт слева. Завтрак с 7 до 10 на первом этаже."), ("Gast", "Гость", "Perfekt. Danke!", "Отлично. Спасибо!")],
            [("Ich habe eine ___.", ["Reservierung", "Reservierungen", "reservieren"], 0, "Reservierung — бронь"), ("Wo ___ der Aufzug?", ["ist", "sind", "bin"], 0, "ist — где")],
        ),
        "post_office": (
            [("Kunde", "Клиент", "Guten Tag. Ich möchte diesen Brief nach Russland schicken.", "Добрый день. Хочу отправить это письмо в Россию."), ("Angestellter", "Сотрудник", "Luftpost oder normal? Luftpost ist schneller.", "Авиа или обычной? Авиа быстрее."), ("Kunde", "Клиент", "Luftpost, bitte. Was kostet das?", "Авиа, пожалуйста. Сколько стоит?"), ("Angestellter", "Сотрудник", "2 Euro 20. Hier sind die Briefmarken.", "2 евро 20. Вот марки."), ("Kunde", "Клиент", "Danke. Wo ist der Briefkasten?", "Спасибо. Где почтовый ящик?"), ("Angestellter", "Сотрудник", "Draußen links. Nächster!", "Снаружи слева. Следующий!")],
            [("Ich möchte diesen Brief ___.", ["schicken", "schickt", "schicke"], 0, "schicken — инфинитив"), ("Was ___ das?", ["kostet", "kosten", "kostest"], 0, "kostet — сколько стоит")],
        ),
        "bank": (
            [("Kunde", "Клиент", "Guten Tag. Ich möchte Geld abheben.", "Добрый день. Хочу снять деньги."), ("Angestellter", "Сотрудник", "Am Geldautomaten dort. Haben Sie eine Karte?", "В банкомате вон там. У вас есть карта?"), ("Kunde", "Клиент", "Ja. Kann ich hier auch wechseln? Ich brauche Euro.", "Да. Здесь можно обменять? Мне нужны евро."), ("Angestellter", "Сотрудник", "Ja, am Schalter 2. Dort ist kein Andrang.", "Да, у окошка 2. Там нет очереди."), ("Kunde", "Клиент", "Danke!", "Спасибо!")],
            [("Ich möchte Geld ___.", ["abheben", "abhebt", "abhebe"], 0, "abheben — снять"), ("Haben Sie eine ___?", ["Karte", "Karten", "Karten"], 0, "Karte — карта")],
        ),
        "apartment": (
            [("Mieter", "Арендатор", "Guten Tag. Ich habe die Anzeige gelesen. Ist die Wohnung noch frei?", "Добрый день. Я прочитал объявление. Квартира ещё свободна?"), ("Vermieter", "Арендодатель", "Ja. Zwei Zimmer, Küche, Bad. 750 Euro kalt.", "Да. Две комнаты, кухня, ванная. 750 евро без комуслуг."), ("Mieter", "Арендатор", "Wann kann ich die Wohnung besichtigen?", "Когда могу посмотреть?"), ("Vermieter", "Арендодатель", "Morgen um 14 Uhr? Hier die Adresse.", "Завтра в 14? Вот адрес."), ("Mieter", "Арендатор", "Perfekt. Bis morgen!", "Отлично. До завтра!")],
            [("Ist die Wohnung noch ___?", ["frei", "freie", "freier"], 0, "frei — свободна"), ("Wann kann ich die Wohnung ___?", ["besichtigen", "besichtigt", "besichtige"], 0, "besichtigen — посмотреть")],
        ),
        "free_time": (
            [("Anna", "Анна", "Was machst du am Samstag?", "Что делаешь в субботу?"), ("Tom", "Том", "Noch nichts. Warum?", "Пока ничего. А что?"), ("Anna", "Анна", "Lass uns ins Kino gehen. Es gibt einen guten Film.", "Давай сходим в кино. Идёт хороший фильм."), ("Tom", "Том", "Gute Idee! Um wie viel Uhr?", "Хорошая идея! Во сколько?"), ("Anna", "Анна", "Um 20 Uhr. Ich kaufe die Karten online.", "В 20. Куплю билеты онлайн."), ("Tom", "Том", "Super! Bis Samstag.", "Супер! До субботы.")],
            [("Was ___ du am Samstag?", ["machst", "macht", "machen"], 0, "machst — с du"), ("Lass ___ ins Kino gehen.", ["uns", "uns", "wir"], 0, "uns — давай мы")],
        ),
        "directions": (
            [("Tourist", "Турист", "Entschuldigung, wie komme ich zum Rathaus?", "Извините, как пройти к ратуше?"), ("Passant", "Прохожий", "Gehen Sie geradeaus bis zur Ampel, dann links. Das Rathaus ist rechts.", "Идите прямо до светофора, потом налево. Ратуша справа."), ("Tourist", "Турист", "Ist es weit?", "Далеко?"), ("Passant", "Прохожий", "Nein, etwa 5 Minuten zu Fuß.", "Нет, минут 5 пешком."), ("Tourist", "Турист", "Vielen Dank!", "Большое спасибо!")],
            [("Wie ___ ich zum Rathaus?", ["komme", "kommt", "kommen"], 0, "komme — с ich"), ("Gehen Sie ___.", ["geradeaus", "geradeaus", "gerade"], 0, "geradeaus — прямо")],
        ),
        "clothes": (
            [("Verkäufer", "Продавец", "Kann ich helfen? Sucht Sie etwas Bestimmtes?", "Могу помочь? Что-то ищете?"), ("Kundin", "Покупательница", "Ich suche eine Jacke. Etwas Warmes.", "Ищу куртку. Что-то тёплое."), ("Verkäufer", "Продавец", "Welche Größe? Wir haben diese hier in M und L.", "Какой размер? Вот эта есть в M и L."), ("Kundin", "Покупательница", "M, bitte. Kann ich anprobieren?", "M, пожалуйста. Можно примерить?"), ("Verkäufer", "Продавец", "Natürlich. Die Umkleide ist dort hinten.", "Конечно. Примерочная там сзади."), ("Kundin", "Покупательница", "Die passt. Ich nehme sie.", "Подходит. Беру.")],
            [("Ich ___ eine Jacke.", ["suche", "suchst", "sucht"], 0, "suche — с ich"), ("Kann ich ___?", ["anprobieren", "anprobiert", "anprobiere"], 0, "anprobieren — примерить")],
        ),
        "school": (
            [("Lehrer", "Учитель", "Guten Morgen! Öffnet die Bücher, Seite 15.", "Доброе утро! Откройте учебники, страница 15."), ("Schüler", "Ученик", "Herr Müller, ich habe eine Frage. Was bedeutet „Zeit“?", "Господин Мюллер, у меня вопрос. Что значит «Zeit»?"), ("Lehrer", "Учитель", "„Zeit“ bedeutet „time“ auf Englisch. Zeit = время.", "«Zeit» по-английски «time». Время."), ("Schüler", "Ученик", "Danke. Und wie schreibt man das?", "Спасибо. А как это пишется?"), ("Lehrer", "Учитель", "Z-E-I-T. Schreibt das in eure Hefte.", "Z-E-I-T. Запишите в тетради.")],
            [("Öffnet die ___.", ["Bücher", "Buch", "Büchern"], 0, "Bücher — мн. ч."), ("Was ___ „Zeit“?", ["bedeutet", "bedeuten", "bedeute"], 0, "bedeutet — что значит")],
        ),
    }
    if theme_id not in templates:
        # Дефолтный короткий диалог
        lines = [
            {"role": "A", "role_ru": "А", "text": "Guten Tag!", "text_ru": "Добрый день!", "audio_file": f"{theme_id}_01.mp3"},
            {"role": "B", "role_ru": "Б", "text": "Guten Tag! Wie geht es?", "text_ru": "Добрый день! Как дела?", "audio_file": f"{theme_id}_02.mp3"},
            {"role": "A", "role_ru": "А", "text": "Gut, danke!", "text_ru": "Хорошо, спасибо!", "audio_file": f"{theme_id}_03.mp3"},
        ]
        exercises = [{"type": "fill_blank", "question": "Guten ___!", "options": ["Tag", "Morgen", "Abend"], "correct": 0, "explanation": "Guten Tag — добрый день."}]
        return {"lines": lines, "exercises": exercises}

    repliken, ex = templates[theme_id]
    lines = []
    for i, (role, role_ru, text, text_ru) in enumerate(repliken, 1):
        lines.append({
            "role": role,
            "role_ru": role_ru,
            "text": text,
            "text_ru": text_ru,
            "audio_file": f"{theme_id}_{i:02d}.mp3",
        })
    exercises = [{"type": "fill_blank", "question": q, "options": opts, "correct": c, "explanation": expl} for q, opts, c, expl in ex]
    return {"lines": lines, "exercises": exercises}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate phrases/dialogues. Single file from word list, or generate all topics."
    )
    parser.add_argument(
        "--words", "-w",
        type=Path,
        metavar="FILE",
        help="Path to word list (vocabulary JSON or phrases JSON). Used with --output.",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        metavar="FILE",
        help="Target path for generated phrases JSON. Used with --words.",
    )
    parser.add_argument("--id", help="Override category id in output (with --words).")
    parser.add_argument("--name", help="Override category name (with --words).")
    parser.add_argument("--name-de", help="Override category name_de (with --words).")
    parser.add_argument("--description", help="Override category description (with --words).")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.words is not None and args.output is not None:
        run_from_word_list(
            args.words,
            args.output,
            id_=args.id,
            name=args.name,
            name_de=args.name_de,
            description=args.description,
        )
    elif args.words is not None or args.output is not None:
        print("Error: use both --words and --output for single-file mode.")
        exit(1)
    else:
        main()
