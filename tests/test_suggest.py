from afss.suggest import suggest_action


def test_suggest_trash_for_known_junk_folders():
    assert suggest_action("$RECYCLE.BIN") == "trash"
    assert suggest_action("System Volume Information") == "trash"
    assert suggest_action(".Spotlight-V100") == "trash"


def test_suggest_category_for_generic_words():
    assert suggest_action("Pics") == "category"
    assert suggest_action("Chat") == "category"
    assert suggest_action("Wallpaper") == "category"


def test_suggest_none_for_proper_noun_like_names():
    assert suggest_action("Forest Whore") is None
    assert suggest_action("sunnykitsunexo") is None
    assert suggest_action("atv") is None


def test_suggest_none_for_empty():
    assert suggest_action("") is None
