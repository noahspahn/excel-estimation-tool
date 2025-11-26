from __future__ import annotations

import datetime as dt
import secrets
from typing import Any, Dict

from sqlalchemy import Column, DateTime, String, JSON, Integer, ForeignKey, text
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
