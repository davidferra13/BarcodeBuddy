"""Inventory HTML page routes: list, detail, create, import, scan."""

from __future__ import annotations

import html as html_mod

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from app.auth import require_user
from app.database import User

router = APIRouter(tags=["inventory-pages"])

_E = html_mod.escape

# ── Shared Styles ───────────────────────────────────────────────────

_CSS = """<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f172a;color:#e2e8f0}
.page{max-width:1200px;margin:0 auto;padding:24px}
.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;flex-wrap:wrap;gap:12px}
.topbar h1{font-size:22px;color:#f8fafc}
.actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
a{color:#60a5fa;text-decoration:none}a:hover{text-decoration:underline}
.btn{padding:8px 16px;border-radius:8px;border:none;font-size:13px;font-weight:600;cursor:pointer;transition:all .2s;display:inline-flex;align-items:center;gap:6px;text-decoration:none}
.btn-primary{background:#3b82f6;color:#fff}.btn-primary:hover{background:#2563eb}
.btn-secondary{background:#334155;color:#e2e8f0}.btn-secondary:hover{background:#475569}
.btn-success{background:#059669;color:#fff}.btn-success:hover{background:#047857}
.btn-danger{background:#dc2626;color:#fff}.btn-danger:hover{background:#b91c1c}
.btn-sm{padding:5px 10px;font-size:12px}
.card{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:16px}
.fg{margin-bottom:14px}.fg label{display:block;font-size:12px;font-weight:600;color:#94a3b8;margin-bottom:4px;text-transform:uppercase;letter-spacing:.5px}
.fg input,.fg select,.fg textarea{width:100%;padding:8px 12px;border-radius:6px;border:1px solid #334155;background:#0f172a;color:#f8fafc;font-size:14px}
.fg input:focus,.fg select:focus,.fg textarea:focus{border-color:#3b82f6;outline:none}
.fr{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.fr3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}
table{width:100%;border-collapse:collapse}
th{text-align:left;font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:.5px;padding:8px 10px;border-bottom:1px solid #334155}
td{padding:10px;border-bottom:1px solid rgba(51,65,85,.5);font-size:13px}
tr:hover td{background:rgba(15,23,42,.5)}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600}
.bg{background:#05966933;color:#4ade80}.by{background:#d9770633;color:#fbbf24}.br{background:#dc262633;color:#f87171}.bb{background:#3b82f633;color:#93c5fd}.bgr{background:#33415533;color:#94a3b8}
.search-bar{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap}
.search-bar input{flex:1;min-width:200px;padding:8px 14px;border-radius:8px;border:1px solid #334155;background:#1e293b;color:#f8fafc;font-size:14px}
.search-bar input:focus{border-color:#3b82f6;outline:none}
.sr{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:20px}
.sb{background:#1e293b;border-radius:8px;padding:14px;text-align:center}
.sb .v{font-size:24px;font-weight:700;color:#f8fafc}.sb .l{font-size:11px;color:#64748b;text-transform:uppercase;margin-top:2px}
.err{background:#450a0a;color:#fca5a5;padding:10px 14px;border-radius:8px;font-size:13px;margin-bottom:12px;display:none}
.suc{background:#052e16;color:#86efac;padding:10px 14px;border-radius:8px;font-size:13px;margin-bottom:12px;display:none}
.empty{text-align:center;padding:40px;color:#64748b}
.nb{font-size:13px;color:#94a3b8;margin-bottom:16px;display:inline-block}.nb:hover{color:#f8fafc}
.ql{color:#fbbf24}.qz{color:#f87171}
.bp{background:#fff;padding:12px;border-radius:8px;display:inline-block;margin:8px 0}
@media(max-width:640px){.fr,.fr3{grid-template-columns:1fr}.page{padding:12px}}
</style>"""

_JS = """<script>
async function apiCall(m,u,b){const o={method:m,headers:{'Content-Type':'application/json'}};if(b)o.body=JSON.stringify(b);const r=await fetch(u,o);return{ok:r.ok,status:r.status,data:await r.json()}}
function showErr(m){const e=document.getElementById('err');if(e){e.textContent=m;e.style.display='block'}}
function showSuc(m){const e=document.getElementById('suc');if(e){e.textContent=m;e.style.display='block'}}
function hideMsg(){document.querySelectorAll('.err,.suc').forEach(e=>e.style.display='none')}
function esc(s){if(!s)return'';const d=document.createElement('div');d.textContent=s;return d.innerHTML}
</script>"""


# ── Inventory List ──────────────────────────────────────────────────

@router.get("/inventory", response_class=HTMLResponse)
def inventory_list_page(user: User = Depends(require_user)) -> HTMLResponse:
    return HTMLResponse(content=f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inventory - Barcode Buddy</title>{_CSS}</head><body>
<div class="page">
  <div class="topbar">
    <h1>Inventory</h1>
    <div class="actions">
      <a href="/scan" class="btn btn-success">Scan</a>
      <a href="/inventory/new" class="btn btn-primary">+ New Item</a>
      <a href="/inventory/import" class="btn btn-secondary">Import CSV</a>
      <a href="/api/inventory/export/csv" class="btn btn-secondary">Export CSV</a>
      <a href="/" class="btn btn-secondary">Dashboard</a>
    </div>
  </div>
  <div class="sr" id="sr"></div>
  <div class="search-bar">
    <input type="text" id="q" placeholder="Search by name, SKU, barcode, location..." autofocus>
    <select id="cf" style="padding:8px;border-radius:8px;border:1px solid #334155;background:#1e293b;color:#f8fafc;"><option value="">All Categories</option></select>
  </div>
  <div class="card" style="padding:0;overflow-x:auto;">
    <table><thead><tr><th>Name</th><th>SKU</th><th>Qty</th><th>Location</th><th>Category</th><th>Barcode</th><th>Status</th><th></th></tr></thead>
    <tbody id="tb"><tr><td colspan="8" class="empty">Loading...</td></tr></tbody></table>
  </div>
</div>
{_JS}
<script>
let all=[];
async function load(){{const[ir,cr]=await Promise.all([fetch('/api/inventory?limit=1000').then(r=>r.json()),fetch('/api/inventory/categories').then(r=>r.json())]);all=ir.items;renderS(all);renderI(all);const s=document.getElementById('cf');cr.categories.forEach(c=>{{const o=document.createElement('option');o.value=c;o.textContent=c;s.appendChild(o)}})}}
function renderS(items){{const a=items.filter(i=>i.status==='active'),tq=a.reduce((s,i)=>s+i.quantity,0),ls=a.filter(i=>i.min_quantity>0&&i.quantity<=i.min_quantity).length,zs=a.filter(i=>i.quantity===0).length,cs=new Set(a.map(i=>i.category).filter(Boolean));document.getElementById('sr').innerHTML=`<div class="sb"><div class="v">${{a.length}}</div><div class="l">Items</div></div><div class="sb"><div class="v">${{tq.toLocaleString()}}</div><div class="l">Total Units</div></div><div class="sb"><div class="v">${{cs.size}}</div><div class="l">Categories</div></div><div class="sb"><div class="v" style="color:${{ls?'#fbbf24':'#4ade80'}}">${{ls}}</div><div class="l">Low Stock</div></div><div class="sb"><div class="v" style="color:${{zs?'#f87171':'#4ade80'}}">${{zs}}</div><div class="l">Out of Stock</div></div>`}}
function renderI(items){{const tb=document.getElementById('tb');if(!items.length){{tb.innerHTML='<tr><td colspan="8" class="empty">No items found. <a href="/inventory/new">Create one</a></td></tr>';return}}tb.innerHTML=items.map(i=>`<tr style="cursor:pointer" onclick="location='/inventory/${{i.id}}'"><td><strong>${{esc(i.name)}}</strong></td><td><code style="color:#94a3b8">${{esc(i.sku)}}</code></td><td class="${{i.quantity===0?'qz':i.min_quantity>0&&i.quantity<=i.min_quantity?'ql':''}}">${{i.quantity}} ${{esc(i.unit)}}</td><td>${{esc(i.location)||'<span style="color:#475569">-</span>'}}</td><td>${{i.category?`<span class="badge bb">${{esc(i.category)}}</span>`:''}}</td><td><code style="font-size:11px;color:#64748b">${{esc(i.barcode_value)}}</code></td><td><span class="badge ${{i.status==='active'?'bg':'bgr'}}">${{i.status}}</span></td><td><a href="/inventory/${{i.id}}" class="btn btn-sm btn-secondary" onclick="event.stopPropagation()">View</a></td></tr>`).join('')}}
document.getElementById('q').addEventListener('input',filt);document.getElementById('cf').addEventListener('change',filt);
function filt(){{const q=document.getElementById('q').value.toLowerCase(),c=document.getElementById('cf').value;let f=all;if(q)f=f.filter(i=>i.name.toLowerCase().includes(q)||i.sku.toLowerCase().includes(q)||i.barcode_value.toLowerCase().includes(q)||(i.location||'').toLowerCase().includes(q)||(i.tags||'').toLowerCase().includes(q));if(c)f=f.filter(i=>i.category===c);renderI(f)}}
load();
</script></body></html>""")


# ── Create Item ─────────────────────────────────────────────────────

@router.get("/inventory/new", response_class=HTMLResponse)
def inventory_create_page(user: User = Depends(require_user)) -> HTMLResponse:
    return HTMLResponse(content=f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>New Item - Barcode Buddy</title>{_CSS}</head><body>
<div class="page">
  <a href="/inventory" class="nb">&larr; Back to Inventory</a>
  <h1 style="margin-bottom:20px;color:#f8fafc">Create New Item</h1>
  <div id="err" class="err"></div>
  <div class="card">
    <form id="cf" onsubmit="return cI(event)">
      <div class="fr"><div class="fg"><label>Name *</label><input type="text" id="name" required autofocus></div><div class="fg"><label>SKU *</label><input type="text" id="sku" required placeholder="e.g. WIDGET-001"></div></div>
      <div class="fg"><label>Description</label><textarea id="description" rows="2"></textarea></div>
      <div class="fr3"><div class="fg"><label>Quantity</label><input type="number" id="quantity" value="0" min="0"></div><div class="fg"><label>Unit</label><input type="text" id="unit" value="each"></div><div class="fg"><label>Min Qty (alert)</label><input type="number" id="min_quantity" value="0" min="0"></div></div>
      <div class="fr"><div class="fg"><label>Location</label><input type="text" id="location" placeholder="Warehouse A, Shelf B3"></div><div class="fg"><label>Category</label><input type="text" id="category" placeholder="Raw Materials"></div></div>
      <div class="fr"><div class="fg"><label>Cost per unit</label><input type="number" id="cost" step="0.01" min="0"></div><div class="fg"><label>Tags (comma-separated)</label><input type="text" id="tags"></div></div>
      <div class="fr"><div class="fg"><label>Barcode Type</label><select id="barcode_type"><option value="Code128" selected>Code 128</option><option value="QRCode">QR Code</option><option value="EAN13">EAN-13</option><option value="Code39">Code 39</option><option value="DataMatrix">Data Matrix</option></select></div><div class="fg"><label>Barcode Value (auto if empty)</label><input type="text" id="barcode_value"></div></div>
      <div class="fg"><label>Notes</label><textarea id="notes" rows="2"></textarea></div>
      <div style="margin-top:16px;display:flex;gap:10px"><button type="submit" class="btn btn-primary">Create Item</button><a href="/inventory" class="btn btn-secondary">Cancel</a></div>
    </form>
  </div>
</div>
{_JS}
<script>
async function cI(e){{e.preventDefault();hideMsg();const b={{}};['name','sku','description','quantity','unit','location','category','tags','notes','barcode_type','barcode_value','min_quantity','cost'].forEach(f=>{{let v=document.getElementById(f).value;if(f==='quantity'||f==='min_quantity')v=parseInt(v)||0;else if(f==='cost')v=v?parseFloat(v):null;b[f]=v}});const r=await apiCall('POST','/api/inventory',b);if(!r.ok){{showErr(r.data.error||'Failed');return false}}location.href='/inventory/'+r.data.item.id;return false}}
</script></body></html>""")


# ── Import CSV ──────────────────────────────────────────────────────

@router.get("/inventory/import", response_class=HTMLResponse)
def inventory_import_page(user: User = Depends(require_user)) -> HTMLResponse:
    return HTMLResponse(content=f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Import - Barcode Buddy</title>{_CSS}</head><body>
<div class="page">
  <a href="/inventory" class="nb">&larr; Back to Inventory</a>
  <h1 style="margin-bottom:20px;color:#f8fafc">Import Inventory from CSV</h1>
  <div id="err" class="err"></div><div id="suc" class="suc"></div>
  <div class="card">
    <p style="color:#94a3b8;margin-bottom:16px">CSV columns: <code>name, sku, description, quantity, unit, location, category, tags, notes, barcode_value, barcode_type, min_quantity, cost</code></p>
    <p style="color:#94a3b8;margin-bottom:16px">Existing SKUs update. New SKUs create. Barcodes auto-generated if blank.</p>
    <form onsubmit="return doImport(event)">
      <div class="fg"><label>CSV File</label><input type="file" id="csvf" accept=".csv" required style="padding:8px"></div>
      <button type="submit" class="btn btn-primary" id="ibtn">Import</button>
    </form>
    <div id="res" style="margin-top:16px;display:none"></div>
  </div>
  <div class="card" style="margin-top:16px"><h3 style="color:#f8fafc;margin-bottom:8px">Template</h3><a href="/api/inventory/export/csv" class="btn btn-secondary">Download CSV Template / Export</a></div>
</div>
{_JS}
<script>
async function doImport(e){{e.preventDefault();hideMsg();const f=document.getElementById('csvf').files[0];if(!f){{showErr('Select a file');return false}}document.getElementById('ibtn').disabled=true;const fd=new FormData();fd.append('file',f);try{{const r=await fetch('/api/inventory/import/csv',{{method:'POST',body:fd}});const d=await r.json();if(!r.ok){{showErr(d.error||'Import failed');document.getElementById('ibtn').disabled=false;return false}}showSuc(d.message);const res=document.getElementById('res');res.style.display='block';let h=`<p style="color:#4ade80">${{d.created}} created, ${{d.updated}} updated</p>`;if(d.errors.length)h+=`<div style="margin-top:8px;color:#fca5a5">${{d.errors.map(e=>'<div>'+e+'</div>').join('')}}</div>`;res.innerHTML=h}}catch(er){{showErr('Network error')}}document.getElementById('ibtn').disabled=false;return false}}
</script></body></html>""")


# ── Item Detail ─────────────────────────────────────────────────────

@router.get("/inventory/{item_id}", response_class=HTMLResponse)
def inventory_detail_page(item_id: str, user: User = Depends(require_user)) -> HTMLResponse:
    safe_id = _E(item_id)
    return HTMLResponse(content=f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Item - Barcode Buddy</title>{_CSS}</head><body>
<div class="page">
  <a href="/inventory" class="nb">&larr; Back to Inventory</a>
  <div id="err" class="err"></div><div id="suc" class="suc"></div>
  <div id="ld" class="empty">Loading...</div>
  <div id="ct" style="display:none">
    <div class="topbar"><div><h1 id="iname" style="color:#f8fafc"></h1><code id="isku" style="color:#94a3b8"></code></div>
      <div class="actions"><button class="btn btn-success" onclick="showAdj()">Adjust Qty</button><button class="btn btn-secondary" onclick="toggleEdit()">Edit</button><button class="btn btn-danger" onclick="delItem()">Delete</button></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 300px;gap:20px;align-items:start" id="mg">
      <div>
        <div class="card" id="dc"></div>
        <div class="card" id="ec" style="display:none"></div>
        <div class="card" id="ac" style="display:none">
          <h3 style="color:#f8fafc;margin-bottom:12px">Adjust Quantity</h3>
          <div class="fr3">
            <div class="fg"><label>Change (+/-)</label><input type="number" id="aq" value="0"></div>
            <div class="fg"><label>Reason</label><select id="ar"><option value="received">Received</option><option value="sold">Sold</option><option value="adjusted">Adjusted</option><option value="damaged">Damaged</option><option value="returned">Returned</option></select></div>
            <div class="fg"><label>Notes</label><input type="text" id="an"></div>
          </div>
          <button class="btn btn-success" onclick="doAdj()">Apply</button>
          <button class="btn btn-secondary" onclick="document.getElementById('ac').style.display='none'">Cancel</button>
        </div>
        <div class="card"><h3 style="color:#f8fafc;margin-bottom:12px">Transaction History</h3>
          <table><thead><tr><th>Date</th><th>Change</th><th>After</th><th>Reason</th><th>Notes</th></tr></thead><tbody id="txb"></tbody></table>
        </div>
      </div>
      <div><div class="card" style="text-align:center">
        <h3 style="color:#f8fafc;margin-bottom:8px">Barcode</h3>
        <div class="bp"><img id="bimg" alt="barcode"></div>
        <div style="margin-top:8px"><code id="bval" style="color:#94a3b8;font-size:12px"></code></div>
        <div style="margin-top:12px;display:flex;gap:8px;justify-content:center;flex-wrap:wrap">
          <a id="bdl" class="btn btn-sm btn-secondary" download>Download</a>
          <button class="btn btn-sm btn-secondary" onclick="printBC()">Print</button>
        </div>
      </div></div>
    </div>
  </div>
</div>
{_JS}
<script>
const ID='{safe_id}';let cur=null;
async function load(){{const r=await apiCall('GET',`/api/inventory/${{ID}}`);if(!r.ok){{showErr('Item not found');return}}cur=r.data.item;document.getElementById('ld').style.display='none';document.getElementById('ct').style.display='block';renderD(r.data.item,r.data.transactions)}}
function renderD(i,tx){{document.getElementById('iname').textContent=i.name;document.getElementById('isku').textContent=i.sku;document.title=i.name+' - Barcode Buddy';const bu=`/api/inventory/${{i.id}}/barcode.png?scale=5`;document.getElementById('bimg').src=bu;document.getElementById('bval').textContent=i.barcode_value;document.getElementById('bdl').href=bu;
const qc=i.quantity===0?'qz':i.min_quantity>0&&i.quantity<=i.min_quantity?'ql':'';
document.getElementById('dc').innerHTML=`<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px"><div><div style="font-size:11px;color:#64748b;text-transform:uppercase">Quantity</div><div style="font-size:28px;font-weight:700" class="${{qc}}">${{i.quantity}} <span style="font-size:14px;color:#94a3b8">${{esc(i.unit)}}</span></div></div><div><div style="font-size:11px;color:#64748b;text-transform:uppercase">Location</div><div style="font-size:16px;color:#f8fafc">${{esc(i.location)||'—'}}</div></div><div><div style="font-size:11px;color:#64748b;text-transform:uppercase">Category</div><div>${{i.category?'<span class="badge bb">'+esc(i.category)+'</span>':'—'}}</div></div><div><div style="font-size:11px;color:#64748b;text-transform:uppercase">Status</div><div><span class="badge ${{i.status==='active'?'bg':'bgr'}}">${{i.status}}</span></div></div><div><div style="font-size:11px;color:#64748b;text-transform:uppercase">Cost</div><div style="color:#f8fafc">${{i.cost!=null?'$'+i.cost.toFixed(2):'—'}}</div></div><div><div style="font-size:11px;color:#64748b;text-transform:uppercase">Min Qty</div><div style="color:#f8fafc">${{i.min_quantity}}</div></div></div>${{i.description?'<div style="margin-top:16px"><div style="font-size:11px;color:#64748b;text-transform:uppercase;margin-bottom:4px">Description</div><div style="color:#e2e8f0">'+esc(i.description)+'</div></div>':''}}${{i.tags?'<div style="margin-top:12px"><div style="font-size:11px;color:#64748b;text-transform:uppercase;margin-bottom:4px">Tags</div><div>'+i.tags.split(',').map(t=>'<span class="badge bgr" style="margin:2px">'+esc(t.trim())+'</span>').join('')+'</div></div>':''}}${{i.notes?'<div style="margin-top:12px"><div style="font-size:11px;color:#64748b;text-transform:uppercase;margin-bottom:4px">Notes</div><div style="color:#94a3b8">'+esc(i.notes)+'</div></div>':''}}<div style="margin-top:16px;font-size:11px;color:#475569">Created: ${{new Date(i.created_at).toLocaleString()}} · Updated: ${{new Date(i.updated_at).toLocaleString()}}</div>`;
document.getElementById('txb').innerHTML=tx.length?tx.map(t=>`<tr><td style="white-space:nowrap">${{new Date(t.created_at).toLocaleString()}}</td><td style="font-weight:600;color:${{t.quantity_change>=0?'#4ade80':'#f87171'}}">${{t.quantity_change>=0?'+':''}}\u200b${{t.quantity_change}}</td><td>${{t.quantity_after}}</td><td><span class="badge bgr">${{esc(t.reason)}}</span></td><td style="color:#94a3b8">${{esc(t.notes)}}</td></tr>`).join(''):'<tr><td colspan="5" class="empty">No transactions yet</td></tr>'}}
function showAdj(){{document.getElementById('ac').style.display='block';document.getElementById('aq').focus()}}
async function doAdj(){{hideMsg();const q=parseInt(document.getElementById('aq').value);if(!q){{showErr('Enter a non-zero quantity');return}}const r=await apiCall('POST',`/api/inventory/${{ID}}/adjust`,{{quantity_change:q,reason:document.getElementById('ar').value,notes:document.getElementById('an').value}});if(!r.ok){{showErr(r.data.error);return}}document.getElementById('ac').style.display='none';document.getElementById('aq').value='0';document.getElementById('an').value='';showSuc('Quantity adjusted');load()}}
function toggleEdit(){{const c=document.getElementById('ec');if(c.style.display==='none'){{const i=cur;c.style.display='block';c.innerHTML=`<h3 style="color:#f8fafc;margin-bottom:12px">Edit Item</h3><div class="fr"><div class="fg"><label>Name</label><input type="text" id="en" value="${{esc(i.name)}}"></div><div class="fg"><label>SKU</label><input type="text" id="es" value="${{esc(i.sku)}}"></div></div><div class="fg"><label>Description</label><textarea id="ed" rows="2">${{esc(i.description)}}</textarea></div><div class="fr3"><div class="fg"><label>Quantity</label><input type="number" id="eq" value="${{i.quantity}}" min="0"></div><div class="fg"><label>Unit</label><input type="text" id="eu" value="${{esc(i.unit)}}"></div><div class="fg"><label>Min Qty</label><input type="number" id="em" value="${{i.min_quantity}}" min="0"></div></div><div class="fr"><div class="fg"><label>Location</label><input type="text" id="el" value="${{esc(i.location)}}"></div><div class="fg"><label>Category</label><input type="text" id="ecat" value="${{esc(i.category)}}"></div></div><div class="fr"><div class="fg"><label>Cost</label><input type="number" id="ec2" step="0.01" value="${{i.cost||''}}"></div><div class="fg"><label>Tags</label><input type="text" id="et" value="${{esc(i.tags)}}"></div></div><div class="fr"><div class="fg"><label>Notes</label><textarea id="eno" rows="2">${{esc(i.notes)}}</textarea></div><div class="fg"><label>Status</label><select id="est"><option value="active" ${{i.status==='active'?'selected':''}}>Active</option><option value="archived" ${{i.status==='archived'?'selected':''}}>Archived</option></select></div></div><div style="margin-top:12px;display:flex;gap:8px"><button class="btn btn-primary" onclick="saveE()">Save</button><button class="btn btn-secondary" onclick="document.getElementById('ec').style.display='none'">Cancel</button></div>`}}else c.style.display='none'}}
async function saveE(){{hideMsg();const b={{name:document.getElementById('en').value,sku:document.getElementById('es').value,description:document.getElementById('ed').value,unit:document.getElementById('eu').value,location:document.getElementById('el').value,category:document.getElementById('ecat').value,tags:document.getElementById('et').value,notes:document.getElementById('eno').value,status:document.getElementById('est').value,quantity:parseInt(document.getElementById('eq').value)||0,min_quantity:parseInt(document.getElementById('em').value)||0}};const cv=document.getElementById('ec2').value;b.cost=cv?parseFloat(cv):null;const r=await apiCall('PUT',`/api/inventory/${{ID}}`,b);if(!r.ok){{showErr(r.data.error);return}}document.getElementById('ec').style.display='none';showSuc('Item updated');load()}}
async function delItem(){{if(!confirm('Delete this item permanently?'))return;const r=await apiCall('DELETE',`/api/inventory/${{ID}}`);if(!r.ok){{showErr(r.data.error);return}}location.href='/inventory'}}
function printBC(){{const img=document.getElementById('bimg');const w=window.open('','','width=400,height=300');w.document.write(`<html><body style="text-align:center;padding:20px"><img src="${{img.src}}" style="max-width:100%"><br><strong>${{esc(cur.name)}}</strong><br><code>${{esc(cur.barcode_value)}}</code><br><code>${{esc(cur.sku)}}</code></body></html>`);w.document.close();w.onload=()=>w.print()}}
load();
</script></body></html>""")


# ── Scan Page ───────────────────────────────────────────────────────

@router.get("/scan", response_class=HTMLResponse)
def scan_page(user: User = Depends(require_user)) -> HTMLResponse:
    return HTMLResponse(content=f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Scan - Barcode Buddy</title>{_CSS}
<style>
.sa{{display:grid;grid-template-columns:1fr 1fr;gap:20px;align-items:start}}
.cb{{background:#000;border-radius:10px;overflow:hidden;position:relative;min-height:300px}}
.cb video{{width:100%;display:block}}.cb canvas{{display:none}}
.sl{{position:absolute;left:10%;right:10%;height:2px;background:#3b82f6;box-shadow:0 0 12px #3b82f6;animation:sm 2s ease-in-out infinite}}
@keyframes sm{{0%,100%{{top:20%}}50%{{top:80%}}}}
.qa{{display:flex;gap:8px;align-items:center;margin-top:12px}}
.qa button{{width:40px;height:40px;border-radius:8px;border:none;font-size:18px;font-weight:700;cursor:pointer}}
.qa .mn{{background:#dc2626;color:#fff}}.qa .pl{{background:#059669;color:#fff}}
.qa input{{width:60px;text-align:center;font-size:18px;font-weight:700;background:#0f172a;border:1px solid #334155;border-radius:8px;color:#f8fafc;padding:6px}}
@media(max-width:768px){{.sa{{grid-template-columns:1fr}}}}
</style></head><body>
<div class="page">
  <div class="topbar"><h1>Scan</h1><div class="actions"><a href="/inventory" class="btn btn-secondary">Inventory</a><a href="/" class="btn btn-secondary">Dashboard</a></div></div>
  <div class="search-bar">
    <input type="text" id="mi" placeholder="Type or scan barcode value..." autofocus style="font-size:18px;padding:12px 16px">
    <button class="btn btn-primary" onclick="lookup()" style="font-size:16px;padding:12px 20px">Lookup</button>
  </div>
  <div class="sa">
    <div>
      <div class="cb" id="cbox">
        <video id="vid" autoplay playsinline></video><canvas id="cvs"></canvas>
        <div class="sl" id="sline" style="display:none"></div>
        <div style="position:absolute;bottom:10px;left:10px;right:10px;display:flex;gap:8px">
          <button class="btn btn-primary btn-sm" id="cbtn" onclick="toggleCam()">Start Camera</button>
          <select id="csel" style="flex:1;padding:6px;border-radius:6px;border:1px solid #334155;background:#1e293b;color:#f8fafc;font-size:12px"></select>
        </div>
      </div>
      <div id="sstat" style="margin-top:8px;font-size:13px;color:#64748b;text-align:center">Enter a barcode or start camera</div>
    </div>
    <div>
      <div id="nr" class="card empty">Scan or enter a barcode to look up an item</div>
      <div id="rc" class="card" style="display:none"></div>
      <div id="nf" class="card" style="display:none">
        <div style="text-align:center;padding:20px">
          <div style="font-size:48px;margin-bottom:8px">?</div>
          <div style="font-size:16px;color:#f87171;font-weight:600">Item Not Found</div>
          <div style="color:#94a3b8;margin:8px 0" id="nfc"></div>
          <a id="cl" href="/inventory/new" class="btn btn-primary">Create New Item</a>
        </div>
      </div>
    </div>
  </div>
  <div class="card" style="margin-top:20px"><h3 style="color:#f8fafc;margin-bottom:8px">Scan History</h3><div id="sh" style="max-height:200px;overflow-y:auto"><span class="empty" style="display:block;padding:12px">No scans yet</span></div></div>
</div>
{_JS}
<script>
let scanning=false,stream=null,hist=[],lastCode='',lastTime=0;
document.getElementById('mi').addEventListener('keydown',e=>{{if(e.key==='Enter')lookup()}});
async function lookup(code){{const inp=document.getElementById('mi');code=code||inp.value.trim();if(!code)return;inp.value=code;const now=Date.now();if(code===lastCode&&now-lastTime<2000)return;lastCode=code;lastTime=now;document.getElementById('nr').style.display='none';document.getElementById('nf').style.display='none';document.getElementById('rc').style.display='none';const r=await apiCall('GET','/api/scan/lookup?code='+encodeURIComponent(code));addHist(code,r.ok);if(!r.ok){{document.getElementById('nf').style.display='block';document.getElementById('nfc').textContent='Code: '+code;document.getElementById('cl').href='/inventory/new?sku='+encodeURIComponent(code);return}}renderRes(r.data.item)}}
function renderRes(i){{const c=document.getElementById('rc');c.style.display='block';const qc=i.quantity===0?'qz':i.min_quantity>0&&i.quantity<=i.min_quantity?'ql':'';c.innerHTML=`<div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:16px"><div><h2 style="color:#f8fafc;font-size:20px">${{esc(i.name)}}</h2><code style="color:#94a3b8">${{esc(i.sku)}}</code></div><a href="/inventory/${{i.id}}" class="btn btn-sm btn-secondary">Full Detail</a></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px"><div><span style="font-size:11px;color:#64748b;text-transform:uppercase">Quantity</span><div style="font-size:28px;font-weight:700" class="${{qc}}">${{i.quantity}} <span style="font-size:14px;color:#94a3b8">${{esc(i.unit)}}</span></div></div><div><span style="font-size:11px;color:#64748b;text-transform:uppercase">Location</span><div style="font-size:16px;color:#f8fafc">${{esc(i.location)||'—'}}</div></div></div>${{i.category?'<span class="badge bb">'+esc(i.category)+'</span>':''}}${{i.description?'<p style="color:#94a3b8;margin-top:8px;font-size:13px">'+esc(i.description)+'</p>':''}}<div class="qa"><span style="font-size:13px;color:#94a3b8">Quick adjust:</span><button class="mn" onclick="qAdj('${{i.id}}',-1)">-</button><input type="number" id="qaa" value="1" min="1"><button class="pl" onclick="qAdj('${{i.id}}',1)">+</button><select id="qar" style="padding:6px;border-radius:6px;border:1px solid #334155;background:#0f172a;color:#f8fafc;font-size:13px"><option value="sold">Sold</option><option value="received">Received</option><option value="adjusted">Adjusted</option><option value="damaged">Damaged</option><option value="returned">Returned</option></select></div>`}}
async function qAdj(id,dir){{const amt=parseInt(document.getElementById('qaa').value)||1;const r=await apiCall('POST',`/api/inventory/${{id}}/adjust`,{{quantity_change:dir*amt,reason:document.getElementById('qar').value,notes:'Quick adjust from scanner'}});if(!r.ok){{alert(r.data.error);return}}renderRes(r.data.item)}}
function addHist(code,found){{hist.unshift({{code,found,time:new Date().toLocaleTimeString()}});if(hist.length>50)hist.pop();document.getElementById('sh').innerHTML=hist.map(h=>`<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #1e293b"><span><code style="color:#e2e8f0">${{esc(h.code)}}</code></span><span style="font-size:12px;color:#64748b">${{h.time}} <span class="badge ${{h.found?'bg':'br'}}">${{h.found?'Found':'Not Found'}}</span></span></div>`).join('')}}
async function toggleCam(){{if(scanning){{stopCam();return}}try{{const devs=await navigator.mediaDevices.enumerateDevices();const cams=devs.filter(d=>d.kind==='videoinput');const sel=document.getElementById('csel');sel.innerHTML=cams.map((c,i)=>`<option value="${{c.deviceId}}">${{c.label||'Camera '+(i+1)}}</option>`).join('');await startCam(cams[0]?.deviceId)}}catch(e){{document.getElementById('sstat').textContent='Camera denied: '+e.message}}}}
async function startCam(did){{const c={{video:{{deviceId:did?{{exact:did}}:undefined,facingMode:'environment',width:{{ideal:1280}},height:{{ideal:720}}}}}};stream=await navigator.mediaDevices.getUserMedia(c);document.getElementById('vid').srcObject=stream;scanning=true;document.getElementById('cbtn').textContent='Stop Camera';document.getElementById('sline').style.display='block';document.getElementById('sstat').textContent='Camera active — scanning...';scanLoop()}}
function stopCam(){{scanning=false;if(stream){{stream.getTracks().forEach(t=>t.stop());stream=null}}document.getElementById('vid').srcObject=null;document.getElementById('cbtn').textContent='Start Camera';document.getElementById('sline').style.display='none';document.getElementById('sstat').textContent='Camera stopped'}}
async function scanLoop(){{if(!scanning)return;const v=document.getElementById('vid'),c=document.getElementById('cvs');if(v.readyState===v.HAVE_ENOUGH_DATA){{c.width=v.videoWidth;c.height=v.videoHeight;c.getContext('2d').drawImage(v,0,0);if('BarcodeDetector' in window){{try{{const det=new BarcodeDetector();const bc=await det.detect(c);if(bc.length>0&&bc[0].rawValue)lookup(bc[0].rawValue)}}catch(e){{}}}}}}setTimeout(scanLoop,500)}}
document.getElementById('csel').addEventListener('change',async e=>{{if(scanning){{stopCam();await startCam(e.target.value)}}}});
</script></body></html>""")
