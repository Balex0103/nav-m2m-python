# gui/dashboard_tabs.py
# NAV M2M vezérlőpult lapfülei.
# Tartalmazza az összes funkcionális fület:
#   1. Feldolgozás       – SAP export → XML pipeline
#   2. Adózási állapot   – NAV státusz összefoglaló
#   3. Határidők         – bevallási határidők
#   4. Előzmények        – audit log / kommunikációs történet
#   5. Beállítások       – NAV config, teszt/éles váltás
#   6. Helpdesk          – hibabejelentés, SMTP/mailto

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

import customtkinter as ctk
from tkinter import messagebox

logger = logging.getLogger(__name__)


class DashboardTabs(ctk.CTkFrame):
    """
    Fő vezérlőpult — minden lapfület tartalmaz.
    A főablak (NavM2MApp) példányosítja.
    """

    def __init__(
        self,
        master: Any,
        kornyezet_callback: Optional[Callable[[str], None]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        self.kornyezet_callback = kornyezet_callback
        self._tabview_letrehozasa()

    # ------------------------------------------------------------------
    # Lapfül felépítés
    # ------------------------------------------------------------------

    def _tabview_letrehozasa(self) -> None:
        self.tabs = ctk.CTkTabview(self, anchor="nw")
        self.tabs.pack(fill="both", expand=True)

        # Lapfülek létrehozása
        tab_feldolgozas  = self.tabs.add("📂 Feldolgozás")
        tab_adozas       = self.tabs.add("📊 Adózási Állapot")
        tab_hataridok    = self.tabs.add("📅 Határidők")
        tab_elozmeny     = self.tabs.add("📋 Előzmények")
        tab_beallitas    = self.tabs.add("⚙️ Beállítások")
        tab_helpdesk     = self.tabs.add("✉️ Helpdesk")

        self._feldolgozas_tab_felep(tab_feldolgozas)
        self._adozas_tab_felep(tab_adozas)
        self._hataridok_tab_felep(tab_hataridok)
        self._elozmeny_tab_felep(tab_elozmeny)
        self._beallitas_tab_felep(tab_beallitas)
        self._helpdesk_tab_felep(tab_helpdesk)

    # ------------------------------------------------------------------
    # 1. Feldolgozás tab
    # ------------------------------------------------------------------

    def _feldolgozas_tab_felep(self, tab: Any) -> None:
        # Felső gombsor
        gomb_sor = ctk.CTkFrame(tab, fg_color="transparent")
        gomb_sor.pack(fill="x", pady=(0, 8))

        ctk.CTkButton(
            gomb_sor,
            text="📂  Fájl betöltése",
            width=160,
            command=self._fajl_betoltese,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            gomb_sor,
            text="▶️  Feldolgozás indítása",
            width=180,
            fg_color="#2e7d32",
            hover_color="#1b5e20",
            command=self._feldolgozas_inditas,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            gomb_sor,
            text="📋  Sablon letöltése",
            width=160,
            fg_color="#1565c0",
            hover_color="#0d47a1",
            command=self._sablon_letoltese,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            gomb_sor,
            text="📤  NAV Beküldés",
            width=160,
            fg_color="#6a1b9a",
            hover_color="#4a148c",
            command=self._nav_bekuldese,
        ).pack(side="right", padx=4)

        # Fájl állapot jelző
        self.fajl_label = ctk.CTkLabel(
            tab,
            text="Nincs betöltött fájl.",
            font=ctk.CTkFont(size=12),
            text_color="#888888",
        )
        self.fajl_label.pack(anchor="w", padx=6)

        # Log ablak
        ctk.CTkLabel(
            tab,
            text="Feldolgozási napló:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", padx=6, pady=(8, 2))

        self.log_ablak = ctk.CTkTextbox(tab, height=320, font=ctk.CTkFont(size=12))
        self.log_ablak.pack(fill="both", expand=True, padx=4, pady=4)
        self.log_ablak.tag_config("hiba",     foreground="#ef5350")
        self.log_ablak.tag_config("siker",    foreground="#66bb6a")
        self.log_ablak.tag_config("figyelem", foreground="#ffb74d")
        self.log_ablak.tag_config("info",     foreground="#4fc3f7")

        # XML előnézet
        ctk.CTkLabel(
            tab,
            text="XML előnézet:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", padx=6, pady=(8, 2))

        self.xml_elonezet = ctk.CTkTextbox(
            tab, height=120, font=ctk.CTkFont(size=10)
        )
        self.xml_elonezet.pack(fill="both", expand=True, padx=4, pady=4)

    # ------------------------------------------------------------------
    # Privát tab felépítő metódusok (stub implementációk)
    # ------------------------------------------------------------------

    def _adozas_tab_felep(self, tab: Any) -> None:
        """Adózási állapot tab felépítése."""
        ctk.CTkLabel(tab, text="Adózási állapot", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=20)

    def _hataridok_tab_felep(self, tab: Any) -> None:
        """Határidők tab felépítése."""
        ctk.CTkLabel(tab, text="Határidők", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=20)

    def _elozmeny_tab_felep(self, tab: Any) -> None:
        """Előzmények tab felépítése."""
        ctk.CTkLabel(tab, text="Előzmények", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=20)

    def _beallitas_tab_felep(self, tab: Any) -> None:
        """Beállítások tab felépítése."""
        ctk.CTkLabel(tab, text="Beállítások", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=20)

    def _helpdesk_tab_felep(self, tab: Any) -> None:
        """Helpdesk tab felépítése."""
        ctk.CTkLabel(tab, text="Helpdesk", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=20)

    # ------------------------------------------------------------------
    # Privát callback metódusok (stub implementációk)
    # ------------------------------------------------------------------

    def _fajl_betoltese(self) -> None:
        """Fájl betöltése callback."""
        pass

    def _feldolgozas_inditas(self) -> None:
        """Feldolgozás indítása callback."""
        pass

    def _sablon_letoltese(self) -> None:
        """Sablon letöltése callback."""
        pass

    def _nav_bekuldese(self) -> None:
        """NAV beküldés callback."""
        pass