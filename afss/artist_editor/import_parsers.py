"""Parst Bio-Text, den der Nutzer manuell von Babepedia/Boobpedia/Pornopedia kopiert und
einfügt - komplett offline, es wird nichts selbst abgerufen. Gibt ein flaches dict zurück,
dessen Keys exakt den Formularfeld-Namen entsprechen (siehe artist_form.html)."""

import re

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def _strip_footnotes(s: str) -> str:
    return re.sub(r"\[\d+\]", "", s).strip()


def _search(pattern: str, text: str) -> str:
    m = re.search(pattern, text, re.I)
    return _strip_footnotes(m.group(1)) if m else ""


def _extract_height_cm(s: str) -> str:
    m = re.search(r"(\d+(?:\.\d+)?)\s*m\b", s, re.I)
    if m and "." in m.group(1):
        return str(round(float(m.group(1)) * 100))
    m = re.search(r"(\d+)\s*cm", s, re.I)
    return m.group(1) if m else ""


def _extract_weight_kg(s: str) -> str:
    m = re.search(r"(\d+(?:\.\d+)?)\s*kg", s, re.I)
    return str(round(float(m.group(1)))) if m else ""


def _inches_to_cm(inches_str: str) -> str:
    try:
        return str(round(float(inches_str) * 2.54))
    except ValueError:
        return ""


def _parse_measurements_inches(s: str) -> tuple[str, str, str]:
    """'31-26-35' oder '32E-24-30' (Bra-Size-Buchstabe wird ignoriert) -> (bust_cm, waist_cm, hips_cm) in cm.
    Bust bleibt leer, wenn nur eine Körbchengröße (Buchstabe) angegeben ist - das lässt sich nicht
    zuverlässig in cm umrechnen und wird bewusst nicht geraten."""
    parts = [p.strip() for p in re.split(r"[-–—]", s) if p.strip()]
    if len(parts) < 3:
        return "", "", ""
    bust_raw, waist_raw, hips_raw = parts[0], parts[1], parts[2]
    bust_cm = _inches_to_cm(bust_raw) if re.fullmatch(r"\d+(\.\d+)?", bust_raw) else ""
    waist_cm = _inches_to_cm(re.sub(r"[^\d.]", "", waist_raw))
    hips_cm = _inches_to_cm(re.sub(r"[^\d.]", "", hips_raw))
    return bust_cm, waist_cm, hips_cm


def _parse_date_words(s: str) -> dict:
    """'Monday 13th of February 1995' / 'May 9, 1993' -> {year, month, day} (Strings, leer wenn unbekannt)."""
    s = _strip_footnotes(s)
    s = re.sub(r"^(mon|tue|wed|thu|fri|sat|sun)\w*\s+", "", s, flags=re.I)
    s = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", s, flags=re.I)
    s = s.replace(" of ", " ")

    m = re.search(r"\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b", s)
    if m:
        day, month_name, year = m.groups()
        month = _MONTHS.get(month_name.lower())
        if month:
            return {"year": year, "month": str(month), "day": str(int(day))}

    m = re.search(r"\b([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})\b", s)
    if m:
        month_name, day, year = m.groups()
        month = _MONTHS.get(month_name.lower())
        if month:
            return {"year": year, "month": str(month), "day": str(int(day))}

    m = re.search(r"\b(\d{4})\b", s)
    if m:
        return {"year": m.group(1), "month": "", "day": ""}
    return {"year": "", "month": "", "day": ""}


def _split_place(s: str) -> dict:
    """'Cincinnati, Ohio, U.S.' -> {city, state, country}; 'United States' -> {country only}."""
    s = _strip_footnotes(s)
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if len(parts) >= 3:
        return {"city": parts[0], "state": parts[1], "country": parts[-1]}
    if len(parts) == 2:
        return {"city": "", "state": parts[0], "country": parts[1]}
    if len(parts) == 1:
        return {"city": "", "state": "", "country": parts[0]}
    return {"city": "", "state": "", "country": ""}


def _split_csv(s: str) -> list[str]:
    return [p.strip() for p in re.split(r",", _strip_footnotes(s)) if p.strip()]


def _birth_fields(date_str: str) -> dict:
    parsed = _parse_date_words(date_str)
    return {"birth_year": parsed["year"], "birth_month": parsed["month"], "birth_day": parsed["day"]}


def _place_fields(place_str: str) -> dict:
    place = _split_place(place_str)
    return {
        "birth_place_city": place["city"],
        "birth_place_state": place["state"],
        "birth_place_country_iso": place["country"],
    }


def _measurement_fields(measurements_str: str) -> dict:
    bust, waist, hips = _parse_measurements_inches(measurements_str)
    return {"bust_cm": bust, "waist_cm": waist, "hips_cm": hips}


def _years_active_fields(text: str, label: str) -> dict:
    """'Years active: 2022-present' oder 'Years active  2012—present' -> since/until/is_currently_active."""
    m = re.search(rf"{label}\s*[\t:]\s*(\d{{4}})\s*[-–—]\s*(present|\d{{4}})", text, re.I)
    if not m:
        return {}
    since, until = m.groups()
    if until.lower() == "present":
        return {"active_since_year": since, "active_until_year": "", "is_currently_active": True}
    return {"active_since_year": since, "active_until_year": until, "is_currently_active": False}


def _parse_babepedia(text: str) -> dict:
    result = {}

    born = _search(r"Born:\s*(.+)", text)
    if born:
        result.update(_birth_fields(born))

    birthplace = _search(r"Birthplace:\s*(.+)", text)
    if birthplace:
        result.update(_place_fields(birthplace))

    nationality = _search(r"Nationality:\s*\(?([^)\n]+)\)?", text)
    if nationality:
        result["nationality"] = nationality.strip("() ")

    ethnicity = _search(r"Ethnicity:\s*(.+)", text)
    if ethnicity:
        result["ethnicity"] = ethnicity

    professions = _search(r"Professions?:\s*(.+)", text)
    if professions:
        result["occupation"] = _split_csv(professions)

    hair = _search(r"Hair color:\s*(.+)", text)
    if hair:
        result["hair_color"] = hair

    eye = _search(r"Eye color:\s*(.+)", text)
    if eye:
        result["eye_color"] = eye

    height = _search(r"Height:\s*(.+)", text)
    if height:
        cm = _extract_height_cm(height)
        if cm:
            result["height_cm"] = cm

    body_type = _search(r"Body type:\s*(.+)", text)
    if body_type:
        result["body_type"] = body_type

    measurements = _search(r"Measurements:\s*(.+)", text)
    if measurements:
        result.update(_measurement_fields(measurements))

    boobs = _search(r"Boobs:\s*(.+)", text)
    if boobs:
        result["boobs_type"] = boobs

    piercings = _search(r"Piercings:\s*(.+)", text)
    if piercings:
        result["pierce_locations"] = _split_csv(piercings)

    result.update(_years_active_fields(text, "Years active"))

    return result


def _parse_boobpedia(text: str) -> dict:
    result = {}

    aliases = _search(r"Also known as\s*[\t:]\s*(.+)", text)
    if aliases:
        result["aliases"] = _split_csv(aliases)

    born_match = re.search(r"Born\s*[\t:]\s*(.+)\n(.+)?", text, re.I)
    if born_match:
        result.update(_birth_fields(born_match.group(1)))
        place_line = (born_match.group(2) or "").strip()
        if place_line and "," in place_line:
            result.update(_place_fields(place_line))

    result.update(_years_active_fields(text, "Years active"))

    ethnicity = _search(r"Ethnicity\s*[\t:]\s*(.+)", text)
    if ethnicity:
        result["ethnicity"] = ethnicity

    nationality = _search(r"Nationality\s*[\t:]\s*(.+)", text)
    if nationality:
        result["nationality"] = nationality

    measurements = _search(r"Measurements\s*[\t:]\s*(.+)", text)
    if measurements:
        result.update(_measurement_fields(measurements))

    boobs = _search(r"Boobs\s*[\t:]\s*(.+)", text)
    if boobs:
        result["boobs_type"] = boobs

    height = _search(r"Height\s*[\t:]\s*(.+)", text)
    if height:
        cm = _extract_height_cm(height)
        if cm:
            result["height_cm"] = cm

    weight = _search(r"Weight\s*[\t:]\s*(.+)", text)
    if weight:
        kg = _extract_weight_kg(weight)
        if kg:
            result["weight_kg"] = kg

    body_type = _search(r"Body type\s*[\t:]\s*(.+)", text)
    if body_type:
        result["body_type"] = body_type

    eye = _search(r"Eye color\s*[\t:]\s*(.+)", text)
    if eye:
        result["eye_color"] = eye

    hair = _search(r"Hair\s*[\t:]\s*(.+)", text)
    if hair:
        result["hair_color"] = hair

    return result


def _parse_pornopedia(text: str) -> dict:
    result = {}

    dob = _search(r"Date of birth:\s*(.+)", text)
    if dob:
        result.update(_birth_fields(dob))

    place = _search(r"Place of birth:\s*(.+)", text)
    if place:
        result.update(_place_fields(place))

    measurements = _search(r"Measurements:\s*(.+)", text)
    if measurements:
        result.update(_measurement_fields(measurements))

    height = _search(r"Height:\s*(.+)", text)
    if height:
        cm = _extract_height_cm(height)
        if cm:
            result["height_cm"] = cm

    weight = _search(r"Weight:\s*(.+)", text)
    if weight:
        kg = _extract_weight_kg(weight)
        if kg:
            result["weight_kg"] = kg

    ethnicity = _search(r"Ethnicity:\s*(.+)", text)
    if ethnicity:
        result["ethnicity"] = ethnicity

    number_films = _search(r"Number of films:\s*(\d+)", text)
    if number_films:
        result["number_videos"] = number_films
        result["number_videos_is_lower_bound"] = True

    return result


_PARSERS = {
    "babepedia": _parse_babepedia,
    "boobpedia": _parse_boobpedia,
    "pornopedia": _parse_pornopedia,
}


def parse_pasted_bio(source: str, text: str) -> dict:
    parser = _PARSERS.get(source)
    if parser is None or not text.strip():
        return {}
    return parser(text)
