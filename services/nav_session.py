from __future__ import annotations

from typing import Any, cast

from config import NavUserConfig
from services import ui_runtime

def nav_config_osszeallitasa() -> NavUserConfig:
    return NavUserConfig(
        tech_user=cast(Any, entry_tech_user).get().strip(),
        password=cast(Any, entry_jelszo).get().strip(),
        sign_key=cast(Any, entry_sign_kulcs).get().strip(),
        exchange_key=cast(Any, entry_xml_kulcs).get().strip(),
        tax_number=cast(Any, entry_adoszam).get().strip(),
        environment=cast(Any, combo_kornyezet).get().strip().upper(),
    )

def helyorzo_vagy_hianyos_ertek(value: str) -> bool:
    text = value.strip().upper()
    if not text:
        return True

    tiltott_reszek = [
        "IDE_",
        "VALODI_",
        "PLACEHOLDER",
        "TECH_USER",
        "SIGN_KEY",
        "EXCHANGE_KEY",
        "JELSZO",
        "PASSWORD",
        "ADOSZAM",
    ]
    return any(resz in text for resz in tiltott_reszek)

def tul_rovid_valodi_kulcshoz(value: str, minimum_hossz: int) -> bool:
    return len(value.strip()) < minimum_hossz

def van_valodi_nav_hitelesites(config: NavUserConfig) -> bool:
    return not any([
        helyorzo_vagy_hianyos_ertek(config.tech_user),
        helyorzo_vagy_hianyos_ertek(config.password),
        helyorzo_vagy_hianyos_ertek(config.sign_key),
        helyorzo_vagy_hianyos_ertek(config.exchange_key),
        helyorzo_vagy_hianyos_ertek(config.tax_number),
        tul_rovid_valodi_kulcshoz(config.password, 8),
        tul_rovid_valodi_kulcshoz(config.sign_key, 16),
        tul_rovid_valodi_kulcshoz(config.exchange_key, 16),
    ])

def eafa_feltoltes_engedelyezve(config: NavUserConfig) -> bool:
    try:
        engedelyezve = bool(cast(Any, chk_eafa_feltoltes).get())
    except Exception:
        engedelyezve = False

    return engedelyezve and config.environment == "TEST"

