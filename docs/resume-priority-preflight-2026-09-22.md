# 우선 게시물 #55·#79·#101 재개 독립 점검 — 2026-09-22

**최신 상태(2026-09-22 16:11 KST): #55·#79·#101 모두 공식 출처 재수집, 독립 모델 의미 검토 및 새 운영 저장상태 사전검사 `ready` 완료.** 아래 15:54 차단은 해결 전 과거 기록이다. 이제 각 신규 검토 순수 bundle과 새 매니페스트를 함께 사용하고, 실배포 담당자가 바로 직전에 정규 updater의 동시 수정/원본 SHA/출처/전체 중복 상태 검사를 다시 통과해야 한다. #103 보류는 변함없다.

| ID | 새 검토 순수 bundle (상대 경로 접두: `tmp/legacy_audit_20260922/priority-prime/`) | 최종 preflight 증거 | 독립 리뷰 KST | 최종 원본·후보 SHA |
| --- | --- | --- | --- | --- |
| #55 | `resume-reviewed-55-1601/candidate.json` | `resume-reviewed-55-1601/approval-verified/approval-manifest.json`, 16:05:11 KST, ready·0 reasons·official source match | 16:04:44 | 아래 기존 SHA와 동일 |
| #79 | `resume-reviewed-79-1601/candidate.json` | `resume-reviewed-79-1601/approval-v2-verified/approval-manifest.json`, 16:09:35 KST, ready·0 reasons·official source match | 16:06:11 | 아래 기존 SHA와 동일 |
| #101 | `resume-reviewed-101-1601/candidate.json` | `resume-reviewed-101-1601/approval-v2-verified/approval-manifest.json`, 16:10:58 KST, ready·0 reasons·official source match | 16:08:07 | 아래 기존 SHA와 동일 |

세 최신 리뷰 모두 6개 의미 항목이 `true`, `issues=[]`이며, 원고의 본문·조건·후보 렌더 해시는 아래 표의 최초 검토안과 같다. 모두 새 출처 스냅샷 보건복지부 공식 공지 SHA `a130f6c6383a191b087ce20851c6d6934746ce054561060e82d6d266318a7822`를 포함하고, 다른 공식 출처까지 실제 재조회 일치했다. 적용 입력은 이 표의 **새 `candidate.json`** 세 개로 교체한다. 이전 검토 원고를 새 정규화 수집기 검토 서명 없이 적용하면 안 된다.

15:54 차단의 첫 원인은 공식 공지 첨부 다운로드/미리보기 횟수 변동이었다. `editorial_writer.py`에서 이 공지의 특정 첨부 메타데이터에 한정하여 누적 횟수만 정규화하고 제목·파일명·파일 크기·기사 내용의 해시 감시는 유지했다. 담당 작업자가 관련 신규 테스트 4개와 기존 테스트 7개가 통과했다고 보고했다. #55 업데이트 후 뒤따른 #79·#101에서는 별도의 `duplicate_topic` 오탐도 발생했다. `search_intent.py`의 기존 글 수정 경로만 범위를 제한해 검증된 출처 *각주* 공유가 중복을 뜻하지 않도록 하고, 제목 용어 일치·본문/CTA 링크·기존 원시 URL·신규 주제 엄격 중복 검사는 유지하도록 게시 담당자가 수정하고 타깃 테스트를 통과했다. 수정 이전 실패 패키지는 그대로 보존했고 위 표의 **서로 다른 새 폴더**에서 최종 사전검사를 다시 통과했다.

## 범위·관찰 시점

2026-09-22 **15:52~15:58 KST**, WordPress에 쓰지 않고 SSH의 `wp post list/get`만 실행하여 저장 원문과 전체 상태를 새로 조회했다. 각 승인 매니페스트·최종 원고·검토 기록·백업 실물 SHA를 대조하고 공식 URL 전체를 다시 수집했다. 프로젝트 Git HEAD 확인 당시 `c58b7aa`이며 이 문서 외 파일을 수정하지 않았다. 이 시점의 재조회는 실제 게시 순간의 동시 변경 검사까지 보장하지 않는다.

**15:54 당시 기록:** 세 편 모두 운영 원본 동일성/백업/의미 검토는 확인됐으나, 그 시점 `prepare_post_approval.py`가 공통 공식 출처 SHA 변경으로 `blocked`를 반환했다. 이후 위의 별도 정규화·독립 재검토·재검사로 모두 `ready`가 됐다. 게시물 변경을 즉시 적용하라는 사용자의 최신 지시는 승인 요건 충족 후 적용을 허용하되 출처·검토·CAS 실패를 무시하도록 허용하지 않는다.

## 운영 저장 원본·전체 인벤토리·백업

실제 명령의 읽기 범위는 `post_type=post`, `post_status=publish,draft,pending,future,private`, `posts_per_page=-1`, `fields=ID,post_title,post_status,post_content`였다. **40건 = publish 30 + draft 10**, 서로 다른 ID 40개. #137은 별도 작업자의 라이브 변경으로 이 시점 저장 SHA가 `19654865151823398b1dcd3a7661a5e1b3016ee5964048b76494c114d96da6df`였으므로 예전 인벤토리 재사용 금지. #55/#79/#101/#103은 목록에서 각각 정확히 한 건의 publish로 조회됐다. #55/#79/#101을 별도 `wp post get --format=json`으로 다시 읽어 목록의 SHA 및 매니페스트 원본과 일치함을 확인했고 세 글 모두 발췌문이 비어 있었다.

| ID | 최종 선택 순수 bundle | 원본 `post_content` SHA256 (15:53 live) | 선택 후보 렌더 SHA256 | 독립 검토 `checked_at` KST |
| --- | --- | --- | --- | --- |
| 55 | `tmp/legacy_audit_20260922/priority-prime/priority-reviewed-55.json` | `10d2b1a8d8db7b1e3d935ba8269ee974de201da625ac4e847003ffca73149a01` | `642b1c3c0572d7cc1c6d3ccbf11cf23a5d20e9812742a833f806f004b23373ed` | 2026-09-22 13:23:47 |
| 79 | `tmp/legacy_audit_20260922/priority-prime/priority-reviewed-79.json` | `3da256c5cde1add3e8083eab37061c9abda22118123516c433833452458578fa` | `ddd5aba8fa081493ff3e236881b2bec59fd4138f27d0f62165110f98992a1677` | 2026-09-22 13:24:47 |
| 101 | `tmp/legacy_audit_20260922/content-worker1/priority-candidate-101.json` | `2e8d80670b8d5b61e2dd77a0e3a7c2d783eea58048904d1d1a4d341e426a225a` | `8a2164194215f35fb1ae9f5914d97fac5d278f730e26f1f1981a2a258335334c` | 2026-09-22 13:51:05 |

위 세 bundle 모두 `brief.existing_post_id`가 대상 ID이고 `review` 항목이 최상위에 있는 **순수 bundle**이다. 각각 의미 검토 6항목 `true`, `issues=[]`, 검토 유효기간 24시간 안이다. #101의 `content-worker1/priority-review-101.json`은 `{bundle,report}`로 감싼 **출력 보고서**여서 updater 입력이 될 수 없다. 최종 순수본 `priority-candidate-101.json`은 이 보고서의 `bundle`과 동일한 검토 시각을 가진다.

승인 비교 화면/원본 백업은 각각 다음 경로를 사용한다.

- #55: `tmp/legacy_audit_20260922/priority-prime/approval-55-ready/`
- #79: `tmp/legacy_audit_20260922/priority-prime/approval-79-ready/`
- #101: `tmp/legacy_audit_20260922/content-worker1/approval-101-20260922-r2/`

각 폴더의 `post-original.PRIVATE.json`을 `Get-FileHash SHA256`으로 직접 계산하여 매니페스트의 `original_full_backup_sha256`과 일치하는지 확인했다. 두 번째 백업 `backups/preapproval/2026-09-22/post{ID}-original-final.PRIVATE.json`도 모두 실제 존재하고 첫 번째 파일과 바이트 해시가 같았다. 백업은 개인·비공개 정보 가능성이 있어 공개 페이지/대시보드/Git에 링크하지 않는다. 동일 컴퓨터의 두 사본은 물리적 별도 백업이나 운영 복원 성공을 증명하지 않는다.

## 원고 선택에서 특히 주의할 점

**#55:** 늦게 생성된 `content-worker1/approval-55-20260922-r2`의 렌더 해시는 `f00a64e1…`이며 대리 신청 가능한 가족·시설장 구체 범위 및 재외국민 주민등록자 제외 문장이 빠졌다. 독립 보강을 거친 `priority-prime/priority-reviewed-55.json`에는 배우자·자녀·형제자매·친족·사회복지 시설장, 친족 범위 8촌 혈족/4촌 인척과 해당 제외 조건이 실제 공식 인용에 연결되어 있다. 따라서 위 표의 `priority-prime` 후보를 사용한다.

**#79:** 두 작업자의 승인 폴더는 동일한 렌더 SHA `ddd5aba8…`를 가진다. 보건복지부 소득인정액 계산식과 공식 모의계산 **진입 링크**만 확인했고 복지로 JS 계산기 입력 필드·완료 화면은 실측하지 않았다. 해당 화면의 세부 버튼·입력 완료 성공을 표현해서는 안 된다.

**#101:** `priority-prime/approval-101-ready`는 렌더 SHA `2cdfb3d1…`인 다른 표 포함 대안이며 선택본이 아니다. 정확한 선택은 `content-worker1/approval-101-20260922-r2`와 위 표의 순수 bundle이다. 선택본에는 각각 산정된 연금액 **부부 감액 20%**, 지역별 기본재산 공제액(1억 3,500만/8,500만/7,250만 원), 자동차 4,000만 원과 회원권 별도 규칙이 공식 원문에 직접 묶여 있다. 숫자 본문을 정적 수집으로 확인하지 못한 국가법령정보센터 고시는 수치 근거에서 제외한다. 두 대안을 서로 섞으면 독립 검토 서명이 무효다.

## 15:54 새롭게 확인된 공통 차단과 근거

정규 사전검사 `tmp/legacy_audit_20260922/priority-prime/resume-preflight-55-1558/approval-manifest.json`은 원본 SHA·후보 SHA 동일, `validation_report.ready`, 그러나 `official_sources_changed_since_review`, `source_hashes_match_live=false`로 차단했다. #79와 #101 역시 같은 차단을 반환했다고 게시 담당자에게 보고받았고, 이 점검에서 **각 후보의 공식 URL을 직접 다시 수집해 모두 비교**했다. 세 후보 모두 보건복지부 `https://www.mohw.go.kr/board.es?act=view&bid=0027&list_no=1488478&mid=a10503010100` 딱 한 URL의 SHA만 불일치했다. 나머지는 #55 3개, #79 2개, #101 4개 모두 원고 저장 SHA와 재조회 SHA가 일치했다.

해당 URL의 이전 해시는 #55와 #79 `d346dcb94d0829916033829b04b79ef35d5626c413084a3261b8bb6355e76c34`, #101 `f3f4bba5e1e0b09b74cad803d42a36c696d977b9d3b96ebdc15144429756edc3`; 15:58 조회 시 공통 새 해시는 `3fc897de7b25d2ae4fa704819944f7f37e6c2ac59276d61c4f4079723bce6116`. 원문 텍스트의 줄 단위 diff에서 확인된 변화는 같은 첨부의 HWPX `127.32KB` 다운로드 횟수 **2389→2390**, PDF `363.34KB` 다운로드 **21006→21007**, 일부 조회 순간 PDF 미리보기 **2751→2752**뿐이다. 기사 본문, 지급 기준·금액·날짜, 파일 이름과 파일 크기의 diff는 없다. 다만 출처 SHA가 실제 달라진 사실은 변경 범위를 확인했더라도 정책 검사를 우회할 근거가 아니다.

당시 `agent-publisher/agents/editorial_writer.py`의 보건복지부 처리기는 `li.hit` 조회수만 한정 제거했다. 이후 보건복지부 `/board.es`의 **특정 공지 첨부 메타데이터 구조**에서 다운로드/미리보기 누적 횟수만 제외하고 첨부 이름·파일 크기·본문 내용 및 일반 본문의 모든 숫자를 그대로 해시하도록 수정·시험했다. 일반 숫자 삭제나 해시 강제 승인 없이 `sources → 별도 의미 review → check → fresh SSH preflight`를 **세 후보 모두 새 폴더에서 완료**했다. 기존 review의 digest는 재사용하지 않았다.

## 적용 순서와 정규 실행 경계

차단 해결 뒤 #55 → #79 → #101을 **순차적으로** 처리한다. 한 편씩 직전 전체 상태 인벤토리(모든 상태), 해당 `post get` 저장 SHA·제목·slug·status·excerpt, 최신 공식 출처 SHA와 24시간 검토 서명을 검증해야 한다. #55 적용 뒤에는 다음 글의 인벤토리를 새로 읽어 중복 주제 검사와 원본 동시 수정 감지에 사용한다. 원본 SHA 또는 출처 해시 불일치, 검토 오류, 게시 ID 불일치 시 즉시 중단하고 원고 수정·재검토로 돌아간다. `update_existing_via_ssh.py`는 로컬 정규 `editorial_updater`의 검사를 유지한 채 WP transport만 엄격히 제한하므로 로컬에서 실행 가능하며 운영 SSH 배포/직접 WP-CLI 편집 우회는 필요 없다. 아래는 **최종 새 검토 순수 bundle을 사용하는 운영 담당자용 명령**이다. 각 명령은 실행 직전 라이브 상태·출처 검사를 다시 수행한다.

```powershell
./agent-publisher/.venv/Scripts/python.exe scripts/update_existing_via_ssh.py tmp/legacy_audit_20260922/priority-prime/resume-reviewed-55-1601/candidate.json --post-id 55 --expected-content-sha256 10d2b1a8d8db7b1e3d935ba8269ee974de201da625ac4e847003ffca73149a01 --confirm-update
./agent-publisher/.venv/Scripts/python.exe scripts/update_existing_via_ssh.py tmp/legacy_audit_20260922/priority-prime/resume-reviewed-79-1601/candidate.json --post-id 79 --expected-content-sha256 3da256c5cde1add3e8083eab37061c9abda22118123516c433833452458578fa --confirm-update
./agent-publisher/.venv/Scripts/python.exe scripts/update_existing_via_ssh.py tmp/legacy_audit_20260922/priority-prime/resume-reviewed-101-1601/candidate.json --post-id 101 --expected-content-sha256 2e8d80670b8d5b61e2dd77a0e3a7c2d783eea58048904d1d1a4d341e426a225a --confirm-update
```

각 적용 이후 라이브 `post get` 저장 본문이 **방금 선택된 검토 후보** SHA인지 재조회하고 공개 사이트에서 목차·링크·모바일/데스크톱/네이티브 200% 화면을 확인해야 한다. 문제 발생 시 현재 운영 본문 SHA가 방금 적용 후보와 같을 때만 승인된 복구 절차에서 원본 전체 백업의 `post_content`/이전 excerpt를 사용한다. 다른 편집이 발견되면 강제 덮어쓰기·자동 롤백 금지.

## #103의 별도 상태

15:53 인벤토리의 #103 저장 원본 SHA는 `3272f95ac464cee49941d86ad142d0d5c1f6c625bdb376727b04e959a1b07444`로 기존 백업과 동일하다. 출처 기록에서 목포시 보건소 9월 16일 공지의 자체사업 대상 상한은 **15~65세**, 9월 18일 시 보도자료는 **15~64세**로 충돌한다. 확인한 6개 의료기관은 어린이 위탁기관만의 목록이며 임신부·어르신·시 자체사업 대상까지 보장되는 목록이 아니다. 독립 공식 정정/현행 대상·기관별 범위 확인 전 #103은 수동 차단하며, 이번 게시 순서에 포함하지 않는다.

이 문서 작업에서 WordPress 게시·수정·서버 파일 설치·정기 스케줄 등록·Git stage/commit/push·복구 실행은 수행하지 않았다.
