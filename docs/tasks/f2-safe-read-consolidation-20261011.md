# F2 안전한 WordPress 읽기 통합 (2026-10-11)

**구현 범위:** 대표이미지 업로드의 최종 pre-import baseline recheck에서 글의 5개 필드와 썸네일 ID를 동일 WordPress 읽기 전용 실행으로 한 번에 가져온다.

| 경로 | 변경 전 | 변경 후 |
| --- | --- | --- |
| 직접 Python 실행 (pre-import recheck) | 글 읽기 1회 + 썸네일 메타 읽기 1회 = WP 읽기 2회 | WP 읽기 1회 |
| 기존 replace-image SSH 어댑터 | 이미 한 번의 원격 SSH snapshot으로 병합됨 | 여전히 SSH 1회 |
| guarded thumbnail CAS 및 쓰기 후 readback | 각각 별도 실행 | 그대로 유지 |

이는 **mock 기반 결정론적 호출 수**이고 실제 WordPress 실행시간·중앙값·P90 개선의 측정값이 아니다. 해당 SSH 어댑터에서는 순수 SSH 횟수 추가 절감이 없으므로 운영 성능 향상을 과장하지 않는다.

## 유지한 안전 계약

- 원래의 baseline read, 원격 이미지 SHA 검증, import 전 attachment 목록, 마지막 pre-import snapshot, import_pending fence, 비멱등 media import, 서버 내부 CAS, attachment·ALT 검사, postwrite readback을 전부 보존한다.
- snapshot 결과를 캐시하지 않는다. 스키마가 누락되거나 타임아웃이 나면 다른 값으로 복구 추측을 하지 않고 차단한다.
- SSH 어댑터는 replace-featured-image 명령에서만 고정 read-only 스크립트를 명시된 post ID에 허용한다. 새로운 쓰기 권한은 없다.
- 한 번의 snapshot 이후 다른 편집자가 변경하면 서버 측 CAS가 거절해야 한다. F2 신규 테스트가 이 시나리오를 장애 주입한다.
- edit-post의 initial read, 공개 글 변경 후 receipt 확인, 추가 image readback은 서로 다른 시점의 안전 경계이므로 결합하지 않았다.

## 검증·한계

test_f2_read_snapshots.py에는 WP roundtrip 2→1 단위 계수, 누락·변조된 snapshot 차단, fresh-read 재호출, 동시 편집 CAS 실패, SSH 응답 유실, read-only target allowlist가 포함된다. 기존 test_featured_image.py의 import 경합·사후 변경·중복 업로드 방지 검증도 유지한다.

실제 WordPress/OCI/cron 수정, 배포, 운영 실행시간 측정은 수행하지 않는다. 실서버 검증은 통합 및 배포 단계의 별도 승인된 disposable 절차에서 진행한다.
