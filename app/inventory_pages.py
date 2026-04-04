"""Inventory HTML page routes: list, detail, create, import, scan."""

from __future__ import annotations

import html as html_mod

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from app.auth import require_user
from app.database import User
from app.layout import render_shell

router = APIRouter(tags=["inventory-pages"])

_E = html_mod.escape


# ── Inventory List ──────────────────────────────────────────────────

@router.get("/inventory", response_class=HTMLResponse)
def inventory_list_page(user: User = Depends(require_user)) -> HTMLResponse:
    body = """
  <div class="page-header">
    <div class="page-header-left">
      <div>
        <p class="page-desc" style="margin-bottom:0">Track, search, and manage your inventory items.</p>
      </div>
    </div>
    <a href="/inventory/new" class="btn btn-primary" style="padding:10px 20px;font-size:14px;">
      <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="10" y1="4" x2="10" y2="16"/><line x1="4" y1="10" x2="16" y2="10"/></svg>
      New Item
    </a>
  </div>
  <div class="sr" id="sr"></div>
  <div class="search-bar">
    <input type="text" id="q" placeholder="Search by name, SKU, barcode, location, tags..." autofocus>
    <select id="cf" style="padding:8px;border-radius:8px;border:1px solid var(--line);background:var(--paper);color:var(--text);font-size:14px;"><option value="">All Categories</option></select>
  </div>
  <div class="panel" style="padding:0;overflow-x:auto;">
    <table><thead><tr><th>Name</th><th>SKU</th><th>Qty</th><th>Location</th><th>Category</th><th>Barcode</th><th>Status</th><th></th></tr></thead>
    <tbody id="tb"><tr><td colspan="8" class="empty">Loading...</td></tr></tbody></table>
  </div>"""

    js = """<script>
let all=[];
async function load(){const[ir,cr]=await Promise.all([fetch('/api/inventory?limit=1000').then(r=>r.json()),fetch('/api/inventory/categories').then(r=>r.json())]);all=ir.items;renderS(all);renderI(all);const s=document.getElementById('cf');cr.categories.forEach(c=>{const o=document.createElement('option');o.value=c;o.textContent=c;s.appendChild(o)})}
function renderS(items){const a=items.filter(i=>i.status==='active'),tq=a.reduce((s,i)=>s+i.quantity,0),ls=a.filter(i=>i.min_quantity>0&&i.quantity<=i.min_quantity).length,zs=a.filter(i=>i.quantity===0).length,cs=new Set(a.map(i=>i.category).filter(Boolean));document.getElementById('sr').innerHTML=`<div class="sb"><div class="v">${a.length}</div><div class="l">Items</div></div><div class="sb"><div class="v">${tq.toLocaleString()}</div><div class="l">Total Units</div></div><div class="sb"><div class="v">${cs.size}</div><div class="l">Categories</div></div><div class="sb"><div class="v" style="color:${ls?'var(--warning)':'var(--success)'}">${ls}</div><div class="l">Low Stock</div></div><div class="sb"><div class="v" style="color:${zs?'var(--failure)':'var(--success)'}">${zs}</div><div class="l">Out of Stock</div></div>`}
function renderI(items){const tb=document.getElementById('tb');if(!items.length){tb.innerHTML='<tr><td colspan="8" class="empty"><div style="padding:20px 0"><svg width="40" height="40" viewBox="0 0 20 20" fill="none" stroke="var(--muted)" stroke-width="1" style="margin-bottom:12px;opacity:0.5"><path d="M2 3h16v4H2z"/><path d="M2 9h16v8H2z"/><line x1="8" y1="12" x2="12" y2="12"/></svg><div style="font-size:15px;margin-bottom:6px;color:var(--text)">No items found</div><div style="margin-bottom:16px">Get started by creating your first inventory item.</div><a href="/inventory/new" class="btn btn-primary">Create Item</a></div></td></tr>';return}tb.innerHTML=items.map(i=>`<tr style="cursor:pointer" onclick="location='/inventory/${i.id}'"><td><strong>${esc(i.name)}</strong></td><td><code style="color:var(--muted)">${esc(i.sku)}</code></td><td class="${i.quantity===0?'qz':i.min_quantity>0&&i.quantity<=i.min_quantity?'ql':''}">${i.quantity} ${esc(i.unit)}</td><td>${esc(i.location)||'<span style="color:var(--muted)">-</span>'}</td><td>${i.category?`<span class="badge bb">${esc(i.category)}</span>`:''}</td><td><code style="font-size:11px;color:var(--muted)">${esc(i.barcode_value)}</code></td><td><span class="badge ${i.status==='active'?'bg':'bgr'}">${i.status}</span></td><td><a href="/inventory/${i.id}" class="btn btn-sm btn-secondary" onclick="event.stopPropagation()">View</a></td></tr>`).join('')}
document.getElementById('q').addEventListener('input',filt);document.getElementById('cf').addEventListener('change',filt);
function filt(){const q=document.getElementById('q').value.toLowerCase(),c=document.getElementById('cf').value;let f=all;if(q)f=f.filter(i=>i.name.toLowerCase().includes(q)||i.sku.toLowerCase().includes(q)||i.barcode_value.toLowerCase().includes(q)||(i.location||'').toLowerCase().includes(q)||(i.tags||'').toLowerCase().includes(q));if(c)f=f.filter(i=>i.category===c);renderI(f)}
load();
</script>"""

    return HTMLResponse(content=render_shell(
        title="Inventory",
        active_nav="items",
        body_html=body,
        body_js=js,
        display_name=user.display_name,
        role=user.role,
    ))


# ── Create Item ─────────────────────────────────────────────────────

@router.get("/inventory/new", response_class=HTMLResponse)
def inventory_create_page(user: User = Depends(require_user)) -> HTMLResponse:
    body = """
  <div id="err" class="err"></div>
  <p class="page-desc">Fill in the details below to add a new item to your inventory. Fields marked with * are required.</p>
  <div class="panel">
    <form id="cf" onsubmit="return cI(event)">
      <div class="form-section">
        <div class="form-section-title">Basic Information</div>
        <div class="fr"><div class="fg"><label>Name *</label><input type="text" id="name" required autofocus></div><div class="fg"><label>SKU *</label><input type="text" id="sku" required placeholder="e.g. WIDGET-001"></div></div>
        <div class="fg"><label>Description</label><textarea id="description" rows="2" placeholder="Brief description of the item..."></textarea></div>
      </div>
      <div class="form-section">
        <div class="form-section-title">Stock &amp; Pricing</div>
        <div class="fr3"><div class="fg"><label>Quantity</label><input type="number" id="quantity" value="0" min="0"></div><div class="fg"><label>Unit</label><input type="text" id="unit" value="each"></div><div class="fg"><label>Min Qty (alert)</label><input type="number" id="min_quantity" value="0" min="0"></div></div>
        <div class="fr"><div class="fg"><label>Cost per unit</label><input type="number" id="cost" step="0.01" min="0" placeholder="0.00"></div><div class="fg"><label>Tags (comma-separated)</label><input type="text" id="tags" placeholder="fragile, high-priority"></div></div>
      </div>
      <div class="form-section">
        <div class="form-section-title">Location &amp; Category</div>
        <div class="fr"><div class="fg"><label>Location</label><input type="text" id="location" placeholder="Warehouse A, Shelf B3"></div><div class="fg"><label>Category</label><input type="text" id="category" placeholder="Raw Materials"></div></div>
      </div>
      <div class="form-section">
        <div class="form-section-title">Barcode</div>
        <div class="form-section-desc">Leave barcode value empty to auto-generate one.</div>
        <div class="fr"><div class="fg"><label>Barcode Type</label><select id="barcode_type"><option value="Code128" selected>Code 128</option><option value="QRCode">QR Code</option><option value="EAN13">EAN-13</option><option value="Code39">Code 39</option><option value="DataMatrix">Data Matrix</option></select></div><div class="fg"><label>Barcode Value</label><input type="text" id="barcode_value" placeholder="Auto-generated if empty"></div></div>
      </div>
      <div class="form-section" style="margin-bottom:0">
        <div class="form-section-title">Notes</div>
        <div class="fg"><label>Additional Notes</label><textarea id="notes" rows="2" placeholder="Any additional information..."></textarea></div>
      </div>
      <div style="margin-top:20px;display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap">
        <div style="display:flex;gap:10px"><button type="submit" class="btn btn-primary" style="padding:10px 24px">Create Item</button><a href="/inventory" class="btn btn-secondary">Cancel</a></div>
        <span id="autosave-badge" class="autosave-badge">Auto-saving</span>
      </div>
    </form>
  </div>"""

    js = """<script>
const _FIELDS=['name','sku','description','quantity','unit','location','category','tags','notes','barcode_type','barcode_value','min_quantity','cost'];
const _as=autosaveInit('new_item',_FIELDS);
const _guard=guardUnsaved('#cf');
if(_as.load()){toast('Draft restored from previous session','info')}
async function cI(e){e.preventDefault();hideMsg();const b={};_FIELDS.forEach(f=>{let v=document.getElementById(f).value;if(f==='quantity'||f==='min_quantity')v=parseInt(v)||0;else if(f==='cost')v=v?parseFloat(v):null;b[f]=v});const r=await apiCall('POST','/api/inventory',b);if(!r.ok){showErr(r.data.error||'Failed');return false}_guard.markClean();_as.clear();location.href='/inventory/'+r.data.item.id;return false}
</script>"""

    return HTMLResponse(content=render_shell(
        title="New Item",
        active_nav="new-item",
        body_html=body,
        body_js=js,
        display_name=user.display_name,
        role=user.role,
    ))


# ── Import CSV ──────────────────────────────────────────────────────

@router.get("/inventory/import", response_class=HTMLResponse)
def inventory_import_page(user: User = Depends(require_user)) -> HTMLResponse:
    body = """
  <div id="err" class="err"></div><div id="suc" class="suc"></div>
  <p class="page-desc">Upload a CSV file to bulk import or update inventory items.</p>
  <div class="panel">
    <form onsubmit="return doImport(event)" id="import-form">
      <div class="dropzone" id="dropzone" onclick="document.getElementById('csvf').click()">
        <div class="dropzone-icon">
          <svg width="40" height="40" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v12a2 2 0 002 2h8a2 2 0 002-2V4a2 2 0 00-2-2z"/><polyline points="7 10 10 13 13 10"/><line x1="10" y1="6" x2="10" y2="13"/></svg>
        </div>
        <div class="dropzone-text"><strong>Click to choose a file</strong> or drag and drop</div>
        <div class="dropzone-hint">.csv files only</div>
        <div id="file-name" style="margin-top:10px;font-weight:600;color:var(--text);display:none"></div>
        <input type="file" id="csvf" accept=".csv" required style="display:none">
      </div>
      <div style="margin-top:16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <button type="submit" class="btn btn-primary" id="ibtn" style="padding:10px 24px" disabled>Import File</button>
        <span id="import-status" style="font-size:13px;color:var(--muted)">Select a CSV file to begin</span>
      </div>
    </form>
    <div id="res" style="margin-top:20px;display:none"></div>
  </div>
  <div class="fr">
    <div class="panel">
      <div class="form-section-title" style="margin-bottom:12px">Expected CSV Columns</div>
      <code style="font-size:12px;line-height:2;color:var(--muted)">name, sku, description, quantity, unit, location, category, tags, notes, barcode_value, barcode_type, min_quantity, cost</code>
    </div>
    <div class="panel">
      <div class="form-section-title" style="margin-bottom:12px">How It Works</div>
      <ul style="color:var(--muted);font-size:13px;padding-left:18px;line-height:2">
        <li>Existing SKUs are <strong style="color:var(--text)">updated</strong></li>
        <li>New SKUs are <strong style="color:var(--text)">created</strong></li>
        <li>Barcodes are <strong style="color:var(--text)">auto-generated</strong> if left blank</li>
      </ul>
      <a href="/api/inventory/export/csv" class="btn btn-secondary btn-sm" style="margin-top:12px">Download Template / Export</a>
    </div>
  </div>"""

    js = """<script>
const dz=document.getElementById('dropzone'),fi=document.getElementById('csvf'),fn=document.getElementById('file-name'),ibtn=document.getElementById('ibtn'),ist=document.getElementById('import-status');
['dragenter','dragover'].forEach(e=>dz.addEventListener(e,ev=>{ev.preventDefault();dz.classList.add('drag-over')}));
['dragleave','drop'].forEach(e=>dz.addEventListener(e,ev=>{ev.preventDefault();dz.classList.remove('drag-over')}));
dz.addEventListener('drop',ev=>{const files=ev.dataTransfer.files;if(files.length&&files[0].name.endsWith('.csv')){fi.files=files;fileSelected(files[0])}else{toast('Please drop a .csv file','warning')}});
fi.addEventListener('change',()=>{if(fi.files[0])fileSelected(fi.files[0])});
function fileSelected(f){fn.textContent=f.name+' ('+Math.round(f.size/1024)+'KB)';fn.style.display='block';ibtn.disabled=false;ist.textContent='Ready to import'}
async function doImport(e){e.preventDefault();hideMsg();const f=fi.files[0];if(!f){showErr('Select a file');return false}ibtn.disabled=true;ist.innerHTML='<span style="color:var(--info)">Importing...</span>';const fd=new FormData();fd.append('file',f);try{const r=await fetch('/api/inventory/import/csv',{method:'POST',body:fd});const d=await r.json();if(!r.ok){showErr(d.error||'Import failed');ibtn.disabled=false;ist.textContent='Import failed';return false}showSuc(d.message);ist.innerHTML='<span style="color:var(--success)">Import complete</span>';const res=document.getElementById('res');res.style.display='block';let h='<div class="panel" style="background:var(--success-bg);border-color:var(--success-border)"><strong style="color:var(--success)">'+d.created+' created, '+d.updated+' updated</strong></div>';if(d.errors.length)h+='<div class="panel" style="background:var(--failure-bg);border-color:var(--failure-border);color:var(--failure)">'+d.errors.map(e=>'<div style="padding:2px 0">'+esc(e)+'</div>').join('')+'</div>';res.innerHTML=h}catch(er){showErr('Network error');ist.textContent='Network error'}ibtn.disabled=false;return false}
</script>"""

    return HTMLResponse(content=render_shell(
        title="Import CSV",
        active_nav="import",
        body_html=body,
        body_js=js,
        display_name=user.display_name,
        role=user.role,
    ))


# ── Item Detail ─────────────────────────────────────────────────────

@router.get("/inventory/{item_id}", response_class=HTMLResponse)
def inventory_detail_page(item_id: str, user: User = Depends(require_user)) -> HTMLResponse:
    safe_id = _E(item_id)

    body = """
  <div id="err" class="err"></div><div id="suc" class="suc"></div>
  <div id="ld" class="empty" style="padding:60px 20px">
    <div style="font-size:14px;color:var(--muted)">Loading item details...</div>
  </div>
  <div id="ct" style="display:none">
    <div class="page-header" style="margin-bottom:24px">
      <div>
        <h2 id="iname" style="font-size:22px;font-weight:700;margin-bottom:2px"></h2>
        <code id="isku" style="color:var(--muted);font-size:13px"></code>
      </div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <button class="btn btn-success" onclick="showAdj()">
          <svg width="14" height="14" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="10" y1="4" x2="10" y2="16"/><line x1="4" y1="10" x2="16" y2="10"/></svg>
          Adjust Qty
        </button>
        <button class="btn btn-secondary" onclick="toggleEdit()">
          <svg width="14" height="14" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M13 2l5 5-9 9H4v-5z"/></svg>
          Edit
        </button>
        <button class="btn btn-danger btn-sm" onclick="delItem()">Delete</button>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 280px;gap:24px;align-items:start" id="mg">
      <div>
        <div class="panel" id="dc"></div>
        <div class="panel" id="ec" style="display:none"></div>
        <div class="panel" id="ac" style="display:none">
          <div class="form-section-title">Adjust Quantity</div>
          <div class="fr3">
            <div class="fg"><label>Change (+/-)</label><input type="number" id="aq" value="0"></div>
            <div class="fg"><label>Reason</label><select id="ar"><option value="received">Received</option><option value="sold">Sold</option><option value="adjusted">Adjusted</option><option value="damaged">Damaged</option><option value="returned">Returned</option></select></div>
            <div class="fg"><label>Notes</label><input type="text" id="an" placeholder="Optional note..."></div>
          </div>
          <div style="display:flex;gap:8px;margin-top:8px">
            <button class="btn btn-success" onclick="doAdj()">Apply Adjustment</button>
            <button class="btn btn-secondary" onclick="document.getElementById('ac').style.display='none'">Cancel</button>
          </div>
        </div>
        <div class="panel">
          <div class="form-section-title" style="margin-bottom:12px">Transaction History</div>
          <div style="overflow-x:auto">
            <table><thead><tr><th>Date</th><th>Change</th><th>After</th><th>Reason</th><th>Notes</th></tr></thead><tbody id="txb"></tbody></table>
          </div>
        </div>
      </div>
      <div>
        <div class="panel" style="text-align:center;position:sticky;top:80px">
          <div class="form-section-title" style="text-align:center">Barcode</div>
          <div class="bp"><img id="bimg" alt="barcode" style="max-width:100%"></div>
          <div style="margin-top:10px"><code id="bval" style="color:var(--muted);font-size:12px"></code></div>
          <div style="margin-top:14px;display:flex;gap:8px;justify-content:center;flex-wrap:wrap">
            <a id="bdl" class="btn btn-sm btn-secondary" download>
              <svg width="12" height="12" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 00-2 2v12a2 2 0 002 2h8a2 2 0 002-2V4a2 2 0 00-2-2z"/><polyline points="7 10 10 7 13 10"/><line x1="10" y1="14" x2="10" y2="7"/></svg>
              Download
            </a>
            <button class="btn btn-sm btn-secondary" onclick="printBC()">
              <svg width="12" height="12" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="4 7 4 2 16 2 16 7"/><rect x="2" y="7" width="16" height="8" rx="1"/><rect x="6" y="12" width="8" height="6"/></svg>
              Print
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>"""

    js = f"""<script>
const ID='{safe_id}';let cur=null;
async function load(){{const r=await apiCall('GET',`/api/inventory/${{ID}}`);if(!r.ok){{showErr('Item not found');return}}cur=r.data.item;document.getElementById('ld').style.display='none';document.getElementById('ct').style.display='block';renderD(r.data.item,r.data.transactions)}}
function renderD(i,tx){{document.getElementById('iname').textContent=i.name;document.getElementById('isku').textContent=i.sku;document.title=i.name+' - Barcode Buddy';const bu=`/api/inventory/${{i.id}}/barcode.png?scale=5`;document.getElementById('bimg').src=bu;document.getElementById('bval').textContent=i.barcode_value;document.getElementById('bdl').href=bu;
const qc=i.quantity===0?'qz':i.min_quantity>0&&i.quantity<=i.min_quantity?'ql':'';
document.getElementById('dc').innerHTML=`<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px"><div><div style="font-size:11px;color:var(--muted);text-transform:uppercase">Quantity</div><div style="font-size:28px;font-weight:700" class="${{qc}}">${{i.quantity}} <span style="font-size:14px;color:var(--muted)">${{esc(i.unit)}}</span></div></div><div><div style="font-size:11px;color:var(--muted);text-transform:uppercase">Location</div><div style="font-size:16px">${{esc(i.location)||'—'}}</div></div><div><div style="font-size:11px;color:var(--muted);text-transform:uppercase">Category</div><div>${{i.category?'<span class="badge bb">'+esc(i.category)+'</span>':'—'}}</div></div><div><div style="font-size:11px;color:var(--muted);text-transform:uppercase">Status</div><div><span class="badge ${{i.status==='active'?'bg':'bgr'}}">${{i.status}}</span></div></div><div><div style="font-size:11px;color:var(--muted);text-transform:uppercase">Cost</div><div>${{i.cost!=null?'$'+i.cost.toFixed(2):'—'}}</div></div><div><div style="font-size:11px;color:var(--muted);text-transform:uppercase">Min Qty</div><div>${{i.min_quantity}}</div></div></div>${{i.description?'<div style="margin-top:16px"><div style="font-size:11px;color:var(--muted);text-transform:uppercase;margin-bottom:4px">Description</div><div>'+esc(i.description)+'</div></div>':''}}${{i.tags?'<div style="margin-top:12px"><div style="font-size:11px;color:var(--muted);text-transform:uppercase;margin-bottom:4px">Tags</div><div>'+i.tags.split(',').map(t=>'<span class="badge bgr" style="margin:2px">'+esc(t.trim())+'</span>').join('')+'</div></div>':''}}${{i.notes?'<div style="margin-top:12px"><div style="font-size:11px;color:var(--muted);text-transform:uppercase;margin-bottom:4px">Notes</div><div style="color:var(--muted)">'+esc(i.notes)+'</div></div>':''}}<div style="margin-top:16px;font-size:11px;color:var(--muted)">Created: ${{new Date(i.created_at).toLocaleString()}} · Updated: ${{new Date(i.updated_at).toLocaleString()}}</div>`;
document.getElementById('txb').innerHTML=tx.length?tx.map(t=>`<tr><td style="white-space:nowrap">${{new Date(t.created_at).toLocaleString()}}</td><td style="font-weight:600;color:${{t.quantity_change>=0?'var(--success)':'var(--failure)'}}">${{t.quantity_change>=0?'+':''}}\u200b${{t.quantity_change}}</td><td>${{t.quantity_after}}</td><td><span class="badge bgr">${{esc(t.reason)}}</span></td><td style="color:var(--muted)">${{esc(t.notes)}}</td></tr>`).join(''):'<tr><td colspan="5" class="empty">No transactions yet</td></tr>'}}
function showAdj(){{document.getElementById('ac').style.display='block';document.getElementById('aq').focus()}}
async function doAdj(){{hideMsg();const q=parseInt(document.getElementById('aq').value);if(!q){{showErr('Enter a non-zero quantity');return}}const r=await apiCall('POST',`/api/inventory/${{ID}}/adjust`,{{quantity_change:q,reason:document.getElementById('ar').value,notes:document.getElementById('an').value}});if(!r.ok){{showErr(r.data.error);return}}document.getElementById('ac').style.display='none';document.getElementById('aq').value='0';document.getElementById('an').value='';showSuc('Quantity adjusted');load()}}
function toggleEdit(){{const c=document.getElementById('ec');if(c.style.display==='none'){{const i=cur;c.style.display='block';c.innerHTML=`<div class="form-section"><div class="form-section-title">Edit Item</div><div class="fr"><div class="fg"><label>Name</label><input type="text" id="en" value="${{esc(i.name)}}"></div><div class="fg"><label>SKU</label><input type="text" id="es" value="${{esc(i.sku)}}"></div></div><div class="fg"><label>Description</label><textarea id="ed" rows="2">${{esc(i.description)}}</textarea></div></div><div class="form-section"><div class="form-section-title">Stock &amp; Pricing</div><div class="fr3"><div class="fg"><label>Quantity</label><input type="number" id="eq" value="${{i.quantity}}" min="0"></div><div class="fg"><label>Unit</label><input type="text" id="eu" value="${{esc(i.unit)}}"></div><div class="fg"><label>Min Qty</label><input type="number" id="em" value="${{i.min_quantity}}" min="0"></div></div><div class="fr"><div class="fg"><label>Cost</label><input type="number" id="ec2" step="0.01" value="${{i.cost||''}}"></div><div class="fg"><label>Tags</label><input type="text" id="et" value="${{esc(i.tags)}}"></div></div></div><div class="form-section"><div class="form-section-title">Location &amp; Status</div><div class="fr"><div class="fg"><label>Location</label><input type="text" id="el" value="${{esc(i.location)}}"></div><div class="fg"><label>Category</label><input type="text" id="ecat" value="${{esc(i.category)}}"></div></div><div class="fr"><div class="fg"><label>Notes</label><textarea id="eno" rows="2">${{esc(i.notes)}}</textarea></div><div class="fg"><label>Status</label><select id="est"><option value="active" ${{i.status==='active'?'selected':''}}>Active</option><option value="archived" ${{i.status==='archived'?'selected':''}}>Archived</option></select></div></div></div><div style="display:flex;gap:8px"><button class="btn btn-primary" onclick="saveE()">Save Changes</button><button class="btn btn-secondary" onclick="document.getElementById('ec').style.display='none'">Cancel</button></div>`}}else c.style.display='none'}}
async function saveE(){{hideMsg();const b={{name:document.getElementById('en').value,sku:document.getElementById('es').value,description:document.getElementById('ed').value,unit:document.getElementById('eu').value,location:document.getElementById('el').value,category:document.getElementById('ecat').value,tags:document.getElementById('et').value,notes:document.getElementById('eno').value,status:document.getElementById('est').value,quantity:parseInt(document.getElementById('eq').value)||0,min_quantity:parseInt(document.getElementById('em').value)||0}};const cv=document.getElementById('ec2').value;b.cost=cv?parseFloat(cv):null;const r=await apiCall('PUT',`/api/inventory/${{ID}}`,b);if(!r.ok){{showErr(r.data.error);return}}document.getElementById('ec').style.display='none';showSuc('Item updated');load()}}
async function delItem(){{if(!confirm('Delete this item permanently?'))return;const r=await apiCall('DELETE',`/api/inventory/${{ID}}`);if(!r.ok){{showErr(r.data.error);return}}location.href='/inventory'}}
function printBC(){{const img=document.getElementById('bimg');const w=window.open('','','width=400,height=300');w.document.write(`<html><body style="text-align:center;padding:20px"><img src="${{img.src}}" style="max-width:100%"><br><strong>${{esc(cur.name)}}</strong><br><code>${{esc(cur.barcode_value)}}</code><br><code>${{esc(cur.sku)}}</code></body></html>`);w.document.close();w.onload=()=>w.print()}}
load();
</script>"""

    return HTMLResponse(content=render_shell(
        title="Item Detail",
        active_nav="items",
        body_html=body,
        body_js=js,
        display_name=user.display_name,
        role=user.role,
    ))


# ── Scan Page ───────────────────────────────────────────────────────

@router.get("/scan", response_class=HTMLResponse)
def scan_page(user: User = Depends(require_user)) -> HTMLResponse:
    body = """
  <p class="page-desc">Look up inventory items by barcode — type a code manually or use your camera to scan.</p>
  <div class="panel" style="margin-bottom:20px">
    <div class="form-section-title" style="margin-bottom:12px">Manual Lookup</div>
    <div class="search-bar" style="margin-bottom:0">
      <input type="text" id="mi" placeholder="Type or scan barcode value..." autofocus style="font-size:18px;padding:12px 16px">
      <button class="btn btn-primary" onclick="lookup()" style="font-size:16px;padding:12px 24px">
        <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="8" cy="8" r="6"/><line x1="13" y1="13" x2="18" y2="18"/></svg>
        Lookup
      </button>
    </div>
  </div>
  <div class="sa">
    <div>
      <div class="panel" style="padding:0;overflow:hidden">
        <div style="padding:16px 20px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center">
          <div class="form-section-title" style="margin:0;border:0;padding:0">Camera Scanner</div>
          <div style="display:flex;gap:8px;align-items:center">
            <select id="csel" style="padding:5px 8px;border-radius:6px;border:1px solid var(--line);background:var(--paper);color:var(--text);font-size:12px"></select>
            <button class="btn btn-primary btn-sm" id="cbtn" onclick="toggleCam()">Start Camera</button>
          </div>
        </div>
        <div class="cb" id="cbox" style="border-radius:0">
          <video id="vid" autoplay playsinline></video><canvas id="cvs"></canvas>
          <div class="sl" id="sline" style="display:none"></div>
          <div id="cam-placeholder" style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;color:rgba(255,255,255,0.5)">
            <svg width="48" height="48" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><path d="M2 4V2h4"/><path d="M14 2h4v2"/><path d="M2 16v2h4"/><path d="M14 18h4v-2"/><line x1="6" y1="6" x2="6" y2="14"/><line x1="10" y1="6" x2="10" y2="14"/><line x1="14" y1="6" x2="14" y2="14"/></svg>
            <div style="margin-top:12px;font-size:13px">Click "Start Camera" to begin scanning</div>
          </div>
        </div>
      </div>
      <div id="sstat" style="margin-top:8px;font-size:13px;color:var(--muted);text-align:center">Ready to scan</div>
    </div>
    <div>
      <div id="nr" class="panel" style="text-align:center;padding:40px 20px">
        <svg width="48" height="48" viewBox="0 0 20 20" fill="none" stroke="var(--muted)" stroke-width="1" style="margin-bottom:12px;opacity:0.4"><path d="M2 4V2h4"/><path d="M14 2h4v2"/><path d="M2 16v2h4"/><path d="M14 18h4v-2"/><line x1="6" y1="6" x2="6" y2="14"/><line x1="10" y1="6" x2="10" y2="14"/><line x1="14" y1="6" x2="14" y2="14"/></svg>
        <div style="font-size:15px;color:var(--text);margin-bottom:4px">Waiting for barcode</div>
        <div style="color:var(--muted);font-size:13px">Scan or enter a barcode to look up an item</div>
      </div>
      <div id="rc" class="panel" style="display:none"></div>
      <div id="nf" class="panel" style="display:none">
        <div style="text-align:center;padding:24px">
          <svg width="40" height="40" viewBox="0 0 20 20" fill="none" stroke="var(--failure)" stroke-width="1.5" stroke-linecap="round" style="margin-bottom:12px"><circle cx="10" cy="10" r="8"/><line x1="7" y1="7" x2="13" y2="13"/><line x1="13" y1="7" x2="7" y2="13"/></svg>
          <div style="font-size:16px;color:var(--failure);font-weight:600;margin-bottom:4px">Item Not Found</div>
          <div style="color:var(--muted);margin-bottom:16px;font-size:13px" id="nfc"></div>
          <a id="cl" href="/inventory/new" class="btn btn-primary">Create New Item</a>
        </div>
      </div>
    </div>
  </div>
  <div class="panel" style="margin-top:20px">
    <div class="form-section-title" style="margin-bottom:8px">Scan History</div>
    <div id="sh" style="max-height:220px;overflow-y:auto"><div style="text-align:center;padding:16px;color:var(--muted);font-size:13px">No scans yet — your recent lookups will appear here.</div></div>
  </div>"""

    js = """<script>
let scanning=false,stream=null,hist=[],lastCode='',lastTime=0;
document.getElementById('mi').addEventListener('keydown',e=>{if(e.key==='Enter')lookup()});
async function lookup(code){const inp=document.getElementById('mi');code=code||inp.value.trim();if(!code)return;inp.value=code;const now=Date.now();if(code===lastCode&&now-lastTime<2000)return;lastCode=code;lastTime=now;document.getElementById('nr').style.display='none';document.getElementById('nf').style.display='none';document.getElementById('rc').style.display='none';const r=await apiCall('GET','/api/scan/lookup?code='+encodeURIComponent(code));addHist(code,r.ok);if(!r.ok){document.getElementById('nf').style.display='block';document.getElementById('nfc').textContent='Code: '+code;document.getElementById('cl').href='/inventory/new?sku='+encodeURIComponent(code);return}renderRes(r.data.item)}
function renderRes(i){const c=document.getElementById('rc');c.style.display='block';const qc=i.quantity===0?'qz':i.min_quantity>0&&i.quantity<=i.min_quantity?'ql':'';c.innerHTML=`<div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:16px"><div><h2 style="font-size:20px;font-weight:700">${esc(i.name)}</h2><code style="color:var(--muted)">${esc(i.sku)}</code></div><a href="/inventory/${i.id}" class="btn btn-sm btn-secondary">Full Detail</a></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px"><div><span style="font-size:11px;color:var(--muted);text-transform:uppercase">Quantity</span><div style="font-size:28px;font-weight:700" class="${qc}">${i.quantity} <span style="font-size:14px;color:var(--muted)">${esc(i.unit)}</span></div></div><div><span style="font-size:11px;color:var(--muted);text-transform:uppercase">Location</span><div style="font-size:16px">${esc(i.location)||'—'}</div></div></div>${i.category?'<span class="badge bb">'+esc(i.category)+'</span>':''}${i.description?'<p style="color:var(--muted);margin-top:8px;font-size:13px">'+esc(i.description)+'</p>':''}<div class="qa"><span style="font-size:13px;color:var(--muted)">Quick adjust:</span><button class="mn" onclick="qAdj('${i.id}',-1)">-</button><input type="number" id="qaa" value="1" min="1"><button class="pl" onclick="qAdj('${i.id}',1)">+</button><select id="qar" style="padding:6px;border-radius:6px;border:1px solid var(--line);background:var(--paper);color:var(--text);font-size:13px"><option value="sold">Sold</option><option value="received">Received</option><option value="adjusted">Adjusted</option><option value="damaged">Damaged</option><option value="returned">Returned</option></select></div>`}
async function qAdj(id,dir){const amt=parseInt(document.getElementById('qaa').value)||1;const r=await apiCall('POST',`/api/inventory/${id}/adjust`,{quantity_change:dir*amt,reason:document.getElementById('qar').value,notes:'Quick adjust from scanner'});if(!r.ok){alert(r.data.error);return}renderRes(r.data.item)}
function addHist(code,found){hist.unshift({code,found,time:new Date().toLocaleTimeString()});if(hist.length>50)hist.pop();document.getElementById('sh').innerHTML=hist.map(h=>`<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--line)"><span><code>${esc(h.code)}</code></span><span style="font-size:12px;color:var(--muted)">${h.time} <span class="badge ${h.found?'bg':'br'}">${h.found?'Found':'Not Found'}</span></span></div>`).join('')}
async function toggleCam(){if(scanning){stopCam();return}try{const devs=await navigator.mediaDevices.enumerateDevices();const cams=devs.filter(d=>d.kind==='videoinput');const sel=document.getElementById('csel');sel.innerHTML=cams.map((c,i)=>`<option value="${c.deviceId}">${c.label||'Camera '+(i+1)}</option>`).join('');await startCam(cams[0]?.deviceId)}catch(e){document.getElementById('sstat').textContent='Camera denied: '+e.message}}
async function startCam(did){const c={video:{deviceId:did?{exact:did}:undefined,facingMode:'environment',width:{ideal:1280},height:{ideal:720}}};stream=await navigator.mediaDevices.getUserMedia(c);document.getElementById('vid').srcObject=stream;scanning=true;document.getElementById('cbtn').textContent='Stop Camera';document.getElementById('sline').style.display='block';const ph=document.getElementById('cam-placeholder');if(ph)ph.style.display='none';document.getElementById('sstat').textContent='Camera active — scanning...';scanLoop()}
function stopCam(){scanning=false;if(stream){stream.getTracks().forEach(t=>t.stop());stream=null}document.getElementById('vid').srcObject=null;document.getElementById('cbtn').textContent='Start Camera';document.getElementById('sline').style.display='none';const ph=document.getElementById('cam-placeholder');if(ph)ph.style.display='flex';document.getElementById('sstat').textContent='Camera stopped'}
async function scanLoop(){if(!scanning)return;const v=document.getElementById('vid'),c=document.getElementById('cvs');if(v.readyState===v.HAVE_ENOUGH_DATA){c.width=v.videoWidth;c.height=v.videoHeight;c.getContext('2d').drawImage(v,0,0);if('BarcodeDetector' in window){try{const det=new BarcodeDetector();const bc=await det.detect(c);if(bc.length>0&&bc[0].rawValue)lookup(bc[0].rawValue)}catch(e){}}}setTimeout(scanLoop,500)}
document.getElementById('csel').addEventListener('change',async e=>{if(scanning){stopCam();await startCam(e.target.value)}});
</script>"""

    return HTMLResponse(content=render_shell(
        title="Scan",
        active_nav="scan",
        body_html=body,
        body_js=js,
        display_name=user.display_name,
        role=user.role,
    ))
