# Test data

- `aws4_testsuite/`: AWS's SigV4 test suite (Apache-2.0, `LICENSE`, `NOTICE`),
  the cases this signer applies to, copied from botocore
  (`tests/unit/auth/aws4_testsuite`, commit 2cd57933, 26 Oct 2026).
- `prusalink_*.json`: `/api/v1/status` and `/api/v1/job` answers written field
  for field the way Prusa-Firmware-Buddy 6.10.1 serialises them
  (`lib/WUI/nhttp/status_renderer.cpp`, `lib/WUI/link_content/basic_gets.cpp`
  `get_job_v1`), with the field names of Prusa-Link-Web's `spec/openapi.yaml`.
  The values (temperatures, names) are made up; not recorded from a printer.
- `metrics_*.bin`: datagrams in the format of `src/common/metric_handlers.cpp`
  (syslog header, then line-protocol points); made with that code's formats,
  not captured from a printer.
