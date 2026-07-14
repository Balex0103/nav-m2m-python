from __future__ import annotations

from typing import Any, cast

from config import NavUserConfig


def nav_config_osszeallitasa(tech_user: str, password: str, sign_key: str, exchange_key: str, tax_number: str, environment: str) -> NavUserConfig:
    return NavUserConfig(
        tech_user=tech_user.strip(),
        password=password.strip(),
        sign_key=sign_key.strip(),
        exchange_key=exchange_key.strip(),
        tax_number=tax_number.strip(),
        environment=environment.strip().upper(),
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

def eafa_feltoltes_engedelyezve(config: NavUserConfig, engedelyezve: bool) -> bool:
    return engedelyezve and config.environment == "TEST"