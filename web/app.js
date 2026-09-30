/* AeroCore frontend — intentionally dependency-light; Leaflet supplies the map. */
const $ = (id) => document.getElementById(id);
let snapshot = null;
let map = null, mapLarge = null;
const markers = new Map(), markersLarge = new Map();

const fmtTime = (iso) => iso ? new Date(iso).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'}) : '—';
const fmtNum = (n) => Number(n ?? 0).toLocaleString();
const km = (m) => (Number(m ?? 0) / 1000).toFixed(1);
const toast = (msg) => { const el=$('toast'); el.textContent=msg; el.classList.add('show'); setTimeout(()=>el.classList.remove('show'),2200); };

function makeIcon(track=0){ return L.divIcon({className:'', html:`<div class="aircraft-marker" style="transform:rotate(${track}deg)">✈</div>`, iconSize:[18,18], iconAnchor:[9,9]}); }

function initMap(){
  map = L.map('map',{zoomControl:true,worldCopyJump:true,preferCanvas:true}).setView([9.0068,7.2632],7);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'© OpenStreetMap contributors'}).addTo(map);
  mapLarge = L.map('mapLarge',{zoomControl:true,worldCopyJump:true,preferCanvas:true}).setView([9.0068,7.2632],7);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'© OpenStreetMap contributors'}).addTo(mapLarge);
}

function updateMap(targetMap, markerMap, aircraft){
  const alive = new Set();
  aircraft.forEach(a=>{
    if(a.lat==null || a.lon==null) return;
    alive.add(a.icao24);
    let marker=markerMap.get(a.icao24);
    if(!marker){ marker=L.marker([a.lat,a.lon],{icon:makeIcon(a.track)}).addTo(targetMap); markerMap.set(a.icao24,marker); }
    else marker.setLatLng([a.lat,a.lon]).setIcon(makeIcon(a.track));
    const alt = a.alt >= 1000 ? `${km(a.alt)} km` : `${Math.round(a.alt)} m`;
    marker.bindTooltip(`${a.callsign || 'UNKNOWN'} · ${a.status}<br>${alt} · ${Math.round(a.speed||0)} kt`,{direction:'top'});
  });
  [...markerMap.entries()].forEach(([id,m])=>{if(!alive.has(id)){targetMap.removeLayer(m);markerMap.delete(id)}});
}

function renderAircraftRows(){
  const rows = snapshot.aircraft.map(a=>`<tr><td>${a.callsign||'UNKNOWN'}</td><td><span class="tag ${a.status==='GROUND'?'':'high'.replace('high','')}">${a.status}</span></td><td>${Math.round(a.alt||0).toLocaleString()} ft</td><td>${Math.round(a.speed||0)} kt</td><td>${Math.round(a.vr||0)} fpm</td><td>${Number(a.lat).toFixed(3)}, ${Number(a.lon).toFixed(3)}</td><td>${fmtTime(a.last_contact)}</td></tr>`).join('');
  $('flightTable').innerHTML=rows;
  $('aircraftTable').innerHTML=snapshot.aircraft.map(a=>`<tr><td>${a.icao24}</td><td>${a.callsign||'UNKNOWN'}</td><td>${a.country}</td><td>${a.status}</td><td>${Math.round(a.alt||0).toLocaleString()} ft</td><td>${Math.round(a.track||0)}°</td></tr>`).join('');
}

function renderTurnarounds(){
  $('turnaroundList').innerHTML = snapshot.turnarounds.map(t=>`<div class="stack-item"><div><h4>${t.flight} · ${t.gate}</h4><p>${t.status} · ${t.elapsed_min}/${t.target_min} min</p></div><span class="tag ${t.risk.toLowerCase()}">${t.risk}</span></div>`).join('');
  $('turnaroundGrid').innerHTML = snapshot.turnarounds.map(t=>Object.entries(t.stages).map(([label,val])=>`<div class="progress-row"><div class="phead"><span>${label}</span><span>${val}%</span></div><div class="progress"><span style="width:${val}%"></span></div></div>`).join('') + `<div class="card turn-card"><div class="turn-top"><div><span class="eyebrow">TURNAROUND</span><h3>${t.flight}</h3><div class="turn-meta">${t.aircraft} · Gate ${t.gate}</div></div><span class="turn-risk ${t.risk==='HIGH'?'risk-high':t.risk==='LOW'?'risk-low':'risk-medium'}">${t.risk} RISK</span></div><div>${Object.entries(t.stages).map(([label,val])=>`<div class="progress-row"><div class="phead"><span>${label}</span><span>${val}%</span></div><div class="progress"><span style="width:${val}%"></span></div></div>`).join('')}</div><div class="turn-summary"><div><span class="eyebrow">ELAPSED</span><strong>${t.elapsed_min} min</strong></div><div><span class="eyebrow">TARGET</span><strong>${t.target_min} min</strong></div><div><span class="eyebrow">STATUS</span><strong>${t.status}</strong></div></div></div>`).join('');
}

function renderAlerts(){
  $('alertList').innerHTML = snapshot.alerts.map(a=>`<div class="stack-item"><div><h4>${a.title}</h4><p>${a.summary}</p></div><span class="tag ${a.severity.toLowerCase()}">${a.severity}</span></div>`).join('');
}

function renderEvents(){
  const html=snapshot.events.map(e=>`<div class="event-row"><div class="event-time">${fmtTime(e.ts)}</div><div class="event-kind">${e.kind}</div><div class="event-detail">${e.entity} · ${e.detail}</div><div class="event-source">${e.source}</div></div>`).join('');
  $('eventList').innerHTML=html;
  $('eventListLarge').innerHTML=html;
}

function renderIncidents(){
  $('incidentGrid').innerHTML=snapshot.incidents.map(i=>`<div class="card incident-card"><div class="row"><div><span class="eyebrow">${i.category}</span><h3>${i.id}</h3></div><span class="tag ${i.severity.toLowerCase()}">${i.severity}</span></div><p><b>${i.title}</b><br>Entity: ${i.entity}<br>Status: ${i.status}<br>Owner: ${i.owner}</p><div class="incident-timeline">${i.opened} · Detected → Acknowledged → Investigating → ${i.status}</div></div>`).join('');
}

function renderWeather(){
  const w=snapshot.weather;
  $('weatherStation').textContent=w?.station || snapshot.airport.code;
  $('weatherMode').textContent=snapshot.weather_meta.mode;
  $('weatherCat').textContent=w?.flight_category || 'NO DATA';
  $('weatherTemp').textContent=w?.temp_c!=null ? `${w.temp_c.toFixed(1)}°` : '—';
  $('weatherWind').textContent=w ? `${w.wind_kt||0} kt${w.wind_dir ? ` @ ${w.wind_dir}°` : ''}` : '—';
  $('weatherVis').textContent=w?.visibility ?? '—';
  $('weatherDew').textContent=w?.dewpoint_c!=null ? `${w.dewpoint_c.toFixed(1)}°C` : '—';
  $('weatherObs').textContent=fmtTime(w?.observed);
  $('weatherRaw').textContent=w?.raw || snapshot.weather_meta.error || 'Waiting for the latest METAR…';
}

function renderSources(){
  $('sourceOpenSky').textContent=snapshot.traffic_meta.mode;
  $('sourceOpenSkyMeta').textContent=`Last success ${fmtTime(snapshot.traffic_meta.last_success)} · refresh ${snapshot.traffic_meta.refresh_seconds}s${snapshot.traffic_meta.error ? ` · ${snapshot.traffic_meta.error}`:''}`;
  $('sourceAWC').textContent=snapshot.weather_meta.mode;
  $('sourceAWCMeta').textContent=`Last success ${fmtTime(snapshot.weather_meta.last_success)}${snapshot.weather_meta.error ? ` · ${snapshot.weather_meta.error}`:''}`;
  $('trafficModuleMode').textContent=snapshot.traffic_meta.mode;
  $('trafficFreshness').textContent=`Last sync ${fmtTime(snapshot.traffic_meta.last_success)}`;
  $('trafficMode').textContent=snapshot.traffic_meta.mode;
}

function renderKpis(){
  $('kTracked').textContent=fmtNum(snapshot.kpis.tracked);
  $('kAirborne').textContent=fmtNum(snapshot.kpis.airborne);
  $('kHigh').textContent=fmtNum(snapshot.kpis.high_altitude);
  $('kAlerts').textContent=fmtNum(snapshot.kpis.alerts);
  $('kIncidentsText').textContent=`${snapshot.kpis.incidents} open incidents`;
  $('kGates').textContent=`${snapshot.kpis.gates.occupied}/${snapshot.kpis.gates.total}`;
  $('kSecurity').textContent=`${snapshot.kpis.security_wait} min`;
  $('bagProcessed').textContent=fmtNum(snapshot.baggage.processed);
  $('bagTotal').textContent=fmtNum(snapshot.baggage.total);
  $('bagExceptions').textContent=fmtNum(snapshot.baggage.exceptions);
  $('bagOpen').textContent=fmtNum(snapshot.baggage.open_exceptions);
}

function renderAll(){
  if(!snapshot) return;
  $('contextTitle').textContent=snapshot.airport.name;
  renderKpis(); renderWeather(); renderSources(); renderTurnarounds(); renderAlerts(); renderEvents(); renderIncidents(); renderAircraftRows();
  if(map){ map.setView([snapshot.airport.lat,snapshot.airport.lon], snapshot.airport.code==='KJFK'||snapshot.airport.code==='KLAX'?9:8); updateMap(map,markers,snapshot.aircraft); }
  if(mapLarge){ mapLarge.setView([snapshot.airport.lat,snapshot.airport.lon], snapshot.airport.code==='KJFK'||snapshot.airport.code==='KLAX'?9:8); updateMap(mapLarge,markersLarge,snapshot.aircraft); }
}

function connect(){
  const proto=location.protocol==='https:'?'wss':'ws';
  const ws=new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen=()=>{$('socketStatus').innerHTML='<span class="status-dot"></span> LIVE STREAM';$('socketStatus').classList.add('pill-live');};
  ws.onmessage=(msg)=>{ const data=JSON.parse(msg.data); if(data.type==='snapshot'){ snapshot=data.payload; renderAll(); }};
  ws.onclose=()=>{ $('socketStatus').innerHTML='<span class="status-dot" style="background:#eecb67"></span> RECONNECTING'; setTimeout(connect,1500); };
}

async function loadSnapshot(){ const r=await fetch('/api/snapshot'); snapshot=await r.json(); renderAll(); }

async function setAirport(code){
  const r=await fetch(`/api/airport/${code}`,{method:'POST'}); const data=await r.json(); if(data.ok){snapshot=data.snapshot;renderAll();toast(`Switched operations context to ${code}`)}
}

function wireNav(){
  document.querySelectorAll('.nav-item,[data-panel]').forEach(el=>{
    el.addEventListener('click',e=>{ const panel=el.dataset.panel; if(!panel) return; document.querySelectorAll('.panel-section').forEach(p=>p.classList.remove('active-panel')); $(panel).classList.add('active-panel'); document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active')); document.querySelector(`.nav-item[data-panel="${panel}"]`)?.classList.add('active'); if(panel==='traffic'&&mapLarge) setTimeout(()=>mapLarge.invalidateSize(),50); });
  });
}

$('airportSelect').addEventListener('change',e=>setAirport(e.target.value));
$('refreshBtn').addEventListener('click',loadSnapshot);
setInterval(()=>$('clock').textContent=new Date().toLocaleTimeString([], {hour12:false}),1000);

(async function init(){ initMap(); wireNav(); await loadSnapshot(); connect(); })();
