"""Offline transport tests: never contact a node or broadcast a transaction."""
import contextlib
import http.client
import io
import json
from pathlib import Path
import socket
import ssl
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import owned_counter as counter


class RpcTests(unittest.TestCase):
    def test_headers_payload_timeout_and_default_tls(self):
        response = io.BytesIO(json.dumps({'result': counter.TESTNET}).encode())
        with patch.object(counter.urllib.request, 'urlopen', return_value=response) as opening:
            self.assertEqual(counter.rpc('https://testnet.ckb.dev', 'get_block_hash', ['0x0']), counter.TESTNET)
        opening.assert_called_once()
        request = opening.call_args.args[0]
        self.assertEqual(request.get_header('User-agent'), 'noir-ckb/owned-counter-v1')
        self.assertEqual(request.get_header('Content-type'), 'application/json')
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(json.loads(request.data), dict(id=1, jsonrpc='2.0', method='get_block_hash', params=['0x0']))
        # No custom SSL context, opener, or timeout change.
        self.assertEqual(opening.call_args.kwargs, {'timeout': 30})
        self.assertTrue(response.closed)

    def test_transport_errors_fail_once_with_actionable_safe_message(self):
        failures = [
            (urllib.error.HTTPError('https://secret@example.invalid', 403, 'secret', {}, None), 'HTTP 403'),
            (urllib.error.HTTPError('https://example.invalid', 429, 'limited', {}, None), 'HTTP 429'),
            (urllib.error.URLError(socket.gaierror('secret')), 'DNS'),
            (TimeoutError('secret'), 'timed out'),
            (urllib.error.URLError(TimeoutError('secret')), 'timed out'),
            (urllib.error.URLError(ssl.SSLCertVerificationError('secret')), 'TLS verification failed'),
            (http.client.RemoteDisconnected('secret'), 'Network connection failed'),
        ]
        for failure, expected in failures:
            with self.subTest(failure=failure), patch.object(counter.urllib.request, 'urlopen', side_effect=failure) as opening:
                with self.assertRaises(counter.RpcError) as raised:
                    counter.rpc('https://example.invalid', 'get_block_hash', ['0x0'])
                self.assertIn(expected, str(raised.exception))
                self.assertIn('retry', str(raised.exception))
                self.assertNotIn('secret', str(raised.exception))
                opening.assert_called_once()

    def test_cli_transport_error_is_nonzero_without_traceback_or_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'policy.json'
            argv = ['owned_counter.py', 'preflight', '--rpc', 'https://example.invalid',
                    '--genesis', counter.TESTNET, '--out', str(output)]
            stderr = io.StringIO()
            with patch.object(sys, 'argv', argv), patch.object(counter.urllib.request, 'urlopen', side_effect=urllib.error.URLError('offline')), contextlib.redirect_stderr(stderr):
                self.assertEqual(counter.cli(), 1)
            self.assertIn('Check the RPC URL', stderr.getvalue())
            self.assertNotIn('Traceback', stderr.getvalue())
            self.assertFalse(output.exists())

    def test_genesis_mismatch_still_rejects(self):
        with patch.object(counter, 'rpc', return_value='0x' + '00' * 32):
            with self.assertRaisesRegex(ValueError, 'genesis differs'):
                counter.network('https://testnet.ckb.dev', counter.TESTNET)

    def test_json_rpc_error_still_rejects(self):
        response = io.BytesIO(b'{"error":{"code":-32601,"message":"not found"}}')
        with patch.object(counter.urllib.request, 'urlopen', return_value=response):
            with self.assertRaisesRegex(ValueError, 'RPC get_block_hash'):
                counter.rpc('https://example.invalid', 'get_block_hash', ['0x0'])

    def test_existing_policy_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'policy.json'
            output.write_text('existing policy\n')
            with self.assertRaises(FileExistsError):
                counter.write(output, {'replacement': True})
            self.assertEqual(output.read_text(), 'existing policy\n')


if __name__ == '__main__':
    unittest.main()
