import base64
import datetime
import gzip
import hashlib
import random
import string
import xml.etree.ElementTree as ET
from typing import Any, Optional

import requests
from requests import Response, Session

from config import DEFAULT_SOFTWARE, NavUserConfig, SoftwareConfig, get_base_url


NS_API = "http://schemas.nav.gov.hu/OSA/3.0/api"
NS_BASE = "http://schemas.nav.gov.hu/OSA/3.0/base"
NS_DATA = "http://schemas.nav.gov.hu/OSA/3.0/data"
NS_COMMON = "http://schemas.nav.gov.hu/NTCA/1.0/common"

ET.register_namespace("", NS_API)
ET.register_namespace("common", NS_COMMON)
ET.register_namespace("base", NS_BASE)
ET.register_namespace("data", NS_DATA)


def _q(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


def generate_request_id() -> str:
    random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=15))
    return f"M2M_{random_part}"


def generate_timestamp() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def password_hash(password: str) -> str:
    return hashlib.sha512(password.encode("utf-8")).hexdigest().upper()


def request_signature(request_id: str, timestamp: str, sign_key: str) -> str:
    payload = request_id + timestamp + sign_key
    return hashlib.sha3_512(payload.encode("utf-8")).hexdigest().upper()


def _extract_first_tag_value(xml_text: str, tag_name: str) -> Optional[str]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    for elem in root.iter():
        if elem.tag.endswith(tag_name):
            return elem.text

    return None


def _looks_like_osa_invoice_data(xml_text: str) -> bool:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return False

    root_tag = root.tag.lower()
    if "vatdeclarationdata" in root_tag:
        return False

    data_tags = {elem.tag.lower() for elem in root.iter()}
    invoice_related_markers = (
        "invoicenumber",
        "invoicedetail",
        "invoicehead",
        "invoicelines",
        "invoicesummary",
    )

    return any(marker in tag for marker in invoice_related_markers for tag in data_tags)


class NavApiClient:
    def __init__(
        self,
        user_config: NavUserConfig,
        software_config: Optional[SoftwareConfig] = None,
        timeout: int = 30,
    ) -> None:
        self.user = user_config
        self.software = software_config or DEFAULT_SOFTWARE
        self.base_url = get_base_url(user_config.environment).rstrip("/")
        self.timeout = timeout
        self.session: Session = requests.Session()
        self.last_request: Optional[dict[str, Any]] = None
        self.last_response: Optional[dict[str, Any]] = None

    def _common_header_values(self) -> tuple[str, str]:
        request_id = generate_request_id()
        timestamp = generate_timestamp()
        return request_id, timestamp

    def _append_common_header(self, parent: ET.Element, request_id: str, timestamp: str) -> None:
        header = ET.SubElement(parent, _q(NS_COMMON, "header"))
        ET.SubElement(header, _q(NS_COMMON, "requestId")).text = request_id
        ET.SubElement(header, _q(NS_COMMON, "timestamp")).text = timestamp
        ET.SubElement(header, _q(NS_COMMON, "requestVersion")).text = "3.0"
        ET.SubElement(header, _q(NS_COMMON, "headerVersion")).text = "1.0"

    def _append_user(self, parent: ET.Element, request_id: str, timestamp: str) -> None:
        user = ET.SubElement(parent, _q(NS_COMMON, "user"))
        ET.SubElement(user, _q(NS_COMMON, "login")).text = self.user.tech_user

        password_hash_node = ET.SubElement(user, _q(NS_COMMON, "passwordHash"))
        password_hash_node.set("cryptoType", "SHA-512")
        password_hash_node.text = password_hash(self.user.password)

        ET.SubElement(user, _q(NS_COMMON, "taxNumber")).text = self.user.tax_number

        signature_node = ET.SubElement(user, _q(NS_COMMON, "requestSignature"))
        signature_node.set("cryptoType", "SHA3-512")
        signature_node.text = request_signature(request_id, timestamp, self.user.sign_key)

    def _append_software(self, parent: ET.Element) -> None:
        software = ET.SubElement(parent, _q(NS_API, "software"))
        ET.SubElement(software, _q(NS_API, "softwareId")).text = self.software.software_id
        ET.SubElement(software, _q(NS_API, "softwareName")).text = self.software.software_name
        ET.SubElement(software, _q(NS_API, "softwareOperation")).text = self.software.software_operation
        ET.SubElement(software, _q(NS_API, "softwareMainVersion")).text = self.software.software_main_version
        ET.SubElement(software, _q(NS_API, "softwareDevName")).text = self.software.software_dev_name
        ET.SubElement(software, _q(NS_API, "softwareDevContact")).text = self.software.software_dev_contact
        ET.SubElement(software, _q(NS_API, "softwareDevCountryCode")).text = self.software.software_dev_country_code
        ET.SubElement(software, _q(NS_API, "softwareDevTaxNumber")).text = self.software.software_dev_tax_number

    def _xml_to_bytes(self, root: ET.Element) -> bytes:
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    def _post_xml(self, endpoint: str, xml_bytes: bytes) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Content-Type": "application/xml",
            "Accept": "application/xml",
        }

        request_body = xml_bytes.decode("utf-8", errors="ignore")
        self.last_request = {
            "url": url,
            "body": request_body,
        }

        try:
            response: Response = self.session.post(
                url,
                data=xml_bytes,
                headers=headers,
                timeout=self.timeout,
            )

            self.last_response = {
                "status_code": response.status_code,
                "body": response.text,
            }

            return {
                "success": response.ok,
                "status_code": response.status_code,
                "text": response.text,
                "request_url": url,
                "request_body": request_body,
            }

        except requests.RequestException as exc:
            self.last_response = {
                "status_code": None,
                "body": str(exc),
            }

            return {
                "success": False,
                "status_code": None,
                "text": str(exc),
                "request_url": url,
                "request_body": request_body,
            }

    def build_token_exchange_xml(self) -> bytes:
        request_id, timestamp = self._common_header_values()

        root = ET.Element(_q(NS_API, "TokenExchangeRequest"))
        self._append_common_header(root, request_id, timestamp)
        self._append_user(root, request_id, timestamp)
        self._append_software(root)

        return self._xml_to_bytes(root)

    def token_exchange(self) -> dict[str, Any]:
        xml_bytes = self.build_token_exchange_xml()
        return self._post_xml("tokenExchange", xml_bytes)

    def build_query_taxpayer_xml(self, tax_number: str) -> bytes:
        request_id, timestamp = self._common_header_values()

        root = ET.Element(_q(NS_API, "QueryTaxpayerRequest"))
        self._append_common_header(root, request_id, timestamp)
        self._append_user(root, request_id, timestamp)
        self._append_software(root)
        ET.SubElement(root, _q(NS_API, "taxNumber")).text = tax_number

        return self._xml_to_bytes(root)

    def query_taxpayer(self, tax_number: str) -> dict[str, Any]:
        xml_bytes = self.build_query_taxpayer_xml(tax_number)
        return self._post_xml("queryTaxpayer", xml_bytes)

    def build_manage_invoice_xml(
        self,
        invoice_xml_text: str,
        operation: str = "CREATE",
        compressed: bool = True,
        exchange_token: str = "",
    ) -> bytes:
        request_id, timestamp = self._common_header_values()

        root = ET.Element(_q(NS_API, "ManageInvoiceRequest"))
        self._append_common_header(root, request_id, timestamp)
        self._append_user(root, request_id, timestamp)
        ET.SubElement(root, _q(NS_API, "exchangeToken")).text = exchange_token
        self._append_software(root)

        invoice_operations = ET.SubElement(
            root,
            _q(NS_API, "invoiceOperations"),
            attrib={"compressedContent": str(compressed).lower()},
        )

        invoice_operation = ET.SubElement(
            invoice_operations,
            _q(NS_API, "invoiceOperation"),
            attrib={"index": "1", "operation": operation},
        )

        invoice_data = ET.SubElement(invoice_operation, _q(NS_API, "invoiceData"))

        raw_bytes = invoice_xml_text.encode("utf-8")
        payload = gzip.compress(raw_bytes) if compressed else raw_bytes
        invoice_data.text = base64.b64encode(payload).decode("ascii")

        return self._xml_to_bytes(root)

    def manage_invoice(self, invoice_xml_text: str, operation: str = "CREATE") -> dict[str, Any]:
        if not _looks_like_osa_invoice_data(invoice_xml_text):
            return {
                "success": False,
                "status_code": None,
                "text": (
                    "A megadott XML nem tűnik OSA 3.0 invoiceData típusú számla XML-nek. "
                    "A jelenlegi XML valószínűleg EAR vagy eÁFA adatexport, ezért manageInvoice művelettel nem küldhető be."
                ),
                "request_url": f"{self.base_url}/manageInvoice",
                "request_body": invoice_xml_text[:1500],
            }

        token_result = self.token_exchange()
        if not token_result.get("success"):
            return {
                "success": False,
                "status_code": token_result.get("status_code"),
                "text": token_result.get("text", ""),
                "request_url": token_result.get("request_url"),
                "request_body": token_result.get("request_body"),
            }

        token_response_text = str(token_result.get("text", ""))
        exchange_token = _extract_first_tag_value(token_response_text, "encodedExchangeToken")

        if not exchange_token:
            return {
                "success": False,
                "status_code": token_result.get("status_code"),
                "text": "Nem található encodedExchangeToken a tokenExchange válaszban.",
                "request_url": token_result.get("request_url"),
                "request_body": token_result.get("request_body"),
            }

        xml_bytes = self.build_manage_invoice_xml(
            invoice_xml_text=invoice_xml_text,
            operation=operation,
            compressed=True,
            exchange_token=exchange_token,
        )
        return self._post_xml("manageInvoice", xml_bytes)

    def build_query_invoice_data_xml(
        self,
        invoice_number: str,
        invoice_direction: str = "OUTBOUND",
    ) -> bytes:
        request_id, timestamp = self._common_header_values()

        root = ET.Element(_q(NS_API, "QueryInvoiceDataRequest"))
        self._append_common_header(root, request_id, timestamp)
        self._append_user(root, request_id, timestamp)
        self._append_software(root)

        invoice_number_query = ET.SubElement(root, _q(NS_API, "invoiceNumberQuery"))
        ET.SubElement(invoice_number_query, _q(NS_BASE, "invoiceNumber")).text = invoice_number
        ET.SubElement(invoice_number_query, _q(NS_BASE, "invoiceDirection")).text = invoice_direction

        return self._xml_to_bytes(root)

    def query_invoice_data(
        self,
        invoice_number: str,
        invoice_direction: str = "OUTBOUND",
    ) -> dict[str, Any]:
        xml_bytes = self.build_query_invoice_data_xml(invoice_number, invoice_direction)
        return self._post_xml("queryInvoiceData", xml_bytes)

    def build_query_transaction_status_xml(
        self,
        transaction_id: str,
        return_original_request: bool = False,
    ) -> bytes:
        request_id, timestamp = self._common_header_values()

        root = ET.Element(_q(NS_API, "QueryTransactionStatusRequest"))
        self._append_common_header(root, request_id, timestamp)
        self._append_user(root, request_id, timestamp)
        self._append_software(root)

        ET.SubElement(root, _q(NS_API, "transactionId")).text = transaction_id
        ET.SubElement(root, _q(NS_API, "returnOriginalRequest")).text = str(return_original_request).lower()

        return self._xml_to_bytes(root)

    def query_transaction_status(
        self,
        transaction_id: str,
        return_original_request: bool = False,
    ) -> dict[str, Any]:
        xml_bytes = self.build_query_transaction_status_xml(transaction_id, return_original_request)
        return self._post_xml("queryTransactionStatus", xml_bytes)