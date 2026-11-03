"""SigV4 against AWS's published test suite and botocore's S3 signer.

data/aws4_testsuite/ is a copy of AWS's "AWS Signature Version 4 Test Suite"
(Apache-2.0, NOTICE and LICENSE beside it) as botocore ships it in
tests/unit/auth/aws4_testsuite (botocore commit 2cd57933, 26 Oct 2026).  Each
case gives a request (.req) and the expected canonical request (.creq), string
to sign (.sts) and Authorization header (.authz), for credentials
AKIDEXAMPLE / wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY, us-east-1, service
"service".  Left out: the normalize-path cases other than get-space (S3 does
not normalise paths, so neither does this signer), a header folded over
several lines and the session-token case (its token is not in the .req).
"""
import hashlib, os, unittest
from urllib.parse import unquote

from layercam import sigv4

SUITE = os.path.join(os.path.dirname(__file__), 'data', 'aws4_testsuite')
KEY, SECRET = 'AKIDEXAMPLE', 'wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY'


def parse_req(text):
    head, _, body = text.partition('\n\n')
    lines = [ln for ln in head.split('\n') if ln]
    # the request line is "METHOD target HTTP/1.1"; the target may hold spaces (get-space)
    method, rest = lines[0].split(' ', 1)
    target = rest.rsplit(' ', 1)[0]
    path, _, qs = target.partition('?')
    query = []
    if qs:
        for part in qs.split('&'):
            k, _, v = part.partition('=')
            query.append((unquote(k), unquote(v)))
    headers = []
    for ln in lines[1:]:
        k, _, v = ln.partition(':')
        headers.append((k, v))
    return method, unquote(path), query, headers, body.encode()


class AwsSuite(unittest.TestCase):
    def test_signing_key(self):
        # the example in AWS's SigV4 documentation ("derive a signing key":
        # this secret, 20150830, us-east-1, iam); the page itself could not be
        # fetched on 26 Oct 2026, but every suite case below checks the same chain
        k = sigv4.signing_key(SECRET, '20150830', 'us-east-1', 'iam')
        self.assertEqual(k.hex(), 'c4afb1cc5771d871763a393e44b703571b55cc28424d1a5e86da6ed3c154a4b9')

    def test_suite(self):
        cases = sorted(os.listdir(SUITE))
        cases = [c for c in cases if os.path.isdir(os.path.join(SUITE, c))]
        self.assertGreaterEqual(len(cases), 20)
        for case in cases:
            d = os.path.join(SUITE, case)

            def read(ext):
                with open(os.path.join(d, case + ext), encoding='utf-8') as f:
                    return f.read()
            with self.subTest(case=case):
                method, path, query, headers, body = parse_req(read('.req'))
                amz_date = dict((k.lower(), v) for k, v in headers)['x-amz-date']
                auth, creq, sts = sigv4.sign(method, path, query, headers, hashlib.sha256(body).hexdigest(),
                                             KEY, SECRET, 'us-east-1', 'service', amz_date)
                self.assertEqual(creq, read('.creq'))
                self.assertEqual(sts, read('.sts'))
                self.assertEqual(auth, read('.authz'))


class S3AgainstBotocore(unittest.TestCase):
    """The same requests signed by botocore 1.43.119's S3SigV4Auth (an
    independent implementation; script in the README's test notes)."""

    CASES = [
        ('minio.example.com:9000', '/timelapses/layercam/2026-10-26_1432_Benchy_0.2mm_PLA.mp4', 'us-east-1',
         b'hello timelapse', 'd879accd5e476aa7ecf84ec10c6ab99d942698041c79a292c95b545d09ee46fc'),
        ('my-bucket.s3.eu-central-1.amazonaws.com', '/layercam/a b+c.mp4', 'eu-central-1', b'\0' * 1000,
         '165a3468a11d90b16976d0d703834e29614025477de5d9b2c512801f8cd0b1d7'),
        ('s3.us-west-004.backblazeb2.com', '/prints/x/y.mp4', 'us-west-004', b'',
         '9529ae6be03d69cfe97dd0d5f952dcad4daa893d1f62881b11041ff53239f654'),
    ]

    def test_put_object(self):
        from layercam.upload import s3_headers
        for host, path, region, body, sig in self.CASES:
            with self.subTest(host=host):
                h = s3_headers('PUT', host, path, hashlib.sha256(body).hexdigest(), len(body), 'video/mp4',
                               KEY, SECRET, region, '20261026T210249Z')
                self.assertTrue(h['Authorization'].endswith('Signature=' + sig), h['Authorization'])
                self.assertIn('SignedHeaders=content-length;content-type;host;x-amz-content-sha256;x-amz-date',
                              h['Authorization'])


if __name__ == '__main__':
    unittest.main()
