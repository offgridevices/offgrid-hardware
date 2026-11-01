# Test data

- `aws4_testsuite/`: AWS's SigV4 test suite (Apache-2.0, `LICENSE`, `NOTICE`),
  the cases this signer applies to, copied from botocore
  (`tests/unit/auth/aws4_testsuite`, commit 2cd57933, 26 Oct 2026).
- `prusalink_*.json`: `/api/v1/status` and `/api/v1/job` answers written field
  for field the way Prusa-Firmware-Buddy 6.10.1 serialises them
  (`lib/WUI/nhttp/status_renderer.cpp`, `lib/WUI/link_content/basic_gets.cpp`
  `get_job_v1`), with the field names of Prusa-Link-Web's `spec/openapi.yaml`.
  The values (temperatures, names) are made up; not recorded from a printer.
- Metrics datagrams are written inline in `tests/test_metrics.py`, in the
  format of Buddy's `src/common/metric_handlers.cpp`; none was captured from
  a printer.
