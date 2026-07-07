# nav/auth.py
# NAV M2M autentikációs réteg.
# Nonce beváltás → Token létrehozás → Bearer token cachelés + megújítás.
# Forrás: NAVGOVHU-m2m_common-1.1.yaml
# Endpoints:
#   POST /NavM2mCommon/userregistrationService/Nonce       → redeemNonce
#   POST /NavM2mCommon/tokenService/Token                  → createToken

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

NAV_BASE_URLS: dict[str, str] = {
    "teszt": "https://m2mtest.nav.gov.hu",
    "eles":  "https://m2m.nav.gov.hu",
}

TOKEN_ELETARTAM_PERC = 55


class NavM2MAuth:
    """
    NAV M2M Bearer Token kezelő.
    Automatikusan megújítja a tokent, ha lejárt.

    Példa:
        auth = NavM2MAuth(user_id="12345678", jelszo="titok", kornyezet="teszt")
        token = auth.get_token()
    """

    def __init__(
        self,
        user_id: str,
        jelszo: str,
        kornyezet: str = "teszt",
        timeout: int = 30,
    ) -> None:
        if kornyezet not in NAV_BASE_URLS:
            raise ValueError(
                f"Ismeretlen környezet: '{kornyezet}'. "
                f"Lehetséges értékek: {list(NAV_BASE_URLS.keys())}"
            )
        self.user_id    = user_id
        self.jelszo     = jelszo
        self.kornyezet  = kornyezet
        self.timeout    = timeout
        self.base_url   = NAV_BASE_URLS[kornyezet]
        self._token: Optional[str]      = None
        self._token_lejar: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Publikus API
    # ------------------------------------------------------------------

    def get_token(self) -> str:
        """Visszaadja az érvényes Bearer tokent, szükség esetén megújítja."""
        if not self._token_ervenyes():
            self._token_megujitas()
        return self._token  # type: ignore[return-value]

    def token_ervenyes_e(self) -> bool:
        """True, ha van érvényes, nem lejárt token."""
        return self._token_ervenyes()

    def kornyezet_valtasa(self, uj_kornyezet: str) -> None:
        """
        Vált teszt ↔ éles között.
        A meglévő tokent törli, az új környezeten frissen authenticál.
        """
        if uj_kornyezet not in NAV_BASE_URLS:
            raise ValueError(
                f"Ismeretlen környezet: '{uj_kornyezet}'. "
                f"Lehetséges értékek: {list(NAV_BASE_URLS.keys())}"
            )
        self.kornyezet  = uj_kornyezet
        self.base_url   = NAV_BASE_URLS[uj_kornyezet]
        self._token     = None
        self._token_lejar = None
        logger.info("Környezet váltva → %s (%s)", uj_kornyezet, self.base_url)

    def auth_fejlecek(self, extra: Optional[dict[str, str]] = None) -> dict[str, str]:
        """
        Visszaad egy kész Authorization + messageId fejléc dict-et.
        Opcionálisan kiegészíthető extra fejlécekkel.
        """
        fejlecek: dict[str, str] = {
            "Authorization": f"Bearer {self.get_token()}",
            "messageId":     str(uuid.uuid4()),
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        }
        if extra:
            fejlecek.update(extra)
        return fejlecek

    # ------------------------------------------------------------------
    # Belső logika
    # ------------------------------------------------------------------

    def _token_ervenyes(self) -> bool:
        if self._token is None or self._token_lejar is None:
            return False
        return datetime.now(timezone.utc) < self._token_lejar

    def _token_megujitas(self) -> None:
        logger.info("Token megújítás indul (környezet: %s)...", self.kornyezet)
        nonce = self._nonce_bevaltas()
        token = self._token_letrehozas(nonce)
        self._token      = token
        self._token_lejar = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_ELETARTAM_PERC)
        logger.info("Token megújítva, lejár: %s UTC", self._token_lejar.strftime("%H:%M:%S"))

    def _nonce_bevaltas(self) -> str:
        """
        POST /NavM2mCommon/userregistrationService/Nonce
        operationId: redeemNonce
        """
        url        = f"{self.base_url}/NavM2mCommon/userregistrationService/Nonce"
        message_id = str(uuid.uuid4())
        payload    = {
            "requestData": {
                "login":    self.user_id,
                "password": self.jelszo,
            }
        }
        headers = {
            "messageId":    message_id,
            "Content-Type": "application/json",
            "Accept":       "application/json",
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            nonce = resp.json().get("responseData", {}).get("nonce")
            if not nonce:
                raise ValueError(f"Nonce nem érkezett. Válasz: {resp.text[:300]}")
            logger.debug("Nonce OK (messageId=%s)", message_id)
            return nonce
        except requests.RequestException as exc:
            logger.error("Nonce beváltás hiba: %s", exc)
            raise

    def _token_letrehozas(self, nonce: str) -> str:
        """
        POST /NavM2mCommon/tokenService/Token
        operationId: createToken
        """
        url        = f"{self.base_url}/NavM2mCommon/tokenService/Token"
        message_id = str(uuid.uuid4())
        payload    = {
            "requestData": {
                "login": self.user_id,
                "nonce": nonce,
            }
        }
        headers = {
            "messageId":    message_id,
            "Content-Type": "application/json",
            "Accept":       "application/json",
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            token = resp.json().get("responseData", {}).get("token")
            if not token:
                raise ValueError(f"Token nem érkezett. Válasz: {resp.text[:300]}")
            logger.debug("Token létrehozva (messageId=%s)", message_id)
            return token
        except requests.RequestException as exc:
            logger.error("Token létrehozás hiba: %s", exc)
            raise