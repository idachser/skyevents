from datetime import datetime, timezone

import pytest

from skyevents import texts
from skyevents.generators.meteor_showers import SHOWERS
from skyevents.model import Event, EventType

DT = datetime(2026, 7, 3, 13, 2, tzinfo=timezone.utc)

# one sample per event type: (event, expected en, expected ru)
SAMPLES = [
    (Event.create(EventType.MOON_PHASE, DT, ["moon"], {"phase": "full"}),
     ("Full Moon", ""),
     ("Полнолуние", "")),
    (Event.create(EventType.SEASON, DT, ["sun"],
                  {"season": "june_solstice"}),
     ("June solstice", ""),
     ("Летнее солнцестояние", "")),
    (Event.create(EventType.LUNAR_APSIS, DT, ["moon"],
                  {"kind": "perigee", "distance_km": 356500.0}),
     ("The Moon at perigee", "Earth–Moon distance 356 500 km"),
     ("Луна в перигее", "Расстояние до Луны 356 500 км")),
    (Event.create(EventType.PLANET_SUN, DT, ["jupiter"],
                  {"kind": "opposition"}),
     ("Jupiter at opposition", ""),
     ("Юпитер в противостоянии", "")),
    (Event.create(EventType.PLANET_SUN, DT, ["venus"],
                  {"kind": "superior"}),
     ("Venus at superior solar conjunction", ""),
     ("Венера в верхнем соединении с Солнцем", "")),
    (Event.create(EventType.ELONGATION, DT, ["mercury"],
                  {"side": "east", "elongation_deg": 27.5}),
     ("Mercury at greatest elongation east", "27.5° east of the Sun"),
     ("Меркурий в наибольшей восточной элонгации",
      "27.5° к востоку от Солнца")),
    (Event.create(EventType.CLOSE_APPROACH, DT, ["venus", "moon"],
                  {"separation_deg": 0.5, "sun_elongation_deg": 40.0}),
     ("Close approach of the Moon and Venus", "Minimum separation 0.5°"),
     ("Сближение Луны и Венеры", "Минимальное разделение 0.5°")),
    (Event.create(EventType.LUNAR_ECLIPSE, DT, ["moon"],
                  {"kind": "total", "umbral_magnitude": 1.15,
                   "penumbral_magnitude": 2.2}),
     ("Total lunar eclipse", "Eclipse magnitude 1.15"),
     ("Полное лунное затмение", "Фаза затмения 1.15")),
    (Event.create(EventType.SOLAR_ECLIPSE, DT, ["sun", "moon"],
                  {"kind": "annular", "separation_deg": 0.2,
                   "radius_ratio": 0.97}),
     ("Annular solar eclipse", ""),
     ("Кольцеобразное солнечное затмение", "")),
    (Event.create(EventType.METEOR_SHOWER, DT, ["perseids"],
                  {"name": "Perseids", "zhr": 100,
                   "solar_lon_deg": 140.0}),
     ("Perseids meteor shower", "ZHR around 100"),
     ("Метеорный поток Персеиды", "ZHR около 100")),
]


def test_every_event_type_has_a_sample():
    assert {e.type for e, _, _ in SAMPLES} == set(EventType)


@pytest.mark.parametrize("event,expected_en,expected_ru", SAMPLES)
def test_render(event, expected_en, expected_ru):
    assert texts.render(event, "en") == expected_en
    assert texts.render(event, "ru") == expected_ru


def test_plain_text_no_html():
    for event, _, _ in SAMPLES:
        for lang in texts.LANGS:
            for text in texts.render(event, lang):
                assert "<" not in text and ">" not in text


def test_every_shower_has_a_russian_name():
    assert set(texts.SHOWERS_RU) == {slug for slug, _, _, _ in SHOWERS}


def test_unsupported_lang_rejected():
    event = SAMPLES[0][0]
    with pytest.raises(ValueError):
        texts.render(event, "de")
