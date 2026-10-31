"""AWS Signature Version 4, for S3 and S3-compatible stores (MinIO,
Backblaze B2, NAS object stores).  Standard library only.

The algorithm is AWS's ("Create a signed AWS API request", IAM user guide):
canonical request -> string to sign -> HMAC chain date/region/service ->
signature.  Tested against AWS's own SigV4 test suite (tests/data/aws4_testsuite,
copied from botocore with its Apache-2.0 licence) and against botocore's S3
signer for S3 requests.

Paths are taken as plain (not yet encoded) text, URI-encoded once and not
normalised, as S3 wants (an object key may contain "//" or "./"); for S3 the
x-amz-content-sha256 header carries the payload hash.
"""
import hashlib, hmac
from urllib.parse import quote

ALGORITHM = 'AWS4-HMAC-SHA256'
EMPTY_SHA256 = hashlib.sha256(b'').hexdigest()


def _hmac(key, msg):
    return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()


def signing_key(secret, date, region, service):
    k = _hmac(('AWS4' + secret).encode('utf-8'), date)
    k = _hmac(k, region)
    k = _hmac(k, service)
    return _hmac(k, 'aws4_request')


def uri_encode(s, safe='-_.~'):
    """RFC 3986 unreserved characters stay, everything else is %XX (upper case)."""
    return quote(s, safe=safe)


def canonical_uri(path):
    return uri_encode(path or '/', safe='/-_.~')


def canonical_query(query):
    """query: list of (name, value) pairs, not yet encoded."""
    pairs = sorted((uri_encode(k), uri_encode(v)) for k, v in query)
    return '&'.join('%s=%s' % kv for kv in pairs)


def canonical_headers(headers):
    """headers: list of (name, value).  Lower-case names, values trimmed and
    inner runs of spaces folded, repeated names joined with commas."""
    merged = {}
    for k, v in headers:
        v = ' '.join(str(v).strip().split())
        merged.setdefault(k.lower().strip(), []).append(v)
    names = sorted(merged)
    text = ''.join('%s:%s\n' % (n, ','.join(merged[n])) for n in names)
    return text, ';'.join(names)


def canonical_request(method, path, query, headers, payload_hash):
    hdr_text, signed = canonical_headers(headers)
    creq = '\n'.join([method, canonical_uri(path), canonical_query(query), hdr_text, signed, payload_hash])
    return creq, signed


def string_to_sign(amz_date, scope, creq):
    return '\n'.join([ALGORITHM, amz_date, scope, hashlib.sha256(creq.encode('utf-8')).hexdigest()])


def sign(method, path, query, headers, payload_hash, access_key, secret_key, region, service, amz_date):
    """-> (Authorization header value, canonical request, string to sign).
    headers must already hold Host and X-Amz-Date (and X-Amz-Content-Sha256
    for S3); every header given is signed."""
    date = amz_date[:8]
    scope = '%s/%s/%s/aws4_request' % (date, region, service)
    creq, signed = canonical_request(method, path, query, headers, payload_hash)
    sts = string_to_sign(amz_date, scope, creq)
    sig = hmac.new(signing_key(secret_key, date, region, service), sts.encode('utf-8'), hashlib.sha256).hexdigest()
    auth = '%s Credential=%s/%s, SignedHeaders=%s, Signature=%s' % (ALGORITHM, access_key, scope, signed, sig)
    return auth, creq, sts
