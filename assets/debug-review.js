/* Shared review state. Bridges use this API rather than another localStorage copy. */
(function(){
  'use strict';
  var key='wfdbg:'+location.pathname.split('/').pop(),notes={},revisions={},clearedAt=0,clock=0;
  var storageMessage='',listeners=[],downloader=null;
  function clone(o){return JSON.parse(JSON.stringify(o));}
  function object(o){return o&&typeof o==='object'&&!Array.isArray(o);}
  function number(n){return typeof n==='number'&&Number.isFinite(n)&&n>=0;}
  function validate(raw){
    if(!object(raw))throw new Error('註記必須是物件');
    var envelope=raw.format==='wf-review',n=envelope?raw.notes:raw,r=envelope?raw.revisions||{}:{},c=envelope?raw.clearedAt||0:0;
    if(envelope&&raw.version!==1)throw new Error('不支援的備份版本');
    if(!object(n)||!object(r)||!number(c))throw new Error('備份結構不正確');
    var clean={},rev={};
    Object.keys(n).forEach(function(k){var v=n[k];
      if(!object(v)||typeof v.src!=='string'||typeof v.path!=='string'||!v.path||
         typeof v.note!=='string'||!v.note.trim()||k!==v.src+'|'+v.path||
         (v.role!==undefined&&typeof v.role!=='string')||(v.text!==undefined&&typeof v.text!=='string'))throw new Error('無效註記：'+k);
      clean[k]={src:v.src,path:v.path,role:v.role||'',text:v.text||'',note:v.note};
    });
    Object.keys(r).forEach(function(k){var v=r[k];
      if(!object(v)||!number(v.at)||typeof v.deleted!=='boolean'||(v.deleted&&clean[k]))throw new Error('無效版本：'+k);
      rev[k]={at:v.at,deleted:v.deleted};
    });
    Object.keys(clean).forEach(function(k){if(!rev[k])rev[k]={at:0,deleted:false};});
    return {notes:clean,revisions:rev,clearedAt:c};
  }
  function snapshot(){return clone({format:'wf-review',version:1,project:key,notes:notes,revisions:revisions,clearedAt:clearedAt});}
  function observeClock(){clock=Math.max(clock,clearedAt);Object.keys(revisions).forEach(function(k){clock=Math.max(clock,revisions[k].at);});}
  function tick(){clock=Math.max(Date.now(),clock+1);return clock;}
  function cache(){try{
    localStorage.setItem(key+':snapshot',JSON.stringify(snapshot()));
    localStorage.setItem(key,JSON.stringify(notes));
    localStorage.setItem(key+':meta',JSON.stringify({revisions:revisions,clearedAt:clearedAt}));storageMessage='';
  }catch(e){storageMessage='本機儲存不可用，請匯出備份';}}
  function notify(reason){listeners.forEach(function(fn){try{fn(reason);}catch(e){console.error(e);}});
    window.dispatchEvent(new CustomEvent('wf-review-change',{detail:{reason:reason}}));}
  function commit(raw){var next=validate(raw).notes,at=tick();
    Object.keys(notes).forEach(function(k){if(!next[k])revisions[k]={at:at,deleted:true};});
    Object.keys(next).forEach(function(k){if(JSON.stringify(next[k])!==JSON.stringify(notes[k]))revisions[k]={at:at,deleted:false};});
    notes=next;cache();notify('edit');
  }
  function merge(raw){var incoming=validate(raw),changed=false;
    if(incoming.clearedAt>clearedAt){clearedAt=incoming.clearedAt;changed=true;
      Object.keys(notes).forEach(function(k){if((revisions[k]||{at:0}).at<=clearedAt)delete notes[k];});}
    Object.keys(incoming.revisions).forEach(function(k){var remote=incoming.revisions[k],local=revisions[k];
      if(remote.at<=clearedAt&&clearedAt>0)return;
      // Unknown legacy versions fill missing keys but never replace local values.
      if(local&&(remote.at<local.at||(remote.at===local.at&&(!remote.deleted||local.deleted))))return;
      revisions[k]=clone(remote);if(remote.deleted)delete notes[k];else if(incoming.notes[k])notes[k]=clone(incoming.notes[k]);
      changed=true;
    });
    observeClock();if(changed){cache();notify('merge');}return changed;
  }
  function clear(){var at=tick();Object.keys(notes).forEach(function(k){revisions[k]={at:at,deleted:true};});
    notes={};clearedAt=at;cache();notify('clear');}
  function markdown(){var by=Object.create(null),lines=['# 線框評審註記',''];
    Object.keys(notes).forEach(function(k){var n=notes[k];(by[n.src]=by[n.src]||[]).push(n);});
    Object.keys(by).sort().forEach(function(src){lines.push('## '+src+'.wf.yaml');
      by[src].sort(function(a,b){return (a.path==='(整頁)'?0:1)-(b.path==='(整頁)'?0:1);}).forEach(function(n){
        lines.push(n.path==='(整頁)'?'- (整頁) → '+n.note:'- ['+n.path+'] '+n.role+' "'+n.text+'" → '+n.note);});lines.push('');});
    if(!Object.keys(notes).length)lines.push('(無註記)');
    lines.push('<!-- wf-notes-json','```json',JSON.stringify(snapshot()),'```','-->');return lines.join('\n');
  }
  function importMarkdown(text){var match=text.match(/<!--\s*wf-notes-json\s*\n```json\s*\n([\s\S]*?)\n```\s*\n-->/);
    if(!match)throw new Error('找不到 wf-notes-json 備份區塊，請貼完整匯出內容');
    return merge(JSON.parse(match[1]));
  }
  function blobDownload(text,name){var url=URL.createObjectURL(new Blob([text],{type:'text/markdown;charset=utf-8'}));
    var a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(url);},2000);}
  async function download(){var text=markdown(),name='wf-notes-'+new Date().toISOString().slice(0,10)+'.md';
    if(downloader){try{await downloader({filename:name,data:text});return;}catch(e){/* Blob fallback */}}
    blobDownload(text,name);
  }
  try{var primary=localStorage.getItem(key+':snapshot');
    var cached=JSON.parse(localStorage.getItem(key)||'{}'),meta=JSON.parse(localStorage.getItem(key+':meta')||'{}');
    var initial=validate(primary?JSON.parse(primary):{format:'wf-review',version:1,notes:cached,revisions:meta.revisions||{},clearedAt:meta.clearedAt||0});
    notes=initial.notes;revisions=initial.revisions;clearedAt=initial.clearedAt;observeClock();
  }catch(e){storageMessage='本機快取無法讀取，請匯入備份';}
  window.wfReview={key:key,notes:function(){return clone(notes);},snapshot:snapshot,commit:commit,merge:merge,clear:clear,
    markdown:markdown,importMarkdown:importMarkdown,download:download,storageStatus:function(){return storageMessage;},
    subscribe:function(fn){listeners.push(fn);return function(){listeners=listeners.filter(function(f){return f!==fn;});};},
    setDownloader:function(fn){downloader=fn;}};
  window.addEventListener('storage',function(e){if(e.key!==key&&e.key!==key+':meta'&&e.key!==key+':snapshot')return;
    try{var primary=localStorage.getItem(key+':snapshot'),n=JSON.parse(localStorage.getItem(key)||'{}'),m=JSON.parse(localStorage.getItem(key+':meta')||'{}');
      merge(primary?JSON.parse(primary):{format:'wf-review',version:1,notes:n,revisions:m.revisions||{},clearedAt:m.clearedAt||0});}catch(err){storageMessage='跨頁快取無法讀取，請匯入備份';notify('storage-error');}});
})();
