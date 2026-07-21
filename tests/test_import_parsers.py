from afss.artist_editor.import_parsers import parse_pasted_bio

BABEPEDIA_SAMPLE = """
Awlivv
20 📷
Add to favoritesAdd her to my list
Awlivv Biography
Personal
Age: 31 years old
Born: Monday 13th of February 1995
Years active: 2022-present (started around 27 years old; 4 years active)
Birthplace: United States
Nationality:  (American)
Ethnicity: Caucasian
Professions: Activist, Adult Model, Fetish Model, Influencer, Porn Star, TikTok Star
Body
Hair color: Brown
Eye color: Grey
Height: 5'4" (or 162 cm) (Petite)
Body type: Slim
Measurements: 31–26–35 (B–W–H) · WHR 0.74
Boobs: Fake/Enhanced
Tattoos: Various
Piercings: Various
"""

BOOBPEDIA_SAMPLE = """
Bonnie Rotten
Personal
Also known as\tAlaina Hicks, Alaina James, Elena De Santis, Dixie
Born\tMay 9, 1993 (age 33)
Cincinnati, Ohio, U.S.
Years active\t2012—present
Ethnicity\tWhite
Nationality\tAmerican
Body
Measurements\t32E-24-30
Bra/cup size\t32E (70E)
Boobs\tEnhanced[1]
Height\t5 ft 7 in (1.70 m)
Weight\t106 lb (48 kg)
Body type\tSlim
Eye color\tBrown
Hair\tBlack, Brown
"""

PORNOPEDIA_SAMPLE = """
Bonnie Rotten
Date of birth:\tMay 9, 1993
(age: 33)  [1]
Place of birth:\tOhio, United States[1]
Measurements:\t32DD-24-30[1]
Height:\t170 cm (5 ft 7 in) (170 cm)[1]
Weight:\t105 lbs (48 kg)[1]
Ethnicity:\tItalian, German, Polish, Jewish[1]
Number of films:\t273[1]
"""


def test_parse_babepedia_extracts_core_fields():
    result = parse_pasted_bio("babepedia", BABEPEDIA_SAMPLE)

    assert result["birth_year"] == "1995"
    assert result["birth_month"] == "2"
    assert result["birth_day"] == "13"
    assert result["birth_place_country_iso"] == "usa"
    assert result["nationality"] == "usa"
    assert result["ethnicity"] == "caucasian"
    assert result["occupation"] == [
        "activist", "adult model", "fetish model", "influencer", "porn star", "tiktok star",
    ]
    assert result["hair_color"] == "brown"
    assert result["eye_color"] == "grey"
    assert result["height_cm"] == "162"
    assert result["body_type"] == "slim"
    assert result["boobs_type"] == "enhanced"
    assert result["pierce_locations"] == ["various"]
    assert result["active_since_year"] == "2022"
    assert result["is_currently_active"] is True


def test_parse_babepedia_converts_measurements_inches_to_cm():
    result = parse_pasted_bio("babepedia", BABEPEDIA_SAMPLE)
    # 31in*2.54=78.74->79, 26in*2.54=66.04->66, 35in*2.54=88.9->89
    assert result["bust_cm"] == "79"
    assert result["waist_cm"] == "66"
    assert result["hips_cm"] == "89"


def test_parse_boobpedia_extracts_aliases_and_birthplace():
    result = parse_pasted_bio("boobpedia", BOOBPEDIA_SAMPLE)

    # Aliases sind Eigennamen und bleiben in Originalschreibweise erhalten.
    assert result["aliases"] == ["Alaina Hicks", "Alaina James", "Elena De Santis", "Dixie"]
    assert result["birth_year"] == "1993"
    assert result["birth_month"] == "5"
    assert result["birth_day"] == "9"
    assert result["birth_place_city"] == "cincinnati"
    assert result["birth_place_state"] == "ohio"
    assert result["birth_place_country_iso"] == "usa"
    assert result["active_since_year"] == "2012"
    assert result["is_currently_active"] is True
    assert result["ethnicity"] == "white"
    assert result["nationality"] == "usa"


def test_parse_boobpedia_converts_height_and_weight():
    result = parse_pasted_bio("boobpedia", BOOBPEDIA_SAMPLE)
    assert result["height_cm"] == "170"
    assert result["weight_kg"] == "48"
    assert result["body_type"] == "slim"
    assert result["eye_color"] == "brown"


def test_parse_boobpedia_normalizes_enhanced_boobs_type():
    result = parse_pasted_bio("boobpedia", BOOBPEDIA_SAMPLE)
    assert result["boobs_type"] == "enhanced"


def test_parse_pornopedia_extracts_core_fields():
    result = parse_pasted_bio("pornopedia", PORNOPEDIA_SAMPLE)

    assert result["birth_year"] == "1993"
    assert result["birth_month"] == "5"
    assert result["birth_day"] == "9"
    assert result["birth_place_state"] == "ohio"
    assert result["birth_place_country_iso"] == "usa"
    assert result["height_cm"] == "170"
    assert result["weight_kg"] == "48"
    assert result["ethnicity"] == "italian, german, polish, jewish"
    assert result["number_videos"] == "273"
    assert result["number_videos_is_lower_bound"] is True


def test_parse_unknown_source_returns_empty_dict():
    assert parse_pasted_bio("unknown_site", "some text") == {}


def test_parse_empty_text_returns_empty_dict():
    assert parse_pasted_bio("babepedia", "") == {}
    assert parse_pasted_bio("babepedia", "   ") == {}


def test_parse_babepedia_missing_fields_are_simply_absent():
    minimal = "Born: Monday 13th of February 1995\nHair color: Brown"
    result = parse_pasted_bio("babepedia", minimal)
    assert result["hair_color"] == "brown"
    assert "eye_color" not in result
    assert "height_cm" not in result


def test_country_name_maps_to_iso3_unknown_falls_back_to_lowercase():
    text = "Birthplace: Wakanda"
    result = parse_pasted_bio("babepedia", text)
    # Unbekanntes Land: kein Code geraten, aber konsistent lowercase.
    assert result["birth_place_country_iso"] == "wakanda"


def test_boobs_type_natural_stays_natural():
    text = "Boobs: Natural"
    result = parse_pasted_bio("babepedia", text)
    assert result["boobs_type"] == "natural"
