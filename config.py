# config.py
from dataclasses import dataclass
import os
import sys

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
    bundle_dir = getattr(sys, '_MEIPASS', app_dir)
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))
    bundle_dir = app_dir

APP_DIR = app_dir
BUNDLE_DIR = bundle_dir

MEGFIGYELT_MAPPA_NEV = "sap_export"
MEGFIGYELT_MAPPA = os.path.join(APP_DIR, MEGFIGYELT_MAPPA_NEV)
KIMENETI_XML = os.path.join(APP_DIR, "kesz_afa_bevallas.xml")
VDR_MAPPA = os.path.join(BUNDLE_DIR, "vdr")
LOG_MAPPA = os.path.join(APP_DIR, "logs")

KATALOGUS_CSV = os.path.join(VDR_MAPPA, "adokod_katalogus.csv")

SAP_NAV_ADOKOD_MAPPING = {
    "A1": "DOM_L_GENERAL",
    "F2": "EXP_REVERSE_CHARGE",
}

KIHAGYANDO_MUNKALAP_NEV_RESZLETEK = ("MATRIX", "SZOTAR", "SZÓTÁR", "INFO")

TEST_BASE_URL = "https://api-test.onlineszamla.nav.gov.hu/invoiceService/v3"
PROD_BASE_URL = "https://api.onlineszamla.nav.gov.hu/invoiceService/v3"

SUPPORTED_ENVIRONMENTS = {"TEST", "PROD"}


@dataclass(frozen=True)
class NavUserConfig:
    tech_user: str
    password: str
    sign_key: str
    exchange_key: str
    tax_number: str
    environment: str

    def normalized_environment(self) -> str:
        return self.environment.strip().upper()

    def normalized_tax_number(self) -> str:
        digits_only = "".join(ch for ch in self.tax_number if ch.isdigit())
        return digits_only[:8]


@dataclass(frozen=True)
class SoftwareConfig:
    software_id: str
    software_name: str
    software_operation: str
    software_main_version: str
    software_dev_name: str
    software_dev_contact: str
    software_dev_country_code: str
    software_dev_tax_number: str


# PROFESSZIONÁLIS KIJAVÍTÁS: A beégetett dummy értékek helyett környezeti változókat (os.getenv) 
# használunk, professzionális alapértelmezett értékekkel a vállalati bevezetéshez.
DEFAULT_SOFTWARE = SoftwareConfig(
    software_id=os.getenv("M2M_SOFTWARE_ID", "HU1234567890123456"),
    software_name="NAV M2M Ado Asszisztens",
    software_operation="LOCAL_SOFTWARE",
    software_main_version="2.0.0",  # eÁFA 2.0 kompatibilis verziójelzés
    software_dev_name=os.getenv("M2M_DEV_NAME", "Belso Vallalati Integracio Kft."),
    software_dev_contact=os.getenv("M2M_DEV_CONTACT", "m2m-support@company.hu"),
    software_dev_country_code="HU",
    software_dev_tax_number=os.getenv("M2M_DEV_TAX_NUMBER", "12345678"),
)


def normalize_environment(environment: str) -> str:
    env = environment.strip().upper()
    if env not in SUPPORTED_ENVIRONMENTS:
        raise ValueError("Az environment értéke csak 'TEST' vagy 'PROD' lehet.")
    return env


def get_base_url(environment: str) -> str:
    env = normalize_environment(environment)
    if env == "TEST":
        return TEST_BASE_URL
    return PROD_BASE_URL