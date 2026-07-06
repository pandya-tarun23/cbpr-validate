from __future__ import annotations

from lxml import etree

# Message families recognised by root-element namespace. Order does not matter;
# each token is unique within an ISO 20022 namespace URN.
_KNOWN_TYPES = ("pacs.008", "pacs.009", "pacs.002", "pacs.004")


def detect_message_type(xml_bytes: bytes) -> str | None:
    """Detect a message type like 'pacs.008' from the XML namespace.

    Checks the root element's namespace first, then falls back to scanning
    child elements (covers documents wrapped in an outer envelope).
    """
    try:
        root = etree.fromstring(xml_bytes)
    except Exception:
        return None

    ns = etree.QName(root).namespace or ""
    for msg_type in _KNOWN_TYPES:
        if msg_type in ns:
            return msg_type

    # fallback: search child elements for a known namespace
    for elem in root.iter():
        qn = etree.QName(elem)
        if not qn.namespace:
            continue
        for msg_type in _KNOWN_TYPES:
            if msg_type in qn.namespace:
                return msg_type

    return None
