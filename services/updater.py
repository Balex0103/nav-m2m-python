# services/updater.py
# NAV M2M Auto-Installer / verzióellenőrző szolgáltatás.
# Figyeli a NAV GitHub repók XSD és YAML verzióit,
# és értesíti a felhasználót, ha frissítés érhető el.
# Forrás repók:
#   https://github.com/nav-gov-hu/eVAT  (XSD sémák)
#   https://github.com/nav-gov-hu/M2M   (REST YAML-ok)

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Any, cast

import requests

logger = logging.getLogger(__name__)

# --- GitHub API végpontok ---
EVAT_COMMITS_URL = (
    "https://api.github.com/repos/nav-gov-hu/eVAT/commits"
    "?path=src/schemas/hu/gov/nav/vdr&per_page=1"
)
M2M_COMMITS_URL = (
    "https://api.github.com/repos/nav-gov-hu/M2M/commits"
    "?path=src/REST&per_page=1"
)

# Helyi verzió cache fájl neve
VERZIO_CACHE_FAJL = "nav_verzio_cache.json"

# Ellenőrzési gyakoriság (óra)
ELLENORZES_GYAKORISAG_ORA = 24


@dataclass
class VerzioInfo:
    """Egy NAV GitHub repó legutóbbi commit információja."""
    repo_nev:       str
    commit_sha:     str
    commit_datum:   str
    commit_uzenet:  str
    frissites_van:  bool = False


class UpdaterService:
    """
    NAV GitHub verzióellenőrző és frissítési értesítő.

    Használat:
        updater = UpdaterService(cache_mappa="/path/to/logs")
        infok = updater.verzio_ellenorzes()
        for info in infok:
            if info.frissites_van:
                print(f"Frissítés: {info.repo_nev}")
    """

    def __init__(
        self,
        cache_mappa: str = ".",
        timeout: int = 10,
    ) -> None:
        self.cache_mappa  = cache_mappa
        self.timeout      = timeout
        self.cache_fajl   = os.path.join(cache_mappa, VERZIO_CACHE_FAJL)

    # ------------------------------------------------------------------
    # Publikus API
    # ------------------------------------------------------------------

    def verzio_ellenorzes(self) -> list[VerzioInfo]:
        """
        Ellenőrzi az eVAT és M2M repók legutóbbi commit-jait.
        Visszaadja a VerzioInfo listát frissítési jelzéssel.
        Ha a GitHub nem elérhető, a cache-ből dolgozik.
        """
        if not self._ellenorzes_szukseges():
            logger.debug("Verzióellenőrzés kihagyva (nem telt el %d óra).", ELLENORZES_GYAKORISAG_ORA)
            return self._cache_betoltese()

        logger.info("Verzióellenőrzés indul (eVAT + M2M)...")
        cache = self._cache_betoltese_dict()
        korabbi_verziok = cast(list[dict[str, Any]], cache.get("verzio_lista", []))
        eredmenyek: list[VerzioInfo] = []

        for repo_nev, url in [
            ("eVAT XSD sémák", EVAT_COMMITS_URL),
            ("M2M REST API",   M2M_COMMITS_URL),
        ]:
            info = self._commit_lekerdezese(repo_nev, url)
            if info:
                # Kikeressük a korábbi SHA-t a cache-ből
                korabbi_sha = ""
                for v in korabbi_verziok:
                    if str(v.get("repo_nev", "")) == repo_nev:
                        korabbi_sha = str(v.get("commit_sha", ""))
                        break
                
                info.frissites_van = (
                    bool(korabbi_sha) and info.commit_sha != korabbi_sha
                )
                eredmenyek.append(info)

        if eredmenyek:
            self._cache_mentese(eredmenyek)
            self._idopont_mentese()
            
        return eredmenyek

    def frissites_van_e(self) -> bool:
        """Gyors ellenőrzés: van-e bármelyik repón frissítés."""
        return any(i.frissites_van for i in self.verzio_ellenorzes())

    def utolso_ellenorzes_ideje(self) -> Optional[str]:
        """Visszaadja az utolsó ellenőrzés időpontját olvasható formában."""
        try:
            with open(self.cache_fajl, "r", encoding="utf-8") as f:
                data = cast(dict[str, Any], json.load(f))
                val = data.get("utolso_ellenorzes")
                return str(val) if val else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Privát segédfüggvények
    # ------------------------------------------------------------------

    def _ellenorzes_szukseges(self) -> bool:
        """Megvizsgálja, hogy eltelt-e az ellenőrzés gyakorisága (24 óra)."""
        try:
            with open(self.cache_fajl, "r", encoding="utf-8") as f:
                data = cast(dict[str, Any], json.load(f))
                last_check_str = str(data.get("utolso_ellenorzes", ""))
                if last_check_str:
                    last_check_date = datetime.fromisoformat(last_check_str)
                    if datetime.now() - last_check_date < timedelta(hours=ELLENORZES_GYAKORISAG_ORA):
                        return False
        except Exception:
            pass
        return True

    def _cache_betoltese(self) -> list[VerzioInfo]:
        """Betölti a VerzioInfo listát a cache-ből."""
        try:
            with open(self.cache_fajl, "r", encoding="utf-8") as f:
                data = cast(dict[str, Any], json.load(f))
                verzio_lista_nyers = cast(list[dict[str, Any]], data.get("verzio_lista", []))
                
                verzio_lista: list[VerzioInfo] = []
                for item in verzio_lista_nyers:
                    verzio_lista.append(VerzioInfo(
                        repo_nev=str(item.get("repo_nev", "")),
                        commit_sha=str(item.get("commit_sha", "")),
                        commit_datum=str(item.get("commit_datum", "")),
                        commit_uzenet=str(item.get("commit_uzenet", "")),
                        frissites_van=bool(item.get("frissites_van", False)),
                    ))
                return verzio_lista
        except Exception:
            return []

    def _cache_betoltese_dict(self) -> dict[str, Any]:
        """Betölti a cache-t szótárként."""
        try:
            with open(self.cache_fajl, "r", encoding="utf-8") as f:
                return cast(dict[str, Any], json.load(f))
        except Exception:
            return {}

    def _cache_mentese(self, verzio_lista: list[VerzioInfo]) -> None:
        """Menti a VerzioInfo listát a cache-be, megtartva az utolsó ellenőrzés idejét."""
        try:
            data = self._cache_betoltese_dict()
            data["verzio_lista"] = [
                {
                    "repo_nev": v.repo_nev,
                    "commit_sha": v.commit_sha,
                    "commit_datum": v.commit_datum,
                    "commit_uzenet": v.commit_uzenet,
                    "frissites_van": v.frissites_van,
                }
                for v in verzio_lista
            ]
            with open(self.cache_fajl, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning("Cache mentés sikertelen: %s", e)

    def _idopont_mentese(self) -> None:
        """Menti az aktuális időpontot az utolsó ellenőrzéshez."""
        try:
            data = self._cache_betoltese_dict()
            data["utolso_ellenorzes"] = datetime.now().isoformat()
            with open(self.cache_fajl, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning("Időpont mentés sikertelen: %s", e)

    def _commit_lekerdezese(self, repo_nev: str, commits_url: str) -> Optional[VerzioInfo]:
        """Lekérdezi a legutóbbi commit adatait a GitHub API-ból."""
        try:
            resp = requests.get(commits_url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            
            if isinstance(data, list) and len(data) > 0:
                commit_obj = cast(dict[str, Any], data[0])
                commit_data = cast(dict[str, Any], commit_obj.get("commit", {}))
                author_data = cast(dict[str, Any], commit_data.get("author", {}))
                
                return VerzioInfo(
                    repo_nev=repo_nev,
                    commit_sha=str(commit_obj.get("sha", ""))[:7],
                    commit_datum=str(author_data.get("date", "")),
                    commit_uzenet=str(commit_data.get("message", "")),
                    frissites_van=False,
                )
        except Exception as e:
            logger.warning("Commit lekérdezés sikertelen (%s): %s", repo_nev, e)
        return None