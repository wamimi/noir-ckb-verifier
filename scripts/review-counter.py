#!/usr/bin/env python3
"""Inspect the recorded public demonstration; optionally refresh READ-ONLY RPC checks."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import owned_counter as c

DEFAULT = c.ROOT / 'evidence/week-15-public/deployment.json'


def raw_digest(tx):
    body = {k: v for k, v in tx.items() if k not in ('hash', 'witnesses')}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate(manifest, transactions):
    """Check committed transaction contents, artifact identities and operation binding."""
    for stage, tx in transactions.items():
        c.require(raw_digest(tx) == manifest['transactions'][stage]['raw_json_sha256'],
                  f'{stage}: transaction differs from public evidence')
    deployment, creation, update = (transactions[n] for n in ('deployment', 'creation', 'update'))
    for index, name in enumerate(('type', 'vk')):
        data = c.raw(deployment['outputs_data'][index])
        identity = manifest['artifacts'][name]
        c.require(len(data) == identity['bytes'] and hashlib.sha256(data).hexdigest() == identity['sha256']
                  and c.hx(c.h(data)) == identity['data_hash'], f'{name}: deployed artifact mismatch')
    app = manifest['application']
    c.require(update['inputs'][0]['previous_output'] == app['initial_outpoint'], 'wrong consumed application Cell')
    for tx, field in ((creation, 'initial_data'), (update, 'successor_data')):
        output = tx['outputs'][0]
        c.require(output['type'] == app['type'] and output['lock'] == app['owner']
                  and int(output['capacity'], 16) == app['capacity_shannons']
                  and tx['outputs_data'][0] == app[field], 'application state/owner/capacity mismatch')
    derived = c.statement(manifest['policy'], update, {'data': {'content': creation['outputs_data'][0]}})
    c.require(derived == manifest['statement'], 'derived public statement mismatch')
    payload = c.witness_parts(update['witnesses'][0])[1][4:]
    c.require(hashlib.sha256(payload).hexdigest() == manifest['proof_witness_sha256'], 'proof witness differs')
    return derived


def review(manifest, rpc_url=None):
    result = {'mode': 'recorded evidence; NOT a live query', 'network': manifest['network'],
              'transactions': {n: t['hash'] for n, t in manifest['transactions'].items()},
              'state': '0 -> 1', 'application_capacity_ckb': 200,
              'initial_outpoint': manifest['application']['initial_outpoint'],
              'successor_outpoint': manifest['application']['successor_outpoint'],
              'public_statement': manifest['statement']}
    if rpc_url:
        c.network(rpc_url, manifest['network'])
        transactions = {}
        for stage, entry in manifest['transactions'].items():
            response = c.rpc(rpc_url, 'get_transaction', [entry['hash']])
            c.require(response and response['tx_status']['status'] == 'committed', f'{stage}: not committed')
            transactions[stage] = response['transaction']
        validate(manifest, transactions)
        initial = c.rpc(rpc_url, 'get_live_cell', [manifest['application']['initial_outpoint'], True])
        successor = c.rpc(rpc_url, 'get_live_cell', [manifest['application']['successor_outpoint'], True])
        c.require(initial['status'] != 'live', 'consumed application Cell still live')
        if successor['status'] == 'live':
            cell = successor['cell']
            c.require(cell['output'] == transactions['update']['outputs'][0]
                      and cell['data']['content'] == manifest['application']['successor_data'], 'live successor mismatch')
        result.update(mode='live read-only RPC: three committed transactions and contents verified',
                      initial_current_status=initial['status'], successor_current_status=successor['status'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT)
    parser.add_argument('--rpc', help='Optional read-only refresh, e.g. https://testnet.ckb.dev')
    parser.add_argument('--out', type=Path, help='New result file; never overwrite')
    args = parser.parse_args()
    manifest = c.read(args.manifest)
    for name, digest in manifest['public_files_sha256'].items():
        c.require(c.sha(args.manifest.parent / name) == digest, f'public artifact changed: {name}')
    result = review(manifest, args.rpc)
    if args.out:
        c.write(args.out, result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (c.RpcError, ValueError, OSError) as error:
        sys.exit(f'error: {error}')
