from __future__ import annotations

import os
from xml.etree import ElementTree as ET

from config import NavUserConfig


def validate_user_config(config: NavUserConfig) -> str | None:
    if not config.tech_user.strip():
        return "A technikai felhasználó megadása kötelező."
    if not config.password.strip():
        return "A jelszó megadása kötelező."
    if not config.sign_key.strip():
        return "A signature kulcs megadása kötelező."
    if not config.exchange_key.strip():
        return "Az exchange kulcs megadása kötelező."
    if not config.tax_number.strip():
        return "Az adószám megadása kötelező."
    if config.environment.upper() not in {"TEST", "PROD"}:
        return "A környezet csak TEST vagy PROD lehet."
    norm = config.normalized_tax_number()
    if not norm.isdigit() or len(norm) < 8:
        return "Az adószám formátuma hibás."
    return None


def _find_xsd_files(vdr_dir: str) -> list[str]:
    if not os.path.isdir(vdr_dir):
        return []
    return [os.path.join(vdr_dir, name) for name in os.listdir(vdr_dir) if name.lower().endswith(".xsd")]


def validate_xml_with_xsd(xml_path: str, vdr_dir: str) -> tuple[bool, str]:
    if not os.path.exists(xml_path):
        return False, "A validálandó XML fájl nem található."
    try:
        ET.parse(xml_path)
    except Exception as exc:
        return False, f"Az XML nem jól formált: {exc}"

    xsd_files = _find_xsd_files(vdr_dir)
    if not xsd_files:
        return True, "XSD fájl nem található, csak jólformáltsági ellenőrzés történt."

    try:
        import xmlschema  # type: ignore
        for xsd in xsd_files:
            try:
                schema = xmlschema.XMLSchema(xsd)
                schema.validate(xml_path)
                return True, f"Sikeres XSD validáció: {os.path.basename(xsd)}"
            except Exception:
                continue
        return False, "Egyik elérhető XSD séma sem fogadta el az XML-t."
    except Exception:
        return True, "Az XML jól formált, de xmlschema csomag hiányában teljes XSD validáció nem futott."
