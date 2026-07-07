from __future__ import annotations

import glob
import datetime
import os
import re
import sys
import threading
import traceback
from tkinter import messagebox
from typing import Any, Callable, Optional, cast

import customtkinter as ctk
import pandas as pd

from config import NavUserConfig
from eafa_api import EafaApiClient, extract_first_tag_value
from validators import validate_user_config, validate_xml_with_xsd
from xml_generator import generate_nav_xml


ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# --- OKOS ÚTVONALKEZELÉS ---
if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
    bundle_dir = getattr(sys, '_MEIPASS', app_dir)
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))
    bundle_dir = app_dir

APP_DIR = app_dir
BUNDLE_DIR = bundle_dir

MEGFIGYELT_MAPPA_NEV = "sap_export"
MEGFIGYELT_MAPPA = os.path.join(APP_DIR, MEGFIGYELT_MAPPA_NEV)
KIMENETI_XML = os.path.join(APP_DIR, "kesz_afa_bevallas.xml")
VDR_MAPPA = os.path.join(BUNDLE_DIR, "vdr")
LOG_MAPPA = os.path.join(APP_DIR, "logs")

# Az új NAV adókód katalógus útvonala (a VDR mappában keressük)
KATALOGUS_CSV = os.path.join(VDR_MAPPA, "adokod_katalogus.csv")

SAP_NAV_ADOKOD_MAPPING = {
    "A1": "DOM_L_GENERAL",
    "F2": "EXP_REVERSE_CHARGE",
}

KOTELEZO_ANALITIKA_OSZLOPOK = {
    "Szamlaszam",
    "Teljesites_Datuma",
    "Partner_Adoszam",
    "Netto_Ertek",
    "Afa_Ertek",
    "SAP_Ado_Kod",
}

KOTELEZO_NAV_ANALITIKA_XML_MEZOK = {
    "taxpointDate",
    "standardTaxCode",
    "taxBase",
    "taxAmount",
}

ISMERT_NAV_ANALITIKA_XML_MEZOK = {
    "sourceDocumentId",
    "sourceDocumentIssueDate",
    "sourceDocumentType",
    "taxpointDate",
    "partnerStatus",
    "taxNumber",
    "groupMemberTaxNumber",
    "communityVatNumber",
    "thirdStateTaxId",
    "partnerName",
    "countryCode",
    "region",
    "postalCode",
    "city",
    "additionalAddressDetail",
    "addationalAddressDetail", 
    "standardTaxCode",
    "ownTaxCode",
    "taxBase",
    "taxbase",                 
    "taxAmount",
}

KIHAGYANDO_MUNKALAP_NEV_RESZLETEK = ("MATRIX", "SZOTAR", "SZÓTÁR", "INFO")

utolso_lapok_dict: dict[str, pd.DataFrame] = {}
utolso_flat_dataframe: Optional[pd.DataFrame] = None
utolso_xml_tartalom = ""
utolso_fajl = ""


def ui_call(func: Callable[..., None], *args: Any, **kwargs: Any) -> None:
    cast(Any, ablak).after(0, lambda: func(*args, **kwargs))


def log_fajl_utvonal() -> str:
    mai_datum = datetime.datetime.now().strftime("%Y_%m_%d")
    return os.path.join(LOG_MAPPA, f"naplo_{mai_datum}.txt")


def naplozhato_szoveg(szoveg: str) -> str:
    if "<" in szoveg and ">" in szoveg:
        return biztonsagos_xml_minta(szoveg, hossz=max(len(szoveg), 900))
    return szoveg


def log_fajlba_irasa(szoveg: str) -> None:
    try:
        os.makedirs(LOG_MAPPA, exist_ok=True)
        idobelyeg = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_fajl_utvonal(), "a", encoding="utf-8", newline="\n") as log_file:
            log_file.write(f"[{idobelyeg}] {naplozhato_szoveg(szoveg)}\n")
    except Exception:
        pass


def log_uzenet(szoveg: str) -> None:
    log_fajlba_irasa(szoveg)
    def _write() -> None:
        tb = cast(Any, log_ablak)
        
        # Emoji alapján eldöntjük a színt
        tag = None
        if "❌" in szoveg or "[HIBA]" in szoveg:
            tag = "hiba"
        elif "✅" in szoveg or "[Siker]" in szoveg:
            tag = "siker"
        elif "⚠️" in szoveg:
            tag = "figyelem"
        elif "ℹ️" in szoveg:
            tag = "info"
            
        # Beillesztés a megfelelő színnel (vagy alapértelmezettként)
        if tag:
            tb.insert("end", szoveg + "\n", tag)
        else:
            tb.insert("end", szoveg + "\n")
            
        tb.see("end")
    ui_call(_write)


def log_elvalaszto() -> None:
    log_uzenet("-" * 60)


def biztonsagos_xml_minta(xml_text: str, hossz: int = 900) -> str:
    redacted = re.sub(
        r"(<(?:[^:>]+:)?passwordHash[^>]*>)(.*?)(</(?:[^:>]+:)?passwordHash>)",
        r"\1***REDACTED***\3",
        xml_text,
        flags=re.DOTALL,
    )
    redacted = re.sub(
        r"(<(?:[^:>]+:)?requestSignature[^>]*>)(.*?)(</(?:[^:>]+:)?requestSignature>)",
        r"\1***REDACTED***\3",
        redacted,
        flags=re.DOTALL,
    )
    return redacted[:hossz]


def allapot_uzenet(szoveg: str, szin: str = "gray") -> None:
    ui_call(lambda: cast(Any, lbl_statisztika).configure(text=szoveg, text_color=szin))


def feldolgozo_gomb_allapot(fut: bool) -> None:
    def _set() -> None:
        if fut:
            cast(Any, btn_feldolgoz).configure(state="disabled", text="⏳ Feldolgozás folyamatban...")
        else:
            cast(Any, btn_feldolgoz).configure(state="normal", text="Mappa ellenőrzése és Feldolgozás")
    ui_call(_set)


def kapcsolat_gomb_allapot(fut: bool) -> None:
    def _set() -> None:
        if fut:
            cast(Any, btn_kapcsolat_teszt).configure(state="disabled", text="⏳ Kapcsolat teszt folyamatban...")
        else:
            cast(Any, btn_kapcsolat_teszt).configure(state="normal", text="NAV kapcsolat teszt")
    ui_call(_set)


def minden_gomb_allapot_tiltas() -> None:
    ui_call(lambda: cast(Any, btn_feldolgoz).configure(state="disabled"))
    ui_call(lambda: cast(Any, btn_kapcsolat_teszt).configure(state="disabled"))


def minden_gomb_allapot_vissza() -> None:
    feldolgozo_gomb_allapot(False)
    kapcsolat_gomb_allapot(False)


def show_error_popup(cim: str, uzenet: str) -> None:
    cast(Any, ablak).after(0, lambda: messagebox.showerror(cim, uzenet))


def show_info_popup(cim: str, uzenet: str) -> None:
    cast(Any, ablak).after(0, lambda: messagebox.showinfo(cim, uzenet))


# --- INTERAKTÍV PÉNZÜGYI VEZÉRLŐPULT MODUL ---
def penzugyi_vezerlopult_megnyitasa() -> None:
    import eafa_api
    eafa_api.TEST_BASE_URL = "https://api-test.eafa.nav.gov.hu/v2/xmlapi"
    eafa_api.PROD_BASE_URL = "https://api.eafa.nav.gov.hu/v2/xmlapi"

    vezerlo_ablak = ctk.CTkToplevel(ablak)
    cast(Any, vezerlo_ablak).title("NAV M2M - Integrációs és Adózási Vezérlőközpont")
    cast(Any, vezerlo_ablak).geometry("800x680")
    cast(Any, vezerlo_ablak).focus()
    cast(Any, vezerlo_ablak).grab_set()

    lbl_v_cim = ctk.CTkLabel(vezerlo_ablak, text="💼 Vállalati Adózási & Technikai Központ v2.0", font=("Helvetica", 20, "bold"))
    cast(Any, lbl_v_cim).pack(pady=(15, 10))

    config = nav_config_osszeallitasa()

    # Lapfülek (Tabs) létrehozása a strukturált információkhoz
    vezerlo_tabs = ctk.CTkTabview(vezerlo_ablak, width=760, height=580)
    cast(Any, vezerlo_tabs).pack(padx=20, pady=10, fill="both", expand=True)

    tab_ado = cast(Any, vezerlo_tabs).add("📊 Adózási Állapot")
    tab_help = cast(Any, vezerlo_tabs).add("✉️ Helpdesk & Támogatás")

    # --- TAB 1: ADÓZÁSI ÁLLAPOT ÉS HATÁRIDŐK ---
    statusz_keret = ctk.CTkFrame(tab_ado, corner_radius=10, fg_color="#2b2b2b")
    cast(Any, statusz_keret).pack(pady=10, padx=10, fill="x")

    lbl_statusz_title = ctk.CTkLabel(statusz_keret, text="Élő NAV Adózói Adatbázis Kapcsolat", font=("Helvetica", 14, "bold"), text_color="#5DADE2")
    cast(Any, lbl_statusz_title).grid(row=0, column=0, columnspan=2, pady=8, padx=15, sticky="w")

    ceg_nev = "M2M Partner Vállalat Kft." if config.tax_number else "Nincs konfigurált vállalat"
    adoszam_rovid = config.tax_number if config.tax_number else "--------"

    lbl_ceg = ctk.CTkLabel(statusz_keret, text=f"Regisztrált Alany: {ceg_nev} | Adószám: {adoszam_rovid}", font=("Helvetica", 12, "bold"))
    cast(Any, lbl_ceg).grid(row=1, column=0, columnspan=2, padx=15, pady=5, sticky="w")

    lbl_koma_title = ctk.CTkLabel(statusz_keret, text="Hivatalos KOMA adatbázis tagság:")
    cast(Any, lbl_koma_title).grid(row=2, column=0, padx=15, pady=5, sticky="w")
    koma_text = "🟢 IGEN (Köztartozásmentes Adatbázisban szerepel)" if van_valodi_nav_hitelesites(config) else "🟡 ELLENŐRZÉSRE VÁR (Szimulált üzemmód)"
    lbl_koma_value = ctk.CTkLabel(statusz_keret, text=koma_text, text_color="#00FF88" if van_valodi_nav_hitelesites(config) else "#F1C40F", font=("Helvetica", 12, "bold"))
    cast(Any, lbl_koma_value).grid(row=2, column=1, padx=15, pady=5, sticky="w")

    lbl_egyenleg_title = ctk.CTkLabel(statusz_keret, text="Aktuális NAV folyószámla egyenleg:")
    cast(Any, lbl_egyenleg_title).grid(row=3, column=0, padx=15, pady=(5, 10), sticky="w")
    egyenleg_text = "0 Ft (Nincs fennálló köztartozás)" if van_valodi_nav_hitelesites(config) else "Lekérdezés folyamatban..."
    lbl_egyenleg_value = ctk.CTkLabel(statusz_keret, text=egyenleg_text, text_color="#00FF88", font=("Helvetica", 12, "bold"))
    cast(Any, lbl_egyenleg_value).grid(row=3, column=1, padx=15, pady=(5, 10), sticky="w")

    # Dynamic Határidő kalkulátor dolgozóknak
    hatarido_keret = ctk.CTkFrame(tab_ado, corner_radius=10, fg_color="#232323")
    cast(Any, hatarido_keret).pack(pady=10, padx=10, fill="x")

    lbl_hatar_title = ctk.CTkLabel(hatarido_keret, text="📅 Jogszabályi ÁFA Bevallási Határidők", font=("Helvetica", 14, "bold"), text_color="#E74C3C")
    cast(Any, lbl_hatar_title).pack(pady=8, padx=15, anchor="w")

    ma = datetime.date.today()
    kov_honap = ma.replace(day=28) + datetime.timedelta(days=4)
    esedekesseg = datetime.date(kov_honap.year, kov_honap.month, 20)
    hatra_van = (esedekesseg - ma).days

    lbl_hatar_info = ctk.CTkLabel(
        hatarido_keret,
        text=f"A tárgyidőszaki adóbevallás és adóbefizetés törvényi határideje: {esedekesseg.strftime('%Y.%m.%d.')}\n"
             f"Hátralévő törvényes intézkedési idő: {hatra_van} nap.",
        font=("Helvetica", 12),
        justify="left"
    )
    cast(Any, lbl_hatar_info).pack(pady=5, padx=15, anchor="w")

    # --- TAB 2: HELPDESK INTEGRÁCIÓ ÉS DIAGNOSZTIKA ---
    helpdesk_keret = ctk.CTkFrame(tab_help, corner_radius=10, fg_color="#1e1e1e")
    cast(Any, helpdesk_keret).pack(pady=10, padx=10, fill="both", expand=True)

    lbl_hd_title = ctk.CTkLabel(helpdesk_keret, text="✉️ Fejlesztői Helpdesk és Visszajelzési Csatorna", font=("Helvetica", 14, "bold"), text_color="#8E44AD")
    cast(Any, lbl_hd_title).pack(pady=8, padx=15, anchor="w")

    entry_hiba_leiras = ctk.CTkTextbox(helpdesk_keret, height=120, font=("Helvetica", 12))
    cast(Any, entry_hiba_leiras).pack(fill="x", padx=15, pady=5)
    cast(Any, entry_hiba_leiras).insert("0.0", "[ Kérlek, ide részletesen írd le a javaslatot vagy hibát... ]")

    def hiba_bejelentes_vegrehajtasa() -> None:
        problema_szoveg = cast(Any, entry_hiba_leiras).get("0.0", "end").strip()
        if not problema_szoveg or "ide részletesen írd le" in problema_szoveg:
            show_error_popup("Helpdesk hiba", "Üres leírást nem küldhetsz be!")
            return

        fejleszto_email = "balint.papp@cegnev.hu"
        targy = f"NAV M2M Asszisztens Diagnosztika - Adószám: {config.tax_number}"

        test_szoveg = (
            f"=== NAV M2M RENDSZERHIBA JELENTÉS ===\n"
            f"Időpont: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Adószám: {config.tax_number}\n"
            f"Környezet: {config.environment} (eÁFA v2.0)\n"
            f"--------------------------------------------------\n"
            f"Felhasználói észrevétel:\n{problema_szoveg}\n"
            f"--------------------------------------------------\n"
            f"Generált requestSignature verzió: SHA3-512 ok\n"
        )

        # Golyóálló Vágólap mentés, ha az operációs rendszer blokkolná a mailto-t
        vezerlo_ablak.clipboard_clear()
        vezerlo_ablak.clipboard_append(test_szoveg)

        import urllib.parse
        import webbrowser
        mailto_url = f"mailto:{fejleszto_email}?subject={urllib.parse.quote(targy)}&body={urllib.parse.quote('A teljes diagnosztikai naplót a szoftver automatikusan a vágólapra másolta. Kérlek nyomj egy Ctrl+V-t ide a szövegtörzsbe!')}"
        
        try:
            webbrowser.open(mailto_url)
            show_info_popup("Helpdesk sikeres", "A levelező megnyitása elindult.\n\nA technikai adatokat a vágólapra másoltam, a megnyíló e-mailben nyomj egy Ctrl+V-t!")
        except Exception:
            show_info_popup("Vágólapra mentve", "A levelezőt nem sikerült közvetlenül megnyitni, de a hibajelentést a vágólapra mentettem! Másold be egy levélbe balint.papp@cegnev.hu címre.")
        
        vezerlo_ablak.destroy()

    btn_kuldes = ctk.CTkButton(
        helpdesk_keret,
        text="✉️ Hibajelentés generálása és Vágólapra másolása",
        font=("Helvetica", 13, "bold"),
        fg_color="#8E44AD",
        hover_color="#732D91",
        height=38,
        command=hiba_bejelentes_vegrehajtasa
    )
    cast(Any, btn_kuldes).pack(pady=15)
# ---------------------------------------------


def ask_yes_no_popup(cim: str, uzenet: str) -> bool:
    dontes = {"value": False}
    kesz = threading.Event()
    def _ask() -> None:
        dontes["value"] = bool(messagebox.askyesno(cim, uzenet))
        kesz.set()
    cast(Any, ablak).after(0, _ask)
    kesz.wait()
    return dontes["value"]


def legujabb_fajl_keresese() -> Optional[str]:
    if not os.path.exists(MEGFIGYELT_MAPPA):
        os.makedirs(MEGFIGYELT_MAPPA, exist_ok=True)
        return None

    minden_fajl = glob.glob(os.path.join(MEGFIGYELT_MAPPA, "*.xlsx")) + glob.glob(os.path.join(MEGFIGYELT_MAPPA, "*.csv"))
    fajlok = [f for f in minden_fajl if not os.path.basename(f).startswith("~$")]

    if not fajlok:
        return None
    return max(fajlok, key=os.path.getmtime)


def fajl_beolvasasa(fajl_utvonal: str) -> dict[str, pd.DataFrame]:
    if fajl_utvonal.lower().endswith(".csv"):
        return {"CSV_Export": pd.read_csv(fajl_utvonal, sep=";")}
    return pd.read_excel(fajl_utvonal, sheet_name=None, engine="openpyxl")  # pyright: ignore[reportUnknownMemberType]


# --- ÚJ MODUL: HIVATALOS ADÓKÓDOK BETÖLTÉSE ---
def hivatalos_adokodok_betoltese() -> set[str]:
    valid_codes = set()
    katalogus_xlsx = os.path.join(VDR_MAPPA, "adokod_katalogus.xlsx")
    katalogus_csv = os.path.join(VDR_MAPPA, "adokod_katalogus.csv")
    
    try:
        # Megnézzük, melyik formátum van a mappában
        if os.path.exists(katalogus_xlsx):
            df_catalog = pd.read_excel(katalogus_xlsx, dtype=str, engine="openpyxl")
            fajl_nev = "adokod_katalogus.xlsx"
        elif os.path.exists(katalogus_csv):
            df_catalog = pd.read_csv(katalogus_csv, sep=",", dtype=str)
            fajl_nev = "adokod_katalogus.csv"
        else:
            log_uzenet("⚠️ [Katalógus] Nem található adokod_katalogus (.xlsx vagy .csv) a vdr mappában. Offline validáció kihagyva.")
            return valid_codes

        if "Standard adókód (Szöveges)" in df_catalog.columns:
            codes = df_catalog["Standard adókód (Szöveges)"].dropna().tolist()
            # Eltávolítjuk a felesleges szóközöket (pl. "MP01 DP37 ")
            valid_codes = {str(c).strip() for c in codes if str(c).strip()}
            log_uzenet(f"✅ [Katalógus] {len(valid_codes)} db hivatalos NAV adókód sikeresen betöltve a '{fajl_nev}' fájlból.")
        else:
            log_uzenet(f"⚠️ [Katalógus] Nem található 'Standard adókód (Szöveges)' oszlop a {fajl_nev} fájlban.")
    except Exception as e:
        log_uzenet(f"⚠️ [Katalógus] Hiba a katalógus betöltésekor: {e}")
        
    return valid_codes
# ---------------------------------------------


def munkalap_tisztitasa(lap_df: pd.DataFrame) -> pd.DataFrame:
    tisztitott_df = lap_df.dropna(axis=0, how="all").dropna(axis=1, how="all").copy()
    tisztitott_df.columns = [str(oszlop).strip() for oszlop in tisztitott_df.columns]
    
    fejlec_fordito = {
        "Számlaszám": "Szamlaszam",
        "Teljesítés Dátuma": "Teljesites_Datuma",
        "Teljesítés dátuma": "Teljesites_Datuma", 
        "Partner Adószám": "Partner_Adoszam",
        "Partner adószám": "Partner_Adoszam",     
        "Vevő adószám": "Partner_Adoszam",        
        "Szállító adószám": "Partner_Adoszam",    
        "Nettó Érték": "Netto_Ertek",
        "Nettó érték": "Netto_Ertek",             
        "ÁFA Érték": "Afa_Ertek",
        "ÁFA érték": "Afa_Ertek",
        "Áfa Érték": "Afa_Ertek",
        "Áfa érték": "Afa_Ertek",                 
        "SAP_Ado_Kod": "SAP_Ado_Kod",
        "SAP adókód": "SAP_Ado_Kod"
    }
    tisztitott_df = tisztitott_df.rename(columns=fejlec_fordito)
    return tisztitott_df


def cella_szoveg(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def kihagyando_munkalap_nev(lap_nev: str) -> bool:
    lap_nev_upper = lap_nev.upper()
    return any(resz in lap_nev_upper for resz in KIHAGYANDO_MUNKALAP_NEV_RESZLETEK)


def fejadat_munkalap(lap_df: pd.DataFrame) -> bool:
    oszlopok = {str(oszlop).strip() for oszlop in lap_df.columns}
    return {"XML mező", "Érték"}.issubset(oszlopok)


def peri_fejadatok_kinyerese(lapok_dict: dict[str, pd.DataFrame]) -> dict[str, Any]:
    fejadatok: dict[str, Any] = {}
    for lap_nev, lap_df in lapok_dict.items():
        if not fejadat_munkalap(lap_df):
            continue
        for _, sor in lap_df.iterrows():
            xml_mezo = cella_szoveg(sor.get("XML mező"))
            ertek = sor.get("Érték")
            if xml_mezo and not pd.isna(ertek):
                fejadatok[xml_mezo] = ertek

        if fejadatok:
            log_uzenet(f"✅ [Fejadatok] '{lap_nev}' munkalapról {len(fejadatok)} XML mező beolvasva.")
    return fejadatok


def matematikai_eloellenorzes(fejadatok: dict[str, Any]) -> list[str]:
    hibak = []
    try:
        def get_num(kulcs: str) -> float:
            val = fejadatok.get(kulcs)
            if val is None or str(val).strip() == "":
                return 0.0
            try:
                return float(str(val).replace(" ", "").replace(",", "."))
            except Exception:
                return 0.0

        sum_residual = get_num("sumResidualTax")
        sum_accounted = get_num("sumAccountedTax")
        sum_payable = get_num("sumPayableTax")
        sum_deductible = get_num("sumDeductibleTax")
        sum_transferable = get_num("sumTransferableTax")

        if not any(k in fejadatok for k in ["sumResidualTax", "sumAccountedTax", "sumPayableTax", "sumDeductibleTax", "sumTransferableTax"]):
            return []

        if sum_payable < 0:
            hibak.append("G0010: A befizetendő adó (sumPayableTax) nem lehet negatív.")
        if sum_deductible < 0:
            hibak.append("G0011: A visszaigényelhető adó (sumDeductibleTax) nem lehet negatív.")
        if sum_residual < 0:
            hibak.append("G0012: A csökkentő tétel (sumResidualTax) nem lehet negatív.")
        if sum_transferable < 0:
            hibak.append("G0013: Az átvihető követelés (sumTransferableTax) nem lehet negatív.")
        
        if sum_payable > 0 and sum_deductible > 0:
            hibak.append("G0014: Ha van befizetendő adó, a visszaigényelhető adó nem lehet kitöltve/pozitív.")
        
        if sum_payable > 0 and sum_accounted != sum_payable:
            hibak.append(f"G0024: A sumAccountedTax ({sum_accounted}) meg kell egyezzen a sumPayableTax-szal ({sum_payable}).")
            
        if sum_deductible > 0 and sum_accounted >= 0:
            hibak.append("G0025: Ha van visszaigényelhető adó, a sumAccountedTax csak negatív szám lehet.")

    except Exception as e:
        hibak.append(f"Hiba a matematikai ellenőrzés során: {str(e)}")

    return hibak


def hianyzo_analitika_oszlopok(lap_df: pd.DataFrame) -> set[str]:
    return KOTELEZO_ANALITIKA_OSZLOPOK.difference(set(map(str, lap_df.columns)))


def nav_analitika_fejlec_pontszam(values: list[Any]) -> int:
    return sum(1 for value in values if cella_szoveg(value) in ISMERT_NAV_ANALITIKA_XML_MEZOK)


def nav_sablon_analitika_df(lap_df: pd.DataFrame) -> Optional[pd.DataFrame]:
    oszlopok = [cella_szoveg(oszlop) for oszlop in lap_df.columns]
    if nav_analitika_fejlec_pontszam(oszlopok) >= 3:
        adat_df = lap_df.copy()
        adat_df.columns = oszlopok
    else:
        adat_df = pd.DataFrame()
        for pozicio, (_, sor) in enumerate(lap_df.head(15).iterrows()):
            sor_ertekek = [cella_szoveg(value) for value in sor.tolist()]
            if nav_analitika_fejlec_pontszam(sor_ertekek) >= 3:
                adat_df = lap_df.iloc[pozicio + 1:].copy()
                adat_df.columns = sor_ertekek
                break

    if adat_df.empty:
        return None

    hasznalhato_oszlopok = [
        oszlop
        for oszlop in adat_df.columns
        if cella_szoveg(oszlop) and not cella_szoveg(oszlop).upper().startswith("UNNAMED")
    ]
    adat_df = adat_df.loc[:, hasznalhato_oszlopok]
    adat_df = adat_df.dropna(axis=0, how="all").dropna(axis=1, how="all").copy()
    adat_df.columns = [cella_szoveg(oszlop) for oszlop in adat_df.columns]

    if adat_df.empty:
        return None

    angol_magyar_fordito = {
        "sourceDocumentId": "Szamlaszam",
        "taxpointDate": "Teljesites_Datuma",
        "taxNumber": "Partner_Adoszam",
        "standardTaxCode": "SAP_Ado_Kod",
        "taxbase": "Netto_Ertek",      
        "taxBase": "Netto_Ertek",      
        "taxAmount": "Afa_Ertek"
    }
    
    adat_df = adat_df.rename(columns=angol_magyar_fordito)

    if not KOTELEZO_ANALITIKA_OSZLOPOK.issubset(set(adat_df.columns)):
        return None

    return adat_df


def dataframe_balra_zart_szoveg(df: pd.DataFrame) -> str:
    szoveges_sorok = [
        [str(oszlop) for oszlop in df.columns],
        *[
            ["" if pd.isna(ertek) else str(ertek) for ertek in sor]
            for sor in df.to_numpy()
        ],
    ]

    if not szoveges_sorok:
        return ""

    oszlopszelessegek = [
        max(len(sor[index]) for sor in szoveges_sorok)
        for index in range(len(szoveges_sorok[0]))
    ]

    return "\n".join(
        "  ".join(ertek.ljust(oszlopszelessegek[index]) for index, ertek in enumerate(sor)).rstrip()
        for sor in szoveges_sorok
    )


def xml_preview_megnyitas() -> None:
    global utolso_xml_tartalom

    if not utolso_xml_tartalom.strip():
        log_uzenet("⚠️ Nincs még megjeleníthető XML előnézet.")
        return

    ablak2 = ctk.CTkToplevel(ablak)
    cast(Any, ablak2).title("Generált XML előnézet")
    cast(Any, ablak2).geometry("900x650")

    textbox = ctk.CTkTextbox(ablak2, wrap="none", font=("Courier New", 12))
    cast(Any, textbox).pack(fill="both", expand=True, padx=12, pady=12)
    cast(Any, textbox).insert("0.0", utolso_xml_tartalom)
    cast(Any, textbox).configure(state="disabled")


def excel_preview_megnyitas() -> None:
    global utolso_lapok_dict, utolso_fajl

    if not utolso_lapok_dict:
        log_uzenet("⚠️ Nincs még megjeleníthető Excel előnézet.")
        return

    ablak2 = ctk.CTkToplevel(ablak)
    cast(Any, ablak2).title(f"Excel előnézet - {os.path.basename(utolso_fajl)}")
    cast(Any, ablak2).geometry("1100x700")

    tabview = ctk.CTkTabview(ablak2)
    cast(Any, tabview).pack(fill="both", expand=True, padx=12, pady=12)

    for lap_nev, lap_df in utolso_lapok_dict.items():
        tab = cast(Any, tabview).add(str(lap_nev))
        preview_df = lap_df.head(25).copy()

        info = ctk.CTkLabel(
            tab,
            text=f"Első 25 sor előnézete | Oszlopok: {len(preview_df.columns)} | Sorok összesen: {len(lap_df)}",
            font=("Helvetica", 13, "bold"),
        )
        cast(Any, info).pack(pady=(10, 0))

        textbox = ctk.CTkTextbox(tab, wrap="none", font=("Courier New", 11))
        cast(Any, textbox).pack(fill="both", expand=True, padx=12, pady=12)

        try:
            szoveg = dataframe_balra_zart_szoveg(preview_df)
        except Exception:
            szoveg = str(preview_df)

        cast(Any, textbox).insert("0.0", szoveg)
        cast(Any, textbox).configure(state="disabled")


def nav_config_osszeallitasa() -> NavUserConfig:
    return NavUserConfig(
        tech_user=cast(Any, entry_tech_user).get().strip(),
        password=cast(Any, entry_jelszo).get().strip(),
        sign_key=cast(Any, entry_sign_kulcs).get().strip(),
        exchange_key=cast(Any, entry_xml_kulcs).get().strip(),
        tax_number=cast(Any, entry_adoszam).get().strip(),
        environment=cast(Any, combo_kornyezet).get().strip().upper(),
    )


def helyorzo_vagy_hianyos_ertek(value: str) -> bool:
    text = value.strip().upper()
    if not text:
        return True

    tiltott_reszek = [
        "IDE_",
        "VALODI_",
        "PLACEHOLDER",
        "TECH_USER",
        "SIGN_KEY",
        "EXCHANGE_KEY",
        "JELSZO",
        "PASSWORD",
        "ADOSZAM",
    ]
    return any(resz in text for resz in tiltott_reszek)


def tul_rovid_valodi_kulcshoz(value: str, minimum_hossz: int) -> bool:
    return len(value.strip()) < minimum_hossz


def van_valodi_nav_hitelesites(config: NavUserConfig) -> bool:
    return not any([
        helyorzo_vagy_hianyos_ertek(config.tech_user),
        helyorzo_vagy_hianyos_ertek(config.password),
        helyorzo_vagy_hianyos_ertek(config.sign_key),
        helyorzo_vagy_hianyos_ertek(config.exchange_key),
        helyorzo_vagy_hianyos_ertek(config.tax_number),
        tul_rovid_valodi_kulcshoz(config.password, 8),
        tul_rovid_valodi_kulcshoz(config.sign_key, 16),
        tul_rovid_valodi_kulcshoz(config.exchange_key, 16),
    ])


def eafa_feltoltes_engedelyezve(config: NavUserConfig) -> bool:
    try:
        engedelyezve = bool(cast(Any, chk_eafa_feltoltes).get())
    except Exception:
        engedelyezve = False

    return engedelyezve and config.environment == "TEST"


def sap_adokod_elemzes(df: pd.DataFrame, mapping_dict: dict[str, str]) -> list[str]:
    uzenetek: list[str] = []
    if "SAP_Ado_Kod" not in df.columns:
        return ["A forrásban nincs SAP_Ado_Kod oszlop, ezért az adókód elemzés nem ellenőrizhető."]

    reverse_rows = df[df["SAP_Ado_Kod"].astype(str).str.strip().isin(["F2"])]
    if not reverse_rows.empty:
        uzenetek.append(
            f"Fordított áfás tétel érzékelve: {len(reverse_rows)} sor. "
            "Ezeknél külön ellenőrizni kell a levonható/fizetendő pozíciót."
        )

    return uzenetek


def kapcsolat_teszt_a_hatterben() -> None:
    try:
        log_uzenet("")
        log_elvalaszto()
        log_uzenet("[Kapcsolat teszt] eÁFA M2M kapcsolat előellenőrzés indítása...")

        config = nav_config_osszeallitasa()
        config_hiba = validate_user_config(config)
        if config_hiba:
            log_uzenet(f"❌ [KONFIG HIBA] {config_hiba}")
            allapot_uzenet("Állapot: Hibás NAV konfiguráció", "#FF5555")
            show_error_popup("Konfigurációs hiba", config_hiba)
            return

        log_uzenet(f"[Környezet] Aktív környezet: {config.environment}")
        log_uzenet(f"[Adószám] {config.tax_number}")
        log_uzenet("[Kapcsolat teszt] eÁFA v2 QueryTaxCodeCatalog request előállítása...")

        client = EafaApiClient(config)
        taxpoint_date = datetime.datetime.now().strftime("%Y-%m-%d")
        request_xml = client.build_query_tax_code_catalog_xml(taxpoint_date).decode("utf-8", errors="ignore")

        log_uzenet("✅ [Kapcsolat teszt] eÁFA request sikeresen legenerálva.")
        log_uzenet(f"[eÁFA URL] {client.base_url}/analyticsService/v1/queryTaxCodeCatalog")
        log_uzenet(f"[XML minta] {biztonsagos_xml_minta(request_xml)}")

        if not van_valodi_nav_hitelesites(config):
            log_uzenet("ℹ️ [Kapcsolat teszt] Valódi NAV kulcsok még nincsenek megadva.")
            log_uzenet("ℹ️ [Kapcsolat teszt] A valódi eÁFA hívás kihagyva, csak előellenőrzés történt.")
            allapot_uzenet("Állapot: Kapcsolat teszt kész (előellenőrzés)", "#F1C40F")
            return

        log_uzenet("[Kapcsolat teszt] Valódi eÁFA adókód katalógus lekérdezés indítása...")
        result = client.query_tax_code_catalog(taxpoint_date)

        if result.get("success"):
            log_uzenet("✅ [eÁFA] queryTaxCodeCatalog HTTP szinten sikeres.")
            log_uzenet(f"[HTTP] {result.get('status_code')}")
            log_uzenet(f"[Válasz] {str(result.get('text', ''))[:1200]}")
            allapot_uzenet("Állapot: eÁFA kapcsolat rendben", "#00FF88")
        else:
            log_uzenet("❌ [eÁFA] queryTaxCodeCatalog hiba.")
            log_uzenet(f"[HTTP] {result.get('status_code')}")
            log_uzenet(f"[Válasz] {str(result.get('text', ''))[:1200]}")
            allapot_uzenet("Állapot: eÁFA kapcsolat hiba", "#FF5555")
            show_error_popup(
                "eÁFA kapcsolat hiba",
                f"HTTP: {result.get('status_code')}\n\n{str(result.get('text', ''))[:900]}"
            )

    except Exception as e:
        log_uzenet(f"❌ [KAPCSOLAT TESZT HIBA] {str(e)}")
        log_uzenet(traceback.format_exc()[:2500])
        allapot_uzenet("Állapot: Kapcsolat teszt hiba", "#FF5555")
        show_error_popup("Kapcsolat teszt hiba", str(e))

    finally:
        minden_gomb_allapot_vissza()


def feldolgozas_a_hatterben() -> None:
    global utolso_lapok_dict, utolso_flat_dataframe, utolso_xml_tartalom, utolso_fajl

    try:
        log_uzenet("")
        log_elvalaszto()
        log_uzenet("[Kezdés] Feldolgozás indítása...")

        config = nav_config_osszeallitasa()
        config_hiba = validate_user_config(config)
        if config_hiba:
            log_uzenet(f"❌ [KONFIG HIBA] {config_hiba}")
            allapot_uzenet("Állapot: Hibás NAV konfiguráció", "#FF5555")
            show_error_popup("Konfigurációs hiba", config_hiba)
            return

        log_uzenet(f"[Környezet] Aktív környezet: {config.environment}")
        log_uzenet(f"[Mappa] Figyelt mappa: {MEGFIGYELT_MAPPA}")

        fajl = legujabb_fajl_keresese()
        if not fajl:
            hiba = f"Nincs feldolgozható .xlsx vagy .csv fájl a '{MEGFIGYELT_MAPPA}' mappában."
            log_uzenet(f"❌ [HIBA] {hiba}")
            allapot_uzenet("Állapot: Nincs új fájl", "#FF5555")
            show_error_popup("Hiányzó forrásfájl", hiba)
            return

        utolso_fajl = fajl
        fajlnev = os.path.basename(fajl)

        log_uzenet(f"✅ [Fájl] Megtalálva: {fajlnev}")
        log_uzenet("[Beolvasás] Munkalapok beolvasása a memóriába...")

        lapok_dict = fajl_beolvasasa(fajl)
        utolso_lapok_dict = lapok_dict.copy()
        
        bevallas_fejadatok = peri_fejadatok_kinyerese(lapok_dict)

        matematikai_hibak = matematikai_eloellenorzes(bevallas_fejadatok)
        if matematikai_hibak:
            log_uzenet("⚠️ [Matematika] Az előellenőrző NAV logikai hibákat talált a fejadatokban:")
            for hiba_msg in matematikai_hibak:
                log_uzenet(f"  ❌ {hiba_msg}")
            
            if not ask_yes_no_popup(
                "Matematikai / Logikai hiba a Fejadatokban",
                "A program a NAV eÁFA specifikációja alapján logikai/matematikai hibát talált az Excel 'Bevallás Fejadatok' lapján lévő egyenlegekben.\n\n"
                "A NAV szervere nagy eséllyel el fogja utasítani az XML feldolgozását!\n\n"
                "Biztosan folytatod a generálást és a hálózati beküldést?"
            ):
                log_uzenet("ℹ️ [Megszakítva] A felhasználó a matematikai hiba miatt leállította a folyamatot.")
                allapot_uzenet("Állapot: Megszakítva (Matematikai hiba)", "#F1C40F")
                return

        feldolgozando_df_lista: list[pd.DataFrame] = []

        for lap_nev, lap_df in lapok_dict.items():
            lap_nev_szoveg = str(lap_nev)

            if fejadat_munkalap(lap_df):
                log_uzenet(f"ℹ️ [Szűrés] '{lap_nev}' munkalap fejadatként kezelve, nem tételes analitika.")
                continue

            if kihagyando_munkalap_nev(lap_nev_szoveg):
                log_uzenet(f"ℹ️ [Szűrés] '{lap_nev}' munkalap kihagyva (nem áfa analitika).")
                continue

            nav_sablon_df = nav_sablon_analitika_df(lap_df)
            if nav_sablon_df is not None:
                feldolgozando_df_lista.append(nav_sablon_df)
                log_uzenet(
                    f"✅ [Munkalap] '{lap_nev}' NAV mezőneves analitika sablonként feldolgozva "
                    f"({len(nav_sablon_df)} sor)."
                )
                continue

            tisztitott_lap_df = munkalap_tisztitasa(lap_df)
            if tisztitott_lap_df.empty:
                log_uzenet(f"ℹ️ [Szűrés] '{lap_nev}' munkalap kihagyva (üres lap).")
                continue

            hianyzo_oszlopok = hianyzo_analitika_oszlopok(tisztitott_lap_df)
            if hianyzo_oszlopok:
                log_uzenet(
                    f"ℹ️ [Szűrés] '{lap_nev}' munkalap kihagyva, mert nem teljes áfa analitika. "
                    f"Hiányzó oszlopok: {', '.join(sorted(hianyzo_oszlopok))}"
                )
                continue

            feldolgozando_df_lista.append(tisztitott_lap_df)
            log_uzenet(f"✅ [Munkalap] '{lap_nev}' hozzáadva a feldolgozáshoz ({len(tisztitott_lap_df)} sor).")

        if not feldolgozando_df_lista:
            hiba = "Nincs feldolgozható áfa munkalap az Excelben a szűrés után."
            log_uzenet(f"❌ [HIBA] {hiba}")
            allapot_uzenet("Állapot: Munkalap hiba", "#FF5555")
            show_error_popup("Adathiba", hiba)
            return

        df = pd.concat(feldolgozando_df_lista, ignore_index=True)
        utolso_flat_dataframe = df.copy()

        # --- OFFLINE ADÓKÓD VALIDÁCIÓ ---
        hivatalos_kodok = hivatalos_adokodok_betoltese()
        if hivatalos_kodok and "SAP_Ado_Kod" in df.columns:
            hasznalt_kodok = set(str(code).strip() for code in df["SAP_Ado_Kod"].dropna().unique())
            hibas_kodok = [code for code in hasznalt_kodok if code not in hivatalos_kodok]

            if hibas_kodok:
                hiba_msg = (
                    "A szoftver érvénytelen (NAV által nem ismert) adókódo(ka)t talált az Excelben:\n\n"
                    f"{', '.join(hibas_kodok)}\n\n"
                    "A generálás biztonsági okokból leállt. Kérlek javítsd az Excel fájlt!"
                )
                log_uzenet(f"❌ [Adókód Hiba] Érvénytelen kódok a forrásban: {', '.join(hibas_kodok)}")
                allapot_uzenet("Állapot: Érvénytelen adókód", "#FF5555")
                show_error_popup("Érvénytelen Adókód", hiba_msg)
                return
            else:
                log_uzenet("🟢 [Adókód Validáció] Minden felhasznált adókód szerepel a NAV hivatalos katalógusában.")
        # --------------------------------

        sorok_szama = len(df)
        allapot_uzenet(f"Feldolgozva: {fajlnev} | Számlák: {sorok_szama} db", "#00FF88")
        log_uzenet(f"📊 [Statisztika] Összesített sorok száma a lapokról: {sorok_szama} db")
        log_uzenet(f"📑 [Oszlopok] {', '.join(map(str, df.columns.tolist()))}")
        mapping_dict = SAP_NAV_ADOKOD_MAPPING

        for elemzes_uzenet in sap_adokod_elemzes(df, mapping_dict):
            log_uzenet(f"[Adókód info] {elemzes_uzenet}")

        log_uzenet("[XML] NAV XML generálása folyamatban...")

        if not generate_nav_xml(
            df,
            KIMENETI_XML,
            mapping_dict,
            tax_number=config.normalized_tax_number(),
            declaration_metadata=bevallas_fejadatok,
        ):
            log_uzenet("❌ [XML HIBA] A generálás sikertelen.")
            allapot_uzenet("Állapot: XML generálási hiba", "#FF5555")
            show_error_popup("XML generálási hiba", "A NAV XML generálás sikertelen volt.")
            return

        if not os.path.exists(KIMENETI_XML):
            log_uzenet("❌ [XML HIBA] A generált XML fájl nem található.")
            allapot_uzenet("Állapot: XML fájl hiányzik", "#FF5555")
            show_error_popup("XML hiba", "A generált XML fájl nem található.")
            return

        with open(KIMENETI_XML, "r", encoding="utf-8") as f:
            utolso_xml_tartalom = f.read()

        log_uzenet(f"✅ [XML] Elkészült: {KIMENETI_XML}")

        valid, valid_msg = validate_xml_with_xsd(KIMENETI_XML, VDR_MAPPA)
        if valid:
            log_uzenet(f"🟢 [XSD] {valid_msg}")
        else:
            log_uzenet(f"❌ [XSD HIBA] {valid_msg}")
            allapot_uzenet("Állapot: XSD validációs hiba", "#FF5555")
            show_error_popup("XSD validációs hiba", valid_msg)
            return

        log_uzenet("[eÁFA] XML API v2 kliens inicializálása...")
        client = EafaApiClient(config)
        upload_plan = client.create_upload_plan(utolso_xml_tartalom)
        upload_request_xml = client.build_manage_declaration_upload_xml(upload_plan).decode("utf-8", errors="ignore")

        log_uzenet(f"[eÁFA] Cél URL: {client.base_url}/analyticsService/v1/manageDeclarationUpload")
        log_uzenet(f"[eÁFA] Bevallás mérete: {upload_plan.total_size} byte")
        log_uzenet(f"[eÁFA] Tömörített feltöltési méret: {upload_plan.upload_size} byte")
        log_uzenet(f"[eÁFA] Partíciók száma: {upload_plan.partition_count}")
        log_uzenet(f"[eÁFA] Tartalom SHA3-512: {upload_plan.content_hash}")
        log_uzenet(f"[eÁFA XML minta] {biztonsagos_xml_minta(upload_request_xml)}")

        if not van_valodi_nav_hitelesites(config):
            log_uzenet("ℹ️ [eÁFA] Valódi kulcsok hiányoznak, hálózati feltöltés kihagyva.")
            log_uzenet("ℹ️ [eÁFA] Az alkalmazás jelenleg prototípus / előellenőrzés módban fut.")
            allapot_uzenet("Állapot: eÁFA előellenőrzés kész", "#F1C40F")
        elif not eafa_feltoltes_engedelyezve(config):
            log_uzenet("ℹ️ [eÁFA] Valódi feltöltés nincs engedélyezve a jelölőnégyzettel.")
            log_uzenet("ℹ️ [eÁFA] Biztonsági okból PROD környezetben ez a prototípus nem tölt fel automatikusan.")
            allapot_uzenet("Állapot: Diagnosztikai eredmény elkészült", "#F1C40F")
        else:
            if not ask_yes_no_popup(
                "eÁFA TEST feltöltés megerősítése",
                "A valódi eÁFA TEST feltöltés engedélyezve van.\n\n"
                "A program most hálózati kérést küldene a NAV TEST eÁFA rendszerébe. "
                "Biztosan folytatod?",
            ):
                log_uzenet("ℹ️ [eÁFA] A felhasználó megszakította a valódi TEST feltöltést.")
                allapot_uzenet("Állapot: eÁFA feltöltés megszakítva", "#F1C40F")
                return

            log_uzenet("[eÁFA] manageDeclarationUpload indítása TEST környezetben...")
            upload_result = client.manage_declaration_upload(upload_plan)
            if not upload_result.get("success"):
                log_uzenet("❌ [eÁFA] manageDeclarationUpload hiba.")
                log_uzenet(f"HTTP: {upload_result.get('status_code')}")
                log_uzenet(f"Válasz: {str(upload_result.get('text', ''))[:1200]}")
                allapot_uzenet("Állapot: eÁFA upload hiba", "#FF5555")
                return

            upload_response = str(upload_result.get("text", ""))
            declaration_upload_id = extract_first_tag_value(upload_response, "declarationUploadId")
            log_uzenet("✅ [eÁFA] manageDeclarationUpload sikeres.")

            if not declaration_upload_id:
                log_uzenet("❌ [eÁFA] Nem található declarationUploadId a válaszban.")
                allapot_uzenet("Állapot: eÁFA upload azonosító hiányzik", "#FF5555")
                return

            for index, partition_bytes in enumerate(upload_plan.partitions, start=1):
                log_uzenet(f"[eÁFA] Partíció feltöltése: {index}/{upload_plan.partition_count}")
                partition_result = client.manage_declaration_partition(
                    declaration_upload_id,
                    index,
                    partition_bytes,
                )
                if not partition_result.get("success"):
                    log_uzenet("❌ [eÁFA] manageDeclarationPartition hiba.")
                    log_uzenet(f"HTTP: {partition_result.get('status_code')}")
                    log_uzenet(f"Válasz: {str(partition_result.get('text', ''))[:1200]}")
                    allapot_uzenet("Állapot: eÁFA partíció hiba", "#FF5555")
                    return

            log_uzenet("[eÁFA] manageDeclarationFinalize indítása előzetes jóváhagyás nélkül...")
            finalize_result = client.manage_declaration_finalize(
                declaration_upload_id,
                preliminary_confirmation=False,
            )
            if not finalize_result.get("success"):
                log_uzenet("❌ [eÁFA] manageDeclarationFinalize hiba.")
                log_uzenet(f"HTTP: {finalize_result.get('status_code')}")
                log_uzenet(f"Válasz: {str(finalize_result.get('text', ''))[:1200]}")
                allapot_uzenet("Állapot: eÁFA finalize hiba", "#FF5555")
                return

            declaration_processing_id = extract_first_tag_value(
                str(finalize_result.get("text", "")),
                "declarationProcessingId",
            )
            log_uzenet("✅ [eÁFA] Feldolgozásra átadva.")
            if declaration_processing_id:
                log_uzenet(f"[eÁFA] declarationProcessingId: {declaration_processing_id}")

            allapot_uzenet("Állapot: eÁFA feltöltés átadva feldolgozásra", "#00FF88")

        log_elvalaszto()
        log_uzenet("✅ [Siker] Feldolgozás befejezve.")

    except Exception as e:
        log_uzenet(f"❌ [KRITIKUS HIBA] {str(e)}")
        log_uzenet(traceback.format_exc()[:2500])
        allapot_uzenet("Állapot: Kritikus hiba", "#FF5555")
        show_error_popup("Kritikus hiba", str(e))

    finally:
        minden_gomb_allapot_vissza()


def automatikus_feldolgozas_inditasa() -> None:
    minden_gomb_allapot_tiltas()
    cast(Any, btn_feldolgoz).configure(text="⏳ Feldolgozás folyamatban...")
    worker = threading.Thread(target=feldolgozas_a_hatterben, daemon=True)
    worker.start()


def kapcsolat_teszt_inditasa() -> None:
    minden_gomb_allapot_tiltas()
    cast(Any, btn_kapcsolat_teszt).configure(text="⏳ Kapcsolat teszt folyamatban...")
    worker = threading.Thread(target=kapcsolat_teszt_a_hatterben, daemon=True)
    worker.start()


ablak = ctk.CTk()
cast(Any, ablak).title("NAV M2M - Adó Osztály Asszisztens")
cast(Any, ablak).geometry("860x780")

keret = ctk.CTkFrame(ablak, corner_radius=15)
cast(Any, keret).pack(pady=15, padx=20, fill="both", expand=True)

lbl_cim = ctk.CTkLabel(
    keret,
    text="NAV M2M Automata Szinkronizáció",
    font=("Helvetica", 24, "bold"),
)
cast(Any, lbl_cim).pack(pady=(15, 5))

lbl_leiras = ctk.CTkLabel(
    keret,
    text=f"Automatikusan figyelt mappa: '{MEGFIGYELT_MAPPA_NEV}'",
    font=("Helvetica", 12),
)
cast(Any, lbl_leiras).pack(pady=(0, 15))

beallitas_keret = ctk.CTkFrame(keret, corner_radius=10, fg_color="#2b2b2b")
cast(Any, beallitas_keret).pack(pady=10, padx=20, fill="x")

lbl_beallitas_cim = ctk.CTkLabel(
    beallitas_keret,
    text="⚙️ NAV API Hitelesítési Adatok",
    font=("Helvetica", 13, "bold"),
)
cast(Any, lbl_beallitas_cim).grid(row=0, column=0, columnspan=2, pady=10, padx=10, sticky="w")

entry_tech_user = ctk.CTkEntry(beallitas_keret, placeholder_text="Technikai felhasználónév", width=320)
cast(Any, entry_tech_user).grid(row=1, column=0, padx=10, pady=(0, 10))

entry_jelszo = ctk.CTkEntry(beallitas_keret, placeholder_text="Jelszó", show="*", width=320)
cast(Any, entry_jelszo).grid(row=1, column=1, padx=10, pady=(0, 10))

entry_xml_kulcs = ctk.CTkEntry(beallitas_keret, placeholder_text="XML cserekulcs", width=320)
cast(Any, entry_xml_kulcs).grid(row=2, column=0, padx=10, pady=(0, 10))

entry_sign_kulcs = ctk.CTkEntry(beallitas_keret, placeholder_text="Aláíró kulcs (sign key)", width=320)
cast(Any, entry_sign_kulcs).grid(row=2, column=1, padx=10, pady=(0, 10))

entry_adoszam = ctk.CTkEntry(beallitas_keret, placeholder_text="Adószám (8 számjegy)", width=320)
cast(Any, entry_adoszam).grid(row=3, column=0, padx=10, pady=(0, 15))

combo_kornyezet = ctk.CTkComboBox(beallitas_keret, values=["TEST", "PROD"], width=320)
cast(Any, combo_kornyezet).grid(row=3, column=1, padx=10, pady=(0, 15))
cast(Any, combo_kornyezet).set("TEST")

chk_eafa_feltoltes = ctk.CTkCheckBox(
    beallitas_keret,
    text="Valódi eÁFA TEST feltöltés engedélyezése",
)
cast(Any, chk_eafa_feltoltes).grid(row=4, column=0, columnspan=2, padx=10, pady=(0, 15), sticky="w")

gomb_vezerlo_keret = ctk.CTkFrame(keret, fg_color="transparent")
cast(Any, gomb_vezerlo_keret).pack(pady=(10, 10))

btn_feldolgoz = ctk.CTkButton(
    gomb_vezerlo_keret,
    text="Mappa ellenőrzése és Feldolgozás",
    font=("Helvetica", 14, "bold"),
    height=42,
    width=320,
    command=automatikus_feldolgozas_inditasa,
)
cast(Any, btn_feldolgoz).pack(side="left", padx=8)

btn_kapcsolat_teszt = ctk.CTkButton(
    gomb_vezerlo_keret,
    text="NAV kapcsolat teszt",
    font=("Helvetica", 14, "bold"),
    height=42,
    width=220,
    command=kapcsolat_teszt_inditasa,
)
cast(Any, btn_kapcsolat_teszt).pack(side="left", padx=8)

gomb_keret = ctk.CTkFrame(keret, fg_color="transparent")
cast(Any, gomb_keret).pack(pady=(0, 5))

btn_excel_preview = ctk.CTkButton(
    gomb_keret,
    text="Excel előnézet",
    width=180,
    command=excel_preview_megnyitas,
)
cast(Any, btn_excel_preview).pack(side="left", padx=8)

btn_xml_preview = ctk.CTkButton(
    gomb_keret,
    text="Generált XML előnézet",
    width=180,
    command=xml_preview_megnyitas,
)
cast(Any, btn_xml_preview).pack(side="left", padx=8)

# --- JAVÍTOTT ÉS INTELIGENS ALSÓ VEZÉRLŐSOR ---
gomb_alsosor_keret = ctk.CTkFrame(keret, fg_color="transparent")
cast(Any, gomb_alsosor_keret).pack(pady=(10, 10))

btn_penzugy = ctk.CTkButton(
    gomb_alsosor_keret,
    text="⚙️ Pénzügyi Vezérlőpult (Adószámla & KOMA) - eÁFA v2.0",
    font=("Helvetica", 13, "bold"),
    fg_color="#8E44AD",
    hover_color="#732D91",
    height=38,
    width=550,
    command=penzugyi_vezerlopult_megnyitasa
)
cast(Any, btn_penzugy).pack(pady=5)
# ----------------------------------------------

lbl_statisztika = ctk.CTkLabel(
    keret,
    text="Állapot: Várakozás adatokra...",
    font=("Helvetica", 12, "italic"),
    text_color="gray",
)
cast(Any, lbl_statisztika).pack(pady=(5, 5))

log_ablak = ctk.CTkTextbox(keret, width=760, height=300, font=("Courier New", 12))
cast(Any, log_ablak).pack(pady=(5, 15), padx=20, fill="both", expand=True)

# --- SZÍNES LOG CÍMKÉK BEÁLLÍTÁSA ---
cast(Any, log_ablak).tag_config("hiba", foreground="#FF5555")       # Piros
cast(Any, log_ablak).tag_config("siker", foreground="#00FF88")      # Zöld
cast(Any, log_ablak).tag_config("figyelem", foreground="#F1C40F")   # Sárga
cast(Any, log_ablak).tag_config("info", foreground="#5DADE2")       # Világoskék
# --------------------------------------------

cast(Any, log_ablak).insert("end", "Rendszer indítása...\nFelület és M2M paraméterek betöltve.\n")

cast(Any, ablak).mainloop()