# 2026-10-02 프로젝트 UTF-8 인코딩 하드닝

## 목적

Windows PowerShell 5.1, CP949 기본 로캘에서도 한글 WordPress/WP-CLI 데이터가 손상되지 않도록 저장 파일과 subprocess 경계를 UTF-8로 고정한다.

## 반영 범위

- `docs/INDEX.md`의 부산·대구·세종 10월 행사 기록에서 `?`로 소실된 한글 3개 항목 복원
- WordPress/WP-CLI 및 SSH 텍스트 subprocess에 `encoding="utf-8"`, `errors="strict"` 명시
- `.editorconfig`, `.gitattributes`에서 UTF-8 no-BOM 및 LF 정책 명시
- Git 추적 텍스트 파일의 strict UTF-8, BOM, U+FFFD, 대표 mojibake, 비의도 연속 물음표를 검사하는 `scripts/check_text_encoding.py` 추가 및 CI 연결
- Windows 예약 백업 스크립트의 로그를 UTF-8 no-BOM으로 기록하고 Python 입출력 인코딩을 UTF-8로 고정
- 기존 추적 파일의 UTF-8 BOM 제거

## 보존 원칙

`tmp/`, `scratch/`, `agent-publisher/data/editorial_runs/`에는 과거 실행 증거가 포함될 수 있으므로 이번 작업에서 일괄 삭제하거나 재인코딩하지 않는다. 새 정책은 정규 코드·문서·CI와 향후 생성 경로에 적용한다.

현재 다른 작업의 미커밋 변경이 있는 파일은 내용 손실 방지를 위해 광범위한 줄바꿈 일괄 정규화 대상에서 제외한다. `.gitattributes`와 `.editorconfig`가 이후 저장·커밋부터 LF를 강제한다.
