import datetime
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET
from typing import Any

import pandas as pd


NS_BASE = "http://schemas.nav.gov.hu/EAR/1.0/base"
NS_DATA = "http://schemas.nav.gov.hu/EAR/1.0/data"


def _q(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    return str(value).strip()


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    try:
        text_value = str(value).strip().replace(" ", "").replace(",", ".")
        if not text_value:
            return default
        return int(float(text_value))
    except Exception:
        return default


def _safe_bool_text(value: Any, default: str = "false") -> str:
    text_value = _safe_str(value, default).strip().lower()
    if text_value in {"true", "1", "yes", "igen"}:
        return "true"
    if text_value in {"false", "0", "no", "nem"}:
        return "false"
    return default


def _first_value(source: Any, names: list[str], default: Any = None) -> Any:
    for name in names:
        try:
            value = source.get(name)
        except Exception:
            value = None

        if value is None:
            continue

        try:
            if pd.isna(value):
                continue
        except Exception:
            pass

        if str(value).strip():
            return value

    return default


def _format_date(value: Any, default_date: str) -> str:
    if value is None:
        return default_date

    try:
        if pd.isna(value):
            return default_date
    except Exception:
        pass

    if hasattr(value, "strftime"):
        try:
            return value.strftime("%Y-%m-%d")
        except Exception:
            return default_date

    text_value = str(value).strip()
    if not text_value:
        return default_date

    normalized = text_value.replace(".", "-").replace("/", "-").split(" ")[0]
    if len(normalized) >= 10:
        return normalized[:10]

    return default_date


def _prettify_xml(root: ET.Element) -> str:
    raw_xml = ET.tostring(root, encoding="utf-8")
    pretty_xml = minidom.parseString(raw_xml).toprettyxml(indent="    ", encoding="utf-8")
    return pretty_xml.decode("utf-8")


def generate_nav_xml(
    df: pd.DataFrame,
    output_file: str,
    mapping_dict: dict[str, str],
    tax_number: str = "11223344",
    declaration_metadata: dict[str, Any] | None = None,
) -> bool:
    try:
        declaration_metadata = declaration_metadata or {}
        ET.register_namespace("earbase", NS_BASE)
        ET.register_namespace("n0", NS_DATA)

        root = ET.Element(_q(NS_DATA, "VatDeclarationData"))

        today = datetime.datetime.now()
        period_date = today.strftime("%Y-%m-%d")
        period_start = today.strftime("%Y-%m-01")

        declaration_info = ET.SubElement(root, _q(NS_DATA, "declarationInfo"))
        ET.SubElement(declaration_info, _q(NS_BASE, "taxNumber")).text = _safe_str(
            declaration_metadata.get("taxNumber"),
            tax_number,
        )
        ET.SubElement(declaration_info, _q(NS_BASE, "declarationType")).text = _safe_str(
            declaration_metadata.get("declarationType"),
            "NONE",
        )
        ET.SubElement(declaration_info, _q(NS_BASE, "declarationKind")).text = _safe_str(
            declaration_metadata.get("declarationKind"),
            "NONE",
        )
        ET.SubElement(declaration_info, _q(NS_BASE, "declarationFrequency")).text = _safe_str(
            declaration_metadata.get("declarationFrequency"),
            "MONTHLY",
        )
        ET.SubElement(declaration_info, _q(NS_BASE, "declarationPeriodStart")).text = _format_date(
            declaration_metadata.get("declarationPeriodStart"),
            period_start,
        )
        ET.SubElement(declaration_info, _q(NS_BASE, "declarationPeriodEnd")).text = _format_date(
            declaration_metadata.get("declarationPeriodEnd"),
            period_date,
        )
        ET.SubElement(declaration_info, _q(NS_BASE, "version")).text = _safe_str(
            declaration_metadata.get("version"),
            "1",
        )
        ET.SubElement(declaration_info, _q(NS_BASE, "declarationMethod")).text = _safe_str(
            declaration_metadata.get("declarationMethod"),
            "BASE",
        )
        ET.SubElement(declaration_info, _q(NS_BASE, "navCorrection")).text = _safe_bool_text(
            declaration_metadata.get("navCorrection"),
            "false",
        )

        analytics = ET.SubElement(root, _q(NS_DATA, "vatAnalytics"))
        ET.SubElement(analytics, _q(NS_DATA, "totalRowCount")).text = str(len(df))

        fizetendo_ado_osszesen = 0

        for row_number, (_, row) in enumerate(df.iterrows(), start=1):
            item = ET.SubElement(analytics, _q(NS_DATA, "vatAnalyticsItem"))
            ET.SubElement(item, _q(NS_DATA, "lineNumber")).text = str(row_number)

            szamlaszam = _safe_str(_first_value(
                row,
                ["sourceDocumentId", "Szamlaszam", "invoiceNumber"],
                f"INV-{row_number}",
            ))
            teljesites = _format_date(_first_value(
                row,
                ["taxpointDate", "sourceDocumentIssueDate", "Teljesites_Datuma"],
                period_date,
            ), period_date)
            netto = _safe_int(_first_value(row, ["taxBase", "Netto_Ertek"], 0), 0)
            afa_ertek = _safe_int(_first_value(row, ["taxAmount", "Afa_Ertek"], 0), 0)
            partner_status = _safe_str(_first_value(row, ["partnerStatus"], "DOMESTIC"), "DOMESTIC")
            partner_adoszam = _safe_str(_first_value(row, ["taxNumber", "Partner_Adoszam"], "11223344"), "11223344")
            partner_adoszam_8 = "".join(ch for ch in partner_adoszam if ch.isdigit())[:8] or "11223344"

            sap_code = _safe_str(_first_value(row, ["SAP_Ado_Kod", "ownTaxCode"], "A1"), "A1")
            nav_code = _safe_str(row.get("standardTaxCode"), "") or mapping_dict.get(sap_code, "DOM_L_GENERAL")

            fizetendo_ado_osszesen += afa_ertek

            ET.SubElement(item, _q(NS_DATA, "sourceDocumentId")).text = szamlaszam
            ET.SubElement(item, _q(NS_DATA, "sourceDocumentIssueDate")).text = teljesites
            ET.SubElement(item, _q(NS_DATA, "sourceDocumentType")).text = "INVOICE"
            ET.SubElement(item, _q(NS_DATA, "taxpointDate")).text = teljesites
            ET.SubElement(item, _q(NS_DATA, "invoiceModificationOrCancellation")).text = "false"

            partner_info = ET.SubElement(item, _q(NS_DATA, "partnerInfo"))
            ET.SubElement(partner_info, _q(NS_DATA, "partnerStatus")).text = partner_status

            partner_tax_data = ET.SubElement(partner_info, _q(NS_DATA, "partnerTaxData"))
            community_vat_number = _safe_str(row.get("communityVatNumber"))
            third_state_tax_id = _safe_str(row.get("thirdStateTaxId"))
            if community_vat_number:
                ET.SubElement(partner_tax_data, _q(NS_DATA, "communityVatNumber")).text = community_vat_number
            elif third_state_tax_id:
                ET.SubElement(partner_tax_data, _q(NS_DATA, "thirdStateTaxId")).text = third_state_tax_id
            else:
                domestic_tax_data = ET.SubElement(partner_tax_data, _q(NS_DATA, "domesticTaxData"))
                ET.SubElement(domestic_tax_data, _q(NS_DATA, "taxNumber")).text = partner_adoszam_8

            partner_name = _safe_str(row.get("partnerName"))
            if partner_name:
                ET.SubElement(partner_info, _q(NS_DATA, "partnerName")).text = partner_name

            tax_information = ET.SubElement(item, _q(NS_DATA, "taxInformation"))
            ET.SubElement(tax_information, _q(NS_DATA, "standardTaxCode")).text = nav_code

            tax_position = ET.SubElement(tax_information, _q(NS_DATA, "taxPosition"))
            ET.SubElement(tax_position, _q(NS_DATA, "positionType")).text = "PAYABLE"
            ET.SubElement(tax_position, _q(NS_DATA, "taxBase")).text = str(netto)
            ET.SubElement(tax_position, _q(NS_DATA, "taxAmount")).text = str(afa_ertek)

        summary = ET.SubElement(root, _q(NS_DATA, "declarationSummary"))
        ET.SubElement(summary, _q(NS_DATA, "sumResidualTax")).text = "0"
        ET.SubElement(summary, _q(NS_DATA, "sumAccountedTax")).text = str(fizetendo_ado_osszesen)
        ET.SubElement(summary, _q(NS_DATA, "sumPayableTax")).text = str(fizetendo_ado_osszesen)

        pretty_xml = _prettify_xml(root)

        with open(output_file, "w", encoding="utf-8", newline="\n") as file:
            file.write(pretty_xml)

        return True

    except Exception as exc:
        print(f"Hiba az XML generáláskor: {exc}")
        return False