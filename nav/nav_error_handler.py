import xml.etree.ElementTree as ET
from typing import Dict, Optional


NAV_ERROR_MAP: Dict[str, Dict[str, str]] = {
    "INVALID_SECURITY_USER": {
        "title": "Helytelen authentikációs adatok",
        "reason": "A technikai felhasználónév, jelszó vagy a passwordHash hibás lehet.",
        "action": "Ellenőrizd a technikai felhasználót, a jelszót, a TEST/PROD környezetet és a SHA-512 jelszó hash számítást."
    },
    "INVALID_REQUEST_SIGNATURE": {
        "title": "Érvénytelen kérés aláírás",
        "reason": "A requestSignature nem egyezik a NAV által elvárt értékkel.",
        "action": "Ellenőrizd a sign key értékét, a requestId + timestamp + signKey összefűzést és a SHA3-512 használatát."
    },
    "INVALID_USER_RELATION": {
        "title": "Helytelen felhasználói kapcsolat",
        "reason": "A technikai felhasználó nem ehhez az adószámhoz tartozik, vagy nincs megfelelő jogosultsága.",
        "action": "Ellenőrizd, hogy a technikai felhasználó ugyanahhoz a céghez tartozik-e, és van-e 'számlák kezelése' és 'számlák lekérdezése' joga."
    },
    "SCHEMA_VIOLATION": {
        "title": "Séma validációs hiba",
        "reason": "Az XML formailag vagy szerkezetileg nem felel meg a NAV sémának.",
        "action": "Ellenőrizd a namespace-eket, kötelező mezőket, adattípusokat és az XSD validáció eredményét."
    },
    "INVALID_REQUEST": {
        "title": "Helytelen kérés",
        "reason": "A kérés XML szerkezete vagy tartalma nem megfelelő.",
        "action": "Nézd meg a request XML-t, a kötelező mezőket, a namespace-eket és a kérés felépítését."
    },
    "INVALID_VAT_DATA": {
        "title": "Hibás áfaadat",
        "reason": "Az áfakulcs, adóalap vagy adóösszeg nem konzisztens.",
        "action": "Ellenőrizd a számlasorok áfaadatait, a taxBase és taxAmount mezőket, illetve a mapping szabályokat."
    },
    "NOT_REGISTERED_CUSTOMER": {
        "title": "Nem regisztrált adózó",
        "reason": "A kérésben szereplő adózó nincs regisztrálva a NAV Online Számla rendszerben.",
        "action": "Ellenőrizd az adószámot és hogy az érintett cég regisztrált-e a megfelelő környezetben."
    },
    "TOKEN_EXCHANGE_ERROR": {
        "title": "Token csere hiba",
        "reason": "A tokenExchange művelet nem adott vissza érvényes exchange tokent.",
        "action": "Ellenőrizd a technikai felhasználó adatait, a jogosultságokat és a tokenExchange válasz tartalmát."
    },
    "MISSING_TRANSACTION_ID": {
        "title": "Hiányzó tranzakcióazonosító",
        "reason": "A manageInvoice válaszból nem sikerült kiolvasni a transactionId értéket.",
        "action": "Ellenőrizd a manageInvoice válasz XML-t és nézd meg, hogy a NAV valóban visszaadta-e a transactionId mezőt."
    },
    "TRANSACTION_NOT_FOUND": {
        "title": "Tranzakció nem található",
        "reason": "A megadott transactionId nincs meg a NAV rendszerben, vagy még nem érhető el.",
        "action": "Ellenőrizd a transactionId értékét, és próbáld meg újra rövid késleltetés után."
    },
    "HTTP_400": {
        "title": "Hibás kérés",
        "reason": "A NAV szerint a request formailag vagy tartalmilag hibás.",
        "action": "Nézd meg a request XML-t, a namespace-eket, az errorCode mezőt és a requestSignature számítást."
    },
    "HTTP_401": {
        "title": "Hitelesítési hiba",
        "reason": "A NAV nem fogadta el a hitelesítési adatokat.",
        "action": "Ellenőrizd a technikai felhasználót, jelszót, XML kulcsokat, adószámot és a környezetet."
    },
    "HTTP_403": {
        "title": "Hozzáférés megtagadva",
        "reason": "A kéréshez nincs megfelelő jogosultság vagy a kapcsolat tiltott.",
        "action": "Ellenőrizd a technikai felhasználó jogosultságait és az adózóhoz tartozó kapcsolatot."
    },
    "HTTP_500": {
        "title": "Szerveroldali vagy kapcsolat-hiba",
        "reason": "A NAV oldalon vagy az entitáskapcsolatoknál hiba történt.",
        "action": "Ellenőrizd az errorCode mezőt, a user-taxNumber kapcsolatot és próbáld meg újra később is."
    }
}


def _find_first_text(root: ET.Element, local_name: str) -> Optional[str]:
    for elem in root.iter():
        if elem.tag.endswith(local_name):
            return elem.text
    return None


def _get_error_details(error_code: Optional[str], http_status_code: Optional[int]) -> Dict[str, Optional[str]]:
    if error_code and error_code in NAV_ERROR_MAP:
        return {
            "title": NAV_ERROR_MAP[error_code]["title"],
            "reason": NAV_ERROR_MAP[error_code]["reason"],
            "action": NAV_ERROR_MAP[error_code]["action"],
        }

    if http_status_code is not None:
        key = f"HTTP_{http_status_code}"
        if key in NAV_ERROR_MAP:
            return {
                "title": NAV_ERROR_MAP[key]["title"],
                "reason": NAV_ERROR_MAP[key]["reason"],
                "action": NAV_ERROR_MAP[key]["action"],
            }

    return {
        "title": None,
        "reason": None,
        "action": None,
    }


def parse_nav_error(xml_text: str, http_status_code: Optional[int] = None) -> Dict[str, Optional[str]]:
    result: Dict[str, Optional[str]] = {
        "func_code": None,
        "error_code": None,
        "validation_result_code": None,
        "validation_error_code": None,
        "transaction_status": None,
        "invoice_status": None,
        "message": None,
        "title": None,
        "reason": None,
        "action": None,
    }

    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
        result["func_code"] = _find_first_text(root, "funcCode")
        result["error_code"] = _find_first_text(root, "errorCode")
        result["validation_result_code"] = _find_first_text(root, "validationResultCode")
        result["validation_error_code"] = _find_first_text(root, "validationErrorCode")
        result["transaction_status"] = _find_first_text(root, "transactionStatus")
        result["invoice_status"] = _find_first_text(root, "invoiceStatus")
        result["message"] = _find_first_text(root, "message")
    except Exception:
        result["message"] = xml_text[:500] if xml_text else "Ismeretlen hibaüzenet."
        details = _get_error_details(None, http_status_code)
        result["title"] = details["title"]
        result["reason"] = details["reason"]
        result["action"] = details["action"]
        return result

    primary_error_code = result["error_code"] or result["validation_error_code"]
    details = _get_error_details(primary_error_code, http_status_code)
    result["title"] = details["title"]
    result["reason"] = details["reason"]
    result["action"] = details["action"]

    return result


def format_nav_error(xml_text: str, http_status_code: Optional[int] = None) -> str:
    parsed = parse_nav_error(xml_text, http_status_code)
    sorok: list[str] = []

    if parsed["title"]:
        sorok.append(f"NAV hiba: {parsed['title']}")
    else:
        sorok.append("NAV hiba: Ismeretlen NAV válasz")

    if parsed["func_code"]:
        sorok.append(f"Funkció kód: {parsed['func_code']}")

    if parsed["error_code"]:
        sorok.append(f"Hibakód: {parsed['error_code']}")

    if parsed["validation_result_code"]:
        sorok.append(f"Validációs eredmény: {parsed['validation_result_code']}")

    if parsed["validation_error_code"]:
        sorok.append(f"Validációs hibakód: {parsed['validation_error_code']}")

    if parsed["transaction_status"]:
        sorok.append(f"Tranzakció státusz: {parsed['transaction_status']}")

    if parsed["invoice_status"]:
        sorok.append(f"Számla státusz: {parsed['invoice_status']}")

    if parsed["message"]:
        sorok.append(f"Üzenet: {parsed['message']}")

    if parsed["reason"]:
        sorok.append(f"Lehetséges ok: {parsed['reason']}")

    if parsed["action"]:
        sorok.append(f"Javasolt lépés: {parsed['action']}")

    return "\n".join(sorok)


def extract_transaction_id(xml_text: str) -> Optional[str]:
    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
        for elem in root.iter():
            if elem.tag.endswith("transactionId"):
                return elem.text
    except Exception:
        return None
    return None


def extract_processing_summary(xml_text: str) -> str:
    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except Exception:
        return "Nem sikerült feldolgozni a NAV válasz XML-t."

    transaction_status = _find_first_text(root, "transactionStatus")
    func_code = _find_first_text(root, "funcCode")
    invoice_status = _find_first_text(root, "invoiceStatus")
    validation_result_code = _find_first_text(root, "validationResultCode")
    validation_error_code = _find_first_text(root, "validationErrorCode")
    message = _find_first_text(root, "message")

    sorok: list[str] = []

    if func_code:
        sorok.append(f"Funkció kód: {func_code}")
    if transaction_status:
        sorok.append(f"Tranzakció státusz: {transaction_status}")
    if invoice_status:
        sorok.append(f"Számla státusz: {invoice_status}")
    if validation_result_code:
        sorok.append(f"Validációs eredmény: {validation_result_code}")
    if validation_error_code:
        sorok.append(f"Validációs hibakód: {validation_error_code}")
    if message:
        sorok.append(f"Üzenet: {message}")

    if not sorok:
        return "A NAV válasz nem tartalmazott feldolgozható státusz mezőt."

    return "\n".join(sorok)