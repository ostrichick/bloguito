"""Bounded HTTP/PDF source collection with stable reviewed source identity."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import re
from urllib.parse import parse_qs, urlsplit
import requests
from bs4 import BeautifulSoup
from agents.fact_validation import snapshot
from agents.workflow_metrics import increment, timed
from agents.source_extractors import (
    _koreakr_article_text,
    _official_request_headers,
    _official_visual_transcript,
    _normalize_nol_product_text,
    _nol_product_booking_metadata,
    _normalize_efine_text,
    _normalize_seocho_property_tax_text,
    _normalize_event_listing_counters,
    _normalize_busan_junggu_weather,
    _normalize_movein_service_text,
    _normalize_post239_chuseok_sources,
    _naver_post233_price_reference_text,
    _yna_post233_distribution_reference_text,
    _newdaily_beartree_reference_text,
)


def _official_get(url):
    """Fetch an official URL without trusting arbitrary redirects.

    Police eFine issues a same-URL HTTP 307 on the first request solely to set
    TMOSHCooKie, then serves the requested page on the second request in the
    same session. Handle only that exact, host-scoped cookie challenge.
    """
    parsed = urlsplit(url)
    efine = (
        parsed.scheme == 'https'
        and parsed.hostname in {'efine.go.kr', 'www.efine.go.kr'}
        and parsed.path.endswith('.do')
    )
    headers = _official_request_headers(url)
    if not efine:
        return requests.get(url, timeout=25, allow_redirects=False, headers=headers)

    session = requests.Session()
    response = session.get(url, timeout=25, allow_redirects=False, headers=headers)
    if (response.status_code == 307
            and response.headers.get('Location') == url
            and session.cookies.get('TMOSHCooKie')):
        response = session.get(url, timeout=25, allow_redirects=False, headers=headers)
    return response


def fetch_sources(brief):
    with timed('source_fetch'):
        official_urls = brief['official_urls']
        reference_urls = brief.get('reference_urls', [])
        if len(official_urls) > 7:
            raise ValueError('too_many_editorial_sources')
        requested = ([('official', url) for url in official_urls]
                     + [('reference', url) for url in reference_urls])
        if len(requested) > 8:
            raise ValueError('too_many_editorial_sources')
        if not requested:
            return []
        increment('source_fetch_requests', len(requested))
        workers = min(4, len(requested))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(_fetch_single_source, brief, source_type, url)
                for source_type, url in requested
            ]
            results = [future.result() for future in futures]
        for index, source in enumerate(results):
            source['id'] = f's{index}'
        return results


def _fetch_single_source(brief, source_type, url):
    single = dict(brief)
    single['official_urls'] = [url] if source_type == 'official' else []
    single['reference_urls'] = [url] if source_type == 'reference' else []
    rows = _fetch_sources_sequential(single)
    if len(rows) != 1:
        raise ValueError('single_source_fetch_failed')
    return rows[0]


def fetch_sources_subset(brief, existing_sources, source_ids):
    """Re-fetch only selected source IDs while preserving reviewed metadata.

    Returns a list of refreshed source records in the same order as source_ids.
    Manual metadata such as actions/citation labels is retained from the
    existing reviewed snapshot; text/title/hash/fetched_at come from the fresh
    network read.
    """
    by_id = {source.get('id'): source for source in existing_sources}
    if not isinstance(source_ids, (list, tuple)) or not source_ids:
        raise ValueError('source_ids_required')
    if len(set(source_ids)) != len(source_ids) or any(source_id not in by_id for source_id in source_ids):
        raise ValueError('unknown_or_duplicate_source_id')
    with timed('source_subset_fetch'):
        increment('source_fetch_requests', len(source_ids))
        workers = min(4, len(source_ids))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(
                    _fetch_single_source,
                    brief,
                    by_id[source_id].get('source_type'),
                    by_id[source_id]['url'],
                )
                for source_id in source_ids
            ]
            fresh_rows = [future.result() for future in futures]
    refreshed = []
    snapshot_keys = {'id', 'url', 'title', 'text', 'source_type', 'fetched_at', 'sha256'}
    for source_id, fresh in zip(source_ids, fresh_rows):
        prior = by_id[source_id]
        merged = {key: value for key, value in prior.items() if key not in snapshot_keys}
        merged.update(fresh)
        merged['id'] = source_id
        refreshed.append(merged)
    return refreshed


def _fetch_sources_sequential(brief):
    sources = []
    official_urls = brief['official_urls']
    reference_urls = brief.get('reference_urls', [])
    if len(official_urls) > 7:
        raise ValueError('too_many_editorial_sources')
    requested = ([('official', url) for url in official_urls]
                 + [('reference', url) for url in reference_urls])
    # A multi-city event can need one official tour listing plus one official
    # product page per region. Keep the collection bounded while permitting a
    # seven-source six-city verification set.
    if len(requested) > 8:
        raise ValueError('too_many_editorial_sources')
    for i, (source_type, url) in enumerate(requested):
        # Redirects require updating the reviewed URL rather than silently trusting another host.
        response = _official_get(url)
        if response.status_code != 200:
            raise ValueError(f'official_source_http_{response.status_code}')
        if response.content.startswith(b'%PDF-'):
            # Some agencies serve PDFs as application/octet-stream from a
            # download endpoint with no .pdf suffix. Preserve page boundaries
            # and layout so row-specific quotations remain reproducible.
            from pypdf import PdfReader
            pages = PdfReader(BytesIO(response.content)).pages
            text = '\n\n'.join(page.extract_text(extraction_mode='layout') or ''
                             for page in pages).strip()
            if not 80 <= len(text) <= 60000:
                raise ValueError('official_pdf_text_missing_or_too_large')
            title = brief['entity'] + ' 공식 첨부 PDF'
            sources.append({'id': f's{i}', **snapshot(url, title, text, source_type)})
            continue
        nol_booking_metadata = _nol_product_booking_metadata(response.content, url)
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.title.get_text(' ', strip=True) if soup.title else brief['entity']
        visual_text = _official_visual_transcript(brief, url, soup)
        if visual_text is not None:
            if not 80 <= len(visual_text) <= 60000:
                raise ValueError('official_source_text_missing_or_too_large')
            sources.append({'id': f's{i}', **snapshot(url, title, visual_text, source_type)})
            continue
        # NTS article metadata renders `<strong>조회수</strong>65289` as two
        # separate text lines, so the line-based filter below cannot remove it.
        # Remove only the verified view-count list item in the NTS metadata;
        # preserve any view-count words or numeric facts in the article body.
        parsed = urlsplit(url)
        if (parsed.hostname in {'nts.go.kr', 'www.nts.go.kr', 'kids.nts.go.kr'}
                and parsed.path == '/nts/na/ntt/selectNttInfo.do'):
            for item in soup.select('.bbs_ViewA .bbsV_data > li'):
                marker = item.find('strong')
                if (marker and marker.get_text(' ', strip=True) == '조회수'
                        and re.fullmatch(r'조회수\s*\d+', item.get_text(' ', strip=True))):
                    item.decompose()
        # The Ministry of Health's board article metadata uses a separate
        # <li class="hit"> counter. It can change between the independent
        # review and source recheck even though article policy text did not.
        # Limit removal to the verified article metadata structure and do not
        # strip any figures or view-count references inside the actual body.
        if parsed.hostname == 'www.mohw.go.kr' and parsed.path == '/board.es':
            for item in soup.select('li.hit'):
                marker = item.find('strong', recursive=False)
                counter = item.get_text(' ', strip=True).replace('\xa0', ' ')
                if (marker and marker.get_text(' ', strip=True) == '조회수'
                        and re.fullmatch(r'조회수\s*:\s*[\d,]+', counter)):
                    item.decompose()
            # These two individually verified MOHW articles embed changing
            # download/preview counters next to meaningful attachment sizes.
            # Preserve filename, size, article body and all other metadata.
            query = parse_qs(parsed.query, keep_blank_values=True)
            if (query.get('act') == ['view'] and query.get('bid') == ['0027']
                    and query.get('list_no') in (['1488478'], ['1491727'])
                    and query.get('mid') == ['a10503010100']):
                attachments = soup.select('div.file')
                if len(attachments) > 1:
                    raise ValueError('mohw_attachment_structure_missing_or_ambiguous')
                if attachments:
                    titles = attachments[0].select('strong.title')
                    if (len(titles) != 1 or titles[0].get_text(' ', strip=True) != '첨부파일'
                            or len(attachments[0].select('ul.list')) != 1):
                        raise ValueError('mohw_attachment_structure_missing_or_ambiguous')
                    rows = attachments[0].select('ul.list > li')
                    if not rows:
                        raise ValueError('mohw_attachment_structure_missing_or_ambiguous')
                    for row in rows:
                        counters = row.find_all('span', class_='txt', recursive=False)
                        if len(counters) != 1:
                            raise ValueError('mohw_attachment_structure_missing_or_ambiguous')
                        value = counters[0].get_text(' ', strip=True).replace('\xa0', ' ')
                        match = re.fullmatch(
                            r'\(\s*(\d+(?:\.\d+)?\s*[KMGT]?B)\s*/\s*다운로드\s*[\d,]+회'
                            r'\s*/\s*미리보기\s*[\d,]+회\s*\)', value,
                            flags=re.IGNORECASE)
                        if not match:
                            raise ValueError('mohw_attachment_counter_format_changed')
                        counters[0].string = '(' + match.group(1) + ')'
        # The Mokpo health bulletin places an incrementing view counter in
        # article title metadata and a separate download counter next to the
        # attachment's file size. Strip only those counters on this exact
        # bulletin route. Keep the attachment size (a replacement file may
        # change it), dates, actual bulletin text and any numbers in the body.
        if (parsed.hostname == 'www.mokpo.go.kr'
                and parsed.path == '/health/citizen_participation/notice'):
            for marker in soup.select('.module_view_box .view_titlebox dl > dt'):
                if marker.get_text(' ', strip=True) != '조회수':
                    continue
                value = marker.find_next_sibling()
                if (value and value.name == 'dd'
                        and re.fullmatch(r'[\d,]+', value.get_text(' ', strip=True))):
                    marker.decompose()
                    value.decompose()
            for counter in soup.select('a[href*="/common/file_download/"] > span.file_info'):
                value = counter.get_text(' ', strip=True)
                match = re.fullmatch(r'\(\s*[\d,]+\s+hit/\s*([\d.]+\s*[KMG]?B)\s*\)',
                                     value, flags=re.IGNORECASE)
                if match:
                    counter.string = '(' + match.group(1) + ')'
        # Seoul MediaHub article pages increment the standalone view counter on
        # every read. Strip only the verified metadata paragraph so an
        # independent source recheck remains stable while article dates,
        # benefit amounts and every number in the body still affect the hash.
        if (parsed.hostname == 'mediahub.seoul.go.kr'
                and re.fullmatch(r'/archives/\d+', parsed.path)):
            for item in soup.select('div.info_view > p.view.bar'):
                marker = ''.join(item.find_all(string=True, recursive=False)).strip()
                value = item.find('span', class_='num', recursive=False)
                if (marker == '조회' and value
                        and re.fullmatch(r'[\d,]+', value.get_text(' ', strip=True))):
                    item.decompose()
        for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
            tag.decompose()
        text = _koreakr_article_text(soup, url)
        if text is None:
            text = _naver_post233_price_reference_text(soup, url)
        if text is None:
            text = _yna_post233_distribution_reference_text(soup, url)
        if text is None:
            text = _newdaily_beartree_reference_text(soup, url)
        if text is None:
            text = soup.get_text('\n', strip=True)
        # Government article page counters change on every read. They are not
        # policy evidence, so omit only the standalone view-count metadata;
        # any actual article-content change must still alter the source hash.
        text = '\n'.join(line for line in text.splitlines()
                         if not re.fullmatch(r'조회수\s*:\s*\d+', line.strip()))
        text = _normalize_nol_product_text(text, url)
        if nol_booking_metadata:
            text = text.rstrip() + '\n' + nol_booking_metadata
        text = _normalize_efine_text(text, url)
        text = _normalize_seocho_property_tax_text(text, url)
        text = _normalize_event_listing_counters(text, url)
        text = _normalize_busan_junggu_weather(text, url)
        text = _normalize_movein_service_text(text, url)
        text = _normalize_post239_chuseok_sources(text, url)
        if not 80 <= len(text) <= 60000:
            raise ValueError('official_source_text_missing_or_too_large')
        sources.append({'id': f's{i}', **snapshot(url, title, text, source_type)})
    return sources


