from __future__ import annotations
from tkinter import messagebox

import logging
from typing import Any

import customtkinter as ctk

from .dashboard_tabs import DashboardTabs

logger = logging.getLogger(__name__)

# --- Megjelenési beállítások ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

ABLAK_CIM    = "NAV M2M Kliens – eÁFA Beküldő"
ABLAK_MERET  = "1200x750"
MIN_SZELESSEG = 1000
MIN_MAGASSAG  = 650

class NavM2MApp(ctk.CTk):
    """
    NAV M2M főablak.
    """
    def __init__(self) -> None:
        super().__init__()
        self._ablak_beallitasok()
        self._fejlec_letrehozasa()
        self._tartalom_letrehozasa()
        self._alaplec_letrehozasa()
        self._billentyukombinacok_regisztralasa()
        logger.info("NavM2MApp főablak elindult.")

    def _ablak_beallitasok(self) -> None:
        self.title(ABLAK_CIM)
        self.geometry(ABLAK_MERET)
        self.minsize(MIN_SZELESSEG, MIN_MAGASSAG)
        self.protocol("WM_DELETE_WINDOW", self._kilep_kezeles)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def _fejlec_letrehozasa(self) -> None:
        self.fejlec_keret = ctk.CTkFrame(self, height=55, corner_radius=0, fg_color=("#1a1a2e", "#1a1a2e"))
        self.fejlec_keret.pack(side="top", fill="x")
        self.fejlec_keret.pack_propagate(False)

        ctk.CTkLabel(self.fejlec_keret, text="🏛  NAV M2M Kliens", font=ctk.CTkFont(size=18, weight="bold"), text_color="#4fc3f7").pack(side="left", padx=20, pady=12)
        self.kornyezet_label = ctk.CTkLabel(self.fejlec_keret, text="⚠️  TESZT KÖRNYEZET", font=ctk.CTkFont(size=12, weight="bold"), text_color="#ffb74d")
        self.kornyezet_label.pack(side="right", padx=20, pady=12)

    def _tartalom_letrehozasa(self) -> None:
        self.tartalom_keret = ctk.CTkFrame(self, corner_radius=0)
        self.tartalom_keret.pack(side="top", fill="both", expand=True)

        self.dashboard = DashboardTabs(self.tartalom_keret, kornyezet_callback=self._kornyezet_frissitese)
        self.dashboard.pack(fill="both", expand=True, padx=8, pady=8)

    def _alaplec_letrehozasa(self) -> None:
        self.alaplec_keret = ctk.CTkFrame(self, height=30, corner_radius=0, fg_color=("#0d0d1a", "#0d0d1a"))
        self.alaplec_keret.pack(side="bottom", fill="x")
        self.alaplec_keret.pack_propagate(False)

        self.statusz_label = ctk.CTkLabel(self.alaplec_keret, text="Kész.", font=ctk.CTkFont(size=11), text_color="#888888")
        self.statusz_label.pack(side="left", padx=12)
        ctk.CTkLabel(self.alaplec_keret, text="NAV M2M v2.0  |  eÁFA 2.0 XSD", font=ctk.CTkFont(size=11), text_color="#555555").pack(side="right", padx=12)

    def _kornyezet_frissitese(self, kornyezet: str) -> None:
        if kornyezet == "eles":
            self.kornyezet_label.configure(text="🔴  ÉLES KÖRNYEZET", text_color="#ef5350")
            messagebox.showwarning("Éles környezet", "FIGYELEM: Éles NAV M2M környezetre váltottál!\nMinden beküldés valódi adóügyi hatással bír.")
        else:
            self.kornyezet_label.configure(text="⚠️  TESZT KÖRNYEZET", text_color="#ffb74d")
        logger.info("Főablak környezet jelző frissítve: %s", kornyezet)

    def statusz_frissitese(self, szoveg: str) -> None:
        self.statusz_label.configure(text=szoveg)

    def _billentyukombinacok_regisztralasa(self) -> None:
        # A lambda lecserélve dedikált típusannotált függvényre!
        self.bind("<Command-q>", self._kilep_esemeny)
        self.bind("<Command-w>", self._kilep_esemeny)

    def _kilep_esemeny(self, event: Any = None) -> None:
        self._kilep_kezeles()

    def _kilep_kezeles(self) -> None:
        if messagebox.askyesno("Kilépés", "Biztosan ki szeretnél lépni a NAV M2M Kliensből?", icon="question"):
            logger.info("Alkalmazás leállítva.")
            self.destroy()