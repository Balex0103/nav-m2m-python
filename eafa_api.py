from __future__ import annotations

import hashlib
import gzip
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Optional

import requests
from requests import Response, Session

from config import DEFAULT_SOFTWARE, NavUserConfig, SoftwareConfig
from nav_api import generate_request_id, generate_timestamp, password_hash, request_signature


NS_EAR_API = "http://schemas.nav.gov.hu/EAR/1.0/api"
NS_EAR_BASE = "http://schemas.nav.gov.hu/EAR/1.0/base"
NS_EAR_DATA = "http://schemas.nav.gov.hu/EAR/1.0/data"
NS_COMMON = "http://schemas.nav.gov.hu/NTCA/1.0/common"

EafaEnvironment = str

TEST_BASE_URL = "https://api-test.eafa.nav.gov.hu/v1/xmlapi"
PROD_BASE_URL = "https://api.eafa.nav.gov.hu/v1/xmlapi"

DEFAULT_PARTITION_SIZE_BYTES = 128 * 1024 * 1024

ET.register_namespace("", NS_EAR_API)
ET.register_namespace("common", NS_COMMON)
ET.register_namespace("earbase", NS_EAR_BASE)
ET.register_namespace("eardata", NS_EAR_DATA)


def _q(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


def get_eafa_base_url(environment: EafaEnvironment) -> str:
    env = environment.strip().upper()
    if env == "TEST":
        return TEST_BASE_URL
    if env == "PROD":
        return PROD_BASE_URL
    raise ValueError("Az eÁFA környezet csak TEST vagy PROD lehet.")


def sha3_512_hex(data: bytes) -> str:
    return hashlib.sha3_512(data).hexdigest().upper()


def extract_first_tag_value(xml_text: str, tag_name: str) -> Optional[str]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    for elem in root.iter():
        if elem.tag.endswith(tag_name):
            return elem.text

    return None


def is_business_success(xml_text: str) -> bool:
    func_code = extract_first_tag_value(xml_text, "funcCode")
    if func_code is None:
        return False
    return func_code.strip().upper() == "OK"


def split_partitions(data: bytes, partition_size: int = DEFAULT_PARTITION_SIZE_BYTES) -> list[bytes]:
    if partition_size <= 0:
        raise ValueError("A partícióméretnek pozitív egésznek kell lennie.")
    if not data:
        return [b""]
    return [data[index:index + partition_size] for index in range(0, len(data), partition_size)]


@dataclass(frozen=True)
class EafaUploadPlan:
    declaration_bytes: bytes
    upload_bytes: bytes
    partition_size: int
    partitions: list[bytes]
    content_hash: str
    declaration_schema: str = "VAT_DECLARATION"

    @property
    def partition_count(self) -> int:
        return len(self.partitions)

    @property
    def total_size(self) -> int:
        return len(self.declaration_bytes)

    @property
    def upload_size(self) -> int:
        return len(self.upload_bytes)


class EafaApiClient:
    """Client for the NAV eÁFA XML API.

    This is intentionally separate from the Online Számla OSA client. eÁFA uses
    EAR request/response schemas and declaration upload operations instead of
    OSA invoice operations.
    """

    def __init__(
        self,
        user_config: NavUserConfig,
        software_config: Optional[SoftwareConfig] = None,
        timeout: int = 30,
    ) -> None:
        self.user = user_config
        self.software = software_config or DEFAULT_SOFTWARE
        self.base_url = get_eafa_base_url(user_config.environment).rstrip("/")
        self.timeout = timeout
        self.session: Session = requests.Session()
        self.last_request: Optional[dict[str, Any]] = None
        self.last_response: Optional[dict[str, Any]] = None

    def create_upload_plan(
        self,
        declaration_xml_text: str,
        partition_size: int = DEFAULT_PARTITION_SIZE_BYTES,
    ) -> EafaUploadPlan:
        declaration_bytes = declaration_xml_text.encode("utf-8")
        upload_bytes = gzip.compress(declaration_bytes)
        partitions = split_partitions(upload_bytes, partition_size)
        return EafaUploadPlan(
            declaration_bytes=declaration_bytes,
            upload_bytes=upload_bytes,
            partition_size=partition_size,
            partitions=partitions,
            content_hash=sha3_512_hex(declaration_bytes),
        )

    def _append_common_header(self, parent: ET.Element, request_id: str, timestamp: str) -> None:
        header = ET.SubElement(parent, _q(NS_COMMON, "header"))
        ET.SubElement(header, _q(NS_COMMON, "requestId")).text = request_id
        ET.SubElement(header, _q(NS_COMMON, "timestamp")).text = timestamp
        ET.SubElement(header, _q(NS_COMMON, "requestVersion")).text = "2.0"
        ET.SubElement(header, _q(NS_COMMON, "headerVersion")).text = "1.0"

    def _append_user(self, parent: ET.Element, request_id: str, timestamp: str) -> None:
        user = ET.SubElement(parent, _q(NS_COMMON, "user"))
        ET.SubElement(user, _q(NS_COMMON, "login")).text = self.user.tech_user

        password_hash_node = ET.SubElement(user, _q(NS_COMMON, "passwordHash"))
        password_hash_node.set("cryptoType", "SHA-512")
        password_hash_node.text = password_hash(self.user.password)

        ET.SubElement(user, _q(NS_COMMON, "taxNumber")).text = self.user.normalized_tax_number()

        signature_node = ET.SubElement(user, _q(NS_COMMON, "requestSignature"))
        signature_node.set("cryptoType", "SHA3-512")
        signature_node.text = request_signature(request_id, timestamp, self.user.sign_key)

    def _append_software(self, parent: ET.Element) -> None:
        software = ET.SubElement(parent, _q(NS_EAR_API, "software"))
        ET.SubElement(software, _q(NS_EAR_API, "softwareId")).text = self.software.software_id
        ET.SubElement(software, _q(NS_EAR_API, "softwareName")).text = self.software.software_name
        ET.SubElement(software, _q(NS_EAR_API, "softwareOperation")).text = self.software.software_operation
        ET.SubElement(software, _q(NS_EAR_API, "softwareMainVersion")).text = self.software.software_main_version
        ET.SubElement(software, _q(NS_EAR_API, "softwareDevName")).text = self.software.software_dev_name
        ET.SubElement(software, _q(NS_EAR_API, "softwareDevContact")).text = self.software.software_dev_contact
        ET.SubElement(software, _q(NS_EAR_API, "softwareDevCountryCode")).text = self.software.software_dev_country_code
        ET.SubElement(software, _q(NS_EAR_API, "softwareDevTaxNumber")).text = self.software.software_dev_tax_number

    def _request_root(self, root_name: str) -> ET.Element:
        request_id = generate_request_id()
        timestamp = generate_timestamp()
        root = ET.Element(_q(NS_EAR_API, root_name))
        self._append_common_header(root, request_id, timestamp)
        self._append_user(root, request_id, timestamp)
        self._append_software(root)
        return root

    def _xml_to_bytes(self, root: ET.Element) -> bytes:
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    def _append_crypto_hash(self, parent: ET.Element, tag_name: str, value: str, crypto_type: str = "SHA3-512") -> None:
        node = ET.SubElement(parent, _q(NS_EAR_API, tag_name))
        node.set("cryptoType", crypto_type)
        node.text = value

    def build_query_tax_code_catalog_xml(self, taxpoint_date: str) -> bytes:
        root = self._request_root("QueryTaxCodeCatalogRequest")
        ET.SubElement(root, _q(NS_EAR_API, "taxpointDate")).text = taxpoint_date
        return self._xml_to_bytes(root)

    def build_manage_declaration_upload_xml(self, plan: EafaUploadPlan) -> bytes:
        root = self._request_root("ManageDeclarationUploadRequest")
        ET.SubElement(root, _q(NS_EAR_API, "partitionCount")).text = str(plan.partition_count)
        self._append_crypto_hash(root, "contentHash", plan.content_hash)
        ET.SubElement(root, _q(NS_EAR_API, "declarationSchema")).text = plan.declaration_schema
        return self._xml_to_bytes(root)

    def build_manage_declaration_partition_xml(
        self,
        declaration_upload_id: str,
        partition: int,
    ) -> bytes:
        root = self._request_root("ManageDeclarationPartitionRequest")
        ET.SubElement(root, _q(NS_EAR_API, "declarationUploadId")).text = declaration_upload_id
        ET.SubElement(root, _q(NS_EAR_API, "partition")).text = str(partition)
        return self._xml_to_bytes(root)

    def build_manage_declaration_finalize_xml(
        self,
        declaration_upload_id: str,
        preliminary_confirmation: bool = False,
    ) -> bytes:
        root = self._request_root("ManageDeclarationFinalizeRequest")
        ET.SubElement(root, _q(NS_EAR_API, "declarationUploadId")).text = declaration_upload_id
        ET.SubElement(root, _q(NS_EAR_API, "preliminaryConfirmation")).text = str(preliminary_confirmation).lower()
        return self._xml_to_bytes(root)

    def build_query_declaration_processing_status_xml(self, declaration_processing_id: str) -> bytes:
        root = self._request_root("QueryDeclarationProcessingStatusRequest")
        ET.SubElement(root, _q(NS_EAR_API, "declarationProcessingId")).text = declaration_processing_id
        return self._xml_to_bytes(root)

    def build_manage_declaration_submission_xml(self, declaration_processing_id: str) -> bytes:
        root = self._request_root("ManageDeclarationSubmissionRequest")
        ET.SubElement(root, _q(NS_EAR_API, "declarationProcessingId")).text = declaration_processing_id
        return self._xml_to_bytes(root)

    def _post_xml(self, endpoint: str, xml_bytes: bytes) -> dict[str, Any]:
        url = f"{self.base_url}/analyticsService/v1/{endpoint}"
        headers = {
            "Content-Type": "application/xml",
            "Accept": "application/xml",
        }
        request_body = xml_bytes.decode("utf-8", errors="ignore")
        self.last_request = {"url": url, "body": request_body}

        try:
            response: Response = self.session.post(
                url,
                data=xml_bytes,
                headers=headers,
                timeout=self.timeout,
            )
            self.last_response = {"status_code": response.status_code, "body": response.text}
            success = response.ok and is_business_success(response.text)
            return {
                "success": success,
                "status_code": response.status_code,
                "text": response.text,
                "request_url": url,
                "request_body": request_body,
            }
        except requests.RequestException as exc:
            self.last_response = {"status_code": None, "body": str(exc)}
            return {
                "success": False,
                "status_code": None,
                "text": str(exc),
                "request_url": url,
                "request_body": request_body,
            }

    def _post_multipart(self, endpoint: str, request_xml: bytes, content: bytes) -> dict[str, Any]:
        url = f"{self.base_url}/analyticsService/v1/{endpoint}"
        request_body = request_xml.decode("utf-8", errors="ignore")
        files = {
            "request": ("request.xml", request_xml, "application/xml"),
            "content": ("declaration-part.xml", content, "application/octet-stream"),
        }
        self.last_request = {
            "url": url,
            "body": request_body,
            "content_size": len(content),
        }

        try:
            response: Response = self.session.post(url, files=files, timeout=self.timeout)
            self.last_response = {"status_code": response.status_code, "body": response.text}
            success = response.ok and is_business_success(response.text)
            return {
                "success": success,
                "status_code": response.status_code,
                "text": response.text,
                "request_url": url,
                "request_body": request_body,
                "content_size": len(content),
            }
        except requests.RequestException as exc:
            self.last_response = {"status_code": None, "body": str(exc)}
            return {
                "success": False,
                "status_code": None,
                "text": str(exc),
                "request_url": url,
                "request_body": request_body,
                "content_size": len(content),
            }

    def query_tax_code_catalog(self, taxpoint_date: str) -> dict[str, Any]:
        return self._post_xml("queryTaxCodeCatalog", self.build_query_tax_code_catalog_xml(taxpoint_date))

    def manage_declaration_upload(self, plan: EafaUploadPlan) -> dict[str, Any]:
        return self._post_xml("manageDeclarationUpload", self.build_manage_declaration_upload_xml(plan))

    def manage_declaration_partition(
        self,
        declaration_upload_id: str,
        partition_number: int,
        partition_content: bytes,
    ) -> dict[str, Any]:
        request_xml = self.build_manage_declaration_partition_xml(declaration_upload_id, partition_number)
        return self._post_multipart("manageDeclarationPartition", request_xml, partition_content)

    def manage_declaration_finalize(
        self,
        declaration_upload_id: str,
        preliminary_confirmation: bool = False,
    ) -> dict[str, Any]:
        request_xml = self.build_manage_declaration_finalize_xml(declaration_upload_id, preliminary_confirmation)
        return self._post_xml("manageDeclarationFinalize", request_xml)

    def query_declaration_processing_status(self, declaration_processing_id: str) -> dict[str, Any]:
        request_xml = self.build_query_declaration_processing_status_xml(declaration_processing_id)
        return self._post_xml("queryDeclarationProcessingStatus", request_xml)

    def manage_declaration_submission(self, declaration_processing_id: str) -> dict[str, Any]:
        request_xml = self.build_manage_declaration_submission_xml(declaration_processing_id)
        return self._post_xml("manageDeclarationSubmission", request_xml)


def estimate_partition_count(byte_size: int, partition_size: int = DEFAULT_PARTITION_SIZE_BYTES) -> int:
    if byte_size <= 0:
        return 1
    return max(1, math.ceil(byte_size / partition_size))
