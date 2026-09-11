const TOKEN_KEY='b2b_v1_access_token';
const $=id=>document.getElementById(id);
let currentUser=null, suppliers=[], products=[], pricing=[], logs=[], sourcingItems=[], orders=[], purchases=[], shipments=[], trackers=[], aiDrafts=[], automationRules=[], integrations=[];

function token(){return localStorage.getItem(TOKEN_KEY)}
function money(v){return `${Math.round(Number(v||0)).toLocaleString('ko-KR')}원`}
function pct(v){return `${Number(v||0).toFixed(1)}%`}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function toast(msg){const t=$('toast');t.textContent=msg;t.classList.remove('hidden');setTimeout(()=>t.classList.add('hidden'),2600)}
async function api(path,opts={}){const headers={...(opts.headers||{})};if(!(opts.body instanceof FormData))headers['Content-Type']='application/json';if(token())headers.Authorization=`Bearer ${token()}`;const res=await fetch(path,{...opts,headers});const type=res.headers.get('content-type')||'';if(!res.ok){let d='요청 처리 실패';try{const j=await res.json();d=j.detail||j.message||d}catch{}throw new Error(Array.isArray(d)?JSON.stringify(d):d)}return type.includes('application/json')?res.json():res.blob()}
function showApp(show){$('authSection').classList.toggle('hidden',show);$('appSection').classList.toggle('hidden',!show)}
function setPage(name){document.querySelectorAll('[data-page-section]').forEach(s=>s.classList.toggle('active',s.dataset.pageSection===name));document.querySelectorAll('.nav-item[data-page]').forEach(b=>b.classList.toggle('active',b.dataset.page===name));document.querySelector('.sidebar')?.classList.remove('open');window.scrollTo({top:0,behavior:'smooth'});if(name==='pricing')loadPriceTracking();if(name==='logs')loadLogs();if(name==='settings')loadPlan();if(name==='sourcing')loadSourcing();if(name==='orders')loadOrders();if(name==='purchase')loadPurchases();if(name==='shipping')loadShipments();if(name==='ai')loadAiDrafts();if(name==='settings'){loadIntegrations();loadReportSummary();loadTaxReserve()}}
function openModal(id){$('modalBackdrop').classList.remove('hidden');$(id).classList.remove('hidden')}
function closeModals(){ $('modalBackdrop').classList.add('hidden');document.querySelectorAll('.modal').forEach(m=>m.classList.add('hidden')) }
function productStatus(p){return String(p.status||'STOP').toUpperCase()==='SELL'?'SELL':'STOP'}
function statusHtml(p){const s=productStatus(p);return `<span class="status ${s==='SELL'?'sell':'stop'}">${s==='SELL'?'판매':'중지'}</span>`}
function productProfit(p){return Number(p.net_profit??p.calculation?.net_profit??0)}
function productMargin(p){return Number(p.margin_rate??p.calculation?.margin_rate??0)}
function supplierName(id){return suppliers.find(s=>s.id===id)?.name||'-'}
function thumbHtml(p){if(p.main_image_url)return `<div class="thumb"><img src="${esc(p.main_image_url)}" alt="" onerror="this.remove()"></div>`;return `<div class="thumb">상품</div>`}

async function checkSession(){if(!token()){showApp(false);return}try{const me=await api('/auth/me');currentUser=me.user;showApp(true);const email=currentUser.email||'-';if($('sidebarUserEmail'))$('sidebarUserEmail').textContent=email;$('topUserEmail').textContent=email;if($('accountMenuEmail'))$('accountMenuEmail').textContent=email;$('settingsEmail').textContent=email;$('settingsRole').textContent=currentUser.role==='admin'?'관리자':'사용자';await Promise.all([loadSuppliers(),loadProducts(),loadPriceTracking(),loadLogs(),loadPlan(),loadSourcing(),loadOrders(),loadPurchases(),loadShipments(),loadAiDrafts()]);renderHome()}catch(e){localStorage.removeItem(TOKEN_KEY);showApp(false);toast('로그인이 필요합니다.')}}

async function loadSuppliers(){const d=await api('/suppliers/');suppliers=d.suppliers||[];renderSupplierOptions();renderSuppliers()}
function renderSupplierOptions(){for(const id of ['productSupplier','productSupplierFilter','sourcingSupplier']){const el=$(id);if(!el)continue;const first=(id==='productSupplier'||id==='sourcingSupplier')?'<option value="">공급처 없음</option>':'<option value="">전체 공급처</option>';el.innerHTML=first+suppliers.map(s=>`<option value="${esc(s.id)}">${esc(s.name)}</option>`).join('')}}
function renderSuppliers(){const body=$('supplierTableBody');if(!body)return;body.innerHTML=suppliers.length?suppliers.map(s=>`<tr><td><strong>${esc(s.name)}</strong></td><td>${esc(s.memo||'-')}</td><td>${esc((s.created_at||'').slice(0,10)||'-')}</td><td><div class="row-actions"><button class="tiny-btn" data-edit-supplier="${esc(s.id)}">수정</button><button class="tiny-btn danger" data-delete-supplier="${esc(s.id)}">삭제</button></div></td></tr>`).join(''):'<tr><td colspan="4" class="muted">등록된 공급처가 없습니다.</td></tr>'}

async function loadProducts(){const q=new URLSearchParams();if($('productSearch')?.value.trim())q.set('q',$('productSearch').value.trim());if($('productStatusFilter')?.value)q.set('status',$('productStatusFilter').value);if($('productSupplierFilter')?.value)q.set('supplier_id',$('productSupplierFilter').value);const d=await api(`/products/${q.toString()?`?${q}`:''}`);products=d.products||[];renderProducts();renderHome()}
function renderProducts(){const b=$('productTableBody');if(!b)return;b.innerHTML=products.length?products.map(p=>`<tr><td><div style="display:flex;align-items:center;gap:9px">${thumbHtml(p)}<strong>${esc(p.name)}</strong></div></td><td>${esc(p.sku||'-')}</td><td>${esc(supplierName(p.supplier_id))}</td><td>${money(p.purchase_price??p.supply_price)}</td><td>${money(p.selling_price??p.sale_price)}</td><td><strong>${money(productProfit(p))}</strong></td><td>${pct(productMargin(p))}</td><td>${statusHtml(p)}</td><td><div class="row-actions"><button class="tiny-btn primary" data-edit-product="${esc(p.id)}">수정</button><button class="tiny-btn danger" data-delete-product="${esc(p.id)}">삭제</button></div></td></tr>`).join(''):'<tr><td colspan="9" class="muted">등록된 상품이 없습니다.</td></tr>';b.querySelectorAll('[data-edit-product]').forEach(btn=>btn.onclick=()=>editProduct(btn.dataset.editProduct))}

async function loadPricing(){return loadPriceTracking()}
function pricingMin(r){return Number(r.minimum_sellable_price??r.break_even_price??0)}
function pricingCurrent(r){return Number(r.selling_price??r.current_selling_price??r.product?.selling_price??0)}
async function loadPriceTracking(){try{const [d,a]=await Promise.all([api('/price-tracking/'),api('/automation/rules')]);trackers=d.tracking||[];automationRules=a.rules||[];pricing=trackers.map(x=>({product_id:x.product?.id,product_name:x.product?.name,selling_price:x.product?.selling_price,minimum_sellable_price:x.minimum_sellable_price,status:x.product?.status,net_profit:x.product?.net_profit}));renderPricing();renderHome()}catch(e){trackers=[];automationRules=[];if($('pricingTableBody'))$('pricingTableBody').innerHTML='<tr><td colspan="8">가격 추적 데이터를 불러오지 못했습니다.</td></tr>'}}
function renderPricing(){const b=$('pricingTableBody');if(!b)return;const rm=new Map(automationRules.map(x=>[x.product?.id,x]));b.innerHTML=trackers.length?trackers.map(x=>{const p=x.product||{},t=x.tracker||{},a=rm.get(p.id)||{},r=a.rule||{},cur=Number(p.selling_price||0),min=Number(x.minimum_sellable_price||0),comp=t.competitor_price,target=a.target_price,act=a.action||'WAIT';return `<tr><td><strong>${esc(p.name||'-')}</strong></td><td><input class="inline-price-input" data-competitor-input="${esc(p.id)}" type="number" min="0" value="${comp??''}" placeholder="경쟁가"/></td><td>${money(cur)}</td><td><strong>${money(min)}</strong></td><td><label class="switch-label"><input type="checkbox" data-auto-enabled="${esc(p.id)}" ${Number(r.enabled??1)?'checked':''}/>사용</label></td><td><input class="inline-price-input small" data-undercut-input="${esc(p.id)}" type="number" min="0" value="${Number(r.undercut_amount??100)}"/></td><td><span class="status ${act==='STOP'?'stop':act==='ADJUST'?'sell':'gray'}">${act==='STOP'?'자동 중지':act==='ADJUST'?`→ ${money(target)}`:'경쟁가 대기'}</span></td><td><div class="row-actions"><button class="tiny-btn primary" data-save-competitor="${esc(p.id)}">경쟁가 저장</button><button class="tiny-btn" data-save-auto-rule="${esc(p.id)}">규칙 저장</button></div></td></tr>`}).join(''):'<tr><td colspan="8" class="muted">추적할 상품이 없습니다. 상품 관리에서 상품을 먼저 등록하세요.</td></tr>'}
async function loadAutomationHistory(){try{const d=await api('/automation/history');const el=$('automationHistory');const rows=d.history||[];el.innerHTML=rows.length?rows.map(x=>`<div class="log-item"><time>${esc(x.created_at||'-')}</time><strong>${esc(x.action||'-')}</strong><p>${money(x.old_price)} → ${money(x.new_price)} · 경쟁가 ${money(x.competitor_price)} · 최저가능 ${money(x.minimum_sellable_price)} · ${esc(x.reason||'')}</p></div>`).join(''):'<div class="muted">자동화 실행 이력이 없습니다.</div>'}catch(e){toast(e.message)}}

async function loadLogs(){try{const d=await api('/activity-logs/?limit=100');logs=d.logs||[];renderLogs();renderHome()}catch{logs=[]}}
function logTitle(l){return l.message||l.action||l.event_type||l.category||'시스템 작업'}
function renderLogs(){const el=$('logsList');if(!el)return;el.innerHTML=logs.length?logs.map(l=>`<div class="log-item"><time>${esc(l.created_at||l.timestamp||'-')}</time><strong>${esc(logTitle(l))}</strong><p>${esc(l.detail||l.description||l.category||'')}</p></div>`).join(''):'<div class="muted">기록된 로그가 없습니다.</div>'}

async function loadPlan(){try{const d=await api('/plans/me');$('settingsPlan').textContent=d.plan||'-';const pu=d.product_usage||d.products||{};const cu=d.calculation_usage||d.calculations||{};$('settingsProductUsage').textContent=typeof pu==='object'?`${pu.used??0} / ${pu.limit??'∞'}`:`${pu}`;$('settingsCalcUsage').textContent=typeof cu==='object'?`${cu.used??0} / ${cu.limit??'∞'}`:`${cu}`;}catch{}}

function homeChannelBadge(channel){
  const c=String(channel||'MANUAL').toUpperCase();
  if(c.includes('NAVER'))return '<span class="channel naver">N</span>';
  if(c.includes('COUPANG'))return '<span class="channel coupang">coupang</span>';
  if(c==='BUYER_APP')return '<span class="status info">APP</span>';
  return '<span class="status gray">직접</span>';
}
function homeChannelName(channel){const c=String(channel||'MANUAL').toUpperCase();if(c.includes('NAVER'))return '네이버';if(c.includes('COUPANG'))return '쿠팡';if(c==='BUYER_APP')return '구매자 앱';return '직접 등록'}
function shortDateTime(v){if(!v)return '-';const d=new Date(v);if(Number.isNaN(d.getTime()))return esc(String(v).slice(0,16));return `${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`}

function renderHome(){
  const stops=products.filter(p=>productStatus(p)==='STOP').length;
  const expectedProfit=orders.filter(o=>!['CANCELLED','REFUNDED'].includes(String(o.status||'').toUpperCase())).reduce((a,o)=>a+Number(o.expected_profit||0),0);
  const newOrders=orders.filter(o=>String(o.status||'').toUpperCase()==='NEW').length;
  const purchaseWaiting=purchases.filter(p=>['READY','READY_TO_PAY','BLOCKED'].includes(String(p.status||'').toUpperCase())).length;
  const shipmentOrderIds=new Set(shipments.map(s=>s.order_id));
  const shippingIssues=orders.filter(o=>String(o.status||'').toUpperCase()==='ORDERED'&&!shipmentOrderIds.has(o.id)).length;
  const activeTrackers=trackers.filter(x=>Number(x.tracker?.tracking_enabled??1)===1).length;
  const activeShipping=shipments.filter(s=>['READY','IN_TRANSIT','OUT_FOR_DELIVERY'].includes(String(s.status||'').toUpperCase())).length;
  const doneShipping=shipments.filter(s=>String(s.status||'').toUpperCase()==='DELIVERED').length;

  if($('homeOrderCount'))$('homeOrderCount').textContent=newOrders;
  if($('homePurchaseCount'))$('homePurchaseCount').textContent=purchaseWaiting;
  if($('homeShippingIssueCount'))$('homeShippingIssueCount').textContent=shippingIssues;
  if($('homeStopCount'))$('homeStopCount').textContent=stops;
  if($('homeProfitTotal'))$('homeProfitTotal').textContent=`₩${Math.round(expectedProfit).toLocaleString('ko-KR')}`;
  if($('homePricingCount'))$('homePricingCount').textContent=activeTrackers;
  if($('bellCount'))$('bellCount').textContent=Math.min(newOrders+purchaseWaiting+shippingIssues+stops,99);

  const actionRows=orders.slice(0,4);
  if($('homeActionProducts'))$('homeActionProducts').innerHTML=actionRows.length?actionRows.map(o=>`<div class="order-row">${homeChannelBadge(o.channel)}<div class="order-meta"><span>${esc(homeChannelName(o.channel))}</span><small>주문번호 ${esc(o.order_no||'-')}</small></div><div class="order-product"><strong>${esc(o.product_name||'-')}</strong><small>${Number(o.quantity||1)}개 / ${money(o.sale_price)}</small></div><div class="order-state"><span class="status ${statusClass(o.status)}">${esc(statusLabel(o.status))}</span><small>${shortDateTime(o.created_at)}</small></div></div>`).join(''):'<div class="muted">처리할 실제 주문이 없습니다.</div>';

  const priceRows=trackers.slice(0,4);
  if($('homePriceAlerts'))$('homePriceAlerts').innerHTML=priceRows.length?priceRows.map(x=>{const p=x.product||{};const t=x.tracker||{};const cur=Number(p.selling_price||0);const floor=Number(x.minimum_sellable_price||0);const comp=t.competitor_price;const ok=x.recommendation!=='STOP';return `<div class="price-row"><div class="price-thumb">${thumbHtml(p)}</div><div class="price-info"><strong>${esc(p.name||'-')}</strong><small>경쟁가 ${comp==null?'미확인':money(comp)} · 내 판매가 <b class="${ok?'green-text':'red-text'}">${money(cur)}</b></small><em>최저 판매 가능가 ${money(floor)}</em></div><div class="price-status">${ok?'<span class="status sell">판매 가능</span>':'<span class="status stop">판매 중지</span>'}<small>${shortDateTime(t.last_checked_at)}</small></div></div>`}).join(''):'<div class="muted">실제 가격 추적 데이터가 없습니다.</div>';

  const notices=[];
  if(shippingIssues)notices.push(`<div class="notice dashboard-notice"><span class="notice-icon danger">▲</span><div><strong>송장 등록 대기 ${shippingIssues}건</strong><p>발주 완료 주문 중 배송정보가 없는 주문입니다.</p></div><time>현재</time></div>`);
  if(purchaseWaiting)notices.push(`<div class="notice dashboard-notice"><span class="notice-icon warning">▲</span><div><strong>발주 확인 필요 ${purchaseWaiting}건</strong><p>결제 준비 또는 검수가 필요한 발주입니다.</p></div><time>현재</time></div>`);
  if(newOrders)notices.push(`<div class="notice dashboard-notice"><span class="notice-icon cart">●</span><div><strong>신규 주문 ${newOrders}건</strong><p>주문정보를 확인하고 발주 준비를 진행하세요.</p></div><time>현재</time></div>`);
  if(stops)notices.push(`<div class="notice dashboard-notice"><span class="notice-icon danger">▲</span><div><strong>판매 중지 상품 ${stops}건</strong><p>수익 조건 또는 판매상태를 확인하세요.</p></div><time>현재</time></div>`);
  if(!notices.length)notices.push('<div class="muted">현재 확인이 필요한 운영 알림이 없습니다.</div>');
  if($('homeNotifications'))$('homeNotifications').innerHTML=notices.slice(0,4).join('');

  if($('homeOrderTabWait'))$('homeOrderTabWait').textContent=purchaseWaiting;
  if($('homeOrderTabNew'))$('homeOrderTabNew').textContent=newOrders;
  if($('homeOrderTabShipping'))$('homeOrderTabShipping').textContent=activeShipping;
  if($('homeOrderTabDone'))$('homeOrderTabDone').textContent=doneShipping;
  if($('homeOrderTable'))$('homeOrderTable').innerHTML=orders.length?orders.slice(0,5).map(o=>`<tr><td>${shortDateTime(o.created_at)}</td><td>${homeChannelBadge(o.channel)}</td><td>${esc(o.order_no||'-')}</td><td>${esc(o.product_name||'-')}</td><td>${Number(o.quantity||1)}</td><td>${money(o.sale_price)}</td><td><span class="status ${statusClass(o.status)}">${esc(statusLabel(o.status))}</span></td><td><button class="tiny-btn primary" data-home-order="${esc(o.id)}">보기</button></td></tr>`).join(''):'<tr><td colspan="8" class="muted">실제 주문 데이터가 없습니다.</td></tr>';

  if($('homeShippingTable'))$('homeShippingTable').innerHTML=shipments.length?shipments.slice(0,5).map(s=>`<tr><td>${esc(s.tracking_no||'-')}</td><td>${esc(s.carrier||'-')}</td><td>${esc(s.order?.product_name||'-')}</td><td><span class="status ${statusClass(s.status)}">${esc(statusLabel(s.status))}</span></td><td>${esc(s.expected_delivery||shortDateTime(s.updated_at||s.created_at))}</td></tr>`).join(''):'<tr><td colspan="5" class="muted">실제 배송 데이터가 없습니다.</td></tr>';
}

function statusLabel(v){const m={NEW:'신규 주문',READY:'발주 대기',PAYMENT_READY:'결제 준비 완료',PAYMENT_BLOCKED:'결제 차단',READY_TO_PAY:'결제 준비 완료',BLOCKED:'결제 차단',ORDERED:'발주 완료',SHIPPING:'배송 중',DONE:'배송 완료',CANCELLED:'취소 완료',CANCEL_REQUESTED:'공급처 취소 필요',RETURN_REQUESTED:'반품 처리 필요',EXCHANGE_REQUESTED:'교환 처리 필요',REFUNDED:'환불 완료',PAID:'결제 완료',IN_TRANSIT:'배송 중',OUT_FOR_DELIVERY:'배송 출발',DELIVERED:'배송 완료',AVAILABLE:'공급 가능',OUT_OF_STOCK:'품절',UNKNOWN:'확인 필요'};return m[v]||v||'-'}
function statusClass(v){if(['DONE','DELIVERED','PAID','AVAILABLE'].includes(v))return 'sell';if(['CANCELLED','OUT_OF_STOCK'].includes(v))return 'stop';if(['NEW','READY'].includes(v))return 'wait';if(['SHIPPING','IN_TRANSIT','OUT_FOR_DELIVERY','ORDERED'].includes(v))return 'info';return 'gray'}
async function doLogout(){try{await api('/auth/logout',{method:'POST'})}catch{}localStorage.removeItem(TOKEN_KEY);location.reload()}

async function loadSourcing(){try{const d=await api('/sourcing/');sourcingItems=d.items||[];renderSourcing()}catch{sourcingItems=[]}}
function renderSourcing(){const b=$('sourcingTableBody');if(!b)return;b.innerHTML=sourcingItems.length?sourcingItems.map(x=>`<tr><td><div style="display:flex;align-items:center;gap:9px">${x.image_url?`<div class="thumb"><img src="${esc(x.image_url)}" alt="" onerror="this.remove()"></div>`:''}<div><strong>${esc(x.product_name)}</strong><div class="muted">${esc(x.options_text||'')}</div></div></div></td><td><strong>${esc(x.source_platform||supplierName(x.supplier_id))}</strong><div class="muted">${esc(supplierName(x.supplier_id))}</div></td><td>${money(x.purchase_price)}${x.source_currency?` <span class="muted">${esc(x.source_currency)}</span>`:''}</td><td>${money(x.shipping_fee)}</td><td><span class="status ${statusClass(x.availability)}">${statusLabel(x.availability)}</span></td><td>${x.source_url?`<a class="url-link" href="${esc(x.source_url)}" target="_blank" rel="noopener noreferrer">열기 ↗</a>`:'-'}</td><td>${esc((x.created_at||'').slice(0,10))}</td><td><button class="tiny-btn danger" data-delete-sourcing="${esc(x.id)}">삭제</button></td></tr>`).join(''):'<tr><td colspan="8" class="muted">등록된 소싱 상품이 없습니다.</td></tr>'}

async function loadOrders(){try{const d=await api('/orders/');orders=d.orders||[];renderOrders();refreshOrderSelects();renderHome()}catch{orders=[]}}
function renderOrders(){const b=$('ordersTableBody');if(!b)return;b.innerHTML=orders.length?orders.map(o=>`<tr><td>${esc(o.channel)}</td><td><strong>${esc(o.order_no)}</strong></td><td>${esc(o.product_name)}<div class="muted">${esc(o.option_text||'')}</div></td><td>${Number(o.quantity||1)}</td><td>${money(o.sale_price)}</td><td>${esc(o.recipient||'-')}</td><td><span class="status ${statusClass(o.status)}">${statusLabel(o.status)}</span></td><td><div class="row-actions">${!['DONE','CANCELLED','CANCEL_REQUESTED','RETURN_REQUESTED','EXCHANGE_REQUESTED','REFUNDED'].includes(o.status)?`<button class="tiny-btn primary" data-prepare-payment="${esc(o.id)}">결제 준비</button><button class="tiny-btn" data-order-status="${esc(o.id)}" data-next-status="CANCELLED">취소</button><button class="tiny-btn" data-after-sales="${esc(o.id)}" data-request-type="RETURN">반품</button><button class="tiny-btn" data-after-sales="${esc(o.id)}" data-request-type="EXCHANGE">교환</button>`:''}<button class="tiny-btn danger" data-delete-order="${esc(o.id)}">삭제</button></div></td></tr>`).join(''):'<tr><td colspan="8" class="muted">등록된 주문이 없습니다.</td></tr>'}
function refreshOrderSelects(){for(const id of ['purchaseOrderSelect','shipmentOrderSelect']){const el=$(id);if(!el)continue;el.innerHTML='<option value="">주문 선택</option>'+orders.map(o=>`<option value="${esc(o.id)}">${esc(o.order_no)} · ${esc(o.product_name)}</option>`).join('')}}

async function loadPurchases(){try{const d=await api('/purchases/');purchases=d.purchases||[];renderPurchases()}catch{purchases=[]}}
function renderPurchases(){const b=$('purchaseTableBody');if(!b)return;b.innerHTML=purchases.length?purchases.map(x=>{const o=x.order||{};return `<tr><td>${esc(o.order_no||'-')}</td><td>${esc(o.product_name||'-')}</td><td>${esc(x.supplier_name||o.supplier_name||'-')}</td><td>${money(x.amount)}</td><td><span class="status ${statusClass(x.status)}">${statusLabel(x.status)}</span></td><td>${x.supplier_url?`<a class="url-link" href="${esc(x.supplier_url)}" target="_blank" rel="noopener noreferrer">주문하러 가기 ↗</a>`:'-'}</td><td>${x.status!=='PAID'?`<button class="tiny-btn primary" data-purchase-paid="${esc(x.id)}">결제 완료</button>`:'-'}</td></tr>`}).join(''):'<tr><td colspan="7" class="muted">생성된 발주가 없습니다.</td></tr>'}

async function loadShipments(){try{const d=await api('/shipping/');shipments=d.shipments||[];renderShipments();renderHome()}catch{shipments=[]}}
function renderShipments(){const b=$('shippingTableBody');if(!b)return;b.innerHTML=shipments.length?shipments.map(x=>{const o=x.order||{};return `<tr><td>${esc(o.order_no||'-')}</td><td>${esc(o.product_name||'-')}</td><td>${esc(x.carrier||'-')}</td><td>${esc(x.tracking_no||'-')}</td><td><span class="status ${statusClass(x.status)}">${statusLabel(x.status)}</span></td><td>${esc(x.expected_delivery||'-')}</td><td><select class="tiny-select" data-shipment-status="${esc(x.id)}"><option value="READY" ${x.status==='READY'?'selected':''}>배송 준비</option><option value="IN_TRANSIT" ${x.status==='IN_TRANSIT'?'selected':''}>배송 중</option><option value="OUT_FOR_DELIVERY" ${x.status==='OUT_FOR_DELIVERY'?'selected':''}>배송 출발</option><option value="DELIVERED" ${x.status==='DELIVERED'?'selected':''}>배송 완료</option></select></td></tr>`}).join(''):'<tr><td colspan="7" class="muted">등록된 배송 정보가 없습니다.</td></tr>'}

async function loadAiDrafts(){try{const d=await api('/ai-content/');aiDrafts=d.drafts||[];renderAiDrafts();renderAiProductOptions()}catch{aiDrafts=[]}}
function renderAiProductOptions(){const el=$('aiProductSelect');if(!el)return;const val=el.value;el.innerHTML='<option value="">직접 입력</option>'+products.map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');el.value=val}
function renderAiDrafts(){const el=$('aiDraftList');if(!el)return;el.innerHTML=aiDrafts.length?aiDrafts.map(d=>`<article class="draft-card"><h3>${esc(d.title)}</h3><p>${esc(d.description)}</p><p><strong>판매 포인트</strong>\n${esc(d.selling_points||'')}</p><small>키워드: ${esc(d.keywords||'-')}</small></article>`).join(''):'<div class="muted">생성된 상품 초안이 없습니다.</div>'}

async function loadIntegrations(){try{const d=await api('/integrations/');integrations=d.connections||[];const el=$('integrationList');if(!el)return;el.innerHTML=integrations.map(x=>{const c=x.api_config||{};const ready=!!c.configured;const fields=x.channel==='NAVER'?`Client ID ${c.client_id?'✓':'×'} · Secret ${c.client_secret?'✓':'×'} · ${esc(c.mode||c.token_type||'SELF')}`:x.channel==='COUPANG'?`Access ${c.access_key?'✓':'×'} · Secret ${c.secret_key?'✓':'×'} · Vendor ${c.vendor_id?esc(c.vendor_id):'×'}`:'다음 단계에서 연동 예정';return `<div class="integration-card"><div class="integration-title-row"><div><strong>${esc(x.channel)}</strong><p>${Number(x.enabled)?'사용 설정됨':'사용 안 함'}</p></div><span class="api-ready ${ready?'ready':'wait'}">${ready?'API 준비':'키 필요'}</span></div><p class="integration-meta">${fields}</p><input class="integration-label" data-integration-label="${esc(x.channel)}" value="${esc(x.account_label||'')}" placeholder="계정 별칭"/><div class="integration-actions"><label class="switch-label"><input type="checkbox" data-integration-enabled="${esc(x.channel)}" ${Number(x.enabled)?'checked':''}/>사용</label><button class="tiny-btn" data-save-integration="${esc(x.channel)}">저장</button>${x.channel!=='11ST'?`<button class="tiny-btn primary" data-test-integration="${esc(x.channel)}" ${ready?'':'disabled'}>API 연결 테스트</button>`:''}</div></div>`}).join('')}catch(err){toast(err.message)}}
async function loadReportSummary(){try{const d=await api('/reports/summary');const el=$('settingsCalcUsage');if(el&&d.order_count!=null)el.title=`주문 ${d.order_count}건 · 예상이익 ${money(d.expected_profit)} · 배송완료 ${d.delivered_count}건`}catch{}}
async function loadTaxReserve(){try{const d=await api('/tax-reserve/summary');const x=d.reserve||{};$('taxTotalProfit').textContent=money(x.total_profit);$('taxReserved').textContent=money(x.total_reserved);$('taxUsableProfit').textContent=money(x.usable_profit);$('taxVatPayable').textContent=money(x.estimated_vat_payable);$('profitTaxReserveRate').value=x.profit_tax_reserve_rate??10;$('incomeTaxReserveRate').value=x.income_tax_reserve_rate??0;$('taxReserveNotice').textContent=x.notice||''}catch(err){toast(err.message)}}
function resetProductForm(){ $('productForm').reset();$('productId').value='';$('productModalTitle').textContent='상품 등록';$('purchasePrice').value=0;$('internationalShipping').value=0;$('domesticShipping').value=0;$('sellingPrice').value=0;$('feeRate').value=0;$('vatRate').value=.1 }
function editProduct(id){const p=products.find(x=>x.id===id);if(!p)return;resetProductForm();$('productId').value=p.id;$('productModalTitle').textContent='상품 수정';$('productName').value=p.name||'';$('productSku').value=p.sku||'';$('productSupplier').value=p.supplier_id||'';$('purchasePrice').value=p.purchase_price??p.supply_price??0;$('internationalShipping').value=p.international_shipping??0;$('domesticShipping').value=p.domestic_shipping??p.shipping_fee??0;$('sellingPrice').value=p.selling_price??p.sale_price??0;$('feeRate').value=p.fee_rate??p.market_fee_rate??0;$('vatRate').value=p.vat_rate??.1;$('mainImageUrl').value=p.main_image_url||'';$('detailImageUrl').value=p.detail_image_url||'';openModal('productModal')}
function resetSupplierForm(){ $('supplierForm').reset();$('supplierId').value='';$('supplierModalTitle').textContent='공급처 등록' }
function editSupplier(id){const s=suppliers.find(x=>x.id===id);if(!s)return;resetSupplierForm();$('supplierId').value=s.id;$('supplierName').value=s.name||'';$('supplierMemo').value=s.memo||'';$('supplierModalTitle').textContent='공급처 수정';openModal('supplierModal')}
async function download(path,name){const blob=await api(path);const u=URL.createObjectURL(blob);const a=document.createElement('a');a.href=u;a.download=name;document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(u)}


function isBadSourcingText(v){const t=String(v||'').trim();return !t||/^(browser|naver|로그인)$/i.test(t)||/에러페이지|시스템오류|access denied|captcha/i.test(t)}
function isBadSourcingUrl(v){try{const u=new URL(String(v||''));return /(^|\.)nid\.naver\.com$/i.test(u.hostname)||/\.js(?:$|\?)/i.test(u.pathname)}catch{return true}}
function isBadProductImage(v){try{const u=new URL(String(v||''));const x=(u.hostname+u.pathname).toLowerCase();return /sp_u_|ntm\.pstatic|static-resource|favicon|logo|icon|\.js$/.test(x)}catch{return true}}
let currentSourcingOptionGroups=[];
let currentSourcingAdditionalOptionGroups=[];
let currentSourcingOptionVariants=[];
let currentSourcingAIJudgment={};

function normalizeSourcingVariants(variants){
  return (Array.isArray(variants)?variants:[]).map(v=>{
    const options=(Array.isArray(v?.options)?v.options:[]).map(x=>({name:String(x?.name||'').trim(),value:String(x?.value||'').trim()})).filter(x=>x.name&&x.value&&!/^https?:\/\//i.test(x.value));
    return {options,additional_price:v?.additional_price??null,availability:v?.availability||'UNKNOWN',verification_status:v?.verification_status||'VERIFIED'};
  }).filter(v=>v.options.length);
}
function optionNoiseName(name){
  const n=String(name||'').trim();
  return !n || /^standardCombinations?$/i.test(n) || /^https?:\/\//i.test(n) || /^(?:A\/?S|AS)\s*(?:안내|정보)?$/i.test(n) || /(?:이미지|image|photo|thumbnail|thumb|url)$/i.test(n);
}
function optionNoiseValue(v){return /^https?:\/\//i.test(String(v||'').trim());}
function cleanOptionDisplayText(v){
  return String(v||'').replace(/\s+/g,' ').trim().replace(/^_+/,'').replace(/_+$/,'').trim();
}
function extractOptionPriceDelta(v){
  const t=cleanOptionDisplayText(v);
  const m=t.match(/\(([+-])\s*([\d,]+)\s*원\)\s*$/);
  if(!m)return 0;
  const n=Number(m[2].replace(/,/g,''))||0;
  return m[1]==='-'?-n:n;
}
function cleanDisplayGroups(groups){
  return (Array.isArray(groups)?groups:[]).slice(0,100)
    .filter(g=>g&&Array.isArray(g.values)&&g.values.length&&!optionNoiseName(g.name))
    .map((g,i)=>({
      name:cleanOptionDisplayText(g.name||`옵션 ${i+1}`),
      values:[...new Set(g.values.map(cleanOptionDisplayText).filter(v=>v&&!optionNoiseValue(v)))]
    }))
    .filter(g=>g.values.length);
}
function isInternalOptionGroupName(name){
  const n=cleanOptionDisplayText(name);
  return !n || /^(?:standardCombinations?|supplementProducts?|additionalProducts?|optionProducts?|options?|values?|items?|list)$/i.test(n) || /^[a-z][A-Za-z0-9_$.-]{2,}$/i.test(n);
}
function visibleGroupLabel(name,fallback,productName=''){
  const n=cleanOptionDisplayText(name), p=cleanOptionDisplayText(productName);
  if(!n||isInternalOptionGroupName(n)||n===p||n===fallback||n.length>70)return fallback;
  return n;
}
function normalizeAdditionalDisplayGroups(groups){
  let src=cleanDisplayGroups(groups).filter(g=>!/(?:A\/?S|고객센터|배송안내|교환|반품|리뷰|구매평|상세설명)/i.test(g.name));
  if(!src.length)return [];
  const norm=x=>cleanOptionDisplayText(x).replace(/\([+-]\s*[\d,]+\s*원\)\s*$/,'').replace(/[\s_]+/g,'').toLowerCase();
  const autoName=n=>/^추가\s*옵션\s*\d+$/i.test(cleanOptionDisplayText(n))||/^추가옵션\d+$/i.test(cleanOptionDisplayText(n));
  const internalName=n=>autoName(n)||isInternalOptionGroupName(n);
  const valueSet=g=>new Set((g.values||[]).map(norm).filter(Boolean));
  const similarity=(a,b)=>{if(!a.size||!b.size)return 0;let hit=0;for(const v of a)if(b.has(v))hit++;return hit/Math.min(a.size,b.size)};

  // Mandatory options must never reappear as add-ons.
  const mainSets=(currentSourcingOptionGroups||[]).map(valueSet);
  src=src.filter(g=>{
    const vals=valueSet(g);let best=0;
    for(const set of mainSets)best=Math.max(best,similarity(vals,set));
    return !(vals.size>=2&&best>=0.80);
  });
  if(!src.length)return [];

  // Cluster near-identical add-on groups and keep the real visible heading over aliases such as 추가옵션5.
  const used=new Set(),dedup=[];
  for(let i=0;i<src.length;i++){
    if(used.has(i))continue;
    const a=valueSet(src[i]),cluster=[i];
    for(let j=i+1;j<src.length;j++){
      if(used.has(j))continue;
      const b=valueSet(src[j]);
      if(similarity(a,b)>=0.92&&Math.max(a.size,b.size)<=Math.min(a.size,b.size)*1.20)cluster.push(j);
    }
    let best=cluster[0];
    for(const j of cluster){
      const score=x=>internalName(x.name)?0:(cleanOptionDisplayText(x.name).length<=60?2:1);
      if(score(src[j])>score(src[best]))best=j;
    }
    cluster.forEach(j=>used.add(j)); dedup.push(src[best]);
  }
  src=dedup;

  // A large synthetic group can be the union of several genuine dropdowns. Suppress that display-only duplicate.
  const meaningful=src.filter(g=>!internalName(g.name)&&cleanOptionDisplayText(g.name).length<=60);
  src=src.filter(g=>{
    const gs=valueSet(g); if(gs.size<8)return true;
    let coveredGroups=0;const covered=new Set();
    for(const h of meaningful){
      if(h===g)continue;const hs=valueSet(h);const hits=[...hs].filter(v=>gs.has(v));
      if(hs.size>=2&&hits.length/hs.size>=0.90){coveredGroups++;hits.forEach(v=>covered.add(v))}
    }
    if(coveredGroups>=2&&covered.size/gs.size>=0.65&&(internalName(g.name)||cleanOptionDisplayText(g.name).length>60))return false;
    return true;
  });

  return src.slice(0,30);
}
function variantSignature(v){return (v.options||[]).map(x=>`${x.name}=${x.value}`).join('|')}
function cleanDisplayVariants(variants){
  const out=[],seen=new Set();
  for(const v of normalizeSourcingVariants(variants)){
    const opts=v.options.filter(x=>!optionNoiseName(x.name)&&!optionNoiseValue(x.value));
    if(!opts.length)continue;
    const nv={...v,options:opts}, k=variantSignature(nv); if(!k||seen.has(k))continue; seen.add(k);out.push(nv);
  }
  return out;
}
function renderVariantMeta(v,leafValue=''){
  const sold=String(v?.availability||'').toUpperCase()==='OUT_OF_STOCK';
  const ap=Number(v?.additional_price); const bits=[];
  if(v?.verification_status==='NEEDS_REVIEW')bits.push(v?.availability==='OUT_OF_STOCK'?'추가금액 확인 필요':'가격·품절 확인 필요');
  // V74: if the visible leaf already contains (+/-N원), do not print the same price again.
  if(Number.isFinite(ap)&&ap!==0&&!/\([+-]\s*[\d,]+\s*원\)/.test(String(leafValue||'')))bits.push(`${ap>0?'+':''}${ap.toLocaleString()}원`);
  if(sold&&!/품절/.test(String(leafValue||'')))bits.push('품절'); return bits.length?` <small>${esc(bits.join(' · '))}</small>`:'';
}
function renderVariantHierarchy(variants){
  // V74: render dependency rows strictly in the real required-option group order.
  // A stale SmartStore selection can temporarily prepend a child option (e.g. 호수 4.0)
  // to a variant. Never display that synthetic prefix or repeat the same group twice.
  const groupOrder=(currentSourcingOptionGroups||[]).map(g=>cleanOptionDisplayText(g.name)).filter(Boolean);
  let vars=cleanDisplayVariants(variants).map(v=>{
    if(!groupOrder.length)return v;
    const byName=new Map();
    for(const o of v.options||[]){
      const n=cleanOptionDisplayText(o.name);
      if(groupOrder.includes(n))byName.set(n,{name:n,value:cleanOptionDisplayText(o.value)});
    }
    const options=groupOrder.map(n=>byName.get(n)).filter(Boolean);
    return {...v,options};
  }).filter(v=>v.options.length);
  const seen=new Set();
  vars=vars.filter(v=>{const k=variantSignature(v);if(!k||seen.has(k))return false;seen.add(k);return true});
  if(!vars.length)return '';
  const firstName=groupOrder[0]||vars[0]?.options[0]?.name;
  const rows=vars.filter(v=>v.options[0]?.name===firstName);
  if(!rows.length)return '';
  const firstVals=[]; for(const v of rows){const x=v.options[0]?.value;if(x&&!firstVals.includes(x))firstVals.push(x)}
  const body=firstVals.map(firstVal=>{
    const matching=rows.filter(v=>v.options[0]?.value===firstVal);
    const children=[],childSeen=new Set();
    for(const v of matching){
      const rest=v.options.slice(1);
      if(!rest.length)continue;
      const label=rest.map(x=>`${x.name} ${x.value}`).join(' · ');
      if(childSeen.has(label))continue; childSeen.add(label);
      children.push(`<li>${esc(label)}${renderVariantMeta(v,rest.at(-1)?.value)}</li>`);
    }
    return `<div class="sourcing-variant-parent"><strong>${esc(firstVal)}</strong>${children.length?`<ul>${children.join('')}</ul>`:''}</div>`;
  }).join('');
  return `<div class="sourcing-variant-group"><div class="sourcing-variant-title">옵션 1 <span>${esc(firstName)}</span></div>${body}</div>`;
}
function renderSourcingOptionGroups(groups,variants=[]){
  const box=$('sourcingOptionGroups'); if(!box)return;
  const src=cleanDisplayGroups(groups); const vars=cleanDisplayVariants(variants);
  currentSourcingOptionGroups=src; currentSourcingOptionVariants=vars;
  const hierarchy=renderVariantHierarchy(vars);
  if(hierarchy){box.innerHTML=hierarchy;return;}
  if(!src.length){box.innerHTML='<div class="muted">자동수집된 옵션이 없습니다.</div>';return;}
  const productName=$('sourcingName')?.value||'';
  box.innerHTML=src.map((g,i)=>{
    const label=visibleGroupLabel(g.name,`옵션 ${i+1}`,productName);
    return `<div class="sourcing-variant-group"><div class="sourcing-variant-title">옵션 ${i+1}${label!==`옵션 ${i+1}`?` <span>${esc(label)}</span>`:''}</div>${g.values.map(v=>{
      const delta=extractOptionPriceDelta(v);
      return `<div class="sourcing-variant-parent"><strong>${esc(v)}</strong></div>`
    }).join('')}</div>`;
  }).join('');
}
function renderSourcingAdditionalOptionGroups(groups){
  const box=$('sourcingAdditionalOptionGroups'); if(!box)return;
  const src=normalizeAdditionalDisplayGroups(groups);
  currentSourcingAdditionalOptionGroups=src;
  const wrap=box.closest('.sourcing-additional-section')||box.parentElement;
  if(!src.length){box.innerHTML=''; if(wrap)wrap.style.display='none';return;}
  if(wrap)wrap.style.display='';
  const productName=$('sourcingName')?.value||'';
  box.innerHTML=src.map((g,i)=>{
    const label=visibleGroupLabel(g.name,`추가 옵션 ${i+1}`,productName);
    const values=(g.values.length===1&&cleanOptionDisplayText(g.values[0])===cleanOptionDisplayText(g.name))?'':g.values.map(v=>`<div class="sourcing-variant-parent"><strong>${esc(v)}</strong></div>`).join('');
    return `<div class="sourcing-variant-group"><div class="sourcing-variant-title">추가 옵션 ${i+1}${label!==`추가 옵션 ${i+1}`?` <span>${esc(label)}</span>`:''}</div>${values}</div>`;
  }).join('');
}
function collectSourcingAdditionalOptionGroups(){return currentSourcingAdditionalOptionGroups.map(g=>({name:g.name,values:[...g.values]}));}
function collectSourcingOptionGroups(){return currentSourcingOptionGroups.map(g=>({name:g.name,values:[...g.values]}));}
function syncSourcingOptions(){
  const groups=collectSourcingOptionGroups();
  const additionalGroups=collectSourcingAdditionalOptionGroups();
  const mainText=groups.map(g=>`${g.name}: ${g.values.join(' / ')}`).join(' | ');
  const extraText=additionalGroups.map(g=>`${g.name}: ${g.values.join(' / ')}`).join(' | ');
  const text=[mainText,extraText?`추가옵션 ${extraText}`:''].filter(Boolean).join(' || ');
  if($('sourcingOptions'))$('sourcingOptions').value=text;
  const valueDetails=groups.map(g=>({name:g.name,values:g.values.map(v=>({text:v,price_delta:extractOptionPriceDelta(v)}))}));
  const additionalValueDetails=additionalGroups.map(g=>({name:g.name,values:g.values.map(v=>({text:v,price_delta:extractOptionPriceDelta(v)}))}));
  if($('sourcingOptionsJson'))$('sourcingOptionsJson').value=JSON.stringify({groups,additional_groups:additionalGroups,variants:currentSourcingOptionVariants,ai_judgment:currentSourcingAIJudgment,value_details:valueDetails,additional_value_details:additionalValueDetails});
  return {groups,additionalGroups,text};
}
function resetSourcingConfirmForm(){
  $('sourcingForm')?.reset(); renderSupplierOptions();
  for(const id of ['sourcingPlatform','sourcingProductId','sourcingCurrency','sourcingImportStatus','sourcingSupplierName','sourcingStoreName','sourcingStoreUrl','sourcingOptionsJson','sourcingImageUrlsJson'])if($(id))$(id).value='';
  if($('sourcingImageGallery'))$('sourcingImageGallery').innerHTML=''; if($('sourcingImageCount'))$('sourcingImageCount').textContent=''; if($('sourcingAutoMeta'))$('sourcingAutoMeta').textContent=''; currentSourcingOptionVariants=[]; renderSourcingOptionGroups([],[]); renderSourcingAdditionalOptionGroups([]);
}
function applyImportedSourcing(p){
  currentSourcingAIJudgment=p.ai_judgment&&typeof p.ai_judgment==='object'?p.ai_judgment:{};
  resetSourcingConfirmForm();
  const originalUrl=p.source_url||'';
  const title=!isBadSourcingText(p.product_name)?p.product_name:'';
  if($('sourcingName'))$('sourcingName').value=title;
  // Never replace the pasted product URL with a login/error redirect URL.
  if($('sourcingUrl'))$('sourcingUrl').value=!isBadSourcingUrl(originalUrl)?originalUrl:(!isBadSourcingUrl(p.final_url)?p.final_url:'');
  if($('sourcingPrice'))$('sourcingPrice').value=(p.purchase_price!=null&&Number(p.purchase_price)>=0)?Number(p.purchase_price):'';
  if($('sourcingShipping'))$('sourcingShipping').value=(p.shipping_fee!=null&&Number(p.shipping_fee)>=0)?Number(p.shipping_fee):'';
  renderSourcingOptionGroups(p.option_groups||[],p.option_variants||[]); renderSourcingAdditionalOptionGroups(p.additional_option_groups||[]); if($('sourcingOptions'))$('sourcingOptions').value=p.options_text||'';
  const allImages=(p.image_urls||[]).filter(u=>u&&!isBadProductImage(u));
  if($('sourcingImage'))$('sourcingImage').value=(!isBadProductImage(p.image_url)?p.image_url:(allImages[0]||''));
  if($('sourcingImageUrlsJson'))$('sourcingImageUrlsJson').value=JSON.stringify(allImages);
  if($('sourcingImageCount'))$('sourcingImageCount').textContent=allImages.length?`(${allImages.length}장)`:'';
  if($('sourcingImageGallery'))$('sourcingImageGallery').innerHTML=allImages.map((u,i)=>`<a href="${esc(u)}" target="_blank" rel="noopener noreferrer" title="이미지 ${i+1}"><img src="${esc(u)}" alt="상품 이미지 ${i+1}" loading="lazy"></a>`).join('');
  if($('sourcingAvailability')&&p.availability)$('sourcingAvailability').value=p.availability;
  if($('sourcingPlatform'))$('sourcingPlatform').value=p.platform||'';
  if($('sourcingProductId'))$('sourcingProductId').value=p.source_product_id||'';
  if($('sourcingCurrency'))$('sourcingCurrency').value=p.currency||'';
  if($('sourcingImportStatus'))$('sourcingImportStatus').value=p.import_status||'';
  if($('sourcingSupplierName'))$('sourcingSupplierName').value=p.supplier_name||'';
  if($('sourcingStoreName'))$('sourcingStoreName').value=p.supplier_store_name||'';
  if($('sourcingStoreUrl'))$('sourcingStoreUrl').value=!isBadSourcingUrl(p.supplier_store_url)?p.supplier_store_url:'';
  if($('sourcingOptionsJson'))$('sourcingOptionsJson').value=JSON.stringify({groups:currentSourcingOptionGroups,additional_groups:currentSourcingAdditionalOptionGroups,variants:currentSourcingOptionVariants,ai_judgment:currentSourcingAIJudgment});
  if($('sourcingSupplier')){
    if(p.matched_supplier_id){$('sourcingSupplier').value=p.matched_supplier_id}
    else if(p.supplier_name){const o=document.createElement('option');o.value='';o.textContent=`${p.supplier_name} (저장 시 자동 생성)`;o.selected=true;$('sourcingSupplier').prepend(o)}
  }
  if($('sourcingMemo')&&p.description)$('sourcingMemo').value=String(p.description).slice(0,800);
  if($('sourcingAutoMeta'))$('sourcingAutoMeta').textContent=`자동수집: ${p.supplier_name||p.platform||'공급처'}${p.source_product_id?` · 상품번호 ${p.source_product_id}`:''}${p.currency?` · 통화 ${p.currency}`:''} · 옵션그룹 ${(p.option_groups||[]).length}개 · 추가옵션 ${(p.additional_option_groups||[]).length}개 · 이미지 ${allImages.length}장 · ${p.import_status||'PARTIAL'}`;
}

function renderImportPreview(p,url){
  const box=$('sourcingImportResult'); box.classList.remove('hidden');
  const images=(p.image_urls||[]).filter(u=>u&&!isBadProductImage(u));
  const missing=[];
  if(!p.product_name) missing.push('상품명');
  if(p.purchase_price==null) missing.push('매입가');
  if(p.shipping_fee==null) missing.push('배송비');
  if(!images.length) missing.push('상품 이미지');
  if(!(p.option_groups||[]).length) missing.push('옵션');
  const ok=p.import_status==='OK';
  const via=p.capture_source==='USER_CHROME_EXTENSION'?'CHROME_HELPER':'SERVER';
  const diag=p.option_capture_diagnostics&&typeof p.option_capture_diagnostics==='object'?p.option_capture_diagnostics:null;
  const events=Array.isArray(diag?.events)?diag.events:[];
  const clicked=events.filter(x=>x?.event==='main_value_clicked'||x?.event==='dependent_value_clicked');
  const priced=events.filter(x=>x?.event==='dependent_variant_captured'&&Number(x?.additional_price)!==0)
    .concat(clicked.filter(x=>/[+-]\s*[\d,]+\s*원/.test(String(x?.value||x?.before_value||x?.after_value||''))));
  const diagHtml=diag?`<details class="option-diagnostic"><summary>일반옵션 진단 · 실제 항목 클릭 ${clicked.length}개 · ±금액 감지 ${priced.length}개</summary><div class="muted">확장프로그램 ${esc(diag.version||'?')} · 상품번호 ${esc(diag.product_id||'?')} · ${Number(diag.elapsed_ms||0).toLocaleString()}ms</div><button id="copyOptionDiagnosticBtn" class="secondary-btn" type="button">진단내용 복사</button><pre>${esc(JSON.stringify(diag,null,2))}</pre></details>`:'';
  const ai=p.ai_judgment&&typeof p.ai_judgment==='object'?p.ai_judgment:null;
  const ai1=ai?.first_pass||{},ai2=ai?.second_pass||{};
  const aiStatus={AUTO_SAVE_READY:'자동 저장 가능',PARTIAL_REVIEW:'부분 확인 필요',REVIEW_REQUIRED:'확인 필요'}[ai2.status]||'판단 대기';
  const aiClass=ai2.status==='AUTO_SAVE_READY'?'ok':'warn';
  const aiIssues=Array.isArray(ai2.issues)?ai2.issues:[];
  const aiHtml=ai?`<div class="ai-judgment"><strong>AI 2중 판단 · ${esc(aiStatus)}</strong><div class="import-meta"><span class="status info">구조 ${esc(ai1.classification?.type||'?')}</span><span class="status ${aiClass}">일치도 ${Number(ai2.agreement||0)}%</span><span class="status gray">문제 ${aiIssues.length}개</span></div>${aiIssues.length?`<div class="muted">${esc(aiIssues.map(x=>x.code).join(' · '))}</div>`:''}</div>`:'';
  box.innerHTML=`<strong>${esc(p.product_name||'상품정보 수집 미완료')}</strong><div class="muted">${esc(p.import_message||'')}</div><div class="import-meta"><span class="status ${p.capture_source==='USER_CHROME_EXTENSION'?'ok':'info'}">수집 방식: ${via}</span><span class="status ${ok?'ok':'warn'}">${ok?'수집 완료':'수집 미완료'}</span><span class="status info">${esc(p.platform||'')}</span><span class="status gray">${p.purchase_price!=null?Number(p.purchase_price).toLocaleString()+' '+esc(p.currency||''):'매입가 미수집'}</span><span class="status gray">배송비 ${p.shipping_fee!=null?Number(p.shipping_fee).toLocaleString():'미수집'}</span><span class="status gray">이미지 ${images.length}장</span><span class="status gray">옵션그룹 ${(p.option_groups||[]).length}개</span></div>${missing.length?`<div class="muted" style="margin-top:8px">미수집 항목: ${esc(missing.join(', '))}</div>`:''}${aiHtml}${diagHtml}<div class="import-actions"><button id="confirmImportedSourcingBtn" class="primary-btn" type="button">확인/수정 후 저장</button><a class="secondary-btn" href="${esc(p.final_url||url)}" target="_blank" rel="noopener noreferrer">원본 확인 ↗</a></div>`;
  if($('confirmImportedSourcingBtn'))$('confirmImportedSourcingBtn').onclick=()=>{applyImportedSourcing(p);openModal('sourcingModal')};
  if($('copyOptionDiagnosticBtn'))$('copyOptionDiagnosticBtn').onclick=async()=>{try{await navigator.clipboard.writeText(JSON.stringify(diag,null,2));toast('옵션 진단내용을 복사했습니다.')}catch{toast('진단내용 복사에 실패했습니다. 펼친 내용을 직접 복사해주세요.')}};
}
async function importSourcingUrl(){
  const input=$('sourcingQuickUrl'); const btn=$('importSourcingUrlBtn'); const box=$('sourcingImportResult');
  const url=input?.value.trim(); if(!url){toast('상품 URL을 붙여넣어 주세요.');return}
  const before=btn.textContent; btn.disabled=true; btn.textContent='상품 분석 중...';
  try{
    let d=await api('/sourcing/import-url',{method:'POST',body:JSON.stringify({url})}); let p=d.preview||{};
    const isNaverProductUrl=/(^|\.)((smartstore|brand)\.)?naver\.com$/i.test(new URL(url).hostname);
    if(isNaverProductUrl){
      renderImportPreview(p,url);
      let hs=null;
      try{hs=await api('/sourcing/browser-helper-status')}catch{}
      if(!hs?.connected){
        box.insertAdjacentHTML('afterbegin','<div class="helper-diagnostic warn"><strong>Chrome 도우미: 연결 안 됨</strong><div class="muted">확장프로그램 최신 버전을 이 프로젝트의 chrome_extension\naver_source_helper 폴더에서 다시 로드한 뒤 시도하세요.</div></div>');
        toast('Chrome 도우미 연결이 확인되지 않습니다. 확장프로그램 최신 버전을 확인해주세요.');
      }else{
        box.insertAdjacentHTML('afterbegin',`<div class="helper-diagnostic ok"><strong>Chrome 도우미 연결됨 · v${esc(hs.version||'?')}</strong><div class="muted">화면 이동 없이 백그라운드에서 상품 정보를 직접 수집합니다.</div></div>`);
      }
      // Ask the installed Chrome helper through a local-page content-script bridge.
      // The helper itself opens/arms the Naver tab, so openerTabId/redirect behavior cannot break the trigger.
      const started=Date.now();
      const requestedAfter=started/1000;
      window.postMessage({type:'B2B_START_NAVER_CAPTURE',url},location.origin);
      while(Date.now()-started<225000){
        await new Promise(r=>setTimeout(r,1500));
        try{
          const st=await api(`/sourcing/browser-capture-status?url=${encodeURIComponent(url)}`);
          const freshCapture=Number(st.preview?.captured_at||0)>=requestedAfter-1;
          if(st.preview?.capture_source==='USER_CHROME_EXTENSION'&&freshCapture){
            d=await api('/sourcing/import-url',{method:'POST',body:JSON.stringify({url})}); p=d.preview||st.preview;
            renderImportPreview(p,url);
            box.insertAdjacentHTML('afterbegin','<div class="helper-diagnostic ok"><strong>Chrome 도우미 전송 완료</strong><div class="muted">실제 네이버 탭에서 수집한 결과가 B2B 서버에 도착했습니다.</div></div>');
            toast('Chrome 실페이지 수집 데이터가 B2B 서버에 도착했습니다.');
            break;
          }
          if((Date.now()-started)%6000<1600){
            const live=await api('/sourcing/browser-helper-status').catch(()=>null);
            if(live?.connected && box.querySelector('.helper-diagnostic')) box.querySelector('.helper-diagnostic').innerHTML=`<strong>Chrome 도우미 연결됨 · v${esc(live.version||'?')}</strong><div class="muted">상태: ${esc(live.last_event||'대기')} · 백그라운드 직접수집 중</div>`;
          }
        }catch{}
      }
      if(p.capture_source!=='USER_CHROME_EXTENSION' && Date.now()-started>=224000) toast('Chrome 도우미에서 상품 데이터가 도착하지 않았습니다. 화면의 연결 상태를 확인해주세요.');
    }else{
      renderImportPreview(p,url);
      toast(p.import_status==='OK'?'상품 정보를 자동으로 가져왔습니다.':'확인된 실제 값만 가져왔습니다. 미수집 항목을 확인해주세요.');
    }
  }catch(e){box.classList.remove('hidden');box.innerHTML=`<strong>자동수집 실패</strong><div class="muted">${esc(e.message)}</div>`;toast(e.message)}
  finally{btn.disabled=false;btn.textContent=before}
}

window.addEventListener('DOMContentLoaded',()=>{
  // 상품 등록은 다른 화면 초기화 오류와 무관하게 가장 먼저 연결한다.
  if($('openProductFormBtn')) $('openProductFormBtn').onclick=()=>{resetProductForm();openModal('productModal')};
  if($('importSourcingUrlBtn'))$('importSourcingUrlBtn').onclick=importSourcingUrl;
  if($('sourcingQuickUrl'))$('sourcingQuickUrl').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();importSourcingUrl()}});
  const d=new Date();$('todayLabel').textContent=d.toLocaleDateString('ko-KR',{year:'numeric',month:'2-digit',day:'2-digit',weekday:'short'});
  document.querySelectorAll('[data-auth-tab]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-auth-tab]').forEach(x=>x.classList.toggle('active',x===b));$('loginForm').classList.toggle('hidden',b.dataset.authTab!=='login');$('signupForm').classList.toggle('hidden',b.dataset.authTab!=='signup')});
  $('loginForm').onsubmit=async e=>{e.preventDefault();try{const d=await api('/auth/login',{method:'POST',body:JSON.stringify({email:$('loginEmail').value.trim(),password:$('loginPassword').value})});localStorage.setItem(TOKEN_KEY,d.access_token);await checkSession();toast('로그인되었습니다.')}catch(err){toast(err.message)}};
  $('signupForm').onsubmit=async e=>{e.preventDefault();try{await api('/auth/signup',{method:'POST',body:JSON.stringify({email:$('signupEmail').value.trim(),password:$('signupPassword').value})});toast('회원가입 완료. 로그인해 주세요.');document.querySelector('[data-auth-tab="login"]').click()}catch(err){toast(err.message)}};
  if($('accountMenuBtn'))$('accountMenuBtn').onclick=(e)=>{e.stopPropagation();const m=$('accountMenu');m.classList.toggle('hidden');$('accountMenuBtn').setAttribute('aria-expanded',String(!m.classList.contains('hidden')))};
  document.addEventListener('click',(e)=>{const m=$('accountMenu');if(!m||m.classList.contains('hidden'))return;if(!e.target.closest('.account-wrap')){m.classList.add('hidden');$('accountMenuBtn')?.setAttribute('aria-expanded','false')}});
  if($('logoutBtn'))$('logoutBtn').onclick=async()=>{try{await api('/auth/logout',{method:'POST'})}catch{}localStorage.removeItem(TOKEN_KEY);location.reload()};
  document.querySelectorAll('.nav-item[data-page]').forEach(b=>b.onclick=()=>setPage(b.dataset.page));document.querySelectorAll('[data-go-page]').forEach(b=>b.onclick=()=>setPage(b.dataset.goPage));
  $('mobileMenuBtn').onclick=()=>document.querySelector('.sidebar').classList.toggle('open');$('refreshHomeBtn').onclick=async()=>{await Promise.all([loadSuppliers(),loadProducts(),loadPricing(),loadLogs()]);toast('새로고침했습니다.')};
  $('globalSearchBtn').onclick=()=>{setPage('products');$('productSearch').value=$('globalSearch').value;loadProducts()};$('globalSearch').addEventListener('keydown',e=>{if(e.key==='Enter')$('globalSearchBtn').click()});
  $('productSearchBtn').onclick=loadProducts;$('openProductFormBtn').onclick=()=>{resetProductForm();openModal('productModal')};$('openSupplierFormBtn').onclick=()=>{resetSupplierForm();openModal('supplierModal')};
  document.querySelectorAll('[data-close-modal]').forEach(b=>b.onclick=closeModals);$('modalBackdrop').onclick=closeModals;
  $('productForm').onsubmit=async e=>{e.preventDefault();const id=$('productId').value;const payload={supplier_id:$('productSupplier').value||null,sku:$('productSku').value.trim()||null,name:$('productName').value.trim(),purchase_price:Number($('purchasePrice').value||0),international_shipping:Number($('internationalShipping').value||0),domestic_shipping:Number($('domesticShipping').value||0),selling_price:Number($('sellingPrice').value||0),fee_rate:Number($('feeRate').value||0),vat_rate:Number($('vatRate').value||.1),main_image_url:$('mainImageUrl').value.trim()||null,detail_image_url:$('detailImageUrl').value.trim()||null};try{await api(id?`/products/${id}`:'/products/',{method:id?'PATCH':'POST',body:JSON.stringify(payload)});closeModals();await Promise.all([loadProducts(),loadPricing(),loadLogs()]);toast(id?'상품을 수정했습니다.':'상품을 등록했습니다.')}catch(err){toast(err.message)}};
  $('supplierForm').onsubmit=async e=>{e.preventDefault();const id=$('supplierId').value;const payload={name:$('supplierName').value.trim(),memo:$('supplierMemo').value.trim()||null};try{await api(id?`/suppliers/${id}`:'/suppliers/',{method:id?'PATCH':'POST',body:JSON.stringify(payload)});closeModals();await loadSuppliers();toast(id?'공급처를 수정했습니다.':'공급처를 등록했습니다.')}catch(err){toast(err.message)}};
  document.body.addEventListener('click',async e=>{const ep=e.target.closest('[data-edit-product]');if(ep)return editProduct(ep.dataset.editProduct);const dp=e.target.closest('[data-delete-product]');if(dp){if(confirm('이 상품을 삭제하시겠습니까?')){try{await api(`/products/${dp.dataset.deleteProduct}`,{method:'DELETE'});await Promise.all([loadProducts(),loadPricing(),loadLogs()]);toast('상품을 삭제했습니다.')}catch(err){toast(err.message)}}return}const es=e.target.closest('[data-edit-supplier]');if(es)return editSupplier(es.dataset.editSupplier);const ds=e.target.closest('[data-delete-supplier]');if(ds){if(confirm('이 공급처를 삭제하시겠습니까?')){try{await api(`/suppliers/${ds.dataset.deleteSupplier}`,{method:'DELETE'});await loadSuppliers();toast('공급처를 삭제했습니다.')}catch(err){toast(err.message)}}}});
  $('recalculateAllBtn').onclick=async()=>{try{await api('/products/recalculate-all',{method:'POST'});await Promise.all([loadProducts(),loadPricing(),loadLogs()]);toast('전체 상품을 재계산했습니다.')}catch(err){toast(err.message)}};$('reloadLogsBtn').onclick=loadLogs;
  $('bulkImportBtn').onclick=async()=>{const f=$('bulkFile').files[0];if(!f)return toast('파일을 선택해 주세요.');const fd=new FormData();fd.append('file',f);try{const d=await api('/bulk-products/import',{method:'POST',body:fd});$('bulkResult').textContent=`등록 ${d.success_count??d.created_count??0}건 · 오류 ${d.error_count??0}건`;await Promise.all([loadProducts(),loadPricing(),loadLogs()]);toast('대량 등록을 처리했습니다.')}catch(err){toast(err.message)}};
  $('templateCsvBtn').onclick=()=>download('/bulk-products/template.csv','product_import_template.csv');$('templateXlsxBtn').onclick=()=>download('/bulk-products/template.xlsx','product_import_template.xlsx');$('exportCsvBtn').onclick=()=>download('/bulk-products/export.csv','products.csv');$('exportXlsxBtn').onclick=()=>download('/bulk-products/export.xlsx','products.xlsx');if($('exportOrdersReportBtn'))$('exportOrdersReportBtn').onclick=()=>download('/reports/orders.csv','orders_report.csv');
  if($('settingsLogoutBtn'))$('settingsLogoutBtn').onclick=doLogout;
  if($('reloadTaxReserveBtn'))$('reloadTaxReserveBtn').onclick=loadTaxReserve;
  if($('saveTaxReserveBtn'))$('saveTaxReserveBtn').onclick=async()=>{try{await api('/tax-reserve/settings',{method:'PATCH',body:JSON.stringify({profit_tax_reserve_rate:Number($('profitTaxReserveRate').value||0),income_tax_reserve_rate:Number($('incomeTaxReserveRate').value||0)})});await loadTaxReserve();toast('세금 적립률을 저장했습니다.')}catch(err){toast(err.message)}};
  if($('logoutBtn'))$('logoutBtn').onclick=doLogout;
  if($('openSourcingBtn'))$('openSourcingBtn').onclick=()=>{ $('sourcingForm').reset(); renderSupplierOptions(); openModal('sourcingModal') };
  if($('openOrderBtn'))$('openOrderBtn').onclick=()=>{ $('orderForm').reset(); $('orderQty').value=1; openModal('orderModal') };
  if($('openPurchaseBtn'))$('openPurchaseBtn').onclick=()=>{ $('purchaseForm').reset(); refreshOrderSelects(); openModal('purchaseModal') };
  if($('openShipmentBtn'))$('openShipmentBtn').onclick=()=>{ $('shipmentForm').reset(); refreshOrderSelects(); openModal('shipmentModal') };
  if($('sourcingForm'))$('sourcingForm').onsubmit=async e=>{e.preventDefault();syncSourcingOptions();const payload={supplier_id:$('sourcingSupplier').value||null,supplier_name:$('sourcingSupplierName')?.value||null,supplier_store_name:$('sourcingStoreName')?.value||null,supplier_store_url:$('sourcingStoreUrl')?.value||null,product_name:$('sourcingName').value.trim(),source_url:$('sourcingUrl').value.trim()||null,source_platform:$('sourcingPlatform')?.value||null,source_product_id:$('sourcingProductId')?.value||null,source_currency:$('sourcingCurrency')?.value||null,import_status:$('sourcingImportStatus')?.value||null,purchase_price:Number($('sourcingPrice').value||0),shipping_fee:Number($('sourcingShipping').value||0),options_text:$('sourcingOptions').value.trim()||null,options_json:$('sourcingOptionsJson')?.value||null,image_url:$('sourcingImage')?.value.trim()||null,image_urls_json:$('sourcingImageUrlsJson')?.value||null,availability:$('sourcingAvailability').value,memo:$('sourcingMemo').value.trim()||null};try{await api('/sourcing/',{method:'POST',body:JSON.stringify(payload)});closeModals();if($('sourcingQuickUrl'))$('sourcingQuickUrl').value='';if($('sourcingImportResult'))$('sourcingImportResult').classList.add('hidden');await Promise.all([loadSourcing(),loadSuppliers(),loadLogs()]);toast('소싱 상품과 공급처 정보를 저장했습니다.')}catch(err){toast(err.message)}};
  if($('orderForm'))$('orderForm').onsubmit=async e=>{e.preventDefault();const payload={channel:$('orderChannel').value,order_no:$('orderNo').value.trim(),product_name:$('orderProductName').value.trim(),option_text:$('orderOption').value.trim()||null,quantity:Number($('orderQty').value||1),sale_price:Number($('orderSalePrice').value||0),expected_profit:Number($('orderProfit').value||0),recipient:$('orderRecipient').value.trim()||null,phone:$('orderPhone').value.trim()||null,postal_code:$('orderPostal').value.trim()||null,address:$('orderAddress').value.trim()||null,detail_address:$('orderDetailAddress').value.trim()||null,supplier_name:$('orderSupplier').value.trim()||null,source_url:$('orderSourceUrl').value.trim()||null};try{await api('/orders/',{method:'POST',body:JSON.stringify(payload)});closeModals();await Promise.all([loadOrders(),loadPurchases(),loadShipments(),loadLogs()]);toast('주문을 등록했습니다.')}catch(err){toast(err.message)}};
  if($('purchaseForm'))$('purchaseForm').onsubmit=async e=>{e.preventDefault();const payload={order_id:$('purchaseOrderSelect').value,supplier_name:$('purchaseSupplier').value.trim()||null,supplier_url:$('purchaseUrl').value.trim()||null,amount:Number($('purchaseAmount').value||0),note:$('purchaseNote').value.trim()||null};try{await api('/purchases/',{method:'POST',body:JSON.stringify(payload)});closeModals();await Promise.all([loadPurchases(),loadOrders(),loadLogs()]);toast('발주 준비를 저장했습니다.')}catch(err){toast(err.message)}};
  if($('shipmentForm'))$('shipmentForm').onsubmit=async e=>{e.preventDefault();const payload={order_id:$('shipmentOrderSelect').value,carrier:$('shipmentCarrier').value.trim()||null,tracking_no:$('shipmentTrackingNo').value.trim()||null,status:$('shipmentStatus').value,expected_delivery:$('shipmentExpected').value||null};try{await api('/shipping/',{method:'POST',body:JSON.stringify(payload)});closeModals();await Promise.all([loadShipments(),loadOrders(),loadLogs()]);toast('송장을 등록했습니다.')}catch(err){toast(err.message)}};
  if($('aiProductSelect'))$('aiProductSelect').onchange=()=>{const p=products.find(x=>x.id===$('aiProductSelect').value);if(p)$('aiSourceName').value=p.name||''};
  if($('generateAiDraftBtn'))$('generateAiDraftBtn').onclick=async()=>{const name=$('aiSourceName').value.trim();if(!name)return toast('상품명을 입력해 주세요.');try{await api('/ai-content/draft',{method:'POST',body:JSON.stringify({product_id:$('aiProductSelect').value||null,source_name:name})});await Promise.all([loadAiDrafts(),loadLogs()]);toast('상품 초안을 생성했습니다.')}catch(err){toast(err.message)}};
  document.body.addEventListener('click',e=>{const b=e.target.closest('[data-home-order]');if(!b)return;setPage('orders');});
  document.body.addEventListener('click',async e=>{const b=e.target.closest('[data-prepare-payment]');if(!b)return;try{const d=await api(`/purchases/prepare/${b.dataset.preparePayment}`,{method:'POST'});await Promise.all([loadOrders(),loadPurchases(),loadLogs()]);if(d.ready&&d.purchase?.checkout_url){window.open(d.purchase.checkout_url,'_blank','noopener');toast('주문정보 검수를 통과했습니다. 공급처 결제 화면을 열었습니다.')}else{toast((d.errors||['결제 준비에 실패했습니다.']).join(' '))}}catch(err){toast(err.message)}});
  document.body.addEventListener('click',async e=>{const a=e.target.closest('[data-after-sales]');if(!a)return;const type=a.dataset.requestType;const label=type==='RETURN'?'반품':'교환';if(!confirm(`${label} 요청을 처리하시겠습니까?`))return;try{const d=await api('/after-sales/',{method:'POST',body:JSON.stringify({order_id:a.dataset.afterSales,request_type:type,reason:`판매자 화면에서 ${label}`,refund_amount:0})});await Promise.all([loadOrders(),loadPurchases(),loadShipments(),loadTaxReserve(),loadLogs()]);toast(d.request?.status==='COMPLETED'?`${label} 처리를 완료했습니다.`:`${label} 요청을 접수했습니다. 공급처 확인이 필요합니다.`)}catch(err){toast(err.message)}});
  document.body.addEventListener('click',async e=>{const ds=e.target.closest('[data-delete-sourcing]');if(ds){if(confirm('이 소싱 항목을 삭제하시겠습니까?')){await api(`/sourcing/${ds.dataset.deleteSourcing}`,{method:'DELETE'});await loadSourcing();toast('삭제했습니다.')}return}const od=e.target.closest('[data-delete-order]');if(od){if(confirm('이 주문을 삭제하시겠습니까?')){await api(`/orders/${od.dataset.deleteOrder}`,{method:'DELETE'});await loadOrders();toast('주문을 삭제했습니다.')}return}const os=e.target.closest('[data-order-status]');if(os){await api(`/orders/${os.dataset.orderStatus}`,{method:'PATCH',body:JSON.stringify({status:os.dataset.nextStatus})});await loadOrders();toast('주문 상태를 변경했습니다.');return}const pp=e.target.closest('[data-purchase-paid]');if(pp){await api(`/purchases/${pp.dataset.purchasePaid}`,{method:'PATCH',body:JSON.stringify({status:'PAID'})});await Promise.all([loadPurchases(),loadOrders(),loadLogs()]);toast('결제 완료로 변경했습니다.');return}const sc=e.target.closest('[data-save-competitor]');if(sc){const input=document.querySelector(`[data-competitor-input="${CSS.escape(sc.dataset.saveCompetitor)}"]`);await api(`/price-tracking/${sc.dataset.saveCompetitor}`,{method:'PATCH',body:JSON.stringify({competitor_price:input.value===''?null:Number(input.value)})});await Promise.all([loadPriceTracking(),loadLogs()]);toast('경쟁가를 저장했습니다.');return}});
  document.body.addEventListener('change',async e=>{const ss=e.target.closest('[data-shipment-status]');if(ss){await api(`/shipping/${ss.dataset.shipmentStatus}`,{method:'PATCH',body:JSON.stringify({status:ss.value})});await Promise.all([loadShipments(),loadOrders(),loadLogs()]);toast('배송 상태를 변경했습니다.')}});
  if($('runAutomationBtn'))$('runAutomationBtn').onclick=async()=>{try{const d=await api('/automation/run',{method:'POST'});await Promise.all([loadProducts(),loadPriceTracking(),loadAutomationHistory(),loadLogs()]);toast(`가격 자동화 ${d.changed||0}건 처리`)}catch(e){toast(e.message)}};
  if($('loadAutomationHistoryBtn'))$('loadAutomationHistoryBtn').onclick=loadAutomationHistory;
  document.body.addEventListener('click',async e=>{const r=e.target.closest('[data-save-auto-rule]');if(r){const id=r.dataset.saveAutoRule;const enabled=document.querySelector(`[data-auto-enabled="${CSS.escape(id)}"]`)?.checked??true;const amount=Number(document.querySelector(`[data-undercut-input="${CSS.escape(id)}"]`)?.value||0);try{await api(`/automation/rules/${id}`,{method:'PATCH',body:JSON.stringify({enabled,undercut_amount:amount,auto_stop:true,auto_resume:true})});await loadPriceTracking();toast('자동화 규칙을 저장했습니다.')}catch(err){toast(err.message)}return}const i=e.target.closest('[data-save-integration]');if(i){const ch=i.dataset.saveIntegration;const enabled=document.querySelector(`[data-integration-enabled="${CSS.escape(ch)}"]`)?.checked??false;const account_label=document.querySelector(`[data-integration-label="${CSS.escape(ch)}"]`)?.value.trim()||null;try{await api(`/integrations/${ch}`,{method:'PATCH',body:JSON.stringify({enabled,account_label,note:'API 자격증명은 서버 환경변수에서 관리'})});await loadIntegrations();toast(`${ch} 연결 설정을 저장했습니다.`)}catch(err){toast(err.message)}return}const t=e.target.closest('[data-test-integration]');if(t){const ch=t.dataset.testIntegration;t.disabled=true;const before=t.textContent;t.textContent='확인 중...';try{const d=await api(`/integrations/${ch}/test`,{method:'POST'});toast(d.message||`${ch} API 연결 성공`)}catch(err){toast(err.message)}finally{t.disabled=false;t.textContent=before}return}});
  checkSession();
});
