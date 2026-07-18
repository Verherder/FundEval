from unittest.mock import MagicMock

from src.services.fund_service import FundService


def _service_with_funds():
    fund_repo = MagicMock()
    fund_repo.get_user_funds.return_value = {
        "000001": {"fund_name": "测试A", "is_hold": False, "sectors": []},
        "000002": {"fund_name": "测试B", "is_hold": True, "sectors": ["旧板块"]},
    }
    service = FundService(MagicMock(), fund_repo, MagicMock(), MagicMock(), MagicMock())
    return service, fund_repo


def test_hold_and_sector_updates_use_repository_without_minifund():
    service, fund_repo = _service_with_funds()

    service.set_hold(1, "000001", True)
    saved = fund_repo.save_user_funds.call_args.args[1]
    assert saved["000001"]["is_hold"] is True

    fund_repo.save_user_funds.reset_mock()
    service.set_sector(1, "000001, 000002", ["新能源"])
    saved = fund_repo.save_user_funds.call_args.args[1]
    assert saved["000001"]["sectors"] == ["新能源"]
    assert saved["000002"]["sectors"] == ["新能源"]

    fund_repo.save_user_funds.reset_mock()
    service.remove_sector(1, "000002")
    assert fund_repo.save_user_funds.call_args.args[1]["000002"]["sectors"] == []


def test_delete_fund_preserves_unselected_entries():
    service, fund_repo = _service_with_funds()

    service.delete_fund(1, "000001")

    saved = fund_repo.save_user_funds.call_args.args[1]
    assert "000001" not in saved
    assert "000002" in saved


def test_get_fund_list_does_not_construct_minifund():
    service, _fund_repo = _service_with_funds()

    result = service.get_fund_list(1)

    assert [fund["code"] for fund in result["data"]] == ["000001", "000002"]
    service._get_lan_fund.assert_not_called()
