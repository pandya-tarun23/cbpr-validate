"""CBPR-ADDR-004 against the completed ISO 3166-1 alpha-2 snapshot.

The code set was a 10-country stub (DE ES FR GB IT JP NL NO SE US), so
CBPR-ADDR-004 rejected most of the world - RO, IN, AE, SG, CN among them. It now
carries the full 249 officially assigned codes.

These tests pin both halves of the contract: real codes are accepted, and the
rule still rejects genuine junk. A code set that accepts everything would make
the rule pointless, which is the failure mode worth guarding against.
"""

from __future__ import annotations

import pytest

from cbpr_validate.codesets.loader import get_codes, is_valid
from cbpr_validate.model.finding import Severity
from cbpr_validate.model.payment import Party, Payment, PostalAddress
from cbpr_validate.rules.address import cbpr_addr_004_country_code

COUNTRY_SET = "ISO3166-1-alpha-2"

# Assigned codes the old stub wrongly rejected.
VALID = ["RO", "IN", "AE", "SG", "CN"]
# Never officially assigned: user-assigned or simply not codes.
INVALID = ["XX", "ZZ"]


def _payment(country: str) -> Payment:
    address = PostalAddress(adr_line=["Main Street"], twn_nm="Bucharest", ctry=country)
    return Payment(
        message_type="pacs.008",
        dbtr=Party(name="Debtor Co", postal_address=address),
        cdtr=Party(name="Ardent Finance", postal_address=address),
    )


# --- the code set itself ---------------------------------------------------


@pytest.mark.parametrize("code", VALID)
def test_code_set_accepts_assigned_codes(code: str) -> None:
    assert is_valid(COUNTRY_SET, code)


@pytest.mark.parametrize("code", INVALID)
def test_code_set_rejects_unassigned_codes(code: str) -> None:
    assert not is_valid(COUNTRY_SET, code)


def test_code_set_is_the_complete_assigned_list() -> None:
    codes = get_codes(COUNTRY_SET)
    assert len(codes) == 249
    assert all(len(c) == 2 and c.isalpha() and c.isupper() for c in codes)


def test_code_set_excludes_codes_that_are_not_officially_assigned() -> None:
    """UK/EU are commonly mistaken for codes; AN/CS are withdrawn; XK is
    user-assigned. Accepting any of them would mean the list was guessed."""
    codes = get_codes(COUNTRY_SET)
    assert not codes & {"UK", "EU", "AN", "CS", "YU", "SU", "XK"}


# --- the rule ---------------------------------------------------------------


@pytest.mark.parametrize("code", VALID)
def test_addr004_accepts_assigned_country(code: str) -> None:
    assert cbpr_addr_004_country_code(_payment(code)) == []


@pytest.mark.parametrize("code", INVALID)
def test_addr004_rejects_unassigned_country(code: str) -> None:
    findings = cbpr_addr_004_country_code(_payment(code))
    # one per party, since both carry the same address
    assert len(findings) == 2
    assert all(f.rule_id == "CBPR-ADDR-004" for f in findings)
    assert all(f.severity is Severity.ERROR for f in findings)
    assert {f.location for f in findings} == {"Dbtr.PstlAdr.Ctry", "Cdtr.PstlAdr.Ctry"}


def test_addr004_is_case_sensitive() -> None:
    """ISO 3166-1 alpha-2 is uppercase; a lowercase 'ro' is not the code."""
    assert cbpr_addr_004_country_code(_payment("ro")) != []


def test_addr004_stays_silent_without_a_country() -> None:
    """Absence is CBPR-ADDR-002's job, not this rule's."""
    address = PostalAddress(adr_line=["Main Street"], twn_nm="Bucharest", ctry=None)
    payment = Payment(
        message_type="pacs.008",
        dbtr=Party(name="Debtor Co", postal_address=address),
        cdtr=Party(name="Ardent Finance", postal_address=address),
    )
    assert cbpr_addr_004_country_code(payment) == []
