# core/analitika.py
# NAV M2M Üzleti logika és adatfeldolgozó motor.
# Kezeli az Excel/CSV importálást, tisztítást és adókód validációt.

from __future__ import annotations

import os
from typing import Any, Optional, cast

import pandas as pd


def dataframe_balra_zart_szoveg(df: pd.DataFrame) -> str:
    """
    Formázza a DataFrame-et balra zárt szövegként az előnézethez.
    """
    return df.to_string(justify='left')


def fajl_beolvasasa(fajl_utvonal: str) -> dict[str, pd.DataFrame]:
    """
    Beolvassa a megadott fájlt (Excel vagy CSV) és visszaadja a munkalapokat egy szótárban.
    """
    if not os.path.exists(fajl_utvonal):
        return {}
    
    if fajl_utvonal.endswith('.csv'):
        df = pd.read_csv(fajl_utvonal)
        return {os.path.basename(fajl_utvonal): df}
    else:
        # Excel esetén kényszerítjük a típust a linter megnyugtatására
        return cast(dict[str, pd.DataFrame], pd.read_excel(fajl_utvonal, sheet_name=None))


def peri_fejadatok_kinyerese(lapok_dict: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """
    Kinyeri a bevallás fejadatokat a 'Bevallás Fejadatok' vagy hasonló nevű munkalapról.
    """
    metadata: dict[str, Any] = {}
    for sheet_name, df in lapok_dict.items():
        if "fejadat" in sheet_name.lower():
            for _, row in df.iterrows():
                if len(row) >= 2:
                    k = str(row.iloc[0]).strip().lower()
                    v = row.iloc[1]
                    if pd.isna(v) or not k:
                        continue
                    
                    if "adószám" in k or "taxnumber" in k:
                        metadata["taxNumber"] = str(v).strip()
                    elif "típus" in k or "declarationtype" in k:
                        metadata["declarationType"] = str(v).strip()
                    elif "fajta" in k or "declarationkind" in k:
                        metadata["declarationKind"] = str(v).strip()
                    elif "gyakoriság" in k or "declarationfrequency" in k:
                        metadata["declarationFrequency"] = str(v).strip()
                    elif "kezdet" in k or "periodstart" in k:
                        metadata["declarationPeriodStart"] = v
                    elif "vég" in k or "periodend" in k:
                        metadata["declarationPeriodEnd"] = v
                    elif "verzió" in k or "version" in k:
                        metadata["version"] = str(v).strip()
                    elif "módszer" in k or "declarationmethod" in k:
                        metadata["declarationMethod"] = str(v).strip()
                    elif "korrekció" in k or "navcorrection" in k:
                        metadata["navCorrection"] = v
    return metadata


def matematikai_eloellenorzes(bevallas_fejadatok: dict[str, Any]) -> list[str]:
    """
    Logikai és dátum ellenőrzéseket hajt végre a bevallás fejadatokon.
    """
    errors: list[str] = []
    start = bevallas_fejadatok.get("declarationPeriodStart")
    end = bevallas_fejadatok.get("declarationPeriodEnd")
    
    if start and end:
        try:
            if isinstance(start, str):
                start = pd.to_datetime(start)
            if isinstance(end, str):
                end = pd.to_datetime(end)
            if start > end:
                errors.append("A bevallási időszak kezdete nem lehet későbbi, mint a vége.")
        except Exception:
            pass
            
    return errors


def fejadat_munkalap(lap_df: pd.DataFrame) -> bool:
    """
    Eldönti egy munkalapról a struktúrája alapján, hogy fejadat-e.
    """
    if lap_df.empty:
        return False
        
    text_sample = "".join(str(val).lower() for val in lap_df.iloc[:5, :2].values.flatten())
    return "adószám" in text_sample or "bevallás" in text_sample or "időszak" in text_sample


def kihagyando_munkalap_nev(lap_nev_szoveg: str) -> bool:
    """
    Kiszűri a nem releváns munkalapneveket.
    """
    nev = lap_nev_szoveg.lower().strip()
    return "fejadat" in nev or "értékek" in nev or "summary" in nev or "vdr" in nev or "history" in nev


def nav_sablon_analitika_df(lap_df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    Ha a munkalap már eleve a hivatalos NAV sémás mezőneveket tartalmazza, visszaadja azt.
    """
    required_fields = {"sourcedocumentid", "taxpointdate", "taxbase", "taxamount"}
    cols = {str(c).strip().lower() for c in lap_df.columns}
    if required_fields.issubset(cols):
        return lap_df
    return None


def munkalap_tisztitasa(lap_df: pd.DataFrame) -> pd.DataFrame:
    """
    Megtisztítja a munkalapot a teljesen üres soroktól és oszlopoktól.
    """
    if lap_df.empty:
        return lap_df
    return lap_df.dropna(how="all")


def hianyzo_analitika_oszlopok(tisztitott_lap_df: pd.DataFrame) -> set[str]:
    """
    Ellenőrzi, hogy megvannak-e a minimálisan szükséges áfa-analitika oszlopok.
    """
    cols = {str(c).strip().lower() for c in tisztitott_lap_df.columns}
    
    has_id = any(x in cols for x in ["sourcedocumentid", "szamlaszam", "invoicenumber"])
    has_date = any(x in cols for x in ["taxpointdate", "sourcedocumentissuedate", "teljesites_datuma"])
    has_base = any(x in cols for x in ["taxbase", "netto_ertek"])
    has_amount = any(x in cols for x in ["taxamount", "afa_ertek"])
    
    missing: set[str] = set()
    if not has_id:
        missing.add("Szamlaszam")
    if not has_date:
        missing.add("Teljesites_Datuma")
    if not has_base:
        missing.add("Netto_Ertek")
    if not has_amount:
        missing.add("Afa_Ertek")
        
    return missing


def hivatalos_adokodok_betoltese() -> set[str]:
    """
    Betölti a hivatalos NAV adókódokat az adókatalógusból.
    """
    path = os.path.join("vdr", "adokod_katalogus.xlsx - Adókód_20240113.csv")
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            if not df.empty:
                return set(str(val).strip() for val in df.iloc[:, 0].dropna().unique())
        except Exception:
            pass
    return {"A1", "A2", "A3", "A4", "E1", "E2", "E3", "E4", "DOM_L_GENERAL"}


def sap_adokod_elemzes(df: pd.DataFrame, mapping_dict: dict[str, str]) -> list[str]:
    """
    Statisztikát készít az Excelben talált SAP adókódokról és azok NAV párjáról.
    """
    messages: list[str] = []
    code_col = None
    for col in df.columns:
        if str(col).strip().lower() in ["sap_ado_kod", "owntaxcode"]:
            code_col = col
            break
            
    if code_col is not None:
        counts = df[code_col].value_counts()
        for code, count in counts.items():
            code_str = str(code).strip()
            nav_code = mapping_dict.get(code_str, "DOM_L_GENERAL")
            messages.append(f"Kód: {code_str} -> NAV: {nav_code} ({count} db számla)")
    else:
        messages.append("Nem található azonosítható SAP_Ado_Kod vagy ownTaxCode oszlop az elemzéshez.")
        
    return messages