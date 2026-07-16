# core/template_generator.py
# Dedikált motor a hivatalos, gyári NAV eÁFA Excel sablon telepítéséhez.

from __future__ import annotations

import os
import shutil
import logging
from config import VDR_MAPPA

logger = logging.getLogger(__name__)


def mentett_mintasablon_gyartasa(target_path: str) -> None:
    """
    Átmásolja a hivatalos NAV sablonfájlt a szoftver belső vdr/ mappájából 
    közvetlenül a felhasználó Asztalára.
    
    Intelligens névellenőrzéssel támogatja az ékezetes és ékezet nélküli 
    fájlelnevezéseket is, elkerülve a Windows-specifikus elérési hibákat.
    """
    # Ellenőrizzük mindkét lehetséges elnevezést (ékezettel és anélkül is!)
    lehetseges_nevek = ["01_pelda_fizetendo.xlsx", "01_példa_fizetendő.xlsx"]
    forras_sablon = None
    
    for fajl_nev in lehetseges_nevek:
        teszt_utvonal = os.path.join(VDR_MAPPA, fajl_nev)
        if os.path.exists(teszt_utvonal):
            forras_sablon = teszt_utvonal
            break
            
    if not forras_sablon:
        logger.error(f"❌ A hivatalos NAV mintasablon nem található a {VDR_MAPPA} mappában.")
        raise FileNotFoundError(
            f"A hivatalos NAV mintasablon nem található a szoftver belső erőforrásai (vdr/) között.\n"
            f"Kérlek győződj meg róla, hogy a '01_pelda_fizetendo.xlsx' vagy '01_példa_fizetendő.xlsx' "
            f"fájl valóban be lett másolva a 'vdr/' mappába!"
        )
        
    try:
        shutil.copy(forras_sablon, target_path)
        logger.info(f"✅ Hivatalos NAV Excel sablon sikeresen átmásolva ide: {target_path}")
    except Exception as e:
        logger.error(f"❌ Nem sikerült a sablon fájl másolása: {str(e)}")
        raise e