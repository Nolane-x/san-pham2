from __future__ import annotations

from dataclasses import dataclass

PRODUCT_NAME = "Nolane Studio"
PRODUCT_TAGLINE = "From idea to motion, without the heavy stack."


@dataclass(frozen=True, slots=True)
class NavItem:
    key: str
    label: str
    eyebrow: str


NAV_ITEMS = (
    NavItem("create", "Create", "START"),
    NavItem("studio", "Studio", "EDIT"),
    NavItem("library", "Library", "LOCAL"),
    NavItem("providers", "Providers", "SYSTEM"),
)


@dataclass(frozen=True, slots=True)
class ThemeTokens:
    canvas: str = "#0A0B0F"
    sidebar: str = "#0D0F15"
    panel: str = "#12151D"
    raised: str = "#171B25"
    hover: str = "#1D2230"
    border: str = "#242A38"
    border_strong: str = "#343B4D"
    text_primary: str = "#F5F7FB"
    text_secondary: str = "#B2BAC9"
    text_muted: str = "#727C8F"
    accent_primary: str = "#8B7CFF"
    accent_primary_hover: str = "#9D91FF"
    accent_secondary: str = "#4ED7C5"
    accent_warm: str = "#FFB86B"
    success: str = "#54D49A"
    danger: str = "#FF6F91"
    radius_sm: int = 8
    radius_md: int = 12
    radius_lg: int = 18


def workspace_spec() -> dict[str, str]:
    return {
        "left_rail": "Scenes",
        "center": "Canvas",
        "right_rail": "Inspector",
        "bottom": "Timeline",
    }


def qss(tokens: ThemeTokens | None = None) -> str:
    t = tokens or ThemeTokens()
    return f"""
    * {{
        font-family: "Segoe UI", "Inter", sans-serif;
        outline: 0;
    }}
    QMainWindow, QWidget#appRoot {{
        background: {t.canvas};
        color: {t.text_primary};
    }}
    QToolTip {{
        color: {t.text_primary};
        background: {t.raised};
        border: 1px solid {t.border_strong};
        border-radius: 6px;
        padding: 6px 8px;
    }}
    QFrame#sidebar {{
        background: {t.sidebar};
        border-right: 1px solid {t.border};
    }}
    QFrame#topbar {{
        background: {t.canvas};
        border-bottom: 1px solid {t.border};
    }}
    QLabel {{ color: {t.text_secondary}; background: transparent; }}
    QLabel#brandName {{
        color: {t.text_primary};
        font-size: 15px;
        font-weight: 700;
    }}
    QLabel#brandMeta {{
        color: {t.text_muted};
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1px;
    }}
    QLabel#pageTitle {{
        color: {t.text_primary};
        font-size: 29px;
        font-weight: 750;
    }}
    QLabel#pageSubtitle {{
        color: {t.text_muted};
        font-size: 13px;
    }}
    QLabel#eyebrow {{
        color: {t.accent_secondary};
        font-size: 10px;
        font-weight: 800;
        letter-spacing: 1.2px;
    }}
    QLabel#sectionTitle {{
        color: {t.text_primary};
        font-size: 15px;
        font-weight: 700;
    }}
    QLabel#muted {{ color: {t.text_muted}; font-size: 12px; }}
    QLabel#metric {{ color: {t.text_primary}; font-size: 20px; font-weight: 750; }}
    QLabel#chip {{
        color: {t.text_secondary};
        background: {t.raised};
        border: 1px solid {t.border};
        border-radius: 10px;
        padding: 4px 8px;
        font-size: 10px;
        font-weight: 650;
    }}
    QFrame#surface {{
        background: {t.panel};
        border: 1px solid {t.border};
        border-radius: {t.radius_md}px;
    }}
    QFrame#surfaceRaised {{
        background: {t.raised};
        border: 1px solid {t.border_strong};
        border-radius: {t.radius_md}px;
    }}
    QFrame#accentSurface {{
        background: #151528;
        border: 1px solid #34325B;
        border-radius: {t.radius_lg}px;
    }}
    QPushButton {{
        min-height: 34px;
        padding: 0 14px;
        color: {t.text_secondary};
        background: {t.raised};
        border: 1px solid {t.border};
        border-radius: {t.radius_sm}px;
        font-size: 12px;
        font-weight: 650;
    }}
    QPushButton:hover {{
        color: {t.text_primary};
        background: {t.hover};
        border-color: {t.border_strong};
    }}
    QPushButton:pressed {{ background: #11141C; }}
    QPushButton#primary {{
        color: #090A0D;
        background: {t.accent_primary};
        border: 1px solid {t.accent_primary};
        font-weight: 800;
    }}
    QPushButton#primary:hover {{
        background: {t.accent_primary_hover};
        border-color: {t.accent_primary_hover};
    }}
    QPushButton#ghost {{ background: transparent; border-color: transparent; }}
    QPushButton#ghost:hover {{ background: {t.hover}; border-color: {t.border}; }}
    QPushButton#navButton {{
        min-height: 48px;
        text-align: left;
        padding: 0 12px;
        background: transparent;
        border: 1px solid transparent;
        border-radius: 10px;
        color: {t.text_muted};
        font-size: 13px;
        font-weight: 650;
    }}
    QPushButton#navButton:hover {{ color: {t.text_primary}; background: {t.hover}; }}
    QPushButton#navButton:checked {{
        color: {t.text_primary};
        background: #191A2A;
        border-color: #2F3150;
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        color: {t.text_primary};
        background: #0F1219;
        border: 1px solid {t.border};
        border-radius: {t.radius_sm}px;
        padding: 8px 10px;
        selection-background-color: {t.accent_primary};
        selection-color: #090A0D;
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
    QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: #6258B9; }}
    QComboBox::drop-down {{ border: 0; width: 22px; }}
    QComboBox QAbstractItemView {{
        background: {t.raised};
        color: {t.text_primary};
        border: 1px solid {t.border_strong};
        selection-background-color: #282643;
    }}
    QListWidget, QTreeWidget, QTableWidget {{
        color: {t.text_secondary};
        background: transparent;
        border: 0;
    }}
    QListWidget::item {{
        min-height: 42px;
        padding: 4px 8px;
        margin: 2px 0;
        border-radius: 8px;
    }}
    QListWidget::item:hover {{ background: {t.hover}; color: {t.text_primary}; }}
    QListWidget::item:selected {{ background: #25233E; color: {t.text_primary}; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: #303646; border-radius: 4px; min-height: 30px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: #303646; border-radius: 4px; min-width: 30px; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QSplitter::handle {{ background: {t.border}; }}
    QSplitter::handle:hover {{ background: #555E78; }}
    QTabWidget::pane {{ border: 0; }}
    QTabBar::tab {{
        color: {t.text_muted};
        background: transparent;
        padding: 9px 11px;
        border-bottom: 2px solid transparent;
    }}
    QTabBar::tab:selected {{ color: {t.text_primary}; border-bottom-color: {t.accent_primary}; }}
    QCheckBox {{ color: {t.text_secondary}; spacing: 8px; }}
    QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {t.border_strong}; border-radius: 5px; background: #0F1219; }}
    QCheckBox::indicator:checked {{ background: {t.accent_primary}; border-color: {t.accent_primary}; }}
    QStatusBar {{ background: {t.sidebar}; color: {t.text_muted}; border-top: 1px solid {t.border}; }}
    """
