"""The whole service on the host: a fake printer (PrusaLink + metrics UDP),
the fake camera, an HTTP upload target.  A print starts, five layer
triggers arrive (one twice, as the snippet sends them), the print finishes,
and an MP4 with five frames arrives at the upload target, named after the
job.  The setup page answers too."""
import json, os, socket, tempfile, threading, time, unittest, urllib.request
from http.server import HTTPServer

from layercam import config, service
from tests import h264util
from tests.test_prusalink import Printer
from tests.test_upload import Store


def free_udp_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


def wait(cond, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


@unittest.skipUnless(h264util.have_ffmpeg(), 'needs ffmpeg (the fake camera has no encoder)')
class EndToEnd(unittest.TestCase):
    def test_print_to_upload(self):
        printer = HTTPServer(('127.0.0.1', 0), Printer)
        store = HTTPServer(('127.0.0.1', 0), Store)
        for s in (printer, store):
            threading.Thread(target=s.serve_forever, daemon=True).start()
        Printer.nonce, Printer.seen = '0123456789abcdef', []
        Printer.status, Printer.job = 'prusalink_status_idle.json', None
        Store.got, Store.answer = [], 201

        d = tempfile.mkdtemp()
        udp = free_udp_port()
        cfg = config.Config({
            ('wifi', 'ssid'): 'Workshop', ('camera', 'backend'): 'fake', ('connect', 'enabled'): False,
            ('prusalink', 'host'): '127.0.0.1:%d' % printer.server_port, ('prusalink', 'password'): Printer.password,
            ('prusalink', 'poll_interval'): 1, ('timelapse', 'udp_port'): udp,
            ('timelapse', 'storage'): os.path.join(d, 'timelapse'), ('timelapse', 'min_free_mb'): 1,
            ('upload', 'target'): 'http', ('upload', 'http_url'): 'http://127.0.0.1:%d/tl/' % store.server_port,
            ('web', 'password'): 'pagepass'}, path=os.path.join(d, 'layercam.ini'))
        cfg.save()
        svc = service.Service(cfg.path, port=0, hw_root=os.path.join(d, 'root'))
        self.assertEqual(len(svc.cfg.get('device', 'fingerprint')), 32)      # made and saved on first start
        t = threading.Thread(target=svc.run, daemon=True)
        t.start()
        try:
            self.assertTrue(wait(lambda: svc.printer is not None))
            Printer.status, Printer.job = 'prusalink_status_printing.json', 'prusalink_job_printing.json'
            self.assertTrue(wait(lambda: svc.rec is not None))
            tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            hdr = '<14>1 - 0a:bc:12:34:56:7f buddy - - - msg=%d,tm=5,v=4 '
            for n in (1, 2, 2, 3, 4, 5):
                tx.sendto((hdr % n + 'gcode v="M118 OGCAM:LAYER:%d" 10\ntemp_bed v=60.0 40000\n' % n).encode(),
                          ('127.0.0.1', udp))
                time.sleep(0.1)
            tx.close()
            self.assertTrue(wait(lambda: svc.rec is not None and svc.rec.frames == 5))
            self.assertEqual(svc.tl.duplicates, 1)

            # the page: password required, secrets not sent back
            port = svc.web.server_port
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen('http://127.0.0.1:%d/api/status' % port, timeout=5)
            self.assertEqual(e.exception.code, 401)
            req = urllib.request.Request('http://127.0.0.1:%d/api/config' % port,
                                         headers={'Authorization': 'Basic YWRtaW46cGFnZXBhc3M='})
            body = json.loads(urllib.request.urlopen(req, timeout=5).read())
            self.assertIs(body['values']['prusalink']['password'], True)
            self.assertNotIn(Printer.password, json.dumps(body))

            Printer.status, Printer.job = 'prusalink_status_finished.json', 'prusalink_job_finished.json'
            self.assertTrue(wait(lambda: Store.got, timeout=30), svc.upload_state)
            path, headers, data = Store.got[0]
            self.assertTrue(path.startswith('/tl/'))
            self.assertTrue(path.endswith('_Benchy_0.4n_0.2mm_PLA_COREONE_45m.mp4'), path)
            out = os.path.join(d, 'got.mp4')
            with open(out, 'wb') as f:
                f.write(data)
            self.assertEqual(int(h264util.probe(out)['nb_read_frames']), 5)
            self.assertTrue(wait(lambda: 'uploaded' in (svc.upload_state or '')))
        finally:
            svc.running = False
            printer.shutdown(); printer.server_close()
            store.shutdown(); store.server_close()


class NoCamera(unittest.TestCase):
    def test_missing_helper_does_not_stop_the_service(self):
        d = tempfile.mkdtemp()
        cfg = config.Config({('camera', 'helper'): '/nonexistent/layercam-media',
                             ('timelapse', 'storage'): os.path.join(d, 'tl')}, path=os.path.join(d, 'c.ini'))
        cfg.save()
        svc = service.Service(cfg.path, port=0, hw_root=os.path.join(d, 'root'))
        svc.act([('start', 'Benchy.bgcode'), ('frame', 1, 0), ('finish', 'finished')])
        self.assertIsNone(svc.rec)
        self.assertIn('timelapse not started', svc.warning)
        svc.update_ir()                      # the night-mode call reaches the missing helper too
        self.assertEqual(svc.ir, ('day', False))


if __name__ == '__main__':
    unittest.main()
