from dataclasses import dataclass


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


DEFAULT_SOFTWARE = SoftwareConfig(
    software_id="123456789123456789",
    software_name="NAV M2M Ado Asszisztens",
    software_operation="LOCAL_SOFTWARE",
    software_main_version="1.0.0",
    software_dev_name="Belso Hasznalatu Fejlesztes",
    software_dev_contact="dev@company.local",
    software_dev_country_code="HU",
    software_dev_tax_number="12345678",
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