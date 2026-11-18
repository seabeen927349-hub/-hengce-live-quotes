"""Authenticate official settlement inputs archived by an independently trusted collector."""
import base64
import json
import re
import subprocess
import tempfile
from datetime import date, datetime, time
from pathlib import Path
from urllib.parse import urlsplit

from hengce_hba_context_bridge_v1 import CARD_TZ, card_time
from hengce_hba_research_ledger import canonical, sha

DOMAINS = frozenset({'www.twse.com.tw', 'openapi.twse.com.tw'})
KINDS = ('taiex', 'trading_status', 'corporate_actions')
OFFICIAL = 'HENGCE_TWSE_OFFICIAL_REFERENCE_V1'
TRUST = Path(__file__).resolve().parents[1] / 'governance/HENGCE_TWSE_REFERENCE_TRUST_V1.json'


class OfficialSessions(dict):
    """Values produced by validating a locked official reference object."""


def verify_signature(public_key, message, signature):
    # The only key source is the repository's reviewed trust registry.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root/'key.pem').write_text(public_key, encoding='utf-8')
        (root/'receipt').write_bytes(message)
        (root/'signature').write_bytes(base64.b64decode(signature, validate=True))
        result = subprocess.run(
            ['openssl', 'pkeyutl', '-verify', '-pubin', '-rawin', '-inkey', str(root/'key.pem'),
             '-in', str(root/'receipt'), '-sigfile', str(root/'signature')],
            capture_output=True, check=False)
    if result.returncode:
        raise ValueError('REFERENCE_SIGNATURE_INVALID')


def verify_packet(packet, kind, day, raw, keys, publication, asof):
    receipt, claims = packet['receipt'], packet['claims']
    signer = keys.get(receipt['key_id'])
    if not signer:
        raise ValueError('REFERENCE_SIGNER_UNTRUSTED')
    source = receipt['source']
    uri = urlsplit(source)
    endpoint = f'{uri.scheme}://{uri.netloc}{uri.path}'
    if (receipt['schema'] != OFFICIAL or receipt['publisher'] != 'TWSE'
            or receipt['dataset'] != kind or receipt['effective_date'] != day.isoformat()
            or uri.scheme != 'https' or uri.netloc not in DOMAINS or uri.fragment
            or endpoint not in signer['endpoints'].get(kind, ())):
        raise ValueError('REFERENCE_SOURCE_UNAPPROVED')
    announced = card_time(receipt['announced_at_taipei'])
    observed = card_time(receipt['first_observed_at_taipei'])
    if not (datetime.combine(day, time(13, 30), CARD_TZ) <= announced <= observed <= publication <= asof
            and card_time(signer['valid_from']) <= observed < card_time(signer['valid_until'])):
        raise ValueError('REFERENCE_SOURCE_TIME_INVALID')
    digest = receipt['raw_sha256']
    blob = raw.get(digest)
    if not blob or sha(blob) != digest or sha(canonical(claims)) != receipt['claims_sha256']:
        raise ValueError('REFERENCE_RAW_OR_CLAIMS_SHA_MISMATCH')
    verify_signature(signer['public_key_pem'], canonical(receipt), packet['signature'])
    return claims, {'status': 'VERIFIED', 'effective_date': day.isoformat(),
                    'available_at': publication.isoformat(), 'sha256': digest,
                    'announcement_taipei': announced.isoformat(), 'observed_taipei': observed.isoformat(),
                    'source': source, 'attestation_sha256': sha(canonical(receipt))}


def official_sessions(bundle, publication, asof, trust):
    if bundle.get('schema') != OFFICIAL:
        raise ValueError('OFFICIAL_REFERENCE_BUNDLE_REQUIRED')
    if trust.get('schema') != 'HENGCE_TWSE_REFERENCE_TRUST_V1' or not trust.get('collectors'):
        raise ValueError('NO_APPROVED_TWSE_REFERENCE_COLLECTORS')
    if sha(canonical(bundle['policy'])) not in trust.get('approved_policy_sha256', ()):
        raise ValueError('UNAPPROVED_SETTLEMENT_POLICY')
    raw = {digest: base64.b64decode(blob, validate=True) for digest, blob in bundle['raw_objects'].items()}
    verified = OfficialSessions()
    for day, packets in bundle['official_sessions'].items():
        day_date = date.fromisoformat(day)
        if set(packets) != set(KINDS):
            raise ValueError('INCOMPLETE_OFFICIAL_REFERENCE_SET')
        (index, ip), (trading, tp), (actions, ap) = [
            verify_packet(packets[kind], kind, day_date, raw, trust['collectors'], publication, asof)
            for kind in KINDS]
        # Require an explicit attested status and action conclusion per ticker.
        # An absent ticker or empty event list is never translated into NONE_VERIFIED.
        if set(index) != {'open','close'} or not isinstance(trading, dict) or not isinstance(actions, dict):
            raise ValueError('REFERENCE_CLAIMS_SCHEMA')
        stocks = {}
        for ticker in trading.keys() & actions.keys():
            if (not re.fullmatch(r'[0-9]{4}', ticker)
                    or trading[ticker] not in ('TRADABLE','HALTED','DELISTED','NOT_TRADABLE')
                    or actions[ticker] not in ('NO_ACTION','ACTION','UNKNOWN')):
                raise ValueError('REFERENCE_STOCK_CLAIM_INVALID')
            stocks[ticker] = {**tp, 'trading_status': trading[ticker],
                              'corporate_action': 'NONE_VERIFIED' if actions[ticker]=='NO_ACTION' else actions[ticker],
                              'corporate_action_proof': ap}
        verified[day] = {'benchmark': {**ip, **index}, 'stocks': stocks}
    return verified


def load_trust():
    return json.loads(TRUST.read_bytes())
