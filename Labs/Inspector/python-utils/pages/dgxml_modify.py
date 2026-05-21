# -*- coding: utf-8 -*-
"""DGServer.xml Parameter Modify - modal panel + API endpoints."""
import os
import re
import json
import shutil
import time

from service_config import load_service_config
from system_utils import _xml_val, _read_lines

try:
    from html_helpers import _UTILS_BASE
except Exception:
    _UTILS_BASE = ""


def _parse_all_params():
    """Return list of (name, xmlfile, safe_id, [(is_disabled, key, val), ...], error)."""
    svc = load_service_config()
    services = svc.get("services", {})
    homes = []
    dgm = services.get("dgserver_m", "")
    if dgm:
        homes.append(("DGServer_M", dgm))
    for i, dgs in enumerate(services.get("dgserver_s", [])):
        if dgs:
            homes.append(("DGServer_S" + str(i + 1), dgs))
    if not homes:
        return []

    # Allow optional attributes in opening tag, e.g. <database_sid service="false">PGN</database_sid>
    RE_PARAM = re.compile(r"<(\w+)(?:\s[^>]*)?>([^<]+)</\1>")
    result = []
    for name, home in homes:
        xmlfile = os.path.join(home, "conf", "DGServer.xml")
        safe_id = re.sub(r'[^a-z0-9]', '', name.lower())
        if not os.path.exists(xmlfile):
            result.append((name, xmlfile, safe_id, [], "File not found"))
            continue
        try:
            lines = _read_lines(xmlfile)
            parsed = []
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                m = RE_PARAM.search(stripped)
                if m:
                    comment_pos = stripped.find("<!--")
                    is_disabled = (comment_pos >= 0 and comment_pos < m.start())
                    parsed.append((is_disabled, m.group(1), m.group(2)))
            result.append((name, xmlfile, safe_id, parsed, None))
        except Exception as e:
            result.append((name, xmlfile, safe_id, [], str(e)))
    return result


def modify_panel_html():
    """Return the Modify Parameter modal panel HTML + JS."""
    all_data = _parse_all_params()
    all_params = set()
    for name, xmlfile, safe_id, parsed, error in all_data:
        for is_disabled, key, val in parsed:
            all_params.add(key)
    params_json = json.dumps(sorted(all_params), ensure_ascii=False)

    html = (
        '<style>'
        '#modify-panel{display:none;position:fixed;inset:0;z-index:9999;'
        'background:rgba(15,15,30,.45);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);'
        'align-items:center;justify-content:center;padding:24px;}'
        '.mp-modal{background:#fff;border-radius:16px;width:100%;max-width:960px;'
        'max-height:92vh;min-height:70vh;display:flex;flex-direction:column;'
        'box-shadow:0 0 0 1px rgba(108,84,232,.12),0 24px 60px rgba(0,0,0,.18);'
        'animation:mpPopIn .25s cubic-bezier(.34,1.56,.64,1) both;overflow:hidden;}'
        '@keyframes mpPopIn{from{opacity:0;transform:scale(.94) translateY(8px);}to{opacity:1;transform:scale(1) translateY(0);}}'
        '.mp-hdr{padding:20px 22px 16px;border-bottom:1px solid #f0eeff;display:flex;align-items:center;justify-content:space-between;flex-shrink:0;}'
        '.mp-hdl{display:flex;align-items:center;gap:11px;}'
        '.mp-hico{width:38px;height:38px;background:#ede9fd;border-radius:10px;display:grid;place-items:center;flex-shrink:0;}'
        '.mp-hico svg{width:18px;height:18px;stroke:#6c54e8;fill:none;stroke-width:2;stroke-linecap:round;}'
        '.mp-ttl{font-size:15px;font-weight:700;color:#1a1d2e;letter-spacing:-.01em;}'
        '.mp-sub{font-size:11.5px;color:#9ca3af;margin-top:2px;}'
        '.mp-xbtn{width:28px;height:28px;border:1px solid #e4e6ed;border-radius:7px;background:#fff;'
        'display:grid;place-items:center;cursor:pointer;color:#9ca3af;font-size:14px;'
        'transition:border-color .15s,color .15s;flex-shrink:0;line-height:1;}'
        '.mp-xbtn:hover{border-color:#ef4444;color:#ef4444;}'
        '.mp-bdy{flex:1;overflow-y:auto;padding:16px 22px;}'
        '.mp-bdy::-webkit-scrollbar{width:4px;}'
        '.mp-bdy::-webkit-scrollbar-thumb{background:#c4b5fd;border-radius:99px;}'
        '.mp-srow{display:flex;gap:8px;margin-bottom:6px;position:relative;}'
        '.mp-si{flex:1;padding:9px 13px;border:1.5px solid #e4e6ed;border-radius:9px;'
        'font-size:13px;color:#1a1d2e;background:#fafafa;outline:none;transition:border-color .15s,box-shadow .15s;}'
        '.mp-si:focus{border-color:#6c54e8;box-shadow:0 0 0 3px rgba(108,84,232,.08);background:#fff;}'
        '.mp-sgo{padding:9px 20px;background:#6c54e8;color:#fff;border:none;border-radius:9px;'
        'font-size:13px;font-weight:600;cursor:pointer;transition:background .15s;white-space:nowrap;}'
        '.mp-sgo:hover{background:#5a43d0;}'
        '.mp-hint{font-size:11.5px;color:#9ca3af;margin-bottom:14px;}'
        '.mp-sug{display:none;position:absolute;top:100%;left:0;right:68px;max-height:50vh;overflow-y:auto;'
        'background:#fff;border:1px solid #e4e6ed;border-top:none;border-radius:0 0 9px 9px;'
        'z-index:10;box-shadow:0 4px 12px rgba(0,0,0,.1);}'
        '.mp-chg{background:#faf9ff;border:1.5px solid #e8e2ff;border-radius:10px;padding:14px 16px;margin-bottom:16px;}'
        '.mp-clbl{font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#6c54e8;margin-bottom:10px;}'
        '.mp-crow{display:flex;align-items:center;gap:8px;flex-wrap:wrap;}'
        '.mp-tg{display:flex;border:1.5px solid #e8e2ff;border-radius:8px;overflow:hidden;flex-shrink:0;}'
        '.mp-to{padding:7px 14px;font-size:12px;font-weight:700;cursor:pointer;user-select:none;'
        'transition:background .15s,color .15s;color:#9ca3af;background:#fff;}'
        '.mp-to.ae{background:#6c54e8;color:#fff;}'
        '.mp-to.ad{background:#6b7280;color:#fff;}'
        '.mp-to:not(:last-child){border-right:1.5px solid #e8e2ff;}'
        '.mp-dvd{width:1px;height:32px;background:#e8e2ff;flex-shrink:0;}'
        '.mp-vi{flex:1;min-width:100px;padding:8px 12px;border:1.5px solid #e8e2ff;border-radius:8px;'
        'font-size:13px;color:#1a1d2e;background:#fff;outline:none;transition:border-color .15s,box-shadow .15s;}'
        '.mp-vi:focus{border-color:#6c54e8;box-shadow:0 0 0 3px rgba(108,84,232,.08);}'
        '.mp-ap{padding:8px 18px;background:#6c54e8;color:#fff;border:none;border-radius:8px;'
        'font-size:12.5px;font-weight:600;cursor:pointer;transition:background .15s;white-space:nowrap;flex-shrink:0;}'
        '.mp-ap:hover{background:#5a43d0;}'
        '.mp-tbl{width:100%;border-collapse:collapse;}'
        '.mp-tbl thead tr{background:#f7f8fb;}'
        '.mp-tbl th{padding:9px 12px;font-size:10.5px;font-weight:700;letter-spacing:.1em;'
        'text-transform:uppercase;color:#9ca3af;border-bottom:1.5px solid #e8e2ff;}'
        '.mp-tbl th:first-child{width:40px;text-align:center;}'
        '.mp-tbl th:nth-child(2){text-align:left;}'
        '.mp-tbl th:nth-child(3){text-align:center;}'
        '.mp-tbl th:nth-child(4){text-align:center;}'
        '.mp-tbl td{padding:11px 12px;border-bottom:1px solid #f0eeff;font-size:13px;vertical-align:middle;}'
        '.mp-tbl tr:last-child td{border-bottom:none;}'
        '.mp-tbl tr.mp-rs td{background:#f5f3ff;}'
        '.mp-tbl tr.mp-rs:hover td{background:#ede9fd;cursor:pointer;}'
        '.mp-tbl tr:not(.mp-rs):hover td{background:#faf9ff;cursor:pointer;}'
        '.mp-tbl td:first-child{text-align:center;}'
        '.mp-tbl td:nth-child(2){font-weight:500;color:#1a1d2e;}'
        '.mp-tbl td:nth-child(3){text-align:center;font-weight:600;color:#6c54e8;}'
        '.mp-tbl td.mp-mt{color:#d1d5db!important;font-weight:400!important;}'
        '.mp-tbl td:nth-child(4){text-align:center;}'
        '.mp-ccb{width:17px;height:17px;border:1.5px solid #d1d5db;border-radius:5px;background:#fff;'
        'display:inline-grid;place-items:center;cursor:pointer;transition:border-color .15s,background .15s;}'
        '.mp-ccb.on{background:#6c54e8;border-color:#6c54e8;}'
        '.mp-ccb svg{width:10px;height:10px;stroke:#fff;fill:none;stroke-width:2.5;stroke-linecap:round;opacity:0;transition:opacity .15s;}'
        '.mp-ccb.on svg{opacity:1;}'
        '.mp-bg{display:inline-flex;align-items:center;justify-content:center;padding:3px 10px;'
        'border-radius:6px;font-size:11px;font-weight:700;letter-spacing:.05em;}'
        '.mp-bge{background:#dcfce7;color:#15803d;border:1px solid #bbf7d0;}'
        '.mp-bgd{background:#f3f4f6;color:#6b7280;border:1px solid #e5e7eb;}'
        '.mp-bgerr{background:#fee2e2;color:#dc2626;border:1px solid #fecaca;}'
        '.mp-ftr{padding:14px 22px 18px;border-top:1px solid #f0eeff;display:flex;align-items:center;justify-content:space-between;flex-shrink:0;}'
        '.mp-fi{font-size:12px;color:#a993f5;font-weight:500;}'
        '.mp-fbs{display:flex;gap:8px;}'
        '.mp-bcl{padding:9px 20px;border:1.5px solid #e4e6ed;border-radius:9px;background:#f4f5f8;'
        'font-size:13px;font-weight:600;color:#6b7280;cursor:pointer;transition:all .15s;}'
        '.mp-bcl:hover{background:#e9eaee;color:#1a1d2e;}'
        '.mp-bsv{padding:9px 28px;border:none;border-radius:9px;background:#6c54e8;color:#fff;'
        'font-size:13px;font-weight:600;cursor:pointer;box-shadow:0 2px 8px rgba(108,84,232,.35);transition:all .15s;}'
        '.mp-bsv:hover:not(:disabled){background:#5a43d0;box-shadow:0 4px 16px rgba(108,84,232,.45);transform:translateY(-1px);}'
        '.mp-bsv:disabled{opacity:.45;cursor:default;box-shadow:none;}'
        '.mp-sm{display:none;position:fixed;inset:0;z-index:10000;background:rgba(15,15,30,.55);'
        'backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px);align-items:center;justify-content:center;padding:24px;}'
        '.mp-sc{background:#fff;border-radius:14px;width:100%;max-width:420px;'
        'box-shadow:0 0 0 1px rgba(108,84,232,.1),0 20px 50px rgba(0,0,0,.2);'
        'animation:mpPopIn .22s cubic-bezier(.34,1.56,.64,1) both;padding:28px 28px 22px;}'
        '.mp-sc h3{font-size:15px;font-weight:700;color:#1a1d2e;margin-bottom:8px;}'
        '.mp-sc p{font-size:13px;color:#6b7280;margin-bottom:20px;line-height:1.6;}'
        '.mp-sc .mp-sbs{display:flex;gap:8px;justify-content:flex-end;}'
        '.mp-rl{max-height:220px;overflow-y:auto;margin-bottom:18px;border:1px solid #f0eeff;border-radius:8px;font-size:12px;}'
        '.mp-rl div{padding:7px 12px;border-bottom:1px solid #f0eeff;display:flex;gap:8px;}'
        '.mp-rl div:last-child{border-bottom:none;}'
        '</style>'

        '<div id="modify-panel" style="display:none;position:fixed;inset:0;z-index:9999;'
        'background:rgba(15,15,30,.45);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);'
        'align-items:center;justify-content:center;padding:24px;" onmousedown="_ovMd(event)" onclick="_ovClick(event,_closeModify)">'
        '<div class="mp-modal">'

        '<div class="mp-hdr">'
        '<div class="mp-hdl">'
        '<div class="mp-hico"><svg viewBox="0 0 24 24"><path d="M12 20h9"/>'
        '<path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/></svg></div>'
        '<div><div class="mp-ttl">Modify Parameter</div>'
        '<div class="mp-sub">파라미터를 검색하고 값을 수정하세요</div></div>'
        '</div>'
        '<button class="mp-xbtn" onclick="_closeModify()">&#x2715;</button>'
        '</div>'

        '<div class="mp-bdy">'
        '<div class="mp-srow">'
        '<input class="mp-si" type="text" id="mp-search" autocomplete="off" '
        'placeholder="파라미터 이름 검색..." oninput="_mpFilter()" onkeydown="_mpKeyDown(event)">'
        '<div id="mp-sug" class="mp-sug"></div>'
        '<button class="mp-sgo" onclick="_mpDoSearch()">검색</button>'
        '</div>'
        '<div class="mp-hint">파라미터 이름을 입력하여 검색하세요.</div>'

        '<div id="mp-chg" class="mp-chg" style="display:none;">'
        '<div class="mp-clbl">Change To</div>'
        '<div class="mp-crow">'
        '<div class="mp-tg">'
        '<div class="mp-to" id="mp-ten" onclick="_mpSetTog(\'enable\')">ENABLE</div>'
        '<div class="mp-to" id="mp-tdis" onclick="_mpSetTog(\'disable\')">DISABLE</div>'
        '</div>'
        '<div class="mp-dvd"></div>'
        '<input class="mp-vi" type="text" id="mp-nv" placeholder="값 입력...">'
        '<button class="mp-ap" onclick="_mpApply()">일괄 적용</button>'
        '</div>'
        '</div>'

        '<div id="mp-res" style="display:none;">'
        '<table class="mp-tbl">'
        '<thead><tr>'
        '<th><div class="mp-ccb" id="mp-cba" onclick="_mpTogAll()">'
        '<svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg></div></th>'
        '<th>DGServer</th><th>Value</th><th>Status</th>'
        '</tr></thead>'
        '<tbody id="mp-tb"></tbody>'
        '</table>'
        '</div>'
        '</div>'

        '<div class="mp-ftr">'
        '<span class="mp-fi" id="mp-fi">선택된 서버 없음</span>'
        '<div class="mp-fbs">'
        '<button class="mp-bcl" onclick="_closeModify()">취소</button>'
        '<button class="mp-bsv" id="mp-sv" onclick="_mpConfirm()" disabled>저장</button>'
        '</div>'
        '</div>'
        '</div>'
        '</div>'

        '<div id="mp-cfm" class="mp-sm" style="display:none;">'
        '<div class="mp-sc">'
        '<h3>변경 사항 저장</h3>'
        '<p id="mp-cfm-msg">선택한 DGServer의 파라미터를 저장합니다.<br>저장 후 DGServer 재시작이 필요합니다.</p>'
        '<div class="mp-sbs">'
        '<button class="mp-bcl" onclick="_mpCfmNo()">취소</button>'
        '<button class="mp-bsv" onclick="_mpDoSave()">저장</button>'
        '</div>'
        '</div>'
        '</div>'

        '<div id="mp-rsm" class="mp-sm" style="display:none;">'
        '<div class="mp-sc">'
        '<h3 id="mp-rsm-ttl">저장 완료</h3>'
        '<div id="mp-rsm-list" class="mp-rl"></div>'
        '<div class="mp-sbs">'
        '<button class="mp-bsv" onclick="_mpRsmOk()">확인</button>'
        '</div>'
        '</div>'
        '</div>'
    )

    ub = _UTILS_BASE
    js = """<script>
var _mpAllParams=%s;
var _mpChanges={};
var _mpCurParam="";
var _mpTog=null;
var _mpRows=[];
var _mpSel=new Set();
var _mpArrowIdx=-1;
function _openModifyPanel(){
  var p=document.getElementById("modify-panel");
  if(p.parentNode!==document.body)document.body.appendChild(p);
  var cfm=document.getElementById("mp-cfm");
  if(cfm&&cfm.parentNode!==document.body)document.body.appendChild(cfm);
  var rsm=document.getElementById("mp-rsm");
  if(rsm&&rsm.parentNode!==document.body)document.body.appendChild(rsm);
  p.style.display="flex";
}
function _closeModify(){
  document.getElementById("modify-panel").style.display="none";
  document.getElementById("mp-search").value="";
  document.getElementById("mp-sug").style.display="none";
  document.getElementById("mp-res").style.display="none";
  document.getElementById("mp-chg").style.display="none";
  document.getElementById("mp-tb").innerHTML="";
  document.getElementById("mp-nv").value="";
  document.getElementById("mp-cba").classList.remove("on");
  _mpChanges={};_mpCurParam="";_mpArrowIdx=-1;_mpRows=[];_mpSel=new Set();_mpTog=null;
  _mpRstTog();
  document.getElementById("mp-sv").disabled=true;
  document.getElementById("mp-fi").textContent="선택된 서버 없음";
}
function _mpFilter(){
  var v=document.getElementById("mp-search").value.toLowerCase().trim();
  var sg=document.getElementById("mp-sug");
  if(!v){sg.style.display="none";return;}
  var m=_mpAllParams.filter(function(p){return p.toLowerCase().indexOf(v)>=0;});
  if(!m.length){sg.style.display="none";return;}
  sg.innerHTML=m.slice(0,80).map(function(p,i){
    var re=new RegExp("("+v.replace(/[.*+?^${}()|[\\]\\\\]/g,"\\\\$&")+")","gi");
    var hl=p.replace(re,"<b style='color:#6c54e8'>$1</b>");
    return "<div data-sgidx='"+i+"' onclick=\\"_mpPick('"+p+"')\\" style='padding:7px 12px;cursor:pointer;font-size:.82rem;color:#334155;border-bottom:1px solid #f0eeff;' onmouseover=\\"this.style.background='#faf9ff'\\" onmouseout=\\"this.style.background=''\\">"+hl+"</div>";
  }).join("");
  sg.style.display="block";_mpArrowIdx=-1;
}
function _mpPick(p){document.getElementById("mp-search").value=p;document.getElementById("mp-sug").style.display="none";_mpDoSearch();}
function _mpDoSearch(){
  var p=document.getElementById("mp-search").value.trim();
  if(!p)return;
  document.getElementById("mp-sug").style.display="none";
  _mpCurParam=p;_mpChanges={};_mpRows=[];_mpSel=new Set();_mpTog=null;_mpRstTog();
  document.getElementById("mp-sv").disabled=true;
  document.getElementById("mp-fi").textContent="선택된 서버 없음";
  var tb=document.getElementById("mp-tb");
  tb.innerHTML="<tr><td colspan='4' style='text-align:center;padding:20px;color:#9ca3af'>불러오는 중...</td></tr>";
  document.getElementById("mp-res").style.display="block";
  document.getElementById("mp-chg").style.display="none";
  fetch("%s/api/dgxml-param-search?param="+encodeURIComponent(p))
  .then(function(r){return r.json();})
  .then(function(d){
    if(!d.ok){tb.innerHTML="<tr><td colspan='4' style='text-align:center;padding:20px;color:#ef4444'>"+d.error+"</td></tr>";return;}
    if(!d.results||!d.results.length){tb.innerHTML="<tr><td colspan='4' style='text-align:center;padding:20px;color:#9ca3af'>검색 결과 없음</td></tr>";return;}
    _mpRows=d.results;_mpRender();
    document.getElementById("mp-chg").style.display="block";
  }).catch(function(){tb.innerHTML="<tr><td colspan='4' style='text-align:center;padding:20px;color:#ef4444'>요청 실패</td></tr>";});
}
function _mpBadge(s){
  if(s==="Enable")return "<span class='mp-bg mp-bge'>ENABLE</span>";
  if(s==="Disable")return "<span class='mp-bg mp-bgd'>DISABLE</span>";
  if(s==="Not Found")return "<span style='color:#d1d5db;font-size:12px;'>-</span>";
  return "<span class='mp-bg mp-bgerr'>"+s+"</span>";
}
function _mpRender(){
  var tb=document.getElementById("mp-tb");
  tb.innerHTML=_mpRows.map(function(r,i){
    var nf=(r.status==="Not Found");
    var sel=_mpSel.has(i);
    var ch=_mpChanges[r.xmlfile]||{};
    var val=ch.value!==undefined?ch.value:r.value;
    var st=ch.status||r.status;
    var muted=(r.value==="-"&&!ch.value)?"mp-mt":"";
    return "<tr class='"+(sel?"mp-rs":"")+"' onclick='_mpRowClick("+i+")'"+(nf?" style='opacity:.55;cursor:default;'":"")+">"
      +"<td><div class='mp-ccb"+(sel?" on":"")+"'><svg viewBox='0 0 24 24'><polyline points='20 6 9 17 4 12'/></svg></div></td>"
      +"<td>"+r.dgserver+"</td>"
      +"<td class='"+muted+"'>"+val+"</td>"
      +"<td>"+_mpBadge(st)+"</td>"
      +"</tr>";
  }).join("");
  _mpUpdAllCb();_mpUpdFi();
}
function _mpRowClick(i){
  if(_mpRows[i]&&_mpRows[i].status==="Not Found")return;
  if(_mpSel.has(i))_mpSel.delete(i);else _mpSel.add(i);
  _mpRender();
}
function _mpTogAll(){
  var el=[];for(var i=0;i<_mpRows.length;i++){if(_mpRows[i].status!=="Not Found")el.push(i);}
  var all=el.length>0&&el.every(function(i){return _mpSel.has(i);});
  if(all)el.forEach(function(i){_mpSel.delete(i);});else el.forEach(function(i){_mpSel.add(i);});
  _mpRender();
}
function _mpUpdAllCb(){
  var el=[];for(var i=0;i<_mpRows.length;i++){if(_mpRows[i].status!=="Not Found")el.push(i);}
  var all=el.length>0&&el.every(function(i){return _mpSel.has(i);});
  var cb=document.getElementById("mp-cba");
  if(all)cb.classList.add("on");else cb.classList.remove("on");
}
function _mpUpdFi(){
  var n=_mpSel.size;
  document.getElementById("mp-fi").textContent=n===0?"선택된 서버 없음":n+"개 서버 선택됨";
}
function _mpSetTog(v){
  _mpTog=v;
  document.getElementById("mp-ten").className="mp-to"+(v==="enable"?" ae":"");
  document.getElementById("mp-tdis").className="mp-to"+(v==="disable"?" ad":"");
}
function _mpRstTog(){
  document.getElementById("mp-ten").className="mp-to";
  document.getElementById("mp-tdis").className="mp-to";
  _mpTog=null;
}
function _mpApply(){
  if(!_mpSel.size){alert("적용할 DGServer를 선택해 주세요.");return;}
  var nv=document.getElementById("mp-nv").value;
  var hasSt=(_mpTog==="enable"||_mpTog==="disable");
  var hasVal=nv.trim()!=="";
  if(!hasSt&&!hasVal){alert("ENABLE/DISABLE 또는 새 값을 입력하세요.");return;}
  _mpSel.forEach(function(i){
    var r=_mpRows[i];if(!r||r.status==="Not Found")return;
    var rec=_mpChanges[r.xmlfile]||{xmlfile:r.xmlfile,param:_mpCurParam};
    if(hasSt)rec.status=_mpTog==="enable"?"Enable":"Disable";
    if(hasVal)rec.value=nv;
    _mpChanges[r.xmlfile]=rec;
  });
  document.getElementById("mp-sv").disabled=false;
  _mpRender();
}
function _mpConfirm(){
  var changes=Object.values(_mpChanges);
  if(!changes.length)return;
  document.getElementById("mp-cfm-msg").innerHTML=changes.length+"개 서버의 파라미터 변경 사항을 저장합니다.<br>저장 후 DGServer 재시작이 필요합니다.";
  document.getElementById("mp-cfm").style.display="flex";
}
function _mpCfmNo(){document.getElementById("mp-cfm").style.display="none";}
function _mpDoSave(){
  document.getElementById("mp-cfm").style.display="none";
  var changes=Object.values(_mpChanges);
  var btn=document.getElementById("mp-sv");btn.disabled=true;btn.textContent="저장 중...";
  fetch("%s/api/dgxml-param-save",{method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({changes:changes})})
  .then(function(r){return r.json();})
  .then(function(d){
    btn.textContent="저장";
    var list=document.getElementById("mp-rsm-list");
    if(d.ok){
      document.getElementById("mp-rsm-ttl").textContent="저장 완료";
      list.innerHTML=d.results.map(function(r){
        var ok=r.status==="ok",nc=r.status==="no_change";
        var col=ok?"#15803d":nc?"#6b7280":"#dc2626";
        var lbl=ok?"완료":nc?"변경 없음":"오류";
        return "<div style='color:"+col+"'><span style='min-width:64px;display:inline-block;font-weight:700;'>"+lbl+"</span>"
          +"<span style='color:#1a1d2e;font-weight:500;'>"+r.xmlfile.split("/").pop()+"</span>"
          +(r.message?"<span style='color:#ef4444;margin-left:6px;'>"+r.message+"</span>":"")+"</div>";
      }).join("");
    }else{
      document.getElementById("mp-rsm-ttl").textContent="저장 실패";
      list.innerHTML="<div style='color:#dc2626;padding:8px 12px;'>"+(d.error||"알 수 없는 오류")+"</div>";
      btn.disabled=false;
    }
    document.getElementById("mp-rsm").style.display="flex";
  }).catch(function(){
    btn.textContent="저장";btn.disabled=false;
    document.getElementById("mp-rsm-ttl").textContent="저장 실패";
    document.getElementById("mp-rsm-list").innerHTML="<div style='color:#dc2626;padding:8px 12px;'>요청 실패</div>";
    document.getElementById("mp-rsm").style.display="flex";
  });
}
function _mpRsmOk(){document.getElementById("mp-rsm").style.display="none";_closeModify();location.reload();}
document.addEventListener("click",function(e){
  var sg=document.getElementById("mp-sug");
  if(sg&&!sg.contains(e.target)&&e.target.id!=="mp-search")sg.style.display="none";
});
function _mpKeyDown(e){
  var sg=document.getElementById("mp-sug");
  var items=sg.querySelectorAll("[data-sgidx]");
  if(e.key==="ArrowDown"){e.preventDefault();_mpArrowIdx=Math.min(_mpArrowIdx+1,items.length-1);_mpHlArr(items);}
  else if(e.key==="ArrowUp"){e.preventDefault();_mpArrowIdx=Math.max(_mpArrowIdx-1,0);_mpHlArr(items);}
  else if(e.key==="Enter"){e.preventDefault();
    if(_mpArrowIdx>=0&&items[_mpArrowIdx])items[_mpArrowIdx].click();
    else _mpDoSearch();
  }else{_mpArrowIdx=-1;_mpFilter();}
}
function _mpHlArr(items){
  items.forEach(function(el,j){el.style.background=j===_mpArrowIdx?"#f5f3ff":"";});
  if(items[_mpArrowIdx])items[_mpArrowIdx].scrollIntoView({block:"nearest"});
}
</script>""" % (params_json, ub, ub)

    return html + js


# ── API endpoints ──────────────────────────────────────────────────────

def api_dgxml_param_search(param_name_str):
    """Search for a parameter across all DGServer.xml files."""
    try:
        from urllib.parse import unquote
    except ImportError:
        from urllib import unquote
    param_name = unquote(param_name_str or "").strip()
    if not param_name:
        return json.dumps({"ok": False, "error": "Empty parameter name"})

    all_data = _parse_all_params()
    if not all_data:
        return json.dumps({"ok": False, "error": "No DGServer configured"})

    results = []
    for name, xmlfile, safe_id, parsed, error in all_data:
        if error:
            results.append({"dgserver": name, "xmlfile": xmlfile, "param": param_name,
                            "value": "-", "status": "Error"})
            continue
        found = False
        for is_disabled, key, val in parsed:
            if key == param_name:
                results.append({"dgserver": name, "xmlfile": xmlfile, "param": key,
                                "value": val, "status": "Disable" if is_disabled else "Enable"})
                found = True
                break
        if not found:
            results.append({"dgserver": name, "xmlfile": xmlfile, "param": param_name,
                            "value": "-", "status": "Not Found"})
    return json.dumps({"ok": True, "results": results}, ensure_ascii=False)


def api_dgxml_param_save(raw_body):
    """Save parameter changes to DGServer.xml files.

    Accepts per-xmlfile entries that may carry BOTH a status toggle
    (Enable/Disable) and a new value. Applied atomically in one file write
    so the resulting XML matches exactly what the preview showed."""
    try:
        data = json.loads(raw_body.decode('utf-8', errors='ignore'))
    except Exception:
        return json.dumps({"ok": False, "error": "Invalid JSON"})

    changes = data.get("changes", [])
    if not changes:
        return json.dumps({"ok": False, "error": "No changes provided"})

    results = []
    for ch in changes:
        xmlfile = ch.get("xmlfile", "")
        param   = ch.get("param", "")

        # New combined form: {status: "Enable"|"Disable"|None, value: str|None}
        new_status = (ch.get("status") or "").strip()
        new_value  = ch.get("value", None)
        has_status = new_status in ("Enable", "Disable")
        has_value  = new_value is not None and new_value != ""

        # Legacy single-action form still supported
        legacy = (ch.get("action") or "").strip().lower()
        if not has_status and not has_value and legacy:
            if legacy == "enable":
                new_status = "Enable"; has_status = True
            elif legacy == "disable":
                new_status = "Disable"; has_status = True
            elif legacy == "value":
                has_value = new_value not in (None, "")

        if not xmlfile or not param or not os.path.exists(xmlfile):
            results.append({"xmlfile": xmlfile, "status": "error", "message": "File not found"})
            continue
        if not has_status and not has_value:
            results.append({"xmlfile": xmlfile, "status": "no_change"})
            continue

        try:
            _today = time.strftime('%y%m%d')
            _seq = 0
            while os.path.exists(xmlfile + '.bak_' + _today + '_' + str(_seq)):
                _seq += 1
            bak = xmlfile + '.bak_' + _today + '_' + str(_seq)
            shutil.copy2(xmlfile, bak)

            with open(xmlfile, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()

            tag_re = re.compile(
                r'(<' + re.escape(param) + r'(?:\s[^>]*)?>)(.*?)(</' + re.escape(param) + r'>)')

            new_lines = []
            modified = False
            for line in lines:
                indent = line[:len(line) - len(line.lstrip())]
                stripped = line.rstrip('\n').strip()

                # Find the tag either bare or inside a single-line comment
                is_commented = stripped.startswith('<!--') and stripped.endswith('-->')
                inner = stripped[4:-3].strip() if is_commented else stripped
                if not tag_re.search(inner):
                    new_lines.append(line)
                    continue

                # Apply value replacement (if requested)
                if has_value:
                    inner = tag_re.sub(lambda m: m.group(1) + new_value + m.group(3), inner)

                # Determine final comment state
                want_commented = (new_status == "Disable") if has_status else is_commented
                rebuilt = ('<!--' + inner + '-->') if want_commented else inner
                new_line = indent + rebuilt + '\n'
                if new_line != line:
                    modified = True
                new_lines.append(new_line)

            if modified:
                with open(xmlfile, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
                results.append({"xmlfile": xmlfile, "status": "ok", "backup": os.path.basename(bak)})
            else:
                os.remove(bak)
                results.append({"xmlfile": xmlfile, "status": "no_change"})
        except Exception as e:
            results.append({"xmlfile": xmlfile, "status": "error", "message": str(e)[:200]})

    return json.dumps({"ok": True, "results": results}, ensure_ascii=False)
