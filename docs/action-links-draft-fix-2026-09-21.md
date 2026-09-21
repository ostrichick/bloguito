# 행동 버튼 목적지 수정 및 운영 확인 — 2026-09-21

## 원인과 범위

- 기존 `agents.editorial.render()`가 `source_type=official`인 근거 자료 3개를 일괄적으로 ‘신청 및 조회 서비스’ 버튼으로 출력했다. 티머니 사업 소개·플랫폼 소개·2026 추석 안내 글이 즉시 예약할 수 있는 것처럼 표시됐고, 민간 서비스에도 정부·공공기관 연결이라는 문구가 붙었다.
- 사용자 요청에 따라 기존 WordPress **임시글 #345**만 갱신했다. 제목·기존 원고 문장·공식 근거 3건·게시 상태를 보존했고 정식 공개는 수행하지 않았다.

## 목적지 확인 및 편집 규칙

- 티머니 운영사의 고속/시외 예매 안내 페이지에 실제 연결된 공식 통합예매 목적지를 확인했다: 고속버스 `https://www.kobus.co.kr/main.do`, 시외버스 `https://intercitybus.tmoney.co.kr/`. 고속버스 페이지는 티머니 운영사의 실제 예매 링크가 근거이며, 실시간 잔여좌석을 예측하지 않았다.
- 티머니GO 개별 앱 설치 목적지를 확인했다: Android `https://play.google.com/store/apps/details?id=kr.co.tmoney.tia`, iPhone `https://apps.apple.com/kr/app/id1483433931`.
- 공식 근거 URL은 하단 출처로만 출력한다. 원고의 근거 `sources[].actions`에 검증된 `booking/install/lookup/apply/purchase` 목적지가 명시될 때만 상단 행동 버튼을 렌더링한다. URL·라벨·설치 스토어 형식을 검증하고 최대 4개로 제한한다. 기본 출처를 자동으로 행동 버튼에 복사하는 경로를 제거했다.
- 모델의 별도 편집 검토에도 소개·홍보·보도자료 페이지를 행동 버튼으로 제공하지 않는 조건을 추가했다. 버튼 없는 글은 CTA 박스 전체가 나타나지 않는다.

## 작업 경로 및 검증

- 로컬 `editorial_cli.py review`와 `check` 재수행 결과 `status=ready`, 사유 없음. 수정은 검토 원고의 출처 metadata `actions`에 한정했다.
- 변경 전 운영 WordPress 본문 SHA256: `f29143b7bf23de9c99f8b1b67ba51204d2dd322f70c15b579ba520262a18eaca`. 원문 해시 및 수정 시점 재검사, 원고 불변 확인, 서버 원본 백업 후 공통 CLI의 `update-draft`로 해당 ID의 본문과 검토 bundle을 함께 갱신했다.
- 서버 코드 교체 전 파일 해시를 대조하고 백업했다. 교체된 파일: `agents/editorial.py`, `agents/editorial_writer.py`, `editorial_cli.py`, `docs/EDITORIAL_SYSTEM.md`, 신규 `agents/editorial_draft_updater.py`. 서버 백업은 비공개 `data/editorial_runs/deploy-action-links-20260921T110101957552`에 저장했다.
- WordPress 재조회: `#345`는 **draft**, 새 SHA256 `6f33c79af95d9961571af7aeeab357e311c3308b20adefa08dd191602b2b8239`. 버튼 목적지 정확히 4건·라벨 일치, 기존 거짓 공공기관 설명 제거, 하단 근거 3건 보존, 저장된 검토 bundle과 렌더링 결과 완전 일치.
- 로컬 전체 유닛 테스트 **162개 통과**. 기존 #243 공개 전환 이후에도 11개 원고의 실제 manifest 상태·HTML 형태를 검증하도록 오래된 초안 테스트를 갱신했다. 이전 GitHub CI의 `publish != draft` 실패를 야기한 잘못된 일괄 상태 가정도 이 변경으로 제거했다.
- 원고 자체의 사실 관계를 다시 독립 조사한 것은 아니며, 이번 검토 범위는 버튼 목적지·기존 원고 보존·출처·배포 결과다. 현재 예약 가능한 좌석 수는 확인하거나 표시하지 않았다.
