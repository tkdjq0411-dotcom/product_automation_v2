const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/../../chrome_extension/naver_source_helper/capture.js','utf8');
const extract=(a,b)=>source.slice(source.indexOf(a),source.indexOf(b,source.indexOf(a)));
async function run(depth,{expiry=false,error=false}={}){
 let now=0,clicks=[],current=[],results=[];
 const ctx={sourceCombinationRecords:[],expectedPaths:[],console,Set,Map,JSON,Date:{now:()=>now},schemaDepth:depth,knownOptionDepth:depth,collectionIncomplete:false,
 __b2bPartialVariants:results,stopped:()=>expiry&&now>=180000,diag:()=>{},
 variantAvailabilityFromText:v=>v.includes('품절')?'OUT_OF_STOCK':'AVAILABLE'};
 const buttons=()=>Array.from({length:depth},(_,i)=>({getAttribute:()=>`group${i}`,level:i}));
 ctx.naverMainOptionButtons=buttons;
 ctx.naverOpenRows=async(b,save)=>{
  const vals=b.level===depth-1?['8호 (+3,500원)','9호 (-1,000원) (품절)']:['실버','단색'];
  for(const v of vals){if(ctx.stopped())break;save(v,v);now+=expiry?10000:1;}
  return vals;
 };
 ctx.naverChoose=async(b,v,k)=>{assert(!clicks.includes(k));clicks.push(k);current[b.level]=v;if(error&&clicks.length===2)throw Error('DOM');return true;};
 vm.createContext(ctx);vm.runInContext(extract('function optionIdentity','function naverExtraGroupsReadOnly'),ctx);
 await ctx.collectDependentMainVariants();
 assert(results.length>0);assert(results.every(v=>v.options.length===depth));
 assert(results.some(v=>v.additional_price===3500));
 if(!expiry)assert(results.some(v=>v.additional_price===-1000&&v.availability==='OUT_OF_STOCK'));
 if(!expiry&&!error)assert.equal(results.length,2**depth);
 if(error)assert(ctx.collectionIncomplete);
 return {depth,rows:results.length,clicks:clicks.length};
}
(async()=>{
 for(const depth of [1,2,3,4,7])console.log('DFS',await run(depth));
 console.log('expiry preserves checkpoint',await run(4,{expiry:true}));
 console.log('branch error preserves rows',await run(4,{error:true}));
 // 30 levels with one value each, no combinatorial fixture explosion.
 const ctx={sourceCombinationRecords:[],expectedPaths:[],schemaDepth:30,knownOptionDepth:30,collectionIncomplete:false,__b2bPartialVariants:[],stopped:()=>false,diag:()=>{},variantAvailabilityFromText:()=> 'AVAILABLE',
 naverMainOptionButtons:()=>Array.from({length:30},(_,i)=>({getAttribute:()=>`g${i}`})),
 naverOpenRows:async(b,cb)=>{cb('same','id');return ['same'];},naverChoose:async()=>true};
 vm.createContext(ctx);vm.runInContext(extract('function optionIdentity','function naverExtraGroupsReadOnly'),ctx);
 await ctx.collectDependentMainVariants();assert.equal(ctx.__b2bPartialVariants[0].options.length,30);console.log('30 levels PASS');
 // Exercise actual click function: stale aria-selected and throwing click cannot cause retries.
 let count=0;
 const row={getAttribute:k=>k==='data-shp-contents-id'?'id':null,click:()=>{count++;throw Error('after click');}};
 const button={getAttribute:k=>k==='aria-expanded'?'true':'group'};
 const c={variantAvailabilityFromText:()=> 'AVAILABLE',diag:()=>{},stopped:()=>false,naverSafeMainButton:()=>true,naverMainRows:()=>[row],visible:()=>true,naverRowValue:()=> 'same',__b2bLogicalSelectionLocks:new Set()};
 vm.createContext(c);vm.runInContext(extract('async function naverChoose','function groupsFromVariants'),c);
 try{await c.naverChoose(button,'same','parent1');}catch{}
 assert.equal(await c.naverChoose(button,'same','parent1'),false);assert.equal(count,1);
 try{await c.naverChoose(button,'same','parent2');}catch{}
 assert.equal(count,2);console.log('physical click prelock / different parent PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
// Actual deadline boundary, with the production stop flag function.
{
 let now=179999;
 const c={Date:{now:()=>now},optionWorkDeadline:180000,stopRequested:false,collectionIncomplete:false};
 vm.createContext(c);vm.runInContext(extract('function stopped()','function extendOptionWork'),c);
 assert.equal(c.stopped(),false);now=180000;assert.equal(c.stopped(),true);assert.equal(c.collectionIncomplete,true);
 console.log('deadline 179999/180000 boundary PASS');
}
