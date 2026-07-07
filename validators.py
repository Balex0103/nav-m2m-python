import os
from pathlib import Path
from typing import Optional

import xmlschema

from config import NavUserConfig, normalize_environment


SUPPORTED_ENVIRONMENTS = {"TEST", "PROD"}


def validate_user_config(config: NavUserConfig) -> Optional[str]:
    tech_user = config.tech_user.strip()
    password = config.password.strip()
    sign_key = config.sign_key.strip()
    exchange_key = config.exchange_key.strip()
    tax_number = "".join(ch for ch in config.tax_number if ch.isdigit())
    environment = config.environment.strip().upper()

    if not tech_user:
        return "A technikai felhasználónév kötelező."

    if not password:
        return "A jelszó kötelező."

    if not sign_key:
        return "Az aláíró kulcs kötelező."

    if not exchange_key:
        return "Az XML cserekulcs kötelező."

    if not tax_number:
        return "Az adószám kötelező."

    if len(tax_number) != 8:
        return "Az adószámnak pontosan 8 számjegyből kell állnia."

    if not tax_number.isdigit():
        return "Az adószám csak számjegyeket tartalmazhat."

    if environment not in SUPPORTED_ENVIRONMENTS:
        return "A környezet csak TEST vagy PROD lehet."

    try:
        normalize_environment(environment)
    except ValueError:
        return "A környezet csak TEST vagy PROD lehet."

    return None


def _friendly_xsd_error_message(raw_error: str) -> str:
    error_text = raw_error.lower()

    if "taxnumber" in error_text or "taxpayerid" in error_text:
        return "A cég vagy partner adószáma hibás formátumú. Pontosan 8 számjegyből kell állnia."

    if "sourcedocumentid" in error_text or "invoicenumber" in error_text:
        return "Egy vagy több számlaszám formátuma érvénytelen vagy hiányzik."

    if "taxbase" in error_text or "taxamount" in error_text:
        return "Az összeg mezőben hibás érték vagy tiltott karakter szerepel."

    if "standardtaxcode" in error_text:
        return "Az áfakód nem felel meg a NAV engedélyezett kódlistájának."

    if "date" in error_text:
        return "Valamelyik dátummező formátuma hibás. A helyes formátum: ÉÉÉÉ-HH-NN."

    if "sequence" in error_text or "unexpected child" in error_text:
        return "Az XML elemek sorrendje vagy szerkezete nem felel meg a NAV sémának."

    return "Formai hiba található az adatokban. Kérlek, ellenőrizd a kötelező mezőket és az XML szerkezetét."


def validate_xml_with_xsd(xml_path: str, vdr_folder: str = "vdr") -> tuple[bool, str]:
    xml_file = Path(xml_path).resolve()
    vdr_path = Path(vdr_folder).resolve()

    if not xml_file.is_file():
        return False, f"A megadott XML fájl nem található: {xml_file}"

    if not vdr_path.exists() or not vdr_path.is_dir():
        return False, f"A vdr mappa nem található: {vdr_path}"

    ear_data_path = vdr_path / "earData.xsd"
    common_path = vdr_path / "common.xsd"
    ear_base_path = vdr_path / "earBase.xsd"
    ear_api_path = vdr_path / "earAPI.xsd"

    required_files = [ear_data_path, common_path, ear_base_path, ear_api_path]
    missing_files = [file.name for file in required_files if not file.is_file()]

    if missing_files:
        return False, f"Hiányzó sémafájl(ok) a vdr mappából: {', '.join(missing_files)}"

    original_cwd = Path.cwd()

    try:
        locations = {
            "http://schemas.nav.gov.hu/NTCA/1.0/common": "common.xsd",
            "http://schemas.nav.gov.hu/EAR/1.0/base": "earBase.xsd",
            "http://schemas.nav.gov.hu/EAR/1.0/data": "earData.xsd",
            "http://schemas.nav.gov.hu/EAR/1.0/api": "earAPI.xsd",
        }

        os.chdir(vdr_path)

        schema = xmlschema.XMLSchema("earData.xsd", locations=locations)
        schema.validate(str(xml_file))

        return True, "Az XML hivatalosan is VALID a megadott XSD alapján."

    except xmlschema.XMLSchemaValidationError as err:
        raw_error = str(getattr(err, "reason", str(err)))
        friendly_message = _friendly_xsd_error_message(raw_error)
        return False, f"{friendly_message} | Részlet: {raw_error[:200]}"

    except Exception as err:
        return False, f"Rendszerhiba az XSD validáció közben: {str(err)[:200]}"

    finally:
        os.chdir(original_cwd)