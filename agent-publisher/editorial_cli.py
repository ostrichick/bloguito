"""Shared manual/automation entry point. Review writes reports; publish creates drafts only."""
import argparse
import json
from pathlib import Path
from agents.editorial import validate_bundle, render
from agents.editorial_writer import EditorialWriterAgent, article_from_bundle, load_inventory, fetch_sources


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['sources', 'check', 'review', 'manual-review', 'publish', 'reformat', 'list-drafts', 'promote-draft', 'update-existing', 'update-draft', 'revise-draft', 'replace-legacy-draft', 'fix-excerpt'])
    parser.add_argument('file', nargs='?', help='post ID for reformat/promote-draft; brief JSON for sources; editorial bundle JSON otherwise')
    parser.add_argument('--ids', nargs='+', type=int, help='one or more post IDs to promote')
    parser.add_argument('--confirm-publish', action='store_true', help='explicit authorization to publish reviewed, unchanged WordPress drafts')
    parser.add_argument('--post-id', type=int, help='specific existing public post to update')
    parser.add_argument('--expected-content-sha256', help='SHA256 of the original public WordPress post content')
    parser.add_argument('--confirm-update', action='store_true', help='explicit authorization to change only the specified reviewed post or draft')
    parser.add_argument('--confirm-title-change', action='store_true', help='explicit authorization to apply the reviewed title when updating an existing public post')
    parser.add_argument('--inventory', type=Path, help='read-only checks/review only; publish always queries WordPress')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--author-model', help='manual-review only: exact interactive author model, e.g. GPT-5.6 Sol')
    args = parser.parse_args()

    if args.action == 'list-drafts':
        from agents.publisher import PublisherAgent
        drafts = PublisherAgent().list_drafts()
        if not drafts:
            print("현재 대기 중인 초안이 없습니다.")
            return
        print(f"\n[대기 중인 초안 목록] (총 {len(drafts)}편)")
        print("-" * 75)
        print(f"{'ID':<6} | {'카테고리':<14} | {'등록일시':<19} | 제목")
        print("-" * 75)
        for d in drafts:
            print(f"{str(d.get('ID', '')):<6} | {str(d.get('category_name', '')):<14} | {str(d.get('post_date', '')):<19} | {d.get('post_title', '')}")
        print("-" * 75)
        return

    if args.action == 'promote-draft':
        from agents.publisher import PublisherAgent
        target_ids = []
        if args.ids:
            target_ids.extend(args.ids)
        if args.file:
            for item in str(args.file).split(','):
                item = item.strip()
                if item.isdigit():
                    target_ids.append(int(item))
        if not target_ids:
            parser.error("promote-draft requires at least one post ID (e.g. editorial_cli.py promote-draft 101,125 or --ids 101 125)")
        if not args.confirm_publish:
            parser.error('promote-draft requires --confirm-publish and a current reviewed editorial bundle')
        agent = PublisherAgent()
        results = []
        for pid in target_ids:
            print(f"\n[Promoting Post #{pid}]")
            res = agent.promote_draft(pid, confirmed=True)
            results.append(res)
        print(f"\n총 {len(results)}편 정식 공개(Publish) 전환 완료!")
        return

    if args.action == 'fix-excerpt':
        if args.inventory or args.file:
            parser.error('fix-excerpt requires only --post-id, --expected-content-sha256 and --confirm-update')
        from agents.editorial_updater import repair_missing_excerpt
        print('Verified excerpt for post ID:', repair_missing_excerpt(
            args.post_id, args.expected_content_sha256, confirmed=args.confirm_update))
        return

    if not args.file:
        parser.error(f"{args.action} requires a file argument")

    if args.action == 'reformat':
        if args.inventory:
            parser.error('reformat always queries WordPress')
        from agents.publisher import PublisherAgent
        print('Reformatted draft ID:', PublisherAgent().reformat_draft(int(args.file)))
        return
    args.file = Path(args.file)
    data = json.loads(args.file.read_text(encoding='utf-8'))
    if args.action == 'manual-review':
        if not args.author_model:
            parser.error('manual-review requires --author-model so the interactive GPT author is recorded explicitly')
        data['authoring'] = {
            'mode': 'interactive_chatgpt',
            'model': args.author_model,
        }
        data['used_model'] = args.author_model
    if args.action == 'replace-legacy-draft':
        if args.inventory:
            parser.error('replace-legacy-draft always queries the live WordPress inventory')
        from agents.editorial_legacy_draft import upgrade_legacy_draft
        print('Upgraded legacy draft ID:', upgrade_legacy_draft(
            args.post_id, data, args.expected_content_sha256, confirmed=args.confirm_update))
        return
    if args.action == 'update-draft':
        if args.inventory:
            parser.error('update-draft always queries WordPress')
        from agents.editorial_draft_updater import update_draft
        print('Updated draft ID:', update_draft(args.post_id, data, args.expected_content_sha256))
        return
    if args.action == 'revise-draft':
        if args.inventory:
            parser.error('revise-draft always queries WordPress')
        from agents.editorial_draft_reviser import revise_reviewed_draft
        print('Revised draft ID:', revise_reviewed_draft(
            args.post_id, data, args.expected_content_sha256, confirmed=args.confirm_update))
        return
    if args.action == 'update-existing':
        if args.inventory:
            parser.error('update-existing always queries the live WordPress inventory')
        from agents.editorial_updater import update_existing_public_post
        print('Updated public post ID:', update_existing_public_post(
            args.post_id, data, args.expected_content_sha256, confirmed=args.confirm_update,
            confirm_title_change=args.confirm_title_change))
        return
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
    if args.action in {'review', 'manual-review', 'publish'}:
        preflight = validate_bundle(data, inventory, require_review=False)
        if preflight['status'] != 'ready':
            print(json.dumps(preflight, ensure_ascii=False, indent=2))
            raise SystemExit(2)
        # These commands receive a completed plan. Keep the model adapter in
        # review-only mode so a manual GPT-authored article cannot be silently
        # rewritten by the configured Gemini writer.
        data['review'] = EditorialWriterAgent(writing_enabled=False).review(data)
    report = validate_bundle(data, inventory)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.output:
        args.output.write_text(json.dumps({'bundle': data, 'report': report}, ensure_ascii=False, indent=2), encoding='utf-8')
    if report['status'] != 'ready':
        raise SystemExit(2)
    if args.action in {'review', 'manual-review'}:
        args.file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        args.file.with_suffix('.html').write_text(render(data['plan'], data['sources']), encoding='utf-8')
    if args.action == 'publish':
        from agents.publisher import PublisherAgent
        print('Draft ID:', PublisherAgent().publish(article_from_bundle(data)))


if __name__ == '__main__':
    main()
