/* Auto-loaded My Orders, white/blue customer cards, token-authorized MongoDB history. */
(function(){
'use strict';
const get=id=>document.getElementById(id);
const list=get('my-orders-list'), count=get('my-orders-count'), info=get('my-orders-info');
if(!list||!window.PutiOrders)return;
const filterButtons=[...document.querySelectorAll('[data-my-filter]')];
const state={rows:[], filter:'all', query:'', loading:false, loaded:false};
const statuses={
  delivered:['Sent','success','Your Robux delivery is confirmed.'],
  manual:['Processing','pending','Payment confirmed. SMM service is being processed.'],
  sending:['Sending','pending','Payment confirmed. Robux are being processed.'],
  hold:['On hold','hold','Account unavailable; order is still active.'],
  unconfirmed:['Needs review','hold','Check with support before ordering again.'],
  failed:['Failed','failed','Contact support if payment was received.'],
  refunded:['Refunded','failed','This order was rejected and refunded.'],
  expired:['Expired','failed','Payment expired, no delivery was started.'],
  payment_error:['QR unavailable','failed','Payment was not started. Please try a new order.'],
  underpaid:['Under review','failed','Payment mismatch. Contact support.'],
  wait:['Pending payment','pending','Your Pay Now order is saved, waiting for payment.']
};
function el(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=String(text);return n;}
function dateText(value){const d=new Date(value||0);return Number.isFinite(d.getTime())?d.toLocaleString(): 'Just now';}
function kind(o){return o.delivered?'delivered':(o.step||'wait');}
function viewLabel(o){
 if(o.product_type==='fox'){const fx={delivered:['Delivered','success','Game Topup was delivered.'],sending:['Processing','pending','TopupFox is processing your order.'],manual:['Waiting','pending','Game Topup is awaiting supplier setup.'],failed:['Refund review','failed','Supplier refunded/failed. Contact support.'],unconfirmed:['Needs review','hold','Supplier order uncertain, contact support.']};return fx[kind(o)]||statuses[kind(o)]||statuses.wait;}
 if(o.product_type==='smm'){
  const smm={delivered:['Completed','success','Your SMM service is complete.'],sending:['Processing','pending','The supplier is processing your SMM order.'],manual:['Processing','pending','Admin will fulfill your SMM order.'],hold:['Needs review','hold','Supplier reports a partial or canceled order. Contact support.'],unconfirmed:['Needs review','hold','Supplier outcome not confirmed. Contact support; do not order again.']};
  return smm[kind(o)]||statuses[kind(o)]||statuses.wait;
 }
 return statuses[kind(o)]||statuses.wait;
}
function sectionLabel(o){const d=new Date(o.created_at||0),now=new Date();if(!Number.isFinite(d.getTime()))return 'RECENT';
  if(d.toDateString()===now.toDateString())return 'TODAY';
  const yesterday=new Date(now);yesterday.setDate(now.getDate()-1);
  return d.toDateString()===yesterday.toDateString()?'YESTERDAY':'OLDER';}
function match(o){
 const k=kind(o), s=state.filter;
 if(s==='unpaid'&&!['wait','expired','payment_error'].includes(k))return false;
 if(s==='paid'&&!o.paid)return false;
 if(s==='sent'&&k!=='delivered')return false;
 if(s==='hold'&&!['hold','unconfirmed'].includes(k))return false;
 if(s==='problem'&&!['failed','payment_error','expired','underpaid'].includes(k))return false;
 const q=state.query.trim().toLowerCase();
 return !q||[o.order_id,o.roblox_username,o.display_name,o.robux_amount,o.product_name,o.target_url,o.package].some(v=>String(v??'').toLowerCase().includes(q));
}
function fact(container,key,value){
 const row=el('div');row.append(el('span','',key),el('strong','',value));container.append(row);
}
function button(text,onClick,primary=false){
 const b=el('button','pr-orders-action'+(primary?' pr-orders-action-primary':''),text);
 b.type='button';b.addEventListener('click',onClick);return b;
}
function safeReceiptLink(o){
 const token=PutiOrders.read().find(e=>e.order_id===o.order_id)?.token;
 if(!token)return null;
 return '/order/success/'+encodeURIComponent(o.order_id)+'?token='+encodeURIComponent(token);
}
async function continuePayment(o,b){
 const row=PutiOrders.read().find(e=>e.order_id===o.order_id);
 if(!row){info.textContent='Order receipt is not available on this browser.';return;}
 b.disabled=true;b.textContent='Opening checkout…';
 try{
   const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),9500);
   const r=await fetch('/api/order-status/'+encodeURIComponent(o.order_id),{
      headers:{'X-Order-Token':row.token},cache:'no-store',signal:controller.signal});
   clearTimeout(timeout);
   if(!r.ok)throw new Error('Could not retrieve the original payment');
   const data=await r.json();
   if(data.paid){window.location.assign(safeReceiptLink(o)||'/check-order');return;}
   if(data.status==='expired'||data.status==='payment_error'||data.status==='failed'){
     info.textContent='This QR is no longer available. Please create a new order.';return;
   }
   if(/^https:\/\/khqrpay\.site\/pay\/[A-Za-z0-9_-]+(?:[?#][^\s]*)?$/.test(data.payment_url||'')){
     window.location.assign(data.payment_url);return;
   }
   info.textContent='QR is still preparing. Refresh My Orders shortly or contact support.';
 }catch(e){info.textContent='Connection problem. Your saved order is still in My Orders.'}
 finally{b.disabled=false;b.textContent='Continue payment'}
}
function loadAvatar(o,img){
 const id=String(o.roblox_id||'');
 if(!/^\d{1,20}$/.test(id))return;
 img.loading='lazy';
 const fn=()=>fetch('/api/roblox-avatar/'+encodeURIComponent(id),{cache:'force-cache'})
  .then(r=>r.ok?r.json():null).then(j=>{
    if(j&&typeof j.avatar==='string'&&j.avatar.startsWith('https://tr.rbxcdn.com/'))img.src=j.avatar;
  }).catch(()=>{});
 if('IntersectionObserver' in window){
   const obs=new IntersectionObserver(e=>{if(e[0].isIntersecting){obs.disconnect();fn();}},{rootMargin:'150px'});
   obs.observe(img);
 }else fn();
}
function card(o){
 const [label,kindClass,note]=viewLabel(o);
 const card=el('section','pr-order-card pr-my-order-card');
 const main=el('div','pr-order-main');
 const ava=el('div','pr-order-avatar');
 const service=o.product_type==='smm';
 const img=el('img');img.alt=service?'SMM':'Roblox profile';img.src=service?'/static/smm-icon.svg':'/static/roblox-mark.svg';
 ava.append(img,el('span','pr-avatar-status pr-avatar-'+(o.delivered?'sent':kindClass),o.delivered?'':'·'));
 const person=el('div','pr-order-person');person.append(el('div','pr-order-name',service?(o.product_name||'SMM service'):(o.display_name||o.roblox_username||'Roblox player')));
 const meta=el('div','pr-order-meta');
 meta.append(el('span','pr-order-handle',service?(o.package||'SMM package'):'@'+(o.roblox_username||'—')),el('span','pr-order-dot','·'),el('span','pr-order-state-label',label));
 person.append(meta,el('div','pr-my-order-time',dateText(o.created_at)));
 const robux=el('div','pr-order-robux');robux.append(el('strong','',service?'$'+Number(o.amount||0).toFixed(2):Number(o.robux_amount||0).toLocaleString('en-US')),el('small','',service?'SMM':'Robux'));
 main.append(ava,person,robux);
 const status=el('div','pr-my-order-status');status.append(el('span','pr-state-pill pr-state-'+kindClass,label),el('span','',note));
 const detail=el('details','pr-order-details');const summary=el('summary','','View order details ▾');
 const facts=el('div','pr-order-details-body');
 fact(facts,'Order ID',o.order_id);
 fact(facts,'Product',o.product_name||'Robux');fact(facts,'Plan',o.package||'Robux');if(service)fact(facts,'Social Link',o.target_url||'—');
 fact(facts,'Total','$'+Number(o.amount||0).toFixed(2));
 fact(facts,'Payment',o.paid?'Paid':o.status==='expired'?'Expired':'Not paid');
 fact(facts,'Delivery',label);
 fact(facts,'Date',dateText(o.created_at));
 detail.append(summary,facts);
 const acts=el('div','pr-order-actions');
 acts.append(button('Copy Order ID',()=>{
   if(navigator.clipboard?.writeText)navigator.clipboard.writeText(o.order_id).then(()=>info.textContent='Order ID copied').catch(()=>info.textContent=o.order_id);
   else info.textContent=o.order_id;
 }));
 if(o.paid){const href=safeReceiptLink(o);if(href){
   const a=el('a','pr-orders-action pr-orders-action-primary','View receipt');a.href=href;acts.append(a);
 }}else if(['pending','scanned','processing'].includes(o.status||'')){
   const pay=button('Continue payment',()=>continuePayment(o,pay),true);acts.append(pay);
 }
 if(/^https:\/\/www\.roblox\.com\/users\/\d+\/profile$/.test(o.profile_url||'')){
    const a=el('a','pr-orders-action','View Roblox profile');a.href=o.profile_url;a.rel='noopener noreferrer';a.target='_blank';acts.append(a);
 }
 card.append(main,status,detail,acts);if(!service)loadAvatar(o,img);return card;
}
function provisional(entry){
 const card=el('div','pr-customer-card pr-my-order-provisional');
 card.append(el('strong','','Preparing checkout…'),el('p','','Your Pay Now request is saved in this browser. Checking for the MongoDB order…'),el('small','',entry.order_id));
 return card;
}
function render(){
 list.replaceChildren();
 const saved=PutiOrders.read(), ordered=state.rows.filter(match);
 count.textContent=saved.length.toLocaleString('en-US')+' saved order'+(saved.length===1?'':'s');
 filterButtons.forEach(btn=>{let active=btn.dataset.myFilter===state.filter;btn.classList.toggle('active',active);btn.setAttribute('aria-pressed',String(active))});
 if(!saved.length){list.append(el('div','pr-orders-empty','No orders yet. Choose a product and click Pay Now — your order will appear here, even before you pay.'));return;}
 if(!ordered.length && state.loaded && (state.filter!=='all'||state.query)){
   list.append(el('div','pr-orders-empty','No orders match this search or filter.'));return;
 }
 let label='';
 for(const o of ordered){const next=sectionLabel(o);if(next!==label){label=next;list.append(el('div','pr-my-order-day',label))}list.append(card(o));}
 if(state.filter==='all'&&!state.query){
   const found=new Set(state.rows.map(o=>o.order_id));
   for(const e of saved.filter(e=>!found.has(e.order_id)).slice(0,5))list.append(provisional(e));
 }
}
async function load(refresh=false){
 if(state.loading)return;
 const refs=PutiOrders.read().map(({order_id,token})=>({order_id,token}));
 if(!refs.length){state.rows=[];state.loaded=true;render();return;}
 state.loading=true;if(!state.loaded){info.textContent='Loading your saved orders…';}
 const ctl=new AbortController(),timeout=setTimeout(()=>ctl.abort(),10000);
 try{
   const res=await fetch('/api/customer-orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({orders:refs,refresh}),signal:ctl.signal,cache:'no-store'});
   if(!res.ok)throw new Error('Unable to load your orders');
   const json=await res.json();if(!json.ok||!Array.isArray(json.orders))throw new Error('Invalid response');
   state.rows=json.orders;state.loaded=true;info.textContent='Orders are kept on the server. This browser remembers your private order references.';
 }catch(e){info.textContent='Could not update your orders. Check your connection; saved references are still on this device.';}
 finally{clearTimeout(timeout);state.loading=false;render();}
}
filterButtons.forEach(btn=>btn.addEventListener('click',()=>{state.filter=btn.dataset.myFilter;render()}));
const search=get('my-orders-search');if(search)search.addEventListener('input',()=>{state.query=search.value;render()});
window.addEventListener('puti:orders-changed',()=>load(false));
render();load(false);
setInterval(()=>{if(!document.hidden&&PutiOrders.read().length)load(true)},20000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)load(false)});
})();
