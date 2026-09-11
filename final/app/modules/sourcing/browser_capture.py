from __future__ import annotations
import json, time, re
from typing import Any
from urllib.parse import urlparse
from .url_importer import parse_product_html, _better, ImportedProduct, detect_platform

_CAPTURES: dict[str, dict[str, Any]] = {}
MAX_AGE = 180.0


def _clean_text(value: Any) -> str:
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def _clean_money(value: Any, *, allow_zero: bool = True) -> float | None:
    if isinstance(value, str):
        value=re.sub(r'[^\d.-]', '', value)
    try:
        number=float(value)
    except (TypeError, ValueError):
        return None
    if number < 0 or number > 1_000_000_000 or (not allow_zero and number == 0):
        return None
    return number


def _normalize_images(values: Any) -> list[str]:
    out=[]
    for raw in values if isinstance(values, list) else []:
        value=_clean_text(raw)
        if not re.match(r'^https?://', value, re.I):
            continue
        if re.search(r'ntm\.pstatic|favicon|(?:^|[/_-])(?:logo|icon)(?:[/_.-]|$)|\.js(?:$|\?)', value, re.I):
            continue
        identity=value.casefold()
        if identity not in {x.casefold() for x in out}:
            out.append(value)
        if len(out) >= 50:
            break
    return out


def _normalize_groups(groups: Any, prefix: str) -> list[dict[str, Any]]:
    out=[]; locations={}
    price_re=re.compile(r'\(([+-])\s*[\d,]+\s*원\)\s*$')
    key=lambda value: re.sub(r'[\s_]+', '', price_re.sub('', _clean_text(value))).casefold()
    for idx, group in enumerate(groups if isinstance(groups, list) else [], 1):
        if not isinstance(group, dict):
            continue
        name=_clean_text(group.get('name')) or f'{prefix} {idx}'
        nk=key(name) or f'{prefix}:{idx}'
        if nk not in locations:
            locations[nk]=len(out);out.append({'name':name,'values':[]})
        target=out[locations[nk]]['values']; value_locations={key(v):i for i,v in enumerate(target)}
        for raw in group.get('values') or []:
            value=_clean_text(raw);vk=key(value)
            if not value or not vk or re.match(r'^https?://', value, re.I):
                continue
            old=value_locations.get(vk)
            if old is None:
                value_locations[vk]=len(target);target.append(value)
            elif not price_re.search(target[old]) and price_re.search(value):
                target[old]=value
    dedup=[];signatures={}
    generic=re.compile(r'^(?:옵션|추가\s*옵션)\s*\d+$', re.I)
    for group in (group for group in out if group['values']):
        signature='|'.join(sorted(key(v) for v in group['values'] if key(v)))
        if not signature:
            continue
        old=signatures.get(signature)
        if old is None:
            signatures[signature]=len(dedup);dedup.append(group)
        elif generic.match(dedup[old]['name']) and not generic.match(group['name']):
            dedup[old]=group
    return dedup[:100]


def _normalize_variants(variants: Any) -> list[dict[str, Any]]:
    out=[];seen=set()
    for raw in variants if isinstance(variants, list) else []:
        if not isinstance(raw, dict):
            continue
        options=[]
        for pair in raw.get('options') or []:
            if not isinstance(pair, dict):
                continue
            name=_clean_text(pair.get('name'));value=_clean_text(pair.get('value'))
            if name and value and not re.match(r'^https?://', value, re.I):
                options.append({'name':name,'value':value, **({'id':str(pair['id'])} if pair.get('id') is not None else {})})
        signature=json.dumps(options, ensure_ascii=False, sort_keys=True)
        if not signature or signature in seen:
            continue
        seen.add(signature)
        try: additional=float(raw.get('additional_price') or 0)
        except (ValueError, TypeError): additional=0
        availability=str(raw.get('availability') or 'UNKNOWN').upper()
        if availability not in {'AVAILABLE','OUT_OF_STOCK','UNKNOWN'}: availability='UNKNOWN'
        out.append({'options':options,'additional_price':None if raw.get('additional_price') is None else additional,'availability':availability,'verification_status':raw.get('verification_status') or 'VERIFIED'})
    return out


def _key(url: str) -> str:
    p=urlparse(url)
    m=re.search(r'/products/(\d+)', p.path)
    if m:
        return f"NAVER:{m.group(1)}"
    return url.split('?',1)[0]


def save_capture(url: str, html: str, title: str = '', state: Any = None) -> dict[str, Any]:
    platform=detect_platform(urlparse(url).hostname or '')
    if platform not in {'NAVER_SMARTSTORE','NAVER_SHOPPING'}:
        raise ValueError('현재 브라우저 직접수집은 네이버 상품 URL만 받습니다.')
    html=(html or '')[:8_000_000]
    best=parse_product_html(html, url, url, 200, 'USER_CHROME_DOM')
    clean_groups=[]
    extra_groups=[]
    direct={}
    option_variants=[]
    raw_network_groups=[]
    raw_network_extra_groups=[]
    option_capture_diagnostics={}
    ai_judgment={}
    if state:
        try:
            blob=json.dumps(state, ensure_ascii=False)[:6_000_000]
            candidate=parse_product_html(f'<html><body><script>{blob}</script></body></html>',url,url,200,'USER_CHROME_STATE')
            best=_better(best,candidate)

            # The extension's __B2B_DIRECT__ values come from the exact visible purchase/gallery
            # regions. They must win over broad HTML heuristics (which can pick marketing text,
            # recommendations, or dozens of unrelated images).
            direct=state.get('__B2B_DIRECT__') if isinstance(state,dict) else None
            if isinstance(direct,dict):
                name=str(direct.get('productName') or '').strip()
                if name and name.casefold() not in {'browser','naver','로그인'} and '에러페이지' not in name:
                    best.product_name=name
                store=str(direct.get('storeName') or '').strip()
                if store:
                    best.supplier_store_name=store
                    best.supplier_name=f'네이버-{store}'
                store_url=str(direct.get('storeUrl') or '').strip()
                if store_url: best.supplier_store_url=store_url
                price=direct.get('price')
                if isinstance(price,(int,float)) and price>=0: best.purchase_price=float(price)
                shipping=direct.get('shippingFee')
                if isinstance(shipping,(int,float)) and shipping>=0: best.shipping_fee=float(shipping)
                imgs=direct.get('imageUrls')
                if isinstance(imgs,list):
                    clean_imgs=[]
                    for x in imgs:
                        x=str(x or '').strip()
                        if x and x not in clean_imgs and 'ntm.pstatic.net' not in x and not x.lower().endswith('.js'):
                            clean_imgs.append(x)
                    # Empty direct gallery means unknown; non-empty direct gallery is authoritative.
                    if clean_imgs: best.image_urls=clean_imgs[:50]
                groups=direct.get('optionGroups')
                if isinstance(groups,list):
                    for idx,g in enumerate(groups,1):
                        if not isinstance(g,dict): continue
                        gn=str(g.get('name') or f'옵션{idx}').strip() or f'옵션{idx}'
                        vals=[]
                        for v in g.get('values') or []:
                            v=str(v or '').strip()
                            if v and v not in vals: vals.append(v)
                        if vals: clean_groups.append({'name':gn,'values':vals})
                    # If direct capture inspected the option area, never resurrect heuristic options.
                    best.option_groups=clean_groups or None
                    best.options=[v for g in clean_groups for v in g['values']] or None
                extra=direct.get('additionalOptionGroups')
                if isinstance(extra,list):
                    for idx,g in enumerate(extra,1):
                        if not isinstance(g,dict): continue
                        gn=str(g.get('name') or f'추가옵션{idx}').strip() or f'추가옵션{idx}'
                        vals=[]
                        for v in g.get('values') or []:
                            v=str(v or '').strip()
                            if v and v not in vals: vals.append(v)
                        if vals: extra_groups.append({'name':gn,'values':vals})
                raw_network_groups=direct.get('rawNetworkOptionGroups') if isinstance(direct.get('rawNetworkOptionGroups'), list) else []
                raw_network_extra_groups=direct.get('rawNetworkAdditionalOptionGroups') if isinstance(direct.get('rawNetworkAdditionalOptionGroups'), list) else []
                raw_variants=direct.get('optionVariants')
                if isinstance(raw_variants,list):
                    for rv in raw_variants:
                        if not isinstance(rv,dict): continue
                        opts=[]
                        for pair in rv.get('options') or []:
                            if not isinstance(pair,dict): continue
                            n=str(pair.get('name') or '').strip(); v=str(pair.get('value') or '').strip()
                            if n and v: opts.append({'name':n,'value':v, **({'id':str(pair['id'])} if pair.get('id') is not None else {})})
                        if opts:
                            option_variants.append({'options':opts,'additional_price':rv.get('additional_price'),'availability':rv.get('availability') or 'UNKNOWN','verification_status':rv.get('verification_status') or 'VERIFIED'})
                av=str(direct.get('availability') or '').upper()
                if av in {'AVAILABLE','OUT_OF_STOCK','UNKNOWN'}: best.availability=av
                raw_diag=direct.get('optionDiagnostics')
                if isinstance(raw_diag,dict):
                    # Ephemeral troubleshooting data only. Keep it bounded and out of SQLite/Supabase.
                    option_capture_diagnostics=raw_diag
                raw_ai=direct.get('aiJudgment')
                if isinstance(raw_ai,dict):
                    ai_judgment=raw_ai
        except Exception:
            pass
    # Server-side boundary normalization protects saved previews even if an older helper
    # sends whitespace, duplicates, URL noise, or string-form money values.
    clean_groups=_normalize_groups(clean_groups, '옵션')
    extra_groups=_normalize_groups(extra_groups, '추가 옵션')
    option_variants=_normalize_variants(option_variants)
    best.product_name=_clean_text(best.product_name) or None
    best.purchase_price=_clean_money(best.purchase_price, allow_zero=False)
    best.shipping_fee=_clean_money(best.shipping_fee)
    best.image_urls=_normalize_images(best.image_urls)
    best.option_groups=clean_groups or None
    best.options=[v for g in clean_groups for v in g['values']] or None

    # Real user Chrome capture is meaningful only when the document is not the Naver error shell.
    tl=(title or '').lower()
    if '에러페이지' in tl or '시스템오류' in tl:
        best.import_status='API_REQUIRED'
        best.import_message='일반 Chrome에서도 네이버 오류페이지가 열렸습니다. 정상 상품 페이지를 연 뒤 다시 자동수집하세요.'
    else:
        # Never surface browser/login shell text as product data.
        if (best.product_name or '').strip().casefold() in {'browser','naver','로그인'}:
            best.product_name=None
        if 'nid.naver.com' in (best.final_url or ''):
            best.final_url=url
        best.image_urls=[u for u in (best.image_urls or []) if 'ntm.pstatic.net' not in u and not u.lower().endswith('.js')] or None
        critical=sum([best.purchase_price is not None, best.shipping_fee is not None, bool(best.option_groups or best.options), bool(best.product_name), bool(best.image_urls), best.availability != 'UNKNOWN'])
        if critical >= 5:
            best.import_status='OK'
            best.import_message='일반 Chrome의 실제 렌더링 상품 페이지에서 가격·배송·옵션 정보를 직접 수집했습니다.'
        else:
            best.import_status='PARTIAL'
            best.import_message='일반 Chrome 실제 페이지를 수집했지만 일부 필드가 페이지 내부에 노출되지 않았습니다.'
    payload=best.to_dict()
    # Keep Naver's optional accessory/add-on dropdowns separate from the required product options.
    try:
        payload['additional_option_groups']=extra_groups
        payload['option_variants']=option_variants
        payload['options_json']=json.dumps({
            'groups': clean_groups,
            'additional_groups': extra_groups,
            'variants': option_variants,
            'ai_judgment': ai_judgment,
            'raw_network_groups': raw_network_groups,
            'raw_network_additional_groups': raw_network_extra_groups,
        }, ensure_ascii=False)
    except Exception:
        payload['additional_option_groups']=[]
    payload['collection_status']=direct.get('collectionStatus', 'PARTIAL') if isinstance(direct,dict) else 'PARTIAL'
    if payload['collection_status']=='PARTIAL':
        payload['import_status']='PARTIAL'
        payload['import_message']='수집된 데이터는 저장되었습니다. 시간 제한 또는 일부 옵션 오류로 부분 수집되었습니다.'
    payload['capture_source']='USER_CHROME_EXTENSION'
    payload['option_capture_diagnostics']=option_capture_diagnostics
    payload['ai_judgment']=ai_judgment
    payload['captured_at']=time.time()
    _CAPTURES[_key(url)]={'ts':time.time(),'preview':payload}
    return payload


def get_capture(url: str) -> dict[str, Any] | None:
    now=time.time()
    for k in list(_CAPTURES):
        if now-_CAPTURES[k]['ts'] > MAX_AGE:
            _CAPTURES.pop(k,None)
    row=_CAPTURES.get(_key(url))
    return row['preview'] if row else None
