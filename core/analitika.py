from __future__ import annotations

import os
from typing import Any, Optional

import pandas as pd

from config import *

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

