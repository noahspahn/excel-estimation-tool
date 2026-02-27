from __future__ import annotations

import os
from unittest.mock import patch

from backend.app.services.contract_store_service import ContractStoreService
from backend.app.services.proposal_store_service import ProposalStoreService


def test_proposal_store_memory_mode_roundtrip() -> None:
    with patch.dict(
        os.environ,
        {
            "PROPOSALS_TABLE_NAME": "",
            "PROPOSAL_VERSIONS_TABLE_NAME": "",
            "PROPOSAL_DOCUMENTS_TABLE_NAME": "",
        },
        clear=False,
    ):
        svc = ProposalStoreService()
        assert svc.mode() == "memory"
        assert svc.is_configured()

        proposal = svc.create_proposal(
            owner_email="dev@example.com",
            title="Proposal",
            payload={"hello": "world"},
        )
        assert proposal["proposal_id"]
        assert proposal["public_id"]

        v2 = svc.create_version(
            proposal_id=proposal["proposal_id"],
            owner_email="dev@example.com",
            title="Proposal v2",
            payload={"hello": "v2"},
        )
        assert int(v2["version"]) == 2

        versions = svc.list_versions(
            proposal_id=proposal["proposal_id"],
            owner_email="dev@example.com",
        )
        assert [int(v["version"]) for v in versions] == [1, 2]


def test_contract_store_memory_mode_roundtrip() -> None:
    with patch.dict(
        os.environ,
        {
            "CONTRACTS_TABLE_NAME": "",
            "CONTRACT_SYNC_TABLE_NAME": "",
        },
        clear=False,
    ):
        svc = ContractStoreService()
        assert svc.mode() == "memory"
        assert svc.is_configured()

        created = svc.create_contract({"title": "My Contract", "source": "manual", "status": "new"})
        assert created["contract_id"]

        fetched = svc.get_contract(created["contract_id"])
        assert fetched is not None
        assert fetched["title"] == "My Contract"

        updated = svc.update_contract(created["contract_id"], {"status": "submitted"})
        assert updated is not None
        assert updated["status"] == "submitted"

        svc.save_sync_state({"source": "sam.gov", "requests_today": 1})
        sync = svc.get_sync_state("sam.gov")
        assert sync is not None
        assert int(sync["requests_today"]) == 1
