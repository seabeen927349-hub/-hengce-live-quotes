"""Content-verified HBA research snapshots. Local records are historical replay only."""
import argparse
import base64
import hashlib
import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from hengce_hba_context_bridge_v1 import CARD_TZ, card_time
from hengce_hba_decision_report import CARD_MAX_BYTES, read_research_cards

SCHEMA = 'HENGCE_HBA_RESEARCH_LEDGER_V1'
REPLAY = 'HISTORICAL_REPLAY'
LIVE = 'PROSPECTIVE'
PREFIX = 'hengce/hba-research/v1'
MIN_RETENTION_DAYS = 365


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'),
                      allow_nan=False).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate_cutoff(manifest):
    cutoff = card_time(manifest['evidence_cutoff_taipei'])
    market_day = date.fromisoformat(manifest['market_date'])
    if market_day > cutoff.date():
        raise ValueError('MARKET_DATE_AFTER_CUTOFF')
    provenance = manifest['provenance']
    for day, legs in provenance['eod'].items():
        if date.fromisoformat(day) > market_day:
            raise ValueError('FUTURE_EOD_DATE')
        for proof in legs.values():
            if proof['effective_date'] != day:
                raise ValueError('EOD_SOURCE_DATE_MISMATCH')
            if proof['status'] == 'VERIFIED':
                for field in ('available_at', 'mother_available_at'):
                    if card_time(proof[field]) > cutoff:
                        raise ValueError('FUTURE_EOD_PROOF')
    for proof in provenance['tdcc']:
        if date.fromisoformat(proof['effective_date']) > market_day:
            raise ValueError('FUTURE_TDCC_DATE')
        if proof['status'] == 'VERIFIED' and card_time(proof['available_at']) > cutoff:
            raise ValueError('FUTURE_TDCC_PROOF')
    for name, day_field, time_field in (('taiwan_vix', 'date', 'observed_at_taipei'),
                                         ('overseas', 'date', 'available_at')):
        evidence = manifest['environment'][name]
        if evidence.get('source_verified') is True or evidence['status'] == 'VERIFIED':
            if date.fromisoformat(evidence[day_field]) > cutoff.date() or card_time(evidence[time_field]) > cutoff:
                raise ValueError('FUTURE_ENVIRONMENT_PROOF')
    return cutoff


def snapshot(directory, source_commit, mode):
    if not re.fullmatch(r'[0-9a-f]{40}', source_commit) or mode not in (LIVE, REPLAY):
        raise ValueError('INVALID_SNAPSHOT_IDENTITY')
    manifest, cards = read_research_cards(directory)
    cutoff = validate_cutoff(manifest)
    identity = {'mode': mode, 'market_date': manifest['market_date'],
                'formed_at_taipei': cutoff.isoformat(), 'research_version': manifest['schema']}
    event_id = sha(canonical(identity))
    # Exact PR-1 bytes, including evidence and research conclusions.
    paths = ['manifest.json', *(item['path'] for item in manifest['shards'])]
    objects = {p: base64.b64encode((directory/p).read_bytes()).decode('ascii') for p in paths}
    return {'schema': SCHEMA, 'snapshot_id': event_id, **identity,
            'source_commit': source_commit, 'objects': objects,
            'ticker_count': len(cards), 'manifest_sha256': sha((directory/'manifest.json').read_bytes())}


def unpack(record):
    """Revalidate historical and protected objects before using the evidence."""
    identity = {key: record[key] for key in ('mode', 'market_date', 'formed_at_taipei', 'research_version')}
    if record['schema'] != SCHEMA or record['snapshot_id'] != sha(canonical(identity)):
        raise ValueError('SNAPSHOT_ID_MISMATCH')
    blobs = {p: base64.b64decode(data, validate=True) for p, data in record['objects'].items()}
    raw = blobs['manifest.json']
    if sha(raw) != record['manifest_sha256']:
        raise ValueError('MANIFEST_SHA_MISMATCH')
    manifest = json.loads(raw)
    formed = validate_cutoff(manifest)
    if (manifest['market_date'] != record['market_date'] or manifest['schema'] != record['research_version']
            or formed.isoformat() != record['formed_at_taipei']):
        raise ValueError('MANIFEST_IDENTITY_MISMATCH')
    cards = {}
    expected = {'manifest.json'}
    for i, shard in enumerate(manifest['shards'], 1):
        name = f'cards-{i:02}.json'
        if shard['path'] != name:
            raise ValueError('SHARD_PATH_MISMATCH')
        data = blobs[name]
        expected.add(name)
        rows = json.loads(data)
        if len(data) >= CARD_MAX_BYTES or sha(data) != shard['sha256'] or len(rows) != shard['rows']:
            raise ValueError('SHARD_SHA_OR_COUNT_MISMATCH')
        for card in rows:
            ticker = card['ticker']
            if not re.fullmatch(r'[0-9]{4}', ticker) or ticker in cards:
                raise ValueError('INVALID_OR_DUPLICATE_TICKER')
            cards[ticker] = card
    if expected != set(blobs) or len(cards) != record['ticker_count'] or len(cards) != manifest['coverage']['stocks']:
        raise ValueError('SNAPSHOT_UNIVERSE_MISMATCH')
    return manifest, cards


def key_for(record):
    return f"{PREFIX}/{record['mode']}/snapshots/{record['snapshot_id']}.json"


def store_replay(root, record):
    if record['mode'] != REPLAY:
        raise ValueError('LOCAL_STORAGE_IS_REPLAY_ONLY')
    path = root/key_for(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical(record)
    # Link a complete local temporary file without replacing any already-present record.
    import tempfile
    with tempfile.NamedTemporaryFile(dir=path.parent) as tmp:
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
        try:
            os.link(tmp.name, path)
        except FileExistsError:
            pass
    if path.read_bytes() != data:
        raise ValueError('REPLAY_EXISTING_RECORD_DIFFERS')
    return {'mode': REPLAY, 'snapshot_id': record['snapshot_id'], 'snapshot_sha256': sha(data),
            'path': str(path), 'published_at_taipei': None}


class LockedArchive:
    def __init__(self, client, bucket, owner):
        if not bucket or not re.fullmatch(r'[0-9]{12}', owner):
            raise ValueError('LOCKED_BUCKET_AND_OWNER_REQUIRED')
        self.client = client
        self.bucket = dict(Bucket=bucket, ExpectedBucketOwner=owner)

    def policy(self):
        if self.client.get_bucket_versioning(**self.bucket).get('Status') != 'Enabled':
            raise ValueError('BUCKET_VERSIONING_REQUIRED')
        config = self.client.get_object_lock_configuration(**self.bucket)['ObjectLockConfiguration']
        retention = config.get('Rule', {}).get('DefaultRetention', {})
        if (config.get('ObjectLockEnabled') != 'Enabled' or retention.get('Mode') != 'COMPLIANCE'
                or max(retention.get('Days', 0), 365*retention.get('Years', 0)) < MIN_RETENTION_DAYS):
            raise ValueError('COMPLIANCE_RETENTION_REQUIRED')

    def read(self, key, version=None):
        args = dict(self.bucket, Key=key)
        if version is not None:
            args['VersionId'] = version
        response = self.client.get_object(**args)
        actual_version = response.get('VersionId')
        if not actual_version or actual_version == 'null' or (version and version != actual_version):
            raise ValueError('LOCKED_VERSION_REQUIRED')
        published = response['LastModified'].astimezone(CARD_TZ)
        hold = self.client.get_object_retention(**args, **(
            {} if version else {'VersionId': actual_version}))['Retention']
        if (hold.get('Mode') != 'COMPLIANCE'
                or hold['RetainUntilDate'] < published + timedelta(days=MIN_RETENTION_DAYS-1)):
            raise ValueError('OBJECT_RETENTION_UNVERIFIED')
        with response['Body'] as body:
            data = body.read()
        if response.get('Metadata', {}).get('sha256') != sha(data):
            raise ValueError('STORED_SHA_MISMATCH')
        return data, {'bucket': self.bucket['Bucket'], 'key': key, 'version_id': actual_version,
                      'published_at_taipei': published.isoformat(),
                      'retain_until': hold['RetainUntilDate'].isoformat(), 'sha256': sha(data)}

    def create(self, key, data):
        self.policy()
        try:
            result = self.client.put_object(**self.bucket, Key=key, Body=data, IfNoneMatch='*',
                                            ContentType='application/json', Metadata={'sha256': sha(data)},
                                            ChecksumSHA256=base64.b64encode(hashlib.sha256(data).digest()).decode())
            version = result['VersionId']
        except Exception as exc:
            if getattr(exc, 'response', {}).get('Error', {}).get('Code') != 'PreconditionFailed':
                raise
            version = None
        actual, receipt = self.read(key, version)
        if actual != data:
            raise ValueError('EXISTING_LOCKED_RECORD_DIFFERS')
        return receipt


def open_archive(bucket, owner):
    import boto3

    return LockedArchive(boto3.client('s3'), bucket, owner)


def publish(archive, record):
    if record['mode'] != LIVE:
        raise ValueError('EXPECTED_PROSPECTIVE_SNAPSHOT')
    if card_time(record['formed_at_taipei']) > datetime.now(CARD_TZ):
        raise ValueError('FUTURE_FORMATION_TIME')
    _, cards = unpack(record)
    receipt = archive.create(key_for(record), canonical(record))
    published = card_time(receipt['published_at_taipei'])
    formed = card_time(record['formed_at_taipei'])
    # S3 LastModified has second-level precision.
    if published < formed.replace(microsecond=0):
        raise ValueError('PUBLICATION_BEFORE_FORMATION')
    receipt = {**receipt, 'snapshot_id': record['snapshot_id'], 'mode': LIVE, 'stocks': len(cards)}
    receipt_key = f"{PREFIX}/{LIVE}/receipts/{record['snapshot_id']}.json"
    index = archive.create(receipt_key, canonical(receipt))
    return {**receipt, 'receipt_key': receipt_key, 'receipt_version_id': index['version_id']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cards', required=True, type=Path)
    parser.add_argument('--source-commit', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--replay-dir', type=Path)
    mode.add_argument('--bucket')
    parser.add_argument('--owner')
    args = parser.parse_args()
    if args.bucket and (os.environ.get('GITHUB_REF') != 'refs/heads/main'
                        or os.environ.get('GITHUB_EVENT_NAME') not in ('push', 'schedule', 'workflow_run', 'workflow_dispatch')
                        or args.source_commit != os.environ.get('GITHUB_SHA')):
        parser.error('live snapshots require the existing trusted main workflow')
    record = snapshot(args.cards, args.source_commit, LIVE if args.bucket else REPLAY)
    unpack(record)
    receipt = (publish(open_archive(args.bucket, args.owner), record) if args.bucket
               else store_replay(args.replay_dir, record))
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
