const ids=['year','platform','category','issue_type'];
const charts={};let page=1, meta, current, sequence=0, tableSequence=0;
const pct=v=>v==null?'无样本':(v*100).toFixed(1)+'%';
function query(){const p=new URLSearchParams();for(const id of ids){const v=document.getElementById(id).value;if(v)p.set(id,v)}return p}
async function get(url){const r=await fetch(url);if(!r.ok)throw Error('请求失败 '+r.status);return r.json()}
function plot(id,option){if(!charts[id])charts[id]=echarts.init(document.getElementById(id));charts[id].setOption({color:['#157f73','#7190cd','#a78bca','#c89b60','#5aaec1','#8eae68','#db8c7e','#76899b','#b6a65e','#bf96af'],textStyle:{fontFamily:'system-ui, Microsoft YaHei, sans-serif',color:'#6c8080'},...option},true)}
function axes(labels,values,line=false){return {tooltip:{trigger:'axis'},grid:{left:55,right:22,bottom:55},xAxis:{type:'category',data:labels,axisLabel:{rotate:25}},yAxis:{type:'value',min:0},series:[{type:line?'line':'bar',data:values,smooth:false,itemStyle:{color:'#157f73'}}]}}
function bars(id,data){const sorted=[...data].sort((a,b)=>a.count-b.count);plot(id,{tooltip:{trigger:'axis'},grid:{left:100,right:30,bottom:30},xAxis:{type:'value',min:0},yAxis:{type:'category',data:sorted.map(d=>d.name)},series:[{type:'bar',data:sorted.map(d=>d.count),itemStyle:{color:'#157f73'}}]})}
function renderMatrix(){
 const field=document.getElementById('matrixMetric').value, m=current.matrix;
 const vals=m.map(d=>[meta.types.indexOf(d.issue_type),meta.categories.indexOf(d.category),field==='count'?d.count:(d.row_share==null?null:+(d.row_share*100).toFixed(2))]);
 plot('matrix',{tooltip:{formatter:p=>meta.categories[p.value[1]]+' / '+meta.types[p.value[0]]+'：'+(p.value[2]??'无样本')+(field==='count'?' 条':'%')},
 grid:{left:100,right:35,bottom:80},xAxis:{type:'category',data:meta.types,axisLabel:{rotate:25}},yAxis:{type:'category',data:meta.categories},
 visualMap:{min:0,max:field==='count'?Math.max(1,...m.map(d=>d.count)):100,calculable:true,orient:'horizontal',bottom:0,left:'center',inRange:{color:['#f0f7ed','#b7d8c1','#157f73']}},
 series:[{type:'heatmap',data:vals,label:{show:true,formatter:p=>p.value[2]==null?'—':p.value[2]},emphasis:{itemStyle:{borderColor:'#23344b',borderWidth:1}}}]})
}
async function table(token){
 const request=++tableSequence;
 document.getElementById('prev').disabled=true;document.getElementById('next').disabled=true;
 const p=query();p.set('page',page);p.set('page_size',10);
 const r=await get('/api/records?'+p);if(token!==sequence||request!==tableSequence)return;
 const tbody=document.getElementById('rows');tbody.replaceChildren();
 for(const row of r.items){const tr=document.createElement('tr');for(const col of ['complaint_id','complaint_date','platform','category','issue_type','amount','status']){const td=document.createElement('td');td.textContent=row[col];tr.append(td)}tbody.append(tr)}
 if(!r.items.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=7;td.textContent='当前筛选没有样本';tr.append(td);tbody.append(tr)}
 document.getElementById('pageInfo').textContent='第 '+page+' 页 / '+Math.max(1,Math.ceil(r.total/10))+' 页 · 共 '+r.total+' 条';
 document.getElementById('prev').disabled=page<=1;document.getElementById('next').disabled=page*10>=r.total
}
async function refresh(reset=true){
 if(reset)page=1;const token=++sequence;
 ++tableSequence;
 document.getElementById('export').removeAttribute('href');document.getElementById('export').setAttribute('aria-disabled','true');
 document.getElementById('prev').disabled=true;document.getElementById('next').disabled=true;
 const s=document.getElementById('status');s.textContent='正在计算…';
 try{
 const r=await get('/api/dashboard?'+query());if(token!==sequence)return;
 current=r.metrics;
 document.getElementById('total').textContent=current.total.toLocaleString();
 document.getElementById('closed').textContent=pct(current.closure_share);
 document.getElementById('amount').textContent=current.median_amount?.toFixed(2)??'无样本';
 document.getElementById('duration').textContent=current.closed_duration_median??'无样本';
 plot('annual',axes(current.annual.map(d=>d.year),current.annual.map(d=>d.count)));
 plot('monthly',axes(current.monthly.map(d=>d.month),current.monthly.map(d=>d.count),true));
 bars('types',current.types);bars('categories',current.categories);renderMatrix();
 plot('platforms',{tooltip:{trigger:'axis'},legend:{type:'scroll'},grid:{left:55,right:20,top:70,bottom:45},
 xAxis:{type:'category',data:meta.platforms},yAxis:{type:'value',max:100,axisLabel:{formatter:'{value}%'}},
 series:meta.types.map(t=>({name:t,type:'bar',stack:'total',data:meta.platforms.map(p=>{const d=current.platform_types.find(x=>x.platform===p&&x.issue_type===t);return d.share==null?null:+(d.share*100).toFixed(4)})}))});
 const top=[...current.types].sort((a,b)=>b.count-a.count).slice(0,5).map(d=>d.name);
 const years=current.annual.map(d=>d.year);
 plot('typeYear',{tooltip:{trigger:'axis'},legend:{type:'scroll'},grid:{left:55,right:25,top:65,bottom:40},
 xAxis:{type:'category',data:years},yAxis:{type:'value',min:0},
 series:top.map(t=>({name:t,type:'line',data:years.map(y=>current.type_year.find(d=>d.year===y&&d.issue_type===t).count)}))});
 await table(token);if(token!==sequence)return;
 document.getElementById('export').href='/api/export?'+query();document.getElementById('export').setAttribute('aria-disabled','false');
 s.textContent='模拟场景：'+r.meta.generation.scenario+'；种子：'+r.meta.generation.seed+'；原始 '+r.meta.quality.raw_rows+' 条 → 清洗后 '+r.meta.quality.clean_rows+' 条；当前接口计算 '+r.elapsed_ms+' ms。'
 }catch(e){if(token===sequence)s.textContent=e.message}
}
async function boot(){
 if(typeof echarts==='undefined'){document.getElementById('status').textContent='ECharts文件缺失，请按README安装图表资源。';return}
 meta=await get('/api/meta');
 const lists=[meta.years,meta.platforms,meta.categories,meta.types];
 ids.forEach((id,i)=>{const s=document.getElementById(id);s.append(new Option('全部',''));lists[i].forEach(v=>s.append(new Option(v,v)));s.onchange=()=>refresh()});
 document.getElementById('reset').onclick=()=>{ids.forEach(id=>document.getElementById(id).value='');refresh()};
 document.getElementById('matrixMetric').onchange=renderMatrix;
 document.getElementById('prev').onclick=()=>{page--;table(sequence).catch(e=>document.getElementById('status').textContent=e.message)};
 document.getElementById('next').onclick=()=>{page++;table(sequence).catch(e=>document.getElementById('status').textContent=e.message)};
 await refresh();
 charts.types.on('click',p=>{document.getElementById('issue_type').value=p.name;refresh()});
 charts.categories.on('click',p=>{document.getElementById('category').value=p.name;refresh()});
 window.onresize=()=>Object.values(charts).forEach(c=>c.resize())
}
boot().catch(e=>document.getElementById('status').textContent=e.message);
