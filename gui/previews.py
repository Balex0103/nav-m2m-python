# gui/previews.py
from __future__ import annotations

import os
import traceback
from typing import Any
from tkinter import messagebox
import customtkinter as ctk

# Explicit import a PyInstaller rögzítéséhez
import openpyxl  # type: ignore

from config import KIMENETI_XML, MEGFIGYELT_MAPPA


def excel_preview_megnyitas(tabs_instance: Any) -> None:
    """
    Megnyitja a legutóbb módosított Excel vagy CSV fájl előnézetét a megfigyelt mappából.
    Fülkezelővel (CTkTabview) külön választja a munkalapokat.
    UX REFAKTORÁLÁS: A wrap="none" kikényszerítésével letiltjuk a sortörést, így az analitika
    oszlopai katonás rendben, vízszintesen görgethetően jelennek meg.
    """
    from core.analitika import fajl_beolvasasa, dataframe_balra_zart_szoveg

    if not os.path.exists(MEGFIGYELT_MAPPA):
        messagebox.showerror("Hiba", f"A megfigyelt mappa nem létezik: {MEGFIGYELT_MAPPA}")
        return

    # Kiszűrjük a rejtett ideiglenes Excel zárolási fájlokat (~$)
    excel_fajlok = [
        f for f in os.listdir(MEGFIGYELT_MAPPA) 
        if f.endswith(('.xlsx', '.xls', '.csv')) and not f.startswith('~$')
    ]
    
    if not excel_fajlok:
        messagebox.showinfo("Infó", "Nincs feldolgozható Excel/CSV fájl a megfigyelt mappában.")
        return

    legfrissebb_fajl = max(
        [os.path.join(MEGFIGYELT_MAPPA, f) for f in excel_fajlok],
        key=os.path.getmtime
    )

    try:
        munkalapok = fajl_beolvasasa(legfrissebb_fajl)
        if not munkalapok:
            messagebox.showerror("Hiba", "A táblázat beolvasása sikertelen vagy üres fájlt találtam.")
            return

        # Előnézeti ablak létrehozása stabil fókusszal
        preview_ablak = ctk.CTkToplevel(tabs_instance)
        preview_ablak.title(f"Excel Előnézet - {os.path.basename(legfrissebb_fajl)}")
        preview_ablak.geometry("1000x700")
        
        preview_ablak.attributes("-topmost", True)
        preview_ablak.after(150, lambda: preview_ablak.attributes("-topmost", False))

        # Munkalap választó fülek létrehozása
        preview_tabs = ctk.CTkTabview(preview_ablak)
        preview_tabs.pack(fill="both", expand=True, padx=10, pady=10)

        has_visible_sheet = False
        for lap_nev, df in munkalapok.items():
            if not df.empty:
                has_visible_sheet = True
                tab_page = preview_tabs.add(lap_nev)
                formazott_szoveg = dataframe_balra_zart_szoveg(df)

                # BIZTONSÁGI UX FINOMHANGOLÁS: wrap="none" kikényszerítése a tökéletes rácsszerkezethez!
                szoveg_doboz = ctk.CTkTextbox(tab_page, font=ctk.CTkFont(family="Courier New", size=11), wrap="none")
                szoveg_doboz.pack(fill="both", expand=True, padx=5, pady=5)
                szoveg_doboz.insert("0.0", formazott_szoveg)
                szoveg_doboz.configure(state="disabled")

        if not has_visible_sheet:
            preview_ablak.destroy()
            messagebox.showinfo("Infó", "A kiválasztott fájl munkalapjai üresek.")
            
    except PermissionError:
        messagebox.showerror(
            "Fájl használatban", 
            f"A(z) '{os.path.basename(legfrissebb_fajl)}' fájl jelenleg meg van nyitva az Excelben!\n\n"
            f"Kérlek, zárd be az Excel programot, majd próbáld újra!"
        )
    except Exception as e:
        hiba_reszletek = traceback.format_exc()
        messagebox.showerror(
            "Excel Renderelési Hiba", 
            f"Nem sikerült az Excel előnézet generálása: {str(e)}\n\nTechnikai részletek:\n{hiba_reszletek}"
        )


def xml_preview_megnyitas(tabs_instance: Any) -> None:
    """
    Megnyitja a generált eÁFA 2.0 XML fájl előnézetét egy külön ablakban.
    """
    if not os.path.exists(KIMENETI_XML):
        messagebox.showerror(
            "Hiba", 
            "Nem található a generált XML fájl! Előbb futtasd le a feldolgozást."
        )
        return

    try:
        with open(KIMENETI_XML, "r", encoding="utf-8") as f:
            xml_tartalom = f.read()

        if hasattr(tabs_instance, "xml_elonezet"):
            tabs_instance.xml_elonezet.configure(state="normal")
            tabs_instance.xml_elonezet.delete("1.0", "end")
            tabs_instance.xml_elonezet.insert("0.0", xml_tartalom)
            tabs_instance.xml_elonezet.configure(state="disabled")

        preview_ablak = ctk.CTkToplevel(tabs_instance)
        preview_ablak.title("Generált NAV eÁFA 2.0 XML Előnézet")
        preview_ablak.geometry("850x650")
        
        preview_ablak.attributes("-topmost", True)
        preview_ablak.after(150, lambda: preview_ablak.attributes("-topmost", False))

        # XML-nél is letiltjuk a sortörést a tiszta fastruktúra megőrzése érdekében
        szoveg_doboz = ctk.CTkTextbox(preview_ablak, font=ctk.CTkFont(family="Courier New", size=11), wrap="none")
        szoveg_doboz.pack(fill="both", expand=True, padx=10, pady=10)
        szoveg_doboz.insert("0.0", xml_tartalom)
        szoveg_doboz.configure(state="disabled")
    except Exception as e:
        messagebox.showerror("Hiba", f"Nem sikerült beolvasni az XML fájlt: {str(e)}")