"""Uploads against fake servers on localhost: what is sent is what was signed,
bodies stream without chunking, SMB/NFS mount commands and the write."""
import hashlib, os, tempfile, threading, time, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from layercam import config, sigv4, upload

KEY, SECRET = 'AKIDEXAMPLE', 'wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY'


class Store(BaseHTTPRequestHandler):
    got = []
    answer = 200

    def log_message(self, *a):
        pass

    def do_PUT(self):
        n = int(self.headers['Content-Length'])
        body = self.rfile.read(n)
        Store.got.append((self.path, dict(self.headers), body))
        self.send_response(Store.answer)
        self.send_header('Content-Length', '0')
        self.end_headers()


class Uploads(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(('127.0.0.1', 0), Store)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = 'http://127.0.0.1:%d' % cls.srv.server_port

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        Store.got, Store.answer = [], 200

    def body(self, n=300000):
        f = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        f.write(os.urandom(n))
        f.close()
        return upload.FileBody(f.name, '2026-10-26_1432_Benchy.mp4')

    def test_s3_path_style_signed_as_sent(self):
        b = self.body()
        clock = lambda: time.struct_time((2026, 10, 26, 21, 2, 49, 0, 299, 0))
        s3 = upload.S3(self.base, 'us-east-1', 'timelapses', KEY, SECRET, 'layercam/', 'auto', clock=clock)
        s3.send(b)
        path, h, data = Store.got[0]
        self.assertEqual(path, '/timelapses/layercam/2026-10-26_1432_Benchy.mp4')
        self.assertEqual(len(data), b.size)
        self.assertNotIn('Transfer-Encoding', h)
        sha = hashlib.sha256(data).hexdigest()
        self.assertEqual(h['X-Amz-Content-Sha256'], sha)
        # sign again from the headers the server received: the same signature
        signed = [(k, h[k]) for k in ('Host', 'X-Amz-Date', 'X-Amz-Content-Sha256', 'Content-Type', 'Content-Length')]
        auth, _, _ = sigv4.sign('PUT', path, [], signed, sha, KEY, SECRET, 'us-east-1', 's3', h['X-Amz-Date'])
        self.assertEqual(h['Authorization'], auth)
        self.assertEqual(h['X-Amz-Date'], '20261026T210249Z')

    def test_s3_addressing(self):
        u, host, path = upload.s3_url('https://s3.eu-central-1.amazonaws.com', 'my-bucket', 'a/b c.mp4')
        self.assertEqual((u, host, path), ('https://my-bucket.s3.eu-central-1.amazonaws.com/a/b%20c.mp4',
                                           'my-bucket.s3.eu-central-1.amazonaws.com', '/a/b c.mp4'))
        u, host, path = upload.s3_url('https://s3.amazonaws.com', 'my.bucket', 'x.mp4')     # dots: path style
        self.assertEqual(host, 's3.amazonaws.com')
        u, host, path = upload.s3_url('http://192.0.2.20:9000', 'prints', 'x.mp4')          # MinIO
        self.assertEqual(u, 'http://192.0.2.20:9000/prints/x.mp4')
        u, host, path = upload.s3_url('http://192.0.2.20:9000', 'prints', 'x.mp4', 'virtual')
        self.assertEqual(host, 'prints.192.0.2.20:9000')

    def test_s3_error(self):
        Store.answer = 403
        s3 = upload.S3(self.base, 'us-east-1', 'b', KEY, SECRET)
        with self.assertRaises(upload.UploadError):
            s3.send(self.body(10))

    def test_http_put(self):
        b = self.body(1000)
        upload.HttpPut(self.base + '/dav/timelapse', 'me', 'pw').send(b)
        path, h, data = Store.got[0]
        self.assertEqual(path, '/dav/timelapse/2026-10-26_1432_Benchy.mp4')
        self.assertEqual(h['Authorization'], 'Basic bWU6cHc=')
        self.assertEqual(len(data), 1000)

    def test_retry(self):
        calls, slept = [], []

        class Flaky:
            def describe(self):
                return 'flaky'

            def send(self, body):
                calls.append(1)
                if len(calls) < 3:
                    raise upload.UploadError('down')
                return 'ok'
        self.assertEqual(upload.send_with_retry(Flaky(), upload.BytesBody(b'x', 'x'), sleep=slept.append), 'ok')
        self.assertEqual(slept, [10, 60])


class Mounts(unittest.TestCase):
    def test_smb(self):
        cmds, seen_cred = [], []
        work, remote = tempfile.mkdtemp(), tempfile.mkdtemp()

        def run(cmd):
            cmds.append(cmd)
            if cmd[0] == 'umount':
                # what was written under the mountpoint was really on the server
                import shutil
                for n in os.listdir(cmd[1]):
                    shutil.move(os.path.join(cmd[1], n), remote)
            if cmd[0] == 'mount':
                opts = cmd[cmd.index('-o') + 1]
                cred = opts.split(',')[0].split('=', 1)[1]
                with open(cred) as f:
                    seen_cred.append((f.read(), os.stat(cred).st_mode & 0o777))
        m = upload.Mounted('smb', '//192.0.2.20/prints', 'timelapse', 'me', 's3cret', '3.0', run=run, workdir=work)
        out = m.send(upload.BytesBody(b'video', 'a.mp4'))
        self.assertEqual(cmds[0][:5], ['mount', '-t', 'cifs', '//192.0.2.20/prints', cmds[0][4]])
        self.assertIn('vers=3.0', cmds[0][-1])
        self.assertNotIn('s3cret', ' '.join(cmds[0]))           # never on the command line
        self.assertEqual(seen_cred, [('username=me\npassword=s3cret\n', 0o600)])
        self.assertEqual(cmds[1][0], 'umount')
        self.assertTrue(out.endswith('/timelapse/a.mp4'))
        with open(os.path.join(remote, 'timelapse', 'a.mp4'), 'rb') as f:
            self.assertEqual(f.read(), b'video')
        self.assertEqual(os.listdir(work), [])                  # mountpoint and credentials cleaned up

    def test_nfs_and_mount_failure(self):
        import subprocess

        def fail(cmd):
            raise subprocess.CalledProcessError(32, cmd, stderr=b'mount: permission denied')
        m = upload.Mounted('nfs', '192.0.2.20:/volume1/prints', 'tl', run=fail, workdir=tempfile.mkdtemp())
        with self.assertRaises(upload.UploadError):
            m.send(upload.BytesBody(b'v', 'a.mp4'))
        self.assertEqual(upload.nfs_mount_cmd('h:/e', '/m')[:4], ['mount', '-t', 'nfs', '-o'])

    def test_from_config(self):
        c = config.Config({('upload', 'target'): 'smb', ('upload', 'smb_share'): '//192.0.2.20/p'})
        self.assertIsInstance(upload.from_config(c), upload.Mounted)
        self.assertIsNone(upload.from_config(config.Config()))


if __name__ == '__main__':
    unittest.main()
