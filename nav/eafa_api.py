# nav/eafa_api.py
# eÁFA M2M API kliens — a meglévő EafaApiClient teljes megőrzésével.
# Az eredeti main.py logikájából kiemelve, semmi nem változott funkcionálisan.
# Forrás: eVAT GitHub repo + NAV eÁFA v2.0 specifikáció

from __future__ import annotations

import hashlib
import math
import re
import uuid
import datetime
from datetime import timezone
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

from config import NavUserConfig

# --- URL konstansok ---
TEST_BASE_URL = "https://api-test.eafa.nav.gov.hu/v2/xmlapi/"
PROD_BASE_URL = "https://api.eafa.nav.gov.hu/v2/xmlapi/"

# Partíció méret: 1 MB
PARTITION_SIZE = 1024 * 1024


def extract_first_tag_value(
    xml_text: str,
    *tag_names: str,
) -> Optional[str]:
    """
    Megkeresi az első előforduló XML tag értékét a megadott tagnevek közül.
    Névtér-független keresés.

    Példa:
        extract_first_tag_value(xml, "declarationUploadId", "declarationProcessingId")
    """
    for tag in tag_names:
        pattern = rf"<(?:[^:>]+:)?{re.escape(tag)}[^>]*>(.*?)</(?:[^:>]+:)?{re.escape(tag)}>"
        match = re.search(pattern, xml_text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return None


@dataclass
class UploadPlan:
    """Feltöltési terv — a manageDeclarationUpload előkészítéséhez."""
    xml_content:      bytes
    content_hash:     str
    total_size:       int
    upload_size:      int
    partition_count:  int
    partitions:       list[bytes] = field(default_factory=list)


class EafaApiClient:
    """
    NAV eÁFA M2M API kliens v2.0.
    Kezeli az XML bevallás feltöltési folyamatát:
      1. queryTaxCodeCatalog  — adókód katalógus lekérdezés
      2. manageDeclarationUpload   — feltöltés indítása
      3. manageDeclarationPartition — partíciók feltöltése
      4. manageDeclarationFinalize  — lezárás

    Példa:
        client = EafaApiClient(config)
        plan   = client.create_upload_plan(xml_str)
        result = client.manage_declaration_upload(plan)
    """

    def __init__(self, config: NavUserConfig) -> None:
        self.config = config
        env = getattr(config, "environment", "TEST").upper()
        self.base_url = PROD_BASE_URL if env == "PROD" else TEST_BASE_URL
        self.timeout  = 30

    # ------------------------------------------------------------------
    # Publikus: feltöltési terv
    # ------------------------------------------------------------------

    def create_upload_plan(self, xml_content: str) -> UploadPlan:
        """
        Elkészíti a feltöltési tervet az XML tartalom alapján.
        Kiszámítja a SHA3-512 hash-t, a partíciókat és a méreteket.
        """
        raw_bytes   = xml_content.encode("utf-8")
        compressed  = raw_bytes          # tömörítés nélkül ebben a verzióban
        hash_hex    = hashlib.sha3_512(raw_bytes).hexdigest()
        total_size  = len(raw_bytes)
        upload_size = len(compressed)
        part_count  = math.ceil(upload_size / PARTITION_SIZE) or 1
        partitions  = [
            compressed[i * PARTITION_SIZE:(i + 1) * PARTITION_SIZE]
            for i in range(part_count)
        ]
        return UploadPlan(
            xml_content     = raw_bytes,
            content_hash    = hash_hex,
            total_size      = total_size,
            upload_size     = upload_size,
            partition_count = part_count,
            partitions      = partitions,
        )

    # ------------------------------------------------------------------
    # Publikus: XML kérés építők
    # ------------------------------------------------------------------

    def build_query_tax_code_catalog_xml(self, taxpoint_date: str) -> bytes:
        """
        Összeállítja a queryTaxCodeCatalog kérés XML-jét.
        taxpoint_date formátum: YYYY-MM-DD
        """
        message_id  = str(uuid.uuid4()).replace("-", "").upper()[:32]
        timestamp   = datetime.datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        sign_key    = getattr(self.config, "sign_key",    "PLACEHOLDER_SIGNKEY")
        tech_user   = getattr(self.config, "tech_user",   "PLACEHOLDER_TECHUSER")
        tax_number  = getattr(self.config, "tax_number",  "00000000")

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<QueryTaxCodeCatalogRequest xmlns="http://schemas.nav.gov.hu/EAFA/2.0">
  <header>
    <messageId>{message_id}</messageId>
    <timestamp>{timestamp}</timestamp>
    <requestVersion>2.0</requestVersion>
    <headerVersion>1.0</headerVersion>
  </header>
  <user>
    ogin>{tech_user}</login>
    <passwordHash cryptoType="SHA3-512">{self._sha3(getattr(self.config,"password",""))}</passwordHash>
    <taxNumber>{tax_number[:8]}</taxNumber>
    <requestSignature cryptoType="SHA3-512">{self._request_signature(message_id, timestamp, sign_key)}</requestSignature>
  </user>
  <software>
    <softwareId>NAV-M2M-KLIENS-001</softwareId>
    <softwareName>NAV M2M Kliens</softwareName>
    <softwareOperation>LOCAL_SOFTWARE</softwareOperation>
    <softwareMainVersion>2.0</softwareMainVersion>
    <softwareDevName>M2M Fejleszto</softwareDevName>
    <softwareDevContact>nav.m2m@example.hu</softwareDevContact>
    <softwareDevCountryCode>HU</softwareDevCountryCode>
    <softwareDevTaxNumber>00000000</softwareDevTaxNumber>
  </software>
  <queryInput>
    <taxpointDate>{taxpoint_date}</taxpointDate>
  </queryInput>
</QueryTaxCodeCatalogRequest>"""
        return xml.encode("utf-8")

    def build_manage_declaration_upload_xml(self, plan: UploadPlan) -> bytes:
        """
        Összeállítja a manageDeclarationUpload kérés XML-jét.
        """
        message_id  = str(uuid.uuid4()).replace("-", "").upper()[:32]
        timestamp   = datetime.datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        sign_key    = getattr(self.config, "sign_key",    "PLACEHOLDER_SIGNKEY")
        tech_user   = getattr(self.config, "tech_user",   "PLACEHOLDER_TECHUSER")
        tax_number  = getattr(self.config, "tax_number",  "00000000")

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ManageDeclarationUploadRequest xmlns="http://schemas.nav.gov.hu/EAFA/2.0">
  <header>
    <messageId>{message_id}</messageId>
    <timestamp>{timestamp}</timestamp>
    <requestVersion>2.0</requestVersion>
    <headerVersion>1.0</headerVersion>
  </header>
  <user>
    ogin>{tech_user}</login>
    <passwordHash cryptoType="SHA3-512">{self._sha3(getattr(self.config,"password",""))}</passwordHash>
    <taxNumber>{tax_number[:8]}</taxNumber>
    <requestSignature cryptoType="SHA3-512">{self._request_signature(message_id, timestamp, sign_key)}</requestSignature>
  </user>
  <software>
    <softwareId>NAV-M2M-KLIENS-001</softwareId>
    <softwareName>NAV M2M Kliens</softwareName>
    <softwareOperation>LOCAL_SOFTWARE</softwareOperation>
    <softwareMainVersion>2.0</softwareMainVersion>
    <softwareDevName>M2M Fejleszto</softwareDevName>
    <softwareDevContact>nav.m2m@example.hu</softwareDevContact>
    <softwareDevCountryCode>HU</softwareDevCountryCode>
    <softwareDevTaxNumber>00000000</softwareDevTaxNumber>
  </software>
  <declarationUpload>
    tentHash cryptoType="SHA3-512">{plan.content_hash}</contentHash>
    <totalSize>{plan.total_size}</totalSize>
    <uploadSize>{plan.upload_size}</uploadSize>
    <partitionCount>{plan.partition_count}</partitionCount>
  </declarationUpload>
</ManageDeclarationUploadRequest>"""
        return xml.encode("utf-8")

    # ------------------------------------------------------------------
    # Publikus: hálózati hívások
    # ------------------------------------------------------------------

    def query_tax_code_catalog(self, taxpoint_date: str) -> dict[str, Any]:
        """
        POST analytics-Service/v1/queryTaxCodeCatalog
        Adókód katalógus lekérdezés — kapcsolat teszt célra is használható.
        """
        url = f"{self.base_url}analyticsService/v1/queryTaxCodeCatalog"
        xml_body = self.build_query_tax_code_catalog_xml(taxpoint_date)
        return self._post(url, xml_body)

    def manage_declaration_upload(self, plan: UploadPlan) -> dict[str, Any]:
        """
        POST analyticsService/v1/manageDeclarationUpload
        Feltöltés indítása — visszaadja a declarationUploadId-t.
        """
        url      = f"{self.base_url}analyticsService/v1/manageDeclarationUpload"
        xml_body = self.build_manage_declaration_upload_xml(plan)
        return self._post(url, xml_body)

    def manage_declaration_partition(
        self,
        declaration_upload_id: str,
        partition_index: int,
        partition_bytes: bytes,
    ) -> dict[str, Any]:
        """
        POST analyticsService/v1/manageDeclarationPartition
        Egy partíció feltöltése.
        """
        import base64
        message_id = str(uuid.uuid4()).replace("-", "").upper()[:32]
        timestamp  = datetime.datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        sign_key   = getattr(self.config, "sign_key",   "PLACEHOLDER_SIGNKEY")
        tech_user  = getattr(self.config, "tech_user",  "PLACEHOLDER_TECHUSER")
        tax_number = getattr(self.config, "tax_number", "00000000")

        part_b64 = base64.b64encode(partition_bytes).decode("ascii")
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ManageDeclarationPartitionRequest xmlns="http://schemas.nav.gov.hu/EAFA/2.0">
  <header>
    <messageId>{message_id}</messageId>
    <timestamp>{timestamp}</timestamp>
    <requestVersion>2.0</requestVersion>
    <headerVersion>1.0</headerVersion>
  </header>
  <user>
    ogin>{tech_user}</login>
    <passwordHash cryptoType="SHA3-512">{self._sha3(getattr(self.config,"password",""))}</passwordHash>
    <taxNumber>{tax_number[:8]}</taxNumber>
    <requestSignature cryptoType="SHA3-512">{self._request_signature(message_id, timestamp, sign_key)}</requestSignature>
  </user>
  <declarationPartition>
    <declarationUploadId>{declaration_upload_id}</declarationUploadId>
    <partitionIndex>{partition_index}</partitionIndex>
    <partitionData>{part_b64}</partitionData>
  </declarationPartition>
</ManageDeclarationPartitionRequest>"""
        url = f"{self.base_url}analyticsService/v1/manageDeclarationPartition"
        return self._post(url, xml.encode("utf-8"))

    def manage_declaration_finalize(
        self,
        declaration_upload_id: str,
        preliminary_confirmation: bool = False,
    ) -> dict[str, Any]:
        """
        POST analyticsService/v1/manageDeclarationFinalize
        Feltöltés lezárása.
        """
        message_id  = str(uuid.uuid4()).replace("-", "").upper()[:32]
        timestamp   = datetime.datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        sign_key    = getattr(self.config, "sign_key",   "PLACEHOLDER_SIGNKEY")
        tech_user   = getattr(self.config, "tech_user",  "PLACEHOLDER_TECHUSER")
        tax_number  = getattr(self.config, "tax_number", "00000000")
        prelim      = "true" if preliminary_confirmation else "false"

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ManageDeclarationFinalizeRequest xmlns="http://schemas.nav.gov.hu/EAFA/2.0">
  <header>
    <messageId>{message_id}</messageId>
    <timestamp>{timestamp}</timestamp>
    <requestVersion>2.0</requestVersion>
    <headerVersion>1.0</headerVersion>
  </header>
  <user>
    <login>{tech_user}</login>
    <passwordHash cryptoType="SHA3-512">{self._sha3(getattr(self.config,"password",""))}</passwordHash>
    <taxNumber>{tax_number[:8]}</taxNumber>
    <requestSignature cryptoType="SHA3-512">{self._request_signature(message_id, timestamp, sign_key)}</requestSignature>
  </user>
  <declarationFinalize>
    <declarationUploadId>{declaration_upload_id}</declarationUploadId>
    <preliminaryConfirmation>{prelim}</preliminaryConfirmation>
  </declarationFinalize>
</ManageDeclarationFinalizeRequest>"""
        url = f"{self.base_url}manageDeclarationFinalize"
        return self._post(url, xml)

    # ------------------------------------------------------------------
    # Privát segédfüggvények
    # ------------------------------------------------------------------

    def _sha3(self, msg: str) -> str:
        """SHA3-512 hashelés."""
        return hashlib.sha3_512(msg.encode()).hexdigest().upper()

    def _request_signature(self, message_id: str, timestamp: str, sign_key: str) -> str:
        """Általános request signature."""
        msg = f"{message_id}{timestamp}{sign_key}"
        return self._sha3(msg)

    def _post(self, url: str, xml_body: str | bytes) -> dict[str, Any]:
        """POST kérés XML testtel."""
        if isinstance(xml_body, str):
            xml_body = xml_body.encode("utf-8")
        resp = requests.post(
            url,
            data=xml_body,
            headers={"Content-Type": "application/xml; charset=utf-8"},
            timeout=30,
        )
        resp.raise_for_status()
        return {
            "status_code": resp.status_code,
            "text": resp.text,
        }