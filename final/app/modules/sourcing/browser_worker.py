from __future__ import annotations
import json
import os
import sys

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"

INTERESTING_HINTS = (
    "product", "products", "item", "items", "option", "options", "sku", "price",
    "smartstore", "brand.naver", "shopping", "commerce", "catalog", "detail"
)


def _collect_response(resp, blobs: list[dict], product_id: str = "", trace: list[dict] | None = None) -> None:
    try:
        ctype = (resp.headers.get("content-type") or "").lower()
        url = resp.url
        url_l = url.lower()
        is_jsonish = any(x in ctype for x in ("application/json", "text/json", "javascript", "text/plain", "text/html"))
        pid_in_url = bool(product_id and product_id in url)
        is_naver = "naver.com" in url_l or "naver.net" in url_l or "pstatic.net" in url_l
        if trace is not None and is_naver and len(trace) < 500:
            try:
                trace.append({"url": url[:800], "status": resp.status, "content_type": ctype[:120]})
            except Exception:
                pass
        if not is_naver and not any(h in url_l for h in INTERESTING_HINTS):
            return
        # V11: SmartStore frequently hides the requested product object behind an opaque
        # Naver endpoint whose URL contains neither /products/{id} nor a useful keyword.
        # Read Naver text/JSON responses and retain them only when the exact requested
        # product id occurs in the body (or the URL itself is anchored). This is still
        # data the browser normally received; no blocked endpoint is called directly.
        if not is_jsonish and not pid_in_url:
            return
        body = resp.text()
        if not body:
            return
        body_has_pid = bool(product_id and product_id in body)
        interesting_url = any(h in url_l for h in INTERESTING_HINTS)
        if not (pid_in_url or body_has_pid or (is_jsonish and interesting_url)):
            return
        if len(body) > 4_000_000:
            if not body_has_pid:
                return
            pos = body.find(product_id)
            lo=max(0,pos-1_500_000); hi=min(len(body),pos+1_500_000)
            body=body[lo:hi]
        blobs.append({"url": url, "content_type": ctype, "body": body[:4_000_000], "product_anchored": bool(pid_in_url or body_has_pid)})
    except Exception:
        return


def main() -> int:
    # Windows redirected stdout may otherwise use CP949 while the parent expects UTF-8.
    # Force a single wire encoding for JSON exchanged with the FastAPI process.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(sys.argv) != 2:
        return 2
    url = sys.argv[1]
    import re
    m_pid = re.search(r'/products/(\d+)', url)
    requested_product_id = m_pid.group(1) if m_pid else ''
    stage = 'start'
    diagnostics = {'stage': stage, 'url': url}
    try:
        stage = 'import_playwright'
        diagnostics['stage'] = stage
        from playwright.sync_api import sync_playwright
        stage = 'launch_browser'
        diagnostics['stage'] = stage
        with sync_playwright() as pw:
            # Prefer the user's installed stable Chrome on Windows. Fall back to bundled Chromium.
            browser = None
            launch_errors = []
            for channel in ("chrome", None):
                try:
                    kwargs = {"headless": True}
                    if channel:
                        kwargs["channel"] = channel
                    browser = pw.chromium.launch(**kwargs)
                    diagnostics['browser_channel'] = channel or 'chromium'
                    break
                except Exception as exc:
                    launch_errors.append(f"{channel or 'chromium'}:{type(exc).__name__}:{exc}")
            if browser is None:
                raise RuntimeError(" | ".join(launch_errors))

            stage = 'new_context'
            diagnostics['stage'] = stage
            context = browser.new_context(
                user_agent=USER_AGENT,
                locale="ko-KR",
                timezone_id="Asia/Seoul",
                viewport={"width": 1440, "height": 1000},
                extra_http_headers={
                    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Upgrade-Insecure-Requests": "1",
                },
                service_workers="block",
            )
            page = context.new_page()
            stage = 'navigate'
            diagnostics['stage'] = stage
            blobs: list[dict] = []
            network_trace: list[dict] = []
            page.on("response", lambda resp: _collect_response(resp, blobs, requested_product_id, network_trace))
            response = page.goto(url, wait_until="domcontentloaded", timeout=35000)
            diagnostics['http_status'] = response.status if response else None
            diagnostics['final_url'] = page.url
            # Allow client-rendered product state/XHR to complete.
            try:
                page.wait_for_load_state("networkidle", timeout=12000)
            except Exception:
                pass
            page.wait_for_timeout(2000)
            # V11 SmartStore stabilization: wait for the product id to appear in either
            # rendered HTML or an anchored network body. If the initial SPA shell never
            # mounts the product, retry the same public URL once in the same browser context.
            is_smartstore = 'smartstore.naver.com' in (page.url or url).lower()
            if is_smartstore and requested_product_id:
                def _product_seen():
                    try:
                        return requested_product_id in page.content() or any(b.get('product_anchored') for b in blobs)
                    except Exception:
                        return any(b.get('product_anchored') for b in blobs)
                for _ in range(8):
                    if _product_seen(): break
                    page.wait_for_timeout(750)
                if not _product_seen():
                    diagnostics['smartstore_retry'] = True
                    try:
                        page.reload(wait_until='domcontentloaded', timeout=35000)
                        try: page.wait_for_load_state('networkidle', timeout=12000)
                        except Exception: pass
                        page.wait_for_timeout(2500)
                    except Exception as exc:
                        diagnostics['smartstore_retry_error'] = f'{type(exc).__name__}: {exc}'
                diagnostics['smartstore_product_seen'] = _product_seen()

            # Extract the values the shopper can actually see on the rendered product page.
            # This runs inside the server-side Playwright page, so end users do NOT need a Chrome extension.
            # It intentionally limits itself to visible product UI and does not bypass login/CAPTCHA/access controls.
            stage = 'extract_rendered_dom'
            diagnostics['stage'] = stage
            # Naver lazily mounts parts of the purchase panel. Scroll through the page once
            # before extraction, then return to the top so price/gallery/option UI has mounted.
            try:
                page.evaluate("""async () => {
                  const sleep = ms => new Promise(r => setTimeout(r, ms));
                  for (const y of [350, 800, 1400, 2200, 0]) { window.scrollTo(0, y); await sleep(250); }
                }""")
                page.wait_for_timeout(500)
            except Exception:
                pass
            direct_payload = {}
            try:
                direct_payload = page.evaluate(r"""
                  async () => {
                    const clean = (t) => (t || '').replace(/\s+/g, ' ').trim();
                    const sleep = (ms) => new Promise(r => setTimeout(r, ms));
                    const uniq = (arr) => [...new Set((arr || []).filter(Boolean))];
                    const badText = (t) => !t || /에러페이지|시스템오류|로그인\s*[:|-]?\s*NAVER|접근이 제한|요청하신 페이지를 찾을 수 없습니다|편안한 휴식/i.test(t);
                    const wonValues = (t) => [...clean(t).matchAll(/([0-9][0-9,]{1,})\s*원/g)]
                      .map(m => Number(m[1].replace(/,/g, ''))).filter(n => Number.isFinite(n) && n >= 0);
                    const isSmartstore = location.hostname === 'smartstore.naver.com';
                    const isBrandstore = location.hostname === 'brand.naver.com';
                    const commonUiRe = /비밀번호\s*표시|비밀번호|로그인|삭제|스마트봇\s*상담|고객센터|언어선택|한국어|English|中文|日本語|Tiếng\s*Việt|NAVER|네이버\s*로그인/i;
                    function jsonLdProducts() {
                      const out=[];
                      for (const sc of document.querySelectorAll('script[type="application/ld+json"]')) {
                        try {
                          const data=JSON.parse(sc.textContent||'null');
                          const walk=(v)=>{
                            if(!v) return;
                            if(Array.isArray(v)){ v.forEach(walk); return; }
                            if(typeof v==='object'){
                              const typ=String(v['@type']||'').toLowerCase();
                              if(typ==='product' || (v.name && (v.offers || v.image || v.sku || v.productID))) out.push(v);
                              Object.values(v).forEach(walk);
                            }
                          };
                          walk(data);
                        } catch(e) {}
                      }
                      return out;
                    }
                    const structuredProducts = jsonLdProducts();

                    const visible = (el) => {
                      if (!el || !(el instanceof Element)) return false;
                      const s = getComputedStyle(el);
                      if (s.display === 'none' || s.visibility === 'hidden' || Number(s.opacity || 1) === 0) return false;
                      const r = el.getBoundingClientRect();
                      return r.width > 1 && r.height > 1 && r.bottom > 0 && r.right > 0;
                    };
                    const text = (el) => visible(el) ? clean(el.innerText || el.textContent || '') : '';

                    function findBuyArea() {
                      const controls = [...document.querySelectorAll('button,a,[role="button"]')].filter(visible);
                      const buy = controls.find(el => /^(?:구매하기|바로구매|장바구니)$/i.test(text(el))) ||
                                  controls.find(el => /구매하기|바로구매/.test(text(el)));
                      if (!buy) return null;
                      let cur = buy;
                      for (let i = 0; cur && i < 12; i++, cur = cur.parentElement) {
                        const r = cur.getBoundingClientRect();
                        const t = text(cur);
                        if (r.width >= 300 && r.width <= Math.max(980, innerWidth * .62) && r.height >= 300 &&
                            t.length >= 60 && t.length <= 30000 && /원|옵션|구매/.test(t)) return cur;
                      }
                      return buy.closest('main,section,article') || buy.parentElement;
                    }

                    function getProductName() {
                      // SmartStore: schema Product -> OG metadata -> visible DOM.
                      // Reject global NAVER controls such as password/language/help text.
                      if (isSmartstore) {
                        for (const obj of structuredProducts) {
                          const t=clean(obj?.name||'');
                          if(t && t.length>=5 && t.length<=220 && !badText(t) && !commonUiRe.test(t)) return t;
                        }
                        for (const sel of ['meta[property="og:title"]','meta[name="twitter:title"]','meta[name="title"]']) {
                          let t = clean(document.querySelector(sel)?.content || '');
                          t = t.replace(/\s*[:|\-]\s*(?:네이버\s*)?(?:스마트스토어|브랜드스토어|쇼핑).*$/i,'').trim();
                          if (t && t.length >= 5 && t.length <= 220 && !badText(t) && !commonUiRe.test(t)) return t;
                        }
                      }
                      const area = findBuyArea();
                      const root = area || document;
                      const els = [...root.querySelectorAll('h1,h2,h3,h4,strong,b,p,span,div')].filter(visible);
                      const ranked = [];
                      for (const el of els) {
                        const t = text(el);
                        if (!t || t.length < 5 || t.length > 220 || badText(t)) continue;
                        if (/^(?:NAVER|알림받기|검색|카테고리|더보기|쇼핑LIVE|베스트|신제품|전체상품|옵션\d*|무료배송|쿠폰 받기)$/i.test(t)) continue;
                        if (/적립|혜택|배송|리뷰|평점|멤버십|쿠폰|최대\s*할인|구매하기|장바구니|판매자 정보/.test(t)) continue;
                        const r = el.getBoundingClientRect();
                        const fs = parseFloat(getComputedStyle(el).fontSize || '0');
                        let score = 0;
                        if (area && area.contains(el)) score += 120;
                        if (r.left > innerWidth * .40) score += 35;
                        if (r.top > 80 && r.top < 520) score += 35;
                        if (/^H[1-3]$/.test(el.tagName)) score += 50;
                        if (fs >= 22) score += 35; else if (fs >= 17) score += 15;
                        if (t.length >= 10 && t.length <= 100) score += 30;
                        // Prefer leaf-ish nodes: large container text is usually the whole purchase panel.
                        const childText = [...el.children].map(c => text(c)).filter(Boolean).join(' ');
                        if (!childText || childText.length < t.length * .55) score += 20;
                        ranked.push({t, score});
                      }
                      ranked.sort((a,b) => b.score - a.score || a.t.length - b.t.length);
                      if (ranked[0] && ranked[0].score >= 80) return ranked[0].t;

                      // Meta is fallback only. Naver pages can use marketing copy in OG metadata.
                      for (const sel of ['meta[name="twitter:title"]','meta[property="og:title"]','meta[name="title"]']) {
                        let t = clean(document.querySelector(sel)?.content || '');
                        t = t.replace(/\s*[:|\-]\s*(?:네이버\s*)?(?:스마트스토어|브랜드스토어|쇼핑).*$/i,'').trim();
                        if (t && t.length >= 5 && t.length <= 220 && !badText(t)) return t;
                      }
                      return '';
                    }

                    function getStore() {
                      const parts = location.pathname.split('/').filter(Boolean);
                      const slug = parts[0] || '';
                      const storeUrl = slug ? `${location.origin}/${slug}` : location.origin;
                      const cands = [];
                      const add = (v, score) => {
                        const t = clean(v);
                        if (!t || t.length > 80 || commonUiRe.test(t) || /검색|알림받기|더보기|스토어 홈|톡톡|쇼핑LIVE|베스트|신제품|전체상품/i.test(t)) return;
                        cands.push({t, score});
                      };
                      document.querySelectorAll('header img,header h1,header h2,header strong,header a,[class*="store"] img,[class*="store"] h1,[class*="store"] h2,[class*="shop"] img,[class*="shop"] h1,[class*="shop"] h2').forEach(el => {
                        if (!visible(el)) return;
                        const r = el.getBoundingClientRect();
                        if (r.top > 220) return;
                        const alt = clean(el.getAttribute('alt') || '');
                        add(alt || el.getAttribute('aria-label') || text(el), alt ? 120 : 80);
                      });
                      // Page metadata/title are fallbacks only. Never use the URL slug as the visible store name.
                      for (const sel of ['meta[property="og:site_name"]','meta[name="application-name"]']) {
                        const t=clean(document.querySelector(sel)?.content || '');
                        if (t && !/^(?:NAVER|네이버|네이버쇼핑|스마트스토어|브랜드스토어|쇼핑)$/i.test(t)) add(t, 65);
                      }
                      if (isSmartstore) {
                        const ttl=clean(document.title || '');
                        const parts=ttl.split(/\s*[:|]\s*/).map(clean).filter(Boolean);
                        if(parts.length>=2){
                          const tail=parts[parts.length-1];
                          if(tail && !/^(?:NAVER|네이버|네이버쇼핑|스마트스토어|쇼핑)$/i.test(tail) && tail.toLowerCase()!==slug.toLowerCase()) add(tail, 55);
                        }
                      }
                      cands.sort((a,b)=>b.score-a.score || a.t.length-b.t.length);
                      const storeName = cands[0]?.t || '';
                      return {storeName, storeUrl};
                    }

                    function getPrice() {
                      if (isSmartstore) {
                        for (const obj of structuredProducts) {
                          const offers=Array.isArray(obj?.offers)?obj.offers:[obj?.offers];
                          for(const off of offers.filter(Boolean)){
                            for(const key of ['price','lowPrice','salePrice']){
                              const n=Number(String(off?.[key]??'').replace(/,/g,''));
                              if(Number.isFinite(n) && n>0) return n;
                            }
                          }
                        }
                      }
                      const buyArea = findBuyArea();
                      const area = buyArea || document;
                      const cands = [];
                      const scanRoot = (root, areaBonus=0) => root.querySelectorAll('strong,b,em,span,div,p,dd').forEach(el => {
                        if (!visible(el)) return;
                        const t = text(el);
                        if (!t || t.length > 160) return;
                        const vals = wonValues(t);
                        if (!vals.length) return;
                        const r = el.getBoundingClientRect();
                        const cs = getComputedStyle(el);
                        let score = 0;
                        if (/최대\s*할인가|최종\s*(?:혜택가|구매가)|쿠폰\s*적용가|결제\s*예상금액/.test(t)) score += 200;
                        else if (/할인가|판매가/.test(t)) score += 100;
                        if (/정가|소비자가|원가/.test(t)) score -= 140;
                        if ((cs.textDecorationLine || '').includes('line-through') || el.closest('s,del')) score -= 220;
                        const fs = parseFloat(cs.fontSize || '0');
                        if (fs >= 22) score += 50; else if (fs >= 16) score += 15;
                        if (r.top > 100 && r.top < 650) score += 25;
                        if (t.length <= 50) score += 25;
                        score += areaBonus;
                        vals.forEach((n,i)=>{ if (n > 0) cands.push({n,score:score+(i===0?5:0)}); });
                      });
                      scanRoot(area, buyArea ? 80 : 0);
                      // SmartStore layouts sometimes mount the price outside the purchase-button ancestor.
                      if (buyArea && isSmartstore) scanRoot(document, -35);
                      cands.sort((a,b)=>b.score-a.score);
                      if (cands[0]?.n > 0) return cands[0].n;

                      // Structured price exposed to the rendered shopper page. This is used only
                      // when it contains a positive product price, never as a fabricated zero.
                      for (const sel of [
                        'meta[property="product:price:amount"]','meta[property="og:price:amount"]',
                        'meta[itemprop="price"]','[itemprop="price"]'
                      ]) {
                        const el=document.querySelector(sel);
                        const raw=clean(el?.content || el?.getAttribute?.('content') || el?.textContent || '');
                        const n=Number(raw.replace(/[^0-9.]/g,''));
                        if(Number.isFinite(n)&&n>0) return n;
                      }
                      try {
                        for (const sc of document.querySelectorAll('script[type="application/ld+json"]')) {
                          const obj=JSON.parse(sc.textContent||'null');
                          const arr=Array.isArray(obj)?obj:[obj];
                          for(const x of arr){
                            const offers=x?.offers; const os=Array.isArray(offers)?offers:[offers];
                            for(const o of os){ const n=Number(o?.price || o?.lowPrice); if(Number.isFinite(n)&&n>0) return n; }
                          }
                        }
                      } catch {}
                      return null;
                    }

                    function getShippingFee() {
                      const area = findBuyArea() || document;
                      const els = [...area.querySelectorAll('div,li,dt,dd,p,span,strong')].filter(visible);
                      for (const el of els) {
                        const t = text(el);
                        if (!/배송/.test(t) || t.length > 600) continue;
                        if (/무료\s*배송|배송비\s*무료|무료\s*택배/.test(t)) return 0;
                        const m = t.match(/(?:배송비|기본배송비)[^0-9]{0,80}([0-9][0-9,]*)\s*원/);
                        if (m) return Number(m[1].replace(/,/g,''));
                      }
                      // Explicit shopper-visible shipping text elsewhere on the page is acceptable.
                      const bt=clean(document.body?.innerText||'');
                      const free=bt.match(/(?:배송비[^\n]{0,60}무료|무료\s*배송)/);
                      if(free) return 0;
                      const paid=bt.match(/(?:배송비|기본배송비)[^0-9\n]{0,80}([0-9][0-9,]*)\s*원/);
                      return paid ? Number(paid[1].replace(/,/g,'')) : null;
                    }

                    function normalizeImage(u) {
                      try {
                        if (!u) return '';
                        if (u.startsWith('//')) u='https:'+u;
                        const x=new URL(u, location.href);
                        if (!/pstatic\.net|naver\.net/i.test(x.hostname)) return '';
                        if (/logo|icon|banner|profile|sp_u_|favicon|ntm\.pstatic|static-resource|sprite|common|event|category|review|editor/i.test(x.href)) return '';
                        x.searchParams.delete('type');
                        return x.href;
                      } catch { return ''; }
                    }
                    const imageKey = (u) => { try { const x=new URL(u); return x.hostname+x.pathname; } catch { return u; } };
                    function getGalleryCount() {
                      const vals=[];
                      [...document.querySelectorAll('span,div,em,strong')].filter(visible).forEach(el=>{
                        const r=el.getBoundingClientRect();
                        if (r.left > innerWidth*.58 || r.top < 80 || r.top > 850) return;
                        const m=text(el).match(/(?:^|\s)(\d{1,2})\s*\/\s*(\d{1,2})(?:\s|$)/);
                        if (m) { const total=Number(m[2]); if(total>=1&&total<=40) vals.push(total); }
                      });
                      return vals.length ? Math.min(...vals) : null;
                    }
                    function getImages() {
                      if (isSmartstore) {
                        const schema=[];
                        for(const obj of structuredProducts){
                          const arr=Array.isArray(obj?.image)?obj.image:[obj?.image];
                          for(const raw of arr.filter(Boolean)){
                            const u=normalizeImage(typeof raw==='string'?raw:(raw?.url||raw?.contentUrl||''));
                            if(u && !schema.includes(u)) schema.push(u);
                          }
                        }
                        if(schema.length) return schema.slice(0,40);
                      }
                      const entries=[];
                      document.querySelectorAll('img').forEach(img=>{
                        if (!visible(img)) return;
                        const r=img.getBoundingClientRect();
                        const urls=[img.currentSrc,img.src, ...(img.srcset||'').split(',').map(x=>x.trim().split(/\s+/)[0])];
                        for(const raw of urls){ const u=normalizeImage(raw); if(u) entries.push({u,r,area:r.width*r.height}); }
                      });
                      const primary=entries.filter(x=>x.r.left<innerWidth*.55 && x.r.top>70 && x.r.top<850 && x.r.width>=220 && x.r.height>=220)
                        .sort((a,b)=>b.area-a.area)[0];
                      if (!primary) {
                        const og=normalizeImage(document.querySelector('meta[property="og:image"]')?.content || '');
                        return og ? [og] : [];
                      }
                      const out=[]; const seen=new Set();
                      const add=(u)=>{const k=imageKey(u); if(u&&!seen.has(k)){seen.add(k);out.push(u);}};
                      add(primary.u);
                      const p=primary.r;
                      entries.filter(x=>x.r.left<innerWidth*.58 && x.r.top>=p.top-120 && x.r.top<=p.bottom+220 &&
                          x.r.width>=28 && x.r.height>=28 && x.r.width<=240 && x.r.height<=240)
                        .sort((a,b)=>a.r.top-b.r.top || a.r.left-b.r.left).forEach(x=>add(x.u));
                      const count=getGalleryCount();
                      return out.slice(0, count || 40);
                    }

                    function triggerText(el){ return clean(el.getAttribute('aria-label') || el.innerText || el.textContent || ''); }
                    function isOptionTrigger(el){
                      const t=triggerText(el);
                      if(!t || t.length>100) return false;
                      return /^(?:옵션\s*\d+|옵션\s*선택.*|색상|사이즈|용량|수량|모델|길이|종류|규격|구성|타입|제품선택|상품선택)(?:\s*\(필수\))?$/i.test(t) || /옵션.*선택|선택.*옵션|필수.*선택/.test(t);
                    }
                    function visibleOptionValues(trigger){
                      const tr=trigger.getBoundingClientRect(); const vals=[];
                      const candidates=[...document.querySelectorAll('[role="option"],[role="menuitem"],[role="listbox"] li,[role="menu"] li,ul li,ol li')].filter(visible);
                      for(const el of candidates){
                        const r=el.getBoundingClientRect(); const t=text(el);
                        if(!t || t.length>240 || /옵션\s*선택|선택해주세요|품절상품 제외|구매하기|장바구니/.test(t)) continue;
                        const sameColumn=Math.abs(r.left-tr.left)<Math.max(280,tr.width*.9)||(r.left<=tr.right+100&&r.right>=tr.left-100);
                        const near=r.top>=tr.top-100&&r.top<=tr.bottom+800;
                        if(sameColumn&&near) vals.push(t);
                      }
                      return uniq(vals);
                    }
                    async function getOptionGroups(){
                      const area=findBuyArea() || document;
                      const groups=[]; const seen=new Set();
                      const optionRoot = area || document;
                      const all=[...optionRoot.querySelectorAll('select,button,[role="button"],[role="combobox"],[aria-haspopup="listbox"]')].filter(el=>{
                        if(!visible(el)) return false;
                        const tt=triggerText(el);
                        if(commonUiRe.test(tt)) return false;
                        if(el.tagName==='SELECT'){
                          const vals=[...el.options].map(o=>clean(o.textContent)).join(' ');
                          if(commonUiRe.test(vals) || /한국어|English|中文|日本語|Tiếng/i.test(vals)) return false;
                          return /옵션|색상|사이즈|용량|수량|모델|길이|종류|규격|구성|타입|제품|상품/.test(clean(el.getAttribute('aria-label')||'')) || !isSmartstore;
                        }
                        return isOptionTrigger(el) || /옵션.*선택|선택.*옵션|색상|사이즈|용량|모델|종류|규격|구성|타입/.test(tt);
                      }).slice(0,40);
                      for(let i=0;i<all.length&&i<30;i++){
                        const tr=all[i];
                        let name=tr.tagName==='SELECT'?clean(tr.getAttribute('aria-label')||`옵션${i+1}`):triggerText(tr).replace(/\(필수\)/g,'').trim();
                        if(!name||name.length>80) name=`옵션${i+1}`;
                        if(seen.has(name)) continue;
                        let values=[];
                        if(tr.tagName==='SELECT'){
                          values=[...tr.options].map(o=>clean(o.textContent)).filter(v=>v&&!/선택/.test(v));
                        } else {
                          try{ tr.scrollIntoView({block:'center'}); await sleep(120); tr.click(); }catch{}
                          await sleep(550);
                          values=visibleOptionValues(tr);
                          if(!values.length){
                            let box=tr.parentElement;
                            for(let d=0;box&&d<5&&!values.length;d++,box=box.parentElement){
                              values=uniq([...box.querySelectorAll('button,label,[role="option"],li')].filter(visible).map(text)
                                .filter(v=>v&&v!==triggerText(tr)&&v.length<=240&&!/구매하기|장바구니|선물하기|톡톡문의|찜하기/.test(v)));
                            }
                          }
                          try{ tr.click(); }catch{}
                          await sleep(100);
                        }
                        values=uniq(values.map(clean).filter(v=>v&&!/^(?:선택|옵션\s*선택|선택해주세요)$/i.test(v))).slice(0,300);
                        if(values.length){ groups.push({name,values}); seen.add(name); }
                      }
                      return groups;
                    }

                    function getAvailability(){
                      const area=findBuyArea() || document; const t=clean(area.innerText||'');
                      if(/판매중지|일시품절|품절|구매할 수 없는 상품/.test(t)) return 'OUT_OF_STOCK';
                      if(/구매하기|장바구니|바로구매/.test(t)) return 'AVAILABLE';
                      return 'UNKNOWN';
                    }

                    const {storeName,storeUrl}=getStore();
                    const optionGroups=await getOptionGroups();
                    return {
                      pageType: isBrandstore ? 'NAVER_BRANDSTORE' : (isSmartstore ? 'NAVER_SMARTSTORE' : 'NAVER_OTHER'),
                      productName:getProductName(),
                      storeName, storeUrl,
                      price:getPrice(),
                      shippingFee:getShippingFee(),
                      imageUrls:getImages(),
                      optionGroups,
                      availability:getAvailability()
                    };
                  }
                """)

            except Exception as exc:
                diagnostics['direct_error'] = f'{type(exc).__name__}: {exc}'

            # V10 SmartStore frame recovery.
            # Some ordinary smartstore pages keep the actual product document in a child
            # frame while the top document contains only NAVER/common controls.  Inspect
            # each Naver child frame and fill only fields the main rendered document missed.
            # This is still the same shopper-visible page; no access control is bypassed.
            if 'smartstore.naver.com' in url.lower():
                frame_results = []
                frame_urls = []
                frame_script_count = 0
                frame_probe_js = r"""
                async () => {
                  const clean=t=>(t||'').replace(/\s+/g,' ').trim();
                  const visible=el=>{if(!el||!(el instanceof Element))return false;const s=getComputedStyle(el);if(s.display==='none'||s.visibility==='hidden'||Number(s.opacity||1)===0)return false;const r=el.getBoundingClientRect();return r.width>1&&r.height>1;};
                  const txt=el=>visible(el)?clean(el.innerText||el.textContent||''):'';
                  const bad=/비밀번호\s*표시|비밀번호|로그인|삭제|스마트봇\s*상담|고객센터|언어선택|한국어|English|中文|日本語|Tiếng\s*Việt|NAVER\s*로그인|네이버\s*로그인/i;
                  const badStore=/^(?:NAVER|네이버|네이버쇼핑|스마트스토어|브랜드스토어|쇼핑)$/i;
                  const productObjs=[];
                  for(const sc of document.querySelectorAll('script[type="application/ld+json"]')){
                    try{const d=JSON.parse(sc.textContent||'null');const walk=v=>{if(!v)return;if(Array.isArray(v)){v.forEach(walk);return;}if(typeof v==='object'){const typ=String(v['@type']||'').toLowerCase();if(typ==='product'||(v.name&&(v.offers||v.image||v.sku||v.productID)))productObjs.push(v);Object.values(v).forEach(walk);}};walk(d);}catch{}
                  }
                  let productName='';
                  for(const o of productObjs){const t=clean(o?.name||'');if(t.length>=5&&t.length<=220&&!bad.test(t)){productName=t;break;}}
                  if(!productName){for(const sel of ['meta[property="og:title"]','meta[name="twitter:title"]','meta[name="title"]']){let t=clean(document.querySelector(sel)?.content||'');t=t.replace(/\s*[:|\-]\s*(?:네이버\s*)?(?:스마트스토어|브랜드스토어|쇼핑).*$/i,'').trim();if(t.length>=5&&t.length<=220&&!bad.test(t)){productName=t;break;}}}
                  if(!productName){
                    const c=[...document.querySelectorAll('h1,h2,h3,strong')].filter(visible).map(el=>({t:txt(el),r:el.getBoundingClientRect(),fs:parseFloat(getComputedStyle(el).fontSize||'0')})).filter(x=>x.t.length>=5&&x.t.length<=220&&!bad.test(x.t));
                    c.sort((a,b)=>((b.r.top<650?30:0)+(b.fs>=20?30:0))-((a.r.top<650?30:0)+(a.fs>=20?30:0))||a.t.length-b.t.length); if(c[0])productName=c[0].t;
                  }
                  let storeName='';
                  const storeC=[]; const addStore=(v,score)=>{const t=clean(v);if(t&&t.length<=80&&!bad.test(t)&&!badStore.test(t))storeC.push({t,score});};
                  document.querySelectorAll('header img,header h1,header h2,header strong,header a,[class*="store"] img,[class*="store"] h1,[class*="store"] h2,[class*="shop"] img,[class*="shop"] h1,[class*="shop"] h2').forEach(el=>{if(!visible(el))return;const r=el.getBoundingClientRect();if(r.top>260)return;addStore(el.getAttribute('alt')||el.getAttribute('aria-label')||txt(el),el.getAttribute('alt')?120:80);});
                  const site=clean(document.querySelector('meta[property="og:site_name"]')?.content||''); addStore(site,60); storeC.sort((a,b)=>b.score-a.score||a.t.length-b.t.length); if(storeC[0])storeName=storeC[0].t;
                  let price=null;
                  for(const o of productObjs){const offers=Array.isArray(o?.offers)?o.offers:[o?.offers];for(const off of offers.filter(Boolean)){for(const k of ['price','lowPrice','salePrice']){const n=Number(String(off?.[k]??'').replace(/,/g,''));if(Number.isFinite(n)&&n>0){price=n;break;}}if(price)break;}if(price)break;}
                  if(!price){for(const sel of ['meta[property="product:price:amount"]','meta[property="og:price:amount"]','meta[itemprop="price"]','[itemprop="price"]']){const el=document.querySelector(sel);const n=Number(clean(el?.content||el?.getAttribute?.('content')||el?.textContent||'').replace(/[^0-9.]/g,''));if(Number.isFinite(n)&&n>0){price=n;break;}}}
                  let shippingFee=null; const body=clean(document.body?.innerText||''); if(/무료\s*배송/.test(body))shippingFee=0; else {const m=body.match(/(?:배송비|기본배송비)[^0-9]{0,30}([0-9][0-9,]*)\s*원/);if(m)shippingFee=Number(m[1].replace(/,/g,''));}
                  const imageUrls=[]; const addImg=u=>{u=clean(u);if(!u)return;if(u.startsWith('//'))u='https:'+u;if(!/^https?:\/\//.test(u)||/favicon|logo|sp_|noimage|no_image/i.test(u))return;if(!imageUrls.includes(u))imageUrls.push(u);};
                  for(const o of productObjs){const im=o?.image;for(const x of (Array.isArray(im)?im:[im])){if(typeof x==='string')addImg(x);else if(x&&typeof x==='object')addImg(x.url||x.contentUrl||x.imageUrl);}}
                  addImg(document.querySelector('meta[property="og:image"]')?.content||'');
                  if(imageUrls.length<=1){document.querySelectorAll('img').forEach(el=>{if(!visible(el))return;const r=el.getBoundingClientRect();if(r.width<120||r.height<120||r.top>900)return;addImg(el.currentSrc||el.src||'');});}
                  const optionGroups=[];
                  for(const sel of [...document.querySelectorAll('select')].filter(visible)){
                    const label=clean(sel.getAttribute('aria-label')||sel.closest('label')?.innerText||'옵션');
                    const vals=[...sel.options].map(o=>clean(o.textContent)).filter(v=>v&&!/선택/.test(v)&&!bad.test(v));
                    if(vals.length&& !bad.test(label)) optionGroups.push({name:label||'옵션',values:[...new Set(vals)]});
                  }
                  if(!optionGroups.length){
                    const triggers=[...document.querySelectorAll('button,[role="button"],[role="combobox"],[aria-haspopup="listbox"]')].filter(visible).filter(el=>/옵션|색상|사이즈|용량|모델|종류|규격|구성|타입/.test(txt(el))&&!bad.test(txt(el))).slice(0,20);
                    for(let i=0;i<triggers.length;i++){const tr=triggers[i],name=txt(tr).replace(/\(필수\)/g,'').trim()||`옵션${i+1}`;try{tr.click();await new Promise(r=>setTimeout(r,350));}catch{} const vals=[...document.querySelectorAll('[role="option"],[role="listbox"] li,ul li')].filter(visible).map(txt).filter(v=>v&&v.length<=180&&!bad.test(v)&&!/선택해주세요|구매하기|장바구니/.test(v));if(vals.length)optionGroups.push({name,values:[...new Set(vals)]});try{tr.click();}catch{}}
                  }
                  let availability='UNKNOWN'; if(/판매중지|일시품절|품절|구매할 수 없는 상품/.test(body))availability='OUT_OF_STOCK'; else if(/구매하기|장바구니|바로구매/.test(body))availability='AVAILABLE';
                  return {productName,storeName,price,shippingFee,imageUrls:imageUrls.slice(0,30),optionGroups:optionGroups.slice(0,30),availability,frameUrl:location.href,title:document.title};
                }
                """
                for fr in page.frames:
                    if fr == page.main_frame:
                        continue
                    try:
                        frame_urls.append(fr.url)
                        host = fr.url.lower()
                        if not any(x in host for x in ('naver.com','naver.net')):
                            continue
                        fp = fr.evaluate(frame_probe_js)
                        if isinstance(fp, dict):
                            frame_results.append(fp)
                        # Also preserve exact-product inline frame state for the anchored parser.
                        if requested_product_id:
                            scripts = fr.evaluate("""(pid)=>[...document.scripts].map(s=>s.textContent||'').filter(t=>t&&t.length<2000000&&t.includes(pid)).slice(0,10)""", requested_product_id)
                            for j, body in enumerate(scripts or []):
                                blobs.append({'url': f'frame-inline://{requested_product_id}/{len(frame_results)}/{j}', 'content_type': 'application/json-ish', 'body': body})
                                frame_script_count += 1
                    except Exception:
                        continue

                def _valid_text(v):
                    return isinstance(v, str) and bool(v.strip())
                def _fill_from_frame(base, fp):
                    if not isinstance(base, dict):
                        base = {}
                    if not _valid_text(base.get('productName')) and _valid_text(fp.get('productName')):
                        base['productName'] = fp.get('productName')
                    if not _valid_text(base.get('storeName')) and _valid_text(fp.get('storeName')):
                        base['storeName'] = fp.get('storeName')
                    if base.get('price') is None and isinstance(fp.get('price'), (int, float)) and fp.get('price') > 0:
                        base['price'] = fp.get('price')
                    if base.get('shippingFee') is None and isinstance(fp.get('shippingFee'), (int, float)) and fp.get('shippingFee') >= 0:
                        base['shippingFee'] = fp.get('shippingFee')
                    if not (base.get('imageUrls') or []) and fp.get('imageUrls'):
                        base['imageUrls'] = fp.get('imageUrls')
                    if not (base.get('optionGroups') or []) and fp.get('optionGroups'):
                        base['optionGroups'] = fp.get('optionGroups')
                    if str(base.get('availability') or 'UNKNOWN').upper() == 'UNKNOWN' and str(fp.get('availability') or '').upper() in {'AVAILABLE','OUT_OF_STOCK'}:
                        base['availability'] = fp.get('availability')
                    return base

                for fp in frame_results:
                    direct_payload = _fill_from_frame(direct_payload, fp)
                diagnostics['smartstore_frame_count'] = len(page.frames)
                diagnostics['smartstore_frame_urls'] = frame_urls[:20]
                diagnostics['smartstore_frame_probe_count'] = len(frame_results)
                diagnostics['smartstore_frame_product_script_count'] = frame_script_count

            # V7: capture inline state only when it is anchored to the exact product id.
            # This is much safer than scanning every script/name/price on the page and helps
            # recover product JSON that Naver embeds instead of fetching as a separate XHR.
            try:
                inline_states = page.evaluate(
                    """(pid) => {
                      if (!pid) return [];
                      const out=[];
                      for (const sc of document.scripts) {
                        const t=sc.textContent||'';
                        if (!t || t.length>2000000 || !t.includes(pid)) continue;
                        if (!/[{\[]/.test(t)) continue;
                        out.push(t.slice(0,2000000));
                        if (out.length>=20) break;
                      }
                      return out;
                    }""", requested_product_id
                )
                for i, body in enumerate(inline_states or []):
                    blobs.append({"url": f"inline://naver-product-state/{requested_product_id}/{i}", "content_type": "application/json-ish", "body": body})
                diagnostics['inline_product_state_count'] = len(inline_states or [])
            except Exception as exc:
                diagnostics['inline_state_error'] = f'{type(exc).__name__}: {exc}'

            # Also capture common page-global JSON states that are already available to the browser.
            globals_payload = page.evaluate("""
                () => {
                  const out = {};
                  const names = ['__NEXT_DATA__','__APOLLO_STATE__','__INITIAL_STATE__','__PRELOADED_STATE__','__NUXT__'];
                  for (const n of names) {
                    try { if (window[n] != null) out[n] = window[n]; } catch (e) {}
                  }
                  for (const id of ['__NEXT_DATA__','__INITIAL_STATE__','__APOLLO_STATE__']) {
                    try {
                      const el = document.getElementById(id);
                      if (el && el.textContent && el.textContent.length < 3000000) out[id + '_SCRIPT'] = el.textContent;
                    } catch (e) {}
                  }
                  return out;
                }
            """)
            if direct_payload and isinstance(direct_payload, dict):
                globals_payload['__B2B_DIRECT__'] = direct_payload
            diagnostics['stage'] = 'complete'
            diagnostics['title'] = page.title()
            diagnostics['network_blob_count'] = len(blobs)
            diagnostics['product_anchored_blob_count'] = sum(1 for b in blobs if b.get('product_anchored'))
            diagnostics['naver_response_trace_count'] = len(network_trace)
            diagnostics['naver_response_trace'] = network_trace[-120:]
            diagnostics['direct_fields'] = {
                'product_name': bool(direct_payload.get('productName')) if isinstance(direct_payload, dict) else False,
                'store_name': bool(direct_payload.get('storeName')) if isinstance(direct_payload, dict) else False,
                'price': direct_payload.get('price') is not None if isinstance(direct_payload, dict) else False,
                'shipping': direct_payload.get('shippingFee') is not None if isinstance(direct_payload, dict) else False,
                'images': len(direct_payload.get('imageUrls') or []) if isinstance(direct_payload, dict) else 0,
                'option_groups': len(direct_payload.get('optionGroups') or []) if isinstance(direct_payload, dict) else 0,
            }

            payload = {
                "ok": True,
                "final_url": page.url,
                "status": response.status if response else 200,
                "title": page.title(),
                "html": page.content()[:8_000_000],
                "network_blobs": blobs[-80:],
                "globals": globals_payload,
                "diagnostics": diagnostics,
            }
            context.close()
            browser.close()
        sys.stdout.write(json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception as exc:
        diagnostics['stage'] = stage
        diagnostics['error'] = f'{type(exc).__name__}: {exc}'
        sys.stdout.write(json.dumps({'ok': False, 'diagnostics': diagnostics}, ensure_ascii=False))
        return 0

if __name__ == "__main__":
    raise SystemExit(main())
