# Q1: 기존 브라우저 세션 기반 QA 하네스

**2026-10-11 실제 공개 WordPress 브라우저 검증 (격리 후속):** 기존 CoS Desktop의 브라우저 탭 제어 API는 이 세션에 노출되지 않았고 기존 CDP 9222는 Lenovo Vantage WebView만 제공했다. 이 후속 작업에서만 별도 사용자 승인 범위에 따라 **단 한 개의 격리 Edge headless 프로필**을 `scratch/tasks/live-qa-641/one-edge-profile/`에 만들고 로컬 CDP 9333으로 공개 게시물 #641을 조회했다. Microsoft Edge 155.0.4283.45, `wordpress_theme`, 실제 서버에서 다시 확인한 `publish`/저장 본문 SHA-256 `78aa3ebed10a8eac20ae5e927f69e7a5b468b14e20b690a277e138a61aec3c17`에 결합한 증거 `scratch/tasks/live-qa-641/evidence/b6d055b4-7c37-4199-bbd7-bef38c222633-evidence.json`을 남겼다.

하네스가 생성한 실제 PNG는 `b6d055b4-7c37-4199-bbd7-bef38c222633-390.png` (390×844, SHA-256 `94ed1059d0f70bd109ad6459caebed8f6e8e9b8b920df8495a13ad5dcdfa407e`) 및 `b6d055b4-7c37-4199-bbd7-bef38c222633-1280.png` (1280×900, SHA-256 `e50b75f1a7fc479aad1e15a1a9f8749c48cc21be2ee499006784d65c64f0e173`)이다. 독립 `verify_browser_qa.py`의 재평가: **`browser_pass`**, `content-mobile-desktop`·`layout-accessibility` 두 scope, `incomplete_scopes={}`; 두 화면의 TOC 12개/비교표 4개/링크/overflow/절반 폭 reflow 통과, DOM 글 ID=641. 화면 파일은 첫 viewport 픽셀을 캡처한 것이며 전체 글의 모든 하단 화면을 시각 캡처한 증거는 아니다. CTA 한 개가 `target=_blank`라 목적지 클릭은 수행하지 않았고 `cta-destination`은 이번 PASS 범위 밖이다. 수동 사이트 관리자 로그인·미리보기 검증도 수행하지 않았다.

`scratch/tasks/live-qa-641/keyboard-zoom-probe.json`에 CDP `Ctrl++` 다섯 번 전달 전후 측정이 기록돼 있다. DPR=1, innerWidth=1246, visualViewport.scale=1이 모두 변하지 않았고 Ctrl+0 복귀 뒤에도 같았다. **브라우저 자체 200% 확대 PASS는 없음**. 원래 하네스의 절반 viewport 재배치와 혼동하지 않는다. 운영 WordPress/DB/게시 상태를 변경하지 않았다. PowerShell 5.1에서 생성한 JSON 설정의 UTF-8 BOM도 실제 재현되어, 하네스가 BOM만 제거해 기존 JSON schema 검증은 유지하도록 보완했다.

**2026-10-11 후속 실제 세션 조사:** 기존 브라우저/CoS Desktop 연결에서 사용할 수 있는 browser tab 조작 API는 노출되지 않았다. 로컬 CDP read-only 조회 결과 `127.0.0.1:9222/json/list`는 Lenovo Vantage 위젯 탭 하나만 반환했고 `9237`, `9241`, `9223`은 접속할 수 없었다. Bloguito의 인증 미리보기나 공개 WordPress 탭은 확인되지 않아 본 하네스의 **실제 운영 페이지 390/1280 실행은 미검증**이며 로컬 정적 검증 또는 코드 테스트를 라이브 브라우저 QA 통과로 기록하지 않는다. 새 프로필·브라우저·포트는 실행하지 않았고 운영 WordPress도 수정하지 않았다. 이후 탭 연결을 확인한 때에만 대상 post ID와 WordPress 읽기 전용 content SHA를 별도 확인해 재실행한다.

**추가 독립 점검 (같은 날, 격리 worktree):** `9222`의 유일한 CDP target `02D9962E3F8BA28738D00076FEEA0F0B`는 `BatteryWidgetHost.exe`의 `msedgewebview2.exe`가 연 Lenovo Vantage 페이지임을 프로세스 명령줄까지 확인했다. `9223/9333`은 접속 불가했고 CoS Desktop browser tab API도 이 세션에 노출되지 않았다. 읽기 전용 WordPress CLI에서 **게시물 #641, publish, 저장 post_content SHA-256 `78aa3ebed10a8eac20ae5e927f69e7a5b468b14e20b690a277e138a61aec3c17`**을 수집했다. 비로그인 HTTP GET은 200 및 동일 글로 canonical redirect되며 body `postid-641`, article `post-641`, shortlink `p=641`의 정적 마커 존재를 확인했다. 이는 실제 브라우저 CDP 렌더·상호작용·390/1280 스크린샷이 아니므로 해당 항목들은 계속 **미검증**이다. 운영 WordPress에는 쓰기를 실행하지 않았다.

이 하네스는 **이미 실행 중인** Edge/Chrome의 CDP 탭 하나에 접속해 읽기 전용 DOM 측정, 제한된 브라우저 내 클릭 및 스크린샷을 수행한다. 브라우저 프로세스·프로필·디버그 포트를 **생성하거나 종료하지 않는다**. WordPress 글과 DB는 수정하지 않는다. `agents/change_classifier.py`가 확정한 `qa_scopes`가 유일한 검사 요구사항이며, 이 도구는 변경 내용을 재분류하지 않는다.

## 증거 범위와 한계

`render_source`는 세 값을 구별한다.

| 값 | 실제 관찰 대상 | WordPress 저장 글 QA 완료에 사용할 수 있는가 |
|---|---|---|
| `local_static` | `file://` 또는 localhost에서 브라우저로 열어 본 정적 HTML | **아니요.** 로컬 브라우저 결과일 뿐 운영 테마·인증 미리보기 검증이 아니다. |
| `wordpress_theme` | HTTPS WordPress 테마 DOM이 확인된 페이지 | 관련 scope PASS 및 task-state와 SHA 결합 시 가능 |
| `authenticated_preview` | HTTPS 미리보기 쿼리와 로그인 DOM이 확인된 WordPress 미리보기 | 관련 scope PASS 및 task-state와 SHA 결합 시 가능 |

모든 관찰은 **390×844** 및 **1280×900 CSS px**의 같은 기존 탭에서 이루어진다. 문서 전체 overflow, 표 caption/열·행/키보드 수평 스크롤, 모바일 카드 행수·표 가시성, TOC 앵커의 실제 클릭 후 해시, 내부/외부 링크, 설정된 CTA의 실제 같은 탭 이동, 계산기 정상/오류 입력 시나리오와 화면 결과를 기록한다. 200% 확대 관련 `zoom_simulated_half_viewport`는 절반 너비로 재배치한 **근사 검사**이며 **브라우저 네이티브 200% 확대, 스크린리더, 실제 모바일 터치의 검증이 아니다**. 이 세 항목은 필요한 경우 사람의 별도 QA에 남긴다.

실제 브라우저 실행 없이 HTML 파서·정적 스캔 결과만으로 `browser_pass`를 만들 수 없도록 정규 경로에서 CDP 실행 메타데이터, 두 viewport의 PNG 실제 픽셀 치수와 SHA, DOM 계측값을 확인한다. 계측 JSON은 별도 verifier가 전달된 성공 여부를 신뢰하지 않고 **다시 계산**한다. 이 기록도 위조 불가능한 브라우저 서명은 아니며, WordPress의 원본 `post_content`를 재수집하지 않는다. `post_id` 및 `content_sha256`은 기존 **WordPress 저장/readback에 묶인 task-state 값**과 맞춰 최종 검증한다. 증거의 글자만으로 운영 DB의 최신 상태까지 증명하는 것은 아니다.

후속 verifier는 두 viewport의 기록 URL이 요청 URL과 정확히 같아야 하고, WordPress 테마 DOM이 광고하는 글 ID(body `postid-N`, 본문 article `post-N`, shortlink `?p=N`)가 요청 post ID와 일치해야 성공 후보로 인정한다. 마커가 없거나 충돌하면 결과는 차단된다. 이는 다른 글의 CDP 탭을 검증 대상으로 잘못 기록하는 사고를 줄이는 검사이며 **WordPress 내용 SHA의 독립 브라우저 측 증명은 아니다**.

## 재사용 흐름 (Windows PowerShell)

1. **CoS Desktop에서 이미 연결된 브라우저 탭**을 재사용한다. 브라우저의 CDP 디버그 endpoint가 *이미* 열려 있을 때만 `http://127.0.0.1:9222/json/list`에서 대상 탭 ID를 찾는다. endpoint가 없으면 **새 Edge/Chrome·프로필·원격 디버그 포트를 띄우지 않는다**. 해당 세션에서 수동 QA하고 자동 브라우저 완료는 보류한다. 읽기 전용 테스트에서 외부 URL에 접근하기 전에 로그인·공개 민원/구매를 수행하지 않는다.
2. 대상 URL을 그 탭에 **미리 열고 로드 완료**한다. 스크립트는 지정한 정확한 URL과 기존 탭의 주소가 다르면 차단한다. 일반 공개 페이지는 `wordpress_theme`, WordPress 관리자에 로그인한 미리보기는 `authenticated_preview`, 로컬 HTML은 `local_static`으로 지정한다. 페이지 출처 유형을 추정해서 올리지 않는다.
3. 승인된 classifier의 `qa_scopes`를 설정 파일에 그대로 반영한다. 예:

```json
{
  "required_scopes": ["content-mobile-desktop", "layout-accessibility", "cta-destination"],
  "cta_targets": ["https://www.gov.kr/portal/service/serviceInfo/example"],
  "allow_cta_navigation": true,
  "calculator_cases": [
    {
      "id": "valid-input",
      "inputs": [{"selector": "#income", "value": "30000000"}],
      "trigger_selector": "#calculate",
      "result_selector": "#calculation-result",
      "expected_text": "300,000"
    },
    {
      "id": "invalid-input",
      "inputs": [{"selector": "#income", "value": "-1"}],
      "trigger_selector": "#calculate",
      "result_selector": "#calculation-error",
      "expected_text": "입력값"
    }
  ]
}
```

위 CSS selector·기대 결과·CTA는 **예시**이며 실제 포스트의 review된 DOM/행동 계약으로 교체해야 한다. `allow_cta_navigation`은 명시된 **같은 탭 `_self` CTA**를 실제 클릭해 URL 도착 여부를 확인한 후 기존 대상 페이지를 다시 탐색한다. `target=_blank`, 로그인 뒤 제출, 구매·신청 폼, 미확정 이동은 자동 PASS 처리하지 않고 미검증으로 남긴다. CTA 검사가 요구되는데 기대 URL이나 클릭 검증이 없으면 그 scope는 완료되지 않는다. 계산기 DOM이 관찰됐는데 기대 입력/결과 사례가 없으면 관련 화면 scope가 미완료된다.

```powershell
# 1. 기존 CDP 탭 확인 (새 브라우저 실행 금지)
Invoke-RestMethod http://127.0.0.1:9222/json/list |
    Select-Object id,title,url

# 2. 이미 열려 있는 탭에서만 실행. 식별값은 실제 readback에 맞춰 기입
node scripts/browser_qa_harness.mjs `
    --endpoint http://127.0.0.1:9222 `
    --target-id <기존-탭-ID> `
    --url 'https://lifeinfo24.org/?p=641' `
    --render-source wordpress_theme `
    --post-id 641 --content-sha <저장-후-64자리-SHA> `
    --config 'scratch/tasks/qa-641/config.json' `
    --output-dir 'scratch/tasks/qa-641/evidence'

# 3. 390/1280 screenshot + 관측값 독립 재평가 (WordPress write 0)
python scripts/verify_browser_qa.py 'scratch/tasks/qa-641/evidence/<run_id>-evidence.json'

# 4. 완료 판정 가능하고 task-state가 saved_pending_qa일 때에만
python agent-publisher/editorial_cli.py complete-task-qa `
    --post-id 641 --expected-content-sha256 <같은-64자리-SHA> `
    --qa-scope content-mobile-desktop --qa-scope layout-accessibility `
    --qa-evidence 'scratch/tasks/qa-641/evidence/<run_id>-evidence.json'
```

위 예시는 `--qa-scope`가 classifier 결과와 일치하는 경우에만 사용한다. 스크립트는 운영 WordPress 인증 데이터를 얻지 않으며, 인증 미리보기 URL의 비필수 쿼리는 저장된 증거에서 제거한다. 결과 PNG와 JSON은 `.gitignore` 적용된 `scratch/tasks/...` 아래 두고 외부 공유 전에 개인정보를 확인한다. 출력 JSON에는 `post_id`, `content_sha256`, URL 출처 유형, 실행 시점과 사용된 기존 target ID, 각 viewport 실제 측정, 파일 SHA, PASS/FAIL/UNVERIFIED와 남은 범위가 기록된다.

**실패·재시도:** 브라우저/tab endpoint 부재·페이지 URL 불일치·CDP 실패·계측 누락·스크린샷 변조·렌더 출처 불일치·CTA/계산기 오류는 각각 차단 또는 미완료로 남긴다. `complete-task-qa`는 필요한 reader QA에 대해 `--qa-evidence`가 없거나 local_static·다른 글 ID/SHA·실패 scope라면 거절한다. 한 건의 정상 `featured-image` readback-only 검증은 기존 attachment ID 비교를 유지한다. 저장 후 task-state를 새로 만들거나 자동 WordPress 게시/수정하지 않는다.
