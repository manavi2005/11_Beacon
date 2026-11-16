/* Dependency-free canvas plots; data is safely serialized by Django json_script. */
const d=JSON.parse(document.getElementById('dashboard-data').textContent);
const colors=['#188578','#e4a348','#5778b2','#bd647e','#8e7eb7','#7d9a44'];
function plot(id,labels,series,kind='bars',axis=''){
 const el=document.getElementById(id), rect=el.getBoundingClientRect(), w=rect.width,h=rect.height,ratio=window.devicePixelRatio||1;
 el.width=w*ratio;el.height=h*ratio;const c=el.getContext('2d');c.scale(ratio,ratio);
 const left=55,top=series.length>2?74:42,bottom=kind==='bars'?90:45,pw=w-left-15,ph=h-top-bottom;
 const vals=kind==='stacked'?labels.map((_,i)=>series.reduce((sum,s)=>sum+(s.values[i]||0),0)):series.flatMap(s=>s.values).filter(v=>v!==null);const max=Math.max(...vals,0.001)*1.12;
 c.font='10px system-ui';c.fillStyle='#587079';
 for(let i=0;i<=4;i++){let y=top+ph-i*ph/4;c.strokeStyle='#e6edef';c.beginPath();c.moveTo(left,y);c.lineTo(w-10,y);c.stroke();c.fillText((max*i/4).toLocaleString(undefined,{maximumFractionDigits:max<.01?5:1}),0,y+3);}
 series.forEach((s,j)=>{const col=j%2,row=Math.floor(j/2);c.fillStyle=colors[j%6];c.fillRect(left+col*150,9+row*18,9,9);c.fillStyle='#587079';c.fillText(s.name,left+13+col*150,17+row*18);});
 if(kind==='stacked'){labels.forEach((_,i)=>{let base=0;series.forEach((s,j)=>{const v=s.values[i]||0;c.fillStyle=colors[j%6];c.fillRect(left+(i+.15)*pw/labels.length,top+ph-(base+v)/max*ph,pw/labels.length*.7,v/max*ph);base+=v;});});}
 if(kind!=='stacked')series.forEach((s,j)=>{c.strokeStyle=colors[j%6];c.fillStyle=colors[j%6];c.lineWidth=2;c.beginPath();let started=false;s.values.forEach((v,i)=>{if(v===null){started=false;return;}const x=left+(i+.5)*pw/labels.length,y=top+ph-v/max*ph;if(kind==='bars'){const bw=pw/labels.length/(series.length+1);c.fillRect(x+(j-series.length/2)*bw,y,bw*.85,top+ph-y);}else{if(!started)c.moveTo(x,y);else c.lineTo(x,y);started=true;}});if(kind!=='bars')c.stroke();});
 labels.forEach((label,i)=>{if(kind!=='bars'&&i%Math.max(1,Math.ceil(labels.length/5)))return;const x=left+(i+.5)*pw/labels.length;c.save();c.translate(x,top+ph+15);if(kind==='bars'){c.rotate(-.55);c.textAlign='right';}else c.textAlign='center';c.fillStyle='#587079';c.fillText(label,0,0);c.restore();});
 c.fillStyle='#587079';c.fillText(axis,left,h-4);
}
function draw(){const names=d.features.map(f=>f.name),s=(name,key)=>({name,values:d.features.map(f=>f[key])}),dates=d.daily.map(x=>x.day.slice(5));
 plot('latency',names,[s('p50','p50'),s('p95','p95')],'bars','Latency (ms)');
 plot('cohorts',names,[s('First week','first'),s('Later','later')],'bars','Calls');
 plot('cost',names,[s('USD / call','cost')],'bars','Estimated USD');
 plot('shares',names,[s('Call share %','call_share'),s('Token share %','token_share')],'bars','Percent of selected total');
 plot('outcomes',dates,['Success','Timeout','Invalid JSON','Provider down','Slow mode'].map(name=>({name,values:d.daily.map(x=>x.outcomes[name]||0)})),'stacked','Calendar day · stacked call counts');
 plot('retention',dates,[{name:'Retry within 24h',values:d.daily.map(x=>x.retry)},{name:'Next-day return',values:d.daily.map(x=>x.returned)}],'line','Calendar day · percent of low-grade events');
 plot('volume',dates,[{name:'Daily calls',values:d.daily.map(x=>x.count)},{name:'7-day mean',values:d.daily.map(x=>x.rolling)}],'line','Calendar day');
 plot('spend',dates,[{name:'Daily USD',values:d.daily.map(x=>x.cost)},{name:'7-day mean',values:d.daily.map(x=>x.rolling_cost)}],'line','Calendar day · estimated USD');
 plot('histogram',d.histogram.map((_,i)=>`${i*.5}–${(i+1)*.5}`),[{name:'Calls',values:d.histogram}],'bars','Latency bins (seconds; 0–10s)');
 const el=document.getElementById('scatter'),r=el.getBoundingClientRect(),ratio=window.devicePixelRatio||1;el.width=r.width*ratio;el.height=r.height*ratio;const c=el.getContext('2d');c.scale(ratio,ratio);c.font='10px system-ui';const maxX=Math.max(1,...d.scatter.map(p=>p.x)),maxY=Math.max(1,...d.scatter.map(p=>p.y));
 for(let i=0;i<=4;i++){const x=45+i*(r.width-65)/4,y=250-i*210/4;c.fillStyle='#587079';c.fillText(Math.round(maxX*i/4),x,268);c.fillText(Math.round(maxY*i/4),0,y);c.strokeStyle='#e6edef';c.beginPath();c.moveTo(45,y);c.lineTo(r.width-20,y);c.stroke();}
 d.scatter.forEach(p=>{c.fillStyle=colors[d.features.findIndex(f=>f.name===p.feature)]+'99';c.beginPath();c.arc(45+p.x/maxX*(r.width-65),250-p.y/maxY*210,3,0,Math.PI*2);c.fill();});c.fillStyle='#587079';c.fillText('Input characters (x) · latency ms (y)',45,295);
}
document.getElementById('print').addEventListener('click',()=>window.print());
draw();let timer;window.addEventListener('resize',()=>{clearTimeout(timer);timer=setTimeout(draw,150);});
