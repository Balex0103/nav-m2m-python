from __future__ import annotations

from tkinter import messagebox
from typing import Any, Callable, cast

import customtkinter as ctk

from config import *

ablak = None
log_ablak = None
lbl_statisztika = None
btn_feldolgoz = None
btn_kapcsolat_teszt = None
entry_tech_user = None
entry_jelszo = None
entry_sign_kulcs = None
entry_xml_kulcs = None
entry_adoszam = None
combo_kornyezet = None
chk_eafa_feltoltes = None

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

def ask_yes_no_popup(cim: str, uzenet: str) -> bool:
    dontes = {"value": False}
    kesz = threading.Event()
    def _ask() -> None:
        dontes["value"] = bool(messagebox.askyesno(cim, uzenet))
        kesz.set()
    cast(Any, ablak).after(0, _ask)
    kesz.wait()
    return dontes["value"]

