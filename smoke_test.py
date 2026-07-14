# smoke_test.py
import datetime
import os
import re

from config import NavUserConfig
from nav.eafa_api import EafaApiClient
from nav.nav_api import generate_request_id
from nav.validators import validate_user_config


def build_test_config() -> NavUserConfig:
    """
    Összeállítja a teszt konfigurációt. 
    BIZTONSÁGI JAVÍTÁS: Az adatok elsődlegesen a titkosított környezeti változókból 
    töltődnek be, így kiküszöböljük az éles kulcsok véletlen repóba kerülését.
    """
    return NavUserConfig(
        tech_user=os.getenv("NAV_TECH_USER", "IDE_A_VALODI_TECHNIKAI_FELHASZNALO"),
        password=os.getenv("NAV_PASSWORD", "IDE_A_VALODI_JELSZO"),
        sign_key=os.getenv("NAV_SIGN_KEY", "IDE_A_VALODI_SIGN_KEY"),
        exchange_key=os.getenv("NAV_EXCHANGE_KEY", "IDE_A_VALODI_EXCHANGE_KEY"),
        tax_number=os.getenv("NAV_TAX_NUMBER", "12345678"),
        environment=os.getenv("NAV_ENVIRONMENT", "TEST"),
    )


def print_block(title: str, content: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)
    print(content)


def redact_request_xml(xml_text: str) -> str:
    redacted = re.sub(
        r"(<(?:[^:>]+:)?passwordHash[^>]*>)(.*?)(</?:[^:>]+:)?passwordHash>)",
        r"\1***REDACTED***\3",
        xml_text,
        flags=re.DOTALL,
    )
    return re.sub(
        r"(<(?:[^:>]+:)?requestSignature[^>]*>)(.*?)(</?:[^:>]+:)?requestSignature>)",
        r"\1***REDACTED***\3",
        redacted,
        flags=re.DOTALL,
    )


def main() -> None:
    config = build_test_config()

    print_block("DEBUG REQUEST ID MINTA", generate_request_id())

    config_error = validate_user_config(config)
    if config_error:
        print_block("KONFIG HIBA", config_error)
        return

    client = EafaApiClient(config)

    print_block("AKTÍV KÖRNYEZET", config.environment)
    print_block("EAFA BASE URL", client.base_url)

    taxpoint_date = datetime.datetime.now().strftime("%Y-%m-%d")
    catalog_xml = client.build_query_tax_code_catalog_xml(taxpoint_date).decode("utf-8", errors="ignore")
    print_block("QUERYTAXCODECATALOG - REQUEST XML", redact_request_xml(catalog_xml)[:4000])

    upload_plan = client.create_upload_plan("<VatDeclarationData />")
    upload_xml = client.build_manage_declaration_upload_xml(upload_plan).decode("utf-8", errors="ignore")
    print_block(
        "MANAGEDECLARATIONUPLOAD - TERV",
        f"partition_count: {upload_plan.partition_count}\n"
        f"content_hash_sha3_512: {upload_plan.content_hash}\n"
        f"total_size: {upload_plan.total_size}\n"
        f"compressed_upload_size: {upload_plan.upload_size}"
    )
    print_block("MANAGEDECLARATIONUPLOAD - REQUEST XML", redact_request_xml(upload_xml)[:4000])

    print("\n[VEGE] A smoke teszt lefutott.")


if __name__ == "__main__":
    main()