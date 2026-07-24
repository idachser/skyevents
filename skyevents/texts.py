"""Plain-text summary/description rendering, en and ru.

No HTML is produced here: the API returns plain text and the bot does
its own escaping. Numeric params stay on the Event; these templates
are presentation only.
"""

from skyevents.model import Event, EventType

LANGS = ("en", "ru")

# nominative, genitive (ru needs both: "Сближение Луны и Венеры")
BODIES_RU = {
    "sun": ("Солнце", "Солнца"),
    "moon": ("Луна", "Луны"),
    "mercury": ("Меркурий", "Меркурия"),
    "venus": ("Венера", "Венеры"),
    "mars": ("Марс", "Марса"),
    "jupiter": ("Юпитер", "Юпитера"),
    "saturn": ("Сатурн", "Сатурна"),
    "uranus": ("Уран", "Урана"),
    "neptune": ("Нептун", "Нептуна"),
}

BODIES_EN = {
    "sun": "the Sun",
    "moon": "the Moon",
    "mercury": "Mercury",
    "venus": "Venus",
    "mars": "Mars",
    "jupiter": "Jupiter",
    "saturn": "Saturn",
    "uranus": "Uranus",
    "neptune": "Neptune",
}

MOON_PHASES = {
    "new": ("New Moon", "Новолуние"),
    "first_quarter": ("Moon at First Quarter", "Первая четверть"),
    "full": ("Full Moon", "Полнолуние"),
    "last_quarter": ("Moon at Last Quarter", "Последняя четверть"),
}

SEASONS = {
    "march_equinox": ("March equinox", "Весеннее равноденствие"),
    "june_solstice": ("June solstice", "Летнее солнцестояние"),
    "september_equinox": ("September equinox", "Осеннее равноденствие"),
    "december_solstice": ("December solstice", "Зимнее солнцестояние"),
}

APSIDES = {
    "perigee": ("The Moon at perigee", "Луна в перигее"),
    "apogee": ("The Moon at apogee", "Луна в апогее"),
}

PLANET_SUN_EN = {
    "opposition": "{} at opposition",
    "conjunction": "{} at solar conjunction",
    "inferior": "{} at inferior solar conjunction",
    "superior": "{} at superior solar conjunction",
}

PLANET_SUN_RU = {
    "opposition": "{} в противостоянии",
    "conjunction": "{} в соединении с Солнцем",
    "inferior": "{} в нижнем соединении с Солнцем",
    "superior": "{} в верхнем соединении с Солнцем",
}

LUNAR_ECLIPSES = {
    "total": ("Total lunar eclipse", "Полное лунное затмение"),
    "partial": ("Partial lunar eclipse", "Частное лунное затмение"),
    "penumbral": ("Penumbral lunar eclipse",
                  "Полутеневое лунное затмение"),
}

SOLAR_ECLIPSES = {
    "total": ("Total solar eclipse", "Полное солнечное затмение"),
    "annular": ("Annular solar eclipse",
                "Кольцеобразное солнечное затмение"),
    "partial": ("Partial solar eclipse", "Частное солнечное затмение"),
}

STATIONS_EN = {
    "retrograde": "{} enters retrograde motion",
    "direct": "{} ends retrograde motion",
}

STATIONS_RU = {
    "retrograde": "{} переходит к попятному движению",
    "direct": "{} возобновляет прямое движение",
}

SHOWERS_RU = {
    "quadrantids": "Квадрантиды",
    "gamma_ursae_minorids": "гамма-Урсе-Минориды",
    "alpha_centaurids": "альфа-Центавриды",
    "gamma_normids": "гамма-Нормиды",
    "lyrids": "Лириды",
    "pi_puppids": "пи-Пуппиды",
    "eta_aquariids": "эта-Аквариды",
    "eta_lyrids": "эта-Лириды",
    "daytime_arietids": "дневные Ариетиды",
    "june_bootids": "июньские Боотиды",
    "piscis_austrinids": "Писцис-Аустриниды",
    "southern_delta_aquariids": "Южные дельта-Аквариды",
    "alpha_capricornids": "альфа-Каприкорниды",
    "perseids": "Персеиды",
    "kappa_cygnids": "каппа-Цигниды",
    "aurigids": "Ауригиды",
    "september_epsilon_perseids": "сентябрьские эпсилон-Персеиды",
    "daytime_sextantids": "дневные Секстантиды",
    "october_camelopardalids": "октябрьские Камелопардалиды",
    "draconids": "Дракониды",
    "southern_taurids": "Южные Тауриды",
    "delta_aurigids": "дельта-Ауригиды",
    "epsilon_geminids": "эпсилон-Геминиды",
    "orionids": "Ориониды",
    "leonis_minorids": "Леонис-Минориды",
    "northern_taurids": "Северные Тауриды",
    "leonids": "Леониды",
    "alpha_monocerotids": "альфа-Моноцеротиды",
    "november_orionids": "ноябрьские Ориониды",
    "phoenicids": "Фенициды",
    "december_phi_cassiopeids": "декабрьские фи-Кассиопеиды",
    "puppid_velids": "Пуппиды-Велиды",
    "monocerotids": "Моноцеротиды",
    "sigma_hydrids": "сигма-Гидриды",
    "geminids": "Геминиды",
    "comae_berenicids": "Комы-Беренициды",
    "december_leonis_minorids": "декабрьские Леонис-Минориды",
    "ursids": "Урсиды",
}


# Minor planets bright enough to be published (see the generator's
# magnitude cut). Unlike SHOWERS_RU this is looked up with .get(): the
# catalog holds hundreds of objects and grows whenever the elements are
# refreshed, and an unnamed newcomer must fall back to its Latin name,
# not break rendering.
ASTEROIDS_RU = {
    "ceres": "Церера",
    "pallas": "Паллада",
    "juno": "Юнона",
    "vesta": "Веста",
    "astraea": "Астрея",
    "hebe": "Геба",
    "iris": "Ирида",
    "flora": "Флора",
    "metis": "Метида",
    "hygiea": "Гигея",
    "parthenope": "Партенопа",
    "victoria": "Виктория",
    "egeria": "Эгерия",
    "irene": "Ирена",
    "eunomia": "Эвномия",
    "psyche": "Психея",
    "melpomene": "Мельпомена",
    "fortuna": "Фортуна",
    "massalia": "Массалия",
    "lutetia": "Лютеция",
    "kalliope": "Каллиопа",
    "thalia": "Талия",
    "themis": "Фемида",
    "proserpina": "Прозерпина",
    "euterpe": "Эвтерпа",
    "bellona": "Беллона",
    "amphitrite": "Амфитрита",
    "urania": "Урания",
    "fides": "Фидес",
    "laetitia": "Летиция",
    "harmonia": "Гармония",
    "daphne": "Дафна",
    "isis": "Исида",
    "ariadne": "Ариадна",
    "nysa": "Ниса",
    "eugenia": "Евгения",
    "hestia": "Гестия",
    "nemausa": "Немауса",
    "ausonia": "Авзония",
    "leto": "Лето",
    "sappho": "Сафо",
    "angelina": "Ангелина",
    "panopaea": "Панопея",
    "eurynome": "Евринома",
    "alkmene": "Алкмена",
    "julia": "Юлия",
    "thyra": "Тира",
    "antigone": "Антигона",
    "vibilia": "Вибилия",
    "nausikaa": "Навсикая",
    "kleopatra": "Клеопатра",
    "athamantis": "Атамантида",
    "desiderata": "Дезидерата",
    "anahita": "Анахита",
    "bamberga": "Бамберга",
    "dembowska": "Дембовска",
    "eleonora": "Элеонора",
    "papagena": "Папагена",
    "herculina": "Геркулина",
    "interamnia": "Интерамния",
}


def _km(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def render(event: Event, lang: str) -> tuple[str, str]:
    """(summary, description) for the event, plain text"""

    if lang not in LANGS:
        raise ValueError(f"unsupported lang {lang!r}")
    ru = lang == "ru"
    params = event.params

    match event.type:
        case EventType.MOON_PHASE:
            return MOON_PHASES[params["phase"]][ru], ""

        case EventType.SEASON:
            return SEASONS[params["season"]][ru], ""

        case EventType.LUNAR_APSIS:
            distance = _km(params["distance_km"])
            description = (f"Расстояние до Луны {distance} км" if ru
                           else f"Earth–Moon distance {distance} km")
            return APSIDES[params["kind"]][ru], description

        case EventType.PLANET_SUN:
            templates = PLANET_SUN_RU if ru else PLANET_SUN_EN
            name = (BODIES_RU[event.bodies[0]][0] if ru
                    else BODIES_EN[event.bodies[0]])
            return templates[params["kind"]].format(name), ""

        case EventType.ELONGATION:
            east = params["side"] == "east"
            deg = params["elongation_deg"]
            if ru:
                planet = BODIES_RU[event.bodies[0]][0]
                side = "восточной" if east else "западной"
                summary = f"{planet} в наибольшей {side} элонгации"
                description = (f"{deg}° к {'востоку' if east else 'западу'} "
                               f"от Солнца")
            else:
                planet = BODIES_EN[event.bodies[0]]
                summary = (f"{planet} at greatest elongation "
                           f"{'east' if east else 'west'}")
                description = (f"{deg}° {'east' if east else 'west'} "
                               f"of the Sun")
            return summary, description

        case EventType.CLOSE_APPROACH:
            sep = params["separation_deg"]
            if ru:
                names = " и ".join(
                    BODIES_RU[b][1] for b in event.bodies)
                return (f"Сближение {names}",
                        f"Минимальное разделение {sep}°")
            names = " and ".join(BODIES_EN[b] for b in event.bodies)
            return (f"Close approach of {names}",
                    f"Minimum separation {sep}°")

        case EventType.LUNAR_ECLIPSE:
            kind = params["kind"]
            magnitude = params["penumbral_magnitude" if kind == "penumbral"
                               else "umbral_magnitude"]
            description = (f"Фаза затмения {magnitude}" if ru
                           else f"Eclipse magnitude {magnitude}")
            return LUNAR_ECLIPSES[kind][ru], description

        case EventType.SOLAR_ECLIPSE:
            return SOLAR_ECLIPSES[params["kind"]][ru], ""

        case EventType.STATION:
            templates = STATIONS_RU if ru else STATIONS_EN
            name = (BODIES_RU[event.bodies[0]][0] if ru
                    else BODIES_EN[event.bodies[0]])
            return templates[params["direction"]].format(name), ""

        case EventType.ASTEROID_OPPOSITION:
            number, magnitude = params["number"], params["magnitude"]
            distance = params["distance_au"]
            if ru:
                name = ASTEROIDS_RU.get(event.bodies[0], params["name"])
                return (f"Астероид ({number}) {name} в противостоянии",
                        f"Блеск {magnitude}m, {distance} а.е. от Земли")
            return (f"Asteroid ({number}) {params['name']} at opposition",
                    f"Magnitude {magnitude}, {distance} AU from Earth")

        case (EventType.COMET_PERIHELION | EventType.COMET_PERIGEE
              | EventType.COMET_PEAK_BRIGHTNESS):
            # the readable designation ("10P/Tempel", "C/2025 A3
            # (Tsuchinshan)") stands in both languages, as an unnamed
            # asteroid's Latin name does -- there is no ru comet lexicon
            name, magnitude = params["name"], params["magnitude"]
            if event.type == EventType.COMET_PERIHELION:
                distance = params["heliocentric_au"]
                if ru:
                    return (f"Комета {name} в перигелии",
                            f"Блеск {magnitude}m, {distance} а.е. от Солнца")
                return (f"Comet {name} at perihelion",
                        f"Magnitude {magnitude}, {distance} AU from the Sun")
            if event.type == EventType.COMET_PERIGEE:
                distance = params["distance_au"]
                if ru:
                    return (f"Комета {name} в перигее",
                            f"Блеск {magnitude}m, {distance} а.е. от Земли")
                return (f"Comet {name} closest to Earth",
                        f"Magnitude {magnitude}, {distance} AU from Earth")
            if ru:
                return (f"Комета {name} в максимуме блеска",
                        f"Блеск {magnitude}m")
            return (f"Comet {name} at peak brightness",
                    f"Magnitude {magnitude}")

        case EventType.METEOR_SHOWER:
            zhr = params["zhr"]
            if ru:
                name = SHOWERS_RU[event.bodies[0]]
                return (f"Метеорный поток {name}", f"ZHR около {zhr}")
            return (f"{params['name']} meteor shower", f"ZHR around {zhr}")

    raise ValueError(f"no template for event type {event.type}")
