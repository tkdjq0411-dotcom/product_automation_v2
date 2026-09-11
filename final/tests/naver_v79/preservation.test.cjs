const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/../../chrome_extension/naver_source_helper/capture.js','utf8');
const code=source.slice(source.indexOf('function optionIdentity'),source.indexOf('function naverExtraGroupsReadOnly'));
const fixture=JSON.parse(fs.readFileSync(__dirname+'/schema_fixture.json','utf8'));
const paths=fixture.optionGroups.find(g=>g.name==='standardCombinations').values.map(v=>v.slice(1,-2).split('_'));
function context(){return {expectedPaths:paths,sourceCombinationRecords:[],__b2bPartialVariants:[],naverMainOptionButtons:()=>['종류','색상','호수'].map(n=>({getAttribute:()=>n})),stopped:()=>true,diag:()=>{},collectionIncomplete:false};}
(async()=>{
 const c=context();vm.createContext(c);vm.runInContext(code,c);await c.collectDependentMainVariants();
 assert.equal(c.__b2bPartialVariants.length,179);assert.equal(c.__b2bPartialVariants.filter(v=>v.options[1].value==='블랙').length,33);
 assert(c.__b2bPartialVariants.every(v=>v.additional_price===null&&v.availability==='UNKNOWN'));
 const d=context();d.stopped=()=>false;d.sourceCombinationRecords=paths.map(p=>({encodedPath:'_'+p.join('_')+'__',additional_price:-1000,availability:'OUT_OF_STOCK'}));
 d.naverOpenRows=()=>{throw Error('must not open resolved/sold branch');};
 vm.createContext(d);vm.runInContext(code,d);await d.collectDependentMainVariants();assert(!d.collectionIncomplete);assert(d.__b2bPartialVariants.every(v=>v.additional_price===-1000&&v.availability==='OUT_OF_STOCK'));
 let click=0;const e={stopped:()=>false,variantAvailabilityFromText:v=>v.includes('품절')?'OUT_OF_STOCK':'AVAILABLE',naverSafeMainButton:()=>true,naverMainRows:()=>[],visible:()=>true};vm.createContext(e);vm.runInContext(source.slice(source.indexOf('async function naverChoose'),source.indexOf('function groupsFromVariants')),e);
 assert.equal(await e.naverChoose({getAttribute:()=> 'group',click:()=>click++},'블랙 (품절)','path'),false);assert.equal(click,0);
 console.log('179 paths / black 33 retained on stop; UNKNOWN preserved; priced sold source skips DOM; sold value emits zero clicks PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
