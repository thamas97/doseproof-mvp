const $ = id => document.getElementById(id);
let busy = false;
let changeSnapshot = '';
const text = (tag, value, cls) => { const e = document.createElement(tag); e.textContent = value; if (cls) e.className = cls; return e; };
async function get(path) { const r = await fetch(path, {cache:'no-store',signal:AbortSignal.timeout(4000)}); const data = await r.json(); if (!r.ok) throw new Error(data.error || 'Evidence API unavailable'); return data; }
function link(id, label) { const b = text('button', label, 'link'); b.addEventListener('click', async () => {
  try { const r = await get('/api/receipts/'+encodeURIComponent(id)); const bytes = Uint8Array.from(atob(r.original_body_base64), c=>c.charCodeAt(0));
    $('receipt').textContent = JSON.stringify({...r, original_body_utf8_preview: new TextDecoder('utf-8',{fatal:false}).decode(bytes)},null,2);
  } catch(e) { $('receipt').textContent = e.message; }
}); return b; }
const actionLabel = {
  dose_request:'Request', dose_approval:'Approval', command:'Command',
  acknowledgement:'Controller acknowledgement', lab_action:'Labelled lab action',
};
function actionSummary(event) {
  const p = event.payload;
  switch (event.event_type) {
    case 'dose_request': return `${p.actor_id} requested ${p.requested_feed_mg_s} mg/s · ${p.request_id}`;
    case 'dose_approval': return `${p.approver_id} approved ${p.approved_feed_mg_s} mg/s · ${p.approval_id}`;
    case 'command': return `${p.actor_id} sent ${p.requested_feed_mg_s} mg/s · ${p.command_id}`;
    case 'acknowledgement': return `${p.accepted ? 'Accepted' : 'Rejected'} · ${p.accepted_feed_mg_s} mg/s · ${p.command_id}`;
    default: return `${p.actor_id} · ${p.action} · ${p.reason}`;
  }
}
function showChanges(data) {
  const snapshot = JSON.stringify(data);
  if (snapshot === changeSnapshot) return;
  changeSnapshot = snapshot;
  const expanded = new Map([...$('changes').querySelectorAll('details')].map(d => [d.dataset.id, d.open]));
  $('changes').replaceChildren();
  const alerts = data.items.filter(f => f.status === 'FAIL' || f.status === 'UNVERIFIED');
  $('action-alerts').textContent = alerts.length ? `Recorded findings needing attention: ${alerts.map(f => f.status + ' — ' + f.reason).join(' ')}` : '';
  if (!data.items.length) $('changes').append(text('p','No change or fault findings for this run.','muted'));
  for (const [index, finding] of data.items.entries()) {
    const section = document.createElement('details');
    section.dataset.id = finding.change_id;
    section.open = expanded.get(finding.change_id) ?? index === 0;
    const summary = text('summary', ` ${finding.rule_id === 'approval-response-v1' ? 'Approval and controller response' : 'Simulation fault'} · ${finding.change_id}`);
    summary.prepend(text('span', finding.status, 'badge ' + finding.status));
    section.append(summary, text('p', finding.reason, 'finding-reason'), text('p', finding.scope, 'muted'),
      text('p', `Confidence ${finding.confidence} · urgency ${finding.urgency}`, 'muted'));
    const actions = document.createElement('ol');
    for (const row of finding.actions) {
      const item = text('li', `${actionLabel[row.event.event_type]} · ${actionSummary(row.event)} · step ${row.event.sim_step} `);
      item.append(link(row.receipt_id, 'Original action'));
      actions.append(item);
    }
    section.append(actions);
    for (const record of finding.supporting_records.filter(r => r.meaning)) {
      section.append(link(record.receipt_id, record.meaning));
    }
    if (finding.observations.length) {
      section.append(text('p', data.observation_scope, 'muted'));
      const observations = document.createElement('ul');
      for (const row of finding.observations) {
        const {event} = row, p = event.payload;
        const reading = event.event_type === 'plant_feedback'
          ? `${p.actual_delivery_mg_s} mg/s delivered · ${p.modeled_residual_mg_l.toFixed(4)} mg/L modeled`
          : `${p.value.toFixed(3)} mg/L · ${p.quality}`;
        const item = text('li', `Step ${event.sim_step} · ${event.source_id} · ${reading} `);
        item.append(link(row.receipt_id,'Original sample'));
        observations.append(item);
      }
      section.append(observations);
    }
    $('changes').append(section);
  }
}
async function refresh() {
 if (busy) return; busy = true;
 try {
  const runs = await get('/api/runs?limit=30'), old = $('run').value;
  $('run').replaceChildren();
  if (!runs.items.length) $('run').append(new Option('Waiting for captured events',''));
  for (const r of runs.items) $('run').append(new Option(r.run_id,r.run_id));
  if (runs.items.some(r=>r.run_id===old)) $('run').value = old;
  const query = $('run').value ? 'run_id='+encodeURIComponent($('run').value)+'&' : '';
  const [health,sources,events,findings,errors,changes] = await Promise.all([get('/api/health'),get('/api/sources?'+query+'limit=50'),get('/api/events?'+query+'limit=30'),get('/api/findings?'+query+'limit=1'),get('/api/errors?limit=10'),get('/api/changes?'+query+'limit=10')]);
  $('connection').textContent = `${health.counts.normalized_events} saved events · ${health.counts.validation_errors} issues · updated ${new Date().toLocaleTimeString()}`;
  $('sources').replaceChildren();
  for (const s of sources.items) {
   const card=text('article','', 'card'), event=s.sample, p=event?.payload;
   card.append(text('h2',s.source_id),text('span',s.state.toUpperCase(),'badge '+s.state));
   const value = !event ? 'No sample' : s.source_id==='plant-model' ? `${p.actual_delivery_mg_s.toFixed(2)} mg/s` : `${p.value.toFixed(3)} mg/L`;
   card.append(text('div',value,'value'),text('p',s.age_seconds===null?'No saved evidence':`Original sample age: ${s.age_seconds.toFixed(1)} seconds`,'muted'));
   if(event) {
     if (s.source_id === 'plant-model' && p.accepted_feed_mg_s != null) card.append(text('p',`Accepted setting ${p.accepted_feed_mg_s.toFixed(2)} mg/s · pump ${p.pump_running ? 'running' : 'stopped'}`,'muted'));
     card.append(text('p',`Step ${event.sim_step} · ${p.quality || 'plant feedback'}`,'muted'),text('p',`Sample UTC ${event.source_timestamp_utc}`,'muted'),link(s.receipt_id,'Inspect original receipt'));
   }
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
  showChanges(changes);
  $('events').replaceChildren();
  for(const row of events.items) {const e=row.event,tr=document.createElement('tr'),source=document.createElement('td');source.append(text('strong',e.source_id),text('small',e.event_type));tr.append(source);
    for(const value of [e.sim_step,e.source_timestamp_utc,row.received_at_utc])tr.append(text('td',value));const proof=document.createElement('td');proof.append(link(row.receipt_id,'Original'));tr.append(proof);$('events').append(tr);}
  $('errors').replaceChildren(); if(!errors.items.length)$('errors').append(text('p','No recorded validation or identity issues.','muted'));
  for(const error of errors.items) {const div=text('div',error.code+': '+error.message+' ','issue');div.append(link(error.receipt_id,'Retained original'));$('errors').append(div);}
 } catch(e) { $('connection').textContent='Evidence unavailable';$('alerts').textContent='Evidence API unavailable. Existing values may be old; displayed ages are no longer updating. '+e.message;
   $('action-alerts').textContent='Recorded findings may be out of date while the evidence API is unavailable.';
   changeSnapshot = '';
   for(const badge of $('sources').querySelectorAll('.badge')) { badge.textContent='CONNECTION UNAVAILABLE';badge.className='badge unavailable'; }
 }
 finally {busy=false;}
}
$('run').addEventListener('change',refresh); refresh(); setInterval(refresh,2000);
