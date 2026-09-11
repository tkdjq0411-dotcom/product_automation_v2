(()=>{
if(window.__B2B_CAPTURE_V79__)return;
window.__B2B_CAPTURE_V79__=true;
try{chrome.runtime.sendMessage({type:'B2B_HELPER_HEARTBEAT'},()=>{});}catch(_){}
const BAD=/비밀번호\s*표시|스마트봇|고객센터|언어선택|로그인|장바구니|English|中文|日本語|Tiếng Việt|본문으로\s*바로가기|콘텐츠로\s*바로가기|톡톡문의|찜하기|리뷰|구매평|문의|혜택|적립|쿠폰/i;
// Hard safety rail: the helper may open option/gallery controls, but it must NEVER
// activate shopper actions while collecting.  This guard is enabled only during an
// explicit B2B capture session and blocks both accidental selector matches and page handlers.
const PROTECTED_ACTION_RE=/(?:장바구니|구매하기|바로\s*구매|선물하기|찜하기|톡톡\s*문의|리뷰|구매평|상품평|문의하기|문의\s*하기|재구매|장바구니\s*담기)/i;
function actionableAncestor(el){
  try{return el?.closest?.('button,a,[role=\"button\"],[role=\"link\"],input[type=\"button\"],input[type=\"submit\"]')||el}catch{return el}
}
function protectedActionTarget(el){
  const a=actionableAncestor(el); if(!a)return false;
  const label=[a.innerText,a.textContent,a.getAttribute?.('aria-label'),a.getAttribute?.('title'),a.getAttribute?.('value')].filter(Boolean).join(' ').replace(/\s+/g,' ').trim();
  let href=''; try{href=String(a.href||a.getAttribute?.('href')||'')}catch{}
  return PROTECTED_ACTION_RE.test(label)||/(?:cart|basket|checkout|purchase|buy|gift|review|talk|inquiry)/i.test(href);
}
function installShopperActionGuard(){
  const handler=(ev)=>{
    const option=ev.target?.closest?.('[role="option"]');
    const soldOption=option&&/품절|판매\s*중지|구매\s*불가/.test(option.textContent||'');
    if(!soldOption&&!protectedActionTarget(ev.target))return;
    ev.preventDefault(); ev.stopPropagation(); ev.stopImmediatePropagation();
    console.warn('[B2B Helper] blocked shopper action during capture:',triggerText(actionableAncestor(ev.target)));
  };
  const events=['pointerdown','mousedown','mouseup','click'];
  for(const type of events)document.addEventListener(type,handler,true);
  return ()=>{for(const type of events)document.removeEventListener(type,handler,true)};
}

// V38: keep the browser parked in the product purchase header while collecting.
// The helper must never scroll down the detail/review area just to discover options.
function installCaptureViewportGuard(){
  // SmartStore links can restore an old scroll position or carry a hash. The sourcing
  // collector always works from the top purchase panel, so park there once, then lock it.
  try{history.scrollRestoration='manual'}catch{}
  try{window.scrollTo({left:0,top:0,behavior:'instant'})}catch{try{window.scrollTo(0,0)}catch{}}
  const lockX=0, lockY=0;
  let restoring=false;
  const restore=()=>{
    if(restoring)return;
    if(Math.abs(window.scrollX-lockX)<2&&Math.abs(window.scrollY-lockY)<2)return;
    restoring=true;
    try{window.scrollTo({left:lockX,top:lockY,behavior:'instant'})}catch{try{window.scrollTo(lockX,lockY)}catch{}}
    requestAnimationFrame(()=>{restoring=false});
  };
  const onScroll=()=>restore();
  window.addEventListener('scroll',onScroll,{capture:true,passive:true});
  // Some controls use focus() internally and the browser may scroll the focused node.
  const onFocus=(ev)=>{
    const el=ev.target;
    if(!el)return;
    requestAnimationFrame(restore);
  };
  document.addEventListener('focusin',onFocus,true);
  return ()=>{
    window.removeEventListener('scroll',onScroll,true);
    document.removeEventListener('focusin',onFocus,true);
    restore();
  };
}
const text=e=>(e?.textContent||'').replace(/\s+/g,' ').trim();
const uniq=a=>[...new Set(a.filter(Boolean))];
let optionWorkDeadline=Infinity;
let optionHardDeadline=Infinity;
let optionDiagnostics=null;
// V2.61.11: always retain a live snapshot of completed DFS leaves so a hard timeout
// can still be saved to B2B instead of discarding everything collected so far.
let __b2bPartialVariants=[];
let stopRequested=false, collectionIncomplete=false, knownOptionDepth=0, schemaDepth=0;
let expectedPaths=[],sourceCombinationRecords=[];
function stopped(){
  if(Date.now()>=optionWorkDeadline){stopRequested=true;collectionIncomplete=true;}
  return stopRequested;
}
function extendOptionWork(reason,extraMs=15000){
  // V2.61.9: strict 3-minute ceiling. Progress may be logged, but never extend the deadline.
  if(!Number.isFinite(optionHardDeadline))return;
  diag('option_progress',{reason,remaining_ms:Math.max(0,optionWorkDeadline-Date.now())});
}
function diag(event,data={}){
  if(!optionDiagnostics)return;
  optionDiagnostics.events.push({event,elapsed_ms:Date.now()-optionDiagnostics.started_at,...data});
  if(optionDiagnostics.events.length>400)optionDiagnostics.events.shift();
}
function diagnosticNode(el){
  if(!el)return null;
  const r=el.getBoundingClientRect?.()||{};
  return {
    tag:String(el.tagName||'').toLowerCase(),
    role:el.getAttribute?.('role')||'',
    aria_expanded:el.getAttribute?.('aria-expanded')||'',
    text:String(el.innerText||el.textContent||'').replace(/\s+/g,' ').trim().slice(0,300),
    rect:{left:Math.round(r.left||0),top:Math.round(r.top||0),width:Math.round(r.width||0),height:Math.round(r.height||0)},
    html:String(el.outerHTML||'').slice(0,1200)
  };
}
function visiblePurchasePriceCandidates(){
  const out=[];
  for(const el of document.querySelectorAll('strong,b,em,span,div,p')){
    if(!visible(el))continue;
    const r=el.getBoundingClientRect(),raw=String(el.innerText||el.textContent||'').replace(/\s+/g,' ').trim();
    if(r.left<innerWidth*.40||r.width<10||r.width>720||r.height<8||r.height>100||raw.length>100)continue;
    if(!/[+-]?\s*[\d,]+\s*원/.test(raw))continue;
    out.push({text:raw.slice(0,100),left:Math.round(r.left),top:Math.round(r.top)});
    if(out.length>=30)break;
  }
  return out;
}
const sleep=ms=>new Promise(resolve=>{
  if(stopped()){resolve();return;}
  setTimeout(()=>{stopped();resolve();},Math.min(ms,Math.max(0,optionWorkDeadline-Date.now())));
});
const productIdFromUrl=()=>{const m=location.pathname.match(/\/products\/(\d+)/i);return m?m[1]:''};
function requestMainProbe(timeout=5000){
  return new Promise(resolve=>{
    const requestId='b2b-'+Date.now()+'-'+Math.random().toString(36).slice(2);
    let done=false;
    const finish=v=>{if(done)return;done=true;window.removeEventListener('message',onMsg);clearTimeout(timer);resolve(v||{images:[],optionGroups:[],additionalOptionGroups:[],debug:{}})};
    const onMsg=ev=>{
      const m=ev.data;
      if(!m||m.type!=='B2B_MAIN_PROBE_RESPONSE'||m.requestId!==requestId)return;
      finish(m.result||{images:[],optionGroups:[],additionalOptionGroups:[],error:m.error||''});
    };
    window.addEventListener('message',onMsg);
    const timer=setTimeout(()=>finish(null),timeout);
    window.postMessage({type:'B2B_MAIN_PROBE_REQUEST',requestId,productId:productIdFromUrl()},'*');
  });
}
function requestOptionPriceProbe(timeout=5000){
  return new Promise(resolve=>{
    const requestId='b2b-price-'+Date.now()+'-'+Math.random().toString(36).slice(2);
    let done=false;
    const finish=v=>{if(done)return;done=true;window.removeEventListener('message',onMsg);clearTimeout(timer);resolve(Array.isArray(v)?v:[])};
    const onMsg=ev=>{const m=ev.data;if(m?.type==='B2B_OPTION_PRICE_RESPONSE'&&m.requestId===requestId)finish(m.entries)};
    window.addEventListener('message',onMsg);
    const timer=setTimeout(()=>finish([]),timeout);
    window.postMessage({type:'B2B_OPTION_PRICE_REQUEST',requestId,productId:productIdFromUrl()},'*');
  });
}
function mergeOptionGroups(primary,secondary){
  const out=[];const seen=new Set();
  for(const g of [...(primary||[]),...(secondary||[])]){
    const name=String(g?.name||'').replace(/\s+/g,' ').trim();
    const values=uniq((g?.values||[]).map(v=>String(v||'').replace(/\s+/g,' ').trim()).filter(optionValueOK));
    if(!values.length)continue;
    const key=(name||'')+'|'+values.join('|');if(seen.has(key))continue;seen.add(key);out.push({name:name||`옵션${out.length+1}`,values});
    if(out.length>=30)break;
  }
  return out;
}
const visible=e=>{if(!e)return false;const r=e.getBoundingClientRect();const s=getComputedStyle(e);return r.width>1&&r.height>1&&s.display!=='none'&&s.visibility!=='hidden'&&Number(s.opacity||1)>0};
const meta=(...sels)=>{for(const s of sels){const e=document.querySelector(s);const v=e?.content||e?.getAttribute?.('content');if(v)return v.trim()}return ''};
function cleanName(v){return String(v||'').replace(/\s+/g,' ').replace(/\s*[:|]\s*네이버.*$/i,'').trim()}
function productName(store=''){
  const stripStore=(v)=>{
    let x=cleanName(v);
    const st=String(store||'').replace(/[.*+?^${}()|[\]\\]/g,'\\$&').trim();
    if(st){
      x=x.replace(new RegExp(`\\s*[:|\\-]\\s*(?:네이버[- ]*)?${st}\\s*$`,'i'),'').trim();
    }
    x=x.replace(/\\s*[:|\\-]\\s*(?:네이버\\s*)?(?:스마트스토어|브랜드스토어|쇼핑)\\s*$/i,'').trim();
    return x;
  };
  const badTitle=(v)=>!v||v.length<5||v.length>250||BAD.test(v)||/스토어등급|프리미엄|도움말|오늘\\s*[\\d,]+|전체\\s*[\\d,]+|판매자\\s*등급|찜\\s*[\\d,]+|알림받기/i.test(v);

  // Product titles must be preserved verbatim (apart from whitespace/store suffix cleanup).
  // SmartStore can expose a SHORT og:title while the visible purchase heading/document title
  // contains the complete seller title. Never return the first candidate blindly: gather all
  // trustworthy title sources and keep the longest compatible original title.
  const titleCandidates=[];
  const addTitle=(raw)=>{const v=stripStore(raw);if(!badTitle(v))titleCandidates.push(v)};
  addTitle(meta('meta[property="og:title"]'));
  addTitle(meta('meta[name="twitter:title"]'));
  addTitle(meta('meta[name="title"]'));
  addTitle(document.title);

  // Also inspect the visible shopper-facing heading before deciding. This is especially
  // important when metadata contains only a shortened marketing name.
  const sels='h1,h2,h3,[class*="productTitle"],[class*="ProductTitle"],[class*="product_title"],[class*="title"]';
  const right=[...document.querySelectorAll(sels)].filter(visible).filter(e=>{
    const r=e.getBoundingClientRect(),v=stripStore(text(e));
    return r.left>innerWidth*.42&&r.top>20&&r.top<360&&r.width>140&&r.width<720&&!badTitle(v)&&!/^[\\d,]+\\s*원/.test(v);
  }).sort((a,b)=>{
    const A=a.getBoundingClientRect(),B=b.getBoundingClientRect();
    const af=parseFloat(getComputedStyle(a).fontSize)||0,bf=parseFloat(getComputedStyle(b).fontSize)||0;
    return bf-af || A.top-B.top || text(a).length-text(b).length;
  });
  for(const e of right)addTitle(text(e));
  if(!titleCandidates.length)return '';
  // De-duplicate, then prefer the longest exact seller-visible candidate. When one candidate
  // is merely a prefix of another (e.g. "델리온 델리리그 비비튠"), the full title wins.
  const unique=[...new Set(titleCandidates.map(v=>v.trim()).filter(Boolean))];
  unique.sort((a,b)=>b.length-a.length);
  return unique[0]||'';
}
function storeName(){
  const slug=location.pathname.split('/').filter(Boolean)[0]||'';
  const scored=[];
  for(const a of document.querySelectorAll('a[href]')){
    let u;try{u=new URL(a.href,location.href)}catch{continue}
    if(!/(^|\.)((smartstore|brand)\.)?naver\.com$/i.test(u.hostname))continue;
    const path=u.pathname.replace(/\/+$/,'');
    if(path!==`/${slug}`&&path!==`/${slug}/home`)continue;
    const vals=[text(a),a.getAttribute('aria-label'),a.getAttribute('title'),a.querySelector('img')?.alt].map(x=>String(x||'').trim());
    for(const v of vals){if(!v||v.length>80||BAD.test(v)||/^네이버$/i.test(v)||/^NAVER$/i.test(v)||v===slug)continue;scored.push(v)}
  }
  for(const e of document.querySelectorAll('header img[alt],header [class*="logo"] img[alt],[class*="store"] img[alt],[class*="seller"] img[alt]')){
    const v=String(e.alt||'').trim();if(v&&v.length<80&&!BAD.test(v)&&!/^네이버$/i.test(v))scored.push(v)
  }
  return scored[0]||'';
}
function price(){
  // V71: authoritative SmartStore purchase price.
  // Never hard-code the numeric price: find the blind label "상품 가격" and read
  // the CURRENT numeric text from its parent every time a product is captured.
  // Example DOM: <span><span class="blind">상품 가격</span>6,500<span>원</span></span>
  for(const blind of document.querySelectorAll('span.blind')){
    if(String(blind.textContent||'').replace(/\s+/g,' ').trim()!=='상품 가격')continue;
    const parent=blind.parentElement;if(!parent)continue;
    let raw='';
    for(const node of parent.childNodes){
      if(node===blind)continue;
      if(node.nodeType===Node.TEXT_NODE)raw+=` ${node.textContent||''}`;
      else if(node.nodeType===Node.ELEMENT_NODE && !/^(원)$/i.test(String(node.textContent||'').trim())) raw+=` ${node.textContent||''}`;
    }
    const m=raw.replace(/\s+/g,' ').match(/([0-9][0-9,]*)/);
    if(m){
      const v=Number(m[1].replace(/,/g,''));
      if(Number.isFinite(v)&&v>=100){diag('purchase_price_selected',{source:'BLIND_PRODUCT_PRICE_PARENT',value:v});return v}
    }
  }

  // V44: product purchase price must come only from the shopper-facing sale-price zone.
  // Never use shipping/benefit/reward/coupon amounts as the purchase price.
  const body=(document.body.innerText||'').replace(/,/g,'');
  const rightX=innerWidth*.46;
  const structuredPrice=()=>{
    const mp=meta('meta[property="product:price:amount"]','meta[property="og:price:amount"]','meta[itemprop="price"]');
    if(/^\d+(?:\.\d+)?$/.test(mp)&&Number(mp)>=100)return Number(mp);
    try{
      for(const sc of document.querySelectorAll('script[type="application/ld+json"]')){
        const j=JSON.parse(sc.textContent||'null');
        for(const row of (Array.isArray(j)?j:[j])){
          if(!/Product/i.test(String(row?.['@type']||'')))continue;
          for(const off of (Array.isArray(row?.offers)?row.offers:[row?.offers]).filter(Boolean)){
            for(const k of ['price','lowPrice']){
              const v=Number(String(off?.[k]??'').replace(/,/g,''));
              if(Number.isFinite(v)&&v>=100)return v;
            }
          }
        }
      }
    }catch(_){ }
    return null;
  };
  const structured=structuredPrice();

  // Naver's current selling price is the large red amount directly under the title.
  // Read that visual signal before broad structured/meta fallbacks, which can expose
  // a reward-point amount on some SmartStore templates.
  const visualSale=[];
  for(const e of document.querySelectorAll('strong,em,b,span')){
    if(!visible(e))continue;
    const r=e.getBoundingClientRect();
    if(r.top<55||r.top>430||r.left<rightX||r.width>360||r.height>100)continue;
    const raw=text(e).replace(/,/g,'').trim();
    const m=raw.match(/^(?:\d{1,2}%\s*)?(\d{3,10})\s*원?$/);
    if(!m)continue;
    const cs=getComputedStyle(e),fs=parseFloat(cs.fontSize)||0;
    const rgb=(cs.color||'').match(/\d+/g)?.map(Number)||[];
    const redish=rgb.length>=3&&rgb[0]>150&&rgb[0]>rgb[1]*1.35&&rgb[0]>rgb[2]*1.35;
    const struck=/line-through/i.test(cs.textDecorationLine||cs.textDecoration||'');
    const val=Number(m[1]);
    if(redish&&fs>=20&&!struck&&Number.isFinite(val)&&val>=100)visualSale.push({val,fs,top:r.top});
  }
  visualSale.sort((a,b)=>b.fs-a.fs||a.top-b.top);
  if(visualSale.length){diag('purchase_price_selected',{source:'LARGE_RED_VISIBLE_PRICE',value:visualSale[0].val});return visualSale[0].val}

  const hasBadPriceContext=(el)=>{
    let n=el;
    for(let d=0;d<6&&n;d++,n=n.parentElement){
      const t=text(n);
      if(t.length<=420&&/배송|택배|배송비|무료배송|도착|적립|포인트|쿠폰|혜택|멤버십|할부|리뷰|구매평|사은품/i.test(t)) return true;
    }
    return false;
  };
  const saleContextScore=(el)=>{
    let score=0,n=el;
    for(let d=0;d<6&&n;d++,n=n.parentElement){
      const t=text(n);
      if(t.length<=500&&/판매가|할인가|할인|즉시할인|최대\s*할인가|상품가/i.test(t)) score+=80;
      if(t.length<=500&&/배송|택배|배송비|무료배송|도착/i.test(t)) score-=320;
      if(t.length<=500&&/적립|포인트|쿠폰|혜택|멤버십|할부|리뷰|구매평/i.test(t)) score-=120;
    }
    return score;
  };

  // 1) Strongest source: exact visible current-price element in the upper-right product header.
  // SmartStore's live selling price is normally the large/bold/red amount next to the discount rate.
  const cand=[];
  const seen=new Set();
  for(const e of document.querySelectorAll('strong,em,b,span,div')){
    if(!visible(e))continue;
    const r=e.getBoundingClientRect();
    if(r.top<55||r.top>570||r.left<rightX||r.width>430||r.height>120)continue;
    const raw=text(e).replace(/,/g,'').trim();
    if(!raw||raw.length>70)continue;
    const m=raw.match(/^(?:\d{1,2}%\s*)?(\d{3,10})\s*원?$/) || raw.match(/^(\d{3,10})\s*원$/);
    if(!m)continue;
    const val=Number(m[1]);
    if(!Number.isFinite(val)||val<100)continue;
    // Reward/point/coupon amounts may be styled like a price. They are never purchase cost.
    if(hasBadPriceContext(e))continue;
    // Ignore wrapper nodes that concatenate option quantities/labels into a fake price.
    // The current sale price is a leaf-like amount; wrappers usually contain another
    // independently visible won amount below them.
    const nestedAmounts=[...e.children].filter(visible).map(text).filter(t=>/[\d,]+\s*원/.test(t));
    if(nestedAmounts.length)continue;
    const key=`${val}|${Math.round(r.top)}|${Math.round(r.left)}`;if(seen.has(key))continue;seen.add(key);
    const cs=getComputedStyle(e), fs=parseFloat(cs.fontSize)||0, fw=parseInt(cs.fontWeight)||400;
    const rgb=(cs.color||'').match(/\d+/g)?.map(Number)||[];
    const redish=rgb.length>=3 && rgb[0]>150 && rgb[0]>rgb[1]*1.25 && rgb[0]>rgb[2]*1.25;
    const struck=/line-through/i.test(cs.textDecorationLine||cs.textDecoration||'');
    let score=0;
    score += Math.min(fs,40)*5;
    if(fw>=600)score+=45;
    if(e.matches('strong,em,b'))score+=25;
    if(redish)score+=220;
    if(fs>=20)score+=90;
    if(fs>=26)score+=70;
    if(struck)score-=350;
    score+=saleContextScore(e);
    // Current price typically sits near the product title and before the benefit/shipping blocks.
    if(r.top>=130&&r.top<=380)score+=50;
    cand.push({val,score,top:r.top,fs,redish});
  }
  cand.sort((a,b)=>b.score-a.score||b.fs-a.fs||a.top-b.top);
  if(cand.length&&cand[0].score>=120){
    // Structured product data is used only as a sanity anchor. A DOM number tens or
    // hundreds of times larger is an option-number concatenation, not a sale price.
    if(structured&&cand[0].val>structured*5){diag('purchase_price_selected',{source:'STRUCTURED_SANITY',value:structured});return structured}
    diag('purchase_price_selected',{source:'VISIBLE_SCORED_PRICE',value:cand[0].val});return cand[0].val;
  }

  // 2) Explicit current-sale labels. This is deliberately narrower than body-wide number guessing.
  const explicit=[
    /(\d{3,10})\s*원?\s*최대\s*할인가/i,
    /(\d{3,10})\s*원?\s*할인\s*판매가/i,
    /최대\s*할인가[^\d]{0,30}(\d{3,10})\s*원?/i,
    /할인\s*판매가[^\d]{0,30}(\d{3,10})\s*원?/i,
    /판매가[^\d]{0,30}(\d{3,10})\s*원?/i
  ];
  for(const re of explicit){const m=body.match(re);if(m){const v=Number(m[1]);if(v>=100){diag('purchase_price_selected',{source:'EXPLICIT_SALE_LABEL',value:v});return v}}}

  // 3) Structured product price fallback. Do not scan arbitrary page numbers.
  if(structured){diag('purchase_price_selected',{source:'STRUCTURED_FALLBACK',value:structured});return structured}
  return null;
}
function shipping(){
  const labels=[...document.querySelectorAll('dt,th,strong,b,span,div')].filter(e=>visible(e)&&/^배송(?:비)?$/.test(text(e)));
  const blocks=[];
  for(const lab of labels){let n=lab;for(let i=0;i<4&&n;i++,n=n.parentElement){const t=text(n);if(t.length>=3&&t.length<=1000)blocks.push(t)}}
  for(const raw of uniq(blocks)){
    const s=raw.replace(/,/g,'');
    const m=s.match(/배송비\s*(?:기본\s*)?(\d{1,7})\s*원/i); if(m)return Number(m[1]);
    const m2=s.match(/(?:^|\s)(\d{1,7})\s*원\s*(?:\([^)]*이상\s*무료[^)]*\))?/i); if(m2&&!/적립|쿠폰|상품가|판매가/.test(s))return Number(m2[1]);
  }
  for(const raw of uniq(blocks)){if(/무료\s*배송|배송비\s*무료|무료배송/i.test(raw))return 0}
  return null;
}
function normImg(u){try{const x=new URL(u,location.href);x.searchParams.delete('type');return x.href}catch{return String(u||'')}}
function imgUrlFromEl(el){
  if(!el)return '';
  const vals=[el.currentSrc,el.src,el.getAttribute?.('data-src'),el.getAttribute?.('data-lazy-src'),el.getAttribute?.('data-original')];
  const ss=el.getAttribute?.('srcset')||el.getAttribute?.('data-srcset')||'';
  if(ss) vals.push(...ss.split(',').map(x=>x.trim().split(/\s+/)[0]));
  const st=getComputedStyle(el).backgroundImage||''; const bm=st.match(/url\(["']?(.*?)["']?\)/); if(bm)vals.push(bm[1]);
  return vals.find(v=>/^https?:/i.test(String(v||'')))||'';
}
function validProductImgUrl(u){return /^https?:/i.test(String(u||''))&&/pstatic|naver/i.test(u)&&!/logo|icon|profile|banner|sp_|ntm\.pstatic/i.test(u)}
function findMainImage(){
  const ims=[...document.querySelectorAll('img')].filter(visible).filter(im=>validProductImgUrl(imgUrlFromEl(im)));
  return ims.filter(im=>{const r=im.getBoundingClientRect();return r.top>20&&r.top<820&&r.left<innerWidth*.56&&r.width>=220&&r.height>=220})
    .sort((a,b)=>{const A=a.getBoundingClientRect(),B=b.getBoundingClientRect();return B.width*B.height-A.width*A.height})[0]||null;
}
function galleryPanel(main){
  if(!main)return null;
  let best=main.parentElement;
  for(let n=main.parentElement,d=0;n&&d<11;n=n.parentElement,d++){
    const r=n.getBoundingClientRect();
    if(r.left>innerWidth*.12||r.right>innerWidth*.70||r.width>innerWidth*.66)continue;
    const candidates=n.querySelectorAll('img,[style*="background-image"],[data-src],[data-lazy-src]').length;
    const hasCounter=[...n.querySelectorAll('*')].some(e=>/^[0-9]{1,2}\s*\/\s*[0-9]{1,2}$/.test(text(e)));
    if(candidates>=2||hasCounter)best=n;
  }
  return best;
}
function galleryTotal(panel){
  const scopes=[panel,document].filter(Boolean);
  const nums=[];
  for(const scope of scopes){
    for(const e of scope.querySelectorAll('*')){
      if(!visible(e))continue; const r=e.getBoundingClientRect();
      if(r.left>innerWidth*.60||r.top>900)continue;
      const v=text(e); if(/^\d{1,2}\s*\/\s*\d{1,2}$/.test(v)){const n=Number(v.split('/')[1]);if(n>=1&&n<=50)nums.push(n)}
    }
  }
  return nums.length?Math.max(...nums):null;
}
function galleryThumbs(panel,main){
  if(!panel||!main)return [];
  const mr=main.getBoundingClientRect(),seen=new Set(),out=[];
  for(const el of panel.querySelectorAll('img,[style*="background-image"],[data-src],[data-lazy-src]')){
    if(el===main)continue;
    const r=el.getBoundingClientRect();
    // Include the thumbnail rail even when individual thumbs are partly clipped by its carousel.
    if(r.width<20||r.width>180||r.height<20||r.height>180)continue;
    if(r.top<mr.bottom-130||r.top>mr.bottom+300)continue;
    const u=normImg(imgUrlFromEl(el)); if(!validProductImgUrl(u)||seen.has(u))continue;
    seen.add(u);out.push({el,u,left:r.left});
  }
  return out.sort((a,b)=>a.left-b.left);
}
function galleryNextButton(panel,main){
  const mr=main.getBoundingClientRect();
  const scope=panel||document;
  const btns=[...scope.querySelectorAll('button,a,[role="button"]')].filter(visible).filter(b=>{
    const r=b.getBoundingClientRect(),lab=(b.getAttribute('aria-label')||b.getAttribute('title')||text(b)||'').trim();
    if(/이전|prev|왼쪽/i.test(lab))return false;
    if(/다음|next|오른쪽/i.test(lab))return true;
    const below=r.top>mr.bottom-120&&r.top<mr.bottom+300;
    const rightish=r.left>mr.left+mr.width*.45&&r.left<Math.min(innerWidth*.62,mr.right+180);
    return below&&rightish&&r.width>=20&&r.width<=90&&r.height>=20&&r.height<=90;
  });
  return btns.sort((a,b)=>b.getBoundingClientRect().left-a.getBoundingClientRect().left)[0]||null;
}
async function galleryImages(){
  let main=findMainImage(); if(!main)return [];
  let panel=galleryPanel(main); const total=galleryTotal(panel); const out=[]; const push=u=>{u=normImg(u);if(validProductImgUrl(u)&&!out.includes(u))out.push(u)};
  push(imgUrlFromEl(main));
  // First collect every URL already present in the actual gallery container, including clipped thumbnails.
  for(const {u} of galleryThumbs(panel,main))push(u);

  // If Naver tells us 1/N, actively advance only the gallery carousel until N unique main images are seen.
  // This is performed only during an explicit B2B import session.
  const target=total||Math.min(30,Math.max(out.length,1));
  let stagnant=0;
  for(let i=0;i<Math.min(50,target+8)&&out.length<target;i++){
    main=findMainImage()||main; panel=galleryPanel(main)||panel;
    const before=out.length;
    const next=galleryNextButton(panel,main);
    if(!next)break;
    if(protectedActionTarget(next)){console.warn('[B2B Helper] gallery candidate rejected as shopper action');break}
    if(stopped())break;
    try{next.click();await sleep(360)}catch{break}
    main=findMainImage()||main; push(imgUrlFromEl(main));
    for(const {u} of galleryThumbs(panel,main))push(u);
    stagnant=out.length===before?stagnant+1:0;
    if(stagnant>=3)break;
  }
  return total?out.slice(0,total):out.slice(0,100);
}
function absTop(e){const r=e.getBoundingClientRect();return r.top+scrollY}
function headingY(re){
  const els=[...document.querySelectorAll('h1,h2,h3,h4,strong,b,span,div')]
    .filter(visible)
    .filter(e=>{const v=text(e);const r=e.getBoundingClientRect();return r.left>innerWidth*.42&&r.width>40&&r.width<520&&v.length<=40&&re.test(v)});
  return els.length?Math.min(...els.map(absTop)):null;
}
function optionValueOK(v){
  v=String(v||'').replace(/\s+/g,' ').trim();
  return !!v&&v.length<=220&&!BAD.test(v)
    &&!/^(선택|옵션\s*선택|옵션선택|품절|추가\s*옵션)$/i.test(v)
    &&!/별점|리뷰|후기|배송|택배|반품|교환|고객센터|멤버십|적립|혜택|문의|찜하기|구매하기|장바구니|무료배송|배송비|부과|1개마다|상품가|판매가/i.test(v);
}
function absTop(e){const r=e.getBoundingClientRect();return r.top+scrollY}
function headingY(re){
  const els=[...document.querySelectorAll('h1,h2,h3,h4,strong,b,span,div,label')]
    .filter(visible)
    .filter(e=>{const v=text(e);const r=e.getBoundingClientRect();return r.left>innerWidth*.42&&r.width>30&&r.width<620&&v.length<=60&&re.test(v)});
  return els.length?Math.min(...els.map(absTop)):null;
}
function triggerText(t){return String(text(t)||t?.getAttribute?.('aria-label')||t?.getAttribute?.('title')||'').replace(/\s+/g,' ').trim()}
function triggerLabel(t,idx,prefix='옵션'){
  let raw=triggerText(t).replace(/\(필수\)/g,'').trim();
  if(raw.includes('/'))raw=raw.split('/')[0].trim();
  if(raw&&raw.length<90&&!BAD.test(raw)&&!/^(선택|옵션|옵션선택)$/i.test(raw))return raw;
  const tr=t.getBoundingClientRect();
  const labs=[...document.querySelectorAll('label,strong,b,span,div')].filter(visible).filter(e=>{
    const r=e.getBoundingClientRect(),x=text(e);return x&&x.length<60&&!BAD.test(x)&&r.left>=tr.left-100&&r.right<=tr.right+100&&r.bottom<=tr.top+12&&r.bottom>=tr.top-120;
  }).sort((a,b)=>b.getBoundingClientRect().bottom-a.getBoundingClientRect().bottom);
  const lv=labs.length?text(labs[0]).replace(/\s+/g,' ').trim():'';
  if(lv&&!/^(옵션\s*선택(?:\s*\(필수\))?|추가\s*옵션)$/i.test(lv))return lv.replace(/\(필수\)/g,'').trim();
  return `${prefix}${idx+1}`;
}
function candidateRectKey(e){const r=e.getBoundingClientRect();return [Math.round(r.left/3),Math.round(r.top/3),Math.round(r.width/3),Math.round(r.height/3)].join(':')}
function sectionTriggerCandidates(y1,y2){
  const sels='select,button,[role="button"],[role="combobox"],[aria-haspopup],[aria-expanded],[tabindex="0"],input[readonly],div[class*="select"],div[class*="Select"],div[class*="dropdown"],div[class*="Dropdown"]';
  const semantic=/^(?:길이|호수|색상|사이즈|규격|종류|타입|모델|수량|옵션\s*선택)(?:\s*\/.*)?$/i;
  const semanticNodes=[...document.querySelectorAll('div[class],span[class]')].filter(e=>semantic.test(triggerText(e)));
  const raw=[...new Set([...document.querySelectorAll(sels),...semanticNodes])].filter(visible).filter(e=>{
    const r=e.getBoundingClientRect(),ay=r.top+scrollY,v=triggerText(e);
    if(ay<y1||ay>y2||r.left<innerWidth*.43||r.width<180||r.width>760||r.height<28||r.height>90)return false;
    if(v.length>180||/구매하기|선물하기|찜하기|장바구니|톡톡문의|자세히보기|쿠폰|적립|혜택|배송/i.test(v))return false;
    return true;
  });
  // Prefer the deepest/smallest node for the same visual rectangle; this is usually the actually clickable control.
  const byRect=new Map();
  for(const e of raw){
    const k=candidateRectKey(e),old=byRect.get(k);
    if(!old||old.contains(e)||e.getBoundingClientRect().width<old.getBoundingClientRect().width)byRect.set(k,e);
  }
  const sorted=[...byRect.values()].sort((a,b)=>absTop(a)-absTop(b));
  // A single SmartStore combobox is often represented by a button plus one or more nested
  // select-looking divs with slightly different rectangles.  Collapse those to one control.
  const dedup=[];
  for(const e of sorted){
    const r=e.getBoundingClientRect();
    const duplicate=dedup.some(x=>{
      const q=x.getBoundingClientRect();
      const hOverlap=Math.max(0,Math.min(r.right,q.right)-Math.max(r.left,q.left));
      const vOverlap=Math.max(0,Math.min(r.bottom,q.bottom)-Math.max(r.top,q.top));
      const areaOverlap=hOverlap*vOverlap;
      const minArea=Math.max(1,Math.min(r.width*r.height,q.width*q.height));
      return areaOverlap/minArea>0.72&&Math.abs(r.top-q.top)<12;
    });
    if(!duplicate)dedup.push(e);
  }
  return dedup;
}
function requiredOptionControlCount(){
  const yMain=headingY(/^옵션\s*선택(?:\s*\(필수\))?/i);
  if(yMain==null)return 0;
  const yExtra=headingY(/^추가\s*옵션$/i);
  const buys=[...document.querySelectorAll('button,a')].filter(visible).filter(e=>/선물하기|구매하기|장바구니/i.test(text(e))&&e.getBoundingClientRect().left>innerWidth*.42);
  const yBuy=buys.length?Math.min(...buys.map(absTop)):null;
  const y2=(yExtra!=null&&yExtra>yMain?yExtra:(yBuy!=null?yBuy:yMain+2000))-4;
  const detected=sectionTriggerCandidates(yMain+4,y2);
  const semantic=/^(?:길이|호수|색상|사이즈|규격|종류|타입|모델|수량|옵션\s*선택)(?:\s*\/.*)?$/i;
  const tops=new Set();
  for(const e of document.querySelectorAll('button,select,[role="combobox"],div[class],span[class]')){
    if(!visible(e)||!semantic.test(triggerText(e)))continue;
    const r=e.getBoundingClientRect(),ay=r.top+scrollY;
    if(ay>=yMain+4&&ay<=y2&&r.left>innerWidth*.43&&r.width>=180&&r.height>=28&&r.height<=90)tops.add(Math.round(ay/8));
  }
  return Math.max(detected.length,tops.size);
}
function visibleTextLeaves(){
  const out=[];
  const sels='label,li,span,div,p,[role="option"],[role="menuitem"],[role="menuitemcheckbox"],[role="menuitemradio"]';
  for(const e of document.querySelectorAll(sels)){
    if(!visible(e))continue;
    const r=e.getBoundingClientRect(),v=text(e).replace(/\s+/g,' ').trim();
    if(r.left<innerWidth*.40||r.width<20||r.width>820||r.height<10||r.height>180||r.top<-100||r.top>innerHeight+1000)continue;
    if(!optionValueOK(v))continue;
    // Avoid huge containers that merely repeat all descendant option text.
    const childTexts=[...e.children].filter(visible).map(text).filter(Boolean);
    if(childTexts.length&&childTexts.some(x=>x===v))continue;
    out.push({el:e,v,r});
  }
  return out;
}
function optionSnapshot(){return new Set(visibleTextLeaves().map(x=>x.v))}
async function clickTrigger(t){
  if(stopped())return false;
  if(protectedActionTarget(t)){diag('trigger_click_blocked',{reason:'protected_action',target:diagnosticNode(t)});console.warn('[B2B Helper] refused protected click:',triggerText(t));return false}
  // Never call scrollIntoView here. If the control is not in the top purchase panel,
  // it is not a valid sourcing control for this pass.
  const r=t.getBoundingClientRect();
  if(r.left<innerWidth*.40||r.width<20||r.height<20){
    diag('trigger_click_blocked',{reason:'outside_purchase_column',target:diagnosticNode(t)});
    console.warn('[B2B Helper] refused non-purchase-column option click');
    return false;
  }
  const before=diagnosticNode(t);
  try{t.click();diag('trigger_clicked',{method:'native_click',before,after:diagnosticNode(t)});return true}catch(e){diag('trigger_click_error',{method:'native_click',error:String(e),target:before})}
  try{t.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));t.dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));t.dispatchEvent(new MouseEvent('click',{bubbles:true}));diag('trigger_clicked',{method:'mouse_events',before,after:diagnosticNode(t)});return true}catch(e){diag('trigger_click_error',{method:'mouse_events',error:String(e),target:before})}
  return false;
}
function normalizeDeltaText(t){
  const m=String(t||'').match(/([+-])\s*([\d,]+)\s*원/);
  return m?`(${m[1]}${m[2]}원)`:'';
}
function nearestRowPrice(e){
  if(!e)return '';
  // SmartStore frequently places the price as a sibling of the checkbox label. Walk upward
  // through small option-row ancestors and stop at the first explicit +/- amount.
  let cur=e;
  for(let i=0;i<8&&cur;i++,cur=cur.parentElement){
    const r=cur.getBoundingClientRect?.();
    if(r&&r.width>0&&r.width<1000&&r.height>0&&r.height<180){
      const d=normalizeDeltaText(cur.innerText||cur.textContent||'');
      if(d)return d;
      for(const sib of [cur.previousElementSibling,cur.nextElementSibling]){
        if(!sib)continue;
        const sr=sib.getBoundingClientRect?.();
        if(sr&&Math.abs((sr.top||0)-(r.top||0))<90){
          const x=normalizeDeltaText(sib.innerText||sib.textContent||'');
          if(x)return x;
        }
      }
    }
  }
  return '';
}
function optionTextWithPrice(e){
  if(!e)return '';
  const own=String(e.innerText||e.textContent||e.getAttribute?.('aria-label')||'').replace(/\s+/g,' ').trim();
  if(!own)return '';
  if(/[+-]\s*[\d,]+\s*원/.test(own))return own;
  // Price may be nested OR rendered as a sibling in the same option row.
  const nested=[];
  for(const n of e.querySelectorAll?.('span,strong,b,em,small,div')||[]){
    const d=normalizeDeltaText(n.innerText||n.textContent||'');
    if(d)nested.push(d);
  }
  const delta=[...new Set(nested)][0]||nearestRowPrice(e);
  return delta?`${own} ${delta}`.trim():own;
}
function decorateValuesWithOpenDomPrices(values,trigger){
  const out=[];
  for(const raw of values||[]){
    let v=String(raw||'').replace(/\s+/g,' ').trim();
    if(!v||/[+-]\s*[\d,]+\s*원/.test(v)){out.push(v);continue}
    const key=priceKey(v).replace(/[\s_]+/g,'').toLowerCase();
    let found='';
    const candidates=document.querySelectorAll('li,label,[role="option"],[role="menuitem"],[role="menuitemcheckbox"],[role="menuitemradio"],div,span');
    for(const el of candidates){
      if(!visible(el))continue;
      const r=el.getBoundingClientRect();
      if(r.left<innerWidth*.40||r.width<20||r.width>1000||r.height<10||r.height>180)continue;
      const t=String(el.innerText||el.textContent||'').replace(/\s+/g,' ').trim();
      if(!t||!/[+-]\s*[\d,]+\s*원/.test(t))continue;
      const tk=priceKey(t).replace(/[\s_]+/g,'').toLowerCase();
      if(!tk.includes(key)&&!key.includes(tk))continue;
      const d=normalizeDeltaText(t)||nearestRowPrice(el);
      if(d){found=d;break}
    }
    out.push(found?`${v} ${found}`:v);
  }
  return uniq(out);
}
function popupValuesFor(trigger){
  const out=[];
  const ids=[trigger.getAttribute?.('aria-controls'),trigger.getAttribute?.('aria-owns')].filter(Boolean);
  for(const id of ids){
    const root=document.getElementById(id);if(!root)continue;
    // Prefer one complete buyer-visible row first. Child spans are only fallback.
    const preferred=root.querySelectorAll('li,[role="option"],[role="menuitem"],[role="menuitemcheckbox"],[role="menuitemradio"],label,button');
    for(const e of preferred){
      if(!visible(e))continue;const v=optionTextWithPrice(e);if(optionValueOK(v))out.push(v);
    }
    if(!out.length){
      for(const e of root.querySelectorAll('span,div')){
        if(!visible(e))continue;const v=optionTextWithPrice(e);if(optionValueOK(v))out.push(v);
      }
    }
  }
  return uniq(out);
}
function optionRowsByGeometry(trigger){
  // V45: SmartStore sometimes renders the option label and +/- price in separate
  // sibling nodes that are not descendants of the checkbox label. Rebuild each
  // visible option row by geometry while the dropdown is open.
  const tr=trigger.getBoundingClientRect(),out=[];
  const inputs=[...document.querySelectorAll('input[type="checkbox"],input[type="radio"]')];
  for(const inp of inputs){
    const anchor=visible(inp)?inp:(visible(inp.parentElement)?inp.parentElement:null);
    if(!anchor)continue;
    const ir=anchor.getBoundingClientRect();
    if(ir.left<tr.left-260||ir.right>tr.right+900||ir.top<tr.top-260||ir.top>tr.bottom+1400)continue;
    const lab=(inp.id&&document.querySelector(`label[for="${CSS.escape(inp.id)}"]`))||inp.closest('label')||inp.parentElement;
    if(!lab)continue;
    let base=String(lab.innerText||lab.textContent||'').replace(/\s+/g,' ').trim();
    if(!base)continue;
    // Strip a duplicated price before re-attaching the authoritative row price.
    base=base.replace(/\s*\([+-]\s*[\d,]+\s*원\)\s*$/,'').trim();
    const lr=(visible(lab)?lab:anchor).getBoundingClientRect();
    const y=(lr.top+lr.bottom)/2;
    let best='',bestDist=1e9;
    const priceNodes=document.querySelectorAll('span,strong,b,em,small,div,p');
    for(const n of priceNodes){
      if(!visible(n))continue;
      const t=String(n.innerText||n.textContent||'').replace(/\s+/g,' ').trim();
      const delta=normalizeDeltaText(t);
      if(!delta)continue;
      const r=n.getBoundingClientRect();
      // Price must be on the same visual option row and inside the opened option column.
      const cy=(r.top+r.bottom)/2,dy=Math.abs(cy-y);
      if(dy>34)continue;
      if(r.right<tr.left-30||r.left>tr.right+700)continue;
      // Ignore huge containers that happen to contain many prices.
      if(r.height>90||r.width>900)continue;
      const dist=dy+Math.max(0,r.left-lr.right)*0.01;
      if(dist<bestDist){bestDist=dist;best=delta;}
    }
    const ownDelta=normalizeDeltaText(String((lab.closest('li,[role="option"],[role="menuitem"],[role="menuitemcheckbox"],[role="menuitemradio"]')||lab.parentElement||lab).innerText||''));
    const delta=ownDelta||best;
    const v=delta?`${base} ${delta}`:base;
    if(optionValueOK(v))out.push(v);
  }
  return uniq(out);
}
function optionScrollContainers(trigger){
  const tr=trigger.getBoundingClientRect(),out=[];
  for(const el of document.querySelectorAll('[role="listbox"],ul,div')){
    if(!visible(el)||el===document.body||el===document.documentElement)continue;
    const r=el.getBoundingClientRect(),cs=getComputedStyle(el);
    if(!/(auto|scroll)/.test(cs.overflowY||'')||el.scrollHeight<=el.clientHeight+8)continue;
    const overlap=Math.max(0,Math.min(r.right,tr.right+160)-Math.max(r.left,tr.left-80));
    if(r.left<innerWidth*.40||overlap<Math.min(r.width,tr.width)*.35||r.top<tr.top-80||r.top>tr.bottom+1000)continue;
    out.push(el);
  }
  return out.sort((a,b)=>a.getBoundingClientRect().top-b.getBoundingClientRect().top).slice(0,3);
}

function checkboxRadioValuesNear(trigger){
  const tr=trigger.getBoundingClientRect(),out=[];
  for(const inp of document.querySelectorAll('input[type="checkbox"],input[type="radio"]')){
    if(!visible(inp)&&!visible(inp.parentElement))continue;
    const anchor=visible(inp)?inp:inp.parentElement;
    const r=anchor.getBoundingClientRect();
    const near=r.right>=tr.left-220&&r.left<=tr.right+520&&r.top>=tr.top-220&&r.top<=tr.bottom+1600;
    if(!near)continue;
    const lab=(inp.id&&document.querySelector(`label[for="${CSS.escape(inp.id)}"]`))||inp.closest('label')||inp.parentElement;
    // SmartStore often places the +/- amount in a sibling span rather than inside the checkbox label.
    // Read one buyer-visible option row so e.g. '(+4,500원)' survives capture.
    let row=lab;
    for(const cand of [lab?.closest?.('li'),lab?.closest?.('[role="option"]'),lab?.closest?.('[role="menuitemcheckbox"]'),lab?.parentElement,lab?.parentElement?.parentElement]){
      if(!cand||!visible(cand))continue;
      const cr=cand.getBoundingClientRect();
      if(cr.height>=18&&cr.height<=120&&cr.width<=Math.max(820,tr.width*1.45)){row=cand;break}
    }
    let v=optionTextWithPrice(row||lab);
    // If row text is too broad, fall back to label + a nearby explicit price span.
    if(!optionValueOK(v)){
      const base=String(text(lab)||'').replace(/\s+/g,' ').trim();
      let delta='';
      const scope=(lab?.parentElement)||lab;
      for(const n of scope?.querySelectorAll?.('span,strong,b,em,small')||[]){
        const t=String(n.innerText||n.textContent||'').replace(/\s+/g,' ').trim();
        const m=t.match(/([+-])\s*([\d,]+)\s*원/);
        if(m){delta=`(${m[1]}${m[2]}원)`;break}
      }
      v=(base&&delta&&!/[+-]\s*[\d,]+\s*원/.test(base))?`${base} ${delta}`:base;
    }
    if(optionValueOK(v))out.push(v);
  }
  return uniq(out);
}
async function openAndRead(trigger){
  if(trigger.tagName==='SELECT')return uniq([...trigger.options].map(o=>optionTextWithPrice(o)).filter(optionValueOK));
  if(trigger.disabled||trigger.getAttribute('aria-disabled')==='true')return [];

  // V38: do not move the page to reach a control. Only read controls already present in
  // the top purchase panel. This prevents detail/review text from entering the option scan.
  const rr=trigger.getBoundingClientRect();
  // V39: the whole page remains locked at the top, but a purchase control may sit below
  // the current viewport (e.g. extra option group 5/6). Programmatic click does not need
  // scrollIntoView, so allow off-screen controls as long as they belong to the right purchase column.
  if(rr.left<innerWidth*.40||rr.width<20||rr.height<20)return [];
  const before=optionSnapshot();
  diag('option_open_start',{trigger:diagnosticNode(trigger),visible_prices:visiblePurchasePriceCandidates()});
  if(!(await clickTrigger(trigger)))return [];

  let vals=[];
  for(const wait of [160,240,360,520]){
    await sleep(wait);
    const tr=trigger.getBoundingClientRect();
    vals.push(...popupValuesFor(trigger),...checkboxRadioValuesNear(trigger),...optionRowsByGeometry(trigger));

    // Fallback for Naver dropdowns without aria-controls.  Only accept text that appeared
    // AFTER the click and is geometrically inside the dropdown/option-control column.
    // Never sweep the rest of the page merely because it is visible.
    const rows=visibleTextLeaves();
    vals.push(...rows.filter(({v,r})=>{
      if(before.has(v))return false;
      const horizontalOverlap=Math.max(0,Math.min(r.right,tr.right+80)-Math.max(r.left,tr.left-30));
      const overlapRatio=horizontalOverlap/Math.max(1,Math.min(r.width,tr.width));
      const verticallyNear=r.top>=tr.top-40&&r.top<=tr.bottom+900;
      const plausibleWidth=r.width<=Math.max(760,tr.width*1.25);
      return r.left>innerWidth*.40&&overlapRatio>=0.55&&verticallyNear&&plausibleWidth;
    }).map(x=>x.v));

    vals=uniq(vals.filter(optionValueOK));
    if(vals.length)extendOptionWork('option_values_found');
    // While the dropdown is still open, recover +/- prices rendered in sibling spans.
    vals=decorateValuesWithOpenDomPrices(vals,trigger);
    const own=triggerText(trigger);
    vals=vals.filter(v=>v!==own&&!/^옵션\s*선택/i.test(v)&&!/^추가\s*옵션$/i.test(v));
    diag('option_open_snapshot',{wait_ms:wait,trigger:diagnosticNode(trigger),values:vals.slice(0,120),priced_values:vals.filter(v=>/[+-]\s*[\d,]+\s*원/.test(v)).slice(0,120),visible_prices:visiblePurchasePriceCandidates()});
    // A label can appear a few frames before its sibling +/- price.  Do not stop at
    // the first name-only snapshot; give the opened layer its full hydration window.
    if(vals.length&&vals.some(v=>/[+-]\s*[\d,]+\s*원/.test(v)))break;
  }
  // Exhaustively inspect only the opened option layer's own scrollbar. The product page
  // viewport remains locked; this is required for virtualized long option/add-on lists.
  for(const scroller of optionScrollContainers(trigger)){
    const original=scroller.scrollTop;let last=-1;
    for(let step=0;step<80;step++){
      const max=Math.max(0,scroller.scrollHeight-scroller.clientHeight);
      const next=Math.min(max,Math.round(step*scroller.clientHeight*.78));
      if(next===last)break;last=next;scroller.scrollTop=next;
      scroller.dispatchEvent(new Event('scroll',{bubbles:true}));
      await sleep(90);
      vals.push(...popupValuesFor(trigger),...checkboxRadioValuesNear(trigger),...optionRowsByGeometry(trigger));
      vals=decorateValuesWithOpenDomPrices(uniq(vals.filter(optionValueOK)),trigger);
      extendOptionWork('option_layer_scrolled',8000);
      if(next>=max)break;
    }
    scroller.scrollTop=original;
  }
  vals=uniq(vals.filter(optionValueOK));
  return vals;
}
function findChoiceElement(value,trigger){
  const want=String(value||'').replace(/\s+/g,' ').trim(),tr=trigger.getBoundingClientRect();
  for(const {el,v,r} of visibleTextLeaves()){
    if(v!==want&&!sameOptionLabel(v,want))continue;
    const near=r.right>=tr.left-180&&r.left<=tr.right+420&&r.top>=tr.top-220&&r.top<=tr.bottom+1300;
    if(near&&el.getAttribute?.('aria-disabled')!=='true')return el;
  }
  return null;
}

async function activelyVerifyMainValues(trigger,values){
  let verified=[...(values||[])];
  // Main options are verified by a real option-row selection.  This is deliberately
  // separate from add-ons, whose already-working capture path must remain unchanged.
  for(const raw of (values||[]).slice(0,1000)){
    if(Date.now()+1400>=optionWorkDeadline)break;
    await closeOptionLayer(trigger);
    await sleep(100);
    if(!(await clickTrigger(trigger)))continue;
    await sleep(360);

    let el=findChoiceElement(raw,trigger);
    if(!el){
      const tr=trigger.getBoundingClientRect();
      for(const row of document.querySelectorAll('li,label,[role="option"],[role="menuitem"],[role="menuitemcheckbox"],[role="menuitemradio"]')){
        if(!visible(row)||!sameOptionLabel(optionTextWithPrice(row),raw))continue;
        const r=row.getBoundingClientRect();
        if(r.right>=tr.left-180&&r.left<=tr.right+700&&r.top>=tr.top-220&&r.top<=tr.bottom+1400){el=row;break}
      }
    }
    if(!el||protectedActionTarget(el)){diag('main_value_not_clickable',{value:raw,trigger:diagnosticNode(trigger),found:diagnosticNode(el)});continue}

    // Read the complete buyer-visible row immediately before selection, then click it.
    // For SmartStore this preserves prices rendered in a sibling span such as (+100원).
    const row=el.closest?.('li,[role="option"],[role="menuitem"],[role="menuitemcheckbox"],[role="menuitemradio"],label')||el.parentElement||el;
    const beforeClick=optionTextWithPrice(row)||optionTextWithPrice(el)||raw;
    const pricesBefore=visiblePurchasePriceCandidates();
    diag('main_value_click_start',{value:raw,resolved_value:beforeClick,target:diagnosticNode(el),row:diagnosticNode(row),visible_prices:pricesBefore});
    try{el.click()}catch{try{el.dispatchEvent(new MouseEvent('click',{bubbles:true}))}catch{continue}}
    extendOptionWork('main_option_clicked');
    await sleep(420);
    const afterClick=optionTextWithPrice(row)||optionTextWithPrice(el)||beforeClick;
    diag('main_value_clicked',{value:raw,before_value:beforeClick,after_value:afterClick,row:diagnosticNode(row),visible_prices_before:pricesBefore,visible_prices_after:visiblePurchasePriceCandidates()});
    verified=mergeOptionValuesPreferPrice(verified,[beforeClick,afterClick]);

    // Checkbox-style options can be safely toggled back off so verification does not
    // accumulate selections. Radio/single-select choices are simply replaced next pass.
    const input=(el.matches?.('input[type="checkbox"]')?el:el.querySelector?.('input[type="checkbox"]'));
    if(input?.checked){try{(input.closest('label')||input).click();await sleep(160);diag('main_value_unchecked',{value:raw})}catch(e){diag('main_value_uncheck_error',{value:raw,error:String(e)})}}
  }
  await closeOptionLayer(trigger);
  return verified;
}
async function unlockNextMandatoryOption(trigger,vals){
  const first=vals.find(optionValueOK);if(!first)return false;
  const el=findChoiceElement(first,trigger);if(!el||protectedActionTarget(el))return false;
  try{el.click();await sleep(500);return true}catch{return false}
}

async function closeOptionLayer(trigger){
  try{document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',code:'Escape',bubbles:true}));await sleep(160)}catch{}
  try{if(trigger.getAttribute?.('aria-expanded')==='true'){trigger.click();await sleep(120)}}catch{}
}
function mergeOptionValuesPreferPrice(...lists){
  const out=[],index=new Map();
  for(const value of lists.flat()){
    const v=String(value||'').replace(/\s+/g,' ').trim();if(!v||!optionValueOK(v))continue;
    const key=priceKey(v).replace(/[\s_]+/g,'').toLowerCase();if(!key)continue;
    const oldIndex=index.get(key);
    if(oldIndex==null){index.set(key,out.length);out.push(v);continue}
    const old=out[oldIndex];
    if(!/[+-]\s*[\d,]+\s*원/.test(old)&&/[+-]\s*[\d,]+\s*원/.test(v))out[oldIndex]=v;
  }
  return out;
}
async function readOptionSection(kind){
  const yMain=headingY(/^옵션\s*선택(?:\s*\(필수\))?/i),yExtra=headingY(/^추가\s*옵션$/i);
  const buys=[...document.querySelectorAll('button,a')].filter(visible).filter(e=>/선물하기|구매하기|장바구니/i.test(text(e))&&e.getBoundingClientRect().left>innerWidth*.42);
  const yBuy=buys.length?Math.min(...buys.map(absTop)):null;
  let y1,y2,prefix;
  if(kind==='main'){
    if(yMain==null)return [];
    y1=yMain+4;y2=(yExtra!=null&&yExtra>yMain?yExtra:(yBuy!=null?yBuy:yMain+2000))-4;prefix='옵션';
  }else{
    if(yExtra==null)return [];
    y1=yExtra+4;y2=(yBuy!=null&&yBuy>yExtra?yBuy:yExtra+6000)-4;prefix='추가옵션';
  }
  const groups=[];
  // Additional-option controls are independent dropdowns.  Snapshot their real control count
  // once so opening the first dropdown cannot create fake 'additional option 3/4/5' candidates.
  const fixedExtraTriggers=kind==='extra'?sectionTriggerCandidates(y1,y2):null;
  for(let i=0;i<30;i++){
    let triggers=fixedExtraTriggers||sectionTriggerCandidates(y1,y2);
    if(i>=triggers.length)break;
    let t=triggers[i];if(!t)break;
    const name=triggerLabel(t,i,prefix);
    let vals=await openAndRead(t);
    if(kind==='main'){
      // V56: every option gets at most two checks. A single-option product uses
      // list-read + one real value verification. A dependent product leaves the second
      // check to collectDependentMainVariants(), where each parent unlocks its children.
      // This removes the former list-read + reopen + value-click triple pass.
      const firstPass=[...vals];
      const dependentLayout=triggers.length>=2;
      if(!dependentLayout){
        try{
          vals=await activelyVerifyMainValues(t,firstPass);
        }catch(e){
          vals=firstPass;
          if(!String(e).includes('B2B_OPTION_TIME_LIMIT'))console.warn('[B2B Helper] mandatory option value verification failed; preserving list pass',e);
        }
      }
    }
    vals=uniq(vals.filter(v=>v!==name&&optionValueOK(v)));
    if(vals.length)groups.push({name,values:vals});
    // Select one value only when another mandatory control still needs unlocking.
    // Never click the final child merely to close/finish the section.
    if(kind==='main'&&vals.length&&i<triggers.length-1&&!naverMainOptionButtons().length)await unlockNextMandatoryOption(t,vals);
    await closeOptionLayer(t);
    await sleep(180);
  }
  return groups.filter((g,i,a)=>g.values?.length&&a.findIndex(x=>x.name===g.name&&x.values.join('|')===g.values.join('|'))===i);
}
function sameOptionLabel(a,b){
  const norm=x=>priceKey(String(x||''))
    .replace(/\(품절\)/g,'')
    .replace(/[\s_]+/g,'')
    .toLowerCase();
  return norm(a)===norm(b);
}
async function chooseOptionValue(trigger,value){
  if(trigger?.tagName==='SELECT'){
    const opts=[...trigger.options];
    const target=opts.find(o=>sameOptionLabel(optionTextWithPrice(o),value)||sameOptionLabel(o.textContent,value));
    if(!target)return false;
    trigger.value=target.value;
    trigger.dispatchEvent(new Event('input',{bubbles:true}));
    trigger.dispatchEvent(new Event('change',{bubbles:true}));
    await sleep(420);
    return true;
  }
  await closeOptionLayer(trigger);
  await sleep(100);
  if(!(await clickTrigger(trigger)))return false;
  await sleep(260);
  let el=findChoiceElement(value,trigger);
  if(!el){
    // aria popup rows are often cleaner than general text leaves.
    const ids=[trigger.getAttribute?.('aria-controls'),trigger.getAttribute?.('aria-owns')].filter(Boolean);
    outer: for(const id of ids){
      const root=document.getElementById(id); if(!root)continue;
      for(const row of root.querySelectorAll('li,[role="option"],[role="menuitem"],[role="menuitemcheckbox"],[role="menuitemradio"],label,button,span,div')){
        if(sameOptionLabel(optionTextWithPrice(row),value)){el=row;break outer}
      }
    }
  }
  if(!el||protectedActionTarget(el))return false;
  try{el.click()}catch{
    try{el.dispatchEvent(new MouseEvent('click',{bubbles:true}))}catch{return false}
  }
  await sleep(520);
  extendOptionWork('dependent_parent_selected');
  return true;
}
function variantAvailabilityFromText(v){return /품절|판매\s*중지|구매\s*불가/i.test(String(v||''))?'OUT_OF_STOCK':'AVAILABLE'}
function naverMainOptionButtons(){
  const seen=new Set();
  return [...document.querySelectorAll('a[role="button"][data-shp-area="pcs.optselect"][data-shp-area-id="optselect"][data-shp-contents-type]')]
    .filter(el=>{if(!el||seen.has(el))return false;seen.add(el);return true})
;
}
function naverMainRows(groupName){
  return [...document.querySelectorAll('a[role="option"][data-shp-area="pcs.optselect"][data-shp-area-id="optselect"][data-shp-contents-type]')]
    .filter(el=>el.getAttribute('data-shp-contents-type')===groupName);
}
function naverRowValue(row){
  const id=String(row?.getAttribute?.('data-shp-contents-id')||'').trim();
  const raw=String(row?.innerText||row?.textContent||'').replace(/\s+/g,' ').trim();
  const delta=(raw.match(/\(([+-])\s*([\d,]+)\s*원\)/)||[])[0]||'';
  const sold=/품절/.test(raw)?' (품절)':'';
  return raw||id;
}
function naverSafeMainButton(button){
  return !!button?.matches?.('a[role="button"][data-shp-area="pcs.optselect"][data-shp-area-id="optselect"][data-shp-contents-type]');
}
function naverSafeMainRow(row,group){
  return !!row?.matches?.('a[role="option"][data-shp-area="pcs.optselect"][data-shp-area-id="optselect"][data-shp-contents-type]') && row.getAttribute('data-shp-contents-type')===group;
}
function closeNaverIntrusiveLayers(){
  if(stopped())return;
  // Only close visible Naver side/modal layers that are unrelated to reading option rows.
  // Never click purchase/cart/coupon/benefit actions; only their explicit X close controls.
  const candidates=[...document.querySelectorAll('button,a')].filter(el=>{
    if(!visible(el))return false;
    const aria=String(el.getAttribute('aria-label')||'');
    const title=String(el.getAttribute('title')||'');
    const t=String(el.innerText||el.textContent||'').trim();
    const close=/^(닫기|close|×|✕|x)$/i.test(t)||/(닫기|close)/i.test(aria+' '+title);
    if(!close)return false;
    const r=el.getBoundingClientRect();
    // Restrict to overlay-like close buttons near the right/top edge or inside dialogs.
    return !!el.closest('[role="dialog"],[aria-modal="true"]') || r.left>innerWidth*.72 || r.top<180;
  });
  for(const el of candidates.slice(0,4)){
    try{el.click()}catch{}
  }
}
async function naverOpenRows(button,onRows=()=>{}){
  const group=button?.getAttribute?.('data-shp-contents-type')||'';
  if(stopped()||!group||!naverSafeMainButton(button))return [];
  if(button.getAttribute('aria-expanded')!=='true'&&!naverMainRows(group).some(visible))button.click();
  const all=[],seen=new Set(); let stable=0;
  // Read and checkpoint before waiting: expiry cannot discard a half-read list.
  for(let round=0;round<2000&&!stopped();round++){
    const rows=naverMainRows(group).filter(visible);let added=0;
    for(const row of rows){
      const value=naverRowValue(row),id=row.getAttribute('data-shp-contents-id')||value;
      if(!value||seen.has(id))continue;
      seen.add(id);all.push(value);added++;
      onRows(value,id);
    }
    let moved=false;
    for(const box of new Set(rows.map(r=>r.closest('[role="listbox"]')).filter(Boolean))){
      const max=box.scrollHeight-box.clientHeight;
      if(box.scrollTop<max-2){box.scrollTop=Math.min(max,box.scrollTop+Math.max(120,box.clientHeight*.82));box.dispatchEvent(new Event('scroll',{bubbles:true}));moved=true;}
    }
    stable=added||moved?0:stable+1;
    if(all.length&&stable>=4)return all;
    if(!all.length&&stable>=30){collectionIncomplete=true;return all;}
    await new Promise(resolve=>setTimeout(resolve,Math.max(0,Math.min(50,optionWorkDeadline-Date.now()))));
  }
  return all;
}
const __b2bPhysicalOptionClickLocks=new Set();
const __b2bSelectedPathLocks=new Set();
const __b2bGroupOpenLocks=new WeakSet();
// Logical selection lock survives DOM re-renders. Key = full parent path + group + semantic value.
// This is independent of aria-selected/page-key, so stale SmartStore DOM cannot cause a second click.
const __b2bLogicalSelectionLocks=new Set();
// During a B2B capture, ignore only Naver's duplicate-selection alert so a stray site-side
// duplicate guard can never freeze the automation. Other alerts are left untouched.
const __b2bNativeAlert=window.alert?.bind(window);
window.alert=function(msg){
  const t=String(msg||'');
  if(t.includes('이미 선택한 옵션')){try{console.warn('[B2B Helper] duplicate-option alert suppressed:',t)}catch{};return;}
  return __b2bNativeAlert?__b2bNativeAlert(msg):undefined;
};
async function naverChoose(button,value,pathKey=""){
  if(stopped())return false;
  const group=button?.getAttribute?.('data-shp-contents-type')||'';
  if(!naverSafeMainButton(button))return false;
  if(variantAvailabilityFromText(value)==='OUT_OF_STOCK')return false;
  if(button.getAttribute('aria-expanded')!=='true'&&!naverMainRows(group).some(visible)){
    button.click();
    await new Promise(r=>setTimeout(r,Math.max(0,Math.min(50,optionWorkDeadline-Date.now()))));
  }
  let row=naverMainRows(group).filter(visible).find(r=>naverRowValue(r)===value);
  // A bulk-read virtual list can finish at the bottom. Locate a parent again by
  // scrolling (never by selecting another value) before its single physical click.
  if(!row){
    const boxes=[...new Set(naverMainRows(group).map(r=>r.closest('[role="listbox"]')).filter(Boolean))];
    for(const box of boxes){box.scrollTop=0;box.dispatchEvent(new Event('scroll',{bubbles:true}));}
    for(let i=0;i<2000&&!stopped()&&!row&&boxes.length;i++){
      await sleep(50);
      row=naverMainRows(group).filter(visible).find(r=>naverRowValue(r)===value);
      if(row)break;
      let moved=false;
      for(const box of boxes){const max=box.scrollHeight-box.clientHeight;if(box.scrollTop<max-2){box.scrollTop=Math.min(max,box.scrollTop+Math.max(120,box.clientHeight*.82));box.dispatchEvent(new Event('scroll',{bubbles:true}));moved=true;}}
      if(!moved)break;
    }
  }
  if(!row||row.getAttribute('aria-disabled')==='true'||variantAvailabilityFromText(naverRowValue(row))==='OUT_OF_STOCK'||stopped())return false;
  const key=JSON.stringify([pathKey,group,row.getAttribute('data-shp-contents-id')||value]);
  if(__b2bLogicalSelectionLocks.has(key))return false;
  __b2bLogicalSelectionLocks.add(key); // BEFORE the one and only physical click; never retry on throw.
  diag('dependent_value_clicked',{path:pathKey,group,value});
  row.click();
  // Wait for dependency hydration, including controls that do not exist until selection.
  let stable=0,last='';
  for(let i=0;i<30&&!stopped();i++){
    await new Promise(r=>setTimeout(r,Math.max(0,Math.min(50,optionWorkDeadline-Date.now()))));
    const buttons=naverMainOptionButtons(),index=buttons.findIndex(b=>b.getAttribute('data-shp-contents-type')===group);
    const next=buttons[index+1];
    const sig=buttons.slice(index+1).map(b=>[b.getAttribute('data-shp-contents-type'),b.getAttribute('aria-disabled'),b.getAttribute('data-shp-contents-id')].join(':')).join('|');
    stable=sig===last?stable+1:0;last=sig;
    if(next&&next.getAttribute('aria-disabled')!=='true'&&stable>=5)return !stopped();
  }
  return !stopped();
}
function groupsFromVariants(variants){
  const order=[],map=new Map();
  for(const v of variants||[])for(const o of v?.options||[]){
    const name=String(o?.name||'').trim(),value=String(o?.value||'').trim();if(!name||!value)continue;
    if(!map.has(name)){map.set(name,[]);order.push(name)}
    map.set(name,mergeOptionValuesPreferPrice(map.get(name),[value]));
  }
  return order.slice(0,30).map(name=>({name,values:map.get(name)}));
}

function inferRequiredSchema(probe,names){
  // Group arrays from the generic probe are NOT a schema: aliases and images occur there.
  const candidates=[];
  for(const group of probe.optionGroups||[]){
    if(group.name!=='standardCombinations')continue;
    for(const raw of group.values||[]){
      const value=String(raw);
      if(!/^_.*__$/.test(value)||/^https?:/.test(value))continue;
      const parts=value.replace(/^_/,'').replace(/__$/,'').split('_');
      if(parts.length&&parts.length<=30&&parts.every(Boolean))candidates.push(parts);
    }
  }
  const depths=new Set(candidates.map(p=>p.length));
  // Only use encoded paths when their depth agrees with the real named DOM controls.
  const paths=depths.size===1&&candidates[0]?.length===names.length?candidates:[];
  const seen=new Set();
  return {depth:names.length,paths:paths.filter(p=>{const k=JSON.stringify(p);if(seen.has(k))return false;seen.add(k);return true;})};
}

function optionIdentity(value){return String(value||'').replace(/\([+-]\s*[\d,]+\s*원\)/g,'').replace(/\(품절\)/g,'').trim();}
function variantPathKey(options){return JSON.stringify(options.map(o=>[o.name,optionIdentity(o.value)]));}
async function collectDependentMainVariants(){
  const variants=__b2bPartialVariants,index=new Map();
  const names=naverMainOptionButtons().map(b=>b.getAttribute('data-shp-contents-type'));
  for(const parts of expectedPaths){
    const options=parts.map((value,i)=>({name:names[i],value}));
    const key=variantPathKey(options);
    if(index.has(key))continue;
    index.set(key,variants.length);
    const record=sourceCombinationRecords.find(r=>JSON.stringify(String(r.encodedPath||'').replace(/^_/,'').replace(/__$/,'').split('_'))===JSON.stringify(parts));
    const verified=record&&record.additional_price!==null&&['AVAILABLE','OUT_OF_STOCK'].includes(record.availability);
    variants.push({options,additional_price:record?.additional_price??null,availability:record?.availability||'UNKNOWN',verification_status:verified?'VERIFIED':'NEEDS_REVIEW'});
  }
  const finish=(options,partial=false)=>{
    const leaf=options.at(-1).value,m=leaf.match(/\(([+-])\s*([\d,]+)\s*원\)/);
    const item={options,additional_price:partial?null:(m?(m[1]==='-'?-1:1)*Number(m[2].replace(/,/g,'')):0),
      availability:options.some(o=>variantAvailabilityFromText(o.value)==='OUT_OF_STOCK')?'OUT_OF_STOCK':'AVAILABLE',
      verification_status:partial?'NEEDS_REVIEW':'VERIFIED'};
    const key=variantPathKey(options);
    if(index.has(key))variants[index.get(key)]=item;
    else{index.set(key,variants.length);variants.push(item);}
  };
  async function walk(level,path){
    if(stopped())return;
    const scoped=variants.filter(v=>path.every((o,i)=>optionIdentity(v.options[i]?.value)===optionIdentity(o.value)));
    if(scoped.length&&scoped.every(v=>v.verification_status==='VERIFIED'||v.availability==='OUT_OF_STOCK'))return;
    if(level>=30){collectionIncomplete=true;return;}
    const buttons=naverMainOptionButtons(),button=buttons[level];
    if(!button){collectionIncomplete=true;return;}
    const name=button.getAttribute('data-shp-contents-type');
    const depth=Math.max(knownOptionDepth,buttons.length);
    // Disabled controls still count. Hidden, not-yet-created controls use passive schema depth.
    const leaf=level===depth-1;
    if(leaf&&depth===1&&!schemaDepth){
      collectionIncomplete=true;
      diag('unverified_terminal_depth',{reason:'No passive schema: hidden downstream controls cannot be ruled out without selecting a terminal candidate.'});
    }
    const ids=new Map();
    const values=await naverOpenRows(button,(value,id)=>{
      ids.set(value,id);
      if(leaf)finish([...path,{name,value,id}]);
    });
    diag('branch_read',{path,group:name,leaf,values:values.length});
    if(leaf)return;
    for(const value of values){
      if(stopped())break;
      const nextPath=[...path,{name,value,id:ids.get(value)}];
      if(variantAvailabilityFromText(value)==='OUT_OF_STOCK'){
        const matches=variants.filter(v=>nextPath.every((o,i)=>optionIdentity(v.options[i]?.value)===optionIdentity(o.value)));
        if(matches.length)for(const item of matches){item.availability='OUT_OF_STOCK';item.options[level]={...item.options[level],value};}
        else finish(nextPath,true);
        diag('sold_out_not_clicked',{path:nextPath});continue;
      }
      try{
        const current=naverMainOptionButtons()[level];
        if(!await naverChoose(current,value,JSON.stringify(nextPath.map((o,i)=>[i,o.name,o.id])))){
          collectionIncomplete=true;continue;
        }
        await walk(level+1,nextPath);
      }catch(error){collectionIncomplete=true;diag('branch_error',{path:nextPath,error:String(error)});}
    }
  }
  try{if(naverMainOptionButtons().length)await walk(0,[]);}
  catch(error){collectionIncomplete=true;diag('traversal_error',{error:String(error)});}
  finally{return variants;}
}
function naverExtraGroupsReadOnly(){
  const rows=[...document.querySelectorAll('a[role="option"][data-shp-area="pcs.addedoptselect"][data-shp-area-id="addedoptselect"][data-shp-contents-type]')];
  const order=[],map=new Map();
  for(const row of rows){
    const name=String(row.getAttribute('data-shp-contents-type')||'').trim();
    const id=String(row.getAttribute('data-shp-contents-id')||'').trim();
    const raw=String(row.innerText||row.textContent||'').replace(/\s+/g,' ').trim();
    if(!name||!id)continue;
    const delta=(raw.match(/\(([+-])\s*([\d,]+)\s*원\)/)||[])[0]||'';
    const sold=/품절/.test(raw)?' (품절)':'';
    const value=`${id}${delta?' '+delta:''}${sold}`.trim();
    if(!map.has(name)){map.set(name,[]);order.push(name)}
    map.set(name,mergeOptionValuesPreferPrice(map.get(name),[value]));
  }
  return order.map(name=>({name,values:map.get(name)}));
}
async function collectOptionsIsolated(aiPlan=null){
  const result={main:[],extra:[],variants:[],error:''},errors=[];
  diag('ai_option_collection_started',{
    classification:aiPlan?.classification?.type||'UNKNOWN',
    planned_actions:Array.isArray(aiPlan?.plan)?aiPlan.plan:[]
  });
  if(aiPlan?.strategy==='DIRECT_INTERNAL_DATA'&&!naverMainOptionButtons().length){
    diag('dom_click_skipped',{reason:'complete_internal_data'});
    return result;
  }
  try{
    // V78: SmartStore's semantic required-option DOM is handled ONLY by the dependent
    // collector below. Do not run the old generic main pass first: that pass clicks 50m/120m
    // once, then the dependent collector clicks them again, producing 50→120→50→120 and
    // Naver's "이미 선택한 옵션입니다." alert.
    for(const ms of [180,260,400,600]){if(headingY(/^옵션\s*선택(?:\s*\(필수\))?/i)!=null||naverMainOptionButtons().length)break;await sleep(ms)}
    if(!naverMainOptionButtons().length) result.main=await readOptionSection('main');
  }catch(e){errors.push(`main:${String(e)}`);console.warn('[B2B Helper] main option pass stopped; preserving partial/base capture',e)}
  // SmartStore semantic path now performs the one and only required-option traversal.
  // Parent order is one-pass (50m complete -> 120m complete); leaf rows are read-only.
  try{result.variants=await collectDependentMainVariants()}
  catch(e){errors.push(`variants:${String(e)}`);console.warn('[B2B Helper] dependent option pass stopped; preserving main options',e)}
  try{
    if(naverMainOptionButtons().length){
      result.extra=naverExtraGroupsReadOnly();
      for(const button of document.querySelectorAll('a[role="button"][data-shp-area="pcs.addedoptselect"][data-shp-area-id="addedoptselect"]')){
        if(stopped())break;
        if(button.getAttribute('aria-expanded')!=='true')button.click();
        await sleep(100);
        result.extra=mergeOptionGroups(result.extra,naverExtraGroupsReadOnly());
      }
      // Additional options are read-only during SmartStore capture: never click benefit/cart UI.
      closeNaverIntrusiveLayers();
    }else result.extra=await readOptionSection('extra');
  }
  catch(e){errors.push(`extra:${String(e)}`);console.warn('[B2B Helper] additional option pass stopped; preserving earlier results',e)}
  result.error=errors.join(' | ');
  return result;
}
function availability(){
  const buy=[...document.querySelectorAll('button,a')].filter(e=>visible(e)&&/(?:^|\s)(?:N\s*)?구매하기(?:\s|$)|바로\s*구매|장바구니/i.test(text(e)));
  const enabled=buy.some(e=>!e.disabled&&e.getAttribute('aria-disabled')!=='true'&&!/disabled|품절|판매중지|구매불가/i.test(String(e.className||'')+' '+text(e)));
  if(enabled)return 'AVAILABLE';
  const disabledBuy=buy.some(e=>e.disabled||e.getAttribute('aria-disabled')==='true'||/품절|판매\s*중지|구매\s*불가/i.test(text(e)+' '+String(e.className||'')));
  if(disabledBuy)return 'OUT_OF_STOCK';
  // Only accept an explicit short out-of-stock label in the upper purchase side. Never scan the whole page.
  const sold=[...document.querySelectorAll('strong,b,span,div')].filter(visible).filter(e=>{const r=e.getBoundingClientRect();const s=text(e);return r.top<1000&&r.left>innerWidth*.42&&s.length<80&&/^(품절|일시품절|판매\s*중지|구매\s*불가|현재\s*품절)$/.test(s)});
  return sold.length?'OUT_OF_STOCK':'UNKNOWN';
}
function priceKey(v){
  return String(v||'').replace(/\([+-]\s*[\d,]+\s*원\)/g,'').replace(/\s+/g,' ').trim().replace(/^_+|_+$/g,'').trim();
}
function enrichVisiblePrices(domGroups,probeGroups,probeVariants){
  const priceMap=new Map();
  const add=(label,delta)=>{
    const k=priceKey(label); const n=Number(delta);
    if(k&&Number.isFinite(n)&&n!==0&&!priceMap.has(k))priceMap.set(k,n);
  };
  for(const g of Array.isArray(probeGroups)?probeGroups:[]){
    for(const v of Array.isArray(g?.values)?g.values:[]){
      const m=String(v||'').match(/\(([+-])\s*([\d,]+)\s*원\)/);
      if(m)add(v,(m[1]==='-'?-1:1)*Number(m[2].replace(/,/g,'')));
    }
  }
  for(const v of Array.isArray(probeVariants)?probeVariants:[]){
    const delta=Number(v?.additional_price);
    if(!Number.isFinite(delta)||delta===0)continue;
    for(const o of Array.isArray(v?.options)?v.options:[])add(o?.value,delta);
  }
  return (Array.isArray(domGroups)?domGroups:[]).map(g=>({
    ...g,
    values:(Array.isArray(g?.values)?g.values:[]).map(v=>{
      if(/[+-]\s*[\d,]+\s*원/.test(String(v||'')))return v;
      const d=priceMap.get(priceKey(v));
      return Number.isFinite(d)&&d!==0?`${v} (${d>0?'+':''}${d.toLocaleString('ko-KR')}원)`:v;
    })
  }));
}
function enrichFromDedicatedOptionPrices(groups,entries){
  const prices=new Map();
  for(const entry of Array.isArray(entries)?entries:[]){
    const key=priceKey(entry?.label).replace(/[\s_]+/g,'').toLowerCase();
    const delta=Number(entry?.delta);
    if(!key||!Number.isFinite(delta)||delta===0)continue;
    if(!prices.has(key))prices.set(key,delta);
  }
  return (Array.isArray(groups)?groups:[]).map(group=>({
    ...group,
    values:(Array.isArray(group?.values)?group.values:[]).map(value=>{
      if(/[+-]\s*[\d,]+\s*원/.test(String(value||'')))return value;
      const key=priceKey(value).replace(/[\s_]+/g,'').toLowerCase();
      const delta=prices.get(key);
      return Number.isFinite(delta)&&delta!==0?`${value} (${delta>0?'+':''}${delta.toLocaleString('ko-KR')}원)`:value;
    })
  }));
}

function normalizeExtraGroupName(name){
  return String(name||'').replace(/\s+/g,' ').trim();
}
function extraValueKey(v){
  return priceKey(String(v||'')).replace(/[\s_]+/g,'').toLowerCase();
}
function extraNameIsAuto(name){
  const n=normalizeExtraGroupName(name);
  return !n || /^추가\s*옵션\s*\d+$/i.test(n) || /^추가옵션\d+$/i.test(n) || /^(?:supplementProducts?|additionalProducts?|options?|items?|values?)$/i.test(n);
}
function extraNameIsMeaningful(name,productName=''){
  const n=normalizeExtraGroupName(name),p=normalizeExtraGroupName(productName);
  return !!n&&!extraNameIsAuto(n)&&n!==p&&n.length<=60&&!/^https?:\/\//i.test(n);
}
function valueSetSimilarity(a,b){
  if(!a.size||!b.size)return 0;
  let hit=0;for(const v of a)if(b.has(v))hit++;
  return hit/Math.min(a.size,b.size);
}
function cleanAndDedupAdditionalGroups(groups,mainGroups,productName=''){
  const raw=(Array.isArray(groups)?groups:[]).map((g,i)=>({
    name:normalizeExtraGroupName(g?.name||`추가옵션${i+1}`),
    values:uniq((Array.isArray(g?.values)?g.values:[]).map(v=>String(v||'').replace(/\s+/g,' ').trim()).filter(optionValueOK))
  })).filter(g=>g.values.length);
  if(!raw.length)return [];

  const mainSets=(Array.isArray(mainGroups)?mainGroups:[]).map(g=>new Set((g?.values||[]).map(extraValueKey).filter(Boolean)));
  let work=raw.filter(g=>{
    const set=new Set(g.values.map(extraValueKey).filter(Boolean));
    let best=0;for(const m of mainSets)best=Math.max(best,valueSetSimilarity(set,m));
    // Mandatory choices appearing again below are not add-ons.
    return !(set.size>=2&&best>=0.80);
  });

  // Same add-on values are sometimes exposed twice: once with the real heading (e.g. '도래류')
  // and once as an internal placeholder (e.g. '추가옵션5'). Keep the real buyer-visible heading.
  const consumed=new Set(),dedup=[];
  for(let i=0;i<work.length;i++){
    if(consumed.has(i))continue;
    const a=work[i],as=new Set(a.values.map(extraValueKey).filter(Boolean));
    const cluster=[i];
    for(let j=i+1;j<work.length;j++){
      if(consumed.has(j))continue;
      const bs=new Set(work[j].values.map(extraValueKey).filter(Boolean));
      const sim=valueSetSimilarity(as,bs);
      if(sim>=0.92&&Math.max(as.size,bs.size)<=Math.min(as.size,bs.size)*1.20)cluster.push(j);
    }
    let best=cluster[0];
    for(const j of cluster){
      const bj=work[j],bb=work[best];
      const js=extraNameIsMeaningful(bj.name,productName)?2:(extraNameIsAuto(bj.name)?0:1);
      const bs=extraNameIsMeaningful(bb.name,productName)?2:(extraNameIsAuto(bb.name)?0:1);
      if(js>bs)best=j;
    }
    cluster.forEach(j=>consumed.add(j));
    dedup.push(work[best]);
  }
  work=dedup;

  // Drop accidental super-groups that are merely a union of several real add-on dropdowns.
  // This is what produced a giant '추가 옵션 1' containing 도래/채비/봉돌/튜닝/미끼/기타 together.
  const meaningful=work.filter(g=>extraNameIsMeaningful(g.name,productName));
  work=work.filter(g=>{
    const gs=new Set(g.values.map(extraValueKey).filter(Boolean));
    if(gs.size<8)return true;
    let coveredGroups=0,coveredValues=new Set();
    for(const h of meaningful){
      if(h===g)continue;
      const hs=new Set(h.values.map(extraValueKey).filter(Boolean));
      const contained=[...hs].filter(v=>gs.has(v));
      if(hs.size>=2&&contained.length/hs.size>=0.90){
        coveredGroups++;contained.forEach(v=>coveredValues.add(v));
      }
    }
    const looksSynthetic=extraNameIsAuto(g.name)||normalizeExtraGroupName(g.name)===normalizeExtraGroupName(productName)||g.name.length>60;
    if(coveredGroups>=2&&coveredValues.size/gs.size>=0.65&&looksSynthetic)return false;
    return true;
  });

  return work.slice(0,100);
}
function repairAdditionalGroupNames(groups,probeGroups,productName=''){
  const probes=(Array.isArray(probeGroups)?probeGroups:[]).filter(g=>extraNameIsMeaningful(g?.name,productName));
  return (Array.isArray(groups)?groups:[]).map(group=>{
    if(extraNameIsMeaningful(group?.name,productName))return group;
    const own=new Set((group?.values||[]).map(extraValueKey).filter(Boolean));
    let best=null,bestScore=0;
    for(const probe of probes){
      const score=valueSetSimilarity(own,new Set((probe?.values||[]).map(extraValueKey).filter(Boolean)));
      if(score>bestScore){bestScore=score;best=probe}
    }
    return best&&bestScore>=0.60?{...group,name:normalizeExtraGroupName(best.name)}:{...group,name:''};
  });
}

let busy=false;
async function collect(){
  if(busy)return;busy=true;
  stopRequested=false;collectionIncomplete=false;
  optionWorkDeadline=Date.now()+180000;optionHardDeadline=optionWorkDeadline;
  __b2bPartialVariants=[];__b2bLogicalSelectionLocks.clear();
  optionDiagnostics={
    version:'2.61.14',
    started_at:Date.now(),
    product_id:productIdFromUrl(),
    page_url:cleanSourceUrl(),
    events:[]
  };
  diag('capture_started',{viewport:{width:innerWidth,height:innerHeight},device_pixel_ratio:window.devicePixelRatio||1});
  const removeShopperActionGuard=installShopperActionGuard();
  const removeViewportGuard=installCaptureViewportGuard();
  try{
    await sleep(1200);
    // Freeze already-working core fields BEFORE gallery/option clicks. Option failures can never
    // erase or replace product name, store, price, shipping or supply status.
    const detectedStore=storeName();
    const detectedShipping=shipping();
    const detectedPrice=price();
    const base={
      productName:productName(detectedStore),
      storeName:detectedStore,
      storeUrl:location.origin+'/'+location.pathname.split('/').filter(Boolean)[0],
      price:detectedPrice,
      shippingFee:detectedShipping,
      availability:availability()
    };
    // Different path from the old click-only collector: ask the MAIN-world passive network/state probe first.
    // It sees SmartStore's hydrated JSON/fetch/XHR data without moving the page.
    let probe={images:[],optionGroups:[],additionalOptionGroups:[],optionVariants:[],debug:{}},optionPriceEntries=[];
    try{[probe,optionPriceEntries]=await Promise.all([requestMainProbe(),requestOptionPriceProbe()])}catch(e){console.warn('[B2B Helper] passive probe failed',e)}

    let gallery=[];
    try{gallery=await galleryImages()}catch(e){console.warn('[B2B Helper] gallery fallback failed, base capture preserved',e)}
    const total=(()=>{try{const m=findMainImage();return galleryTotal(galleryPanel(m))}catch{return null}})();
    let imgs=uniq([...(gallery||[]),...((probe.images||[]).map(normImg).filter(validProductImgUrl))]);
    if(total&&imgs.length>=total)imgs=imgs.slice(0,total);
    else imgs=imgs.slice(0,100);

    // First AI pass MUST happen before any option click. It judges the passive DOM/network
    // evidence and creates the collection plan; the collector then exhaustively follows
    // every required dependency and reads every additional-option group.
    const aiEngine=window.B2BAIOptionEngine;
    const requiredControls=requiredOptionControlCount();
    let aiPlan=aiEngine?.firstPass?aiEngine.firstPass({
      ...base,
      imageUrls:imgs,
      optionGroups:probe.optionGroups||[],
      additionalOptionGroups:probe.additionalOptionGroups||[],
      optionVariants:probe.optionVariants||[],
      rawNetworkOptionGroups:probe.optionGroups||[],
      rawNetworkAdditionalOptionGroups:probe.additionalOptionGroups||[],
      rawNetworkOptionVariants:probe.optionVariants||[],
      optionDiagnostics:{...optionDiagnostics,phase:'PRE_CLICK'}
    }):null;
    if(requiredControls>=2&&aiPlan){
      aiPlan={...aiPlan,strategy:'TARGETED_CLICK_FALLBACK',plan:[
        'CAPTURE_CORE','READ_ALL_INTERNAL_PRODUCT_DATA','CLICK_ONLY_MISSING_REQUIRED_COMBINATIONS',
        ...((probe.additionalOptionGroups||[]).length?['READ_ALL_ADDITIONAL_GROUPS']:[]),'DEDUPLICATE','SECOND_PASS_AUDIT'
      ],forced_by:'MULTIPLE_REQUIRED_CONTROLS_ALWAYS_VERIFY'};
    }
    diag('ai_click_plan_created',{
      classification:aiPlan?.classification?.type||'UNKNOWN',
      confidence:aiPlan?.classification?.confidence||0,
      required_controls:requiredControls,
      forced_by:aiPlan?.forced_by||'',
      planned_actions:Array.isArray(aiPlan?.plan)?aiPlan.plan:[]
    });

    // During an explicit B2B import, read the actual visible purchase controls as the authoritative
    // DISPLAY layer. This preserves labels exactly as the buyer sees them, including +/- option prices.
    // The passive network/state probe is still kept as RAW/fallback data for mapping and future ordering.
    let domOpt={main:[],extra:[],variants:[],error:''};
    __b2bPartialVariants=[];
    // V40 fail-safe: interactive option verification is useful, but it must never leave
    // the B2B screen waiting forever. Give the purchase-control pass a hard budget; when
    // SmartStore changes DOM or a dropdown refuses to answer, return the passive probe data.
    // V2.61.9: strict three-minute total option budget. At 180 seconds, stop traversal
    // and return all complete values collected so far instead of continuing indefinitely.
    const requiredNames=naverMainOptionButtons().map(b=>b.getAttribute('data-shp-contents-type'));
    const schema=inferRequiredSchema(probe,requiredNames);
    schemaDepth=schema.depth;knownOptionDepth=schema.depth;expectedPaths=schema.paths;
    sourceCombinationRecords=probe.standardCombinationRecords||[];
    diag('required_schema',{names:requiredNames,depth:schemaDepth,expected_paths:expectedPaths.length,
      ignored_probe_group_count:(probe.optionGroups||[]).length});
    try{domOpt=await collectOptionsIsolated(aiPlan)}catch(e){
      diag('option_collection_error',{error:String(e),partial_variants:__b2bPartialVariants.length});
      // Hard guarantee: even if timeout escapes from any nested stage, keep every completed DFS leaf.
      if(__b2bPartialVariants.length)domOpt={...domOpt,variants:__b2bPartialVariants.slice(),error:String(e)};
      if(String(e).includes('B2B_OPTION_TIME_LIMIT')) console.warn('[B2B Helper] 3-minute option limit reached; saving partial data');
      else console.warn('[B2B Helper] DOM option verification failed',e);
    } finally { stopped(); }
    // A nested collector may have returned without propagating its partial snapshot. Never lose it.
    if((!Array.isArray(domOpt.variants)||!domOpt.variants.length)&&__b2bPartialVariants.length){
      domOpt.variants=__b2bPartialVariants.slice();
    }

    const domMain=mergeOptionGroups(domOpt.main,groupsFromVariants(domOpt.variants));
    const domExtra=mergeOptionGroups(domOpt.extra,[]);
    const probeMain=mergeOptionGroups(probe.optionGroups,[]);
    const probeExtra=mergeOptionGroups(probe.additionalOptionGroups,[]);
    // V73: when the exact SmartStore semantic DOM path succeeded, keep its clean
    // required-option groups as-is. Generic probe enrichment can inject full variant
    // descriptions back into a single option value, causing duplicated text such as
    // "호수 4.0 · 길이 50m · 호수 ...".
    const exactDomMain=naverMainOptionButtons().length>0 && domMain.length>0;
    const baseMainGroups=exactDomMain?domMain:(domMain.length?enrichVisiblePrices(domMain,probeMain,probe.optionVariants):probeMain);
    let mainGroups=exactDomMain?baseMainGroups:enrichFromDedicatedOptionPrices(baseMainGroups,optionPriceEntries);
    let extraGroups=domExtra.length?enrichVisiblePrices(domExtra,probeExtra,probe.optionVariants):probeExtra;
    extraGroups=repairAdditionalGroupNames(extraGroups,probeExtra,base.productName);

    // V41: normalize add-ons by the actual buyer-visible dropdown groups.
    // Internal duplicate aliases and accidental mega-groups are kept in RAW probe data only,
    // never shown as separate B2B additional options.
    extraGroups=cleanAndDedupAdditionalGroups(extraGroups,mainGroups,base.productName);
    const domVariants=Array.isArray(domOpt.variants)?domOpt.variants:[];
    const probeVariants=Array.isArray(probe.optionVariants)?probe.optionVariants:[];
    // Prefer the source that preserves the deepest real dependency chain. A two-level DOM
    // partial result must not hide a three-level network combination (종류→색상→호수).
    const variantDepth=rows=>Math.max(0,...rows.map(v=>Array.isArray(v?.options)?v.options.length:0));
    const domDepth=variantDepth(domVariants),probeDepth=variantDepth(probeVariants);
    // SmartStore semantic DOM traversal is deliberately depth-first and stable:
    // 1-1-1, 1-1-2, 1-2-1 ... 2-1-1. Never replace it with network rows merely because
    // the probe reports a deeper/duplicated shape; doing so destroys order and reintroduces duplicates.
    const finalVariants=domVariants.length?domVariants:probeVariants;
    mainGroups=mergeOptionGroups(groupsFromVariants(finalVariants),mainGroups);
    const unresolved=finalVariants.filter(v=>v.verification_status==='NEEDS_REVIEW');
    if(unresolved.length)collectionIncomplete=true;
    diag('metadata_audit',{unverified:unresolved.length,paths:unresolved.map(v=>v.options)});
    const identity=value=>String(value||'').replace(/\([+-]\s*[\d,]+\s*원\)/g,'').replace(/\(품절\)/g,'').trim();
    const capturedKeys=new Set(finalVariants.map(v=>JSON.stringify((v.options||[]).map(o=>identity(o.value)))));
    const missingPaths=expectedPaths.filter(p=>!capturedKeys.has(JSON.stringify(p)));
    if(missingPaths.length)collectionIncomplete=true;
    diag('coverage_audit',{expected:expectedPaths.length,captured:finalVariants.length,missing:missingPaths.length,missing_paths:missingPaths});
    const metaTitle=meta('meta[property="og:title"]','meta[name="twitter:title"]');
    const metaPrice=meta('meta[property="product:price:amount"]','meta[property="og:price:amount"]','meta[itemprop="price"]');
    const rawData={
      ...base,
      imageUrls:imgs,
      optionGroups:mainGroups,
      additionalOptionGroups:extraGroups,
      optionVariants:finalVariants,
      rawNetworkOptionGroups:probeMain,
      rawNetworkAdditionalOptionGroups:probeExtra,
      rawNetworkOptionVariants:probeVariants
      ,normalizationCandidates:{
        productNames:[base.productName,probe.productName,metaTitle],
        storeNames:[base.storeName,probe.storeName],
        prices:[base.price,probe.price,metaPrice],
        shippingFees:[base.shippingFee,probe.shippingFee],
        imageUrls:[imgs,gallery,probe.images],
        optionGroups:[mainGroups,probeMain],
        additionalOptionGroups:[extraGroups,probeExtra],
        optionVariants:[finalVariants,probeVariants]
      }
      ,rawDedicatedOptionPrices:optionPriceEntries
      ,optionDiagnostics:{
        ...optionDiagnostics,
        completed_at:Date.now(),
        elapsed_ms:Date.now()-optionDiagnostics.started_at,
        dom_main_groups:domMain,
        probe_main_groups:probeMain,
        dedicated_price_entries:optionPriceEntries,
        final_main_groups:mainGroups,
        collection_error:domOpt.error||''
      }
    };
    // Stage 1: one isolated normalization layer. Collection remains untouched; only
    // the final handoff is cleaned and deduplicated into a stable schema.
    const aiFirst=aiPlan||((aiEngine?.firstPass)?aiEngine.firstPass(rawData):null);
    const dataNormalize=window.B2BOptionAnalyzer?.normalizePayload;
    let normalized=rawData;
    try{normalized=dataNormalize?dataNormalize(rawData):rawData;}catch(e){collectionIncomplete=true;}
    normalized.optionVariants=finalVariants;
    normalized.collectionStatus=(collectionIncomplete||stopRequested||domOpt.error)?
      (finalVariants.length||base.productName?'PARTIAL':'FAILED_WITH_NO_DATA'):'COMPLETE';
    const aiSecond=aiEngine?.secondPass?aiEngine.secondPass(normalized,rawData,aiFirst):null;
    const data={...normalized,aiJudgment:{mode:'URL_INTERNAL_FIRST_WITH_CLICK_FALLBACK',first_pass:aiFirst,second_pass:aiSecond}};
    const state={__B2B_DIRECT__:data};
    const payload={url:cleanSourceUrl(),title:document.title,html:document.documentElement.outerHTML.slice(0,7000000),state};
    // Completion is not declared until the B2B server ACKs the saved capture.
    // The background worker closes the temporary Naver tab only after this ACK.
    await new Promise((resolve,reject)=>{
      chrome.runtime.sendMessage({type:'B2B_NAVER_CAPTURE',payload},(res)=>{
        if(chrome.runtime.lastError)return reject(new Error(chrome.runtime.lastError.message));
        if(!res?.ok)return reject(new Error(res?.error||'B2B capture save rejected'));
        console.info('[B2B Helper] capture saved and acknowledged',data);
        resolve(res);
      });
    });
  }finally{
    try{removeViewportGuard()}catch{}
    try{removeShopperActionGuard()}catch{}
    optionWorkDeadline=Infinity;optionHardDeadline=Infinity;
    optionDiagnostics=null;
    busy=false
  }
}

function cleanSourceUrl(){
  try{const u=new URL(location.href);u.searchParams.delete('__b2b_capture');return u.toString()}catch{return location.href}
}
chrome.runtime.onMessage.addListener(msg=>{if(msg?.type==='B2B_CAPTURE_NOW')collect()});
// Deliberately no load timer and no MutationObserver.
// This content script stays completely idle during ordinary Naver browsing.
})();
