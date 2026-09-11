(()=>{
  'use strict';
  const clean=v=>String(v??'').replace(/\s+/g,' ').trim();
  const badShell=/^(?:browser|naver|로그인)$/i;
  const priceRe=/\(([+-])\s*([\d,]+)\s*원\)\s*$/;
  const stripPrice=v=>clean(v).replace(priceRe,'').trim();
  const key=v=>stripPrice(v).replace(/[\s_]+/g,'').toLowerCase();
  const internalName=v=>/^(?:standardCombinations?|supplementProducts?|additionalProducts?|optionProducts?|options?|values?|items?|list)$/i.test(clean(v));
  const invalidValue=v=>!clean(v)||/^https?:\/\//i.test(clean(v));
  const flatten=a=>(Array.isArray(a)?a:[a]).flat(3);
  const finiteMoney=v=>{
    if(typeof v==='string')v=v.replace(/[^\d.-]/g,'');
    const n=Number(v);return Number.isFinite(n)&&n>=0&&n<=1_000_000_000?n:null;
  };
  function normalizeName(candidates){
    for(const raw of flatten(candidates)){
      const value=clean(raw);
      if(!value||value.length<2||value.length>500||badShell.test(value)||/에러페이지|시스템오류|captcha|access denied/i.test(value))continue;
      return value;
    }
    return '';
  }
  function normalizeMoney(candidates,{allowZero=true}={}){
    const values=flatten(candidates).map(finiteMoney).filter(v=>v!=null&&(allowZero||v>0));
    if(!values.length)return null;
    return values[0];
  }
  function normalizeImages(candidates){
    const out=[],seen=new Set();
    for(const raw of flatten(candidates)){
      const value=clean(raw);if(!/^https?:\/\//i.test(value))continue;
      let normalized=value;
      try{const u=new URL(value);u.searchParams.delete('type');normalized=u.href}catch{}
      if(/ntm\.pstatic|favicon|(?:^|[\/_-])(?:logo|icon)(?:[\/_-]|\.)|\.js(?:$|\?)/i.test(normalized))continue;
      const k=normalized.toLowerCase();if(seen.has(k))continue;seen.add(k);out.push(normalized);
      if(out.length>=50)break;
    }
    return out;
  }
  const deltaFromText=v=>{
    const m=clean(v).match(priceRe);if(!m)return 0;
    const n=Number(m[2].replace(/,/g,''))||0;return m[1]==='-'?-n:n;
  };
  const preferValue=(oldValue,newValue)=>{
    if(!oldValue)return newValue;
    const oldPriced=priceRe.test(clean(oldValue)),newPriced=priceRe.test(clean(newValue));
    if(newPriced&&!oldPriced)return newValue;
    return oldValue;
  };
  function normalizeGroups(groups,{additional=false}={}){
    const out=[],byName=new Map();
    for(const [index,raw] of (Array.isArray(groups)?groups:[]).slice(0,100).entries()){
      if(!raw||!Array.isArray(raw.values))continue;
      let name=clean(raw.name);
      if(!name||internalName(name))name=`${additional?'추가 옵션':'옵션'} ${index+1}`;
      const nk=key(name)||`${additional?'extra':'main'}:${index}`;
      let target=byName.get(nk);
      if(!target){target={name,values:[]};byName.set(nk,target);out.push(target)}
      const valueIndex=new Map(target.values.map((v,i)=>[key(v),i]));
      for(const rawValue of raw.values.slice(0,2000)){
        const value=clean(rawValue);if(invalidValue(value))continue;
        const vk=key(value);if(!vk)continue;
        const oldIndex=valueIndex.get(vk);
        if(oldIndex==null){valueIndex.set(vk,target.values.length);target.values.push(value)}
        else target.values[oldIndex]=preferValue(target.values[oldIndex],value);
      }
    }
    const nonEmpty=out.filter(g=>g.values.length),dedup=[],signatures=new Map();
    for(const group of nonEmpty){
      const signature=group.values.map(key).filter(Boolean).sort().join('|');
      if(!signature)continue;
      const oldIndex=signatures.get(signature);
      if(oldIndex==null){signatures.set(signature,dedup.length);dedup.push(group);continue}
      const generic=n=>/^(?:옵션|추가\s*옵션)\s*\d+$/i.test(clean(n));
      if(generic(dedup[oldIndex].name)&&!generic(group.name))dedup[oldIndex]=group;
    }
    return dedup;
  }
  function normalizeVariants(variants){
    const out=[],seen=new Set();
    for(const raw of (Array.isArray(variants)?variants:[]).slice(0,10000)){
      const options=[];
      for(const pair of (Array.isArray(raw?.options)?raw.options:[])){
        const name=clean(pair?.name),value=clean(pair?.value);
        if(!name||internalName(name)||invalidValue(value))continue;
        options.push({name,value});
      }
      if(!options.length)continue;
      const signature=options.map(x=>`${key(x.name)}=${key(x.value)}`).join('|');
      if(!signature||seen.has(signature))continue;seen.add(signature);
      let additionalPrice=Number(raw?.additional_price);
      if(!Number.isFinite(additionalPrice))additionalPrice=0;
      if(additionalPrice===0){
        for(const option of options){const parsed=deltaFromText(option.value);if(parsed!==0){additionalPrice=parsed;break}}
      }
      const availability=String(raw?.availability||'AVAILABLE').toUpperCase()==='OUT_OF_STOCK'?'OUT_OF_STOCK':'AVAILABLE';
      out.push({options,additional_price:additionalPrice,availability});
    }
    return out;
  }
  function normalizePayload(payload){
    const source=payload&&typeof payload==='object'?payload:{};
    const candidates=source.normalizationCandidates&&typeof source.normalizationCandidates==='object'?source.normalizationCandidates:{};
    const {normalizationCandidates,...rest}=source;
    const optionGroups=normalizeGroups(source.optionGroups?.length?source.optionGroups:candidates.optionGroups);
    const additionalOptionGroups=normalizeGroups(source.additionalOptionGroups?.length?source.additionalOptionGroups:candidates.additionalOptionGroups,{additional:true});
    const optionVariants=normalizeVariants(source.optionVariants?.length?source.optionVariants:candidates.optionVariants);
    const productName=normalizeName([source.productName,candidates.productNames]);
    const storeName=normalizeName([source.storeName,candidates.storeNames]);
    // The capture layer's shopper-visible sale price is authoritative. Never replace it
    // with a smaller benefit/point/meta number from secondary normalization candidates.
    const directPrice=finiteMoney(source.price);
    const price=directPrice!=null&&directPrice>0?directPrice:normalizeMoney(candidates.prices,{allowZero:false});
    const shippingFee=normalizeMoney([source.shippingFee,candidates.shippingFees]);
    const imageUrls=normalizeImages([source.imageUrls,candidates.imageUrls]);
    const availability=['AVAILABLE','OUT_OF_STOCK','UNKNOWN'].includes(String(source.availability||'').toUpperCase())?String(source.availability).toUpperCase():'UNKNOWN';
    return {
      ...rest,productName,storeName,price,shippingFee,imageUrls,availability,
      optionGroups,additionalOptionGroups,optionVariants,
      normalizationSummary:{schema_version:1,images:imageUrls.length,option_groups:optionGroups.length,additional_option_groups:additionalOptionGroups.length,variants:optionVariants.length}
    };
  }
  window.B2BOptionAnalyzer=Object.freeze({normalizeName,normalizeMoney,normalizeImages,normalizeGroups,normalizeVariants,normalizePayload});
})();
