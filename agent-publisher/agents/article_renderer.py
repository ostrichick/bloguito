"""Deterministic article HTML rendering with explicit editorial dependencies."""
import base64
import html
import json
import math
import re
from urllib.parse import quote

from agents.event_post_standard import overview_event_date_labels
from agents.reader_tools import render_reader_tools


def render_article(plan, sources, category_key=None, *, helpers, map_key):
    """Presentation is deterministic: retain every reviewed sentence and condition."""
    validated_lead_image = helpers['validated_lead_image']
    section_kind = helpers['section_kind']
    actionable_links = helpers['actionable_links']
    validated_section_action_links = helpers['validated_section_action_links']
    validated_section_official_links = helpers['validated_section_official_links']
    normalized = helpers['normalized']
    all_blocks = helpers['all_blocks']
    official_navigation_links = helpers['official_navigation_links']
    lead_image = validated_lead_image(plan)
    source_map = {s['id']: s for s in sources}
    def inline_text(block):
        text = block['text']
        emphasis = block.get('emphasis') or []
        if not emphasis:
            return html.escape(text)
        # Match the longest phrase first when reviewed emphasis phrases overlap.
        pattern = re.compile('(' + '|'.join(re.escape(item) for item in sorted(emphasis, key=len, reverse=True)) + ')')
        emphasized = set(emphasis)
        return ''.join(
            (f'<strong style="font-weight:700;color:#1f2937">{html.escape(part)}</strong>'
             if part in emphasized else html.escape(part))
            for part in pattern.split(text) if part
        )

    def paragraph(block):
        return (f'<p style="margin:0 0 16px;line-height:1.8;color:#2d3748;'
                f'font-size:16px;font-weight:400;letter-spacing:normal">{inline_text(block)}</p>')

    def mobile_event_name(text):
        """Keep compact ASCII+Hangul event-name units together on narrow cards.

        Names such as ``M 드론라이트쇼`` are one reader-facing label even
        though they contain an ASCII brand token followed by a space.  Mobile
        fallback wrapping may otherwise strand ``M`` at the end of a line.
        The source text is unchanged; only the rendered grouping is added.
        """
        escaped = html.escape(text)
        return re.sub(
            r'(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9.+-]{0,8})\s+([가-힣][가-힣0-9-]{1,20})',
            r'<span class="bloguito-semantic-unit">\1 \2</span>',
            escaped,
        )

    # 1. Immediate answer, with one heading and no repeated decorative badges.
    result = ('<div class="bloguito-article" style="line-height:1.8;font-size:16px;color:#2d3748;'
              'font-family:-apple-system,BlinkMacSystemFont,\'Malgun Gothic\',\'Apple SD Gothic Neo\',\'Noto Sans KR\',sans-serif;'
              'font-weight:400;letter-spacing:normal;overflow-wrap:anywhere;word-break:keep-all">'
              '<style id="bloguito-responsive-layout">'
              '.bloguito-article *{box-sizing:border-box}'
              '@media(max-width:640px){'
              '.bloguito-article *{overflow-wrap:anywhere!important;word-break:break-word!important}'
              '.bloguito-summary p{word-break:keep-all!important;overflow-wrap:anywhere!important}'
              '.bloguito-semantic-unit{white-space:nowrap!important;word-break:keep-all!important;overflow-wrap:normal!important}'
              '.festival-facts{grid-template-columns:minmax(0,1fr)!important}'
              '.bloguito-info-table table{table-layout:fixed!important}'
              '.bloguito-info-table th,.bloguito-info-table td{overflow-wrap:anywhere!important;word-break:break-word!important}'
              '}</style>'
              '<div class="bloguito-summary" style="padding:18px 20px;margin:16px 0 24px;background:#f0f8f5;border:1px solid #d1e7dd;border-left:5px solid #0d7d59;border-radius:10px">'
              '<div style="font-size:18px;font-weight:700;color:#134e4a">한눈에 보기</div>'
              + f'<p style="margin:8px 0 0;line-height:1.75;color:#1f2937;font-size:16px">{inline_text(plan["lead"])}</p></div>')
    if lead_image:
        result += (
            '<figure class="bloguito-lead-image" style="margin:0 0 28px">'
            f'<img src="{html.escape(lead_image["url"], quote=True)}" '
            f'alt="{html.escape(lead_image["alt"], quote=True)}" '
            f'width="{lead_image["width"]}" height="{lead_image["height"]}" '
            'loading="eager" decoding="async" '
            'style="display:block;width:100%;max-width:100%;height:auto;border-radius:10px" />'
            '</figure>'
        )
    result += render_reader_tools(plan)

    # A source-reviewed overview table belongs immediately after the answer.
    sections = plan['sections']
    overview_first = bool(sections and section_kind(sections[0]) == 'overview')
    procedure_number = 0
    # One isolated procedure is not a sequence. A lonely STEP 1 confuses the
    # heading hierarchy and was mistakenly included in the table of contents.
    numbered_procedures = sum(section_kind(section) == 'procedure' for section in sections) > 1

    actions = actionable_links(sources)
    section_actions, scoped_action_urls = validated_section_action_links(plan, sources)
    section_official_links, _ = validated_section_official_links(plan, sources)

    def action_button(action, *, block=False):
        display = 'flex' if block else 'inline-flex'
        width = 'width:100%;' if block else ''
        return (
            f'<a href="{html.escape(action["url"], quote=True)}" target="_blank" rel="noopener noreferrer" '
            f'style="display:{display};{width}align-items:center;justify-content:center;gap:10px;min-width:0;'
            'padding:13px 16px;background:#0d7d59;color:#ffffff !important;border:1px solid #0d7d59;'
            'text-decoration:none !important;border-radius:10px;font-size:16px;font-weight:700;overflow-wrap:anywhere">'
            f'<span style="flex-grow:1;text-align:center">{html.escape(action["label"])}</span>'
            '<span aria-hidden="true">↗</span></a>'
        )

    def section_markup(number, section):
        nonlocal procedure_number
        event_section = isinstance(section.get('event_name'), str) and bool(section['event_name'].strip())
        clean_heading = re.sub(r'^\s*(\d+[.)]\s*)?(STEP\s*\d+[.)]?\s*)?', '', section['heading'], flags=re.IGNORECASE).strip()
        procedural = numbered_procedures and section_kind(section) == 'procedure'
        if procedural:
            procedure_number += 1
        badge = (f'<span style="background:#e6f4ea;color:#0d7d59;font-size:13px;font-weight:700;padding:4px 9px;border-radius:20px;margin-right:9px">STEP {procedure_number}</span>'
                 if procedural else '')
        body = (f'<h2 id="step-{number}" style="font-family:inherit;font-size:clamp(20px,2.5vw,23px);'
                f'font-weight:700;font-style:normal;letter-spacing:normal;text-align:left;'
                f'line-height:1.45;margin:32px 0 14px;padding-bottom:10px;border-bottom:2px solid #e2e8f0;color:#1a202c">'
                f'{badge}{html.escape(clean_heading)}</h2>')
        facts = section.get('facts') or []
        if facts and not event_section:
            items = ''.join(
                '<div style="padding:10px 12px;background:#ffffff;border:1px solid #dbe5e1;border-radius:8px">'
                f'<div style="font-size:12px;font-weight:700;color:#64748b;margin-bottom:3px">{html.escape(fact["label"])}</div>'
                f'<div style="font-size:15px;font-weight:700;color:#1f2937;line-height:1.55">{html.escape(fact["value"])}</div>'
                '</div>' for fact in facts)
            body += ('<div class="festival-facts" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,180px),1fr));'
                     'gap:8px;margin:0 0 18px;padding:12px;background:#f0f8f5;border:1px solid #d1e7dd;border-radius:10px">'
                     + items + '</div>')
        image = section.get('image')
        if image:
            source = source_map[image['source_id']]
            photo_source_url = image.get('rights_url') or source['url']
            show_photo_source = (
                not event_section
                or image.get('rights') in {'open_license', 'permission_granted', 'source_attributed'}
            )
            photo_source = (
                ', '
                f'<a href="{html.escape(photo_source_url, quote=True)}" target="_blank" rel="noopener noreferrer" '
                'style="color:#0d7d59;text-decoration:underline">사진 출처</a>'
                if show_photo_source else ''
            )
            body += (
                '<figure class="bloguito-event-image" style="margin:4px 0 18px">'
                f'<img src="{html.escape(image["url"], quote=True)}" '
                f'alt="{html.escape(image["alt"], quote=True)}" loading="lazy" decoding="async" '
                'style="display:block;width:100%;max-width:100%;height:auto;max-height:520px;object-fit:cover;border-radius:10px" />'
                '<figcaption style="margin-top:7px;font-size:13px;line-height:1.55;color:#64748b">'
                f'{html.escape(image["caption"])}{photo_source}</figcaption></figure>'
            )
        if event_section:
            body += ''.join(paragraph(b) for b in section['paragraphs'])
        table = section.get('table')
        if table:
            headers = ''.join(f'<th scope="col" style="padding:10px;border-bottom:2px solid #cbd5e1;text-align:left">{html.escape(h)}</th>'
                              for h in table['headers'])
            rows = ''.join('<tr>' + ''.join(
                (f'<th scope="row" style="padding:10px;border-bottom:1px solid #e2e8f0;text-align:left;font-weight:700">{html.escape(cell)}</th>'
                 if index == 0 else
                 f'<td style="padding:10px;border-bottom:1px solid #e2e8f0;vertical-align:top">{html.escape(cell)}</td>')
                for index, cell in enumerate(row['cells'])) + '</tr>' for row in table['rows'])
            scrolling = len(table['headers']) >= 3
            mobile_cards = bool(table.get('mobile_cards'))
            hint = ('<p class="bloguito-table-hint" style="font-size:13px;color:#475569;margin:0 0 6px">모바일에서는 카드형 비교로 핵심 정보를 한 번에 확인할 수 있습니다.</p>'
                    if mobile_cards else
                    ('<p class="bloguito-table-hint" style="font-size:13px;color:#475569;margin:0 0 6px">작은 화면에서는 표를 좌우로 밀어 확인할 수 있습니다.</p>'
                     if scrolling else ''))
            desktop_class = ' bloguito-overview-desktop' if mobile_cards else ''
            body += (hint + f'<div class="bloguito-info-table{desktop_class}" role="region" aria-label="'
                     + html.escape(table['caption'], quote=True)
                     + '" tabindex="0" style="overflow-x:auto;margin:8px 0 24px;max-width:100%">'
                     + '<table style="border-collapse:collapse;width:100%;min-width:'
                     + ('580px' if scrolling else '0')
                     + ';font-size:15px;line-height:1.6;overflow-wrap:anywhere;word-break:keep-all">'
                     + '<caption style="text-align:left;font-weight:700;margin-bottom:8px">'
                     + html.escape(table['caption']) + '</caption><thead style="background:#edf7f3"><tr>'
                     + headers + '</tr></thead><tbody>' + rows + '</tbody></table></div>')
            if mobile_cards:
                cards = []
                mobile_title_index = next(
                    (idx for idx, header in enumerate(table['headers'])
                     if isinstance(header, str)
                     and any(token in header for token in ('행사', '축제'))),
                    1 if len(table['headers']) > 1 else 0,
                )
                for row in table['rows']:
                    pairs = ''.join(
                        '<div style="display:grid;grid-template-columns:78px minmax(0,1fr);gap:8px;padding:4px 0">'
                        f'<span style="font-size:12px;font-weight:700;color:#64748b">{html.escape(table["headers"][idx])}</span>'
                        f'<span style="font-size:14px;color:#334155;line-height:1.5">{html.escape(cell)}</span></div>'
                        for idx, cell in enumerate(row['cells']) if idx != mobile_title_index and cell.strip())
                    cards.append(
                        '<article style="padding:14px 15px;background:#ffffff;border:1px solid #dbe5e1;border-left:4px solid #0d7d59;border-radius:10px">'
                        f'<div style="font-size:16px;font-weight:800;color:#1f2937;margin-bottom:7px">{mobile_event_name(row["cells"][mobile_title_index])}</div>'
                        + pairs + '</article>')
                body += (
                    '<style>.bloguito-overview-mobile{display:none}@media(max-width:640px){.bloguito-overview-desktop{display:none!important}.bloguito-overview-mobile{display:grid!important}}</style>'
                    '<div class="bloguito-overview-mobile" style="grid-template-columns:1fr;gap:10px;margin:8px 0 24px">'
                    + ''.join(cards) + '</div>')
        if not event_section:
            body += ''.join(paragraph(b) for b in section['paragraphs'])
        scoped = section_actions[number - 1]
        official_links = section_official_links[number - 1]
        if official_links:
            body += (
                '<div class="bloguito-section-official-links" style="margin:4px 0 20px;padding:12px 14px;'
                'background:#f8fafc;border:1px solid #dbe5e1;border-left:4px solid #0d7d59;border-radius:8px">'
                '<div style="display:flex;flex-direction:column;gap:8px">'
                + ''.join(
                    f'<a href="{html.escape(link["url"], quote=True)}" target="_blank" rel="noopener noreferrer" '
                    'style="color:#0d7d59 !important;text-decoration:underline;font-size:14px;font-weight:700;line-height:1.6">'
                    f'{html.escape(link["label"])} <span aria-hidden="true">↗</span></a>'
                    for link in official_links
                )
                + ('<div class="bloguito-section-cta" style="display:grid;grid-template-columns:1fr;gap:10px;margin-top:4px">'
                   + ''.join(action_button(action, block=True) for action in scoped)
                   + '</div>' if event_section and scoped else '')
                + '</div></div>'
            )
        if scoped and not event_section:
            body += (
                '<div class="bloguito-section-cta" style="margin:4px 0 20px;padding:14px;background:#f8fafc;'
                'border:1px solid #cbd5e1;border-radius:10px">'
                '<div style="display:grid;grid-template-columns:1fr;gap:10px">'
                + ''.join(action_button(action, block=True) for action in scoped)
                + '</div></div>'
            )
        location = section.get('location')
        if location:
            query = quote(location['query'].strip(), safe='')
            venue_text = location['venue'].strip()
            address_text = location['address'].strip()
            venue = html.escape(venue_text)
            address_line = ''
            if address_text and normalized(address_text).casefold() != normalized(venue_text).casefold():
                address_line = (
                    '<div style="font-size:14px;color:#475569;margin-bottom:10px;line-height:1.6">'
                    f'<strong>주소</strong>: {html.escape(address_text)}</div>'
                )
            heading_margin = '4px' if address_line else '10px'
            body += (
                '<div class="festival-location-card" style="margin:16px 0 24px;padding:14px 18px;background:#f8fafc;'
                'border:1px solid #e2e8f0;border-left:4px solid #0d7d59;border-radius:8px">'
                f'<div style="font-weight:700;color:#1e293b;font-size:15px;margin-bottom:{heading_margin}">'
                f'📍 행사장 위치: {venue}</div>'
                + address_line
                + '<div style="display:flex;gap:8px;flex-wrap:wrap">'
                f'<a href="https://map.kakao.com/link/search/{query}" target="_blank" rel="noopener noreferrer" '
                'style="display:inline-flex;align-items:center;gap:4px;padding:7px 13px;background:#fee500;color:#111827 !important;'
                'font-size:13px;font-weight:700;border-radius:6px;text-decoration:none !important">카카오맵 위치 보기 <span aria-hidden="true">↗</span></a>'
                f'<a href="https://map.naver.com/v5/search/{query}" target="_blank" rel="noopener noreferrer" '
                'style="display:inline-flex;align-items:center;gap:4px;padding:7px 13px;background:#03c75a;color:#ffffff !important;'
                'font-size:13px;font-weight:700;border-radius:6px;text-decoration:none !important">네이버지도 위치 보기 <span aria-hidden="true">↗</span></a>'
                '</div></div>'
            )
        return body

    def event_map_markup():
        event_sections = [
            (number, section) for number, section in enumerate(sections, 1)
            if isinstance(section.get('event_name'), str) and section['event_name'].strip()
        ]
        if len(event_sections) < 2 or not overview_first:
            return ''
        try:
            date_labels = overview_event_date_labels(sections[0])
        except (TypeError, ValueError):
            return ''

        spots = []
        for number, section in event_sections:
            location = section.get('location') or {}
            latitude, longitude = location.get('latitude'), location.get('longitude')
            event_name = section['event_name'].strip()
            if (type(latitude) not in {int, float} or type(longitude) not in {int, float}
                    or not math.isfinite(float(latitude)) or not math.isfinite(float(longitude))
                    or not -90 <= float(latitude) <= 90 or not -180 <= float(longitude) <= 180
                    or event_name not in date_labels):
                return ''
            spots.append({
                'event_name': event_name,
                'date': date_labels[event_name],
                'venue': location.get('venue', '').strip(),
                'lat': float(latitude),
                'lng': float(longitude),
                'anchor': f'#step-{number}',
            })

        key = map_key.strip() if isinstance(map_key, str) else ''
        if not re.fullmatch(r'[A-Za-z0-9_-]{16,128}', key):
            raise ValueError('kakao_map_javascript_key_missing_or_invalid')

        grouped = {}
        for spot in spots:
            grouped.setdefault((spot['lat'], spot['lng']), []).append(spot)
        marker_groups = []
        for (latitude, longitude), members in grouped.items():
            info_rows = ''.join(
                '<div style="padding:8px 0;border-bottom:1px solid #e2e8f0">'
                f'<div style="font-weight:700;color:#0d7d59;font-size:13.5px;margin-bottom:4px">{html.escape(member["event_name"])}</div>'
                f'<div style="color:#475569;font-size:12px;margin-bottom:2px">📅 {html.escape(member["date"])}</div>'
                f'<div style="color:#64748b;font-size:11.5px;margin-bottom:8px">📍 {html.escape(member["venue"])}</div>'
                f'<a href="{member["anchor"]}" style="display:inline-block;padding:4px 10px;background:#0d7d59;color:#ffffff !important;border-radius:4px;text-decoration:none !important;font-size:11.5px;font-weight:700">본문 행사 상세 보기 →</a>'
                '</div>'
                for member in members
            )
            marker_groups.append({
                'lat': latitude,
                'lng': longitude,
                'title': ' / '.join(member['event_name'] for member in members),
                'content': '<div style="padding:6px 14px;min-width:220px;max-width:300px;font-family:-apple-system,BlinkMacSystemFont,Malgun Gothic,sans-serif;line-height:1.5;color:#1e293b">' + info_rows + '</div>',
            })

        # Keep this JSON ASCII before Base64. atob() returns a byte-valued string;
        # JSON \u escapes let JSON.parse restore Korean text without mojibake.
        payload = json.dumps(marker_groups, ensure_ascii=True, separators=(',', ':'))
        # Keep HTML for InfoWindow content out of the literal post body. WordPress
        # wpautop can otherwise interpret <div>/<a> inside an inline JS string and
        # inject <p> tags into the script, which breaks the map at runtime.
        payload_b64 = base64.b64encode(payload.encode('utf-8')).decode('ascii')
        map_title = f'{len(spots)}개 행사장 위치 한눈에 보기'
        return (
            '<section class="bloguito-kakao-map-container" aria-label="행사장 위치 지도" '
            'style="margin:28px 0;padding:20px 22px;background:#ffffff;border:1px solid #cbd5e1;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.05)">'
            '<div style="font-size:17.5px;font-weight:700;color:#0f172a;margin-bottom:8px">🗺️ '
            + html.escape(map_title) + '</div>'
            '<p style="margin:0 0 12px;font-size:13.5px;line-height:1.6;color:#475569">'
            '마커를 누르면 행사 일정과 장소를 확인하고 본문의 상세 안내로 바로 이동할 수 있습니다.</p>'
            '<div id="bloguito-kakao-map" class="bloguito-kakao-map" '
            'style="width:100%;height:clamp(320px,52vw,440px);border-radius:10px;border:1px solid #e2e8f0;background:#f8fafc;position:relative;touch-action:pan-y pinch-zoom"></div>'
            f'<script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={html.escape(key, quote=True)}"></script>'
            '<script type="text/javascript">(function(){var groups=JSON.parse(atob("' + payload_b64 + '"));'
            'function initBloguitoMap(){if(typeof kakao==="undefined"||!kakao.maps){setTimeout(initBloguitoMap,150);return;}'
            'var container=document.getElementById("bloguito-kakao-map");if(!container||container.dataset.mapReady==="1")return;container.dataset.mapReady="1";'
            'var first=groups[0];var map=new kakao.maps.Map(container,{center:new kakao.maps.LatLng(first.lat,first.lng),level:7});'
            'var zoomControl=new kakao.maps.ZoomControl();map.addControl(zoomControl,kakao.maps.ControlPosition.RIGHT);'
            'var bounds=new kakao.maps.LatLngBounds();var activeInfoWindow=null;'
            'groups.forEach(function(group){var pos=new kakao.maps.LatLng(group.lat,group.lng);bounds.extend(pos);'
            'var marker=new kakao.maps.Marker({position:pos,map:map,title:group.title});'
            'var info=new kakao.maps.InfoWindow({content:group.content,removable:true});'
            'kakao.maps.event.addListener(marker,"click",function(){if(activeInfoWindow)activeInfoWindow.close();info.open(map,marker);activeInfoWindow=info;});});'
            'if(groups.length===1){map.setCenter(new kakao.maps.LatLng(first.lat,first.lng));map.setLevel(5);}else{map.setBounds(bounds);}'
            '}if(document.readyState==="loading"){document.addEventListener("DOMContentLoaded",initBloguitoMap);}else{initBloguitoMap();}})();</script>'
            '</section>'
        )

    if overview_first:
        result += section_markup(1, sections[0])
        result += event_map_markup()

    # 2. Only confirmed booking/apply/lookup/purchase/install destinations are actions.
    # Informational sources remain in the citations below, never in the CTA.
    global_actions = [action for action in actions if action['url'] not in scoped_action_urls]
    if global_actions:
        buttons = []
        for idx, action in enumerate(global_actions):
            primary = idx == 0 and len(global_actions) <= 2
            background = '#0d7d59' if primary or len(global_actions) > 2 else '#ffffff'
            color = '#ffffff' if primary or len(global_actions) > 2 else '#0d7d59'
            buttons.append(
                f'<a href="{html.escape(action["url"], quote=True)}" target="_blank" rel="noopener noreferrer" '
                f'style="display:flex;align-items:center;justify-content:center;gap:10px;min-width:0;padding:13px 16px;background:{background};color:{color} !important;border:1px solid #0d7d59;text-decoration:none !important;border-radius:10px;font-size:16px;font-weight:700;overflow-wrap:anywhere">'
                f'<span style="flex-grow:1;text-align:center">{html.escape(action["label"])}</span>'
                f'<span aria-hidden="true">↗</span></a>'
            )
        result += ('<div class="bloguito-cta" style="margin:20px 0 26px;padding:16px;background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px">'
                   '<style>@media(max-width:640px){.bloguito-cta-grid{grid-template-columns:1fr!important}}</style>'
                   '<div style="font-size:17px;font-weight:700;color:#0f172a;margin-bottom:12px">공식 서비스 바로가기</div>'
                   f'<div class="bloguito-cta-grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,210px),1fr));gap:10px">{"".join(buttons)}</div></div>')

    # Navigation is visibly distinct from verified direct-service actions.
    navigation = official_navigation_links(plan, sources)
    if navigation:
        items = ''.join(
            '<li style="margin:10px 0 14px"><a href="'
            + html.escape(item['url'], quote=True)
            + '" target="_blank" rel="noopener noreferrer" '
            + 'style="color:#0d7d59;text-decoration:underline;font-weight:600">'
            + html.escape(item['label']) + '</a><div style="font-size:14px;color:#475569">'
            + html.escape(item['note']) + '</div></li>' for item in navigation)
        result += ('<aside class="bloguito-official-navigation" style="margin:18px 0 26px;'
                   'padding:12px 20px;background:#f8fafc;border:1px solid #cbd5e1;'
                   'border-radius:10px"><h2 style="font-size:17px;color:#334155;'
                   'margin:4px 0 8px">공식 사이트에서 메뉴 찾기</h2>'
                   + '<ul style="padding-left:20px;margin:0">' + items + '</ul></aside>')

    # 3. 경량 네이티브 목차 (Table of Contents - 구글 사이트링크 및 모바일 UX 최적화)
    toc_items = []
    toc_procedure_number = 0
    for number, section in enumerate(sections, 1):
        if number == 1 and overview_first:
            continue
        clean_heading = re.sub(r'^\s*(\d+[.)]\s*)?(STEP\s*\d+[.)]?\s*)?', '', section['heading'], flags=re.IGNORECASE).strip()
        if numbered_procedures and section_kind(section) == 'procedure':
            toc_procedure_number += 1
            heading_label = f'STEP {toc_procedure_number}. {clean_heading}'
        else:
            heading_label = clean_heading
        toc_items.append(f'<li style="margin:6px 0"><a href="#step-{number}" style="color:#0d7d59;text-decoration:none;font-weight:500">{html.escape(heading_label)}</a></li>')
    if plan.get('faq'):
        toc_items.append('<li style="margin:6px 0"><a href="#faq" style="color:#0d7d59;text-decoration:none;font-weight:500">자주 묻는 질문 (FAQ)</a></li>')
    # The evidence list is a footer, not an additional article section.

    result += ('<nav class="bloguito-toc" aria-label="본문 목차" style="padding:16px 20px;margin:20px 0 28px;background:#f8fafc;border:1px solid #e2e8f0;border-left:4px solid #0d7d59;border-radius:8px">'
               '<div style="font-weight:700;font-size:16px;color:#1e293b;margin-bottom:8px">목차</div>'
               '<ul style="margin:0;padding-left:22px;line-height:1.75;color:#475569;font-size:15px">'
               + ''.join(toc_items) + '</ul></nav>')

    # 4. 본문 섹션 (각 소제목에 점프 링크 앵커 ID 매핑)
    for number, section in enumerate(sections, 1):
        if number == 1 and overview_first:
            continue
        result += section_markup(number, section)

    # 4. 자주 묻는 질문 (FAQ)
    if plan.get('faq'):
        result += ('<h2 id="faq" style="font-family:inherit;font-size:clamp(20px,2.5vw,23px);'
                   'font-weight:700;letter-spacing:normal;line-height:1.45;'
                   'margin:36px 0 16px;padding-bottom:10px;border-bottom:2px solid #e2e8f0;color:#1a202c">자주 묻는 질문</h2>')
        for faq in plan['faq']:
            result += ('<div class="bloguito-faq" style="padding:20px 22px;margin:18px 0;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px">'
                       '<div style="display:flex;align-items:flex-start;margin-bottom:12px"><span style="background:#2563eb;color:#ffffff;font-weight:800;font-size:13px;padding:3px 9px;border-radius:4px;margin-right:10px;flex-shrink:0;margin-top:2px">Q</span>'
                       f'<h3 style="font-family:inherit;font-size:18px;line-height:1.5;margin:0;color:#1e293b;font-weight:700;letter-spacing:normal">{html.escape(faq["question"])}</h3></div>'
                       '<div style="display:flex;align-items:flex-start;padding-left:2px"><span style="background:#059669;color:#ffffff;font-weight:800;font-size:13px;padding:3px 9px;border-radius:4px;margin-right:10px;flex-shrink:0;margin-top:2px">A</span>'
                       f'<div style="flex-grow:1;color:#334155;line-height:1.8">{inline_text(faq["answer"])}</div></div></div>')

    # 5. Render only explicitly reviewed related-post links.  A reviewed bundle
    # must determine its HTML without consulting a mutable local recommendation
    # index at render time; candidate discovery belongs before semantic review.
    interlink_html = ''
    related = plan.get('related_posts', [])
    if related:
        items = ''.join(
            '<li style="margin-bottom:10px"><a href="'
            + html.escape(item['url'], quote=True)
            + '" style="color:#0d7d59;text-decoration:underline;font-weight:600;font-size:15.5px">'
            + html.escape(item['label']) + '</a></li>' for item in related)
        interlink_html = (
            '<div class="bloguito-interlink" style="padding:20px 24px;margin:40px 0 20px;'
            'background:#f8fafc;border:1px solid #e2e8f0;border-left:5px solid #0d7d59;border-radius:10px">'
            '<h3 style="margin:0 0 12px;font-size:18px;color:#1e293b;font-weight:700">관련 글</h3>'
            '<ul style="margin:0;padding-left:22px;line-height:1.8">' + items + '</ul></div>')

    # 6. 공식 출처 및 사실 검증 자료.
    # Exact action destinations already have a prominent reader-facing CTA, so
    # do not repeat those same URLs in the evidence footer. The footer is for
    # distinct evidence/reference pages first. If that would erase the entire
    # provenance section, retain the cited sources even when also used by a CTA.
    ids = []
    for block in all_blocks(plan):
        ids.extend(e['source_id'] for e in block['evidence'])
    for tool in plan.get('reader_tools', []):
        if isinstance(tool, dict):
            ids.extend(e['source_id'] for e in tool.get('evidence', [])
                       if isinstance(e, dict) and 'source_id' in e)
    ids = list(dict.fromkeys(ids))
    action_urls = {action['url'] for action in actions}
    citation_ids = [i for i in ids if source_map[i]['url'] not in action_urls]
    if not citation_ids:
        citation_ids = ids
    links = ''.join(
        '<li style="margin:8px 0"><a href="'
        + html.escape(source_map[i].get('citation_url') or source_map[i]['url'], quote=True)
        + '" rel="noopener noreferrer" style="color:#0d7d59;text-decoration:underline;word-break:break-all">'
        + html.escape((source_map[i].get('citation_label')
                       or source_map[i]['title'].splitlines()[0])[:100])
        + '</a></li>'
        for i in citation_ids)
    source_footer = (
        '<div style="margin-top:44px;padding:22px 24px;background:#fcfdfd;border:1px dashed #cbd5e1;border-radius:10px">'
        '<h2 id="sources" style="font-family:inherit;font-size:20px;font-weight:700;letter-spacing:normal;line-height:1.45;margin:0 0 14px;color:#334155;display:flex;align-items:center"><span style="margin-right:8px">🏛️</span>공식 출처 및 사실 검증 자료</h2>'
        '<ul class="source-list" style="padding-left:22px;margin:0;color:#64748b">'
        + links + '</ul></div>'
        if links else '')
    return result + interlink_html + source_footer + '</div>'
