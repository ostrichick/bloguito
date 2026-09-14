"""Shared manual/automation entry point. Review writes reports; publish creates drafts only."""
import argparse
import json
from pathlib import Path
from agents.editorial import validate_bundle, render
from agents.editorial_writer import EditorialWriterAgent, article_from_bundle, load_inventory, fetch_sources


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['sources', 'check', 'review', 'publish'])
    parser.add_argument('file', type=Path, help='brief JSON for sources; editorial bundle JSON otherwise')
    parser.add_argument('--inventory', type=Path, help='read-only checks/review only; publish always queries WordPress')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    data = json.loads(args.file.read_text(encoding='utf-8'))
    if args.action == 'sources':
        from agents.editorial import topic_reasons
        errors = topic_reasons(data)
        if errors:
            raise ValueError(errors)
        if not args.output:
            parser.error('sources requires --output')
        args.output.write_text(json.dumps({'brief': data, 'sources': fetch_sources(data)}, ensure_ascii=False, indent=2), encoding='utf-8')
        return
    if args.action == 'publish' and args.inventory:
        parser.error('publish cannot use an inventory override')
    if args.action == 'publish':
        from sync_wordpress_inventory import sync_inventory
        sync_inventory()
    inventory = json.loads(args.inventory.read_text(encoding='utf-8')) if args.inventory else load_inventory()
    if args.action in {'review', 'publish'}:
        preflight = validate_bundle(data, inventory, require_review=False)
        if preflight['status'] != 'ready':
            print(json.dumps(preflight, ensure_ascii=False, indent=2))
            raise SystemExit(2)
        data['review'] = EditorialWriterAgent().review(data)
    report = validate_bundle(data, inventory)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.output:
        args.output.write_text(json.dumps({'bundle': data, 'report': report}, ensure_ascii=False, indent=2), encoding='utf-8')
    if report['status'] != 'ready':
        raise SystemExit(2)
    if args.action == 'review':
        args.file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        args.file.with_suffix('.html').write_text(render(data['plan'], data['sources']), encoding='utf-8')
    if args.action == 'publish':
        from agents.publisher import PublisherAgent
        print('Draft ID:', PublisherAgent().publish(article_from_bundle(data)))


if __name__ == '__main__':
    main()
