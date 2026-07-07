from __future__ import annotations

import os
from typing import Any, cast

import customtkinter as ctk

from utils.logger import logger
from core.analitika import dataframe_balra_zart_szoveg
from config import *

utolso_lapok_dict = {}
utolso_flat_dataframe = None
utolso_xml_tartalom = ''
utolso_fajl = ''

def xml_preview_megnyitas(ablak: Any) -> None:
    global utolso_xml_tartalom

    if not utolso_xml_tartalom.strip():
        logger.warning("⚠️ Nincs még megjeleníthető XML előnézet.")
        return

    ablak2 = ctk.CTkToplevel(ablak)
    cast(Any, ablak2).title("Generált XML előnézet")
    cast(Any, ablak2).geometry("900x650")

    textbox = ctk.CTkTextbox(ablak2, wrap="none", font=("Courier New", 12))
    cast(Any, textbox).pack(fill="both", expand=True, padx=12, pady=12)
    cast(Any, textbox).insert("0.0", utolso_xml_tartalom)
    cast(Any, textbox).configure(state="disabled")

def excel_preview_megnyitas(ablak: Any) -> None:
    global utolso_lapok_dict, utolso_fajl

    if not utolso_lapok_dict:
        logger.warning("⚠️ Nincs még megjeleníthető Excel előnézet.")
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

