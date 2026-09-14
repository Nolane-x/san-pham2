from nolane_studio.ui.design import NAV_ITEMS, PRODUCT_NAME, ThemeTokens, qss, workspace_spec


def test_new_product_identity_is_stable():
    assert PRODUCT_NAME == "Nolane Studio"
    assert [item.key for item in NAV_ITEMS] == ["create", "studio", "library", "providers"]


def test_theme_has_high_contrast_layering_and_signature_accents():
    tokens = ThemeTokens()
    assert tokens.canvas != tokens.panel
    assert tokens.panel != tokens.raised
    assert tokens.text_primary != tokens.text_muted
    assert tokens.accent_primary.startswith("#")
    assert tokens.accent_secondary.startswith("#")
    assert tokens.radius_lg > tokens.radius_sm


def test_studio_workspace_preserves_creator_information_architecture():
    spec = workspace_spec()
    assert spec["left_rail"] == "Scenes"
    assert spec["center"] == "Canvas"
    assert spec["right_rail"] == "Inspector"
    assert spec["bottom"] == "Timeline"


def test_global_stylesheet_uses_native_font_fallback():
    """Do not force a family that can render as tofu on headless Windows."""
    sheet = qss()
    global_rule = sheet.split("}", 1)[0]
    assert "font-family" not in global_rule
