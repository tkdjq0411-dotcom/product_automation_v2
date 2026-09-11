(()=>{
  if(window.__B2B_OPTION_PRICE_HOOK__)return;
  window.__B2B_OPTION_PRICE_HOOK__=true;
  const bodies=[];const MAX_BODIES=80,MAX_BODY=3000000;
  const keep=raw=>{try{const s=String(raw||'');if(!s||s.length<2)return;bodies.push(s.slice(0,MAX_BODY));while(bodies.length>MAX_BODIES)bodies.shift()}catch{}};
  try{
    const original=window.fetch;
    if(typeof original==='function')window.fetch=async function(...args){
      const response=await original.apply(this,args);
      try{response.clone().text().then(keep).catch(()=>{})}catch{}
      return response;
    };
  }catch{}
  try{
    const open=XMLHttpRequest.prototype.open,send=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open=function(method,url,...rest){this.__b2bOptionPriceUrl=String(url||'');return open.call(this,method,url,...rest)};
    XMLHttpRequest.prototype.send=function(...args){
      this.addEventListener('load',()=>{try{if(typeof this.responseText==='string')keep(this.responseText)}catch{}},{once:true});
      return send.apply(this,args);
    };
  }catch{}

  const clean=v=>String(v??'').replace(/\s+/g,' ').trim();
  const isObj=v=>v&&typeof v==='object';
  const labelKeys=['optionValue','optionValueName','valueName','displayName','optionNameValue','label'];
  const deltaKeys=['addPrice','additionalPrice','optionPrice','priceDelta','extraPrice','surcharge'];
  const validLabel=v=>!!v&&v.length<=220&&!/^(?:선택|옵션|품절)$/i.test(v)&&!/^https?:\/\//i.test(v);
  function addEntry(out,label,delta,source){
    label=clean(label);delta=Number(String(delta??'').replace(/,/g,''));
    if(!validLabel(label)||!Number.isFinite(delta)||delta===0)return;
    const key=label.replace(/\([+-]\s*[\d,]+\s*원\)/g,'').replace(/[\s_]+/g,'').toLowerCase();
    if(!key)return;
    const old=out.find(x=>x.key===key);
    if(!old)out.push({key,label,delta,source});
    else if(old.delta!==delta)old.conflict=true;
  }
  function scanObject(root,out){
    const seen=new WeakSet();
    const walk=(node,depth=0)=>{
      if(depth>20||!isObj(node)||seen.has(node))return;seen.add(node);
      if(!Array.isArray(node)){
        let delta=null,deltaKey='';
        for(const k of deltaKeys){
          const n=Number(String(node?.[k]??'').replace(/,/g,''));
          if(Number.isFinite(n)&&n!==0){delta=n;deltaKey=k;break}
        }
        if(delta!=null){
          for(const k of labelKeys){if(node?.[k]!=null)addEntry(out,node[k],delta,`state:${deltaKey}`)}
          // Combination payloads use optionValue1/2/... with one combination surcharge.
          for(let i=1;i<=20;i++){
            const v=node[`optionValue${i}`]??node[`option${i}Value`]??node[`option_value${i}`];
            if(v!=null)addEntry(out,v,delta,`combination:${deltaKey}`);
          }
        }
      }
      if(Array.isArray(node)){for(const v of node.slice(0,1000))walk(v,depth+1)}
      else for(const v of Object.values(node))walk(v,depth+1);
    };
    walk(root);
  }
  const parseJson=s=>{try{return JSON.parse(s)}catch{return null}};
  function scanLoose(raw,out){
    // Fallback for JavaScript-embedded JSON. Only explicit option-value keys are accepted.
    const key='(?:optionValue|optionValueName|valueName|displayName)';
    const price='(?:addPrice|additionalPrice|optionPrice|priceDelta|extraPrice|surcharge)';
    const patterns=[
      new RegExp(`"${key}"\\s*:\\s*"((?:\\\\.|[^"\\\\]){1,220})"[\\s\\S]{0,700}?"${price}"\\s*:\\s*"?(-?[\\d,.]+)`, 'g'),
      new RegExp(`"${price}"\\s*:\\s*"?(-?[\\d,.]+)"?[\\s\\S]{0,700}?"${key}"\\s*:\\s*"((?:\\\\.|[^"\\\\]){1,220})"`, 'g')
    ];
    let m;
    while((m=patterns[0].exec(raw))){let label=m[1];try{label=JSON.parse(`"${label}"`)}catch{}addEntry(out,label,m[2],'embedded-json')}
    while((m=patterns[1].exec(raw))){let label=m[2];try{label=JSON.parse(`"${label}"`)}catch{}addEntry(out,label,m[1],'embedded-json')}
  }
  function collect(productId){
    const out=[],roots=[];
    for(const raw of bodies){
      if(productId&&!raw.includes(String(productId)))continue;
      const parsed=parseJson(raw);if(parsed)roots.push(parsed);else scanLoose(raw,out);
    }
    for(const id of ['__NEXT_DATA__','__APOLLO_STATE__','__PRELOADED_STATE__','__INITIAL_STATE__','__NUXT__','__STATE__']){try{if(isObj(window[id]))roots.push(window[id])}catch{}}
    for(const script of document.scripts){
      const raw=script.textContent||'';if(!raw||raw.length>5000000||(productId&&!raw.includes(String(productId))))continue;
      const parsed=parseJson(raw.trim());if(parsed)roots.push(parsed);else scanLoose(raw,out);
    }
    for(const root of roots)scanObject(root,out);
    return out.filter(x=>!x.conflict).slice(0,5000).map(({key,label,delta,source})=>({key,label,delta,source}));
  }
  window.addEventListener('message',event=>{
    const msg=event.data;
    if(!msg||msg.type!=='B2B_OPTION_PRICE_REQUEST'||!msg.requestId)return;
    try{window.postMessage({type:'B2B_OPTION_PRICE_RESPONSE',requestId:msg.requestId,entries:collect(msg.productId)},'*')}
    catch(error){window.postMessage({type:'B2B_OPTION_PRICE_RESPONSE',requestId:msg.requestId,entries:[],error:String(error)},'*')}
  });
})();
