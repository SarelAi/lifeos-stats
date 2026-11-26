# -*- coding: utf-8 -*-
"""Собирает _site/stats.json для доски «LifeOS в цифрах».

Берёт stats.json из репозитория (там цифры Grafana и рекламы, их правят вручную)
и обновляет из API Яндекс Метрики посетителей, страны, карту, график и начала регистрации.
Без токена METRIKA_TOKEN или при ошибке API публикует stats.json как есть.
"""
import datetime, json, os, shutil, sys, urllib.parse, urllib.request

COUNTER = "113327643"
GOAL_START = "676169428"          # «ГЛАВНАЯ: переход на регистрацию (все кнопки)»
DAILY_FROM = "2026-10-20"
TZ = datetime.timezone(datetime.timedelta(hours=4))   # Тбилиси
TOKEN = os.environ.get("METRIKA_TOKEN", "").strip()

NAMES = {"Россия": "RU", "Казахстан": "KZ", "Германия": "DE", "Финляндия": "FI", "Грузия": "GE", "Узбекистан": "UZ",
         "Израиль": "IL", "Объединённые Арабские Эмираты": "AE", "Армения": "AM", "США": "US", "Польша": "PL",
         "Литва": "LT", "Нидерланды": "NL", "Болгария": "BG", "Оман": "OM", "Великобритания": "GB", "Ирландия": "IE",
         "Испания": "ES", "Кипр": "CY", "Катар": "QA", "Франция": "FR", "Греция": "GR", "Италия": "IT", "Чехия": "CZ",
         "Канада": "CA", "Австралия": "AU", "Швеция": "SE", "Словакия": "SK", "Норвегия": "NO", "Сербия": "RS",
         "Швейцария": "CH", "Венгрия": "HU", "Португалия": "PT", "Бельгия": "BE", "Австрия": "AT", "Дания": "DK",
         "Беларусь": "BY", "Словения": "SI", "Хорватия": "HR", "Саудовская Аравия": "SA", "Китай": "CN",
         "Сингапур": "SG", "Босния и Герцеговина": "BA", "Индия": "IN", "Новая Зеландия": "NZ", "Бразилия": "BR",
         "Кыргызстан": "KG", "Республика Корея": "KR", "Турция": "TR", "Вьетнам": "VN"}


def api(params):
    params = dict({"ids": COUNTER, "accuracy": "full", "lang": "ru"}, **params)
    url = "https://api-metrika.yandex.net/stat/v1/data?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": "OAuth " + TOKEN})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def iso(dim):
    code = (dim.get("iso_name") or "").upper()
    if len(code) == 2 and code.isalpha():
        return code
    return NAMES.get(dim.get("name") or "")


def countries(d1, d2, limit=None):
    p = {"metrics": "ym:s:users", "dimensions": "ym:s:regionCountry", "date1": d1, "date2": d2,
         "sort": "-ym:s:users", "limit": limit or 500}
    j = api(p)
    rows = []
    for row in j.get("data", []):
        code = iso(row["dimensions"][0])
        if code:
            rows.append([code, int(row["metrics"][0])])
    return int(j["totals"][0]), rows


def main():
    data = json.load(open("stats.json", encoding="utf-8"))
    now = datetime.datetime.now(TZ)
    today = now.date().isoformat()
    if TOKEN:
        try:
            since = data["since"]
            week = (now.date() - datetime.timedelta(days=6)).isoformat()
            total = int(api({"metrics": "ym:s:users", "date1": since, "date2": today})["totals"][0])
            j = api({"metrics": "ym:s:users", "dimensions": "ym:s:date", "date1": DAILY_FROM, "date2": today,
                     "sort": "ym:s:date", "limit": 1000})
            by_day = {r["dimensions"][0]["name"]: int(r["metrics"][0]) for r in j.get("data", [])}
            daily, d = [], datetime.date.fromisoformat(DAILY_FROM)
            while d <= now.date():
                daily.append([d.isoformat(), by_day.get(d.isoformat(), 0)])
                d += datetime.timedelta(days=1)
            all_v, all_rows = countries(since, today)
            week_v, week_rows = countries(week, today, 15)
            today_v, today_rows = countries(today, today, 15)
            if not (today_v <= week_v <= all_v) or not all_rows:
                raise ValueError("непохожие цифры: %s %s %s" % (today_v, week_v, all_v))
            data["visitorsTotal"] = total
            data["daily"] = daily
            data["periods"] = {"all": {"visitors": all_v, "rows": all_rows[:15]},
                               "week": {"visitors": week_v, "rows": week_rows},
                               "today": {"visitors": today_v, "rows": today_rows}}
            data["map"] = all_rows
            data["countriesLabel"] = "%d+" % (len(all_rows) // 10 * 10)
            ads = data.get("ads", {})
            if "funnel" in ads:
                ads["funnel"]["visitors"] = total
                try:
                    started = api({"metrics": "ym:s:goal%susers" % GOAL_START, "date1": since, "date2": today})
                    ads["funnel"]["started"] = int(started["totals"][0])
                except Exception as e:  # цель не прочиталась: оставляем прошлое значение
                    print("goal users skipped:", e, file=sys.stderr)
            data["updatedAt"] = now.strftime("%Y-%m-%dT%H:%M:00+04:00")
            print("Метрика: обновлено", data["updatedAt"], "посетителей", total)
        except Exception as e:
            print("Метрика не ответила, публикую прошлые цифры:", e, file=sys.stderr)
    else:
        print("METRIKA_TOKEN не задан, публикую stats.json как есть", file=sys.stderr)
    os.makedirs("_site", exist_ok=True)
    shutil.copy("index.html", "_site/index.html")
    json.dump(data, open("_site/stats.json", "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main()
