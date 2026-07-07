from __future__ import annotations

import datetime
import os
import threading
import traceback
from typing import Any

import pandas as pd

from config import *
from nav.eafa_api import EafaApiClient, extract_first_tag_value
from nav.validators import validate_user_config, validate_xml_with_xsd
from nav.xml_generator import generate_nav_xml
from core.file_watcher import legujabb_fajl_keresese
from core.analitika import *
from services.ui_runtime import *
from services.nav_session import *
from gui import previews

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

