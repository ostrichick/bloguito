# 📢 [Bloguito] 대한민국 생활정보 24 - AI 멀티 에이전트 자동화 블로그

본 디렉터리는 오라클 클라우드(OCI) 인스턴스에 구축된 **워드프레스 및 5대 멀티 에이전트 자율 포스팅 시스템('생활정보 24')**의 핵심 문서 및 프로젝트 저장소입니다.

---

## 📚 프로젝트 주요 문서 안내

| 문서 파일 | 설명 및 용도 | 바로가기 |
| :--- | :--- | :---: |
| **`PROJECT_HANDOVER.md`** | **종합 프로젝트 인계서 & 아키텍처 가이드**<br>- 서버 인프라, Docker 환경, 5대 에이전트 구조, 프롬프트 규칙, 크론 스케줄, 전체 히스토리 총정리 | [열기](./PROJECT_HANDOVER.md) |
| **`implementation_plan.md`** | **시스템 지능화 및 인프라 최적화 계획서**<br>- 긴급 버그 수정, 1GB RAM 튜닝, 내부 링크(Interlinking), 타이포 배너 설계 | [열기](./implementation_plan.md) |
| **`walkthrough.md`** | **종합 개선 및 최적화 완료 결과 보고서**<br>- 캐싱 가동, 백업 스크립트, DB 메모리 캡, 크론 등록 등 실서버 검증 내역 | [열기](./walkthrough.md) |

---

## 🖥️ 서버 접속 및 기본 정보

- **서버 공용 IP**: `<YOUR_ORACLE_SERVER_IP>`
- **블로그 주소**: `http://<YOUR_ORACLE_SERVER_IP>/`
- **관리자 페이지**: `http://<YOUR_ORACLE_SERVER_IP>/wp-admin/`
- **SSH 접속 명령어 (PowerShell)**:
  ```powershell
  ssh -i "<PATH_TO_SSH_KEY>/ssh-key.key" ubuntu@<YOUR_ORACLE_SERVER_IP>
  ```

---

## 🤖 5대 멀티 에이전트 파이프라인

```text
[1. Radar Agent]      구글 뉴스 RSS 실시간 탐색 및 중복 필터링 (키워드당 2개 버퍼)
       ↓
[2. Curator Agent]    Protobuf 암호화 링크 디코딩, 본문 추출, NOL 티켓 예매처 능동 가격 발굴
       ↓
[3. Copywriter Agent] Gemini 3.6 Flash 기반 팩트 100% 원고 집필 & 내부 링크(Interlinking) 자동 주입
       ↓
[4. Designer Agent]   1번 카드뉴스 인포그래픽 / 2번 4K 실사 스톡+매거진 타이포 배너 자동 교차 생성
       ↓
[5. Publisher Agent]  워드프레스 포스팅 등록, 특성 썸네일 장착, 내부 링크 색인 자동 누적
```

---

## ⏰ 자동화 스케줄 (KST 기준)

- **매일 새벽 04:00**: MariaDB 데이터베이스 자동 압축 백업 및 7일 롤링 보관 (`backup_daily.sh`)
- **매일 아침 08:00**: 3대 카테고리 자율 발행 파이프라인 무인 가동 (`run_daily.sh`)
