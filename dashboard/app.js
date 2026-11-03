const $ = id => document.getElementById(id);
let busy = false;
const text = (tag, value, cls) => { const e = document.createElement(tag); e.textContent = value; if (cls) e.className = cls; return e; };
async function get(path) { const r = await fetch(path, {cache:'no-store',signal:AbortSignal.timeout(4000)}); const data = await r.json(); if (!r.ok) throw new Error(data.error || 'Evidence API unavailable'); return data; }
function link(id, label) { const b = text('button', label, 'link'); b.addEventListener('click', async () => {
  try { const r = await get('/api/receipts/'+encodeURIComponent(id)); const bytes = Uint8Array.from(atob(r.original_body_base64), c=>c.charCodeAt(0));
    $('receipt').textContent = JSON.stringify({...r, original_body_utf8_preview: new TextDecoder('utf-8',{fatal:false}).decode(bytes)},null,2);
  } catch(e) { $('receipt').textContent = e.message; }
}); return b; }
async function refresh() {
 if (busy) return; busy = true;
 try {
  const runs = await get('/api/runs?limit=30'), old = $('run').value;
  $('run').replaceChildren();
  if (!runs.items.length) $('run').append(new Option('Waiting for captured events',''));
  for (const r of runs.items) $('run').append(new Option(r.run_id,r.run_id));
  if (runs.items.some(r=>r.run_id===old)) $('run').value = old;
  const query = $('run').value ? 'run_id='+encodeURIComponent($('run').value)+'&' : '';
  const [health,sources,events,findings,errors] = await Promise.all([get('/api/health'),get('/api/sources?'+query+'limit=50'),get('/api/events?'+query+'limit=30'),get('/api/findings?'+query+'limit=1'),get('/api/errors?limit=10')]);
  $('connection').textContent = `${health.counts.normalized_events} saved events · ${health.counts.validation_errors} issues · updated ${new Date().toLocaleTimeString()}`;
  $('sources').replaceChildren();
  for (const s of sources.items) {
   const card=text('article','', 'card'), event=s.sample, p=event?.payload;
   card.append(text('h2',s.source_id),text('span',s.state.toUpperCase(),'badge '+s.state));
   const value = !event ? 'No sample' : s.source_id==='plant-model' ? `${p.actual_delivery_mg_s.toFixed(2)} mg/s` : `${p.value.toFixed(3)} mg/L`;
   card.append(text('div',value,'value'),text('p',s.age_seconds===null?'No saved evidence':`Original sample age: ${s.age_seconds.toFixed(1)} seconds`,'muted'));
   if(event) {card.append(text('p',`Step ${event.sim_step} · ${p.quality || 'plant feedback'}`,'muted'),link(s.receipt_id,'Inspect original receipt'));}
   $('sources').append(card);
  }
  const concerns=sources.items.filter(s=>s.state!=='fresh');
  $('alerts').textContent=concerns.length ? 'Monitoring attention: '+concerns.map(s=>s.source_id+' is '+s.state).join('; ')+'. Retained values are not fresh measurements.' : 'All three sources have recent saved observations. This is source freshness, not an approval or safety verdict.';
  $('finding').replaceChildren();
  const finding=findings.items[0];
  if(!finding) $('finding').append(text('p','No saved finding yet. Waiting for a complete same-step observation set.'));
  else { $('finding').append(text('span',finding.status,'badge '+finding.status),text('p',finding.reason,'finding-reason'),text('p',`Historical step ${finding.sim_step} · ${finding.rule_id} · confidence: ${finding.confidence} · urgency: ${finding.urgency}`,'muted'));
    const links=text('div','','evidence-links'); for(const r of finding.supporting_records) links.append(link(r.receipt_id,r.source_id+' evidence')); $('finding').append(links);
  }
  $('events').replaceChildren();
  for(const row of events.items) {const e=row.event,tr=document.createElement('tr'),source=document.createElement('td');source.append(text('strong',e.source_id),text('small',e.event_type));tr.append(source);
    for(const value of [e.sim_step,e.source_timestamp_utc,row.received_at_utc])tr.append(text('td',value));const proof=document.createElement('td');proof.append(link(row.receipt_id,'Original'));tr.append(proof);$('events').append(tr);}
  $('errors').replaceChildren(); if(!errors.items.length)$('errors').append(text('p','No recorded validation or identity issues.','muted'));
  for(const error of errors.items) {const div=text('div',error.code+': '+error.message+' ','issue');div.append(link(error.receipt_id,'Retained original'));$('errors').append(div);}
 } catch(e) { $('connection').textContent='Evidence unavailable';$('alerts').textContent='Evidence API unavailable. Existing values may be old; displayed ages are no longer updating. '+e.message;
   for(const badge of $('sources').querySelectorAll('.badge')) { badge.textContent='CONNECTION UNAVAILABLE';badge.className='badge unavailable'; }
 }
 finally {busy=false;}
}
$('run').addEventListener('change',refresh); refresh(); setInterval(refresh,2000);
