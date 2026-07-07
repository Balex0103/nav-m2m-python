# nav/__init__.py
# NAV M2M / eÁFA API réteg csomag inicializálója.
# Exportálja a főbb klienseket és segédfüggvényeket.

from .eafa_api import EafaApiClient, extract_first_tag_value
from .auth import NavM2MAuth
from .document_api import NavDocumentApiClient
from .validators import validate_user_config, validate_xml_with_xsd
from .xml_generator import generate_nav_xml
from .xsd_generator import list_xsd_files, primary_xsd
from .deadlines import kovetkezo_afa_hatarido

__all__ = [
    "EafaApiClient",
    "extract_first_tag_value",
    "NavM2MAuth",
    "NavDocumentApiClient",
    "validate_user_config",
    "validate_xml_with_xsd",
    "generate_nav_xml",
    "list_xsd_files",
    "primary_xsd",
    "kovetkezo_afa_hatarido",
]