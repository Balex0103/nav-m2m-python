# services/helpdesk.py
# NAV M2M Helpdesk / hibabejelentés szolgáltatás.
# macOS-kompatibilis megoldás:
#   1. SMTP küldés (ha be van állítva)
#   2. mailto: fallback (megnyitja a Mail appt)
#   3. Vágólapra másolás (ha egyik sem működik)
# Ez a három réteg garantálja, hogy macOS-en is mindig működjön.

from __future__ import annotations

import logging
import os
import platform
import smtplib
import subprocess
import urllib.parse
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)

# --- Helpdesk alapértékek ---
HELPDESK_EMAIL       = "nav.m2m.helpdesk@example.com"
SMTP_TIMEOUT_MP      = 10
DIAGNOSZTIKA_SOROK   = 15


@dataclass
class HelpdeskUzenet:
    """Egy helpdesk bejelentés összes adata."""
    felado_nev:    str
    felado_email:  str
    targy:         str
    leiras:        str
    user_id:       str           = ""
    kornyezet:     str           = "teszt"
    utolso_hiba:   str           = ""
    message_id:    str           = field(
        default_factory=lambda: str(uuid.uuid4())
    )
    idopont:       str           = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    def szoveg_formatalt(self) -> str:
        """Visszaadja az e-mail törzsét formázott szövegként."""
        return (
            f"NAV M2M Hibabejelentés\n"
            f"{'=' * 50}\n"
            f"Időpont:      {self.idopont}\n"
            f"Message ID:   {self.message_id}\n"
            f"Feladó:       {self.felado_nev} <{self.felado_email}>\n"
            f"NAV User ID:  {self.user_id or '(nincs megadva)'}\n"
            f"Környezet:    {self.kornyezet.upper()}\n"
            f"{'=' * 50}\n\n"
            f"LEÍRÁS:\n{self.leiras}\n\n"
            f"UTOLSÓ HIBA:\n{self.utolso_hiba or '(nincs)'}\n"
        )

    def targy_formatalt(self) -> str:
        return f"[NAV M2M] {self.targy} – {self.idopont}"


@dataclass
class SmtpKonfig:
    """SMTP szerver beállítások."""
    host:       str
    port:       int  = 587
    user:       str  = ""
    jelszo:     str  = ""
    tls:        bool = True


class HelpdeskService:
    """
    Helpdesk üzenetküldő szolgáltatás.
    Három rétegű fallback: SMTP → mailto → vágólap.

    Példa:
        svc = HelpdeskService(smtp_konfig=None)
        ok, mod = svc.kuldes(uzenet)
    """

    def __init__(self, smtp_konfig: Optional[SmtpKonfig] = None) -> None:
        self.smtp_konfig = smtp_konfig

    # ------------------------------------------------------------------
    # Publikus API
    # ------------------------------------------------------------------

    def kuldes(self, uzenet: HelpdeskUzenet) -> tuple[bool, str]:
        """
        Elküldi a helpdesk üzenetet.
        Visszatér: (siker: bool, modszer: str)
        Modszer lehet: "smtp", "mailto", "vagolap"
        """
        # 1. réteg: SMTP
        if self.smtp_konfig:
            try:
                self._smtp_kuldes(uzenet)
                logger.info("Helpdesk üzenet elküldve SMTP-vel.")
                return True, "smtp"
            except Exception as exc:
                logger.warning("SMTP küldés sikertelen, fallback mailto: %s", exc)

        # 2. réteg: mailto
        try:
            self._mailto_megnyitas(uzenet)
            logger.info("Helpdesk: mailto megnyitva.")
            return True, "mailto"
        except Exception as exc:
            logger.warning("mailto sikertelen, fallback vágólap: %s", exc)

        # 3. réteg: vágólap
        try:
            self._vagólapra_masolás(uzenet)
            logger.info("Helpdesk üzenet vágólapra másolva.")
            return True, "vagolap"
        except Exception as exc:
            logger.error("Minden helpdesk módszer sikertelen: %s", exc)
            return False, "hiba"

    def diagnosztika_szoveg(
        self,
        log_mappa: str,
        max_sor: int = DIAGNOSZTIKA_SOROK,
    ) -> str:
        """
        Összegyűjti az utolsó N sor naplót diagnosztikai célból.
        A helpdesk űrlapba automatikusan beilleszthető.
        """
        try:
            log_fajlok = sorted(
                [
                    os.path.join(log_mappa, f)
                    for f in os.listdir(log_mappa)
                    if f.endswith(".log")
                ],
                key=os.path.getmtime,
                reverse=True,
            )
            if not log_fajlok:
                return "(Nincs elérhető napló.)"
            with open(log_fajlok[0], encoding="utf-8", errors="replace") as fh:
                sorok = fh.readlines()
            return "".join(sorok[-max_sor:])
        except Exception as exc:
            return f"(Napló olvasási hiba: {exc})"

    # ------------------------------------------------------------------
    # Belső metódusok
    # ------------------------------------------------------------------

    def _smtp_kuldes(self, uzenet: HelpdeskUzenet) -> None:
        """SMTP e-mail küldés TLS-sel."""
        assert self.smtp_konfig is not None
        msg = MIMEMultipart("alternative")
        msg["Subject"] = uzenet.targy_formatalt()
        msg["From"]    = (
            f"{uzenet.felado_nev} <{uzenet.felado_email}>"
        )
        msg["To"]      = HELPDESK_EMAIL
        msg["Reply-To"] = uzenet.felado_email
        msg.attach(MIMEText(uzenet.szoveg_formatalt(), "plain", "utf-8"))

        with smtplib.SMTP(
            self.smtp_konfig.host,
            self.smtp_konfig.port,
            timeout=SMTP_TIMEOUT_MP,
        ) as server:
            if self.smtp_konfig.tls:
                server.starttls()
            if self.smtp_konfig.user:
                server.login(self.smtp_konfig.user, self.smtp_konfig.jelszo)
            server.send_message(msg)

    def _mailto_megnyitas(self, uzenet: HelpdeskUzenet) -> None:
        """
        Megnyitja az alapértelmezett levelező alkalmazást
        előre kitöltött levéllel.
        macOS-en: open mailto:...
        Windows-on: start mailto:...
        Linux-on: xdg-open mailto:...
        """
        params = urllib.parse.urlencode(
            {
                "subject": uzenet.targy_formatalt(),
                "body":    uzenet.szoveg_formatalt(),
            },
            quote_via=urllib.parse.quote,
        )
        mailto_url = f"mailto:{HELPDESK_EMAIL}?{params}"

        rendszer = platform.system()
        if rendszer == "Darwin":       # macOS
            subprocess.Popen(["open", mailto_url])
        elif rendszer == "Windows":
            os.startfile(mailto_url)   # type: ignore[attr-defined]
        else:                          # Linux
            subprocess.Popen(["xdg-open", mailto_url])

    def _vagólapra_masolás(self, uzenet: HelpdeskUzenet) -> None:
        """
        A teljes helpdesk szöveget vágólapra másolja.
        Utolsó fallback, ha sem SMTP, sem mailto nem működik.
        """
        import tkinter as tk
        gyoker = tk.Tk()
        gyoker.withdraw()
        gyoker.clipboard_clear()
        gyoker.clipboard_append(uzenet.szoveg_formatalt())
        gyoker.update()
        gyoker.after(2000, gyoker.destroy)
        gyoker.mainloop()
        logger.info("Helpdesk szöveg vágólapra másolva.")