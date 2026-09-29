"""Closed vocabularies shared by every package. Stored as text in databases (never native enums)."""

from __future__ import annotations

from enum import StrEnum


class ScriptType(StrEnum):
    P2PKH = "p2pkh"
    P2SH = "p2sh"
    P2WPKH = "p2wpkh"
    P2WSH = "p2wsh"
    P2TR = "p2tr"
    UNKNOWN = "unknown"


class FileFormat(StrEnum):
    CSV = "csv"
    TSV = "tsv"
    JSON = "json"  # a JSON array of objects
    NDJSON = "ndjson"  # one JSON object per line
    XML = "xml"


class ObservationModel(StrEnum):
    """How the network layer was captured (detected from the data, blueprint §4.5)."""

    VANTAGE = "vantage"  # a few listening sensors record announcements from their peers
    FLOW = "flow"  # ISP-level flow records between arbitrary peers
    MIXED = "mixed"  # both
    SINGLE = "single"  # exactly one record per transaction: origin is "as reported"
    NONE = "none"  # no network fields: chain-only mode


class Method(StrEnum):
    """How an edge or claim was produced. Every derived edge names one (I2)."""

    OBS = "obs"
    PREVOUT = "prevout"
    ADDR_AMOUNT_MATCH = "addr_amount_match"
    CIOH = "cioh"
    CHANGE_MODEL = "change_model"
    PEEL_MODEL = "peel_model"
    ORIGIN_MODEL = "origin_model"
    AS_REPORTED = "as_reported"
    CONTROL_AGG = "control_agg"
    CO_ORIGIN = "co_origin"
    ER_MODEL = "er_model"
    EMBED_SIM = "embed_sim"
    ANALYST_ASSERTION = "analyst_assertion"
    GEOIP = "geoip"
    HAIRCUT = "haircut"
    PPR = "ppr"
    RULE = "rule"


class Family(StrEnum):
    """Independent kinds of evidence; a lead's grade counts how many support it."""

    NET = "NET"
    FLOW = "FLOW"
    TAINT = "TAINT"
    ANOM = "ANOM"
    BEHAV = "BEHAV"


class LeadType(StrEnum):
    ACTOR = "ACTOR"
    CASHOUT = "CASHOUT"
    CHAIN = "CHAIN"
    TX = "TX"
    IP = "IP"


class Grade(StrEnum):
    A = "A"
    B = "B"
    C = "C"


class LeadStatus(StrEnum):
    NEW = "NEW"
    IN_REVIEW = "IN_REVIEW"
    ESCALATED = "ESCALATED"
    CONFIRMED = "CONFIRMED"
    DISMISSED = "DISMISSED"
    SNOOZED = "SNOOZED"


class Role(StrEnum):
    ANALYST = "analyst"
    LEAD = "lead"
    ADMIN = "admin"
    AUDITOR = "auditor"
    DEMO = "demo"


class AppMode(StrEnum):
    DEV = "dev"
    DEMO = "demo"
    AIRGAP = "airgap"
