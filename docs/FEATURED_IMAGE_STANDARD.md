# Bloguito 대표 이미지 표준

이 문서는 대표 이미지에 적용하는 현행 규약이다. 일반 정보글의 수동 작성과 스케줄러 자동 발행은 이미지 생성 경로가 다르다. 도시별 월간 행사 포스트에는 [EVENT_POST_STANDARD.md](EVENT_POST_STANDARD.md)의 추가 규칙을 적용한다.

## 1. 일반 정보글의 기본 경로

대표 이미지를 **새로 생성**할 때는 작업 형태(수동·자동), 후보 수, 최종 선택 주체와 관계없이 반드시 **ChatGPT 이미지 생성 도구(`image_gen`)**를 사용한다. Gemini 생성기, 로컬 Pillow/SVG/도형 합성, 다른 이미지 생성기, 로컬 클립아트/텍스트 포스터는 생성 대체 경로가 아니다. 예외는 *새로 생성하는 행위가 아닌* 검증된 공식 포스터 원본 보존처럼 별도 정책에 명시된 원본 활용뿐이다.

별도 개수 요청이 없으면 ChatGPT는 글의 주제와 독자 의도를 바탕으로 대표 이미지 **후보 5개를 기본 생성**한다. 사용자가 후보 개수를 1개·3개 등으로 지정한 경우에는 **반드시 해당 개수를 우선**한다. 여러 후보는 단순한 색상·폰트 변형이 아니라 구도, 장면, 시각적 접근 중 적어도 하나가 실질적으로 달라야 한다. 후보 최종 선택은 **사용자 직접 선택 또는 사용자가 위임한 에이전트 선택** 모두 가능하다. 명시적 위임 없이 다중 후보를 임의 선택하지 않는다. 사용자가 1개 제작과 바로 업로드를 요청한 경우에는 그 1개가 선택된 것으로 처리할 수 있다.

후보 생성 단계에서는 특정 템플릿을 강제하지 않는다. 기존의 왼쪽 텍스트/오른쪽 장면 비율, 텍스트 위치, 텍스트 블록 수, 고정 줄바꿈, 지정 서체, 색상 수, 장면 영역 비율 같은 레이아웃 제약을 일반 정보글의 ChatGPT 후보에 적용하지 않는다. ChatGPT가 주제에 맞는 구도, 이미지 스타일, 텍스트 사용 여부와 위치를 자율적으로 결정한다.

## 2. 선택 전후의 규칙

- **실제로 생성한 후보 N개 전부**를 생성 직후 CoS Core `save_image`로 각 원본을 로컬 `candidate-1`~`candidate-N` 안정 경로에 저장한다. 저장 도구는 반드시 현재 대화에서 ChatGPT가 생성한 **원본**만 저장해야 한다. 실패하면 브라우저 스크롤·nth 재시도·Base64 변환·별도 bridge·로컬 재그리기로 우회하지 않고 해당 후보를 차단하여 원인을 보고한다. 이어 `seal_featured_image_candidates.py`로 후보 번호·경로·SHA-256·format/dimensions를 manifest에 고정한다. 원본 저장·decode·seal 실패 후보는 선택지로 제시하지 않는다.
- 로컬에 고정한 N개 후보는 사용자가 비교·선택하려는 경우 모두 보여준다. 사용자가 에이전트에 선택을 위임한 경우에는 직접 품질을 비교해 선정 이유를 남기며, 사용자가 비교 화면을 요구하지 않았다면 별도의 선택 응답을 기다릴 필요가 없다.
- 선택 주체는 `user` 또는 `agent-delegated` 중 하나로 명시한다. `agent-delegated`는 사용자의 명시적 선택 위임·1개 즉시 업로드 지시에만 사용한다. 위임이 없으면 사용자 선택을 받아야 한다.
- 선택이 확정되기 전에는 어느 후보도 WordPress 대표 이미지로 지정하지 않는다. 선택한 candidate 번호를 해당 파일/SHA에 결합하며, 선택 이후에는 브라우저 히스토리에서 다시 이미지를 찾아 저장하지 않는다. 브라우저 캐시·스크린샷·클립보드·Base64 재조립·별도 대화 파일 bridge는 일반 후보 이미지 전달 경로에 사용하지 않는다.
- 선택된 원본 후보를 그대로 후속 업로드의 source로 사용하며 후보 번호를 바꾸거나 다른 후보로 대체하지 않는다. WordPress 규격에 맞추기 위한 결정론적 1200×675 staging은 허용하되 비율이 다른 경우 피사체를 잘라내지 않고 전체 전경을 보존한다.
- 생성 대표이미지의 staging 기본 출력은 WebP다. `stage_featured_image.py --candidate-manifest <manifest> --selected-candidate N --selection-mode user|agent-delegated <candidate-file>`에서 manifest와 선택 주체/번호는 필수이며 선택 source의 sealed path/SHA와 정확히 같아야 한다. 글자 품질 등 이유로 무손실이 필요한 특수 경우에만 PNG를 명시적으로 선택한다. 로컬 staging은 전경을 유지한 크기·형식 변환만 허용하며 장면 재제작·그리기는 금지한다.
- 선택 후에는 정규 `replace-featured-image` 또는 신규 draft의 `--image-path` 경로로 업로드하고 thumbnail readback을 확인한다.
- 이미지 생성 호출 때문에 작업 turn이 끊기는 환경에서는 `AFTER_IMAGE` 체크포인트를 남겨 다음 turn에서 후보 선택·업로드 작업을 이어간다.

### ChatGPT + CoS 즉시 업로드 경로 (기존 포스트, 1개 후보 즉시 업로드)

1. 먼저 CoS Core 연결을 실제 호출로 확인한다. `python scripts/featured_image_followthrough.py probe --post-id 856`로 SSH/WordPress 읽기도 검증하고, `begin --post-id 856`로 기준 본문 SHA·기존 이미지 ID와 `AFTER_IMAGE`를 **이미지 생성 전에** 저장한다. 기존 active 체크포인트가 있으면 `status`부터 확인하고 중복 `begin`을 하지 않는다.
2. ChatGPT 네이티브 `image_gen`에서 해당 포스트 주제에 맞는 후보를 생성한다. 한글 이미지라면 글자가 정확히 보이는지 확인한다. 생성에 성공하면 **같은 채팅의 CoS Core `save_image`로 원본을 로컬 `scratch/tasks/<작업명>/candidate-1.png`에 저장**한다. 이미지 생성 직후 턴이 종료된 경우 이 작업을 재개할 수 있도록 사전 체크포인트를 유지한다.
3. `python scripts/featured_image_followthrough.py continue --post-id 856 --source scratch/tasks/<작업명>/candidate-1.png --alt-text "해당 이미지 설명"`을 실행한다. 이 명령은 기존 SHA 봉인·WebP staging과 정규 `replace-featured-image`를 잇고 이미지 변경 CAS·readback을 수행한다. 업로드가 이미 시작된 뒤 결과가 불명확하면 **동일 명령을 무작정 재실행하지 않는다.** 먼저 failure receipt/WordPress 상태와 import fence를 검사한다.
4. `python scripts/featured_image_followthrough.py status --post-id 856`에서 `missing_requirements=[]`, `wordpress_verified=true`를 확인한 뒤에만 업로드 완료라고 보고한다.

이 단일 명령 경로는 **한 개 후보를 바로 업로드하도록 선택이 위임된 경우**만 지원한다. 기본 5개/다중 후보를 비교·선택하는 요청에는 기존 후보 전체 봉인 및 사용자 선택 경로를 사용한다. CLI는 ChatGPT `image_gen`을 실행하거나 비활성화된 호스트 도구를 활성화하지 못하며, 이미지 생성 호출 자체가 턴을 종료시키는 플랫폼 동작을 강제로 바꾸지 못한다. 따라서 체크포인트는 **중단 후 이어하기 보장 장치**이지 호스트의 자동 재호출을 보장하는 기능은 아니다.

## 3. 품질 기준

자유로운 구성을 허용하되 대표 이미지로서 다음 기준은 유지한다.

- 글의 핵심 주제와 이미지가 직접 관련되어야 한다.
- 모바일 썸네일과 데스크톱에서 핵심 피사체나 메시지를 알아볼 수 있어야 한다.
- 사람의 얼굴·손·신체, 문서, 제품 등 핵심 요소에 명백한 생성 오류가 없어야 한다.
- 이미지에 글자가 있다면 읽을 수 있고 내용이 정확해야 한다.
- 오래된 웹 배너, 저품질 클립아트, 깨진 글자처럼 명백히 품질이 낮은 결과는 후보에서 제외하고 다시 생성한다.

## 4. 스케줄러 자동 발행 예외

**스케줄러에서도 새 대표이미지에 Gemini나 로컬 이미지를 생성해 사용하지 않는다.** 스케줄러는 ChatGPT 이미지 생성 도구의 실제 출력과 sealed candidate/staging receipt를 제공받을 수 없는 경우, 새 커버를 만들어 발행하는 작업을 **실패 차단**해야 한다. 자동 게시 성공을 위해 생성 제공자를 바꾸거나 로컬 이미지를 대체하는 것은 금지한다.

스케줄러의 비전 검수는 실제 ChatGPT 원본을 검사하는 용도에만 사용할 수 있다. 검수가 생성 원본을 대체하거나 새 장면을 합성할 권한을 주지는 않는다.

## 5. 공개 전 이미지 승인 결속

이미지 업로드 성공이나 1200×675 규격 통과만으로 공개 자격을 만들지 않는다. 수동 경로는 사용자 후보 선택, 스케줄러 경로는 자동 비전 검수 통과가 있어야 versioned publication attestation을 만들 수 있다. 이 attestation은 현재 reviewed 본문 SHA, 제목 SHA, 대표 attachment ID, 이미지 파일 SHA, ALT SHA, review digest, source/review freshness와 `requires_live_state` 여부에 결합한다. attestation 생성 시 current policy의 review binding과 source declaration/freshness 검사를 다시 통과해야 한다.

본문·제목·대표이미지·ALT·원본 파일 중 하나라도 승인 뒤 바뀌거나 검토 시간이 만료되면 공개 게이트는 실패한다. 성공적으로 공개되면 attestation은 소비되어 삭제하므로 공개 글을 다시 draft로 되돌린 경우 과거 승인을 재사용하지 않는다. 과거 draft에는 승인 기록을 임의로 backfill하지 않는다.

로그인한 WordPress 관리자의 직접 발행 권한은 본래대로 유지한다. Python 자동 발행은 `promote-draft --confirm-publish`과 attestation을 요구한다. `requires_live_state=true`인 글은 현재 판매·신청·예매·재고 상태를 정규 경로에서 재조회하고 reviewed snapshot과 비교해야 한다.

## 6. 행사 포스트

도시별 월간 행사 포스트와 공연·콘서트의 공식 포스터 처리에는 별도 현행 규칙이 있을 수 있다. 해당 글에는 `EVENT_POST_STANDARD.md`와 공식 포스터 보존 규칙을 우선 적용한다.
