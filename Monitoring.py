import sys
import os
import json
from pathlib import Path
from datetime import datetime, timedelta

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QPushButton,
    QSpinBox, QDoubleSpinBox, QScrollArea, QFrame, QSystemTrayIcon, QMenu, QDialog,
    QAbstractItemView, QAbstractSpinBox, QStyle, QSizePolicy, QCheckBox, QTimeEdit,
    QStackedWidget, QLayout, QLineEdit, QGraphicsDropShadowEffect, QComboBox, QGraphicsOpacityEffect, QFileDialog
)
from PyQt5.QtCore import (
    Qt, QTimer, QTime, QPoint, QRect, QSize, QUrl, QSettings, pyqtSignal,
    QThreadPool, QRunnable, QObject, QEvent, QMimeData, QPropertyAnimation, QEasingCurve
)
from PyQt5.QtGui import (
    QColor, QDesktopServices, QPainter, QPen, QFontMetrics, QFont, QDrag )

MAX_CACHE_SIZE = 10000
TIMER_INTERNAL = 3600*1000 # 1 час
SAVE_DIR = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local' / 'share')) / 'monitoring'
SAVE_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# МАСШТАБ ИНТЕРФЕЙСА — все параметры масштаба только в этом блоке
# ---------------------------------------------------------------------------
# Эталон: 1920x1080 физических пикселей -> UI_SCALE = 1.0.
# BASE_PIXEL_RATIO — калибровка «эталонных» чисел в коде: раньше тот же вид
# давал UI_SCALE = 0.7, теперь его даёт UI_SCALE = 1.0.
# Если вашим эталоном реально был 0.8 — поставьте 0.8.
BASE_PIXEL_RATIO  = 0.7

REF_SCREEN_HEIGHT = 1080.0      # эталонная высота, физические px
REF_SCREEN_WIDTH  = 1920.0      # используется только в режиме "fit"

SCALE_MODE   = "height"         # "height" | "fit" | "manual"
SCALE_MANUAL = 1.0              # значение для SCALE_MODE = "manual"
SCALE_MIN    = 0.6              # нижний ограничитель
SCALE_MAX    = 1.5              # верхний ограничитель
SCALE_ROUND  = int              # int — усечение как в исходнике; round — округление

UI_SCALE = 1.0                  # рабочее значение, ставится init_ui_scale()



def s(val):
    """Эталонные пиксели -> реальные с учётом масштаба."""
    return SCALE_ROUND(val * UI_SCALE * BASE_PIXEL_RATIO)


def calc_ui_scale(screen=None):
    """1080p -> 1.0; 1440p -> 1.33; 2160p -> 2.0; 720p -> 0.67."""
    if SCALE_MODE == "manual":
        raw = SCALE_MANUAL
    else:
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            raw = 1.0
        else:
            dpr = screen.devicePixelRatio() or 1.0
            geo = screen.geometry()
            raw = (geo.height() * dpr) / REF_SCREEN_HEIGHT
            if SCALE_MODE == "fit":
                raw = min(raw, (geo.width() * dpr) / REF_SCREEN_WIDTH)
    return max(SCALE_MIN, min(SCALE_MAX, raw))


def init_ui_scale(screen=None):
    """Вызывать строго до создания любых виджетов и стилей."""
    global UI_SCALE
    UI_SCALE = calc_ui_scale(screen)
    return UI_SCALE


# --- Шрифты (эталонные px, применяются через s()) ---
FONT_XL, FONT_L, FONT_TITLE = 32, 24, 20
FONT_BTN_MAIN, FONT_BTN, FONT_INPUT = 16, 20, 18
FONT_TABLE, FONT_MENU, FONT_TEXT = 16, 14, 18
FONT_TEXT_COMPACT = 16

# --- Геометрия (эталонные px) ---
WIDGET_BLOCK_WIDTH  = 300
WIDGET_BLOCK_HEIGHT = 550
DETAIL_DATA_ROWS    = 20        # сколько строк видно в раскрытых данных блока

ALL_COLUMNS = [
    "filename", "date", "time", "DOY", "daytime", "file_records", "used_records",
    "Tau", "qc_Tau", "rand_err_Tau", "H", "qc_H", "rand_err_H", "LE", "qc_LE", "rand_err_LE", 
    "co2_flux", "qc_co2_flux", "rand_err_co2_flux", "h2o_flux", "qc_h2o_flux", "rand_err_h2o_flux", 
    "ch4_flux", "qc_ch4_flux", "rand_err_ch4_flux", "none_flux", "qc_none_flux", "rand_err_none_flux",
    "H_strg", "LE_strg", "co2_strg", "h2o_strg", "ch4_strg", "none_strg",
    "co2_v-adv", "h2o_v-adv", "ch4_v-adv", "none_v-adv",
    "co2_molar_density", "co2_mole_fraction", "co2_mixing_ratio", "co2_time_lag", "co2_def_timelag",
    "h2o_molar_density", "h2o_mole_fraction", "h2o_mixing_ratio", "h2o_time_lag", "h2o_def_timelag",
    "ch4_molar_density", "ch4_mole_fraction", "ch4_mixing_ratio", "ch4_time_lag", "ch4_def_timelag",
    "none_molar_density", "none_mole_fraction", "none_mixing_ratio", "none_time_lag", "none_def_timelag",
    "sonic_temperature", "air_temperature", "air_pressure", "air_density", 
    "air_heat_capacity", "air_molar_volume", "ET", "water_vapor_density", 
    "e", "es", "specific_humidity", "RH", "VPD", "Tdew",
    "u_unrot", "v_unrot", "w_unrot", "u_rot", "v_rot", "w_rot",
    "wind_speed", "max_wind_speed", "wind_dir", "yaw", "pitch", "roll",
    "u*", "TKE", "L", "(z-d)/L", "bowen_ratio", "T*", 
    "model", "x_peak", "x_offset", "x_10%", "x_30%", "x_50%", "x_70%", "x_90%",
    "un_Tau", "Tau_scf", "un_H", "H_scf", "un_LE", "LE_scf", 
    "un_co2_flux", "co2_scf", "un_h2o_flux", "h2o_scf", 
    "un_ch4_flux", "ch4_scf", "un_none_flux", "un_none_scf",
    "spikes_hf", "amplitude_resolution_hf", "drop_out_hf", "absolute_limits_hf",
    "skewness_kurtosis_hf", "skewness_kurtosis_sf", "discontinuities_hf", "discontinuities_sf",
    "timelag_hf", "timelag_sf", "attack_angle_hf", "non_steady_wind_hf",
    "u_spikes", "v_spikes", "w_spikes", "ts_spikes", "co2_spikes", "h2o_spikes", "ch4_spikes", "none_spikes",
    "head_detect_LI-7200", "t_out_LI-7200", "t_in_LI-7200", "aux_in_LI-7200", 
    "delta_p_LI-7200", "chopper_LI-7200", "detector_LI-7200", "pll_LI-7200", "sync_LI-7200", 
    "chopper_LI-7500", "detector_LI-7500", "pll_LI-7500", "sync_LI-7500",
    "not_ready_LI-7700", "no_signal_LI-7700", "re_unlocked_LI-7700", "bad_temp_LI-7700",
    "laser_temp_unregulated_LI-7700", "block_temp_unregulated_LI-7700", "motor_spinning_LI-7700",
    "pump_on_LI-7700", "top_heater_on_LI-7700", "bottom_heater_on_LI-7700", "calibrating_LI-7700",
    "motor_failure_LI-7700", "bad_aux_tc1_LI-7700", "bad_aux_tc2_LI-7700", "bad_aux_tc3_LI-7700",
    "box_connected_LI-7700", "mean_value_RSSI_LI-7200", "mean_value_LI-7500",
    "u_var", "v_var", "w_var", "ts_var", "co2_var", "h2o_var", "ch4_var", "none_var",
    "w/ts_cov", "w/co2_cov", "w/h2o_cov", "w/ch4_cov", "w/none_cov",
    "co2_mean", "h2o_mean", "air_p_mean", "vin_sf_mean", "dew_point_mean",
    "avg_signal_strength_7200_mean", "co2_signal_strength_7200_mean", 
    "h2o_signal_strength_7200_mean", "delta_signal_strength_7200_mean",
    "flowrate_mean", "hit_power_mean", "hit_vin_mean", "ch4_mean", "rssi_77_mean", "CHK"
]

PARAM_RANGES = {
    "co2_molar_density": (14.0, 25.0), "co2_mixing_ratio": (350.0, 600.0),
    "h2o_molar_density": (100.0, 1200.0), "h2o_mixing_ratio": (3.0, 30.0),
    "ch4_mixing_ratio": (1.5, 6.0), "ch4_molar_density": (0.05, 0.2),
    "air_pressure": (96000.0, 100000.0), "flowrate_mean": (10.0, 15.0),
    "co2_signal_strength_7200_mean": (85.0, 100.0), "h2o_signal_strength_7200_mean": (85.0, 100.0),
    "avg_signal_strength_7200_mean": (85.0, 100.0), "delta_signal_strength_7200_mean": (0.0, 3.0),
    "rssi_77_mean": (40.0, 85.0), "mean_value_RSSI_LI-7200": (40.0, 100.0),
    "u_unrot": (-15.0, 15.0), "v_unrot": (-15.0, 15.0), "w_unrot": (-2.0, 2.0),
    "wind_speed": (0.0, 20.0), "wind_dir": (0.0, 360.0),
    "sonic_temperature": (-40.0, 50.0), "air_temperature": (-40.0, 40.0), "RH": (20.0, 100.0),
    "t_out_LI-7200": (0.0, 0.0), "t_in_LI-7200": (0.0, 0.0)
}

TEMP_COLUMNS = {"sonic_temperature", "air_temperature", "Tdew"}

WIDGET_MAIN_COLUMNS = [
    ("date", "Дата"), ("time", "Время"),
    ("co2_mixing_ratio", "CO2 ppm"), ("ch4_mixing_ratio", "CH4 ppb"),
    ("sonic_temperature", "TS (°C)"), ("air_temperature", "TA (°C)"),
    ("wind_speed", "U (m/s)"), ("wind_dir", "Dir (°)"),
    ("mean_value_RSSI_LI-7200", "RSSI 7200"), ("rssi_77_mean", "RSSI 7700"),
    ("co2_signal_strength_7200_mean", "CO2 SS"), 
    ("t_out_LI-7200", "T_out"), ("t_in_LI-7200", "T_in")
]

WIDGET_BLOCK_WIDTH = 300
WIDGET_BLOCK_HEIGHT = 550

# ---------------------------------------------------------------------------
# ПАЛИТРА И ГЕОМЕТРИЯ ОФОРМЛЕНИЯ
# ---------------------------------------------------------------------------
class P:
    bg          = "#eef2f7"
    bg_deep     = "#e3eaf3"
    surface     = "#ffffff"
    inset       = "#e9eff6"
    border      = "#dce4ee"
    border_mid  = "#c8d5e4"
    ink         = "#1e293b"
    ink_soft    = "#475569"
    muted       = "#78889f"
    faint       = "#9aa8bd"
    accent      = "#3b82f6"
    accent_deep = "#2563eb"
    accent_press= "#1d4ed8"
    accent_tint = "#e8f1fe"
    accent_edge = "#b9d7fb"
    ok          = "#22c55e"
    ok_deep     = "#15803d"
    ok_press    = "#16a34a"
    ok_edge     = "#14532d"
    ok_ink      = "#052e16"
    ok_tint     = "#e6f7ed"
    warn        = "#f59e0b"
    warn_deep   = "#b45309"
    bad         = "#ef4444"
    bad_hover   = "#dc2626"
    bad_deep    = "#b91c1c"
    bad_tint    = "#fdeaea"
    bad_edge    = "#f6c9c9"
    violet      = "#8b5cf6"
    idle        = "#94a3b8"

R_CARD, R_BTN, R_INPUT, R_CHIP = 14, 10, 8, 9
CARD_SHADOW = True

# Геометрия полей ввода — общая для QSS и расчёта ширины
FIELD_PAD_X   = 6      # горизонтальный padding, эталонные px
FIELD_PAD_Y   = 3      # вертикальный padding, эталонные px
FIELD_BTN_W   = 16     # ширина кнопок спинбокса, эталонные px
FIELD_COMBO_W = 18     # ширина зоны стрелки комбобокса, эталонные px
FIELD_BORDER  = 1      # рамка, реальные px (не масштабируется)


def field_width(sample, buttons=False, btn_ref=None, min_ref=64):
    """Ширина поля = самый длинный текст + padding + рамка + запас.
    Кнопки по умолчанию отключены через QAbstractSpinBox.NoButtons."""
    f = QFont()
    f.setPixelSize(max(1, s(FONT_INPUT)))
    fm = QFontMetrics(f)
    adv = fm.horizontalAdvance(sample) if hasattr(fm, "horizontalAdvance") else fm.width(sample)
    chrome = 2 * s(FIELD_PAD_X) + 2 * FIELD_BORDER + s(10)
    return max(s(min_ref), adv + chrome)


# ---------------------------------------------------------------------------
# СТИЛИ
# ---------------------------------------------------------------------------
class Styles:
    # ---------- полотно и скроллбары ----------
    @staticmethod
    def app_shell():
        return f"""
            #blocksRoot, #blocksPage, #mapViewport, #mainScroll {{
                background: transparent; border: none;
            }}
            QScrollBar:vertical {{
                background: {P.bg_deep}; width: {s(10)}px;
                border-radius: {s(5)}px; margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {P.border_mid}; border-radius: {s(5)}px; min-height: {s(30)}px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {P.accent}; }}
            QScrollBar:horizontal {{
                background: {P.bg_deep}; height: {s(10)}px;
                border-radius: {s(5)}px; margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: {P.border_mid}; border-radius: {s(5)}px; min-width: {s(30)}px;
            }}
            QScrollBar::handle:horizontal:hover {{ background: {P.accent}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
            QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
        """

    @staticmethod
    def shell_normal():
        return f"#centralWidget {{ background-color: {P.bg}; border: none; }}"

    @staticmethod
    def central_widget():
        return f"#centralWidget {{ background-color: {P.bg}; border: 1px solid {P.border_mid}; }}"

    @staticmethod
    def transparent_bg():
        return "background: transparent; border: none;"

    # ---------- карточка блока ----------
    @staticmethod
    def block_detail():
        return f"""
            QFrame#block {{
                background-color: {P.surface};
                border: 1px solid {P.border};
                border-radius: {s(R_CARD)}px;
            }}
        """

    @staticmethod
    def block_compact():
        return f"""
            QFrame#block {{
                background-color: {P.surface};
                border: 1px solid {P.border};
                border-radius: {s(R_CARD)}px;
            }}
        """

    @staticmethod
    def settings_card():
        return f"""
            QFrame#settingsCard {{
                background-color: {P.inset};
                border: 1px solid {P.border};
                border-radius: {s(R_BTN + 2)}px;
            }}
        """

    @staticmethod
    def info_card():
        return f"""
            QFrame#infoCard {{
                background-color: {P.inset};
                border: 1px solid {P.border};
                border-radius: {s(R_BTN + 2)}px;
            }}
        """

    @staticmethod
    def separator():
        return f"background-color: {P.border}; border: none;"

    @staticmethod
    def section_caption():
        return f"""
            QLabel {{
                color: {P.muted}; font-size: {s(FONT_INPUT)}px; font-weight: bold;
                background: transparent; border: none;
                padding: {s(4)}px 0px 0px 0px;
            }}
        """

    @staticmethod
    def section_rule():
        return f"background-color: {P.border_mid}; border: none;"

    # ---------- текст ----------
    @staticmethod
    def name_edit():
        return f"""
            QLineEdit {{
                border: 1px solid transparent; background: transparent;
                color: {P.ink}; font-weight: bold; font-size: {s(FONT_TITLE)}px;
                padding: {s(2)}px {s(4)}px; border-radius: {s(6)}px;
                selection-background-color: {P.accent}; selection-color: #ffffff;
            }}
            QLineEdit:hover {{ background: {P.inset}; }}
            QLineEdit:focus {{ background: {P.surface}; border: 1px solid {P.accent_edge}; }}
        """

    @staticmethod
    def path_label():
        return f"color: {P.muted}; font-size: {s(FONT_TEXT)}px; background: transparent; border: none;"

    @staticmethod
    def label_input():
        return f"""
            QLabel {{ color: {P.ink_soft}; font-size: {s(FONT_INPUT)}px; background: transparent; border: none; }}
            QLabel:disabled {{ color: {P.faint}; }}
        """

    @staticmethod
    def info_text():
        return f"color: {P.ink_soft}; font-size: {s(FONT_TEXT)}px; background: transparent; border: none;"

    @staticmethod
    def alert_text():
        return f"color: {P.muted}; font-size: {s(FONT_TEXT)}px; background: transparent; border: none;"

    @staticmethod
    def compact_meta():
        return f"color: {P.muted}; font-size: {s(12)}px; background: transparent; border: none;"

    # ---------- поля ввода ----------
    @staticmethod
    def input_field():
        return f"""
            QSpinBox, QDoubleSpinBox, QTimeEdit, QComboBox {{
                background: {P.surface}; color: {P.ink};
                border: {FIELD_BORDER}px solid {P.border_mid}; border-radius: {s(R_INPUT)}px;
                padding: {s(FIELD_PAD_Y)}px {s(FIELD_PAD_X)}px; font-size: {s(FONT_INPUT)}px;
                selection-background-color: {P.accent}; selection-color: #ffffff;
            }}
            QSpinBox:hover, QDoubleSpinBox:hover, QTimeEdit:hover, QComboBox:hover {{
                border-color: {P.accent_edge};
            }}
            QSpinBox:focus, QDoubleSpinBox:focus, QTimeEdit:focus, QComboBox:focus {{
                border: {FIELD_BORDER}px solid {P.accent};
            }}
            QSpinBox:disabled, QDoubleSpinBox:disabled, QTimeEdit:disabled, QComboBox:disabled {{
                background: {P.inset}; color: {P.faint}; border-color: {P.border};
            }}

            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding; subcontrol-position: center right;
                width: {s(FIELD_COMBO_W)}px; background: {P.inset};
                border-left: {FIELD_BORDER}px solid {P.border};
                border-top-right-radius: {s(R_INPUT - 2)}px;
                border-bottom-right-radius: {s(R_INPUT - 2)}px;
            }}
            QComboBox QAbstractItemView {{
                background: {P.surface}; color: {P.ink};
                border: {FIELD_BORDER}px solid {P.border}; outline: none;
                selection-background-color: {P.accent_tint}; selection-color: {P.accent_deep};
            }}
        """
    @staticmethod
    def checkbox():
        return f"""
            QCheckBox {{
                color: {P.ink_soft}; font-size: {s(FONT_INPUT)}px;
                spacing: {s(6)}px; background: transparent;
            }}
            QCheckBox::indicator {{
                width: {s(15)}px; height: {s(15)}px;
                border-radius: {s(4)}px;
                border: 1px solid {P.border_mid}; background: {P.surface};
            }}
            QCheckBox::indicator:hover {{ border-color: {P.accent}; }}
            QCheckBox::indicator:checked {{ background: {P.accent}; border-color: {P.accent_deep}; }}
            QCheckBox:disabled {{ color: {P.faint}; }}
            QCheckBox::indicator:disabled {{ background: {P.inset}; border-color: {P.border}; }}
        """

    # ---------- кнопки ----------
    @staticmethod
    def btn_primary():
        return f"""
            QPushButton {{
                background: {P.ok_deep}; color: #ffffff; font-weight: bold;
                border: 1px solid {P.ok_edge}; border-radius: {s(R_BTN)}px;
                padding: {s(8)}px {s(14)}px; font-size: {s(FONT_BTN)}px;
            }}
            QPushButton:hover {{
                background: {P.ok}; color: {P.ok_ink}; border-color: {P.ok_deep};
            }}
            QPushButton:pressed {{
                background: {P.ok_press}; color: {P.ok_ink}; border-color: {P.ok_edge};
            }}
            QPushButton:disabled {{ background: {P.inset}; color: {P.faint}; border-color: {P.border}; }}
        """

    @staticmethod
    def btn_stop():
        return f"""
            QPushButton {{
                background: {P.surface}; color: {P.ink}; font-weight: bold;
                border: 1px solid {P.border_mid}; border-radius: {s(R_BTN)}px;
                padding: {s(8)}px {s(14)}px; font-size: {s(FONT_BTN)}px;
            }}
            QPushButton:hover {{
                background: {P.bad_hover}; color: #ffffff; border-color: {P.bad_deep};
            }}
            QPushButton:pressed {{
                background: {P.bad_deep}; color: #ffffff; border-color: {P.bad_deep};
            }}
            QPushButton:disabled {{ background: {P.inset}; color: {P.faint}; border-color: {P.border}; }}
        """

    @staticmethod
    def btn_action():
        return f"""
            QPushButton {{
                background: {P.surface}; color: {P.ink};
                border: 1px solid {P.border_mid}; border-radius: {s(R_BTN)}px;
                padding: {s(8)}px {s(14)}px; font-size: {s(FONT_BTN)}px;
            }}
            QPushButton:hover {{ background: {P.accent_tint}; border-color: {P.accent_edge}; color: {P.accent_deep}; }}
            QPushButton:pressed {{ background: #dbeafe; }}
            QPushButton:disabled {{ background: {P.inset}; color: {P.faint}; border-color: {P.border}; }}
        """

    @staticmethod
    def btn_main():
        return f"""
            QPushButton {{
                background: {P.surface}; color: {P.ink}; font-weight: bold;
                border: 1px solid {P.border}; border-radius: {s(R_BTN)}px;
                padding: {s(7)}px {s(14)}px; font-size: {s(FONT_BTN_MAIN)}px;
            }}
            QPushButton:hover {{ background: {P.accent_tint}; border-color: {P.accent_edge}; color: {P.accent_deep}; }}
            QPushButton:pressed {{ background: #dbeafe; }}
        """

    @staticmethod
    def icon_btn():
        return f"""
            QPushButton {{
                background: {P.surface}; border: 1px solid {P.border};
                border-radius: {s(R_BTN)}px; padding: 0px;
            }}
            QPushButton:hover {{ background: {P.accent_tint}; border-color: {P.accent_edge}; }}
            QPushButton:pressed {{ background: #dbeafe; }}
        """

    @staticmethod
    def ghost_btn():
        return f"""
            QPushButton {{
                background: transparent; border: 1px solid transparent;
                border-radius: {s(8)}px; color: {P.muted};
                font-size: {s(FONT_TEXT_COMPACT)}px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {P.accent_tint}; border-color: {P.accent_edge}; color: {P.accent_deep}; }}
        """

    @staticmethod
    def delete_btn():
        return f"""
            QPushButton {{
                background: transparent; border: 1px solid transparent;
                border-radius: {s(13)}px; color: {P.faint}; font-size: {s(FONT_BTN)}px;
            }}
            QPushButton:hover {{ background: {P.bad_tint}; border-color: {P.bad_edge}; color: {P.bad_deep}; }}
            QPushButton:pressed {{ background: #fbdcdc; }}
        """

    @staticmethod
    def clear_btn():
        return f"""
            QPushButton {{
                background: {P.surface}; color: {P.bad_deep};
                border: 1px solid {P.bad_edge}; border-radius: {s(R_BTN)}px;
                padding: {s(6)}px {s(12)}px; font-size: {s(FONT_BTN)}px;
            }}
            QPushButton:hover {{ background: {P.bad_tint}; }}
        """

    # ---------- индикаторы ----------
    @staticmethod
    def indicator(color_style, radius):
        return f"background-color: {color_style}; border-radius: {s(radius)}px; border: none;"

    @staticmethod
    def indicator_strip(color_style, top_radius):
        return f"""
            background-color: {color_style}; border: none;
            border-top-left-radius: {s(top_radius)}px; border-top-right-radius: {s(top_radius)}px;
            border-bottom-left-radius: 0px; border-bottom-right-radius: 0px;
        """

    @staticmethod
    def param_indicator(color):
        return f"background-color: {color}; border-radius: {s(3)}px; border: none;"

    # ---------- данные ----------
    @staticmethod
    def data_scroll():
        return f"""
            QScrollArea#dataScroll {{
                background: {P.surface}; border: 1px solid {P.border};
                border-radius: {s(R_BTN)}px;
            }}
        """

    @staticmethod
    def data_label():
        return f"""
            QLabel#dataLabel {{
                font-size: {s(FONT_TEXT)}px; color: {P.ink};
                padding: {s(8)}px; background: transparent; border: none;
            }}
        """

    # ---------- компактный режим ----------
    @staticmethod
    def compact_name():
        return f"""
            ClickableLabel {{
                font-size: {s(FONT_TEXT_COMPACT)}px; font-weight: bold; color: {P.ink};
                background-color: {P.surface}; border: 1px solid {P.border};
                border-radius: {s(R_BTN)}px; padding: {s(2)}px {s(6)}px;
            }}
            ClickableLabel:hover {{
                border: 1px solid {P.accent}; background: {P.accent_tint}; color: {P.accent_deep};
            }}
        """

    @staticmethod
    def compact_cell_bg():
        return f"""
            QFrame#compactCell {{
                background-color: {P.surface}; border: 1px solid {P.border};
                border-radius: {s(R_BTN)}px;
            }}
            QFrame#compactCell:hover {{
                border: 1px solid {P.accent}; background-color: {P.accent_tint};
            }}
        """

    @staticmethod
    def compact_cell_name():
        return f"font-size: {s(14)}px; color: {P.muted}; background: transparent; border: none;"

    @staticmethod
    def compact_cell_value():
        return f"font-size: {s(20)}px; color: {P.ink}; font-weight: bold; background: transparent; border: none;"

    # ---------- подсказки, панель перетаскивания ----------
    @staticmethod
    def hint():
        return f"color: {P.faint}; padding: {s(30)}px; font-size: {s(FONT_TITLE)}px; background: transparent; border: none;"

    @staticmethod
    def hint_compact():
        return f"color: {P.faint}; font-size: {s(FONT_XL)}px; padding: {s(4)}px; background: transparent; border: none;"

    @staticmethod
    def drag_panel():
        return f"#dragPanel {{ background: {P.surface}; border-bottom: 1px solid {P.border}; }}"

    @staticmethod
    def drag_grip():
        return f"color: {P.faint}; font-size: {s(FONT_L)}px; font-weight: bold; border: none; background: transparent;"

    @staticmethod
    def expand_btn():
        return f"""
            QPushButton {{
                border: 1px solid {P.border}; background: {P.surface};
                border-radius: {s(8)}px; font-size: {s(FONT_TITLE)}px;
                font-weight: bold; color: {P.ink_soft};
            }}
            QPushButton:hover {{ background: {P.accent_tint}; border-color: {P.accent_edge}; color: {P.accent_deep}; }}
        """

    # ---------- меню, таблица, диалоги ----------
    @staticmethod
    def menu():
        return f"""
            QMenu {{
                background-color: {P.surface}; color: {P.ink};
                border: 1px solid {P.border}; border-radius: {s(R_BTN)}px;
                padding: {s(5)}px; font-size: {s(FONT_MENU)}px;
            }}
            QMenu::item {{
                background-color: transparent;
                padding: {s(7)}px {s(26)}px {s(7)}px {s(12)}px;
                border-radius: {s(7)}px;
            }}
            QMenu::item:selected {{ background-color: {P.accent_tint}; color: {P.accent_deep}; }}
            QMenu::separator {{ height: 1px; background-color: {P.border}; margin: {s(4)}px {s(8)}px; }}
        """

    @staticmethod
    def table():
        return f"""
            QTableWidget {{
                background: {P.surface}; alternate-background-color: #f6f9fc; color: {P.ink};
                gridline-color: {P.border}; border: 1px solid {P.border};
                border-radius: {s(R_BTN)}px; font-size: {s(FONT_TABLE)}px;
                selection-background-color: {P.accent_tint}; selection-color: {P.ink};
            }}
            QHeaderView::section {{
                background: {P.inset}; color: {P.ink_soft}; border: none;
                border-bottom: 1px solid {P.border}; padding: {s(6)}px;
                font-size: {s(FONT_TABLE)}px; font-weight: bold;
            }}
            QTableCornerButton::section {{ background: {P.inset}; border: none; }}
        """

    @staticmethod
    def dialog_style():
        return f"""
            QDialog {{ background-color: {P.bg}; }}
            QLabel {{ color: {P.ink}; background: transparent; }}
            QCheckBox {{ color: {P.ink_soft}; font-size: {s(FONT_INPUT)}px; spacing: {s(6)}px; background: transparent; }}
            QCheckBox::indicator {{
                width: {s(15)}px; height: {s(15)}px; border-radius: {s(4)}px;
                border: 1px solid {P.border_mid}; background: {P.surface};
            }}
            QCheckBox::indicator:checked {{ background: {P.accent}; border-color: {P.accent_deep}; }}
            QLineEdit {{
                color: {P.ink}; background-color: {P.surface};
                border: 1px solid {P.border_mid}; border-radius: {s(R_INPUT)}px;
                padding: {s(6)}px; font-size: {s(FONT_INPUT)}px;
                selection-background-color: {P.accent}; selection-color: #ffffff;
            }}
            QLineEdit:focus {{ border: 1px solid {P.accent}; }}
            QScrollArea {{ background-color: {P.surface}; border: 1px solid {P.border}; border-radius: {s(R_BTN)}px; }}
            QScrollArea > QWidget > QWidget {{ background-color: {P.surface}; }}
        """ + Styles.app_shell()


# ---------------------------------------------------------------------------
# КАСТОМНЫЕ ТУЛТИПЫ
# ---------------------------------------------------------------------------
class CustomToolTipManager(QObject):
    def __init__(self):
        super().__init__()
        self.label = None

    def _tooltip_qss(self):
        return f"""
            QLabel {{
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #999999;
                border-radius: {s(6)}px;
                padding: {s(6)}px {s(10)}px;
                font-size: {s(FONT_TEXT)}px;
            }}
        """

    def _ensure_label(self):
        if self.label is None:
            self.label = QLabel()
            self.label.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self.label.setAttribute(Qt.WA_TransparentForMouseEvents)
            self.label.setStyleSheet(self._tooltip_qss())
            self.label.hide()

    def show_text(self, text, target_pos):
        self._ensure_label()
        if not text: return
        self.label.setText(text)
        self.label.adjustSize()
        
        x, y = target_pos.x(), target_pos.y()
        screen = QApplication.screenAt(target_pos) or QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            if x + self.label.width() > geo.right(): x = geo.right() - self.label.width()
            if y + self.label.height() > geo.bottom(): y = geo.bottom() - self.label.height()
            if x < geo.left(): x = geo.left()
            if y < geo.top(): y = geo.top()
            
        self.label.move(x, y)
        self.label.show()

    def hide_tooltip(self):
        if self.label is not None:
            self.label.hide()

tooltip_manager = CustomToolTipManager()

class ToolTipFilter(QObject):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.text = text

    def setText(self, text):
        self.text = text

    def eventFilter(self, obj, event):
        if event.type() == QEvent.ToolTip:
            tooltip_manager._ensure_label()
            tooltip_manager.label.setText(self.text)
            tooltip_manager.label.adjustSize()
            
            center_x = obj.mapToGlobal(QPoint(obj.width() // 2, 0)).x()
            y = obj.mapToGlobal(QPoint(0, obj.height())).y() + s(5)
            
            screen = QApplication.screenAt(QPoint(center_x, y)) or QApplication.primaryScreen()
            if screen and y + tooltip_manager.label.height() > screen.availableGeometry().bottom():
                y = obj.mapToGlobal(QPoint(0, 0)).y() - tooltip_manager.label.height() - s(5)
                
            tooltip_manager.show_text(self.text, QPoint(center_x - tooltip_manager.label.width() // 2, y))
            return True
        elif event.type() in (QEvent.Leave, QEvent.MouseButtonPress):
            tooltip_manager.hide_tooltip()
        return False

def set_custom_tooltip(widget, text):
    filter_obj = ToolTipFilter(text, widget)
    widget.installEventFilter(filter_obj)
    widget._custom_tooltip_filter = filter_obj

# ---------------------------------------------------------------------------
# ФОНОВЫЕ ПОТОКИ
# ---------------------------------------------------------------------------
class WorkerSignals(QObject):
    finished = pyqtSignal(list, bool, datetime, object, dict)  # добавлен dict для кэша
    error = pyqtSignal(str, datetime)
    data_parsed = pyqtSignal(dict, str, object)

class ScanWorker(QRunnable):
    def __init__(self, folder_path, last_check_time, initial, file_cache=None):
        super().__init__()
        self.folder_path = folder_path
        self.last_check_time = last_check_time
        self.initial = initial
        self.file_cache = file_cache or {}  # {filename: mtime}
        self.signals = WorkerSignals()

    def run(self):
        start_time = datetime.now()
        found, max_file_time = [], None
        current_cache = {}
        
        try:
            with os.scandir(self.folder_path) as it:
                for entry in it:
                    try:
                        # Фильтр только .txt файлов на раннем этапе
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        if not entry.name.endswith('.txt'):
                            continue
                        
                        # Используем stat без follow_symlinks для скорости
                        st = entry.stat(follow_symlinks=False)
                        mtime = st.st_mtime
                        # Сохраняем в текущий кэш
                        current_cache[entry.name] = mtime
                        # Находим максимальное время (как datetime, чтобы не ломать strftime)
                        file_dt = datetime.fromtimestamp(mtime)
                        if max_file_time is None or file_dt > max_file_time:
                            max_file_time = file_dt
                        
                        # Инкрементальная проверка: только новые или измененные файлы
                        if self.initial:
                            # При первом запуске — все файлы
                            found.append((entry.name, datetime.fromtimestamp(mtime)))
                        else:
                            # Проверяем только если файл новый или изменился
                            old_mtime = self.file_cache.get(entry.name)
                            if old_mtime is None or mtime > old_mtime:
                                # Файл новый или обновился после последней проверки
                                if mtime > self.last_check_time.timestamp():
                                    found.append((entry.name, datetime.fromtimestamp(mtime)))
                    except OSError:
                        continue
        except Exception as e:
            self.signals.error.emit(str(e), start_time)
            return
        
        # Возвращаем найденные файлы и обновленный кэш
        self.signals.finished.emit(found, self.initial, start_time, max_file_time, current_cache)
        
        
class FileParseWorker(QRunnable):
    TAIL_BYTES = 65536
    def __init__(self, folder_path, selected_columns, file_cache=None):
        super().__init__()
        self.folder_path = folder_path
        self.selected_columns = selected_columns
        self.file_cache = file_cache or {}
        self.signals = WorkerSignals()

    def run(self):
        try:
            latest_path, latest_mtime = None, -1.0
            
            # Используем кэш если доступен
            if self.file_cache:
                for name, mtime in self.file_cache.items():
                    if name.endswith('.txt') and mtime > latest_mtime:
                        latest_mtime = mtime
                        latest_path = os.path.join(self.folder_path, name)
            else:
                # Fallback: полное сканирование
                with os.scandir(self.folder_path) as it:
                    for entry in it:
                        if entry.is_file(follow_symlinks=False) and entry.name.endswith('.txt'):
                            m = entry.stat(follow_symlinks=False).st_mtime
                            if m > latest_mtime:
                                latest_mtime, latest_path = m, entry.path

            if not latest_path:
                self.signals.data_parsed.emit({}, "Файл не найден", None)
                return

            with open(latest_path, 'rb') as f:
                header_line = f.readline()
                if not header_line:
                    self.signals.data_parsed.emit({}, "Файл пуст", None)
                    return
                headers = header_line.decode('utf-8', errors='ignore').rstrip('\n').split('\t')
                idx_date, idx_time = headers.index('date') if 'date' in headers else 0, headers.index('time') if 'time' in headers else 1
                
                col_indices = {col: headers.index(col) for col in self.selected_columns if col in headers}
                max_needed = max([idx_date, idx_time] + list(col_indices.values())) if col_indices else max(idx_date, idx_time)

                f.seek(0, os.SEEK_END)
                size = f.tell()
                if size <= len(header_line):
                    self.signals.data_parsed.emit({}, "Файл повреждён", None)
                    return

                read_size, latest_data = min(self.TAIL_BYTES, size), None
                while True:
                    f.seek(size - read_size)
                    chunk = f.read(read_size)
                    for raw in reversed(chunk.split(b'\n')):
                        if not raw.startswith(b'DATA\t'): continue
                        parts = raw.decode('utf-8', errors='ignore').split('\t')
                        if len(parts) <= max_needed: continue
                        try:
                            datetime.strptime(f"{parts[idx_date]} {parts[idx_time]}", "%Y-%m-%d %H:%M:%S")
                            latest_data = parts
                            break
                        except Exception: continue
                    
                    if latest_data is not None or read_size >= size: break
                    read_size = min(read_size * 4, size)

                if not latest_data:
                    self.signals.data_parsed.emit({}, "Нет валидных DATA-строк", None)
                    return

                result = {}
                for col_name, idx in col_indices.items():
                    if idx < len(latest_data):
                        val = latest_data[idx].strip()
                        try:
                            f_val = float(val)
                            if col_name in TEMP_COLUMNS: f_val -= 273.15
                            val = str(int(f_val)) if f_val.is_integer() else f"{f_val:.2f}"
                        except Exception: pass
                        result[col_name] = val

                self.signals.data_parsed.emit(result, "", os.path.getmtime(latest_path))
        except OSError as e:
            self.signals.data_parsed.emit({}, str(e), None)

# ---------------------------------------------------------------------------
# ДИАЛОГ ВЫБОРА СТОЛБЦОВ
# ---------------------------------------------------------------------------
class ColumnSelectDialog(QDialog):
    def __init__(self, all_columns, selected_columns, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выбор столбцов")
        self.resize(s(400), s(600))
        self.setStyleSheet(Styles.dialog_style())
        
        layout = QVBoxLayout(self)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск столбца...")
        layout.addWidget(self.search_edit)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content, vbox = QWidget(), QVBoxLayout()
        scroll.setWidget(content)
        
        self.checkboxes = {}
        for col in all_columns:
            cb = QCheckBox(col)
            cb.setChecked(col in selected_columns)
            self.checkboxes[col] = cb
            vbox.addWidget(cb)
            self.search_edit.textChanged.connect(lambda text, c=cb, n=col: c.setVisible(text.lower() in n.lower()))
            
        content.setLayout(vbox)
        layout.addWidget(scroll)

        btn_save = QPushButton("Сохранить")
        btn_save.setStyleSheet(Styles.btn_main())
        btn_save.clicked.connect(self.accept)
        layout.addWidget(btn_save)

    def get_selected(self):
        return [col for col, cb in self.checkboxes.items() if cb.isChecked()]

# ---------------------------------------------------------------------------
# КОМПОНЕНТЫ
# ---------------------------------------------------------------------------
class ClickableLabel(QLabel):
    clicked = pyqtSignal()
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
        else: super().mousePressEvent(event)

class ClickableFrame(QFrame):
    clicked = pyqtSignal(str)
    def __init__(self, col_key, parent=None):
        super().__init__(parent)
        self.col_key = col_key
        self.setCursor(Qt.PointingHandCursor)
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.col_key)
            event.accept()
        else: super().mousePressEvent(event)

class ResizeGrip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(s(20), s(20))
        self.setCursor(Qt.SizeFDiagCursor)
        self._drag_pos = None
        self._resize_start_size = None
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(150, 150, 150), max(1.0, s(2))))
        for i in range(3):
            offset = s(i * 6 + 4)
            painter.drawLine(s(20) - offset, s(18), s(18), s(20) - offset)
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos()
            self._resize_start_size = self.window().size()
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_pos is not None:
            delta = event.globalPos() - self._drag_pos
            self.window().resize(self._resize_start_size + QSize(delta.x(), delta.y()))
    def mouseReleaseEvent(self, event): self._drag_pos = None

class DragPanel(QFrame):
    expand_clicked = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(s(40))
        self.setObjectName("dragPanel")
        self.setStyleSheet(Styles.drag_panel())
        self._drag_pos = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(s(12), s(4), s(12), s(4))
        
        grip = QLabel("≡")
        grip.setStyleSheet(Styles.drag_grip())
        layout.addWidget(grip, 0, Qt.AlignLeft | Qt.AlignVCenter)
        layout.addStretch()
        
        self.expand_btn = QPushButton("⤢")
        self.expand_btn.setFixedSize(s(36), s(28))
        self.expand_btn.setStyleSheet(Styles.expand_btn())
        self.expand_btn.clicked.connect(self.expand_clicked.emit)
        layout.addWidget(self.expand_btn, 0, Qt.AlignRight | Qt.AlignVCenter)
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.window().frameGeometry().topLeft()
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_pos is not None:
            self.window().move(event.globalPos() - self._drag_pos)
    def mouseReleaseEvent(self, event): self._drag_pos = None

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, h_spacing=-1, v_spacing=-1):
        super().__init__(parent)
        self.itemList = []
        self.setContentsMargins(margin, margin, margin, margin)
        self._h_spacing, self._v_spacing = h_spacing, v_spacing
    def __del__(self):
        item = self.takeAt(0)
        while item: item = self.takeAt(0)
    def addItem(self, item): self.itemList.append(item)
    def count(self): return len(self.itemList)
    def itemAt(self, index): return self.itemList[index] if 0 <= index < len(self.itemList) else None
    def takeAt(self, index): return self.itemList.pop(index) if 0 <= index < len(self.itemList) else None
    def removeWidget(self, widget):
        for i in range(self.count()):
            if self.itemAt(i).widget() == widget:
                self.takeAt(i)
                return
    def expandingDirections(self): return Qt.Orientations(Qt.Orientation(0))
    def hasHeightForWidth(self): return True
    def heightForWidth(self, width):
        m = self.contentsMargins()
        return self.doLayout(QRect(0, 0, width - m.left() - m.right(), 0), True) + m.top() + m.bottom()
    def setGeometry(self, rect):
        super().setGeometry(rect)
        m = self.contentsMargins()
        self.doLayout(rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom()), False)
    def sizeHint(self): return self.minimumSize()
    def minimumSize(self):
        size = QSize()
        for item in self.itemList: size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())
    def horizontalSpacing(self): return self._h_spacing if self._h_spacing >= 0 else self.spacing()
    def verticalSpacing(self): return self._v_spacing if self._v_spacing >= 0 else self.spacing()
    def doLayout(self, rect, testOnly):
        x, y, lineHeight = rect.x(), rect.y(), 0
        spaceX, spaceY = self.horizontalSpacing(), self.verticalSpacing()
        for item in self.itemList:
            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x, y, nextX, lineHeight = rect.x(), y + lineHeight + spaceY, rect.x() + item.sizeHint().width() + spaceX, 0
            if not testOnly: item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x, lineHeight = nextX, max(lineHeight, item.sizeHint().height())
        return y + lineHeight - rect.y()

# ---------------------------------------------------------------------------
# БЛОК НАБЛЮДЕНИЯ
# ---------------------------------------------------------------------------
class BlockWidget(QFrame):
    status_changed = pyqtSignal(str, str, str)
    delete_requested = pyqtSignal(object)

    def __init__(self, folder_path, parent=None):
        super().__init__(parent)
        self.folder_path = folder_path
        self.custom_name = os.path.basename(self.folder_path.rstrip(os.sep)) or self.folder_path
        self.last_check_time, self.last_file_time, self._watch_start = datetime.now(), None, None
        self.next_check_time = None
        self._running, self._start_time_qtime, self._compact, self._is_scanning = False, None, False, False
        self.selected_columns, self.parsed_data, self.parse_error = [], {}, ""
        self.is_parsing, self._detail_expanded, self._last_parsed_mtime = False, False, None
        self._file_cache = {}  # {filename: mtime} для инкрементального сканирования
        
        self.widget_columns = list(WIDGET_MAIN_COLUMNS)
        self._compact_collapsed = False

        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("block")
        self.setStyleSheet(Styles.block_detail())

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer)
        self.blink_timer = QTimer(self)
        self.blink_timer.setInterval(500)
        self.blink_timer.timeout.connect(self._toggle_blink)
        
        self.ui_timer = QTimer(self)
        self.ui_timer.setInterval(TIMER_INTERNAL) # 1 час
        self.ui_timer.timeout.connect(self._update_check_times)
        self.ui_timer.start()

        self._blink_state, self._base_color_hex = False, "#999999"
        self._drag_start_pos=None

        self._build_ui()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if CARD_SHADOW:
            self._card_shadow = QGraphicsDropShadowEffect(self)
            self._card_shadow.setBlurRadius(s(18))
            self._card_shadow.setColor(QColor(15, 23, 42, 26))
            self._card_shadow.setOffset(0, s(2))
            self.setGraphicsEffect(self._card_shadow)
        self._set_circle("gray")
        self._update_data_label()
        self._update_check_times()
        self.setAcceptDrops(False)
        for child in self.findChildren(QWidget): child.setAcceptDrops(False)

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._stack = QStackedWidget(self)
        outer.addWidget(self._stack)
        
        self.detail_page = QWidget()
        self._build_detail_ui(self.detail_page)
        self._stack.addWidget(self.detail_page)
        
        self.compact_page = QWidget()
        self._build_compact_ui(self.compact_page)
        self._stack.addWidget(self.compact_page)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_start_pos is not None:
            if (event.pos() - self._drag_start_pos).manhattanLength() > QApplication.startDragDistance():
                self._start_drag()
        super().mouseMoveEvent(event)

    def _start_drag(self):
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setData("application/x-blockwidget", b"")
        drag.setMimeData(mime_data)
        
        pixmap = self.grab()
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        painter.fillRect(pixmap.rect(), QColor(0, 0, 0, 150))
        painter.end()
        
        drag.setPixmap(pixmap)
        drag.setHotSpot(self._drag_start_pos)
        
        if hasattr(self.window(), 'blocks_container'):
            self.window().blocks_container.dragged_block = self
            drag.exec_(Qt.MoveAction)
            self.window().blocks_container.dragged_block = None

    def _build_detail_ui(self, parent):
        outer = QVBoxLayout(parent)
        outer.setContentsMargins(s(14), s(12), s(14), s(12))
        outer.setSpacing(s(10))

        # --- Шапка блока (фиксированная, не зависит от раскрытия данных) ---
        header_container = QWidget()
        header_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        header_container.setStyleSheet("background: transparent; border: none;")
        header_layout = QVBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(s(6))
    
        head = QHBoxLayout()
        head.setSpacing(s(8))
        self.circle = QLabel()
        self.circle.setFixedSize(s(14), s(14))
        set_custom_tooltip(self.circle, "Серый — остановлен\nЗелёный — файлы в норме\nКрасный — нет новых файлов")
        self.circle_glow = QGraphicsDropShadowEffect(self)
        self.circle_glow.setBlurRadius(s(16))
        self.circle_glow.setOffset(0, 0)
        self.circle.setGraphicsEffect(self.circle_glow)
        head.addWidget(self.circle, 0, Qt.AlignVCenter)
        self.name_edit = QLineEdit(self.custom_name)
        self.name_edit.setStyleSheet(Styles.name_edit())
        self.name_edit.textChanged.connect(self._on_name_changed)
        head.addWidget(self.name_edit, 1)
        self.delete_btn = QPushButton("✕")
        self.delete_btn.setFixedSize(s(32), s(32))
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        set_custom_tooltip(self.delete_btn, "Удалить блок")
        self.delete_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: 1px solid transparent;
                border-radius: {s(8)}px; color: #999; font-size: {s(18)}px; font-weight: bold;
            }}
            QPushButton:hover {{
                background: #fdeaea; border-color: #f6c9c9; color: #b91c1c;
            }}
            QPushButton:pressed {{ background: #fbdcdc; }}
        """)
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self))
        head.addWidget(self.delete_btn, 0, Qt.AlignVCenter)
        header_layout.addLayout(head)
    
        path_row = QHBoxLayout()
        path_row.setSpacing(s(6))
        self.open_btn = QPushButton()
        self.open_btn.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.open_btn.setIconSize(QSize(s(16), s(16)))
        self.open_btn.setFixedSize(s(32), s(32))
        self.open_btn.setCursor(Qt.PointingHandCursor)
        set_custom_tooltip(self.open_btn, "Открыть папку")
        self.open_btn.clicked.connect(self._open_folder)
        path_row.addWidget(self.open_btn, 0, Qt.AlignTop)
        self.path_label = QLabel(self.folder_path)
        self.path_label.setStyleSheet(Styles.path_label())
        self.path_label.setWordWrap(True)
        self.path_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        path_row.addWidget(self.path_label, 1)
        header_layout.addLayout(path_row)
    
        line = QFrame()
        line.setFixedHeight(max(1, s(1)))
        line.setStyleSheet(Styles.separator())
        header_layout.addWidget(line)
    
        outer.addWidget(header_container)

        card = QFrame()
        card.setObjectName("settingsCard")
        card.setStyleSheet(Styles.settings_card())
        settings_layout = QVBoxLayout(card)
        settings_layout.setContentsMargins(s(10), s(9), s(10), s(9))
        settings_layout.setSpacing(s(7))

        row_period = QHBoxLayout()
        row_period.setSpacing(s(6))
        lbl_p = QLabel("Период, мин:")
        lbl_p.setStyleSheet(Styles.label_input())
        row_period.addWidget(lbl_p)
        self.period_spin = QSpinBox()
        self.period_spin.setStyleSheet(Styles.input_field())
        self.period_spin.setRange(1, 24 * 60)
        self.period_spin.setValue(5)
        self.period_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.period_spin.setFixedWidth(field_width("8888", buttons=False))
        set_custom_tooltip(self.period_spin, "Интервал проверки папки")
        self.period_spin.valueChanged.connect(self._update_alert_info)
        row_period.addWidget(self.period_spin)
        row_period.addStretch()
        settings_layout.addLayout(row_period)

        lbl_alert_caption = QLabel("Параметры тревоги")
        lbl_alert_caption.setStyleSheet(Styles.section_caption())
        settings_layout.addWidget(lbl_alert_caption)

        alert_rule = QFrame()
        alert_rule.setFixedHeight(max(1, s(1)))
        alert_rule.setStyleSheet(Styles.section_rule())
        settings_layout.addWidget(alert_rule)

        row_alert = QHBoxLayout()
        row_alert.setSpacing(s(6))
        self.use_period_alert_cb = QCheckBox()
        self.use_period_alert_cb.setStyleSheet(Styles.checkbox())
        self.use_period_alert_cb.setCursor(Qt.PointingHandCursor)
        self.use_period_alert_cb.setFixedWidth(s(20))
        set_custom_tooltip(self.use_period_alert_cb, "Включить множитель периода\nТревога = период × множитель")
        self.use_period_alert_cb.toggled.connect(self._on_multiplier_toggled)
        row_alert.addWidget(self.use_period_alert_cb, 0, Qt.AlignVCenter)
        self.lbl_mult = ClickableLabel("Множ:")
        self.lbl_mult.setStyleSheet(Styles.label_input())
        self.lbl_mult.setCursor(Qt.PointingHandCursor)
        self.lbl_mult.setEnabled(False)
        self.lbl_mult.clicked.connect(self.use_period_alert_cb.toggle)
        row_alert.addWidget(self.lbl_mult)
        self.multiplier_spin = QDoubleSpinBox()
        self.multiplier_spin.setStyleSheet(Styles.input_field())
        self.multiplier_spin.setRange(1.1, 10.0)
        self.multiplier_spin.setSingleStep(0.1)
        self.multiplier_spin.setValue(1.5)
        self.multiplier_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.multiplier_spin.setFixedWidth(field_width("88,88", buttons=False))
        self.multiplier_spin.setEnabled(False)
        set_custom_tooltip(self.multiplier_spin, "Множитель периода тревоги")
        self.multiplier_spin.valueChanged.connect(self._update_alert_info)
        row_alert.addWidget(self.multiplier_spin)
        row_alert.addSpacing(s(14))
        lbl_cap = QLabel("Старт (> мин):")
        lbl_cap.setStyleSheet(Styles.label_input())
        row_alert.addWidget(lbl_cap)
        self.start_timeout_spin = QSpinBox()
        self.start_timeout_spin.setStyleSheet(Styles.input_field())
        self.start_timeout_spin.setRange(1, 24 * 60)
        self.start_timeout_spin.setValue(30)
        self.start_timeout_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.start_timeout_spin.setFixedWidth(field_width("8888", buttons=False))
        set_custom_tooltip(self.start_timeout_spin, "Тревога, если новых файлов нет дольше этого времени")
        self.start_timeout_spin.valueChanged.connect(self._update_alert_info)
        row_alert.addWidget(self.start_timeout_spin)
        row_alert.addStretch()
        settings_layout.addLayout(row_alert)

        row_time = QHBoxLayout()
        row_time.setSpacing(s(6))
        self.use_exact_start_cb = QCheckBox("Точное время:")
        self.use_exact_start_cb.setStyleSheet(Styles.checkbox())
        self.use_exact_start_cb.setCursor(Qt.PointingHandCursor)
        self.use_exact_start_cb.toggled.connect(self._on_exact_start_toggled)
        row_time.addWidget(self.use_exact_start_cb)
        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setStyleSheet(Styles.input_field())
        self.start_time_edit.setDisplayFormat("HH:mm")
        now_t = QTime.currentTime()
        self.start_time_edit.setTime(QTime(now_t.hour(), now_t.minute(), 0))
        self.start_time_edit.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.start_time_edit.setFixedWidth(field_width("88:88", buttons=False))
        self.start_time_edit.setEnabled(False)
        row_time.addWidget(self.start_time_edit)
        row_time.addStretch()
        settings_layout.addLayout(row_time)

        row_mode = QHBoxLayout()
        row_mode.setSpacing(s(6))
        lbl_m = QLabel("Режим:")
        lbl_m.setStyleSheet(Styles.label_input())
        row_mode.addWidget(lbl_m)
        self.indicator_mode_combo = QComboBox()
        self.indicator_mode_combo.setStyleSheet(Styles.input_field())
        self.indicator_mode_combo.setCursor(Qt.PointingHandCursor)
        self.indicator_mode_combo.addItems(["Статика", "Мигание"])
        self.indicator_mode_combo.setMinimumWidth(field_width("Мигание", btn_ref=FIELD_COMBO_W))
        self.indicator_mode_combo.currentTextChanged.connect(self._on_indicator_mode_changed)
        row_mode.addWidget(self.indicator_mode_combo)
        row_mode.addStretch()
        settings_layout.addLayout(row_mode)
        outer.addWidget(card)

        btn_status_row = QHBoxLayout()
        btn_status_row.setSpacing(s(8))
        self.start_btn = QPushButton("Запуск")
        self.start_btn.setStyleSheet(Styles.btn_primary())
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.start_btn.clicked.connect(self.start)
        self.stop_btn = QPushButton("Стоп")
        self.stop_btn.setStyleSheet(Styles.btn_stop())
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        btn_status_row.addWidget(self.start_btn, 2)
        btn_status_row.addWidget(self.stop_btn, 1)
        outer.addLayout(btn_status_row)

        info_card = QFrame()
        info_card.setObjectName("infoCard")
        info_card.setStyleSheet(Styles.info_card())
        info_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        info = QVBoxLayout(info_card)
        info.setContentsMargins(s(10), s(9), s(10), s(9))
        info.setSpacing(s(10))
        self.last_file_label = QLabel("Последний файл: —")
        self.last_file_label.setStyleSheet(Styles.info_text())
        self.last_file_label.setWordWrap(True)
        self.last_file_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        info.addWidget(self.last_file_label)
        self.check_time_label = QLabel("Проверка: —")
        self.check_time_label.setWordWrap(True)
        self.check_time_label.setStyleSheet(Styles.info_text())
        self.check_time_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        info.addWidget(self.check_time_label)
        self.no_file_label = QLabel("Нет: —")
        self.no_file_label.setWordWrap(True)
        self.no_file_label.setStyleSheet(Styles.info_text())
        self.no_file_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        info.addWidget(self.no_file_label)
        self.alert_info = QLabel()
        self.alert_info.setStyleSheet(Styles.alert_text())
        self.alert_info.setWordWrap(True)
        self.alert_info.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        info.addWidget(self.alert_info)
        info.addStretch(1)
        outer.addWidget(info_card)
        self._update_alert_info()

        self.detail_toggle_btn = QPushButton("▼ Показать данные")
        self.detail_toggle_btn.setStyleSheet(Styles.btn_action())
        self.detail_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.detail_toggle_btn.clicked.connect(self._toggle_detail_data)
        outer.addWidget(self.detail_toggle_btn)

        self.detail_data_widget = QWidget()
        self.detail_data_widget.setVisible(False)
        dd_layout = QVBoxLayout(self.detail_data_widget)
        dd_layout.setContentsMargins(0, s(2), 0, 0)
        dd_layout.setSpacing(s(8))
        self.btn_select_cols = QPushButton("Выбрать столбцы")
        self.btn_select_cols.setStyleSheet(Styles.btn_action())
        self.btn_select_cols.setCursor(Qt.PointingHandCursor)
        self.btn_select_cols.clicked.connect(self._open_column_selector)
        dd_layout.addWidget(self.btn_select_cols)
        self.detail_scroll = QScrollArea()
        self.detail_scroll.setObjectName("dataScroll")
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setFrameShape(QFrame.NoFrame)
        self.detail_scroll.setStyleSheet(Styles.data_scroll())
        self.detail_data_label = QLabel("Нет данных")
        self.detail_data_label.setObjectName("dataLabel")
        self.detail_data_label.setWordWrap(True)
        self.detail_data_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.detail_data_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        self.detail_data_label.setStyleSheet(Styles.data_label())
        self.detail_scroll.setWidget(self.detail_data_label)
        _f = QFont()
        _f.setPixelSize(max(1, s(FONT_TEXT)))
        fm = QFontMetrics(_f)
        self.detail_scroll.setFixedHeight(fm.lineSpacing() * 20 + s(16))
        dd_layout.addWidget(self.detail_scroll)
        outer.addWidget(self.detail_data_widget)


    def _build_compact_ui(self, parent):
        self.compact_layout = QVBoxLayout(parent)
        self.compact_layout.setContentsMargins(0, 0, 0, 0)
        self.compact_layout.setSpacing(0)

        self.compact_indicator = QFrame()
        self.compact_indicator.setFixedHeight(s(18))
        self.compact_indicator.setStyleSheet(Styles.indicator_strip(P.idle, R_CARD - 1))
        self.indicator_glow = QGraphicsDropShadowEffect(self)
        self.indicator_glow.setBlurRadius(s(14))
        self.indicator_glow.setOffset(0, 0)
        self.compact_indicator.setGraphicsEffect(self.indicator_glow)
        self.compact_layout.addWidget(self.compact_indicator, 0)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(s(10), s(10), s(10), s(10))
        content_layout.setSpacing(s(8))

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(s(6))
        self.compact_name = ClickableLabel(self.custom_name)
        self.compact_name.setAlignment(Qt.AlignCenter)
        self.compact_name.setWordWrap(True)
        self.compact_name.setFixedHeight(s(34))
        self.compact_name.setStyleSheet(Styles.compact_name())
        self.compact_name.setCursor(Qt.PointingHandCursor)
        set_custom_tooltip(self.compact_name, self.folder_path)
        self.compact_name.clicked.connect(self._open_folder)
        header_layout.addWidget(self.compact_name, 1)
        self.collapse_btn = QPushButton("▲")
        self.collapse_btn.setFixedSize(s(26), s(26))
        self.collapse_btn.setCursor(Qt.PointingHandCursor)
        self.collapse_btn.setStyleSheet(Styles.ghost_btn())
        self.collapse_btn.clicked.connect(self._toggle_compact_collapse)
        header_layout.addWidget(self.collapse_btn, 0, Qt.AlignVCenter)
        content_layout.addLayout(header_layout)

        self.compact_check_time_label = QLabel("Проверка: —")
        self.compact_check_time_label.setAlignment(Qt.AlignCenter)
        self.compact_check_time_label.setWordWrap(True)
        self.compact_check_time_label.setFixedHeight(s(40))
        self.compact_check_time_label.setStyleSheet(f"""
            QLabel {{
                color: {P.ink_soft}; font-size: {s(14)}px;
                background: transparent; border: none;
            }}
        """)
        content_layout.addWidget(self.compact_check_time_label)

        self.compact_grid_container = QWidget()
        self.compact_grid_layout = QGridLayout(self.compact_grid_container)
        self.compact_grid_layout.setHorizontalSpacing(s(8))
        self.compact_grid_layout.setVerticalSpacing(s(8))
        self.compact_grid_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.compact_grid_container, 1)
        self.compact_layout.addWidget(content, 1)
        self._rebuild_compact_grid()

    def _toggle_compact_collapse(self):
        self._compact_collapsed = not self._compact_collapsed
        self.compact_grid_container.setVisible(not self._compact_collapsed)
        self.collapse_btn.setText("▼" if self._compact_collapsed else "▲")
        self._update_block_height()

    def _rebuild_compact_grid(self):
        for i in reversed(range(self.compact_grid_layout.count())):
            w = self.compact_grid_layout.itemAt(i).widget()
            if w is not None:
                w.setParent(None)
        self.compact_value_labels, self.compact_indicators = {}, {}
        for i, (col_key, display_name) in enumerate(self.widget_columns):
            cell = ClickableFrame(col_key)
            cell.setObjectName("compactCell")
            cell.setStyleSheet(Styles.compact_cell_bg())
            cell.setFixedHeight(s(60))
            cell.clicked.connect(self._copy_param_value)
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(s(8), s(6), s(8), s(6))
            cell_layout.setSpacing(s(2))
            top_row = QHBoxLayout()
            top_row.setSpacing(s(4))
            name_lbl = QLabel(display_name.strip())
            name_lbl.setStyleSheet(Styles.compact_cell_name())
            set_custom_tooltip(name_lbl, col_key)
            top_row.addWidget(name_lbl, 1)
            ind_lbl = QFrame()
            ind_lbl.setFixedSize(s(5), s(16))
            ind_lbl.setStyleSheet(Styles.param_indicator("transparent"))
            top_row.addWidget(ind_lbl, 0, Qt.AlignRight | Qt.AlignVCenter)
            cell_layout.addLayout(top_row)
            val_lbl = QLabel("—")
            val_lbl.setAlignment(Qt.AlignCenter)
            val_lbl.setStyleSheet(Styles.compact_cell_value())
            cell_layout.addWidget(val_lbl)
            self.compact_grid_layout.addWidget(cell, i // 2, i % 2)
            self.compact_value_labels[col_key] = val_lbl
            self.compact_indicators[col_key] = ind_lbl
        self._update_data_label()
        self._update_block_height()

    def _update_block_height(self):
        rows = (len(self.widget_columns) + 1) // 2
        strip, pad, header, gap, check = s(18), s(10) * 2, s(34), s(8), s(40)
        cell, vspace = s(60), s(8)
        if getattr(self, '_compact_collapsed', False):
            new_height = strip + pad + header + gap + check
        else:
            grid = rows * cell + max(0, rows - 1) * vspace
            new_height = strip + pad + header + gap + check + gap + grid
        if self._compact:
            self.setFixedSize(s(WIDGET_BLOCK_WIDTH), max(s(120), new_height))

    def _add_widget_parameter(self):
        current_keys = [c[0] for c in self.widget_columns]
        dlg = ColumnSelectDialog(ALL_COLUMNS, current_keys, self)
        dlg.setWindowTitle("Настройка параметров виджета")
        
        if dlg.exec_():
            selected_keys = dlg.get_selected()
            default_display_names = dict(WIDGET_MAIN_COLUMNS)
            self.widget_columns = [(k, default_display_names.get(k, k)) for k in selected_keys]
            self._rebuild_compact_grid()
            self._last_parsed_mtime = None 
            self.fetch_file_data(force=True)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(Styles.menu())
        add_action = menu.addAction("Настроить параметры виджета")
        add_action.triggered.connect(self._add_widget_parameter)
        menu.exec_(event.globalPos())

    def _toggle_detail_data(self):
        self._detail_expanded = not self._detail_expanded
        self.detail_data_widget.setVisible(self._detail_expanded)
        self.detail_toggle_btn.setText("▲ Скрыть данные" if self._detail_expanded else "▼ Показать данные")
        self.detail_data_widget.layout().invalidate()
        self.updateGeometry()
        p = self.parentWidget()
        while p is not None:
            if p.layout() is not None:
                p.layout().invalidate()
            p.updateGeometry()
            p = p.parentWidget()
        if self._detail_expanded and not self.parsed_data and not self.is_parsing:
            self.fetch_file_data()

    def _get_fetch_columns(self):
        return list(set(self.selected_columns) | {col[0] for col in self.widget_columns})

    def _get_latest_txt_mtime(self):
        if not self._file_cache:
            return None
        # Фильтруем только .txt файлы из кэша
        txt_files = {name: mtime for name, mtime in self._file_cache.items() if name.endswith('.txt')}
        return max(txt_files.values()) if txt_files else None

    def fetch_file_data(self, force=False):
        if self.is_parsing: return
        if not force and self.parsed_data and (cur := self._get_latest_txt_mtime()) is not None and cur == self._last_parsed_mtime: return
        
        self.is_parsing = True
        self._update_data_label()
        worker = FileParseWorker(self.folder_path, self._get_fetch_columns(), self._file_cache)
        worker.signals.data_parsed.connect(self._on_file_data_parsed)
        QThreadPool.globalInstance().start(worker)

    def _on_file_data_parsed(self, data, error, mtime):
        self.is_parsing, self.parsed_data, self.parse_error = False, data, error
        if not error and mtime is not None: self._last_parsed_mtime = mtime
        self._update_data_label()

    def _update_data_label(self):
        if self.is_parsing and not self.parsed_data: text = "Чтение файла..."
        elif self.parse_error: text = f"Ошибка: {self.parse_error}"
        elif not self.parsed_data: text = "Нет данных"
        else: text = "<br>".join(f"<b>{col}</b>: {self.parsed_data[col]}" for col in self.selected_columns if col in self.parsed_data) or "Нет данных"
        if hasattr(self, "detail_data_label"): self.detail_data_label.setText(text)
        if hasattr(self, "compact_value_labels"):
            for col_key, label in self.compact_value_labels.items():
                ind = self.compact_indicators.get(col_key)
                if self.is_parsing and not self.parsed_data:
                    label.setText("…")
                    if ind: ind.setStyleSheet(Styles.param_indicator("transparent"))
                elif self.parse_error:
                    label.setText("err")
                    if ind: ind.setStyleSheet(Styles.param_indicator(P.bad))
                elif col_key in self.parsed_data:
                    val_str = str(self.parsed_data[col_key])
                    label.setText(val_str)
                    if ind:
                        if col_key in PARAM_RANGES:
                            try:
                                vmin, vmax = PARAM_RANGES[col_key]
                                ind.setStyleSheet(Styles.param_indicator(P.bad if not (vmin <= float(val_str) <= vmax) else P.ok))
                            except ValueError:
                                ind.setStyleSheet(Styles.param_indicator(P.violet))
                        else:
                            ind.setStyleSheet(Styles.param_indicator(P.violet))
                else:
                    label.setText("—")
                    if ind: ind.setStyleSheet(Styles.param_indicator("transparent"))

    def _open_column_selector(self):
        dlg = ColumnSelectDialog(ALL_COLUMNS, self.selected_columns, self)
        if dlg.exec_():
            self.selected_columns = dlg.get_selected()
            self._last_parsed_mtime = None
            self.fetch_file_data(force=True)

    def _on_name_changed(self, text):
        if text.strip():
            self.custom_name = text
            self.compact_name.setText(text)

    def _on_indicator_mode_changed(self, text): self._update_blink_state()
    def _toggle_blink(self):
        self._blink_state = not self._blink_state
        self._apply_indicator_color()

    def _update_blink_state(self):
        if self._base_color_hex == P.bad and self.indicator_mode_combo.currentText() == "Мигание":
            if not self.blink_timer.isActive(): self.blink_timer.start()
        else:
            self.blink_timer.stop()
            self._blink_state = False
        self._apply_indicator_color()

    def set_compact(self, compact):
        self._compact = compact
        self._stack.setCurrentIndex(1 if compact else 0)
        if compact:
            self.setStyleSheet(Styles.block_compact())
            self._update_block_height()
        else:
            self.setMinimumSize(0, 0)
            self.setMaximumSize(16777215, 16777215)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.setStyleSheet(Styles.block_detail())
        self.unsetCursor()

    def _open_folder(self): QDesktopServices.openUrl(QUrl.fromLocalFile(self.folder_path))

    def _copy_param_value(self, col_key):
        QApplication.clipboard().setText(f"{col_key}: {self.parsed_data.get(col_key, '—')}")

    def _update_alert_info(self):
        if self.use_period_alert_cb.isChecked():
            p, mult = self.period_spin.value(), self.multiplier_spin.value()
            self.alert_info.setText("Тревога > %.1f мин (период %d × %.1f)." % (p * mult, p, mult))
        else:
            self.alert_info.setText("Тревога > %d мин с момента прихода последнего файла." % self.start_timeout_spin.value())

    def _on_exact_start_toggled(self, checked): self.start_time_edit.setEnabled(checked and not self._running)

    def _on_multiplier_toggled(self, checked):
        active = checked and not self._running
        self.multiplier_spin.setEnabled(active)
        self.lbl_mult.setEnabled(active)
        self._update_alert_info()
    
    def _set_circle(self, color):
        self._base_color_hex = {"gray": P.idle, "green": P.ok, "red": P.bad}.get(color, color)
        self._update_blink_state()

    def _apply_indicator_color(self):
        c = QColor(self._base_color_hex)
        alpha = 70 if (self.blink_timer.isActive() and self._blink_state) else 255
        color_style = f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"
        glow_c = QColor(c)
        glow_c.setAlpha(int(alpha * 0.75))
        if hasattr(self, "circle"):
            self.circle.setStyleSheet(Styles.indicator(color_style, 7))
            self.circle_glow.setColor(glow_c)
        if hasattr(self, "compact_indicator"):
            self.compact_indicator.setStyleSheet(Styles.indicator_strip(color_style, R_CARD - 1))
            self.indicator_glow.setColor(glow_c)

    def _update_last_file_label(self):
        if self.last_file_time is not None: text = "Последний файл: " + self.last_file_time.strftime("%Y-%m-%d %H:%M:%S")
        elif self._watch_start is not None: text = "Последний файл: — (в папке нет файлов)"
        else: text = "Последний файл: —"
        self.last_file_label.setText(text)
        
        if hasattr(self.compact_indicator, '_custom_tooltip_filter'):
            self.compact_indicator._custom_tooltip_filter.setText(text)
        else:
            set_custom_tooltip(self.compact_indicator, text)

    def _update_check_times(self):
        ref_time = self.last_file_time or self._watch_start
        no_file_str = "Нет: —"
        if ref_time is not None:
            delta_sec = max(0, int((datetime.now() - ref_time).total_seconds()))
            days = delta_sec // 86400
            hours = (delta_sec % 86400) // 3600
            minutes = (delta_sec % 3600) // 60
            if days > 0:
                dur = f"{days} д {hours} ч"
            elif hours > 0:
                dur = f"{hours} ч {minutes} мин"
            elif minutes > 0:
                dur = f"{minutes} мин"
            else:
                dur = "менее минуты"
            no_file_str = f"Нет: {dur}"
        if self._running:
            last_str = self.last_check_time.strftime("%H:%M:%S")
            next_str = self.next_check_time.strftime("%H:%M:%S") if self.next_check_time else "—"
            head = f"Посл: {last_str} | След: {next_str}"
        else:
            head = "Проверка: остановлен"
        if hasattr(self, "check_time_label"):
            self.check_time_label.setText(head)
        if hasattr(self, "no_file_label"):
            self.no_file_label.setText(no_file_str)
        if hasattr(self, "compact_check_time_label"):
            self.compact_check_time_label.setText(head + "\n" + no_file_str)

    def start(self):
        if self._running: return
        self._watch_start = datetime.now()
        self._start_time_qtime = self.start_time_edit.time() if self.use_exact_start_cb.isChecked() else None
        self._running = True
        self.last_check_time = datetime.now()
        self._update_check_times()
        
        for w in (self.start_btn, self.period_spin, self.multiplier_spin, self.use_period_alert_cb, self.start_timeout_spin, self.use_exact_start_cb, self.start_time_edit): w.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.lbl_mult.setEnabled(False)
        self.check_files(initial=True)
        self._schedule_next_check()
        self.fetch_file_data(force=True)

    def stop(self):
        if not self._running: return
        self._running = False
        self.next_check_time = None
        self.timer.stop()
        self._file_cache.clear()
        self._update_check_times()
        
        for w in (self.start_btn, self.period_spin, self.use_period_alert_cb, self.start_timeout_spin, self.use_exact_start_cb): w.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.start_time_edit.setEnabled(self.use_exact_start_cb.isChecked())
        self._on_multiplier_toggled(self.use_period_alert_cb.isChecked())
        self._set_circle("gray")

    def is_running(self): return self._running

    def _schedule_next_check(self):
        now = datetime.now()
        if self._start_time_qtime is not None:
            next_tick = self._compute_next_tick(now)
            delay_ms = max(int((next_tick - now).total_seconds() * 1000), 100)
        else: delay_ms = self.period_spin.value() * 60 * 1000
        
        self.next_check_time = now + timedelta(milliseconds=delay_ms)
        self.timer.setSingleShot(True)
        self.timer.start(delay_ms)
        self._update_check_times()

    def _compute_next_tick(self, now):
        period_sec = self.period_spin.value() * 60
        base = now.replace(hour=self._start_time_qtime.hour(), minute=self._start_time_qtime.minute(), second=self._start_time_qtime.second(), microsecond=0)
        if base > now: base -= timedelta(days=1)
        return base + timedelta(seconds=(int((now - base).total_seconds() // period_sec) + 1) * period_sec)

    def _on_timer(self):
        if self._running:
            self.check_files(initial=False)
            self._schedule_next_check()

    def check_files(self, initial=False):
        if self._is_scanning: return
        self._is_scanning = True
        worker = ScanWorker(self.folder_path, self.last_check_time, initial, self._file_cache)
        worker.signals.finished.connect(self._on_scan_finished)
        worker.signals.error.connect(self._on_scan_error)
        QThreadPool.globalInstance().start(worker)

    def _on_scan_error(self, err_msg, scan_time):
        self._is_scanning = False
        self.status_changed.emit(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), self.custom_name, f"Ошибка: {err_msg}")
        self._set_circle("red")
        


    def _on_scan_finished(self, found, initial, scan_time, max_file_time, current_cache):
        self._is_scanning = False
        self.last_check_time = scan_time
        
        # Ограничиваем размер кэша
        if len(current_cache) > MAX_CACHE_SIZE:
            # Оставляем только самые свежие файлы
            sorted_files = sorted(current_cache.items(), key=lambda x: x[1], reverse=True)
            self._file_cache = dict(sorted_files[:MAX_CACHE_SIZE])
        else:
            self._file_cache = current_cache
        self._file_cache = current_cache  # Обновляем кэш
        if max_file_time: self.last_file_time = max_file_time
        self._update_last_file_label()
        if not self._running: 
            self._update_check_times()
            return
        if found:
            self.status_changed.emit(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), self.custom_name, ("Файлы найдены (%d)" if initial else "Файлы пришли (%d)") % len(found))
            if not initial: self.fetch_file_data()
        else:
            self.status_changed.emit(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), self.custom_name, "Файлов нет")
        self._update_indicator(datetime.now(), initial=initial)
        self._update_check_times()

    def _update_indicator(self, now=None, initial=False):
        if not self._running:
            self._set_circle("gray")
            return
        now = now or datetime.now()
        
        if self.last_file_time is None:
            self._set_circle("red")
            return
            
        ref_time = self.last_file_time
        threshold = (self.period_spin.value() * self.multiplier_spin.value()) if self.use_period_alert_cb.isChecked() else self.start_timeout_spin.value()
        self._set_circle("red" if (now - ref_time).total_seconds() / 60.0 > threshold else "green")

# ---------------------------------------------------------------------------
# ОВЕРЛЕЙ ПОДСВЕТКИ ЗОНЫ ВСТАВКИ
# ---------------------------------------------------------------------------
class DropOverlay(QWidget):
    """Прозрачный оверлей, рисует подсвеченную зону вставки при drag & drop блока."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)  # drag-события проходят сквозь
        self.setAttribute(Qt.WA_NoSystemBackground)         # не заливать фон под блоки
        self._rect = QRect()

    def set_rect(self, rect):
        rect = QRect(rect)
        if rect != self._rect:
            self._rect = rect
            self.update()

    def clear(self):
        if not self._rect.isNull():
            self._rect = QRect()
            self.update()

    def paintEvent(self, event):
        if self._rect.isNull() or self._rect.isEmpty():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(52, 152, 219, 60))                   # полупрозрачная заливка
        painter.setPen(QPen(QColor(52, 152, 219), max(2, s(2)), Qt.DashLine))
        painter.drawRoundedRect(self._rect.adjusted(1, 1, -1, -1), s(8), s(8))

# ---------------------------------------------------------------------------
# КОНТЕЙНЕР БЛОКОВ
# ---------------------------------------------------------------------------
class BlocksContainer(QWidget):
    block_added = pyqtSignal(object)
    block_removed = pyqtSignal(object)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("blocksRoot")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self.stack = QStackedWidget(self)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.stack)

        self.normal_page = QWidget()
        self.normal_page.setObjectName("blocksPage")
        self.normal_layout = QVBoxLayout(self.normal_page)
        self.normal_layout.setAlignment(Qt.AlignTop)
        self.normal_layout.setSpacing(s(8))
        self.normal_layout.setContentsMargins(s(12), s(12), s(12), s(12))
        self.stack.addWidget(self.normal_page)

        self.compact_page = QWidget()
        self.compact_page.setObjectName("blocksPage")
        self.compact_page.setContentsMargins(0, 0, 0, 0)
        self.compact_layout = FlowLayout(self.compact_page, margin=s(16), h_spacing=s(24), v_spacing=s(24))
        self.stack.addWidget(self.compact_page)

        self.blocks, self._compact = [], False
        self.dragged_block = None
        self.hint = QLabel("Перетащите папки сюда,\nчтобы создать блоки наблюдения")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setStyleSheet(Styles.hint())
        self.hint.setAcceptDrops(False)
        self.hint.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.normal_layout.addWidget(self.hint)
        self.normal_layout.addStretch()

        # Оверлей для отрисовки подсвеченной зоны вставки
        self.drop_overlay = DropOverlay(self)
        self.drop_overlay.setGeometry(self.rect())
        self.drop_overlay.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "drop_overlay"):
            self.drop_overlay.setGeometry(self.rect())
            self.drop_overlay.raise_()
        if self._compact: self.compact_layout.invalidate()

    def set_compact(self, compact):
        self._compact = compact
        self.stack.setCurrentIndex(1 if compact else 0)
        if compact:
            for b in self.blocks:
                self.normal_layout.removeWidget(b)
                self.compact_layout.addWidget(b)
            if not self.blocks:
                self.normal_layout.removeWidget(self.hint)
                self.compact_layout.addWidget(self.hint)
            self.hint.setText("📁 →")
            self.hint.setStyleSheet(Styles.hint_compact())
        else:
            for b in self.blocks:
                self.compact_layout.removeWidget(b)
                self.normal_layout.insertWidget(self.normal_layout.count() - 1, b, 0, Qt.AlignTop)
            if not self.blocks:
                self.compact_layout.removeWidget(self.hint)
                self.normal_layout.insertWidget(self.normal_layout.count() - 1, self.hint)
            self.hint.setText("Перетащите папки сюда,\nчтобы создать блоки наблюдения")
            self.hint.setStyleSheet(Styles.hint())
        self.compact_page.updateGeometry()
        self.normal_page.updateGeometry()
        if hasattr(self, "drop_overlay"):
            self.drop_overlay.raise_()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasFormat("application/x-blockwidget"):
            event.acceptProposedAction()

    def _get_drop_index(self, pos):
        """Вычисляет индекс для вставки блока"""
        drop_idx = len(self.blocks)
        if not self._compact:
            for i, b in enumerate(self.blocks):
                b_rect = QRect(b.mapTo(self, QPoint(0, 0)), b.size())
                if pos.y() < b_rect.center().y():
                    drop_idx = i
                    break
        else:
            for i, b in enumerate(self.blocks):
                b_rect = QRect(b.mapTo(self, QPoint(0, 0)), b.size())
                if pos.y() < b_rect.top():
                    drop_idx = i
                    break
                elif pos.y() <= b_rect.bottom():
                    if pos.x() < b_rect.center().x():
                        drop_idx = i
                        break
                    else:
                        drop_idx = i + 1
        return drop_idx

    def _compute_drop_rect(self, drop_idx):
        if not self.blocks:
            return QRect()
        if not self._compact:
            return self._compute_normal_drop_rect(drop_idx)
        return self._compute_compact_drop_rect(drop_idx)

    def _compute_normal_drop_rect(self, drop_idx):
        """Зона вставки для вертикального списка (основное окно)."""
        top_margin, bottom_margin = s(8), s(8)
        min_h = s(44)

        if drop_idx <= 0:
            b_top = self.blocks[0].mapTo(self, QPoint(0, 0)).y()
            gap_top, gap_bottom = top_margin, b_top
        elif drop_idx >= len(self.blocks):
            last = self.blocks[-1]
            b_bottom = last.mapTo(self, QPoint(0, last.height())).y()
            gap_top, gap_bottom = b_bottom, self.height() - bottom_margin
        else:
            prev_b = self.blocks[drop_idx - 1]
            next_b = self.blocks[drop_idx]
            gap_top = prev_b.mapTo(self, QPoint(0, prev_b.height())).y()
            gap_bottom = next_b.mapTo(self, QPoint(0, 0)).y()

        if gap_bottom - gap_top < min_h:
            center_y = (gap_top + gap_bottom) / 2.0
            gap_top = int(center_y - min_h / 2.0)
            gap_bottom = gap_top + min_h

        gap_top = max(gap_top, top_margin)
        gap_bottom = min(gap_bottom, self.height() - bottom_margin)
        if gap_bottom <= gap_top:
            return QRect()
        return QRect(s(8), gap_top, max(self.width() - s(16), 0), gap_bottom - gap_top)

    def _compute_compact_drop_rect(self, drop_idx):
        """Зона вставки для сетки (режим виджета)."""
        def br(b):
            return QRect(b.mapTo(self, QPoint(0, 0)), b.size())

        pad = s(10)
        edge_overlap = s(4)

        if drop_idx <= 0:
            r = br(self.blocks[0])
            left = max(r.x() - pad, s(4))
            return QRect(left, r.top(), (r.x() + edge_overlap) - left, r.height())
        elif drop_idx >= len(self.blocks):
            r = br(self.blocks[-1])
            right_end = min(r.x() + r.width() + pad, self.width() - s(4))
            start_x = r.x() + r.width() - edge_overlap
            return QRect(start_x, r.top(), right_end - start_x, r.height())
        else:
            prev_r = br(self.blocks[drop_idx - 1])
            next_r = br(self.blocks[drop_idx])
            same_row = abs(prev_r.top() - next_r.top()) < s(10)
            if same_row:
                x = (prev_r.x() + prev_r.width() + next_r.x()) // 2
                return QRect(x - pad, prev_r.top(), pad * 2, prev_r.height())
            else:
                y = (prev_r.y() + prev_r.height() + next_r.y()) // 2
                return QRect(next_r.x(), y - pad, next_r.width(), pad * 2)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-blockwidget"):
            drop_idx = self._get_drop_index(event.pos())
            self.drop_overlay.set_rect(self._compute_drop_rect(drop_idx))
            self.drop_overlay.raise_()
            event.acceptProposedAction()
        elif event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.drop_overlay.clear()
        event.accept()

    def dropEvent(self, event):
        self.drop_overlay.clear()

        if event.mimeData().hasFormat("application/x-blockwidget"):
            source_block = self.dragged_block
            if not source_block:
                return

            drop_idx = self._get_drop_index(event.pos())
            old_idx = self.blocks.index(source_block)

            if drop_idx > old_idx:
                drop_idx -= 1

            if drop_idx != old_idx:
                self.blocks.pop(old_idx)
                self.blocks.insert(drop_idx, source_block)
                self._refresh_layout()

            event.acceptProposedAction()
            return

        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if os.path.isdir(path) and not any(b.folder_path == path for b in self.blocks):
                    self.add_block(path)

    def _refresh_layout(self):
        """Перестраивает интерфейс после изменения порядка блоков"""
        for b in self.blocks:
            if self._compact: self.compact_layout.removeWidget(b)
            else: self.normal_layout.removeWidget(b)
        
        for b in self.blocks:
            if self._compact: self.compact_layout.addWidget(b)
            else: self.normal_layout.insertWidget(self.normal_layout.count() - 1, b, 0, Qt.AlignTop)
        
        self.compact_page.updateGeometry()
        self.normal_page.updateGeometry()
        
        if self._compact:
            self.compact_layout.invalidate()
            self.compact_layout.activate()
            self.compact_page.update()
        
        if hasattr(self, "drop_overlay"):
            self.drop_overlay.raise_()

    def add_block(self, path):
        self.hint.hide()
        block = BlockWidget(path)
        block.delete_requested.connect(self.remove_block)
        self.blocks.append(block)
        if self._compact: self.compact_layout.addWidget(block)
        else: self.normal_layout.insertWidget(self.normal_layout.count() - 1, block, 0, Qt.AlignTop)
        self.block_added.emit(block)
        return block

    def remove_block(self, block):
        if block.is_running(): block.stop()
        block.deleteLater()
        if block in self.blocks: self.blocks.remove(block)
        if self._compact: self.compact_layout.removeWidget(block)
        else: self.normal_layout.removeWidget(block)
        if not self.blocks: self.hint.show()
        self.block_removed.emit(block)

# ---------------------------------------------------------------------------
# ДИАЛОГ ЖУРНАЛА
# ---------------------------------------------------------------------------
class JournalDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Журнал блоков")
        self.resize(s(800), s(500))
        self.setStyleSheet(Styles.dialog_style())
        layout = QVBoxLayout(self)
        
        self.clear_btn = QPushButton("Очистить журнал")
        self.clear_btn.setStyleSheet(Styles.clear_btn())
        self.clear_btn.clicked.connect(lambda: self.table.setRowCount(0))
        layout.addWidget(self.clear_btn, 0, Qt.AlignLeft)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Время проверки", "Блок", "Статус"])
        self.table.setStyleSheet(Styles.table())
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

    def add_entry(self, time_str, block_name, status):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(time_str))
        self.table.setItem(row, 1, QTableWidgetItem(block_name))
        item = QTableWidgetItem(status)
        low = status.lower()
        item.setForeground(QColor("green" if ("пришли" in low or "найдены" in low) else "red" if "ошибка" in low else "gray"))
        self.table.setItem(row, 2, item)
        self.table.scrollToBottom()

#---------------------------------------------------------------------------
#ВСПЛЫВАЮЩЕЕ УВЕДОМЛЕНИЕ ВНУТРИ ОКНА
#---------------------------------------------------------------------------
class ToastNotification(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setStyleSheet(f"""
            QFrame#toast {{
                background-color: {P.surface};
                border: 1px solid {P.border};
                border-radius: {s(R_BTN)}px;
            }}
        """)
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(s(20))
        self._shadow.setColor(QColor(15, 23, 42, 60))
        self._shadow.setOffset(0, s(4))
        self.setGraphicsEffect(self._shadow)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(s(12), s(8), s(14), s(8))
        lay.setSpacing(s(8))
        self.icon_label = QLabel()
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        self.text_label = QLabel()
        self.text_label.setStyleSheet(f"""
            QLabel {{
                color: {P.ink}; font-size: {s(FONT_INPUT)}px;
                background: transparent; border: none;
            }}
        """)
        lay.addWidget(self.icon_label, 0, Qt.AlignVCenter)
        lay.addWidget(self.text_label, 0, Qt.AlignVCenter)

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)

        self._anim = None
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)
        self.hide()

    def show_message(self, text, kind="info", duration=2500):
        icons = {"info": "✓", "error": "✕", "warn": "⚠"}
        colors = {"info": P.ok_deep, "error": P.bad_deep, "warn": P.warn_deep}
        self.icon_label.setText(icons.get(kind, "✓"))
        self.icon_label.setStyleSheet(
            f"color: {colors.get(kind, P.ok_deep)}; font-weight: bold;"
            f"font-size: {s(18)}px; background: transparent; border: none;"
        )
        self.text_label.setText(text)
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        self._fade_in()
        self._hide_timer.start(duration)

    def reposition(self):
        p = self.parentWidget()
        if p is None:
            return
        x = (p.width() - self.width()) // 2
        y = p.height() - self.height() - s(16)
        self.move(max(s(8), x), max(s(8), y))

    def _fade_in(self):
        if self._anim is not None:
            self._anim.stop()
        self._effect.setOpacity(0.0)
        self._anim = QPropertyAnimation(self._effect, b"opacity")
        self._anim.setDuration(200)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.start()

    def _fade_out(self):
        if self._anim is not None:
            self._anim.stop()
        self._anim = QPropertyAnimation(self._effect, b"opacity")
        self._anim.setDuration(300)
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.InCubic)
        self._anim.finished.connect(self.hide)
        self._anim.start()


# ---------------------------------------------------------------------------
# ГЛАВНОЕ ОКНО
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Наблюдение за файлами")
        self.resize(s(1000), s(800))
        self.setMinimumSize(s(800), s(600))
        
        self.settings = QSettings("FileWatcher", "FileDateWatcher")
        self.journal = JournalDialog(self)
        self._tray_msg_shown, self._widget_mode, self._normal_geometry_bytes, self._normal_flags, self._saved_widget_pos = False, False, None, None, None
        self._current_save_path = None   # путь к активному файлу .mon; None = ещё не сохраняли
        self.setAcceptDrops(True)

        self._build_ui()
        self.toast = ToastNotification(self.central_widget)
        self._build_tray()
        self._restore_window_state()

        self.daily_timer = QTimer(self)
        self.daily_timer.setInterval(60000)
        self.daily_timer.timeout.connect(self._check_daily_update)
        self.daily_timer.start()
        self._last_update_day = datetime.now().day
        self._load_last_config()

    def _check_daily_update(self):
        now = datetime.now()
        if now.hour == 8 and now.minute == 0 and self._last_update_day != now.day:
            self._last_update_day = now.day
            self._refresh_all_data()

    def _refresh_all_data(self):
        for block in self.blocks_container.blocks: block.fetch_file_data(force=True)

    def _build_ui(self):
        self.central_widget = QWidget()
        self.central_widget.setObjectName("centralWidget")
        self.central_widget.setAttribute(Qt.WA_StyledBackground, True)
        self.central_widget.setStyleSheet(Styles.shell_normal() + Styles.app_shell())
        self.setCentralWidget(self.central_widget)
        
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(s(8), s(8), s(8), s(8))
        main_layout.setSpacing(0)
        self._main_layout = main_layout

        self.drag_panel = DragPanel(self.central_widget)
        self.drag_panel.setVisible(False)
        self.drag_panel.expand_clicked.connect(self.toggle_widget_mode)
        main_layout.addWidget(self.drag_panel)

        self.top_bar_widget = QWidget()
        top_layout = QHBoxLayout(self.top_bar_widget)
        top_layout.setContentsMargins(0, 0, 0, s(8))
        
        for text, slot in [("Запустить все блоки", self.run_all), ("Остановить все блоки", self.stop_all), ("Обновить данные", self._refresh_all_data), ("Режим виджета", self.toggle_widget_mode)]:
            btn = QPushButton(text)
            btn.setStyleSheet(Styles.btn_main())
            btn.clicked.connect(slot)
            top_layout.addWidget(btn)
            
        top_layout.addStretch()
        main_layout.addWidget(self.top_bar_widget)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("mainScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setAcceptDrops(False)
        self.scroll.viewport().setAcceptDrops(False)
        self.scroll.viewport().setObjectName("mapViewport")
        self.scroll.setFrameShape(QFrame.NoFrame)
        
        self.blocks_container = BlocksContainer()
        self.blocks_container.block_added.connect(self.on_block_added)
        self.blocks_container.block_removed.connect(self.on_block_removed)
        self.scroll.setWidget(self.blocks_container)
        main_layout.addWidget(self.scroll, 1)

        self.resize_grip = ResizeGrip(self.central_widget)
        self.resize_grip.setVisible(False)

    def _update_overlay_positions(self):
        if self._widget_mode:
            self.resize_grip.move(self.central_widget.width() - self.resize_grip.width() - s(6), self.central_widget.height() - self.resize_grip.height() - s(6))
            self.resize_grip.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_overlay_positions()
        if hasattr(self, "toast"):
            self.toast.reposition()

    def contextMenuEvent(self, event):
        if not self._widget_mode: return
        menu = QMenu(self)
        menu.setStyleSheet(Styles.menu())
        menu.addAction("Развернуть").triggered.connect(self._exit_widget_mode)
        menu.addSeparator()
        on_top = menu.addAction("Поверх всех окон")
        on_top.setCheckable(True)
        on_top.setChecked(bool(self.windowFlags() & Qt.WindowStaysOnTopHint))
        on_top.triggered.connect(self.toggle_stays_on_top)
        menu.addSeparator()
        menu.addAction("Выход").triggered.connect(self.quit_app)
        menu.exec_(event.globalPos())

    def toggle_stays_on_top(self, checked):
        flags = self.windowFlags() | Qt.WindowStaysOnTopHint if checked else self.windowFlags() & ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def _build_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))
        self.tray.setToolTip("Наблюдение")
        menu = QMenu()
        menu.setStyleSheet(Styles.menu())
        menu.addAction("Показать окно").triggered.connect(self.show_normal)
        menu.addAction("Режим виджета").triggered.connect(self.toggle_widget_mode)
        menu.addAction("Открыть журнал блоков").triggered.connect(self.show_journal)
        menu.addSeparator()
        menu.addAction("Выход").triggered.connect(self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def _restore_window_state(self):
        if (geo := self.settings.value("window/geometry")) is not None: self.restoreGeometry(geo)
        if isinstance((pos := self.settings.value("window/widget_pos")), QPoint): self._saved_widget_pos = pos

    def _save_window_state(self):
        if self._widget_mode and self._normal_geometry_bytes is not None: self.settings.setValue("window/geometry", self._normal_geometry_bytes)
        elif not self._widget_mode: self.settings.setValue("window/geometry", self.saveGeometry())
        if self._widget_mode: self.settings.setValue("window/widget_pos", self.pos())
        self.settings.sync()

    def toggle_widget_mode(self):
        if self._widget_mode: self._exit_widget_mode()
        else: self._enter_widget_mode()

    def _enter_widget_mode(self):
        if self._widget_mode: return
        self._normal_geometry_bytes, self._normal_flags = self.saveGeometry(), self.windowFlags()
        self._widget_mode = True
        if self._saved_widget_pos is None: self._saved_widget_pos = self.pos()

        self.hide()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        self.top_bar_widget.setVisible(False)
        self.drag_panel.setVisible(True)
        self._main_layout.setContentsMargins(s(0), 0, s(0), 0)
        self.setStyleSheet(f"QMainWindow {{ background-color: {P.bg}; }}")
        self.central_widget.setStyleSheet(Styles.central_widget() + Styles.app_shell())
        
        self.blocks_container.set_compact(True)
        for b in self.blocks_container.blocks: b.set_compact(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Фиксированный размер вместо авто-размера
        self.resize(s(800), s(600))

        self.show()
        self.move(self._saved_widget_pos)
        self.resize_grip.setVisible(True)
        QTimer.singleShot(0, self._update_overlay_positions)
        self.raise_()
        self.activateWindow()


    def _exit_widget_mode(self):
        if not self._widget_mode: return
        self._widget_mode = False
        self.hide()
        self.setWindowFlags(self._normal_flags)
        self.setStyleSheet("")
        self.central_widget.setStyleSheet(Styles.shell_normal() + Styles.app_shell())

        for b in self.blocks_container.blocks: b.set_compact(False)
        self.blocks_container.set_compact(False)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.top_bar_widget.setVisible(True)
        self.drag_panel.setVisible(False)
        self._main_layout.setContentsMargins(s(8), s(8), s(8), s(8))
        self.resize_grip.setVisible(False)


        self.setMinimumSize(s(800), s(600))
        self.show()
        if self._normal_geometry_bytes is not None: self.restoreGeometry(self._normal_geometry_bytes)
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.sync()
        self.raise_()
        self.activateWindow()

    def on_block_added(self, block):
        block.status_changed.connect(self.on_status_changed)
        if self._widget_mode:
            block.set_compact(True)

    def on_block_removed(self, block):
        pass

    def on_status_changed(self, time_str, block_name, status): self.journal.add_entry(time_str, block_name, status)
    
    def run_all(self):
        for block in self.blocks_container.blocks: block.start()

    def stop_all(self):
        for block in self.blocks_container.blocks: block.stop()

    def show_normal(self):
        if self._widget_mode: self._exit_widget_mode()
        else: self.showNormal()
        self.activateWindow()
        self.raise_()

    def show_journal(self):
        self.journal.show()
        self.journal.activateWindow()
        self.journal.raise_()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible() and not self._widget_mode: self.hide()
            else: self.show_normal()

    def _get_blocks_data(self):
        """Собирает данные всех блоков для сохранения."""
        print(f'[save] Количество блоков: {len(self.blocks_container.blocks)}')
        blocks = []
        for i, block in enumerate(self.blocks_container.blocks):
            print(f'[save] Блок {i}: {block.folder_path}')
            blocks.append({
                'folder_path': block.folder_path,
                'custom_name': block.custom_name,
                'period': block.period_spin.value(),
                'multiplier': block.multiplier_spin.value(),
                'use_period_alert': block.use_period_alert_cb.isChecked(),
                'start_timeout': block.start_timeout_spin.value(),
                'use_exact_start': block.use_exact_start_cb.isChecked(),
                'start_time': block.start_time_edit.time().toString('HH:mm'),
                'indicator_mode': block.indicator_mode_combo.currentText(),
                'selected_columns': block.selected_columns,
                'widget_columns': block.widget_columns
            })
        data = {'blocks': blocks}
        print(f'[save] Данные для сохранения: {data}')
        return data

    def _apply_block_settings(self, block, data):
        """Применяет настройки к блоку после загрузки."""
        block.custom_name = data.get('custom_name', block.custom_name)
        block.name_edit.setText(block.custom_name)
        block.period_spin.setValue(data.get('period', 5))
        block.multiplier_spin.setValue(data.get('multiplier', 1.5))
        block.use_period_alert_cb.setChecked(data.get('use_period_alert', False))
        block.start_timeout_spin.setValue(data.get('start_timeout', 30))
        block.use_exact_start_cb.setChecked(data.get('use_exact_start', False))
        block.start_time_edit.setTime(QTime.fromString(data.get('start_time', '00:00'), 'HH:mm'))
        block.indicator_mode_combo.setCurrentText(data.get('indicator_mode', 'Статика'))
        block.selected_columns = data.get('selected_columns', [])
        block.widget_columns = data.get('widget_columns', list(WIDGET_MAIN_COLUMNS))
        block._on_multiplier_toggled(block.use_period_alert_cb.isChecked())
        block._update_alert_info()
        if self._widget_mode:
            block._rebuild_compact_grid()

    def _do_write_file(self, filepath):
        """Запись данных в файл + обновление QSettings + toast."""
        data = self._get_blocks_data()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.settings.setValue('save/last_file', filepath)
        self.settings.sync()
        self._current_save_path = filepath
        print(f'[save] Сохранено: {filepath}')
        self.toast.show_message(f"Сохранено: {Path(filepath).name} ({len(data['blocks'])} блоков)", "info")

    def save_to_file(self, force_dialog=False):
        """Сохраняет конфигурацию.
        force_dialog=True  — всегда открывает диалог (Ctrl+Shift+S).
        force_dialog=False — если файл уже выбран, перезаписывает его; иначе открывает диалог."""
        filepath = self._current_save_path
        if filepath is None or force_dialog:
            filepath, _ = QFileDialog.getSaveFileName(
                self, "Сохранить конфигурацию",
                str(SAVE_DIR / f"config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mon"),
                "Monitoring files (*.mon);;All files (*)"
            )
            if not filepath:
                self.toast.show_message("Сохранение отменено", "warn", 2000)
                return
            if not filepath.endswith('.mon'):
                filepath += '.mon'
        try:
            self._do_write_file(filepath)
        except Exception as e:
            print(f'[save] Ошибка: {e}')
            self.toast.show_message(f"Ошибка сохранения: {e}", "error", 5000)

    def save_as(self):
        """Сохранить как — всегда с диалогом."""
        self.save_to_file(force_dialog=True)

    def load_from_file(self, filepath):
        """Загружает конфигурацию из файла .mon."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f'[load] Загруженные данные: {data}')
            blocks_count = len(data.get('blocks', []))
            print(f'[load] Количество блоков в файле: {blocks_count}')
            for block in list(self.blocks_container.blocks):
                self.blocks_container.remove_block(block)
            created = 0
            skipped = 0
            for block_data in data.get('blocks', []):
                folder_path = block_data.get('folder_path', '')
                if folder_path and os.path.isdir(folder_path):
                    block = self.blocks_container.add_block(folder_path)
                    self._apply_block_settings(block, block_data)
                    created += 1
                else:
                    print(f'[load] Пропущен блок: {folder_path} (папка не существует)')
                    skipped += 1
            print(f'[load] Создано блоков: {created}, пропущено: {skipped}')
            self.settings.setValue('save/last_file', filepath)
            self.settings.sync()
            self._current_save_path = filepath
            print(f'[load] Загружено: {filepath}')
            self.toast.show_message(f"Загружено: {Path(filepath).name} ({created} блоков)", "info")
        except Exception as e:
            print(f'[load] Ошибка: {e}')
            self.toast.show_message(f"Ошибка загрузки: {e}", "error", 5000)

    def _load_last_config(self):
        """Загружает последнее сохранение при старте."""
        last_path = self.settings.value('save/last_file', '')
        if last_path and Path(last_path).exists():
            self.load_from_file(last_path)
        else:
            print('[load] Файл не найден, загрузка пропущена')            

    def load_from_dialog(self):
        """Открыть файл .mon через диалог (Ctrl+O)."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Открыть конфигурацию",
            str(SAVE_DIR),
            "Monitoring files (*.mon);;All files (*)"
        )
        if filepath:
            self.load_from_file(filepath)
        else:
            print('[load] Файл не найден, загрузка пропущена')

    def quit_app(self):
        self._save_window_state()
        for block in self.blocks_container.blocks:
            if block.is_running(): block.stop()
        self.tray.hide()
        if self._current_save_path is not None:
            try:
                self._do_write_file(self._current_save_path)
            except Exception as e:
                print(f'[quit] Ошибка автосохранения: {e}')
        QThreadPool.globalInstance().clear()
        QThreadPool.globalInstance().waitForDone(1000)
        QApplication.quit()
        sys.exit(0)

    def keyPressEvent(self, event):
        """Обработчик горячих клавиш."""
        mods = event.modifiers()
        if mods & Qt.ControlModifier and mods & Qt.ShiftModifier and event.key() == Qt.Key_S:
            self.save_as()                      # Ctrl+Shift+S — сохранить как
            event.accept()
        elif mods & Qt.ControlModifier and event.key() == Qt.Key_S:
            self.save_to_file()                 # Ctrl+S — сохранить / перезаписать
            event.accept()
        elif mods & Qt.ControlModifier and event.key() == Qt.Key_O:
            self.load_from_dialog()             # Ctrl+O — открыть
            event.accept()
        else:
            super().keyPressEvent(event)


    def closeEvent(self, event):
        self._save_window_state()
        event.ignore()
        self.hide()
        if not self._tray_msg_shown:
            self._tray_msg_shown = True
            self.tray.showMessage("Наблюдение за файлами", "Программа свёрнута в трей", QSystemTrayIcon.Information, 2000)

if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)

    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    init_ui_scale(app.primaryScreen())
    print(f"[scale] mode={SCALE_MODE} UI_SCALE={UI_SCALE:.3f} s(16)={s(16)}")  # диагностика, потом удалить


    app.setOrganizationName("FileWatcher")
    app.setApplicationName("FileDateWatcher")
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())