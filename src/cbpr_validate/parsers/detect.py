from __future__ import annotations

from lxml import etree


def detect_message_type(xml_bytes: bytes) -> str | None:
    """Detect a message type like 'pacs.008' from the XML namespace or element names.

    This is intentionally lightweight for Phase 1: it looks for known pacs.008 namespaces.
    """
    try:
        root = etree.fromstring(xml_bytes)
    except Exception:
        return None

    ns = etree.QName(root).namespace or ""
    if "pacs.008" in ns:
        return "pacs.008"

    # fallback: search child elements for a pacs.008 namespace
    for elem in root.iter():
        qn = etree.QName(elem)
        if qn.namespace and "pacs.008" in qn.namespace:
            return "pacs.008"

    return None
