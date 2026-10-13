#!/usr/bin/env node
/** Reuse an already-running Edge/Chrome CDP tab; never launch a browser/profile.
 * Node >=22 provides the WebSocket client. No npm packages or WordPress writes.
 */
import {createHash, randomUUID} from 'node:crypto';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {resolve, join} from 'node:path';

const SHA = /^[0-9a-f]{64}$/;
const SCOPES = new Set(['content-mobile-desktop', 'layout-accessibility',
  'cta-destination', 'featured-image', 'public-page']);
const SOURCE = new Set(['local_static', 'wordpress_theme', 'authenticated_preview']);

function argumentsMap(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) {
    if (!argv[i]?.startsWith('--') || !argv[i + 1]) throw Error('invalid_browser_qa_arguments');
    if (args[argv[i]]) throw Error('duplicate_browser_qa_argument');
    args[argv[i]] = argv[i + 1];
  }
  return args;
}
function validateArgs(args) {
  const required = ['--post-id', '--content-sha', '--render-source', '--target-id', '--output-dir', '--url'];
  if (required.some(key => !args[key])) throw Error('required_browser_qa_options_missing');
  if (!Number.isSafeInteger(Number(args['--post-id'])) || Number(args['--post-id']) <= 0 ||
      !SHA.test(args['--content-sha']) || !SOURCE.has(args['--render-source']))
    throw Error('invalid_browser_qa_identity');
  if (!/^[A-Za-z0-9_-]{8,128}$/.test(args['--target-id'])) throw Error('invalid_cdp_target_id');
  const source = args['--render-source'];
  const target = new URL(args['--url']);
  if (source === 'local_static' ?
      !(target.protocol === 'file:' || (target.protocol === 'http:' && ['localhost','127.0.0.1'].includes(target.hostname))) :
      target.protocol !== 'https:') throw Error('render_source_url_conflict');
  if (source === 'authenticated_preview' &&
      !(['1','true'].includes(target.searchParams.get('preview')) ||
        /^[1-9]\d*$/.test(target.searchParams.get('preview_id') || '')))
    throw Error('authenticated_preview_url_required');
  const urlIds = ['p','page_id','preview_id'].flatMap(key => target.searchParams.getAll(key));
  if (urlIds.some(id => !/^[1-9]\d*$/.test(id) || Number(id) !== Number(args['--post-id'])))
    throw Error('browser_qa_url_post_id_mismatch');
  const endpoint = args['--endpoint'] || 'http://127.0.0.1:9222';
  const parsed = new URL(endpoint);
  if (parsed.protocol !== 'http:' || !['localhost', '127.0.0.1'].includes(parsed.hostname))
    throw Error('cdp_must_be_existing_local_browser');
  return endpoint;
}

class CDP {
  constructor(url) {
    this.next = 1; this.pending = new Map();
    this.socket = new WebSocket(url);
  }
  async connect() {
    await new Promise((resolveReady, reject) => {
      const timeout = setTimeout(() => reject(Error('cdp_connection_timeout')), 8000);
      this.socket.addEventListener('open', () => {clearTimeout(timeout); resolveReady();}, {once:true});
      this.socket.addEventListener('error', () => {clearTimeout(timeout); reject(Error('cdp_connection_failed'));}, {once:true});
    });
    this.socket.addEventListener('message', event => {
      const response = JSON.parse(event.data);
      if (response.id === undefined) return;
      const pending = this.pending.get(response.id);
      if (!pending) return;
      this.pending.delete(response.id);
      clearTimeout(pending.timer);
      response.error ? pending.reject(Error(response.error.message)) : pending.resolve(response.result);
    });
  }
  send(method, params={}) {
    const id = this.next++;
    return new Promise((resolveResult,reject) => {
      const timer = setTimeout(() => {this.pending.delete(id); reject(Error('cdp_command_timeout:'+method));}, 15000);
      this.pending.set(id, {resolve:resolveResult,reject,timer});
      this.socket.send(JSON.stringify({id, method, params}));
    });
  }
  async evaluate(fn, arg) {
    const expression = `(${fn.toString()})(${JSON.stringify(arg)})`;
    const result = await this.send('Runtime.evaluate', {
      expression, returnByValue:true, awaitPromise:true, userGesture:true});
    if (result.exceptionDetails) throw Error('browser_evaluation_exception');
    return result.result?.value;
  }
  close() {this.socket.close();}
}

const pause = (ms) => new Promise(resolveLater => setTimeout(resolveLater,ms));

function redactEvidenceUrl(url) {
  const parsed=new URL(url);
  const allow=new Set(['p','page_id','preview','preview_id','post_type']);
  for (const name of Array.from(parsed.searchParams.keys())) {
    if (!allow.has(name)) parsed.searchParams.delete(name);
  }
  parsed.hash='';
  return parsed.href;
}

function observePage() {
  const visible = (element) => Boolean(element && element.getClientRects().length &&
    getComputedStyle(element).display !== 'none' && getComputedStyle(element).visibility !== 'hidden');
  const main = document.documentElement;
  // A caller-supplied --post-id and --content-sha are insufficient evidence
  // that the CDP tab actually rendered that WordPress post. Record the post ID
  // independently advertised by the theme markup, when present.
  const bodyMatch = document.body?.className?.match(/(?:^|\s)postid-(\d+)(?:\s|$)/);
  const articleMatch = document.querySelector('.entry-content')?.closest('article[id^="post-"]')
    ?.id?.match(/^post-(\d+)$/);
  const shortlink = document.querySelector('link[rel="shortlink"]')?.href;
  const shortlinkId = shortlink ? new URL(shortlink).searchParams.get('p') : null;
  const postIds = [bodyMatch?.[1], articleMatch?.[1], shortlinkId]
    .filter(id => id && /^[1-9]\d*$/.test(id)).map(Number);
  const pagePostId = postIds.length && postIds.every(id => id === postIds[0]) ? postIds[0] : null;
  const tableContainers = Array.from(document.querySelectorAll('.bloguito-info-table'));
  const mobileCards = document.querySelectorAll('.bloguito-overview-mobile');
  const cardContainers = Array.from(mobileCards);
  let pairedCardIndex=0;
  const tables = tableContainers.map((el, i) => {
    const table = el.querySelector('table');
    const hasMobileCards=el.classList.contains('bloguito-overview-desktop');
    const cards = hasMobileCards ? cardContainers[pairedCardIndex++] : null;
    return {caption: table?.querySelector('caption')?.textContent?.trim() || '',
      headers: table?.querySelectorAll('thead th[scope="col"]').length || 0,
      rows: table?.querySelectorAll('tbody tr').length || 0,
      region: el.getAttribute('role') === 'region', focusable: el.tabIndex >= 0,
      visible: visible(el), has_mobile_cards: hasMobileCards,
      cards_visible: visible(cards), card_count: cards?.querySelectorAll('article').length ?? 0,
      client_width: el.clientWidth, scroll_width: el.scrollWidth, keyboard_scroll_delta: 0};
  });
  const toc = Array.from(document.querySelectorAll('.bloguito-toc a[href^="#"]'))
    .map(anchor => {
      const href = anchor.getAttribute('href');
      const id = decodeURIComponent(href.slice(1));
      const targets = Array.from(document.querySelectorAll('[id]')).filter(el => el.id === id);
      const previous = location.href;
      anchor.click();
      const matched = location.hash === href;
      history.replaceState(null, '', previous);
      return {href, target_found: targets.length > 0, target_unique: targets.length === 1,
        click_hash_matched: matched};
    });
  const ctas = Array.from(document.querySelectorAll('.bloguito-cta a[href],.bloguito-section-cta a[href]'))
    .map(anchor => ({href:anchor.href, target: anchor.target || '_self',
      click_navigation_verified:false, navigated_url:''}));
  const links=Array.from(document.querySelectorAll('.bloguito-article a[href]'))
    .map(a=>({href:a.href,valid:/^(https?:|#)/.test(a.getAttribute('href') || ''),
      target_existing: !(a.getAttribute('href') || '').startsWith('#') ||
        Array.from(document.querySelectorAll('[id]')).some(el=>el.id===decodeURIComponent(a.getAttribute('href').slice(1)))}));
  window.scrollTo(0,0);
  return {ready_state: document.readyState, page_post_id: pagePostId,
    inner_width: window.innerWidth,
    client_width: main.clientWidth,
    scroll_width: main.scrollWidth, toc:{links:toc}, tables, ctas,
    wp_theme_dom:Boolean(document.querySelector('.wp-site-blocks,.site-main,#primary,.entry-content') ||
      document.body?.classList.contains('single-post')),
    authenticated_dom:Boolean(document.getElementById('wpadminbar') ||
      document.body?.classList.contains('logged-in')),
    links,
    calculator_present:Boolean(document.querySelector('.calculator,[data-calculator],form input[type=number]')),
    calculator_cases:[]};
}

async function measureKeyboard(cdp, observed) {
  for (let index=0; index<observed.tables.length; index++) {
    const item = observed.tables[index];
    if (!item.visible || item.scroll_width <= item.client_width + 2) continue;
    const initial = await cdp.evaluate(i => {
      const el = document.querySelectorAll('.bloguito-info-table')[i];
      el.focus(); el.scrollLeft=0; return el.scrollLeft;
    },index);
    for (let k=0;k<5;k++) {
      await cdp.send('Input.dispatchKeyEvent', {type:'keyDown',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});
      await cdp.send('Input.dispatchKeyEvent', {type:'keyUp',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});
    }
    await pause(180);
    const moved = await cdp.evaluate(i => document.querySelectorAll('.bloguito-info-table')[i].scrollLeft,index);
    item.keyboard_scroll_delta = moved - initial;
  }
}

async function measureCalculator(cdp, config) {
  const result=[];
  for (const item of config.calculator_cases || []) {
    const tested = await cdp.evaluate(async item => {
      try {
        for (const input of item.inputs) {
          const el = document.querySelector(input.selector);
          if (!el || !('value' in el)) return {id:item.id,inputs_executed:false,result_observed:false,text:''};
          el.value=String(input.value);
          el.dispatchEvent(new Event('input',{bubbles:true}));
          el.dispatchEvent(new Event('change',{bubbles:true}));
        }
        if (item.trigger_selector) {
          const control = document.querySelector(item.trigger_selector);
          if (!control) return {id:item.id,inputs_executed:false,result_observed:false,text:''};
          control.click();
        }
        await new Promise(resolveLater=>setTimeout(resolveLater,250));
        const display=document.querySelector(item.result_selector);
        return {id:item.id,inputs_executed:true,result_observed:!!display,
          text:display?.textContent?.trim() || ''};
      } catch {return {id:item.id,inputs_executed:false,result_observed:false,text:''};}
    },item);
    result.push(tested);
  }
  return result;
}

async function checkCtaNavigation(cdp, observed, config, pageUrl) {
  for (const href of config.cta_targets || []) {
    const row=observed.ctas.find(link=>link.href === href);
    if (!row || row.target !== '_self') continue;
    await cdp.evaluate(href => {
      const a=Array.from(document.querySelectorAll('.bloguito-cta a[href],.bloguito-section-cta a[href]'))
        .find(item=>item.href === href && (!item.target || item.target === '_self'));
      if (a) a.click();
    },href);
    for (let attempt=0;attempt<20;attempt++) {
      await pause(150);
      let now;
      try {now=await cdp.evaluate(()=>location.href);} catch {continue;}
      if (now.split('#')[0] === href.split('#')[0]) {
        row.click_navigation_verified=true;
        row.navigated_url=now;
        break;
      }
    }
    await cdp.send('Page.navigate',{url:pageUrl});
    await waitReady(cdp);
  }
}

async function waitReady(cdp) {
  for (let attempt=0;attempt<40;attempt++) {
    try {
      if (await cdp.evaluate(()=>document.readyState) === 'complete') return;
    } catch { /* navigation replaced JS context */ }
    await pause(150);
  }
  throw Error('browser_page_load_timeout');
}

async function run() {
  const args=argumentsMap(process.argv.slice(2));
  const endpoint=validateArgs(args);
  // Windows PowerShell 5.1 frequently writes UTF-8 JSON with BOM. The BOM is
  // not evidence of a malformed QA plan; preserve all subsequent JSON checks.
  const config=args['--config'] ?
    JSON.parse((await readFile(args['--config'],'utf8')).replace(/^\uFEFF/,'')) : {};
  const scopes=config.required_scopes || [];
  if (!Array.isArray(scopes) || scopes.some(scope=>!SCOPES.has(scope))) throw Error('unknown_classifier_qa_scope');
  const targets=await (await fetch(endpoint+'/json/list')).json();
  const tab=targets.find(target=>target.type==='page' && target.id===args['--target-id']);
  if (!tab?.webSocketDebuggerUrl) throw Error('existing_cdp_target_not_found');
  const cdp=new CDP(tab.webSocketDebuggerUrl);
  if (!['127.0.0.1','localhost'].includes(new URL(tab.webSocketDebuggerUrl).hostname))
    throw Error('cdp_websocket_not_local');
  await cdp.connect();
  const directory=resolve(args['--output-dir']);
  try {
    await cdp.send('Page.enable'); await cdp.send('Runtime.enable');
    const expected=new URL(args['--url']);
    const existing=await cdp.evaluate(()=>location.href);
    if (existing.split('#')[0] !== expected.href.split('#')[0])
      throw Error('target_tab_url_mismatch_open_requested_url_in_existing_tab_first');
    await waitReady(cdp);
    const runId=randomUUID();
    const ua=await cdp.evaluate(()=>navigator.userAgent);
    const screens=[];
    for (const [width,height] of [[390,844],[1280,900]]) {
      await cdp.send('Emulation.setDeviceMetricsOverride', {
        width,height,deviceScaleFactor:1,mobile:width===390});
      await pause(250); await waitReady(cdp);
      const observation=await cdp.evaluate(observePage);
      await measureKeyboard(cdp,observation);
      observation.calculator_cases=await measureCalculator(cdp,config);
      if (config.allow_cta_navigation === true) {
        await checkCtaNavigation(cdp,observation,config,expected.href);
      }
      // A CTA may redirect the restored preview to login/error content. Never
      // capture it as a screenshot of the originally tested WordPress page.
      if ((await cdp.evaluate(()=>location.href)).split('#')[0] !== expected.href.split('#')[0])
        throw Error('browser_qa_url_changed_before_screenshot');
      const restored=await cdp.evaluate(()=>({
        ready_state:document.readyState,
        wp_theme_dom:Boolean(document.querySelector('.wp-site-blocks,.site-main,#primary,.entry-content') ||
          document.body?.classList.contains('single-post')),
        authenticated_dom:Boolean(document.getElementById('wpadminbar') ||
          document.body?.classList.contains('logged-in'))}));
      if (restored.ready_state!=='complete' ||
          (args['--render-source']!=='local_static' && !restored.wp_theme_dom) ||
          (args['--render-source']==='authenticated_preview' && !restored.authenticated_dom))
        throw Error('browser_qa_restored_preview_not_verified');
      // WCAG 1.4.10 reflow uses 320 CSS px; 390/2=195 is below that target
      // and may hit the logged-in WordPress admin bar's 240px min-width.
      // Keep the desktop half-width 640px check. Neither viewport override
      // establishes native browser zoom (which remains unverified).
      const reflowWidth = width === 390 ? 320 : Math.round(width / 2);
      await cdp.send('Emulation.setDeviceMetricsOverride', {
        width:reflowWidth,height,deviceScaleFactor:1,mobile:width===390});
      await pause(200);
      observation.reflow_simulated_viewport={kind:'css_viewport_reflow_not_native_zoom',
        width:reflowWidth,metrics:await cdp.evaluate(()=>({
          inner_width:window.innerWidth,client_width:document.documentElement.clientWidth,
          scroll_width:document.documentElement.scrollWidth}))};
      await cdp.send('Emulation.setDeviceMetricsOverride', {
        width,height,deviceScaleFactor:1,mobile:width===390});
      await pause(180);
      await cdp.evaluate(()=>window.scrollTo(0,0));
      const shot=await cdp.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
      const bytes=Buffer.from(shot.data,'base64');
      const filename=`${runId}-${width}.png`;
      await mkdir(directory,{recursive:true});
      await writeFile(join(directory,filename),bytes,{flag:'wx'});
      screens.push({viewport:{width,height},url:redactEvidenceUrl(expected.href),
        screenshot:{path:filename,sha256:createHash('sha256').update(bytes).digest('hex')},
        observation});
    }
    const evidence={schema:2,run_id:runId,post_id:Number(args['--post-id']),
      content_sha256:args['--content-sha'],render_source:args['--render-source'],
      url:redactEvidenceUrl(expected.href),executed_at:new Date().toISOString(),required_scopes:scopes,
      config:{cta_targets:config.cta_targets || [],calculator_cases:config.calculator_cases || []},
      execution:{engine:'existing_cdp_session',target_id:tab.id,user_agent:ua},screens};
    const path=join(directory,`${runId}-evidence.json`);
    await writeFile(path,JSON.stringify(evidence,null,2)+'\n',{flag:'wx'});
    process.stdout.write(JSON.stringify({evidence:path,run_id:runId,render_source:evidence.render_source,
      viewports:[390,1280],note:'Evidence recorded; independently validate before claiming QA PASS.'})+'\n');
  } finally {
    try {await cdp.send('Emulation.clearDeviceMetricsOverride');} catch {}
    cdp.close(); // never closes the tab or launches a browser
  }
}

run().catch(error=>{process.stderr.write('BROWSER_QA_BLOCKED: '+error.message+'\n');process.exitCode=1;});
