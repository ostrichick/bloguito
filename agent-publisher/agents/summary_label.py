"""Deterministic, label-only migration; never reserialize article HTML."""
import hashlib
import re
from html.parser import HTMLParser

SUMMARY_LABEL = '한눈에 보기'
LEGACY_LABELS = {'핵심 답변', '핵심답변', '핵심 요약', '핵심요약', '빠른 요약', '핵심 정보', '먼저 답부터'}
GREEN_BACKGROUNDS = {'#f0f8f5', '#edf7f4', '#edf7f3', '#eaf7f2'}
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}


def sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class SummaryParser(HTMLParser):
    def __init__(self, content):
        super().__init__(convert_charrefs=False)
        self.content = content
        self.lines = [0]
        self.lines.extend(m.end() for m in re.finditer('\n', content))
        self.stack = []
        self.edits = []
        self.labels = []
        self.unknown = []
        self.boxes = 0

    def position(self):
        line, col = self.getpos()
        return self.lines[line - 1] + col

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        style = re.sub(r'\s+', '', attrs.get('style', '').lower())
        green = any(re.search(r'(?:background|background-color):' + color + r'(?:;|$)', style)
                    for color in GREEN_BACKGROUNDS)
        summary = tag == 'div' and ('bloguito-summary' in attrs.get('class', '').split()
                                   or (green and 'border-left:' in style))
        if tag not in VOID:
            self.stack.append({'tag': tag, 'summary': summary, 'start': self.position(),
                               'data': [], 'children': 0, 'matched': False,
                               'explicit': 'bloguito-summary' in attrs.get('class', '').split()})
            if len(self.stack) > 1:
                self.stack[-2]['children'] += 1

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_data(self, data):
        if self.stack:
            self.stack[-1]['data'].append((self.position(), data))

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1]['tag'] != tag:
            # Legacy WP markup can contain stray paragraph ends. Do not widen scope.
            return
        node = self.stack.pop()
        if node['summary'] and (node['matched'] or node['explicit']):
            self.boxes += 1
        if not any(item['summary'] for item in self.stack):
            return
        if node['children'] or len(node['data']) != 1 or tag not in {'div', 'strong', 'b', 'h2', 'h3', 'span'}:
            return
        start, raw = node['data'][0]
        label = raw.strip()
        if label == '3초 요약' and tag == 'span':
            end = self.position() + len('</span>')
            self.edits.append((node['start'], end, self.content[node['start']:end], ''))
        elif label in LEGACY_LABELS or label == SUMMARY_LABEL:
            self.labels.append(label)
            next(item for item in reversed(self.stack) if item['summary'])['matched'] = True
            if label != SUMMARY_LABEL:
                left = len(raw) - len(raw.lstrip())
                self.edits.append((start + left, start + left + len(label), label, SUMMARY_LABEL))


def inspect(content):
    parser = SummaryParser(content)
    parser.feed(content)
    parser.close()
    if parser.boxes and len(parser.labels) != parser.boxes:
        raise ValueError('unrecognized_or_ambiguous_summary_heading')
    return parser


def normalize_summary_labels(content):
    parser = inspect(content)
    updated = content
    for start, end, old, new in sorted(parser.edits, reverse=True):
        if content[start:end] != old:
            raise ValueError('summary_edit_span_mismatch')
        updated = updated[:start] + new + updated[end:]
    saved = inspect(updated)
    if saved.boxes != parser.boxes or any(label != SUMMARY_LABEL for label in saved.labels) or saved.edits:
        raise ValueError('summary_label_verification_failed')
    # Bytes outside the explicitly recognized heading and obsolete badge stay identical.
    edits = [{'start': len(content[:a].encode('utf-8')), 'end': len(content[:b].encode('utf-8')),
              'old': old, 'new': new} for a, b, old, new in sorted(parser.edits)]
    return updated, {'boxes': parser.boxes, 'old_labels': parser.labels, 'edits': edits,
                     'before_sha256': sha256(content), 'after_sha256': sha256(updated)}
