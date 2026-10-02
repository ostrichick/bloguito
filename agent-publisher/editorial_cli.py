"""Shared manual/automation entry point. Review writes reports; publish creates drafts only."""
import argparse
from contextlib import contextmanager
from contextvars import ContextVar
import json
import sys
from pathlib import Path
from agents.editorial import validate_bundle, render
from agents.editorial_writer import EditorialWriterAgent, article_from_bundle, load_inventory, fetch_sources
from agents.runtime_stdio import configure_utf8_stdio
from agents.workflow_metrics import workflow_run


configure_utf8_stdio()


_prepared_edit_decision = ContextVar('prepared_edit_decision', default=None)


def _load_media_metadata_file(path: Path) -> tuple[str, str]:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('invalid_media_metadata_file') from exc
    if not isinstance(payload, dict) or set(payload) != {'media_title', 'alt_text'}:
        raise ValueError('invalid_media_metadata_file')
    media_title = payload.get('media_title')
    alt_text = payload.get('alt_text')
    if not isinstance(media_title, str) or not isinstance(alt_text, str):
        raise ValueError('invalid_media_metadata_file')
    return media_title, alt_text


@contextmanager
def prepared_edit_decision(decision):
    """Bind one preclassified edit decision across the SSH adapter boundary."""
    token = _prepared_edit_decision.set(decision)
    try:
        yield
    finally:
        _prepared_edit_decision.reset(token)


PRIMARY_CONTENT_ACTIONS = {
    'prepare-draft',
    'edit-post',
    'replace-featured-image',
}
PUBLICATION_ACTIONS = {'promote-draft'}
MAINTENANCE_ACTIONS = {
    'sources', 'check', 'review', 'manual-review', 'reformat', 'list-drafts',
    'import-section-image', 'complete-task-qa', 'checkpoint-after-image',
    'update-after-image-checkpoint', 'repair-draft-category', 'fix-excerpt',
    'volatility-report',
}
ALL_ACTIONS = sorted(
    PRIMARY_CONTENT_ACTIONS | PUBLICATION_ACTIONS | MAINTENANCE_ACTIONS
)


def _main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=ALL_ACTIONS)
    parser.add_argument('file', nargs='?', help='post ID for reformat/promote-draft; brief JSON for sources; editorial bundle JSON otherwise')
    parser.add_argument('--ids', nargs='+', type=int, help='one or more post IDs to promote')
    parser.add_argument('--confirm-publish', action='store_true', help='explicit authorization to publish reviewed, unchanged WordPress drafts')
    parser.add_argument('--post-id', type=int, help='specific existing public post to update')
    parser.add_argument('--expected-content-sha256', help='SHA256 of the original public WordPress post content')
    parser.add_argument('--expected-thumbnail-id', type=int,
                        help='replace-featured-image: current _thumbnail_id CAS value')
    parser.add_argument('--confirm-update', action='store_true', help='explicit authorization to change only the specified reviewed post or draft')
    parser.add_argument('--confirm-title-change', action='store_true', help='explicit authorization to apply the reviewed title when updating an existing public post or reviewed draft')
    parser.add_argument('--edit-intent', help='edit-post: the user-requested scope of this edit')
    parser.add_argument('--resume', action='store_true',
                        help='edit-post: resume a matching interrupted task-state after live SHA reconciliation')
    parser.add_argument('--alt-text', help='replace-featured-image: reviewed alt text for the imported image')
    parser.add_argument('--media-title', help='import-section-image: reviewed WordPress attachment title')
    parser.add_argument('--media-metadata-file', type=Path,
                        help='import-section-image: UTF-8 JSON with media_title and alt_text; avoids non-ASCII command-line transport')
    parser.add_argument('--qa-scope', action='append',
                        choices=['content-mobile-desktop', 'cta-destination', 'layout-accessibility',
                                 'featured-image', 'public-page'],
                        help='complete-task-qa: QA scope actually completed; repeat for multiple scopes')
    parser.add_argument('--observed-thumbnail-id', type=int,
                        help='complete-task-qa: thumbnail ID observed during featured-image browser QA')
    parser.add_argument('--remaining-step', action='append',
                        help='checkpoint-after-image: user-requested work that must continue after image generation')
    parser.add_argument('--completion-requirement', action='append', choices=[
        'image_generated', 'image_saved_or_handed_off', 'uploaded', 'featured_image_set',
        'requested_content_or_meta_edits_done', 'readback_verified', 'content_sha_preserved',
    ], help='checkpoint-after-image: condition that must be true before the compound task may finish')
    parser.add_argument('--completed-step', action='append', choices=[
        'image_generated', 'image_saved_or_handed_off', 'uploaded', 'featured_image_set',
        'requested_content_or_meta_edits_done', 'readback_verified', 'content_sha_preserved',
    ], help='update-after-image-checkpoint: completed continuation condition')
    parser.add_argument('--image-handle',
                        help='checkpoint-after-image/update-after-image-checkpoint: expected or observed image file/handle')
    parser.add_argument('--inventory', type=Path, help='read-only checks/review only; publish always queries WordPress')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--author-model', help='manual-review/prepare-draft: exact interactive author model, e.g. GPT-5.6 Sol')
    parser.add_argument('--image-path', type=Path,
                        help='prepare-draft: required reviewed local representative image; Gemini cover generation is scheduler-only')
    args = parser.parse_args()

    if args.media_metadata_file and args.action != 'import-section-image':
        parser.error('--media-metadata-file is only valid for import-section-image')

    if args.action == 'volatility-report':
        from agents.volatility import migration_report
        source = Path(args.file) if args.file else Path(__file__).resolve().parent / 'data' / 'search_briefs.json'
        try:
            briefs = json.loads(source.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError('invalid_volatility_report_source') from exc
        if not isinstance(briefs, list) or any(not isinstance(item, dict) for item in briefs):
            raise ValueError('invalid_volatility_report_source')
        if args.file is None:
            source_label = 'data/search_briefs.json'
        else:
            try:
                source_label = source.resolve().relative_to(Path.cwd().resolve()).as_posix()
            except ValueError:
                source_label = str(source)
        payload = {
            'source': source_label,
            'mode': 'read-only-suggestion',
            'rows': migration_report(briefs),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if args.output:
            args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return

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

    if args.action == 'complete-task-qa':
        if args.inventory or args.file:
            parser.error('complete-task-qa requires only --post-id and --expected-content-sha256')
        from agents.task_state import mark_browser_qa_complete
        state = mark_browser_qa_complete(
            args.post_id, args.expected_content_sha256, completed_scopes=args.qa_scope,
            observed_thumbnail_id=args.observed_thumbnail_id)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        if args.output:
            args.output.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        return

    if args.action == 'checkpoint-after-image':
        if args.inventory or args.file:
            parser.error('checkpoint-after-image uses --post-id and checkpoint arguments only')
        if (not args.post_id or not args.expected_content_sha256 or not args.expected_thumbnail_id
                or not args.remaining_step or not args.completion_requirement or not args.image_handle):
            parser.error('checkpoint-after-image requires --post-id, --expected-content-sha256, '
                         '--expected-thumbnail-id, --remaining-step, --completion-requirement and --image-handle')
        from agents.task_state import write_after_image_checkpoint
        state = write_after_image_checkpoint(
            args.post_id,
            remaining_steps=args.remaining_step,
            expected_content_sha256=args.expected_content_sha256,
            expected_thumbnail_id=args.expected_thumbnail_id,
            target_image_handle=args.image_handle,
            completion_requirements=args.completion_requirement,
        )
        print(json.dumps(state, ensure_ascii=False, indent=2))
        if args.output:
            args.output.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        return

    if args.action == 'update-after-image-checkpoint':
        if args.inventory or args.file:
            parser.error('update-after-image-checkpoint uses --post-id and checkpoint arguments only')
        if not args.post_id or (not args.completed_step and not args.image_handle):
            parser.error('update-after-image-checkpoint requires --post-id and --completed-step and/or --image-handle')
        from agents.task_state import update_after_image_checkpoint
        state = update_after_image_checkpoint(
            args.post_id,
            completed_steps=args.completed_step,
            target_image_handle=args.image_handle,
        )
        print(json.dumps(state, ensure_ascii=False, indent=2))
        if args.output:
            args.output.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        return

    if args.action == 'replace-featured-image':
        label = args.action
        if args.inventory or args.file:
            parser.error(f'{label} uses --post-id/--image-path and no bundle file')
        if not args.post_id or not args.image_path or not args.alt_text or not args.confirm_update:
            parser.error(f'{label} requires --post-id, --image-path, --alt-text and --confirm-update')
        if args.expected_content_sha256 or args.expected_thumbnail_id:
            parser.error(f'{label} reads its own current content SHA and thumbnail baseline')
        from agents.featured_image import replace_featured_image_from_live_baseline
        result = replace_featured_image_from_live_baseline(
            args.post_id,
            args.image_path,
            alt_text=args.alt_text,
            confirmed=True,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.output:
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return

    if args.action == 'import-section-image':
        if args.inventory or args.file:
            parser.error('import-section-image uses --post-id/--image-path and no bundle file')
        media_title = args.media_title
        alt_text = args.alt_text
        if args.media_metadata_file:
            if media_title or alt_text:
                parser.error('import-section-image uses either --media-metadata-file or --media-title/--alt-text')
            try:
                media_title, alt_text = _load_media_metadata_file(args.media_metadata_file)
            except ValueError as exc:
                parser.error(str(exc))
        if not args.image_path or not alt_text or not media_title:
            parser.error('import-section-image requires --image-path and either --media-metadata-file or --media-title/--alt-text')
        from agents.section_image import import_section_image
        result = import_section_image(
            args.post_id, args.image_path, args.expected_content_sha256,
            media_title=media_title, alt_text=alt_text,
            confirmed=args.confirm_update,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.output:
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return

    if args.action == 'edit-post':
        if args.inventory:
            parser.error('edit-post always uses tracked reviewed state and live WordPress CAS')
        if not args.post_id or not args.expected_content_sha256 or not args.confirm_update:
            parser.error('edit-post requires --post-id, --expected-content-sha256 and --confirm-update')
        bundle = None
        if args.file:
            candidate = Path(args.file)
            if not candidate.is_file():
                parser.error('edit-post bundle file not found')
            bundle = json.loads(candidate.read_text(encoding='utf-8'))
            if not args.edit_intent:
                parser.error('edit-post with a bundle requires --edit-intent')
        if args.image_path and (not args.expected_thumbnail_id or not args.alt_text):
            parser.error('edit-post with --image-path requires --expected-thumbnail-id and --alt-text')
        if bundle is None and not args.image_path:
            parser.error('edit-post requires either a bundle file or --image-path')
        from agents.edit_post import edit_reviewed_post
        result = edit_reviewed_post(
            args.post_id,
            bundle,
            args.expected_content_sha256,
            confirmed=True,
            edit_intent=args.edit_intent,
            confirm_title_change=args.confirm_title_change,
            image_path=args.image_path,
            expected_thumbnail_id=args.expected_thumbnail_id,
            alt_text=args.alt_text,
            resume=args.resume,
            prepared_decision=_prepared_edit_decision.get(),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.output:
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
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
    if args.action == 'manual-review' and args.author_model:
        data['authoring'] = {
            'mode': 'interactive_chatgpt',
            'model': args.author_model,
        }
        data['used_model'] = args.author_model
    if args.action == 'manual-review':
        if not args.author_model:
            parser.error('manual-review requires --author-model so the interactive GPT author is recorded explicitly')
    if args.action == 'repair-draft-category':
        if args.inventory:
            parser.error('repair-draft-category always queries WordPress')
        from agents.editorial_draft_category import repair_reviewed_draft_category
        print('Repaired draft category ID:', repair_reviewed_draft_category(
            args.post_id, args.expected_content_sha256, confirmed=args.confirm_update))
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
    if args.action == 'prepare-draft' and args.inventory:
        parser.error(f'{args.action} cannot use an inventory override')
    if args.image_path and (not args.image_path.is_file()
                            or args.image_path.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp'}):
        parser.error('--image-path must point to an existing jpg/jpeg/png/webp file')
    if args.action == 'prepare-draft':
        # The fast manual-authoring path deliberately avoids a pre-review WordPress
        # inventory round trip. Content/source checks run locally; the Publisher
        # performs the one authoritative live inventory/full validation immediately
        # before the draft write.
        local_preflight = validate_bundle(
            data, {}, require_review=False, scopes={'content', 'source'})
        if local_preflight['status'] != 'ready':
            print(json.dumps(local_preflight, ensure_ascii=False, indent=2))
            raise SystemExit(2)

        # Interactive/manual authoring (including ChatGPT and CoS) must never
        # invoke Gemini image generation. Automatic cover generation belongs
        # exclusively to the scheduled pipeline in main.py/run_daily.sh.
        if not args.image_path:
            parser.error(
                'prepare-draft requires --image-path for manual/interactive runs; '
                'Gemini cover generation is scheduler-only'
            )

        existing_review = validate_bundle(
            data, {}, scopes={'content', 'source', 'review'}) if data.get('review') else None
        review_is_current = bool(existing_review and existing_review['status'] == 'ready')
        if not review_is_current and not args.author_model:
            parser.error('prepare-draft requires --author-model when a current semantic review is not already bound')
        if not review_is_current:
            data['authoring'] = {
                'mode': 'interactive_chatgpt',
                'model': args.author_model,
            }
            data['used_model'] = args.author_model

        def review_bundle():
            if review_is_current:
                return data['review']
            return EditorialWriterAgent(writing_enabled=False).review(data)

        image_path = Path(args.image_path)
        if not review_is_current:
            data['review'] = review_bundle()

        local_final = validate_bundle(
            data, {}, scopes={'content', 'source', 'review'})
        if local_final['status'] != 'ready':
            print(json.dumps(local_final, ensure_ascii=False, indent=2))
            raise SystemExit(2)

        # Persist the completed review before the external write so an interrupted
        # WordPress step can be resumed without paying for the same review again.
        args.file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        args.file.with_suffix('.html').write_text(render(data['plan'], data['sources']), encoding='utf-8')

        from agents.publisher import PublisherAgent
        post_id = PublisherAgent().publish(article_from_bundle(data), image_path=image_path)
        seo = data.get('brief', {}).get('seo') or {}
        receipt = {
            'action': 'prepare-draft',
            'post_id': int(post_id),
            'status': 'draft',
            'title': data['plan']['title'],
            'focus_keyword': data['brief'].get('primary_keyword', ''),
            'seo_title': seo.get('title') or data['plan']['title'],
            'seo_description': seo.get('description') or data['plan']['lead']['text'][:160],
            'semantic_review': 'reused' if review_is_current else 'created',
            'featured_image_path': str(image_path),
            'featured_image_attached': True,
            'live_inventory_validation': 'passed',
        }
        print('Draft ID:', post_id)
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        if args.output:
            args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
        return
    inventory = json.loads(args.inventory.read_text(encoding='utf-8')) if args.inventory else load_inventory()
    if args.action in {'review', 'manual-review'}:
        preflight = validate_bundle(data, inventory, require_review=False)
        if preflight['status'] != 'ready':
            print(json.dumps(preflight, ensure_ascii=False, indent=2))
            raise SystemExit(2)
        # These commands receive a completed plan. Keep the model adapter in
        # review-only mode so a manual GPT-authored article cannot be silently
        # rewritten by the configured Gemini writer.
        data['review'] = EditorialWriterAgent(writing_enabled=False).review(data)
        report = validate_bundle(data, inventory)
    else:
        report = validate_bundle(data, inventory)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.output:
        args.output.write_text(json.dumps({'bundle': data, 'report': report}, ensure_ascii=False, indent=2), encoding='utf-8')
    if report['status'] != 'ready':
        raise SystemExit(2)
    if args.action in {'review', 'manual-review'}:
        args.file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        args.file.with_suffix('.html').write_text(render(data['plan'], data['sources']), encoding='utf-8')


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else 'unknown'
    with workflow_run(action):
        return _main()


if __name__ == '__main__':
    main()
