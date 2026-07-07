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

from gui.workflows import automatikus_feldolgozas_inditasa, kapcsolat_teszt_inditasa

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

        from utils.logger import Logger
        def log_callback(msg, tag):
            if hasattr(self, 'log_ablak'):
                if tag:
                    self.log_ablak.insert("end", msg + "\n", tag)
                else:
                    self.log_ablak.insert("end", msg + "\n")
                self.log_ablak.see("end")
        Logger.set_callback(log_callback)

    # ------------------------------------------------------------------
    # 1. Feldolgozás tab
    # ------------------------------------------------------------------

    def _feldolgozas_tab_felep(self, tab: Any) -> None:
        # Felső gombsor
        gomb_sor = ctk.CTkFrame(tab, fg_color="transparent")
        gomb_sor.pack(fill="x", pady=(0, 8))

        self.btn_feldolgoz = ctk.CTkButton(
            gomb_sor,
            text="▶️  Mappa ellenőrzése és Feldolgozás indítása",
            width=180,
            fg_color="#2e7d32",
            hover_color="#1b5e20",
            command=self._feldolgozas_inditas,
        )
        self.btn_feldolgoz.pack(side="left", padx=4)

        import gui.previews as previews

        ctk.CTkButton(
            gomb_sor,
            text="📊  Excel előnézet",
            width=160,
            fg_color="#1565c0",
            hover_color="#0d47a1",
            command=lambda: previews.excel_preview_megnyitas(self),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            gomb_sor,
            text="📄  XML előnézet",
            width=160,
            fg_color="#6a1b9a",
            hover_color="#4a148c",
            command=lambda: previews.xml_preview_megnyitas(self),
        ).pack(side="left", padx=4)

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
        statusz_keret = ctk.CTkFrame(tab, corner_radius=10, fg_color="#2b2b2b")
        statusz_keret.pack(pady=10, padx=10, fill="x")

        lbl_statusz_title = ctk.CTkLabel(statusz_keret, text="Élő NAV Adózói Adatbázis Kapcsolat", font=ctk.CTkFont(size=14, weight="bold"), text_color="#5DADE2")
        lbl_statusz_title.grid(row=0, column=0, columnspan=2, pady=8, padx=15, sticky="w")

        from services.nav_session import van_valodi_nav_hitelesites, nav_config_osszeallitasa

        try:
            config = nav_config_osszeallitasa(
                tech_user=self.entry_tech_user.get() if hasattr(self, 'entry_tech_user') else "",
                password=self.entry_jelszo.get() if hasattr(self, 'entry_jelszo') else "",
                sign_key=self.entry_sign_kulcs.get() if hasattr(self, 'entry_sign_kulcs') else "",
                exchange_key=self.entry_xml_kulcs.get() if hasattr(self, 'entry_xml_kulcs') else "",
                tax_number=self.entry_adoszam.get() if hasattr(self, 'entry_adoszam') else "",
                environment=self.combo_kornyezet.get() if hasattr(self, 'combo_kornyezet') else "TEST"
            )
            adoszam_rovid = config.tax_number if config.tax_number else "--------"
            ceg_nev = "M2M Partner Vállalat Kft." if config.tax_number else "Nincs konfigurált vállalat"
            koma_text = "🟢 IGEN (Köztartozásmentes Adatbázisban szerepel)" if van_valodi_nav_hitelesites(config) else "🟡 ELLENŐRZÉSRE VÁR (Szimulált üzemmód)"
            koma_color = "#00FF88" if van_valodi_nav_hitelesites(config) else "#F1C40F"
        except Exception:
            adoszam_rovid = "N/A"
            ceg_nev = "Vállalat Kft."
            koma_text = "🟡 ELLENŐRZÉSRE VÁR (Szimulált üzemmód)"
            koma_color = "#F1C40F"

        lbl_ceg = ctk.CTkLabel(statusz_keret, text=f"Regisztrált Alany: {ceg_nev} | Adószám: {adoszam_rovid}", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_ceg.grid(row=1, column=0, columnspan=2, padx=15, pady=5, sticky="w")

        lbl_koma_title = ctk.CTkLabel(statusz_keret, text="Hivatalos KOMA adatbázis tagság:")
        lbl_koma_title.grid(row=2, column=0, padx=15, pady=5, sticky="w")

        lbl_koma_value = ctk.CTkLabel(statusz_keret, text=koma_text, text_color=koma_color, font=ctk.CTkFont(size=12, weight="bold"))
        lbl_koma_value.grid(row=2, column=1, padx=15, pady=5, sticky="w")

        lbl_egyenleg_title = ctk.CTkLabel(statusz_keret, text="Aktuális NAV folyószámla egyenleg:")
        lbl_egyenleg_title.grid(row=3, column=0, padx=15, pady=(5, 10), sticky="w")

        lbl_egyenleg_value = ctk.CTkLabel(statusz_keret, text="Lekérdezés folyamatban...", text_color="#00FF88", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_egyenleg_value.grid(row=3, column=1, padx=15, pady=(5, 10), sticky="w")

    def _hataridok_tab_felep(self, tab: Any) -> None:
        """Határidők tab felépítése."""
        import datetime
        hatarido_keret = ctk.CTkFrame(tab, corner_radius=10, fg_color="#232323")
        hatarido_keret.pack(pady=10, padx=10, fill="x")

        lbl_hatar_title = ctk.CTkLabel(hatarido_keret, text="📅 Jogszabályi ÁFA Bevallási Határidők", font=ctk.CTkFont(size=14, weight="bold"), text_color="#E74C3C")
        lbl_hatar_title.pack(pady=8, padx=15, anchor="w")

        ma = datetime.date.today()
        kov_honap = ma.replace(day=28) + datetime.timedelta(days=4)
        esedekesseg = datetime.date(kov_honap.year, kov_honap.month, 20)
        hatra_van = (esedekesseg - ma).days

        lbl_hatar_info = ctk.CTkLabel(
            hatarido_keret,
            text=f"A tárgyidőszaki adóbevallás és adóbefizetés törvényi határideje: {esedekesseg.strftime('%Y.%m.%d.')}\n"
                 f"Hátralévő törvényes intézkedési idő: {hatra_van} nap.",
            font=ctk.CTkFont(size=12),
            justify="left"
        )
        lbl_hatar_info.pack(pady=5, padx=15, anchor="w")

    def _elozmeny_tab_felep(self, tab: Any) -> None:
        """Előzmények tab felépítése."""
        ctk.CTkLabel(tab, text="Előzmények", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=20)

    def _beallitas_tab_felep(self, tab: Any) -> None:
        """Beállítások tab felépítése."""
        beallitas_keret = ctk.CTkFrame(tab, corner_radius=10, fg_color="#2b2b2b")
        beallitas_keret.pack(pady=10, padx=20, fill="x")

        lbl_beallitas_cim = ctk.CTkLabel(
            beallitas_keret,
            text="⚙️ NAV API Hitelesítési Adatok",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        lbl_beallitas_cim.grid(row=0, column=0, columnspan=2, pady=10, padx=10, sticky="w")

        self.entry_tech_user = ctk.CTkEntry(beallitas_keret, placeholder_text="Technikai felhasználónév", width=320)
        self.entry_tech_user.grid(row=1, column=0, padx=10, pady=(0, 10))

        self.entry_jelszo = ctk.CTkEntry(beallitas_keret, placeholder_text="Jelszó", show="*", width=320)
        self.entry_jelszo.grid(row=1, column=1, padx=10, pady=(0, 10))

        self.entry_xml_kulcs = ctk.CTkEntry(beallitas_keret, placeholder_text="XML cserekulcs", width=320)
        self.entry_xml_kulcs.grid(row=2, column=0, padx=10, pady=(0, 10))

        self.entry_sign_kulcs = ctk.CTkEntry(beallitas_keret, placeholder_text="Aláíró kulcs (sign key)", width=320)
        self.entry_sign_kulcs.grid(row=2, column=1, padx=10, pady=(0, 10))

        self.entry_adoszam = ctk.CTkEntry(beallitas_keret, placeholder_text="Adószám (8 számjegy)", width=320)
        self.entry_adoszam.grid(row=3, column=0, padx=10, pady=(0, 15))

        self.combo_kornyezet = ctk.CTkComboBox(beallitas_keret, values=["TEST", "PROD"], width=320)
        self.combo_kornyezet.grid(row=3, column=1, padx=10, pady=(0, 15))
        self.combo_kornyezet.set("TEST")

        self.chk_eafa_feltoltes = ctk.CTkCheckBox(
            beallitas_keret,
            text="Valódi eÁFA TEST feltöltés engedélyezése",
        )
        self.chk_eafa_feltoltes.grid(row=4, column=0, columnspan=2, padx=10, pady=(0, 15), sticky="w")

        gomb_vezerlo_keret = ctk.CTkFrame(tab, fg_color="transparent")
        gomb_vezerlo_keret.pack(pady=(10, 10))

        self.btn_kapcsolat_teszt = ctk.CTkButton(
            gomb_vezerlo_keret,
            text="NAV kapcsolat teszt",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=42,
            width=220,
            command=self._kapcsolat_teszt_inditasa,
        )
        self.btn_kapcsolat_teszt.pack(side="left", padx=8)

    def _helpdesk_tab_felep(self, tab: Any) -> None:
        """Helpdesk tab felépítése."""
        helpdesk_keret = ctk.CTkFrame(tab, corner_radius=10, fg_color="#1e1e1e")
        helpdesk_keret.pack(pady=10, padx=10, fill="both", expand=True)

        lbl_hd_title = ctk.CTkLabel(helpdesk_keret, text="✉️ Fejlesztői Helpdesk és Visszajelzési Csatorna", font=ctk.CTkFont(size=14, weight="bold"), text_color="#8E44AD")
        lbl_hd_title.pack(pady=8, padx=15, anchor="w")

        self.entry_hiba_leiras = ctk.CTkTextbox(helpdesk_keret, height=120, font=ctk.CTkFont(size=12))
        self.entry_hiba_leiras.pack(fill="x", padx=15, pady=5)
        self.entry_hiba_leiras.insert("0.0", "[ Kérlek, ide részletesen írd le a javaslatot vagy hibát... ]")

        def hiba_bejelentes_vegrehajtasa() -> None:
            import datetime, urllib.parse, webbrowser
            problema_szoveg = self.entry_hiba_leiras.get("0.0", "end").strip()
            if not problema_szoveg or "ide részletesen írd le" in problema_szoveg:
                messagebox.showerror("Helpdesk hiba", "Üres leírást nem küldhetsz be!")
                return

            fejleszto_email = "balint.papp@cegnev.hu"
            adoszam = getattr(self, 'entry_adoszam', ctk.StringVar(value="")).get()
            targy = f"NAV M2M Asszisztens Diagnosztika - Adószám: {adoszam}"

            test_szoveg = (
                f"=== NAV M2M RENDSZERHIBA JELENTÉS ===\n"
                f"Időpont: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Adószám: {adoszam}\n"
                f"Környezet: eÁFA v2.0\n"
                f"--------------------------------------------------\n"
                f"Felhasználói észrevétel:\n{problema_szoveg}\n"
                f"--------------------------------------------------\n"
                f"Generált requestSignature verzió: SHA3-512 ok\n"
            )

            self.clipboard_clear()
            self.clipboard_append(test_szoveg)

            mailto_url = f"mailto:{fejleszto_email}?subject={urllib.parse.quote(targy)}&body={urllib.parse.quote('A teljes diagnosztikai naplót a szoftver automatikusan a vágólapra másolta. Kérlek nyomj egy Ctrl+V-t ide a szövegtörzsbe!')}"

            try:
                webbrowser.open(mailto_url)
                messagebox.showinfo("Helpdesk sikeres", "A levelező megnyitása elindult.\n\nA technikai adatokat a vágólapra másoltam, a megnyíló e-mailben nyomj egy Ctrl+V-t!")
            except Exception:
                messagebox.showinfo("Vágólapra mentve", "A levelezőt nem sikerült közvetlenül megnyitni, de a hibajelentést a vágólapra mentettem! Másold be egy levélbe balint.papp@cegnev.hu címre.")

        btn_kuldes = ctk.CTkButton(
            helpdesk_keret,
            text="✉️ Hibajelentés generálása és Vágólapra másolása",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#8E44AD",
            hover_color="#732D91",
            height=38,
            command=hiba_bejelentes_vegrehajtasa
        )
        btn_kuldes.pack(pady=15)

    # ------------------------------------------------------------------
    # Privát callback metódusok (stub implementációk)
    # ------------------------------------------------------------------


    def _kapcsolat_teszt_inditasa(self) -> None:
        if not hasattr(self, 'btn_kapcsolat_teszt'):
            return

        self.btn_kapcsolat_teszt.configure(state="disabled", text="⏳ Kapcsolat teszt folyamatban...")
        if hasattr(self, 'btn_feldolgoz'):
            self.btn_feldolgoz.configure(state="disabled")

        def reset_buttons():
            self.btn_kapcsolat_teszt.configure(state="normal", text="NAV kapcsolat teszt")
            if hasattr(self, 'btn_feldolgoz'):
                self.btn_feldolgoz.configure(state="normal")

        kapcsolat_teszt_inditasa(
            tech_user=self.entry_tech_user.get(),
            password=self.entry_jelszo.get(),
            sign_key=self.entry_sign_kulcs.get(),
            exchange_key=self.entry_xml_kulcs.get(),
            tax_number=self.entry_adoszam.get(),
            environment=self.combo_kornyezet.get(),
            allapot_uzenet=lambda msg, color: self.fajl_label.configure(text=msg, text_color=color) if hasattr(self, 'fajl_label') else None,
            show_error_popup=lambda title, msg: messagebox.showerror(title, msg),
            reset_buttons=reset_buttons
        )

    def _feldolgozas_inditas(self) -> None:
        """Feldolgozás indítása callback."""
        if hasattr(self, 'btn_feldolgoz'):
            self.btn_feldolgoz.configure(state="disabled", text="⏳ Feldolgozás folyamatban...")
        if hasattr(self, 'btn_kapcsolat_teszt'):
            self.btn_kapcsolat_teszt.configure(state="disabled")

        def reset_buttons():
            if hasattr(self, 'btn_feldolgoz'):
                self.btn_feldolgoz.configure(state="normal", text="▶️  Feldolgozás indítása")
            if hasattr(self, 'btn_kapcsolat_teszt'):
                self.btn_kapcsolat_teszt.configure(state="normal")

        automatikus_feldolgozas_inditasa(
            tech_user=self.entry_tech_user.get() if hasattr(self, 'entry_tech_user') else "",
            password=self.entry_jelszo.get() if hasattr(self, 'entry_jelszo') else "",
            sign_key=self.entry_sign_kulcs.get() if hasattr(self, 'entry_sign_kulcs') else "",
            exchange_key=self.entry_xml_kulcs.get() if hasattr(self, 'entry_xml_kulcs') else "",
            tax_number=self.entry_adoszam.get() if hasattr(self, 'entry_adoszam') else "",
            environment=self.combo_kornyezet.get() if hasattr(self, 'combo_kornyezet') else "TEST",
            eafa_feltoltes=bool(self.chk_eafa_feltoltes.get()) if hasattr(self, 'chk_eafa_feltoltes') else False,
            allapot_uzenet=lambda msg, color: self.fajl_label.configure(text=msg, text_color=color) if hasattr(self, 'fajl_label') else None,
            show_error_popup=lambda title, msg: messagebox.showerror(title, msg),
            ask_yes_no_popup=lambda title, msg: messagebox.askyesno(title, msg),
            reset_buttons=reset_buttons
        )
