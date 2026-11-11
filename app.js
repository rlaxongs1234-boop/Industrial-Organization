const $=id=>document.getElementById(id);
const fmt=x=>Number(x).toLocaleString('ko-KR',{maximumFractionDigits:3});
let worker, nextId=0, requests=new Map(), sectors=[], rowChoices=[], cells=[], basket=[], result=null, linkRows=[], loading=false;
function text(tag,value){const e=document.createElement(tag);e.textContent=value;return e;}
function call(type,payload){return new Promise((resolve,reject)=>{const id=++nextId;requests.set(id,{resolve,reject});worker.postMessage({id,type,payload});});}
function startWorker(){worker=new Worker('./worker.js');worker.onmessage=({data:d})=>{if(d.type==='status'){$('status').textContent=d.text;return;}const p=requests.get(d.id);if(!p)return;requests.delete(d.id);d.ok?p.resolve(d.result):p.reject(Error(d.error));};worker.onerror=e=>{for(const p of requests.values())p.reject(Error(e.message||'Worker 실행 오류'));requests.clear();};}
function options(el,list){el.replaceChildren(...list.map(x=>{const o=document.createElement('option');o.value=x.code;o.textContent=x.code+' '+x.name;return o;}));}
function invalidate(){result=null;$('results').hidden=true;}
const LOCKED=['sheet','row','sector','add','run','row-search','col-search','sector-search','amount','linkage-search','linkage-type','linkage-sort','linkage-download'];
async function load(buffer){
 invalidate();basket=[];renderBasket();
 for(const id of LOCKED)$(id).disabled=true;
 if(worker)worker.terminate();for(const p of requests.values())p.reject(Error('데이터 다시 로드'));requests.clear();startWorker();
 const info=await call('init',buffer);
 sectors=info.sectors;options($('sector'),sectors);
 $('sector-search').value='';$('row-search').value='';$('col-search').value='';$('linkage-search').value='';
 $('sheet').replaceChildren(...info.sheets.map(s=>{const o=text('option',s);o.value=s;return o;}));
 $('validation').textContent=JSON.stringify(info.residuals,null,2)+'\n최대 절대 잔차: 허용값 1e-8 미만';
 for(const id of LOCKED)$(id).disabled=false;
 await explore();
 const lk=await call('linkage');linkRows=lk.rows;renderLinkage();
 $('status').textContent='준비 완료 · '+info.classification+' · '+sectors.length+'개 부문 · '+info.sheets.length+'개 시트 · 계수 검증 통과';
}
let exploreSeq=0;
async function explore(){const seq=++exploreSeq;try{const d=await call('explore',{sheet:$('sheet').value,row:$('row').value});if(seq!==exploreSeq)return;rowChoices=d.rows;filterRows(d.selected);cells=d.cells;$('unit').textContent='단위: '+d.unit;$('explore-caption').textContent=$('sheet').value+' / 행: '+d.selected+' '+d.name;renderCells();}catch(e){$('status').textContent=e.message;}}
function filterRows(selected){const q=$('row-search').value.trim();options($('row'),rowChoices.filter(r=>(r.code+' '+r.name).includes(q)));if([...$('row').options].some(o=>o.value===selected))$('row').value=selected;}
function renderCells(){const q=$('col-search').value.trim();$('cells').replaceChildren(...cells.filter(c=>(c.code+' '+c.name).includes(q)).map(c=>{const tr=document.createElement('tr');for(const v of [c.code,c.name,c.value===null?'빈 셀':typeof c.value==='number'?fmt(c.value):c.value])tr.append(text('td',v));return tr;}));}
$('sheet').onchange=()=>{$('row-search').value='';$('row').replaceChildren();explore();};$('row').onchange=explore;
$('row-search').oninput=()=>{filterRows();if($('row').value)explore();else{$('cells').replaceChildren();$('explore-caption').textContent='일치하는 행이 없습니다.';}};
$('col-search').oninput=renderCells;
$('sector-search').oninput=()=>{const q=$('sector-search').value.trim();options($('sector'),sectors.filter(s=>(s.code+' '+s.name).includes(q)));};
function renderBasket(){$('basket').replaceChildren(...basket.map((s,i)=>{const li=text('li',s.code+' '+s.name+' / '+fmt(s.amount)+'백만원 ');const b=text('button','삭제');b.type='button';b.onclick=()=>{basket.splice(i,1);invalidate();renderBasket();};li.append(b);return li;}));$('sim-status').textContent=basket.length?basket.length+'개 입력 준비. 계산 버튼을 누르세요.':'시나리오를 추가하세요.';}
$('scenario').onsubmit=e=>{e.preventDefault();const amount=Number($('amount').value),s=sectors.find(s=>s.code===$('sector').value);if(!s||!Number.isFinite(amount)||amount<=0){$('sim-status').textContent='산업과 양의 증가액을 확인하세요.';return;}basket.push({...s,amount});invalidate();renderBasket();};
$('clear').onclick=()=>{basket=[];invalidate();renderBasket();};
$('run').onclick=async()=>{if(!basket.length){$('sim-status').textContent='시나리오를 먼저 추가하세요.';return;}const snapshot=basket.map(s=>({...s}));$('run').disabled=true;$('sim-status').textContent='계산 중…';try{const r=await call('simulate',snapshot);if(JSON.stringify(snapshot)!==JSON.stringify(basket)){$('sim-status').textContent='입력이 변경되었습니다. 다시 계산하세요.';return;}result=r;renderResult();$('sim-status').textContent='계산 완료. 아래 결과는 현재 시나리오에 대응합니다.';}catch(e){invalidate();$('sim-status').textContent='계산 실패: '+e.message;}finally{$('run').disabled=false;}};
function renderResult(){$('results').hidden=false;
 const items=[['수요 증가액',result.demand,'백만원'],['생산유발액',result.production,'백만원'],['수입유발액',result.imports,'백만원'],['부가가치유발액',result.valueAdded,'백만원'],['생산유발승수',result.multiplier,'배 (생산유발액÷수요증가액)'],['부가가치유발률',result.valueAdded/result.demand*100,'% (부가가치유발액÷수요증가액)']];
 $('cards').replaceChildren(...items.map(([title,v,u])=>{const d=text('div',title);d.className='card';d.append(text('strong',fmt(v)),text('span',u));return d;}));
 const max=Math.max(...result.rows.map(r=>r.production),1);
 $('bars').replaceChildren(...result.rows.slice(0,15).map(r=>{const d=text('div',r.name+' · '+fmt(r.production)+'백만원');d.className='bar';const t=document.createElement('div');t.className='track';const f=document.createElement('div');f.className='fill';f.style.width=Math.max(0,r.production/max*100)+'%';t.append(f);d.append(t);return d;}));
 $('result-rows').replaceChildren(...result.rows.map(r=>{const tr=document.createElement('tr');[r.code,r.name,fmt(r.production),fmt(r.imports),fmt(r.valueAdded)].forEach(v=>tr.append(text('td',v)));return tr;}));}
function csvCell(v){let s=String(v);if(/^[=+@-]/.test(s)&&typeof v!=='number')s="'"+s;return '"'+s.replaceAll('"','""')+'"';}
function saveCsv(rows,name){const url=URL.createObjectURL(new Blob(['\ufeff'+rows.map(r=>r.map(csvCell).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('download').onclick=()=>{if(!result)return;saveCsv([['산업코드','산업명','생산유발액_백만원','수입유발액_백만원','부가가치유발액_백만원'],...result.rows.map(r=>[r.code,r.name,r.production,r.imports,r.valueAdded])],'io-results.csv');};

// ---- 연쇄효과 ----
const TYPE_LABEL={key:'핵심산업',back:'후방연쇄 선도',fwd:'전방연쇄 선도',low:'낮은 연쇄'};
function filteredLinkage(){const q=$('linkage-search').value.trim(),t=$('linkage-type').value,s=$('linkage-sort').value;
 const list=linkRows.filter(r=>(t==='all'||r.type===t)&&(r.code+' '+r.name).includes(q));
 if(s==='code')list.sort((a,b)=>a.code.localeCompare(b.code,'ko',{numeric:true}));else list.sort((a,b)=>b[s]-a[s]);return list;}
function renderLinkage(){const list=filteredLinkage();
 $('linkage-caption').textContent='연쇄효과 계수 — '+list.length+'/'+linkRows.length+'개 산업 (무차원 비율)';
 $('linkage-rows').replaceChildren(...list.map(r=>{const tr=document.createElement('tr');[r.code,r.name,r.backward.toFixed(3),r.forward.toFixed(3),TYPE_LABEL[r.type]].forEach((v,i)=>{const td=text('td',v);if(r.type==='key'&&i===4)td.className='tag-key';tr.append(td);});return tr;}));}
for(const id of ['linkage-search','linkage-type','linkage-sort'])$(id).oninput=renderLinkage;
$('linkage-download').onclick=()=>{saveCsv([['산업코드','산업명','영향력계수','감응도계수','유형'],...filteredLinkage().map(r=>[r.code,r.name,r.backward,r.forward,TYPE_LABEL[r.type]])],'io-linkage.csv');};

// ---- 분류 카드 → 엑셀 파일 로드 ----
const FILES={
 '기본부문':'io-2023.xlsx',
 '대분류':'(표)(2023연장)투입산출표_생산자가격_통합대분류.xlsx',
 '중분류':'(표)(2023연장)투입산출표_생산자가격_통합중분류.xlsx',
 '소분류':'(표)(2023연장)투입산출표_생산자가격_통합소분류.xlsx'};
const cards=[...document.querySelectorAll('.io-select-card')];
async function loadClass(label,card){
 if(loading)return;loading=true;cards.forEach(c=>c.disabled=true);
 try{
  $('status').textContent=label+' 엑셀 파일 불러오는 중…';
  const res=await fetch('./data/'+encodeURIComponent(FILES[label]));
  if(!res.ok)throw Error(label+' 파일을 불러오지 못했습니다. HTTP '+res.status);
  await load(await res.arrayBuffer());
  cards.forEach(c=>c.classList.toggle('selected',c===card));
 }catch(e){$('status').textContent='불러오기 실패: '+e.message+' — 다른 카드를 누르거나 새로고침하세요.';}
 finally{loading=false;cards.forEach(c=>c.disabled=false);}
}
cards.forEach(card=>card.onclick=()=>loadClass(card.dataset.label,card));
