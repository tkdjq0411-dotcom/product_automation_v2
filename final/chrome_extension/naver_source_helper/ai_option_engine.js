(()=>{
  'use strict';
  const clean=v=>String(v??'').replace(/\s+/g,' ').trim();
  const stripPrice=v=>clean(v).replace(/\(([+-])\s*[\d,]+\s*원\)/g,'').replace(/\(품절\)/g,'').trim();
  const key=v=>stripPrice(v).replace(/[\s_]+/g,'').toLowerCase();
  const groups=v=>Array.isArray(v)?v.filter(g=>g&&Array.isArray(g.values)&&g.values.length):[];
  const variants=v=>Array.isArray(v)?v.filter(x=>x&&Array.isArray(x.options)&&x.options.length):[];
  const depth=v=>Math.max(0,...variants(v).map(x=>x.options.length));
  const valueCount=v=>groups(v).reduce((n,g)=>n+g.values.length,0);
  const pricedText=v=>/[+-]\s*[\d,]+\s*원/.test(clean(v));
  const groupSignature=g=>(g?.values||[]).map(key).filter(Boolean).sort().join('|');
  const variantSignature=v=>(v?.options||[]).map(o=>`${key(o.name)}=${key(o.value)}`).join('|');
  const duplicateCount=(rows,signature)=>{
    const seen=new Set();let duplicates=0;
    for(const row of rows){const k=signature(row);if(!k)continue;if(seen.has(k))duplicates++;else seen.add(k)}
    return duplicates;
  };
  function observe(raw={}){
    const domMain=groups(raw.optionGroups),domExtra=groups(raw.additionalOptionGroups);
    const networkMain=groups(raw.rawNetworkOptionGroups),networkExtra=groups(raw.rawNetworkAdditionalOptionGroups);
    const domVariants=variants(raw.optionVariants),networkVariants=variants(raw.rawNetworkOptionVariants);
    const diagnostics=raw.optionDiagnostics&&typeof raw.optionDiagnostics==='object'?raw.optionDiagnostics:{};
    const events=Array.isArray(diagnostics.events)?diagnostics.events:[];
    const clicked=events.filter(e=>e?.event==='main_value_clicked'||e?.event==='dependent_value_clicked').length;
    const captured=events.filter(e=>e?.event==='dependent_variant_captured').length;
    const observedPrices=[
      ...domMain.flatMap(g=>g.values),...domExtra.flatMap(g=>g.values),
      ...domVariants.flatMap(v=>v.options.map(o=>o.value))
    ].filter(pricedText).length;
    return {
      dom:{main_groups:domMain.length,main_values:valueCount(domMain),extra_groups:domExtra.length,extra_values:valueCount(domExtra),variant_count:domVariants.length,depth:depth(domVariants)},
      network:{main_groups:networkMain.length,main_values:valueCount(networkMain),extra_groups:networkExtra.length,extra_values:valueCount(networkExtra),variant_count:networkVariants.length,depth:depth(networkVariants)},
      interaction:{clicked,captured,priced_values:observedPrices},
      duplicates:{main:duplicateCount(domMain,groupSignature),extra:duplicateCount(domExtra,groupSignature),variants:duplicateCount(domVariants,variantSignature)}
    };
  }
  function classify(observation){
    const o=observation,main=Math.max(o.dom.main_groups,o.network.main_groups),extra=Math.max(o.dom.extra_groups,o.network.extra_groups);
    const variantDepth=Math.max(o.dom.depth,o.network.depth);
    const deepest=variantDepth||(main?1:0);
    let type='NO_OPTION';
    if(main===1&&deepest<=1)type='SINGLE';
    else if(main>1&&deepest<=1)type='MULTI_UNRESOLVED';
    else if(deepest>=2)type=`DEPENDENT_${Math.min(5,deepest)}`;
    if(extra&&main)type=`MIXED_${type}`;else if(extra&&!main)type='ADDITIONAL_ONLY';
    const evidence=(o.dom.main_groups>0?1:0)+(o.network.main_groups>0?1:0)+(o.interaction.clicked>0?1:0)+(o.dom.extra_groups===o.network.extra_groups?1:0);
    return {type,confidence:Math.min(99,60+evidence*9),deepest_level:deepest,has_additional:extra>0};
  }
  function firstPass(raw={}){
    const observation=observe(raw),classification=classify(observation);
    const networkHasMain=observation.network.main_groups>0&&observation.network.main_values>0;
    const networkHasVariants=observation.network.variant_count>0;
    const networkComplete=classification.type==='NO_OPTION'||classification.type==='ADDITIONAL_ONLY'||(networkHasMain&&(observation.network.main_groups===1||networkHasVariants));
    const strategy=networkComplete?'DIRECT_INTERNAL_DATA':(networkHasMain?'TARGETED_CLICK_FALLBACK':'DOM_DISCOVERY_FALLBACK');
    const plan=['CAPTURE_CORE','READ_ALL_INTERNAL_PRODUCT_DATA'];
    if(strategy!=='DIRECT_INTERNAL_DATA')plan.push('CLICK_ONLY_MISSING_REQUIRED_COMBINATIONS');
    if(classification.has_additional||classification.type==='ADDITIONAL_ONLY')plan.push('READ_ALL_ADDITIONAL_GROUPS');
    plan.push('DEDUPLICATE','SECOND_PASS_AUDIT');
    return {engine:'HYBRID_AI_V2',pass:1,strategy,classification,observation,plan};
  }
  function secondPass(normalized={},raw={},first=null){
    const observation=observe({...raw,optionGroups:normalized.optionGroups,additionalOptionGroups:normalized.additionalOptionGroups,optionVariants:normalized.optionVariants});
    const main=groups(normalized.optionGroups),extra=groups(normalized.additionalOptionGroups),vars=variants(normalized.optionVariants);
    const expectedDepth=Math.max(first?.classification?.deepest_level||0,observation.network.depth);
    const actualDepth=depth(vars);
    const expectedExtra=Math.max(observation.dom.extra_groups,observation.network.extra_groups);
    const expectedVariants=Math.max(observation.dom.variant_count,observation.network.variant_count);
    const issues=[];
    if(expectedDepth>=2&&actualDepth<expectedDepth)issues.push({code:'DEPENDENCY_DEPTH_MISSING',expected:expectedDepth,actual:actualDepth});
    if(expectedExtra>extra.length)issues.push({code:'ADDITIONAL_GROUP_MISSING',expected:expectedExtra,actual:extra.length});
    if(expectedVariants>vars.length)issues.push({code:'VARIANT_COUNT_MISMATCH',expected:expectedVariants,actual:vars.length});
    if(observation.duplicates.main||observation.duplicates.extra||observation.duplicates.variants)issues.push({code:'DUPLICATE_REMAINS',...observation.duplicates});
    if(first?.strategy!=='DIRECT_INTERNAL_DATA'&&(main.length||vars.length)&&observation.interaction.clicked===0)issues.push({code:'NO_REAL_OPTION_CLICK'});
    const priceSignals=observation.interaction.priced_values+vars.filter(v=>Number(v.additional_price)!==0).length;
    if(expectedDepth>=2&&priceSignals===0)issues.push({code:'NO_OPTION_PRICE_SIGNAL'});
    const coreOk=Boolean(normalized.productName)&&Number.isFinite(Number(normalized.price))&&Array.isArray(normalized.imageUrls)&&normalized.imageUrls.length>0;
    if(!coreOk)issues.push({code:'CORE_FIELD_MISSING'});
    const status=issues.some(x=>['DEPENDENCY_DEPTH_MISSING','ADDITIONAL_GROUP_MISSING','NO_REAL_OPTION_CLICK','CORE_FIELD_MISSING'].includes(x.code))?'REVIEW_REQUIRED':(issues.length?'PARTIAL_REVIEW':'AUTO_SAVE_READY');
    const agreement=Math.max(0,100-issues.length*18);
    return {engine:'HYBRID_AI_V2',pass:2,status,agreement,issues,observation,checked_at:Date.now()};
  }
  window.B2BAIOptionEngine=Object.freeze({observe,classify,firstPass,secondPass});
})();
