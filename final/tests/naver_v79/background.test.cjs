const vm=require('vm'),fs=require('fs'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/../../chrome_extension/naver_source_helper/background.js','utf8');
const event=()=>({addListener:()=>{}});let state={},closed=[],active=[],focused=[];
const ctx={console,AbortSignal,URL,setTimeout,fetch:async()=>({ok:true,json:async()=>({ok:true})}),chrome:{
 storage:{session:{get:async k=>({[k]:state[k]}),set:async x=>Object.assign(state,x),remove:async k=>delete state[k]}},
 tabs:{remove:async id=>closed.push(id),get:async()=>({windowId:7}),update:async id=>active.push(id),onUpdated:event(),onRemoved:event()},
 windows:{update:async id=>focused.push(id)},runtime:{onInstalled:event(),onStartup:event(),onMessage:event()},action:{onClicked:event()}}};
vm.createContext(ctx);vm.runInContext(source,ctx);
(async()=>{
 await ctx.closeCaptureTabAndReturn(99);assert.equal(closed.length,0);
 await ctx.rememberTempTab(11,22);
 // Maps are empty, as after a worker restart: persisted ownership is sufficient.
 await ctx.closeCaptureTabAndReturn(11);
 assert.deepEqual(closed,[11]);assert.deepEqual(active,[22]);assert.deepEqual(focused,[7]);
 ctx.fetch=async()=>({ok:true,json:async()=>({ok:false})});
 await assert.rejects(()=>ctx.sendCapture({}));console.log('ACK rejection / owned tab only / persisted return PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
