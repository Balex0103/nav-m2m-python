# nav/document_api.py
# NAV M2M Document API kliens.
# Kezeli a teljes beküldési folyamatot: létrehozás → validáció → beküldés.
# Forrás: NAVGOVHU-m2m_document-1.2.yaml
# Endpoints:
#   POST  /NavM2mDocument/documentService/Document         → createDocument
#   PATCH /NavM2mDocument/documentService/Document         → updateDocument
#   GET   /NavM2mDocument/documentService/Document/{id}   → getDocument
#
# DocumentStatus folyamat:
#   UNDER_PREVALIDATION → PREVALIDATION_ERROR | UNDER_VALIDATION
#   UNDER_VALIDATION    → VALIDATION_ERROR    | VALIDATED
#   VALIDATED           → UNDER_SUBMIT
#   UNDER_SUBMIT        → SUBMIT_ERROR        | SUBMITTED

from __future__ import annotations


import logging
from typing import Any

import requests

from .auth import NavM2MAuth

logger = logging.getLogger(__name__)


class DocumentStatus:
    """NAV M2M DocumentStatus enum értékek."""
    UNDER_PREVALIDATION = "UNDER_PREVALIDATION"
    PREVALIDATION_ERROR = "PREVALIDATION_ERROR"
    UNDER_VALIDATION    = "UNDER_VALIDATION"
    VALIDATION_ERROR    = "VALIDATION_ERROR"
    VALIDATED           = "VALIDATED"
    UNDER_SUBMIT        = "UNDER_SUBMIT"
    SUBMIT_ERROR        = "SUBMIT_ERROR"
    SUBMITTED           = "SUBMITTED"

    HIBA_STATUSZOK = {PREVALIDATION_ERROR, VALIDATION_ERROR, SUBMIT_ERROR}
    VEGSO_STATUSZOK = {SUBMITTED, PREVALIDATION_ERROR, VALIDATION_ERROR, SUBMIT_ERROR}


# Polling beállítások
POLLING_MAX_PROBALKOZAS = 24   # max ~2 perc (24 × 5mp)
POLLING_VARAKOZAS_MP    = 5


class NavDocumentApiClient:
    """
    NAV M2M Document API teljes beküldési folyamat kezelője.

    Példa:
        auth    = NavM2MAuth("12345678", "titok", "teszt")
        kliens  = NavDocumentApiClient(auth)
        eredmeny = kliens.teljes_bekuldesi_folyamat(xml_str, "ear_bevallas.xml")
    """

    def __init__(self, auth: NavM2MAuth, timeout: int = 30) -> None:
        self.auth    = auth
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Publikus: teljes folyamat egyben
    # ------------------------------------------------------------------

    def teljes_bekuldesi_folyamat(
        self,
        xml_tartalom: str,
        fajlnev: str = "ear_bevallas.xml",
    ) -> dict[str, Any]:
        """
        Végigvezeti az XML-t a teljes NAV M2M beküldési folyamaton.
        Visszatérési érték:
            {
              "siker": bool,
              "document_id": str | None,
              "statusz": str,
              "uzenet": str,
            }
        """
        logger.info("=== NAV M2M beküldési folyamat indul: %s ===", fajlnev)

        # 1. lépés: dokumentum létrehozás
        try:
            create_resp = self.dokumentum_letrehozas(xml_tartalom, fajlnev)
        except Exception as exc:
            return self._hiba("Dokumentum létrehozás sikertelen.", reszletek=str(exc))

        document_id: str | None = (
            create_resp.get("responseData", {}).get("documentFileId")
        )
        if not document_id:
            return self._hiba("Dokumentum azonosító (documentFileId) nem érkezett.")

        logger.info("Dokumentum létrehozva → ID: %s", document_id)

        # 2. lépés: validáció megvárása
        valid_statusz = self._statusz_varas(
            document_id,
            cel_statuszok={DocumentStatus.VALIDATED},
            hiba_statuszok=DocumentStatus.HIBA_STATUSZOK,
            lepes_neve="Validáció",
        )
        if valid_statusz != DocumentStatus.VALIDATED:
            return self._hiba(
                f"Validáció sikertelen. Státusz: {valid_statusz}",
                document_id=document_id,
                statusz=valid_statusz,
            )

        logger.info("Validáció sikeres → beküldés indul...")

        # 3. lépés: beküldés indítása
        try:
            self.dokumentum_statusz_valtas(document_id, DocumentStatus.UNDER_SUBMIT)
        except Exception as exc:
            return self._hiba(
                "UNDER_SUBMIT státuszváltás sikertelen.",
                document_id=document_id,
                reszletek=str(exc),
            )

        # 4. lépés: beküldés megvárása
        vegso_statusz = self._statusz_varas(
            document_id,
            cel_statuszok={DocumentStatus.SUBMITTED},
            hiba_statuszok={DocumentStatus.SUBMIT_ERROR},
            lepes_neve="Beküldés",
        )

        if vegso_statusz == DocumentStatus.SUBMITTED:
            logger.info("=== Beküldés SIKERES! document_id=%s ===", document_id)
            return {
                "siker":       True,
                "document_id": document_id,
                "statusz":     vegso_statusz,
                "uzenet":      "Sikeres beküldés a NAV M2M rendszerébe.",
            }
        else:
            return self._hiba(
                f"Beküldés sikertelen. Végső státusz: {vegso_statusz}",
                document_id=document_id,
                statusz=vegso_statusz,
            )

    # ------------------------------------------------------------------
    # Publikus: egyedi műveletek
    # ------------------------------------------------------------------

    def dokumentum_letrehozas(
        self,
        xml_tartalom: str,
        fajlnev: str = "ear_bevallas.xml",
    ) -> dict[str, Any]:
        """
        POST /NavM2mDocument/documentService/Document
        operationId: createDocument
        """
        url     = f"{self.auth.base_url}/NavM2mDocument/documentService/Document"
        payload = {
            "requestData": {
                "fileName":    fajlnev,
                "fileContent": xml_tartalom,
            }
        }
        resp = requests.post(
            url,
            json=payload,
            headers=self.auth.auth_fejlecek(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def dokumentum_statusz_lekerdezese(self, document_file_id: str) -> str:
        """
        GET /NavM2mDocument/documentService/Document/{documentFileId}
        operationId: getDocument
        Visszaadja az aktuális DocumentStatus stringet.
        """
        url  = (
            f"{self.auth.base_url}"
            f"/NavM2mDocument/documentService/Document/{document_file_id}"
        )
        resp = requests.get(
            url,
            headers=self.auth.auth_fejlecek(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        doc = resp.json()
        return doc.get("responseData", {}).get("documentStatus", DocumentStatus.PREVALIDATION_ERROR)

    def dokumentum_statusz_valtas(self, document_file_id: str, new_status: str) -> None:
        """
        PATCH /NavM2mDocument/documentService/Document/{documentFileId}
        operationId: updateDocument
        Státusz váltása.
        """
        url     = f"{self.auth.base_url}/NavM2mDocument/documentService/Document/{document_file_id}"
        payload = {
            "requestData": {
                "documentStatus": new_status,
            }
        }
        resp = requests.patch(
            url,
            json=payload,
            headers=self.auth.auth_fejlecek(),
            timeout=self.timeout,
        )
        resp.raise_for_status()

    # ------------------------------------------------------------------
    # Privát segédfüggvények
    # ------------------------------------------------------------------

    def _hiba(
        self,
        uzenet: str,
        document_id: str | None = None,
        statusz: str | None = None,
        reszletek: str | None = None,
    ) -> dict[str, Any]:
        """Hibaválasz összeállítása."""
        result: dict[str, Any] = {
            "siker": False,
            "document_id": document_id,
            "statusz": statusz or "UNKNOWN",
            "uzenet": uzenet,
        }
        if reszletek:
            result["reszletek"] = reszletek
        logger.error("NavDocumentApiClient hiba: %s (statusz: %s)", uzenet, statusz or "UNKNOWN")
        return result

    def _statusz_varas(
        self,
        document_id: str,
        cel_statuszok: set[str],
        hiba_statuszok: set[str],
        lepes_neve: str = "Státusz várakozás",
    ) -> str:
        """
        Megvárja, amíg a dokumentum az egyik célállapotba kerül.
        Ha hibaállapotba kerül, azonnal leáll.
        """
        import time
        aktualis_statusz = DocumentStatus.PREVALIDATION_ERROR
        for probalkozas in range(1, POLLING_MAX_PROBALKOZAS + 1):
            aktualis_statusz = self.dokumentum_statusz_lekerdezese(document_id)
            logger.info(
                "%s: próbálkozás %d/%d — statusz: %s",
                lepes_neve, probalkozas, POLLING_MAX_PROBALKOZAS, aktualis_statusz
            )

            if aktualis_statusz in cel_statuszok:
                logger.info("%s — CÉL STATUSZ ELÉRVE: %s", lepes_neve, aktualis_statusz)
                return aktualis_statusz

            if aktualis_statusz in hiba_statuszok:
                logger.error("%s — HIBA STATUSZ: %s", lepes_neve, aktualis_statusz)
                return aktualis_statusz

            if probalkozas < POLLING_MAX_PROBALKOZAS:
                logger.debug("%s: vár %d másodpercet...", lepes_neve, POLLING_VARAKOZAS_MP)
                time.sleep(POLLING_VARAKOZAS_MP)

        logger.error("%s — TIMEOUT: %s próbálkozás után", lepes_neve, POLLING_MAX_PROBALKOZAS)
        return aktualis_statusz