import os
import inspect

os.environ.setdefault('JWT_SECRET', 'test-secret')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_chat_router.db')

from backend.genlayer_client import GenLayerClientWrapper
from genlayer_py.client import create_client


def test_pinned_sdk_exposes_appeal_protocol_functions():
    client = object.__new__(GenLayerClientWrapper)
    client.network = 'studionet'
    chain = client._chain_config()
    available = set()
    for contract_name in ('appeals_contract', 'consensus_main_contract'):
        contract = getattr(chain, contract_name, None)
        if isinstance(contract, dict):
            available.update(
                entry.get('name')
                for entry in contract.get('abi', [])
                if entry.get('type') == 'function'
            )

    sdk_client = create_client(chain=chain, endpoint='http://127.0.0.1:4000/api')
    appeal_impl = sdk_client.appeal_transaction.__func__.__globals__['appeal_transaction']
    encode_impl = appeal_impl.__globals__['_encode_submit_appeal_data']
    print(inspect.getsource(encode_impl))
    print(sorted(name for name in dir(sdk_client) if 'appeal' in name.lower()))
    print(chain)
    print(chain.__dict__ if hasattr(chain, '__dict__') else dir(chain))
    assert 'submitAppeal' in available


import pytest
from web3 import Web3


@pytest.mark.asyncio
async def test_appeal_requirements_reads_authoritative_round_and_bond(monkeypatch):
    consensus_tx_id = '0x' + 'ab' * 32
    client = object.__new__(GenLayerClientWrapper)
    async def status(_tx_id):
        return {'status': 'ACCEPTED', 'statusCode': 5, 'final': False, 'appealable': True, 'terminal': False}
    async def read(function_name, args):
        if function_name == 'canAppeal':
            assert args == [Web3.to_bytes(hexstr=consensus_tx_id)]
            return True
        if function_name == 'getRoundNumber':
            return 2
        if function_name == 'calculateMinAppealBond':
            assert args == [Web3.to_bytes(hexstr=consensus_tx_id), 2, 5]
            return 123456
        raise AssertionError(function_name)
    async def transaction_details(_tx_id):
        return {'transaction': {'status': 5}, 'execution_status': 'UNKNOWN'}
    monkeypatch.setattr(client, 'get_consensus_transaction_status', status)
    monkeypatch.setattr(client, 'get_transaction_details', transaction_details)
    monkeypatch.setattr(client, '_has_protocol_function', lambda name: name in {'canAppeal', 'getRoundNumber', 'calculateMinAppealBond'})
    monkeypatch.setattr(client, '_read_protocol_function', read)
    result = await client.get_appeal_requirements(consensus_tx_id)
    assert result['minimum_appeal_bond_wei'] == 123456
    assert result['appeal_round'] == 2
    assert result['appeal_status_code'] == 5
    assert result['minimum_appeal_bond_source'] == 'protocol_calculate_min_appeal_bond'


@pytest.mark.asyncio
async def test_appeal_requirements_fails_closed_without_authoritative_bond(monkeypatch):
    client = object.__new__(GenLayerClientWrapper)
    async def status(_tx_id):
        return {'status': 'ACCEPTED', 'statusCode': 5}
    monkeypatch.setattr(client, 'get_consensus_transaction_status', status)
    monkeypatch.setattr(client, '_has_protocol_function', lambda name: False)
    with pytest.raises(RuntimeError, match='canAppeal'):
        await client.get_appeal_requirements('0x' + 'cd' * 32)


@pytest.mark.asyncio
async def test_build_appeal_transaction_rejects_bond_below_authoritative_minimum(monkeypatch):
    client = object.__new__(GenLayerClientWrapper)
    async def requirements(_tx_id):
        return {'appeal_window_open': True, 'consensus_status': 'ACCEPTED', 'minimum_appeal_bond_wei': 100}
    monkeypatch.setattr(client, 'get_appeal_requirements', requirements)
    with pytest.raises(ValueError, match='below the required minimum'):
        await client.build_appeal_transaction('0x' + '11' * 20, '0x' + 'ef' * 32, bond_wei=99)



@pytest.mark.asyncio
async def test_appeal_requirements_rejects_zero_protocol_bond(monkeypatch):
    client = object.__new__(GenLayerClientWrapper)
    async def status(_tx_id):
        return {'status': 'ACCEPTED', 'statusCode': 5}
    async def transaction_details(_tx_id):
        return {'transaction': {'status': 5}, 'execution_status': 'UNKNOWN'}
    async def read(function_name, _args):
        return {'canAppeal': True, 'getRoundNumber': 0, 'calculateMinAppealBond': 0}[function_name]
    monkeypatch.setattr(client, 'get_consensus_transaction_status', status)
    monkeypatch.setattr(client, 'get_transaction_details', transaction_details)
    monkeypatch.setattr(client, '_has_protocol_function', lambda _name: True)
    monkeypatch.setattr(client, '_read_protocol_function', read)
    with pytest.raises(RuntimeError, match='invalid minimum appeal bond'):
        await client.get_appeal_requirements('0x' + '44' * 32)
