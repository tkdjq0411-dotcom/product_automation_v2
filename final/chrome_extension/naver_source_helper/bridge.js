(()=>{
  const allowed=location.hostname==='127.0.0.1'||location.hostname==='localhost';
  if(!allowed||location.port!=='8000')return;
  try{chrome.runtime.sendMessage({type:'B2B_HELPER_HEARTBEAT'},()=>{});}catch(_){ }
  window.addEventListener('message',(ev)=>{
    if(ev.source!==window)return;
    const msg=ev.data||{};
    if(msg.type!=='B2B_START_NAVER_CAPTURE')return;
    const url=String(msg.url||'');
    if(!/^https:\/\/(?:smartstore|brand)\.naver\.com\/[^/]+\/products\/\d+/i.test(url))return;
    chrome.runtime.sendMessage({type:'B2B_START_NAVER_CAPTURE',url},(res)=>{
      window.postMessage({type:'B2B_NAVER_CAPTURE_ACK',ok:!!res?.ok,error:res?.error||'',url},location.origin);
    });
  });
  window.postMessage({type:'B2B_HELPER_BRIDGE_READY'},location.origin);
})();
