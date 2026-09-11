const VERSION='2.61.14';
const BASES=['http://127.0.0.1:8000','http://localhost:8000'];
const armedTabs=new Set();
const firedTabs=new Map();
const returnTabs=new Map();
const SESSION_KEY='b2b_temp_capture_tabs_v261';
const tabKey=id=>`${SESSION_KEY}:${id}`;
async function rememberTempTab(captureTabId,returnTabId){
  await chrome.storage.session.set({[tabKey(captureTabId)]:{returnTabId:returnTabId||null,createdAt:Date.now()}});
}
async function forgetTempTab(captureTabId){await chrome.storage.session.remove(tabKey(captureTabId));}
async function getTempTabInfo(captureTabId){return (await chrome.storage.session.get(tabKey(captureTabId)))[tabKey(captureTabId)]||null;}
async function closeCaptureTabAndReturn(captureTabId){
  if(!captureTabId)return;
  const persisted=await getTempTabInfo(captureTabId);
  if(!persisted)return;
  const returnTabId=returnTabs.get(captureTabId)||persisted?.returnTabId||null;
  armedTabs.delete(captureTabId);firedTabs.delete(captureTabId);returnTabs.delete(captureTabId);
  await forgetTempTab(captureTabId);
  await heartbeat('capture_saved_closing_temp_tab');
  // Save ACK is already complete. Close the exact temporary product tab even if the MV3 worker restarted.
  try{await chrome.tabs.remove(captureTabId)}catch(_){}
  if(returnTabId){
    try{
      const rt=await chrome.tabs.get(returnTabId);
      if(rt?.windowId)await chrome.windows.update(rt.windowId,{focused:true});
      await chrome.tabs.update(returnTabId,{active:true});
    }catch(_){}
  }
  await heartbeat('capture_temp_tab_closed_returned_b2b');
}
async function postLocal(path,payload){
  let last='';
  for(const base of BASES){
    try{
      const r=await fetch(base+path,{signal:AbortSignal.timeout(10000),method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload||{})});
      if(r.ok)return await r.json();
      last=`HTTP ${r.status}`;
    }catch(e){last=String(e)}
  }
  throw new Error(last||'B2B 서버 연결 실패');
}
async function heartbeat(event='heartbeat',error=''){
  try{await postLocal('/sourcing/browser-helper-heartbeat',{version:VERSION,event,error})}catch(_){}
}
async function sendCapture(payload){
  await heartbeat('capture_send');
  try{
    const result=await postLocal('/sourcing/browser-capture',payload);
    if(result?.ok!==true)throw new Error('B2B server did not acknowledge save');
    await heartbeat('capture_success');
    return result;
  }catch(e){
    await heartbeat('capture_error',String(e));
    throw e;
  }
}
function isNaverProduct(raw){
  try{
    const u=new URL(String(raw||''));
    return /^(?:smartstore|brand)\.naver\.com$/i.test(u.hostname) && /^\/[^/]+\/products\/\d+/i.test(u.pathname);
  }catch{return false}
}
function isLocalB2B(raw){
  try{
    const u=new URL(String(raw||''));
    return (u.hostname==='127.0.0.1'||u.hostname==='localhost') && u.port==='8000';
  }catch{return false}
}
chrome.runtime.onInstalled.addListener(()=>heartbeat('installed'));
chrome.runtime.onStartup.addListener(()=>heartbeat('startup'));
chrome.runtime.onMessage.addListener((msg,sender,reply)=>{
  if(msg?.type==='B2B_NAVER_CAPTURE'){
    const captureTabId=sender?.tab?.id||null;
    sendCapture(msg.payload).then(async x=>{
      // The B2B server has fully saved the capture at this point.
      // Reply to the capture script first, then dispose of ONLY the temporary Naver tab.
      reply({ok:true,result:x});
      if(captureTabId){
        const persisted=await getTempTabInfo(captureTabId);
        // Close only tabs explicitly created for B2B capture. Persistent session state survives service-worker sleep.
        if(armedTabs.has(captureTabId)||persisted) await closeCaptureTabAndReturn(captureTabId);
      }
    }).catch(e=>reply({ok:false,error:String(e)}));
  }
  if(msg?.type==='B2B_HELPER_HEARTBEAT') heartbeat('content_ready').then(()=>reply({ok:true}));
  if(msg?.type==='B2B_START_NAVER_CAPTURE'){
    const url=String(msg.url||'');
    if(!isNaverProduct(url)){reply({ok:false,error:'invalid naver product url'});return true;}
    (async()=>{
      try{
        await heartbeat('b2b_capture_request');
        const sourceTabId=sender?.tab?.id||null;
        const tab=await chrome.tabs.create({url,active:true,...(sourceTabId?{openerTabId:sourceTabId}:{})});
        if(tab?.id){
          armedTabs.add(tab.id);
          if(sourceTabId)returnTabs.set(tab.id,sourceTabId);
          await rememberTempTab(tab.id,sourceTabId);
          const ready=await chrome.tabs.get(tab.id);
          if(ready.status==='complete')trigger(tab.id,ready.url);
          await heartbeat('b2b_background_capture_tab_opened');
        }
        reply({ok:true,tabId:tab?.id||null});
      }catch(e){await heartbeat('b2b_capture_open_error',String(e));reply({ok:false,error:String(e)})}
    })();
  }
  return true;
});

// Tabs are armed only by an explicit request relayed from the local B2B page.
async function trigger(tabId,tabUrl){
  if(!tabId || !isNaverProduct(tabUrl))return;
  const info=await getTempTabInfo(tabId);
  if(!info||info.started)return;
  await chrome.storage.session.set({[tabKey(tabId)]:{...info,started:true}});
  const key=String(tabUrl||'');
  if(firedTabs.get(tabId)===key)return;
  firedTabs.set(tabId,key);
  await heartbeat('explicit_import_trigger');
  try{
    // Capture-only MAIN-world guard: Naver can raise a blocking native alert when its
    // own state briefly considers a dependent combination already selected. Never let
    // that one known alert freeze the automated import. All other alerts are preserved.
    try{
      await chrome.scripting.executeScript({target:{tabId},world:'MAIN',func:()=>{
        if(window.__B2B_DUP_ALERT_GUARD__)return;
        window.__B2B_DUP_ALERT_GUARD__=true;
        const original=window.alert.bind(window);
        window.__B2B_ORIGINAL_ALERT__=original;
        window.alert=function(message){
          const text=String(message??'');
          if(/이미\s*선택한\s*옵션입니다/.test(text)){console.info('[B2B Helper] duplicate-option alert suppressed during capture');return;}
          return original(message);
        };
        setTimeout(()=>{
          try{if(window.__B2B_ORIGINAL_ALERT__)window.alert=window.__B2B_ORIGINAL_ALERT__;}catch(_){}
          try{delete window.__B2B_ORIGINAL_ALERT__;delete window.__B2B_DUP_ALERT_GUARD__;}catch(_){}
        },185000);
      }});
    }catch(_){ }
    await chrome.tabs.sendMessage(tabId,{type:'B2B_CAPTURE_NOW'});
  }catch(e){
    try{
      await chrome.scripting.executeScript({target:{tabId},files:['capture.js']});
      setTimeout(()=>chrome.tabs.sendMessage(tabId,{type:'B2B_CAPTURE_NOW'}).catch(()=>{}),1200);
    }catch(err){await heartbeat('inject_error',String(err))}
  }
}
chrome.tabs.onUpdated.addListener((tabId,changeInfo,tab)=>{
  if(changeInfo.status!=='complete')return;
  if(isNaverProduct(tab.url))setTimeout(()=>trigger(tabId,tab.url),2200);
});
chrome.tabs.onRemoved.addListener(tabId=>{armedTabs.delete(tabId);firedTabs.delete(tabId);returnTabs.delete(tabId);forgetTempTab(tabId).catch(()=>{})});
chrome.action.onClicked.addListener(()=>heartbeat('icon_clicked_idle'));
heartbeat('worker_loaded');
