"""Read-only demo checker regression tests, without network or blockchain mutation."""
import copy
import hashlib
import importlib.util
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import owned_counter as c
spec = importlib.util.spec_from_file_location('counter_review', Path(__file__).resolve().parents[1] / 'review-counter.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class ReviewTests(unittest.TestCase):
    def fixture(self):
        m = c.read(review.DEFAULT)
        m = copy.deepcopy(m)
        app = m['application']
        output = c.output(app['capacity_shannons'], app['owner'], app['type'])
        creation = dict(outputs=[output], outputs_data=[app['initial_data']])
        update = dict(inputs=[dict(previous_output=app['initial_outpoint'])],
                      outputs=[output], outputs_data=[app['successor_data']], witnesses=[c.witness(b'example')])
        deployment = dict(outputs_data=[c.hx(b'code'), c.hx(b'vk')])
        for name, data in [('type', b'code'), ('vk', b'vk')]:
            m['artifacts'][name] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), data_hash=c.hx(c.h(data)))
        m['proof_witness_sha256'] = hashlib.sha256(b'example').hexdigest()
        txs = dict(deployment=deployment, creation=creation, update=update)
        for name, tx in txs.items():m['transactions'][name]['raw_json_sha256'] = review.raw_digest(tx)
        return m, txs

    def test_recorded_mode_does_not_call_rpc(self):
        with patch.object(c, 'rpc', side_effect=AssertionError('network forbidden')):
            result = review.review(c.read(review.DEFAULT))
        self.assertIn('NOT a live query', result['mode'])

    def test_valid_operation_and_unsigned_json_digest(self):
        m, txs = self.fixture()
        self.assertEqual(review.validate(m, txs), m['statement'])
        with_hash = dict(txs['update'], hash='unused')
        self.assertEqual(review.raw_digest(with_hash), review.raw_digest(txs['update']))

    def test_changed_transaction_rejects(self):
        m, txs = self.fixture()
        txs['update']['outputs_data'][0] = '0x010200000000000000'
        with self.assertRaisesRegex(ValueError, 'transaction differs'):
            review.validate(m, txs)

    def test_wrong_context_rejects_even_with_matching_transaction_digest(self):
        m, txs = self.fixture()
        m['statement'][2] = '0'
        with self.assertRaisesRegex(ValueError, 'public statement mismatch'):
            review.validate(m, txs)

    def test_witness_change_rejects(self):
        m, txs = self.fixture()
        txs['update']['witnesses'][0] = c.witness(b'changed')
        with self.assertRaisesRegex(ValueError, 'proof witness differs'):
            review.validate(m, txs)

    def test_unconfirmed_transaction_rejects_without_retry(self):
        m = c.read(review.DEFAULT)
        with patch.object(c, 'network'), patch.object(c, 'rpc', return_value={'tx_status': {'status': 'pending'}}) as rpc:
            with self.assertRaisesRegex(ValueError, 'not committed'):
                review.review(m, 'https://example.invalid')
            rpc.assert_called_once()


if __name__ == '__main__':unittest.main()
