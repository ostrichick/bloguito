"""Evaluate *observed* browser QA evidence without initiating browser or WP I/O.

The single change classifier owns required QA scopes. This module only checks
recorded observations, not whether an edit needs a browser. It never marks a
task complete; task_state accepts its independently re-evaluated receipt.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image

from agents.qa_scope import validate_qa_scopes


QA_EVIDENCE_SCHEMA = 1
RENDER_SOURCES = {'local_static', 'wordpress_theme', 'authenticated_preview'}
QA_VIEWPORTS = (390, 1280)
_SHA = re.compile(r'[0-9a-f]{64}\Z')


def _pass_or_fail(ok: bool) -> str:
    return 'pass' if ok else 'fail'


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _valid_url(url: str, render_source: str) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urlsplit(url)
    if render_source == 'local_static':
        return parsed.scheme == 'file' or (parsed.scheme == 'http' and parsed.hostname in {'localhost', '127.0.0.1'})
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        return False
    if render_source == 'authenticated_preview':
        return ('preview=true' in parsed.query or 'preview=1' in parsed.query
                or 'preview_id=' in parsed.query)
    return True


def _evaluate_screen(screen: dict, *, width: int, scopes: list[str], config: dict) -> dict:
    if (not isinstance(screen, dict) or not isinstance(screen.get('viewport'), dict)
            or screen['viewport'].get('width') != width
            or type(screen['viewport'].get('height')) is not int
            or screen['viewport']['height'] < 300):
        raise ValueError('browser_qa_viewport_mismatch')
    observation = screen.get('observation')
    if not isinstance(observation, dict) or observation.get('ready_state') != 'complete':
        raise ValueError('browser_qa_dom_not_observed')
    if screen.get('source') is not None:
        raise ValueError('browser_qa_unsupported_source_override')
    client, scroll = observation.get('client_width'), observation.get('scroll_width')
    if any(type(v) not in {int, float} or v <= 0 for v in (client, scroll)):
        raise ValueError('browser_qa_overflow_metrics_missing')
    if observation.get('inner_width') != width:
        raise ValueError('browser_qa_emulated_viewport_not_applied')
    results = {'document_overflow': _pass_or_fail(scroll <= client + 2)}
    zoom = observation.get('zoom_simulated_half_viewport')
    if (not isinstance(zoom, dict) or zoom.get('kind') != 'css_half_width_reflow_not_native_zoom'
            or zoom.get('width') != round(width / 2)
            or not isinstance(zoom.get('metrics'), dict)):
        results['zoom_reflow_simulated'] = 'unverified'
    else:
        metrics=zoom['metrics']
        results['zoom_reflow_simulated'] = _pass_or_fail(
            metrics.get('inner_width') == round(width / 2)
            and type(metrics.get('client_width')) in {int, float}
            and type(metrics.get('scroll_width')) in {int, float}
            and metrics['scroll_width'] <= metrics['client_width'] + 2)

    toc = observation.get('toc')
    if not isinstance(toc, dict) or not isinstance(toc.get('links'), list):
        raise ValueError('browser_qa_toc_observation_missing')
    links = toc['links']
    results['toc_anchors'] = _pass_or_fail(bool(links) and all(
        isinstance(link, dict) and link.get('target_found') is True
        and link.get('target_unique') is True and link.get('click_hash_matched') is True
        for link in links
    ))

    tables = observation.get('tables')
    if not isinstance(tables, list):
        raise ValueError('browser_qa_tables_observation_missing')
    expected_mobile = width == 390
    table_ok = True
    for table in tables:
        if not isinstance(table, dict):
            raise ValueError('browser_qa_table_shape_invalid')
        has_cards = table.get('has_mobile_cards') is True
        if not (isinstance(table.get('caption'), str) and table['caption'].strip()
                and type(table.get('headers')) is int and table['headers'] >= 2
                and type(table.get('rows')) is int and table['rows'] > 0
                and table.get('region') is True and table.get('focusable') is True):
            table_ok = False
        if has_cards:
            table_ok &= (table.get('visible') is (not expected_mobile)
                         and table.get('cards_visible') is expected_mobile
                         and table.get('card_count') == table.get('rows'))
        elif table.get('visible') is not True:
            table_ok = False
        if table.get('visible') is True:
            if not all(type(table.get(field)) in {int, float}
                       for field in ('client_width', 'scroll_width', 'keyboard_scroll_delta')):
                table_ok = False
            elif table['scroll_width'] > table['client_width'] + 2:
                table_ok &= table.get('keyboard_scroll_delta', 0) > 0
    results['tables_cards_keyboard'] = _pass_or_fail(bool(table_ok))
    page_links = observation.get('links')
    if not isinstance(page_links, list):
        results['links'] = 'unverified'
    else:
        results['links'] = _pass_or_fail(all(
            isinstance(link,dict) and link.get('valid') is True
            and link.get('target_existing') is True
            for link in page_links))

    if 'cta-destination' in scopes:
        ctas = observation.get('ctas')
        expected = config.get('cta_targets')
        if not isinstance(ctas, list) or not isinstance(expected, list) or not expected:
            results['cta_destination'] = 'unverified'
        else:
            by_href = {entry.get('href'): entry for entry in ctas if isinstance(entry, dict)}
            results['cta_destination'] = _pass_or_fail(all(
                isinstance(href, str) and href in by_href
                and by_href[href].get('click_navigation_verified') is True
                and by_href[href].get('navigated_url', '').split('#', 1)[0] == href.split('#', 1)[0]
                for href in expected
            ))

    calculator_cases = config.get('calculator_cases', [])
    calculator_present = observation.get('calculator_present') is True
    calculated = observation.get('calculator_cases', [])
    if calculator_present or calculator_cases:
        if not isinstance(calculator_cases, list) or not calculator_cases or not isinstance(calculated, list):
            results['calculator_inputs_results'] = 'unverified'
        else:
            cases = {case.get('id'): case for case in calculated if isinstance(case, dict)}
            results['calculator_inputs_results'] = _pass_or_fail(all(
                isinstance(case, dict) and case.get('id') in cases
                and isinstance(case.get('expected_text'), str)
                and bool(case['expected_text'])
                and cases[case['id']].get('inputs_executed') is True
                and cases[case['id']].get('result_observed') is True
                and isinstance(cases[case['id']].get('text'), str)
                and case.get('expected_text') in cases[case['id']]['text']
                for case in calculator_cases
            ))
    else:
        results['calculator_inputs_results'] = 'not_applicable'
    return results


def evaluate_browser_qa(evidence: dict, *, evidence_dir: Path) -> dict:
    """Return a re-evaluated receipt. Never trust a supplied success/status flag."""
    if not isinstance(evidence, dict) or evidence.get('schema') != QA_EVIDENCE_SCHEMA:
        raise ValueError('browser_qa_schema_invalid')
    source = evidence.get('render_source')
    post_id, content_sha = evidence.get('post_id'), evidence.get('content_sha256')
    if (source not in RENDER_SOURCES or type(post_id) is not int or post_id <= 0
            or not isinstance(content_sha, str) or not _SHA.fullmatch(content_sha)):
        raise ValueError('browser_qa_identity_invalid')
    url = evidence.get('url')
    if not _valid_url(url, source):
        raise ValueError('browser_qa_render_source_url_conflict')
    execution = evidence.get('execution')
    if (not isinstance(execution, dict) or execution.get('engine') != 'existing_cdp_session'
            or not isinstance(execution.get('target_id'), str)
            or len(execution['target_id']) < 8
            or not isinstance(execution.get('user_agent'), str)
            or not execution['user_agent'].strip()):
        raise ValueError('browser_qa_actual_execution_evidence_required')
    try:
        recorded = datetime.fromisoformat(evidence['executed_at'])
        if recorded.tzinfo is None:
            raise ValueError()
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('browser_qa_execution_time_required') from exc
    scopes = validate_qa_scopes(evidence.get('required_scopes'))
    config = evidence.get('config')
    if not isinstance(config, dict):
        raise ValueError('browser_qa_config_missing')
    screens = evidence.get('screens')
    if not isinstance(screens, list) or len(screens) != 2:
        raise ValueError('browser_qa_two_viewports_required')

    verified = {}
    for width, screen in zip(QA_VIEWPORTS, screens):
        if not isinstance(screen, dict) or not _valid_url(screen.get('url'), source):
            raise ValueError('browser_qa_screen_url_invalid')
        if urlsplit(screen['url']).hostname != urlsplit(url).hostname:
            raise ValueError('browser_qa_site_origin_changed')
        screenshot = screen.get('screenshot')
        if not isinstance(screenshot, dict):
            raise ValueError('browser_qa_screenshot_missing')
        name, claimed_hash = screenshot.get('path'), screenshot.get('sha256')
        if (not isinstance(name, str) or '/' in name or '\\' in name or name.startswith('.')
                or not isinstance(claimed_hash, str) or not _SHA.fullmatch(claimed_hash)):
            raise ValueError('browser_qa_screenshot_receipt_invalid')
        path = evidence_dir / name
        if not path.is_file() or _sha256(path) != claimed_hash:
            raise ValueError('browser_qa_screenshot_hash_mismatch')
        try:
            with Image.open(path) as captured:
                if captured.format != 'PNG' or captured.size != (
                        width, screen['viewport']['height']):
                    raise ValueError('browser_qa_screenshot_dimensions_mismatch')
                captured.verify()
        except (OSError, SyntaxError) as exc:
            raise ValueError('browser_qa_screenshot_decode_failed') from exc
        verified[str(width)] = _evaluate_screen(screen, width=width, scopes=scopes, config=config)

    if source in {'wordpress_theme', 'authenticated_preview'}:
        if not all(screen['observation'].get('wp_theme_dom') is True for screen in screens):
            raise ValueError('browser_qa_wordpress_theme_not_observed')
    if source == 'authenticated_preview':
        if not all(screen['observation'].get('authenticated_dom') is True for screen in screens):
            raise ValueError('browser_qa_authenticated_preview_not_observed')

    needs = {'content-mobile-desktop': ['document_overflow', 'toc_anchors', 'tables_cards_keyboard', 'links'],
             'layout-accessibility': ['document_overflow', 'tables_cards_keyboard', 'zoom_reflow_simulated'],
             'cta-destination': ['cta_destination']}
    completed = []
    incomplete = {}
    for scope in scopes:
        checks = needs.get(scope)
        if checks is None:
            incomplete[scope] = 'outside_q1_browser_harness'
            continue
        missed = [f'{width}:{check}:{verified[str(width)].get(check, "unverified")}'
                  for width in QA_VIEWPORTS for check in checks
                  if verified[str(width)].get(check) != 'pass']
        if (scope in {'content-mobile-desktop', 'layout-accessibility'}
                and any(verified[str(w)]['calculator_inputs_results'] in {'fail', 'unverified'}
                        for w in QA_VIEWPORTS)):
            missed.append('calculator_inputs_results_incomplete')
        if missed:
            incomplete[scope] = missed
        else:
            completed.append(scope)
    status = ('needs_browser_or_manual_review' if incomplete else
              'local_static_browser_pass_only' if source == 'local_static' else
              'browser_pass')
    # JS execution through a local file may verify its *own* rendered DOM, but
    # cannot close QA for a saved WordPress post's actual theme/preview.
    eligible = completed if source != 'local_static' else []
    return {
        'schema': QA_EVIDENCE_SCHEMA, 'post_id': post_id, 'content_sha256': content_sha,
        'render_source': source, 'url': url, 'required_scopes': scopes,
        'observed_checks': verified, 'completed_scopes': completed,
        'eligible_wp_completed_scopes': eligible,
        'incomplete_scopes': incomplete, 'status': status,
        'native_zoom_200pct': 'not_verified_by_cdp_viewport_simulation',
        'wordpress_content_sha_readback': 'external_task_state_binding_only',
    }


def verify_qa_completion_receipt(path: Path, *, post_id: int, content_sha256: str,
                                 required_scopes: set[str]) -> dict:
    """Fail closed on absent, static, partial or mismatched evidence at QA close."""
    path = Path(path)
    try:
        evidence = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError('browser_qa_evidence_unreadable') from exc
    result = evaluate_browser_qa(evidence, evidence_dir=path.parent)
    if result['post_id'] != post_id or result['content_sha256'] != content_sha256:
        raise ValueError('browser_qa_evidence_content_binding_mismatch')
    if not required_scopes.issubset(set(result['eligible_wp_completed_scopes'])):
        raise ValueError('browser_qa_evidence_scope_unverified')
    return result
