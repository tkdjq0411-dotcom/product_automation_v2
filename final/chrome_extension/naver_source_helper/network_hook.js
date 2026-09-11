(()=>{
  // Passive capture only. Never clicks, scrolls or changes the page.
  if(window.__B2B_NETWORK_HOOK__) return;
  window.__B2B_NETWORK_HOOK__ = true;
  const cache=[];
  const MAX=250, MAX_BODY=10000000;
  const push=(url,body)=>{
    try{
      const s=String(body||'');
      if(!s || s.length<2) return;
      cache.push({url:String(url||''), body:s.slice(0,MAX_BODY), ts:Date.now()});
      while(cache.length>MAX) cache.shift();
    }catch(_){ }
  };
  try{
    const ofetch=window.fetch;
    if(typeof ofetch==='function') window.fetch=async function(...args){
      const r=await ofetch.apply(this,args);
      try{
        const u=String(args?.[0]?.url||args?.[0]||r.url||'');
        const ct=(r.headers?.get?.('content-type')||'').toLowerCase();
        if(/json|javascript|text/.test(ct)||/product|option|commerce|store|shopping/i.test(u)){
          r.clone().text().then(t=>push(u,t)).catch(()=>{});
        }
      }catch(_){ }
      return r;
    };
  }catch(_){ }
  try{
    const oopen=XMLHttpRequest.prototype.open, osend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open=function(method,url,...rest){this.__b2bUrl=String(url||'');return oopen.call(this,method,url,...rest)};
    XMLHttpRequest.prototype.send=function(...args){
      this.addEventListener('load',()=>{
        try{
          const ct=(this.getResponseHeader('content-type')||'').toLowerCase();
          if((/json|javascript|text/.test(ct)||/product|option|commerce|store|shopping/i.test(this.__b2bUrl||'')) && typeof this.responseText==='string') push(this.__b2bUrl,this.responseText);
        }catch(_){ }
      },{once:true});
      return osend.apply(this,args);
    };
  }catch(_){ }

  const isObj=v=>v&&typeof v==='object';
  const clean=s=>String(s??'').replace(/\s+/g,' ').trim();
  const uniq=a=>[...new Set(a.filter(Boolean))];
  const imgNorm=u=>{try{const x=new URL(String(u||''),location.href);x.searchParams.delete('type');return x.href}catch{return String(u||'')}};
  const imgOk=u=>/^https?:/i.test(String(u||''))&&/(?:pstatic|naver)/i.test(String(u||''))&&!/(?:logo|icon|profile|banner|sp_|sprite|emoji)/i.test(String(u||''));
  const badVal=/^(?:선택|옵션|옵션선택|추가\s*옵션|품절)$/i;
  const uiBad=/스마트봇|고객센터|언어선택|로그인|장바구니|리뷰|구매평|배송비|무료배송|적립|쿠폰|혜택|톡톡문의|찜하기/i;
  const valueText=(v,allowGenericPrice=false)=>{
    if(v==null) return '';
    if(typeof v==='string'||typeof v==='number') return clean(v);
    if(!isObj(v)) return '';
    let s='';
    for(const k of ['optionValue','valueName','optionValueName','displayName','name','label','title','text','productName']){
      if(v[k]!=null && (typeof v[k]==='string'||typeof v[k]==='number')) {s=clean(v[k]); if(s) break;}
    }
    if(!s) return '';
    let add=Number(v.addPrice??v.additionalPrice??v.optionPrice??v.priceDelta??v.extraPrice??v.surcharge??NaN);
    // Supplemental-product payloads often expose the buyer-visible add-on amount simply as
    // price/salePrice rather than addPrice. Only allow those generic keys inside an extra path.
    if(allowGenericPrice&&!Number.isFinite(add)){
      for(const k of ['price','salePrice','discountedPrice','discountPrice','finalPrice','productPrice']){
        const n=Number(v?.[k]); if(Number.isFinite(n)){add=n;break}
      }
    }
    if(Number.isFinite(add)&&add!==0&&!/[+-]\s*[\d,]+\s*원/.test(s)) s+=` (${add>0?'+':''}${add.toLocaleString('ko-KR')}원)`;
    const sold=Boolean(v.soldOut??v.isSoldOut??v.outOfStock??v.disabled===true??false) || /SOLD_OUT|OUT_OF_STOCK/i.test(String(v.status||''));
    if(sold&&!/품절/.test(s)) s+=' (품절)';
    return clean(s);
  };
  const labelText=(o)=>{
    if(!isObj(o)) return '';
    for(const k of ['optionName','groupName','optionGroupName','name','label','title']){
      const x=o[k]; if(typeof x==='string'&&clean(x)&&clean(x).length<100) return clean(x);
    }
    return '';
  };
  const optionish=k=>/option|choice|select|variant|combination|supplement|additional|extra|add[-_]?on/i.test(String(k||''));
  const extraish=k=>/supplement|additional|extra|add[-_]?on|추가/i.test(String(k||''));
  const validValue=s=>{s=clean(s);return !!s&&!/^https?:\/\//i.test(s)&&s.length<=220&&!badVal.test(s)&&!uiBad.test(s)};
  const groups=[], extras=[], images=[], variants=[], standardCombinationRecords=[];
  const variantSeen=new Set();
  const groupSeen=new Set();
  const addVariant=(pairs,node={})=>{
    const options=(pairs||[]).filter(x=>x&&validValue(x.value)&&clean(x.name)).map(x=>({name:clean(x.name),value:clean(x.value)}));
    if(!options.length)return;
    const key=options.map(x=>x.name+'='+x.value).join('|');
    if(!key||variantSeen.has(key))return; variantSeen.add(key);
    let additional=null;
    for(const k of ['addPrice','additionalPrice','optionPrice','priceDelta']){const n=Number(node?.[k]);if(Number.isFinite(n)){additional=n;break}}
    const sold=Boolean(node?.soldOut??node?.isSoldOut??node?.outOfStock??node?.disabled===true??false)||/SOLD_OUT|OUT_OF_STOCK/i.test(String(node?.status||''));
    variants.push({options,additional_price:additional,availability:sold?'OUT_OF_STOCK':'AVAILABLE'});
  };

  const addGroup=(target,name,vals)=>{
    vals=uniq((vals||[]).map(valueText).filter(validValue));
    name=clean(name)||`${target===extras?'추가옵션':'옵션'}${target.length+1}`;
    if(!vals.length||uiBad.test(name)) return;
    const key=(target===extras?'E':'M')+'|'+name+'|'+vals.join('|');
    if(groupSeen.has(key)) return; groupSeen.add(key); target.push({name,values:vals});
  };
  const scanOptions=(node,path='',depth=0,seen=new WeakSet())=>{
    if(depth>30||!isObj(node)) return;
    if(seen.has(node)) return; seen.add(node);
    const pathExtra=extraish(path), pathOpt=optionish(path);
    if(Array.isArray(node)){
      if(pathOpt&&node.length){
        const vals=node.map(x=>valueText(x,pathExtra)).filter(validValue);
        if(vals.length>=1){
          const seg=path.split('.').filter(Boolean).pop()||'';
          const name=/options?|values?|items?|list/i.test(seg)?'':seg;
          addGroup(pathExtra?extras:groups,name,vals);
        }
      }
      for(let i=0;i<Math.min(node.length,10000);i++) scanOptions(node[i],`${path}[${i}]`,depth+1,seen);
      return;
    }
    if(/standardCombinations\[\d+\]$/.test(path)&&typeof node.name==='string'&&/^_.*__$/.test(node.name)){
      let additional=null,availability='UNKNOWN';
      for(const key of ['addPrice','additionalPrice','optionPrice','priceDelta']){
        if(node[key]!==null&&node[key]!==undefined&&node[key]!==''&&Number.isFinite(Number(node[key]))){additional=Number(node[key]);break;}
      }
      for(const key of ['soldOut','isSoldOut','outOfStock']){
        if(typeof node[key]==='boolean'){availability=node[key]?'OUT_OF_STOCK':'AVAILABLE';break;}
      }
      if(/^(SOLD_OUT|OUT_OF_STOCK)$/.test(String(node.status||'')))availability='OUT_OF_STOCK';
      standardCombinationRecords.push({encodedPath:node.name,additional_price:additional,availability});
    }
    // Common group object: {name, options:[...]}
    const nm=labelText(node);
    for(const k of Object.keys(node)){
      const v=node[k];
      if(Array.isArray(v)&&optionish(k||path)){
        const vals=v.map(x=>valueText(x,pathExtra||extraish(k))).filter(validValue);
        if(vals.length) addGroup((pathExtra||extraish(k))?extras:groups,nm||k,vals);
      }
    }
    // Combination forms such as optionName1/optionValue1. Keep the full row as a variant
    // so dependent options (상품명 -> 호수 -> ...) can be reconstructed in the B2B UI.
    const comboPairs=[];
    for(let i=1;i<=30;i++){
      const n=node[`optionName${i}`]??node[`option${i}Name`]??node[`option_name${i}`]??node[`name${i}`];
      const v=node[`optionValue${i}`]??node[`option${i}Value`]??node[`option_value${i}`]??node[`value${i}`];
      if(n!=null&&v!=null){addGroup(pathExtra?extras:groups,clean(n),[v]);comboPairs.push({name:n,value:v});}
    }
    if(comboPairs.length) addVariant(comboPairs,node);

    // Some Naver payloads store combinations as arrays of {name,value} / {optionName,optionValue}.
    for(const k of ['selectedOptions','optionValues','optionCombination','combination','choices']){
      const arr=node[k]; if(!Array.isArray(arr))continue;
      const pairs=arr.map(x=>isObj(x)?{name:x.optionName??x.groupName??x.name??x.label,value:x.optionValue??x.valueName??x.value??x.text}:null).filter(x=>x&&x.name!=null&&x.value!=null);
      if(pairs.length) addVariant(pairs,node);
    }
    for(const [k,v] of Object.entries(node)){
      if(/image|photo|thumb|representative/i.test(k)){
        const collectImg=x=>{
          if(typeof x==='string'&&imgOk(x)) images.push(imgNorm(x));
          else if(Array.isArray(x)) x.forEach(collectImg);
          else if(isObj(x)) Object.values(x).forEach(collectImg);
        };
        collectImg(v);
      }
      scanOptions(v,path?`${path}.${k}`:k,depth+1,seen);
    }
  };
  const parseLoose=(txt)=>{try{return JSON.parse(txt)}catch{return null}};
  const gatherRoots=(productId)=>{
    const roots=[];
    for(const e of cache){if(!productId||e.body.includes(String(productId))){const j=parseLoose(e.body);if(j) roots.push(j)}}
    for(const s of document.querySelectorAll('script[type="application/ld+json"]')){const j=parseLoose(s.textContent||'');if(j) roots.push(j)}
    for(const name of ['__NEXT_DATA__','__APOLLO_STATE__','__PRELOADED_STATE__','__INITIAL_STATE__','__NUXT__','__STATE__']){
      try{if(isObj(window[name])) roots.push(window[name])}catch(_){ }
    }
    // Parse JSON script bodies that actually mention this product id.
    for(const s of document.scripts){
      const t=s.textContent||''; if(!t||t.length>5000000||!String(productId||'')||!t.includes(String(productId))) continue;
      const trimmed=t.trim(); if(trimmed.startsWith('{')||trimmed.startsWith('[')){const j=parseLoose(trimmed);if(j) roots.push(j)}
    }
    return roots;
  };
  const productScopedRoots=(roots,productId)=>{
    const out=[]; const pid=String(productId||'');
    const seen=new WeakSet();
    const walk=(n,d=0)=>{
      if(d>14||!isObj(n)||seen.has(n)) return;seen.add(n);
      let hit=false;
      try{
        for(const [k,v] of Object.entries(n)){
          if(/product.*id|channel.*product.*no|product.*no|id$/i.test(k)&&String(v)===pid){hit=true;break}
        }
      }catch(_){ }
      if(hit) out.push(n);
      if(Array.isArray(n)){for(const v of n.slice(0,10000))walk(v,d+1)} else {for(const v of Object.values(n))walk(v,d+1)}
    };
    roots.forEach(r=>walk(r));
    return out.length?out:roots;
  };
  window.addEventListener('message',ev=>{
    const m=ev.data;if(!m||m.type!=='B2B_MAIN_PROBE_REQUEST'||!m.requestId)return;
    try{
      standardCombinationRecords.length=0;groups.length=0;extras.length=0;images.length=0;variants.length=0;groupSeen.clear();variantSeen.clear();
      const roots=gatherRoots(m.productId); const scoped=productScopedRoots(roots,m.productId);
      scoped.forEach((r,i)=>scanOptions(r,`root${i}`));
      window.postMessage({type:'B2B_MAIN_PROBE_RESPONSE',requestId:m.requestId,result:{
        images:uniq(images).slice(0,50),
        optionGroups:groups.slice(0,100),
        additionalOptionGroups:extras.slice(0,100),
        optionVariants:variants.slice(0,10000),
        standardCombinationRecords,
        debug:{networkEntries:cache.length,roots:roots.length,scopedRoots:scoped.length}
      }},'*');
    }catch(e){window.postMessage({type:'B2B_MAIN_PROBE_RESPONSE',requestId:m.requestId,error:String(e)},'*')}
  });
})();
