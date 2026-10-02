"""Precisely scoped source text adapters; preserve reviewed facts and conditions."""
import hashlib
import re
from datetime import datetime
from urllib.parse import parse_qs, urlsplit
import requests
from agents.temporal_validation import KST


def _koreakr_article_text(soup, url):
    """Extract only the verified Korea.kr article, not its rotating news rails.

    A changed article structure must fail the source recheck rather than silently
    hashing unrelated recommendations or dropping the evidence-bearing body.
    """
    parsed = urlsplit(url)
    # The 2026 Chuseok emergency-medical press release is currently served from
    # admin2.korea.kr. Its article body is stable, while the page footer contains
    # rotating "실시간 인기뉴스" timestamps and rankings. Scope this extractor
    # to the exact reviewed release so a recheck hashes only evidence-bearing
    # article content and still fails closed if the article structure changes.
    if (parsed.hostname == 'admin2.korea.kr'
            and parsed.path == '/briefing/pressReleaseView.do'
            and parse_qs(parsed.query, keep_blank_values=True) == {
                'newsId': ['156782659'], 'pWise': ['mSub'], 'pWiseSub': ['C1']}):
        heads = soup.select('.article_wrap .article_head')
        bodies = soup.select('.article_wrap .article_body .view_cont')
        if len(heads) != 1 or len(bodies) != 1:
            raise ValueError('koreakr_press_release_main_missing_or_ambiguous')
        titles = heads[0].select(':scope > h1')
        info = heads[0].select(':scope > .info > span')
        if (len(titles) != 1 or len(info) != 2
                or not re.fullmatch(r'\d{4}\.\d{2}\.\d{2}', info[0].get_text(' ', strip=True))):
            raise ValueError('koreakr_press_release_main_missing_or_ambiguous')
        parts = [titles[0].get_text('\n', strip=True), info[0].get_text(' ', strip=True),
                 info[1].get_text(' ', strip=True), bodies[0].get_text('\n', strip=True)]
        if any(not part for part in parts):
            raise ValueError('koreakr_press_release_main_missing_or_ambiguous')
        return '\n'.join(parts)
    # The 2025-03-31 One-Click briefing has a different article-head layout
    # from /news/policyNewsView.do. Scope this extractor to its *exact* URL:
    # title is outside article_wrap, date/byline and attachments are inside
    # article_head, and the full transcript lives in article_body/view_cont.
    # The adjacent aside.as_side holds independently rotating recommendations.
    if (parsed.hostname == 'www.korea.kr'
            and parsed.path == '/briefing/policyBriefingView.do'
            and parse_qs(parsed.query, keep_blank_values=True) == {'newsId': ['156681719']}):
        prefix = 'main#main section#container'
        titles = soup.select(f'{prefix} .view_title h1')
        info = soup.select(f'{prefix} .article_wrap .article_head .variety .info > span')
        bodies = soup.select(f'{prefix} .article_wrap .article_body .view_cont')
        attachments = soup.select(f'{prefix} .article_wrap .article_head .filedown > dl')
        if (len(titles) != 1 or len(info) != 2 or len(bodies) != 1
                or len(attachments) != 1
                or not re.fullmatch(r'\d{4}\.\d{2}\.\d{2}', info[0].get_text(' ', strip=True))):
            raise ValueError('koreakr_briefing_main_missing_or_ambiguous')
        attachment = attachments[0]
        labels = attachment.select(':scope > dt')
        rows = attachment.select(':scope > dd > p')
        if (len(labels) != 1 or labels[0].get_text(' ', strip=True) != '첨부파일'
                or not rows):
            raise ValueError('koreakr_briefing_attachments_missing_or_ambiguous')
        files = []
        for row in rows:
            links = row.select(':scope > span:first-child > a')
            if len(links) != 1:
                raise ValueError('koreakr_briefing_attachments_missing_or_ambiguous')
            filename = links[0].get_text(' ', strip=True)
            href = links[0].get('href', '')
            if (not re.search(r'\.(?:hwp|hwpx|pdf)$', filename, re.IGNORECASE)
                    or not re.fullmatch(r'/common/download\.do\?fileId=\d+', href)):
                raise ValueError('koreakr_briefing_attachments_missing_or_ambiguous')
            files.append(f'{filename}\n{href}')
        parts = [titles[0].get_text('\n', strip=True), info[0].get_text(' ', strip=True),
                 info[1].get_text(' ', strip=True), '첨부파일', *files,
                 bodies[0].get_text('\n', strip=True)]
        if any(not part for part in parts):
            raise ValueError('koreakr_briefing_main_missing_or_ambiguous')
        return '\n'.join(parts)
    if parsed.hostname != 'www.korea.kr' or parsed.path != '/news/policyNewsView.do':
        return None
    prefix = 'main#main section#container'
    titles = soup.select(f'{prefix} .view_title h1')
    subtitles = soup.select(f'{prefix} .article_wrap .article_head > h2')
    dates = soup.select(f'{prefix} .article_wrap .article_head .variety span')
    bodies = soup.select(f'{prefix} .article_wrap .article_body .view_cont')
    if (len(titles) != 1 or len(subtitles) != 1 or len(bodies) != 1 or not dates
            or not re.fullmatch(r'\d{4}\.\d{2}\.\d{2}', dates[0].get_text(' ', strip=True))):
        raise ValueError('koreakr_article_main_missing_or_ambiguous')
    parts = [titles[0].get_text('\n', strip=True), subtitles[0].get_text('\n', strip=True),
             dates[0].get_text(' ', strip=True), bodies[0].get_text('\n', strip=True)]
    if any(not part for part in parts):
        raise ValueError('koreakr_article_main_missing_or_ambiguous')
    return '\n'.join(parts)


def _official_request_headers(url):
    """Use browser-equivalent headers only for verified public routes that gate Python UAs.

    NOL's public product page returns a generic 403 interstitial to Python's
    default user agent while the same URL is public in a normal browser.
    Incheon Airport's public Korean subview pages similarly return an empty
    HTTP 302 to Python's default user agent but HTTP 200 to a browser UA.
    Keep these exceptions host/path scoped; redirects and non-200 responses
    still fail closed in fetch_sources().
    """
    parsed = urlsplit(url)
    nol_product = (parsed.scheme == 'https' and parsed.hostname == 'nol.yanolja.com'
                   and re.fullmatch(r'/ticket/products/\d+', parsed.path))
    yes24_product = (
        parsed.scheme == 'https'
        and parsed.hostname == 'm.ticket.yes24.com'
        and parsed.path == '/Perf/Detail/PerfInfo.aspx'
        and re.fullmatch(r'\d+', (parse_qs(parsed.query).get('IdPerf') or [''])[0])
        and re.fullmatch(r'\d+', (parse_qs(parsed.query).get('IdSubGenre') or [''])[0])
    )
    airport_public = (
        parsed.scheme == 'https'
        and parsed.hostname in {'www.airport.kr', 'airinfo.airport.kr'}
        and re.fullmatch(r'/ap_ko/\d+/subview\.do', parsed.path)
    )
    donggu_public_event = (
        parsed.scheme == 'https'
        and parsed.hostname == 'www.donggu.go.kr'
        and (
            (parsed.path == '/yeyak/www/viewTnExprnU.do'
             and re.fullmatch(r'\d+', (parse_qs(parsed.query).get('exprnKey') or [''])[0]))
            or parsed.path == '/yeyak/www/selectTnExprnListU.do'
        )
    )
    beartree_event = (
        parsed.scheme == 'https'
        and parsed.hostname == 'beartreepark.com'
        and parsed.path == '/events/'
        and (parse_qs(parsed.query).get('bmode') or [''])[0] == 'view'
        and re.fullmatch(r'\d+', (parse_qs(parsed.query).get('idx') or [''])[0])
    )
    if nol_product or yes24_product or airport_public or donggu_public_event or beartree_event:
        return {
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/153.0 Safari/537.36'),
            'Accept': ('text/html,application/xhtml+xml,application/xml;q=0.9,'
                       'image/avif,image/webp,*/*;q=0.8'),
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
        }
    return {}


def _official_visual_transcript(brief, url, soup):
    """Bind a human-reviewed transcript to one exact visual-only official source.

    Some official event boards publish the substantive schedule only as images.
    The transcript is accepted only when the configured HTTPS asset is actually
    embedded in the exact reviewed official page. The asset bytes are fetched
    and hashed into the source text, so later image replacement invalidates the
    source snapshot instead of silently reusing stale visual evidence.
    """
    configured = (brief.get('visual_source_transcripts') or {}).get(url)
    if configured is None:
        return None
    if not isinstance(configured, dict) or set(configured) != {'asset_url', 'asset_sha256', 'transcript'}:
        raise ValueError('official_visual_transcript_invalid')
    asset_url = configured.get('asset_url')
    asset_sha256 = configured.get('asset_sha256')
    transcript = configured.get('transcript')
    page = urlsplit(url)
    asset = urlsplit(asset_url) if isinstance(asset_url, str) else None
    # This route is intentionally narrow: it exists for the verified Beartree
    # event board whose announcement body is a sequence of CDN card images.
    if (page.scheme != 'https' or page.hostname != 'beartreepark.com'
            or page.path != '/events/'
            or (parse_qs(page.query).get('bmode') or [''])[0] != 'view'
            or not re.fullmatch(r'\d+', (parse_qs(page.query).get('idx') or [''])[0])
            or asset is None or asset.scheme != 'https' or asset.hostname != 'cdn.imweb.me'
            or not isinstance(asset_sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', asset_sha256)
            or not isinstance(transcript, str) or not 20 <= len(transcript.strip()) <= 4000):
        raise ValueError('official_visual_transcript_invalid')
    board = soup.select('.board_txt_area')
    if len(board) != 1:
        raise ValueError('official_visual_source_structure_missing_or_ambiguous')
    matches = [img for img in board[0].select('img[src]') if img.get('src') == asset_url]
    if len(matches) != 1:
        raise ValueError('official_visual_asset_missing_or_ambiguous')
    response = requests.get(asset_url, headers=_official_request_headers(url), timeout=15, allow_redirects=False)
    content_type = (response.headers.get('Content-Type', '') if hasattr(response, 'headers') else '').lower()
    if response.status_code != 200 or not response.content or (content_type and 'image/' not in content_type):
        raise ValueError(f'official_visual_asset_http_{response.status_code}')
    asset_sha = hashlib.sha256(response.content).hexdigest()
    if asset_sha != asset_sha256:
        raise ValueError('official_visual_asset_sha256_mismatch')
    return transcript.strip() + '\nofficial_visual_asset_sha256: ' + asset_sha


def _normalize_nol_product_text(text, url):
    """Drop only volatile social counters from a verified NOL product page."""
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname != 'nol.yanolja.com'
            or not re.fullmatch(r'/ticket/products/\d+', parsed.path)):
        return text
    # Review/like/ranking counters change independently of the product facts
    # used for editorial evidence. Preserve dates, prices, venue, sale terms,
    # booking limits and every other visible product sentence.
    text = re.sub(r'(?m)^콘서트\s+주간\s+[\d,]+위\s*$', '', text)
    text = re.sub(r'(?m)^찜\s+[\d,]+명\s*$', '', text)
    text = re.sub(r'(?m)^리뷰\s*\n[\d,]+\s*\n개\s*$', '', text)
    return '\n'.join(line for line in text.splitlines() if line.strip())


def _nol_product_booking_metadata(raw_html, url, now=None):
    """Recover NOL's booking window/status from its official embedded product JSON.

    The visible product page keeps the booking metadata in the Next.js payload,
    which BeautifulSoup text extraction intentionally drops with ``script`` tags.
    Bind the payload to the exact product ID in the reviewed URL, accept only one
    consistent metadata tuple, and expose the same labelled evidence consumed by
    the dated-concert availability validator.  An inactive/out-of-window product
    never receives an ``예매중`` label merely because the product record exists.
    """
    parsed = urlsplit(url)
    match = re.fullmatch(r'/ticket/products/(\d+)', parsed.path)
    if parsed.scheme != 'https' or parsed.hostname != 'nol.yanolja.com' or not match:
        return ''
    if isinstance(raw_html, bytes):
        raw_html = raw_html.decode('utf-8')
    if not isinstance(raw_html, str):
        return ''

    # Next.js Flight data JSON-escapes quotes inside script strings.  This copy
    # is used only for strict metadata matching; the original HTML is untouched.
    searchable = raw_html.replace('\\"', '"')
    product_id = match.group(1)
    marker = f'"goodsCode":"{product_id}"'
    records = set()
    position = 0
    while True:
        start = searchable.find(marker, position)
        if start < 0:
            break
        next_record = searchable.find('"goodsCode":"', start + len(marker))
        segment = searchable[start:next_record if next_record >= 0 else start + 12000]
        fields = re.search(
            r'"bookingOpenTime":"([^"]+)".*?'
            r'"bookingEndTime":"([^"]+)".*?'
            r'"goodsStatus":"([^"]+)"',
            segment,
            flags=re.DOTALL,
        )
        if fields:
            records.add(fields.groups())
        position = start + len(marker)

    if not records:
        return ''
    if len(records) != 1:
        raise ValueError('nol_product_booking_metadata_ambiguous')
    opened, closes, status = next(iter(records))
    try:
        opened_at = datetime.strptime(opened, '%Y-%m-%d %H:%M:%S').replace(tzinfo=KST)
        closes_at = datetime.strptime(closes, '%Y-%m-%d %H:%M:%S').replace(tzinfo=KST)
    except ValueError as exc:
        raise ValueError('nol_product_booking_metadata_invalid') from exc
    if closes_at <= opened_at:
        raise ValueError('nol_product_booking_metadata_invalid')

    now = now or datetime.now(KST)
    if now.tzinfo is None:
        raise ValueError('reference time must be timezone-aware')
    now = now.astimezone(KST)
    lines = [
        '예매기간: '
        + opened_at.strftime('%Y.%m.%d %H:%M')
        + ' ~ '
        + closes_at.strftime('%Y.%m.%d %H:%M')
    ]
    if status == 'Y' and opened_at <= now <= closes_at:
        lines.append('예매상태: 예매중')
    return '\n'.join(lines)


def _normalize_efine_text(text, url):
    """Drop only eFine's volatile accessibility skip-link label.

    The same official help page can render the exact line 본문 바로가기
    inconsistently across otherwise identical responses. It is navigation
    chrome, not evidence-bearing content.
    """
    parsed = urlsplit(url)
    if (parsed.scheme != 'https'
            or parsed.hostname not in {'efine.go.kr', 'www.efine.go.kr'}
            or not parsed.path.endswith('.do')):
        return text
    return '\n'.join(
        line for line in text.splitlines()
        if line.strip() != '본문 바로가기'
    )


def _normalize_seocho_property_tax_text(text, url):
    """Drop only the volatile view counter from the verified #144 source."""
    parsed = urlsplit(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if (parsed.scheme != 'https'
            or parsed.hostname != 'www.seocho.go.kr'
            or parsed.path != '/site/tax/ex/bbs/View.do'
            or query.get('bcIdx') != ['410947']
            or query.get('cbIdx') != ['419']):
        return text
    lines = text.splitlines()
    matches = [
        index for index in range(len(lines) - 1)
        if lines[index].strip() == '조회수'
        and re.fullmatch(r'[\d,]+', lines[index + 1].strip())
    ]
    if len(matches) != 1:
        raise ValueError('seocho_property_tax_view_counter_structure_changed')
    index = matches[0]
    return '\n'.join(lines[:index] + lines[index + 2:])


def _normalize_event_listing_counters(text, url):
    """Remove only volatile list/view counters from two official event templates.

    Event dates, times, prices, body numbers and attachment text remain hashed.
    Fail closed when the verified metadata shape changes so a body number cannot
    be silently mistaken for chrome.
    """
    parsed = urlsplit(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    lines = text.splitlines()

    if (parsed.scheme == 'https' and parsed.hostname == 'www.science.go.kr'
            and parsed.path == '/mps/0/bbs/431/moveBbsNttDetail.do'
            and query == {'nttSn': ['49259']}):
        markers = [index for index, line in enumerate(lines) if line.strip() == '조회수']
        matches = [
            index for index in range(len(lines) - 1)
            if lines[index].strip() == '조회수'
            and re.fullmatch(r'[\d,]+', lines[index + 1].strip())
        ]
        if len(markers) != 1 or len(matches) != 1:
            raise ValueError('science_event_view_counter_structure_changed')
        index = matches[0]
        return '\n'.join(lines[:index] + lines[index + 2:])

    if (parsed.scheme == 'https' and parsed.hostname == 'daejeontour.co.kr'
            and parsed.path in {'/festival_djt/46', '/festival_djt/49'}
            and not parsed.query):
        matches = [
            index for index in range(1, len(lines) - 2)
            if lines[index - 1].strip() == '인기'
            and re.fullmatch(r'[\d,]+', lines[index].strip())
            and re.fullmatch(r'\d+', lines[index + 1].strip())
            and lines[index + 2].strip()
        ]
        if len(matches) != 1:
            raise ValueError('daejeontour_popularity_counter_structure_changed')
        index = matches[0]
        return '\n'.join(lines[:index] + lines[index + 1:])

    return text


def _normalize_busan_junggu_weather(text, url):
    """Remove only the volatile weather widget from the exact Jung-gu event page.

    The cultural-event schedule above the widget remains byte-for-byte part of
    the source snapshot.  The live temperature and particulate status change
    independently of the event facts, so hashing them would make a reviewed
    draft impossible to save even when the official schedule is unchanged.
    """
    parsed = urlsplit(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if (parsed.scheme != 'https'
            or parsed.hostname != 'www.bsjunggu.go.kr'
            or parsed.path != '/tour/index.junggu'
            or query != {'menuCd': ['DOM_000000203003000000']}):
        return text

    lines = text.splitlines()
    matches = [
        index for index in range(1, len(lines) - 4)
        if lines[index - 1].strip() == '매우 불만족'
        and re.fullmatch(r'-?\d+(?:\.\d+)?', lines[index].strip())
        and lines[index + 1].strip() == '℃'
        and lines[index + 2].strip() == '미세먼지'
        and lines[index + 3].strip() in {'좋음', '보통', '나쁨', '매우 나쁨'}
        and lines[index + 4].strip() == '관광도우미'
    ]
    if len(matches) == 1:
        index = matches[0]
        return '\n'.join(lines[:index] + lines[index + 4:])
    if any(line.strip() in {'℃', '미세먼지'} for line in lines):
        raise ValueError('busan_junggu_weather_widget_structure_changed')
    return text


def _normalize_movein_service_text(text, url):
    """Remove only view counters from the exact official #475 evidence pages."""
    parsed = urlsplit(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    lines = text.splitlines()

    if (parsed.scheme == 'https' and parsed.hostname == 'www.gov.kr'
            and parsed.path == '/portal/faq/869' and query == {'backBtnYn': ['N']}):
        matches = [
            index for index in range(1, len(lines) - 1)
            if lines[index - 1].strip() == '전입신고'
            and re.fullmatch(r'[\d,]+', lines[index].strip())
            and '온라인 전입신고 시 [세대주확인]' in lines[index + 1]
        ]
        if len(matches) != 1:
            raise ValueError('movein_household_faq_view_counter_structure_changed')
        index = matches[0]
        return '\n'.join(lines[:index] + lines[index + 1:])

    if (parsed.scheme == 'https' and parsed.hostname == 'www.gov.kr'
            and parsed.path == '/portal/faq/867' and query == {'backBtnYn': ['N']}):
        matches = [
            index for index in range(1, len(lines) - 1)
            if lines[index - 1].strip() == '처리결과'
            and re.fullmatch(r'[\d,]+', lines[index].strip())
            and '전입신고 담당자가 전입처리를 완료한 후' in lines[index + 1]
        ]
        if len(matches) != 1:
            raise ValueError('movein_result_faq_view_counter_structure_changed')
        index = matches[0]
        return '\n'.join(lines[:index] + lines[index + 1:])

    if (parsed.scheme == 'https' and parsed.hostname == 'www.110.go.kr'
            and parsed.path == '/data/counselView.do'
            and query.get('num') == ['A01_660027']):
        matches = [
            index for index in range(1, len(lines) - 1)
            if lines[index - 1].strip() == '조회수 :'
            and re.fullmatch(r'[\d,]+', lines[index].strip())
            and lines[index + 1].strip() == '질문내용'
        ]
        if len(matches) != 1:
            raise ValueError('movein_110_view_counter_structure_changed')
        index = matches[0]
        return '\n'.join(lines[:index] + lines[index + 1:])

    return text


def _normalize_post239_chuseok_sources(text, url):
    """Remove only verified volatile chrome from the exact #239 source set."""
    parsed = urlsplit(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    lines = text.splitlines()

    if (parsed.scheme == 'https' and parsed.hostname == 'www.korea.kr'
            and parsed.path == '/briefing/pressReleaseView.do'
            and query == {'newsId': ['156782379']}):
        matches = [index for index, line in enumerate(lines)
                   if line.strip() == '실시간 인기뉴스']
        if len(matches) != 1:
            raise ValueError('post239_koreakr_dynamic_section_changed')
        return '\n'.join(lines[:matches[0]]).rstrip()

    royal = {
        '20260921134912308090': ('창덕궁', '2026-09-21'),
        '20260916111620269300': ('종묘', '2026-09-16'),
    }
    royal_id = (query.get('id') or [None])[0]
    if (parsed.scheme == 'https' and parsed.hostname == 'royal.khs.go.kr'
            and parsed.path == '/ROYAL/contents/R403000000.do'
            and royal_id in royal):
        label, published = royal[royal_id]
        matches = [
            index for index in range(len(lines) - 2)
            if lines[index].strip() == label
            and re.fullmatch(r'\d+', lines[index + 1].strip())
            and lines[index + 2].strip() == published
        ]
        if len(matches) != 1:
            raise ValueError('post239_royal_view_counter_changed')
        index = matches[0]
        return '\n'.join(lines[:index + 1] + lines[index + 2:])

    if (parsed.scheme == 'https' and parsed.hostname == 'm.mmca.go.kr'
            and parsed.path == '/pr/newsDetail.do'
            and query == {'bdCId': ['202609080010583']}):
        matches = [
            index for index in range(len(lines) - 2)
            if lines[index].strip() == '조회수'
            and re.fullmatch(r'\d+', lines[index + 1].strip())
            and lines[index + 2].strip() == 'SNS 공유'
        ]
        if len(matches) != 1:
            raise ValueError('post239_mmca_view_counter_changed')
        index = matches[0]
        return '\n'.join(lines[:index] + lines[index + 2:])

    return text


def _naver_post233_price_reference_text(soup, url):
    """Extract the reviewed Naver post body without volatile blog chrome.

    This exception is deliberately locked to the one price-comparison post used
    by draft #233.  Likes, recommendations and neighboring-post widgets change
    independently of the article, while ``.se-main-container`` contains the
    authored comparison itself.
    """
    parsed = urlsplit(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if not (parsed.scheme == 'https' and parsed.hostname == 'blog.naver.com'
            and parsed.path == '/PostView.naver'
            and query == {'blogId': ['coocoo625'], 'logNo': ['223501023245']}):
        return None
    bodies = soup.select('div.se-main-container')
    if len(bodies) != 1:
        raise ValueError('post233_naver_price_body_missing_or_ambiguous')
    text = bodies[0].get_text('\n', strip=True)
    if len(text) < 500:
        raise ValueError('post233_naver_price_body_too_short')
    return text


def _yna_post233_distribution_reference_text(soup, url):
    """Extract only the reviewed Yonhap article body used by draft #233.

    The Yonhap page surrounds the article with live ranking/recommendation
    modules that can change between source review and the final CAS update.
    Lock this normalization to the exact article URL and require the two
    distribution facts used by #233 before returning the stable article body.
    """
    parsed = urlsplit(url)
    if not (parsed.scheme == 'https' and parsed.hostname == 'www.yna.co.kr'
            and parsed.path == '/view/AKR20260619134300017'
            and not parsed.query):
        return None
    bodies = soup.select('div.story-news.article')
    if len(bodies) != 1:
        raise ValueError('post233_yna_body_missing_or_ambiguous')
    text = bodies[0].get_text('\n', strip=True)
    required = (
        '현재 편의점 판매가 허용된 의약품은 모두 13종이다.',
        '실제로 구입할 수 있는 의약품은 11종이다.',
    )
    if len(text) < 1500 or any(phrase not in text for phrase in required):
        raise ValueError('post233_yna_body_required_facts_missing')
    return text


def _newdaily_beartree_reference_text(soup, url):
    """Extract only the stable article body used by event post #665.

    The page includes a live ranking rail whose ordering changes independently
    of the article. Lock normalization to the exact reviewed URL and fail closed
    if the article-body structure or required facts disappear.
    """
    if url != 'https://cc.newdaily.co.kr/site/data/html/2026/09/30/2026093000102.html':
        return None
    bodies = soup.select('.article-body')
    if len(bodies) != 1:
        raise ValueError('newdaily_beartree_article_body_missing_or_ambiguous')
    text = bodies[0].get_text('\n', strip=True)
    required = ('10월 3일부터 11월 22일까지', '가을 산책길', '팝업 마켓')
    if any(phrase not in text for phrase in required):
        raise ValueError('newdaily_beartree_article_body_required_facts_missing')
    return text


