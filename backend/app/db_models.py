from __future__ import annotations

import datetime as dt
import secrets
from typing import Any, Dict

from sqlalchemy import Column, DateTime, String, JSON, Integer, ForeignKey, text, Text, Float, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.orm import declarative_base


Base = declarative_base()


def _gen_id(prefix: str = "prop") -> str:
    return f"{prefix}_{secrets.token_urlsafe(8)}"  # ~11 chars payload


def _gen_public_id() -> str:
    return secrets.token_urlsafe(9)  # ~12 chars, URL-safe


class Proposal(Base):
    __tablename__ = "proposals"

    id = Column(String(64), primary_key=True, default=_gen_id)
    public_id = Column(String(64), unique=True, nullable=False, index=True, default=_gen_public_id)
    title = Column(String(255), nullable=True)
    owner_email = Column(String(255), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    versions = relationship("ProposalVersion", back_populates="proposal", cascade="all, delete-orphan")
    documents = relationship("ProposalDocument", back_populates="proposal", cascade="all, delete-orphan")
    contracts = relationship("ContractOpportunity", back_populates="proposal", cascade="all, delete-orphan")


class ProposalVersion(Base):
    __tablename__ = "proposal_versions"

    id = Column(String(64), primary_key=True, default=lambda: _gen_id("ver"))
    proposal_id = Column(String(64), ForeignKey("proposals.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    title = Column(String(255), nullable=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    proposal = relationship("Proposal", back_populates="versions")


class ProposalDocument(Base):
    __tablename__ = "proposal_documents"

    id = Column(String(64), primary_key=True, default=lambda: _gen_id("doc"))
    proposal_id = Column(String(64), ForeignKey("proposals.id"), nullable=False, index=True)
    version = Column(Integer, nullable=True)
    kind = Column(String(32), nullable=False, default="report")  # report | attachment | source
    filename = Column(String(255), nullable=False)
    content_type = Column(String(128), nullable=True)
    bucket = Column(String(255), nullable=False)
    key = Column(String(512), nullable=False)
    size_bytes = Column(Integer, nullable=True)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    proposal = relationship("Proposal", back_populates="documents")


class ContractOpportunity(Base):
    __tablename__ = "contract_opportunities"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_contract_source"),
    )

    id = Column(String(64), primary_key=True, default=lambda: _gen_id("con"))
    source = Column(String(64), nullable=False, index=True, default="sam.gov")
    source_id = Column(String(128), nullable=True, index=True)
    title = Column(String(512), nullable=True)
    agency = Column(String(255), nullable=True)
    sub_agency = Column(String(255), nullable=True)
    office = Column(String(255), nullable=True)
    naics = Column(String(32), nullable=True)
    psc = Column(String(32), nullable=True)
    set_aside = Column(String(128), nullable=True)
    posted_at = Column(DateTime, nullable=True)
    due_at = Column(DateTime, nullable=True)
    value = Column(String(128), nullable=True)
    location = Column(String(255), nullable=True)
    url = Column(String(1024), nullable=True)
    synopsis = Column(Text, nullable=True)
    contract_excerpt = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="new", index=True)
    proposal_id = Column(String(64), ForeignKey("proposals.id"), nullable=True, index=True)
    report_submitted_at = Column(DateTime, nullable=True)
    decision_date = Column(DateTime, nullable=True)
    awardee_name = Column(String(255), nullable=True)
    award_value = Column(Float, nullable=True)
    award_notes = Column(Text, nullable=True)
    win_factors = Column(Text, nullable=True)
    loss_factors = Column(Text, nullable=True)
    analysis_notes = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)
    raw_payload = Column(JSON, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    proposal = relationship("Proposal", back_populates="contracts")


class ContractSyncState(Base):
    __tablename__ = "contract_sync_state"

    source = Column(String(64), primary_key=True)
    last_run_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    last_status = Column(String(32), nullable=True)
    requests_today = Column(Integer, nullable=False, default=0)
    requests_today_date = Column(String(10), nullable=True)
    last_result = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class ReportJob(Base):
    __tablename__ = "report_jobs"

    id = Column(String(64), primary_key=True, default=lambda: _gen_id("job"))
    owner_email = Column(String(255), nullable=False, index=True)
    job_kind = Column(String(32), nullable=False, index=True, default="report")
    status = Column(String(32), nullable=False, index=True, default="queued")
    request_payload = Column(JSON, nullable=False)
    result_payload = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
