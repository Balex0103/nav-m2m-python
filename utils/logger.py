from __future__ import annotations
import os
import re
import datetime

from config import LOG_MAPPA

class Logger:
    _instance = None
    _log_callback = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = Logger()
        return cls._instance

    @classmethod
    def set_callback(cls, callback):
        cls.get_instance()._log_callback = callback

    def info(self, msg: str):
        self.log(msg, level="INFO")

    def warning(self, msg: str):
        self.log(msg, level="WARNING")

    def error(self, msg: str):
        self.log(msg, level="ERROR")

    def success(self, msg: str):
        self.log(msg, level="SUCCESS")

    def divider(self):
        self.log("-" * 60, level="INFO")

    def log(self, szoveg: str, level="INFO"):
        self._write_to_file(szoveg)
        if self._log_callback:
            # Determine tag based on msg or level
            tag = "info"
            if level == "ERROR" or "❌" in szoveg or "[HIBA]" in szoveg:
                tag = "hiba"
            elif level == "SUCCESS" or "✅" in szoveg or "[Siker]" in szoveg:
                tag = "siker"
            elif level == "WARNING" or "⚠️" in szoveg:
                tag = "figyelem"

            self._log_callback(szoveg, tag)

    def _write_to_file(self, szoveg: str):
        try:
            os.makedirs(LOG_MAPPA, exist_ok=True)
            idobelyeg = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            mai_datum = datetime.datetime.now().strftime("%Y_%m_%d")
            path = os.path.join(LOG_MAPPA, f"naplo_{mai_datum}.txt")
            with open(path, "a", encoding="utf-8", newline="\n") as log_file:
                log_file.write(f"[{idobelyeg}] {self.biztonsagos_xml_minta(szoveg)}\n")
        except Exception:
            pass

    def biztonsagos_xml_minta(self, szoveg: str, hossz: int = 900) -> str:
        if "<" not in szoveg or ">" not in szoveg:
            return szoveg

        redacted = re.sub(
            r"(<(?:[^:>]+:)?passwordHash[^>]*>)(.*?)(</(?:[^:>]+:)?passwordHash>)",
            r"\1***REDACTED***\3",
            szoveg,
            flags=re.DOTALL,
        )
        redacted = re.sub(
            r"(<(?:[^:>]+:)?requestSignature[^>]*>)(.*?)(</(?:[^:>]+:)?requestSignature>)",
            r"\1***REDACTED***\3",
            redacted,
            flags=re.DOTALL,
        )
        return redacted[:hossz]

# Expose a global logger instance for convenience
logger = Logger.get_instance()
