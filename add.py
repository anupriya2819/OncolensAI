from pathlib import Path
import shutil, zipfile, textwrap, os, json

src_backend = Path("/mnt/data/oncolens_mvp/backend")
root = Path("/mnt/data/oncolens_v2")
frontend_dir = root / "frontend"
backend_dir = root / "backend"
frontend_dir.mkdir(parents=True, exist_ok=True)
backend_dir.mkdir(parents=True, exist_ok=True)

# Reuse the already-created backend files if present.
for name in ["server.py", "requirements.txt", "START_BACKEND.bat"]:
    src = src_backend / name
    if src.exists():
        shutil.copy2(src, backend_dir / name)

html = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>OncoLens AI</title>
<script src="https://cdn.tailwindcss.com"></script>
<script crossorigin src="https://unpkg.com/react@18/umd/react.development.js"></script>
<script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>
<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
<style>
  *{box-sizing:border-box}
  body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f6f9fc;color:#17324d}
  .shadow-soft{box-shadow:0 12px 30px rgba(26,71,103,.08)}
  .glass{backdrop-filter:blur(14px);background:rgba(255,255,255,.92)}
  .fade{animation:fade .28s ease both}
  @keyframes fade{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}
  .pulse{animation:pulse 1.4s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.45}}
  .spinner{width:34px;height:34px;border:4px solid rgba(255,255,255,.25);border-top-color:white;border-radius:50%;animation:spin .75s linear infinite}
  @keyframes spin{to{transform:rotate(360deg)}}
  .sidebar-scroll::-webkit-scrollbar,.thin-scroll::-webkit-scrollbar{width:6px}
  .sidebar-scroll::-webkit-scrollbar-thumb,.thin-scroll::-webkit-scrollbar-thumb{background:#d6e3ec;border-radius:99px}
  .report-paper{background:white;box-shadow:0 14px 45px rgba(22,58,87,.10)}
  .heat-legend{background:linear-gradient(90deg,#1f4aff,#20b5e6,#52d46f,#f5e943,#fb5a24,#d7191c)}
  @media print{
    body{background:white}
    .no-print{display:none!important}
    .print-area{display:block!important;margin:0!important;padding:0!important}
    .report-paper{box-shadow:none;border:none!important}
  }
</style>
</head>
<body>
<div id="root"></div>
<script type="text/babel">
const {useState,useEffect,useMemo}=React;

const navItems=[
  ["dashboard","Dashboard","▦"],
  ["newPatient","New Patient","＋"],
  ["patients","Existing Patients","◫"],
  ["analysis","New Analysis","⌁"],
  ["history","Case History","◷"],
  ["compare","Compare Reports","⇄"],
  ["reports","Reports","▤"],
  ["analytics","Analytics","◔"],
  ["hospital","Hospital Integration","⊞"],
  ["cloud","Cloud Storage","☁"],
  ["assistant","AI Assistant","✦"],
  ["settings","Settings","⚙"],
];

const demoPatients=[
 {id:"PT-7734",name:"Jeet Sharma",age:52,gender:"Female",hospitalId:"HSP-204832",doctor:"Dr. Ananya Rao",cases:3,status:"Active"},
 {id:"PT-7741",name:"Nisha Verma",age:47,gender:"Female",hospitalId:"HSP-204901",doctor:"Dr. Arjun Menon",cases:1,status:"Active"},
 {id:"PT-7698",name:"Riya Singh",age:61,gender:"Female",hospitalId:"HSP-204245",doctor:"Dr. Ananya Rao",cases:2,status:"Reviewed"},
];

const demoSpecialists=[
 {name:"Dr. Kavya Mehra",specialty:"Pathologist",hospital:"Apex Institute of Oncology",distance:"2.4 km",phone:"+91 90000 10001"},
 {name:"Dr. Arjun Menon",specialty:"Medical Oncologist",hospital:"City Oncology Centre",distance:"4.1 km",phone:"+91 90000 10002"},
 {name:"Dr. Naina Joseph",specialty:"Surgical Oncologist",hospital:"Metro Cancer Institute",distance:"5.7 km",phone:"+91 90000 10003"},
 {name:"Dr. Ishaan Rao",specialty:"Breast Surgeon",hospital:"Apex Institute of Oncology",distance:"2.4 km",phone:"+91 90000 10004"},
];

const seedResult={
 patientId:"PT-7734",
 prediction:"Likely malignant",
 confidence:87.4,
 malignancyProbability:87.4,
 confidenceBand:"Moderate",
 biomarkers:[
  {name:"ER/PR",priority:"High",rationale:"Prioritize confirmatory receptor testing after pathologist review."},
  {name:"HER2",priority:"High",rationale:"High-priority confirmatory IHC/ISH workflow if invasive malignancy is confirmed."},
  {name:"Ki-67",priority:"Medium",rationale:"Consider proliferative-index testing according to institutional workflow."},
 ],
 report:"AI-assisted assessment suggests a high-risk malignant pattern in the submitted H&E image. The visual attention overlay highlights regions that most influenced the model workflow. Reflex biomarker testing is prioritized for ER/PR and HER2, with Ki-67 as a secondary priority. Findings require pathologist confirmation and must be interpreted alongside morphology and clinical context.",
 modelStatus:"DEMO CASE",
 disclaimer:"AI-assisted decision support only. Pathologist confirmation is required. Prototype pending clinical validation."
};

function badge(priority){
 const p=(priority||"").toLowerCase();
 if(p.includes("high"))return "bg-rose-50 text-rose-700 border-rose-200";
 if(p.includes("medium")||p.includes("moderate"))return "bg-amber-50 text-amber-700 border-amber-200";
 return "bg-emerald-50 text-emerald-700 border-emerald-200";
}

function App(){
 const [logged,setLogged]=useState(()=>localStorage.getItem("ol_login")==="1");
 const [page,setPage]=useState("dashboard");
 const [api,setApi]=useState(()=>localStorage.getItem("ol_api")||"");
 const [backend,setBackend]=useState("idle");
 const [patientId,setPatientId]=useState("PT-7734");
 const [file,setFile]=useState(null);
 const [preview,setPreview]=useState("");
 const [result,setResult]=useState(seedResult);
 const [loading,setLoading]=useState(false);
 const [step,setStep]=useState(1);
 const [viewMode,setViewMode]=useState("original");
 const [reports,setReports]=useState(()=>JSON.parse(localStorage.getItem("ol_reports")||"[]"));
 const [patients,setPatients]=useState(demoPatients);
 const [chat,setChat]=useState([{from:"ai",text:"Hi, I’m OncoLens Assistant. Ask me about the current case, confidence score, heatmap, or biomarker priorities."}]);
 const [chatInput,setChatInput]=useState("");
 const [showSpecialists,setShowSpecialists]=useState(false);

 useEffect(()=>{localStorage.setItem("ol_api",api)},[api]);
 useEffect(()=>{localStorage.setItem("ol_reports",JSON.stringify(reports))},[reports]);

 const analyze=async()=>{
  if(!file){alert("Upload an H&E image first.");return}
  if(!api.trim()){alert("Paste the Ngrok backend URL first.");return}
  setLoading(true); setStep(4);
  try{
   const fd=new FormData(); fd.append("file",file); fd.append("patientId",patientId);
   const res=await fetch(api.replace(/\/+$/,"")+"/analyze",{method:"POST",headers:{"ngrok-skip-browser-warning":"true"},body:fd});
   const data=await res.json();
   if(!res.ok) throw new Error(data.detail||"Analysis failed");
   setResult(data); setViewMode("heatmap"); setBackend("connected"); setStep(5);
   const saved={...data,createdAt:new Date().toISOString(),reportId:"RPT-"+Date.now().toString().slice(-6)};
   setReports(r=>[saved,...r].slice(0,25));
  }catch(e){alert(e.message); setBackend("error"); setStep(3)}
  finally{setLoading(false)}
 };

 const testBackend=async()=>{
  if(!api.trim())return alert("Paste Ngrok URL first.");
  setBackend("testing");
  try{
   const r=await fetch(api.replace(/\/+$/,"")+"/health",{headers:{"ngrok-skip-browser-warning":"true"}});
   if(!r.ok)throw new Error();
   setBackend("connected");
  }catch{setBackend("error");alert("Backend connection failed. Check FastAPI + Ngrok.");}
 };

 const askAI=()=>{
  const q=chatInput.trim(); if(!q)return;
  const low=q.toLowerCase();
  let a="";
  if(low.includes("heatmap")) a="The heatmap shows regions that most influenced the model workflow. It is an explainability aid, not a tumor segmentation map.";
  else if(low.includes("her2")) a=`For case ${result.patientId}, HER2 is currently marked ${result.biomarkers?.find(x=>x.name==="HER2")?.priority||"pending"}. This is a test-priority suggestion only; it does not predict HER2 status.`;
  else if(low.includes("confidence")) a=`The displayed AI confidence is ${Number(result.confidence||0).toFixed(1)}%. This should be interpreted as decision-support output and confirmed by a pathologist.`;
  else if(low.includes("summary")||low.includes("case")) a=result.report||"No case summary is available yet.";
  else if(low.includes("doctor")||low.includes("specialist")){a="I can open the specialist directory for this case. Use the “Find Specialist” action to view the demo directory.";setShowSpecialists(true);}
  else a="I can explain the current case, confidence, heatmap, biomarker priorities, report wording, or specialist options. I do not provide a definitive diagnosis or treatment recommendation.";
  setChat(c=>[...c,{from:"user",text:q},{from:"ai",text:a}]);setChatInput("");
 };

 const onFile=f=>{
  if(!f)return; setFile(f); setPreview(URL.createObjectURL(f)); setStep(2);
  setTimeout(()=>setStep(3),700);
 };

 const printReport=()=>window.print();

 if(!logged)return <Login onLogin={()=>{localStorage.setItem("ol_login","1");setLogged(true)}}/>;

 return <div className="min-h-screen flex">
  <aside className="no-print fixed left-0 top-0 bottom-0 w-[248px] bg-white border-r border-slate-200 z-30 flex flex-col">
   <div className="h-[76px] px-5 flex items-center gap-3 border-b border-slate-100">
    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-700 grid place-items-center text-white text-xl">⌁</div>
    <div><div className="font-bold text-[18px] text-slate-800">OncoLens AI</div><div className="text-[10px] tracking-[.18em] uppercase text-slate-400">Insight Compass</div></div>
   </div>
   <div className="sidebar-scroll overflow-y-auto px-3 py-4 flex-1">
    {navItems.map(([id,label,icon])=><button key={id} onClick={()=>setPage(id)}
      className={`w-full mb-1.5 px-3.5 py-2.5 rounded-xl flex items-center gap-3 text-[13px] font-medium transition ${page===id?"bg-cyan-50 text-cyan-700":"text-slate-500 hover:bg-slate-50 hover:text-slate-800"}`}>
      <span className="w-5 text-center">{icon}</span><span>{label}</span>
    </button>)}
   </div>
   <div className="p-3 border-t border-slate-100">
    <button onClick={()=>{localStorage.removeItem("ol_login");setLogged(false)}} className="w-full px-3.5 py-2.5 rounded-xl flex items-center gap-3 text-[13px] font-medium text-slate-500 hover:bg-rose-50 hover:text-rose-700">
      <span>↪</span> Logout
    </button>
   </div>
  </aside>

  <div className="ml-[248px] min-h-screen flex-1">
   <header className="no-print sticky top-0 z-20 h-[76px] glass border-b border-slate-200 px-6 flex items-center gap-4">
    <div className="h-10 flex-1 max-w-[520px] bg-slate-50 border border-slate-200 rounded-xl flex items-center px-3 gap-2">
     <span className="text-slate-400">⌕</span><input className="w-full bg-transparent text-sm" placeholder="Search patients, cases, reports..."/>
    </div>
    <div className="ml-auto flex items-center gap-3">
      <div className="hidden xl:flex items-center gap-2">
       <input value={api} onChange={e=>{setApi(e.target.value);setBackend("idle")}} placeholder="Paste Ngrok URL" className="h-9 w-[290px] px-3 rounded-lg border border-slate-200 bg-white text-xs"/>
       <button onClick={testBackend} className="h-9 px-3 rounded-lg border border-slate-200 bg-white text-xs font-semibold">Test</button>
      </div>
      <div className={`h-9 px-3 rounded-full border flex items-center gap-2 text-xs font-semibold ${backend==="connected"?"bg-emerald-50 text-emerald-700 border-emerald-200":backend==="error"?"bg-rose-50 text-rose-700 border-rose-200":"bg-slate-50 text-slate-500 border-slate-200"}`}>
       <span className={`w-2 h-2 rounded-full ${backend==="connected"?"bg-emerald-500":backend==="testing"?"bg-amber-400 pulse":backend==="error"?"bg-rose-500":"bg-slate-300"}`}></span>
       {backend==="connected"?"Backend Connected":backend==="testing"?"Testing...":backend==="error"?"Backend Error":"Backend"}
      </div>
      <button className="w-9 h-9 rounded-full border border-slate-200 bg-white">♢</button>
      <div className="flex items-center gap-2 pl-2">
       <div className="w-9 h-9 rounded-full bg-gradient-to-br from-cyan-100 to-blue-100 grid place-items-center text-cyan-700 font-bold">KM</div>
       <div className="hidden md:block"><div className="text-xs font-semibold text-slate-800">Dr. Kavya Mehra</div><div className="text-[10px] text-slate-400">Pathologist</div></div>
      </div>
    </div>
   </header>

   <main className="p-6 lg:p-8">
    {page==="dashboard" && <Dashboard setPage={setPage} patients={patients} reports={reports} setPatientId={setPatientId}/>}
    {page==="newPatient" && <NewPatient patients={patients} setPatients={setPatients} setPage={setPage}/>}
    {page==="patients" && <Patients patients={patients} setPatientId={setPatientId} setPage={setPage}/>}
    {page==="analysis" && <Analysis patientId={patientId} setPatientId={setPatientId} file={file} onFile={onFile} preview={preview} step={step} setStep={setStep} analyze={analyze} result={result} loading={loading} viewMode={viewMode} setViewMode={setViewMode} setPage={setPage} showSpecialists={()=>setShowSpecialists(true)}/>}
    {page==="history" && <CaseHistory reports={reports} setResult={setResult} setPage={setPage}/>}
    {page==="compare" && <Compare reports={reports.length?reports:[seedResult,{...seedResult,patientId:"PT-7741",prediction:"Likely benign",confidence:82.1,malignancyProbability:17.9}]}/>}
    {page==="reports" && <Reports reports={reports} result={result} setResult={setResult} printReport={printReport} showSpecialists={()=>setShowSpecialists(true)}/>}
    {page==="analytics" && <Analytics reports={reports}/>}
    {page==="hospital" && <Hospital/>}
    {page==="cloud" && <Cloud reports={reports}/>}
    {page==="assistant" && <Assistant chat={chat} input={chatInput} setInput={setChatInput} ask={askAI} result={result}/>}
    {page==="settings" && <Settings api={api} setApi={setApi} testBackend={testBackend} backend={backend}/>}
   </main>
  </div>

  {showSpecialists && <SpecialistModal close={()=>setShowSpecialists(false)}/>}
 </div>
}

function Login({onLogin}){
 const [email,setEmail]=useState("pathologist@oncolens.demo");
 const [pwd,setPwd]=useState("demo");
 return <div className="min-h-screen grid lg:grid-cols-[1.08fr_.92fr] bg-white">
  <section className="hidden lg:flex p-16 xl:p-20 bg-gradient-to-br from-[#0b4b71] via-[#106a8b] to-[#13a9b4] text-white flex-col justify-between">
   <div className="flex items-center gap-3"><div className="w-12 h-12 rounded-2xl bg-white/15 grid place-items-center text-2xl">⌁</div><div><div className="text-xl font-bold">OncoLens AI</div><div className="text-xs text-cyan-100 tracking-[.18em] uppercase">Insight Compass</div></div></div>
   <div className="max-w-xl"><div className="text-sm text-cyan-100 mb-4">AI-assisted pathology decision support</div><h1 className="text-5xl font-bold leading-tight">From H&E slide to explainable clinical insight.</h1><p className="text-cyan-50/85 mt-6 text-lg leading-8">Patient workflow, slide analysis, attention heatmaps, reflex biomarker prioritization, reports, and pathologist review.</p></div>
   <div className="text-xs text-cyan-100">Prototype pending clinical validation • Pathologist-in-the-loop</div>
  </section>
  <section className="flex items-center justify-center p-8"><form onSubmit={e=>{e.preventDefault();onLogin()}} className="w-full max-w-md">
   <div className="text-cyan-700 text-sm font-semibold">Secure clinical workspace</div><h2 className="text-3xl font-bold mt-2 text-slate-800">Welcome back</h2><p className="text-slate-500 mt-2">Sign in to continue to OncoLens.</p>
   <label className="block mt-8 text-sm font-medium">Email<input value={email} onChange={e=>setEmail(e.target.value)} className="mt-2 w-full h-12 px-4 rounded-xl border border-slate-200 bg-slate-50"/></label>
   <label className="block mt-4 text-sm font-medium">Password<input type="password" value={pwd} onChange={e=>setPwd(e.target.value)} className="mt-2 w-full h-12 px-4 rounded-xl border border-slate-200 bg-slate-50"/></label>
   <button className="w-full h-12 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-semibold mt-6 shadow-soft">Sign In</button>
   <div className="mt-5 p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-800">Demo authentication only. Add real RBAC before clinical deployment.</div>
  </form></section>
 </div>
}

function PageTitle({eyebrow,title,subtitle,actions}){return <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-6"><div><div className="text-xs font-bold tracking-[.12em] uppercase text-cyan-600">{eyebrow}</div><h1 className="text-3xl font-bold text-slate-800 mt-1">{title}</h1><p className="text-sm text-slate-500 mt-1">{subtitle}</p></div>{actions}</div>}

function Dashboard({setPage,patients,reports,setPatientId}){
 const cards=[["Total Patients",patients.length,"↑ 12% this month","bg-cyan-50 text-cyan-700"],["Completed Reports",Math.max(12,reports.length),"8 this week","bg-blue-50 text-blue-700"],["Pending Reviews",4,"Needs attention","bg-amber-50 text-amber-700"],["High Priority",3,"Pathologist review","bg-rose-50 text-rose-700"]];
 return <div className="fade">
  <PageTitle eyebrow="Clinical workspace" title="Dashboard" subtitle="Overview of patients, analyses, reports, and current workflow." actions={<div className="flex gap-2"><button onClick={()=>setPage("newPatient")} className="h-10 px-4 rounded-xl border border-cyan-200 bg-cyan-50 text-cyan-700 font-semibold text-sm">＋ New Patient</button><button onClick={()=>setPage("analysis")} className="h-10 px-4 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-semibold text-sm">⌁ New Analysis</button></div>}/>
  <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4">{cards.map(([a,b,c,s])=><div key={a} className="bg-white rounded-2xl border border-slate-200 p-5 shadow-soft"><div className="flex justify-between"><div className="text-xs text-slate-400 uppercase tracking-wider">{a}</div><div className={`w-9 h-9 rounded-xl grid place-items-center ${s}`}>◈</div></div><div className="text-3xl font-bold mt-4">{b}</div><div className="text-xs text-slate-500 mt-2">{c}</div></div>)}</div>
  <div className="grid xl:grid-cols-[1.25fr_.75fr] gap-5 mt-5">
   <section className="bg-white rounded-2xl border border-slate-200 shadow-soft overflow-hidden">
    <div className="px-5 py-4 border-b border-slate-100 flex justify-between items-center"><div><div className="font-semibold">Recent Patients</div><div className="text-xs text-slate-400">Continue patient review or start a new case</div></div><button onClick={()=>setPage("patients")} className="text-xs text-cyan-700 font-semibold">View all</button></div>
    {patients.map(p=><div key={p.id} className="px-5 py-4 border-b border-slate-100 flex items-center gap-4"><div className="w-10 h-10 rounded-full bg-slate-100 grid place-items-center font-semibold text-slate-600">{p.name.split(" ").map(x=>x[0]).join("").slice(0,2)}</div><div className="flex-1"><div className="font-semibold text-sm">{p.name}</div><div className="text-xs text-slate-400">{p.id} • {p.age} yrs • {p.cases} cases</div></div><button onClick={()=>{setPatientId(p.id);setPage("analysis")}} className="h-8 px-3 rounded-lg bg-cyan-50 text-cyan-700 text-xs font-semibold">New Analysis</button></div>)}
   </section>
   <section className="bg-white rounded-2xl border border-slate-200 shadow-soft p-5"><div className="font-semibold">Recent Activity</div><div className="mt-4 space-y-4">{["PT-7734 analysis completed","Report reviewed by Dr. Kavya","HER2 reflex priority updated","New patient PT-7741 added"].map((x,i)=><div key={x} className="flex gap-3"><div className="w-8 h-8 rounded-full bg-cyan-50 text-cyan-700 grid place-items-center text-xs">✓</div><div><div className="text-sm">{x}</div><div className="text-xs text-slate-400">{i+1}h ago</div></div></div>)}</div></section>
  </div>
 </div>
}

function NewPatient({patients,setPatients,setPage}){
 const [form,setForm]=useState({name:"",age:"",gender:"Female",hospitalId:"",doctor:""});
 const save=()=>{if(!form.name)return alert("Enter patient name"); const p={...form,id:"PT-"+Math.floor(7800+Math.random()*150),cases:0,status:"Active"};setPatients([...patients,p]);setPage("patients")};
 return <div className="fade max-w-4xl"><PageTitle eyebrow="Patient Management" title="New Patient" subtitle="Register a de-identified patient profile for the prototype workflow."/>
 <div className="bg-white rounded-2xl border border-slate-200 shadow-soft p-6 grid md:grid-cols-2 gap-5">{[["Full Name","name"],["Age","age"],["Hospital ID","hospitalId"],["Referring Doctor","doctor"]].map(([l,k])=><label key={k} className="text-sm font-medium">{l}<input value={form[k]} onChange={e=>setForm({...form,[k]:e.target.value})} className="mt-2 w-full h-11 rounded-xl border border-slate-200 px-3 bg-slate-50"/></label>)}<label className="text-sm font-medium">Gender<select value={form.gender} onChange={e=>setForm({...form,gender:e.target.value})} className="mt-2 w-full h-11 rounded-xl border border-slate-200 px-3 bg-slate-50"><option>Female</option><option>Male</option><option>Other / Not specified</option></select></label><div className="md:col-span-2 flex justify-end"><button onClick={save} className="h-10 px-5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-semibold text-sm">Save Patient</button></div></div></div>
}

function Patients({patients,setPatientId,setPage}){return <div className="fade"><PageTitle eyebrow="Patient Management" title="Existing Patients" subtitle="Search and continue cases for registered patients."/><div className="grid lg:grid-cols-2 xl:grid-cols-3 gap-4">{patients.map(p=><div key={p.id} className="bg-white rounded-2xl border border-slate-200 shadow-soft p-5"><div className="flex gap-3"><div className="w-11 h-11 rounded-full bg-cyan-50 text-cyan-700 grid place-items-center font-bold">{p.name.split(" ").map(x=>x[0]).join("").slice(0,2)}</div><div><div className="font-semibold">{p.name}</div><div className="text-xs text-slate-400">{p.id} • {p.hospitalId}</div></div></div><div className="grid grid-cols-3 gap-2 mt-5 text-xs"><div className="bg-slate-50 rounded-xl p-3"><div className="text-slate-400">Age</div><div className="font-semibold mt-1">{p.age}</div></div><div className="bg-slate-50 rounded-xl p-3"><div className="text-slate-400">Cases</div><div className="font-semibold mt-1">{p.cases}</div></div><div className="bg-slate-50 rounded-xl p-3"><div className="text-slate-400">Status</div><div className="font-semibold mt-1">{p.status}</div></div></div><div className="mt-4 flex gap-2"><button onClick={()=>{setPatientId(p.id);setPage("analysis")}} className="flex-1 h-9 rounded-lg bg-cyan-600 text-white text-xs font-semibold">New Case</button><button className="flex-1 h-9 rounded-lg border border-slate-200 text-xs font-semibold">View History</button></div></div>)}</div></div>}

function Steps({step}){return <div className="flex items-center gap-2 overflow-x-auto pb-2">{["Case & Upload","Quality Check","Preprocessing","AI Processing","Results"].map((s,i)=>{const n=i+1;return <React.Fragment key={s}><div className={`shrink-0 flex items-center gap-2 ${step>=n?"text-cyan-700":"text-slate-400"}`}><div className={`w-8 h-8 rounded-full grid place-items-center text-xs font-bold ${step>=n?"bg-cyan-600 text-white":"bg-slate-100"}`}>{step>n?"✓":n}</div><div className="text-xs font-semibold">{s}</div></div>{i<4&&<div className={`h-[2px] min-w-8 flex-1 ${step>n?"bg-cyan-400":"bg-slate-200"}`}></div>}</React.Fragment>})}</div>}

function Analysis({patientId,setPatientId,file,onFile,preview,step,setStep,analyze,result,loading,viewMode,setViewMode,setPage,showSpecialists}){
 const shown=viewMode==="heatmap"?(result.heatmapImage||preview):(result.originalImage||preview);
 return <div className="fade">
  <PageTitle eyebrow="AI Pathology Workflow" title="New Analysis" subtitle="Five-step slide review from case details to explainable results."/>
  <div className="bg-white rounded-2xl border border-slate-200 shadow-soft p-5"><Steps step={step}/></div>
  <div className="grid xl:grid-cols-[1.1fr_.9fr] gap-5 mt-5">
   <section className="bg-white rounded-2xl border border-slate-200 shadow-soft overflow-hidden">
    <div className="px-5 py-4 border-b border-slate-100"><div className="font-semibold">Case Details & H&E Upload</div><div className="text-xs text-slate-400">Attach a microscopy image and patient/case information.</div></div>
    <div className="p-5 grid md:grid-cols-2 gap-4">
     <label className="text-xs font-semibold text-slate-600">Patient ID<input value={patientId} onChange={e=>setPatientId(e.target.value)} className="mt-2 w-full h-10 border border-slate-200 rounded-xl px-3 bg-slate-50"/></label>
     <label className="text-xs font-semibold text-slate-600">Sample ID<input defaultValue="SMP-7734-A" className="mt-2 w-full h-10 border border-slate-200 rounded-xl px-3 bg-slate-50"/></label>
     <label className="text-xs font-semibold text-slate-600">Priority<select className="mt-2 w-full h-10 border border-slate-200 rounded-xl px-3 bg-slate-50"><option>Routine</option><option>Urgent</option></select></label>
     <label className="text-xs font-semibold text-slate-600">Referring Doctor<input defaultValue="Dr. Ananya Rao" className="mt-2 w-full h-10 border border-slate-200 rounded-xl px-3 bg-slate-50"/></label>
     <label className="md:col-span-2 text-xs font-semibold text-slate-600">Clinical History<textarea defaultValue="Breast lump; core biopsy submitted for AI-assisted slide review." className="mt-2 w-full h-20 border border-slate-200 rounded-xl px-3 py-2 bg-slate-50"/></label>
    </div>
    <div className="px-5 pb-5">
     <div onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();onFile(e.dataTransfer.files?.[0])}} className="rounded-2xl border-2 border-dashed border-cyan-200 bg-cyan-50/40 min-h-[280px] flex items-center justify-center overflow-hidden">
      {shown?<img src={shown} className="max-h-[390px] max-w-full object-contain"/>:<label className="text-center cursor-pointer p-10"><div className="w-14 h-14 mx-auto rounded-2xl bg-cyan-100 text-cyan-700 grid place-items-center text-2xl">↑</div><div className="font-semibold mt-4">Upload H&E slide image</div><div className="text-xs text-slate-400 mt-2">Drag & drop or click to browse</div><input type="file" accept="image/*" className="hidden" onChange={e=>onFile(e.target.files?.[0])}/></label>}
      {loading&&<div className="absolute inset-0 bg-slate-900/70 grid place-items-center"><div className="text-center text-white"><div className="spinner mx-auto"></div><div className="mt-3 font-semibold">Running AI pipeline</div><div className="text-xs mt-1 text-slate-200">Phikon-v2 → MIL → heatmap → report</div></div></div>}
     </div>
     {file&&<div className="mt-3 text-xs text-slate-500">Selected: <b>{file.name}</b></div>}
     <div className="mt-4 flex flex-wrap gap-2"><button onClick={()=>setStep(2)} className="h-9 px-3 rounded-lg border border-slate-200 text-xs font-semibold">Quality Check</button><button onClick={()=>setStep(3)} className="h-9 px-3 rounded-lg border border-slate-200 text-xs font-semibold">Preprocess</button><button onClick={analyze} className="h-9 px-4 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-xs font-semibold">Run AI Analysis</button></div>
    </div>
   </section>
   <section className="space-y-5">
    {step===2&&<WorkflowCard title="Quality Check" items={[["Resolution","Passed"],["Tissue detected","Yes"],["Blur assessment","Acceptable"],["Stain quality","Acceptable"],["Severe artifacts","Not detected"]]}/>}
    {step===3&&<WorkflowCard title="Preprocessing" items={[["Color conversion","RGB"],["Tissue filtering","Applied"],["Patch size","224 × 224"],["Patch selection","Tissue-rich tiles"],["Feature target","Phikon-v2 CLS embeddings"]]}/>}
    {(step>=4)&&<div className="bg-white rounded-2xl border border-slate-200 shadow-soft p-5">
      <div className="text-xs uppercase tracking-wider text-slate-400 font-bold">Malignancy Assessment</div><div className="flex items-end justify-between mt-3"><div className="text-xl font-bold">{result.prediction}</div><div className="text-3xl font-bold">{Number(result.confidence||0).toFixed(1)}%</div></div><div className="h-2 rounded-full bg-slate-100 mt-4 overflow-hidden"><div className="h-full bg-gradient-to-r from-cyan-500 to-blue-600" style={{width:`${Math.min(100,result.confidence||0)}%`}}></div></div>
      <div className="mt-5 flex gap-2"><button onClick={()=>setViewMode("original")} className={`h-8 px-3 rounded-lg text-xs font-semibold ${viewMode==="original"?"bg-cyan-50 text-cyan-700":"bg-slate-50 text-slate-500"}`}>Original</button><button onClick={()=>setViewMode("heatmap")} className={`h-8 px-3 rounded-lg text-xs font-semibold ${viewMode==="heatmap"?"bg-cyan-50 text-cyan-700":"bg-slate-50 text-slate-500"}`}>Heatmap</button></div>
     </div>}
    {step>=5&&<><div className="bg-white rounded-2xl border border-slate-200 shadow-soft p-5"><div className="font-semibold">Reflex Biomarker Prioritization</div><div className="mt-4 space-y-3">{(result.biomarkers||[]).map(b=><div key={b.name} className="border border-slate-200 rounded-xl p-3"><div className="flex justify-between"><b className="text-sm">{b.name}</b><span className={`text-[10px] px-2 py-1 rounded-full border font-bold uppercase ${badge(b.priority)}`}>{b.priority}</span></div><div className="text-xs text-slate-500 mt-2">{b.rationale}</div></div>)}</div></div>
     <div className="bg-white rounded-2xl border border-slate-200 shadow-soft p-5"><div className="font-semibold">Pathologist Clinical Summary</div><p className="text-sm leading-6 text-slate-600 mt-3">{result.report}</p><div className="mt-4 flex gap-2"><button onClick={()=>setPage("reports")} className="h-9 px-4 rounded-lg bg-cyan-600 text-white text-xs font-semibold">Open Report</button><button onClick={showSpecialists} className="h-9 px-4 rounded-lg border border-slate-200 text-xs font-semibold">Find Specialist</button></div></div></>}
   </section>
  </div>
 </div>
}

function WorkflowCard({title,items}){return <div className="bg-white rounded-2xl border border-slate-200 shadow-soft p-5"><div className="font-semibold">{title}</div><div className="mt-4 space-y-3">{items.map(([a,b])=><div key={a} className="flex justify-between items-center border-b border-slate-100 pb-3 text-sm"><span className="text-slate-500">{a}</span><span className="font-semibold text-emerald-700">{b}</span></div>)}</div></div>}

function CaseHistory({reports,setResult,setPage}){const rows=reports.length?reports:[{...seedResult,createdAt:new Date().toISOString(),reportId:"RPT-773401"}];return <div className="fade"><PageTitle eyebrow="Longitudinal Review" title="Case History" subtitle="Previously analyzed cases and review status."/><div className="bg-white rounded-2xl border border-slate-200 shadow-soft overflow-hidden">{rows.map((r,i)=><div key={i} className="p-5 border-b border-slate-100 grid grid-cols-[1fr_1fr_.8fr_.8fr_auto] gap-4 items-center text-sm"><div><div className="font-semibold">{r.patientId}</div><div className="text-xs text-slate-400">{r.reportId||"RPT-DEMO"}</div></div><div>{r.prediction}</div><div>{Number(r.confidence||0).toFixed(1)}%</div><div className="text-xs text-slate-400">{new Date(r.createdAt||Date.now()).toLocaleString()}</div><button onClick={()=>{setResult(r);setPage("reports")}} className="h-8 px-3 rounded-lg border border-slate-200 text-xs font-semibold">Open</button></div>)}</div></div>}

function Compare({reports}){const a=reports[0]||seedResult,b=reports[1]||seedResult;return <div className="fade"><PageTitle eyebrow="Decision Support" title="Compare Reports" subtitle="Side-by-side comparison of two case outputs."/><div className="grid lg:grid-cols-2 gap-5">{[a,b].map((r,i)=><div key={i} className="bg-white rounded-2xl border border-slate-200 shadow-soft p-5"><div className="text-xs text-slate-400">CASE {i+1}</div><div className="text-xl font-bold mt-1">{r.patientId}</div><div className="mt-5 grid grid-cols-2 gap-3"><Metric l="Prediction" v={r.prediction}/><Metric l="Confidence" v={`${Number(r.confidence||0).toFixed(1)}%`}/></div><div className="mt-5 font-semibold text-sm">Biomarker priorities</div><div className="mt-2 space-y-2">{(r.biomarkers||[]).map(x=><div className="flex justify-between text-sm border-b border-slate-100 pb-2" key={x.name}><span>{x.name}</span><b>{x.priority}</b></div>)}</div></div>)}</div></div>}

function Metric({l,v}){return <div className="rounded-xl bg-slate-50 p-3"><div className="text-[10px] text-slate-400 uppercase">{l}</div><div className="text-sm font-semibold mt-1">{v}</div></div>}

function Reports({reports,result,setResult,printReport,showSpecialists}){const r=result||reports[0]||seedResult;return <div className="fade print-area">
 <div className="no-print"><PageTitle eyebrow="Clinical Documentation" title="Reports" subtitle="Hospital-style AI-assisted pathology report." actions={<div className="flex gap-2"><button onClick={printReport} className="h-10 px-4 rounded-xl border border-slate-200 bg-white text-sm font-semibold">Print</button><button onClick={printReport} className="h-10 px-4 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-sm font-semibold">Download PDF</button></div>}/></div>
 <div className="report-paper border border-slate-200 rounded-2xl max-w-[1050px] mx-auto overflow-hidden">
  <div className="p-8 border-b-4 border-cyan-600 flex justify-between items-start"><div><div className="text-2xl font-bold text-slate-800">Apex Institute of Oncology</div><div className="text-sm text-slate-500 mt-1">Department of Pathology • AI-Assisted Decision Support</div></div><div className="text-right"><div className="text-xl font-bold text-cyan-700">OncoLens AI</div><div className="text-xs text-slate-400 mt-1">Insight Compass Report</div></div></div>
  <div className="p-8 grid md:grid-cols-2 gap-5"><div><div className="text-xs font-bold uppercase tracking-wider text-cyan-700">Patient Details</div><ReportRows rows={[["Patient Name","Jeet Sharma"],["Patient ID",r.patientId],["Hospital ID","HSP-204832"],["Age / Gender","52 / Female"],["Referring Doctor","Dr. Ananya Rao"]]}/></div><div><div className="text-xs font-bold uppercase tracking-wider text-cyan-700">Sample Details</div><ReportRows rows={[["Sample ID","SMP-7734-A"],["Stain","H&E"],["Priority","Routine"],["Report ID",r.reportId||"RPT-DEMO-7734"],["Generated",new Date(r.createdAt||Date.now()).toLocaleString()]]}/></div></div>
  <div className="px-8 pb-8"><div className="text-xs font-bold uppercase tracking-wider text-cyan-700">Clinical History</div><p className="mt-2 text-sm text-slate-600 leading-6">Breast lump; core biopsy submitted for AI-assisted histopathology review.</p></div>
  <div className="px-8 pb-8"><div className="text-xs font-bold uppercase tracking-wider text-cyan-700">AI Assessment</div><div className="mt-3 grid md:grid-cols-3 gap-3"><Metric l="Prediction" v={r.prediction}/><Metric l="Malignancy Probability" v={`${Number(r.malignancyProbability||0).toFixed(1)}%`}/><Metric l="AI Confidence" v={`${Number(r.confidence||0).toFixed(1)}%`}/></div></div>
  <div className="px-8 pb-8"><div className="text-xs font-bold uppercase tracking-wider text-cyan-700">Slide Imaging & Explainability</div><div className="grid md:grid-cols-2 gap-4 mt-3">{r.originalImage?<img src={r.originalImage} className="w-full rounded-xl border border-slate-200"/>:<div className="h-48 rounded-xl bg-slate-100 grid place-items-center text-slate-400">Original H&E</div>}{r.heatmapImage?<img src={r.heatmapImage} className="w-full rounded-xl border border-slate-200"/>:<div className="h-48 rounded-xl bg-slate-100 grid place-items-center text-slate-400">Attention Heatmap</div>}</div><div className="heat-legend h-2 rounded-full mt-3"></div><div className="text-[10px] text-slate-400 mt-1">Low influence → High influence</div></div>
  <div className="px-8 pb-8"><div className="text-xs font-bold uppercase tracking-wider text-cyan-700">Reflex Biomarker Prioritization</div><div className="grid md:grid-cols-3 gap-3 mt-3">{(r.biomarkers||[]).map(b=><div key={b.name} className="border border-slate-200 rounded-xl p-4"><div className="flex justify-between items-center"><b>{b.name}</b><span className={`text-[10px] px-2 py-1 rounded-full border font-bold uppercase ${badge(b.priority)}`}>{b.priority}</span></div><div className="text-xs text-slate-500 mt-2 leading-5">{b.rationale}</div></div>)}</div></div>
  <div className="px-8 pb-8"><div className="text-xs font-bold uppercase tracking-wider text-cyan-700">Pathologist Clinical Summary</div><p className="mt-3 text-sm text-slate-600 leading-6">{r.report}</p></div>
  <div className="p-8 bg-amber-50 border-t border-amber-200 text-xs text-amber-900 leading-5"><b>Important:</b> {r.disclaimer||seedResult.disclaimer}</div>
  <div className="no-print p-6 border-t border-slate-100 flex justify-end gap-2"><button onClick={showSpecialists} className="h-9 px-4 rounded-lg border border-slate-200 text-xs font-semibold">Find Specialist</button><button className="h-9 px-4 rounded-lg bg-emerald-600 text-white text-xs font-semibold">Confirm Reviewed</button></div>
 </div>
</div>}

function ReportRows({rows}){return <div className="mt-3 space-y-2">{rows.map(([a,b])=><div key={a} className="flex justify-between gap-4 text-sm border-b border-slate-100 pb-2"><span className="text-slate-400">{a}</span><span className="font-medium text-right">{b}</span></div>)}</div>}

function Analytics({reports}){const n=Math.max(18,reports.length);return <div className="fade"><PageTitle eyebrow="Operational Intelligence" title="Analytics" subtitle="Demo metrics for the hackathon product story."/><div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4"><MetricCard t="Cases Analyzed" v={n} s="+14%"/><MetricCard t="Avg. Confidence" v="86.2%" s="Demo metric"/><MetricCard t="High Priority" v="31%" s="Requires review"/><MetricCard t="Avg. Turnaround" v="1.8s" s="GPU target"/></div><div className="grid xl:grid-cols-2 gap-5 mt-5"><FakeChart title="Case Volume" bars={[40,55,48,68,80,71,92]}/><FakeChart title="Confidence Distribution" bars={[20,34,56,77,91,68,42]}/></div></div>}
function MetricCard({t,v,s}){return <div className="bg-white border border-slate-200 rounded-2xl shadow-soft p-5"><div className="text-xs text-slate-400 uppercase">{t}</div><div className="text-3xl font-bold mt-3">{v}</div><div className="text-xs text-cyan-700 mt-2">{s}</div></div>}
function FakeChart({title,bars}){return <div className="bg-white border border-slate-200 rounded-2xl shadow-soft p-5"><div className="font-semibold">{title}</div><div className="h-52 flex items-end gap-3 mt-5">{bars.map((h,i)=><div key={i} className="flex-1 rounded-t-lg bg-gradient-to-t from-cyan-500 to-blue-500" style={{height:h+"%"}}></div>)}</div></div>}

function Hospital(){return <div className="fade"><PageTitle eyebrow="Interoperability" title="Hospital Integration" subtitle="Demo integration layer for LIS/HIS/FHIR connectivity."/><div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">{[["Hospital HIS","Sandbox Connected","FHIR R4"],["Laboratory LIS","Demo Ready","HL7 / REST"],["PACS / Slide Archive","Not Connected","DICOM / WSI"],["Audit Log","Enabled","Prototype"],["SSO / Identity","Planned","OAuth / SAML"],["Report Export","Ready","PDF / JSON"]].map(([a,b,c])=><div key={a} className="bg-white border border-slate-200 rounded-2xl shadow-soft p-5"><div className="text-sm font-semibold">{a}</div><div className="mt-4 flex items-center justify-between"><span className="text-xs text-emerald-700 font-semibold">{b}</span><span className="text-[10px] bg-slate-100 rounded-full px-2 py-1">{c}</span></div></div>)}</div><div className="mt-5 p-4 rounded-xl bg-cyan-50 border border-cyan-200 text-sm text-cyan-900"><b>Hackathon demo:</b> These cards represent the planned integration surface. No real hospital system is connected in this prototype.</div></div>}

function Cloud({reports}){return <div className="fade"><PageTitle eyebrow="Data Workspace" title="Cloud Storage" subtitle="Demo file workspace for slides and generated reports."/><div className="grid md:grid-cols-3 gap-4"><MetricCard t="Slide Files" v="24" s="8.6 GB demo"/><MetricCard t="Reports" v={Math.max(12,reports.length)} s="JSON / PDF"/><MetricCard t="Storage Used" v="38%" s="Demo quota"/></div><div className="mt-5 bg-white border border-slate-200 rounded-2xl shadow-soft overflow-hidden">{["PT-7734_slide_A.jpg","PT-7734_heatmap.jpg","RPT-7734.pdf","PT-7741_slide_A.jpg"].map((x,i)=><div key={x} className="px-5 py-4 border-b border-slate-100 flex items-center"><div className="w-9 h-9 rounded-lg bg-cyan-50 text-cyan-700 grid place-items-center">☁</div><div className="ml-3 flex-1"><div className="text-sm font-medium">{x}</div><div className="text-xs text-slate-400">{i<2?"Image":"Report"} • Demo storage</div></div><button className="text-xs font-semibold text-cyan-700">Download</button></div>)}</div></div>}

function Assistant({chat,input,setInput,ask,result}){return <div className="fade max-w-5xl"><PageTitle eyebrow="Case-Aware Copilot" title="AI Assistant" subtitle="Explain current case outputs without making a definitive diagnosis."/><div className="grid lg:grid-cols-[1fr_300px] gap-5"><div className="bg-white rounded-2xl border border-slate-200 shadow-soft overflow-hidden"><div className="h-[520px] thin-scroll overflow-y-auto p-5 space-y-4">{chat.map((m,i)=><div key={i} className={`flex ${m.from==="user"?"justify-end":"justify-start"}`}><div className={`max-w-[78%] rounded-2xl px-4 py-3 text-sm leading-6 ${m.from==="user"?"bg-cyan-600 text-white":"bg-slate-100 text-slate-700"}`}>{m.text}</div></div>)}</div><div className="p-4 border-t border-slate-100 flex gap-2"><input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==="Enter"&&ask()} placeholder="Ask about confidence, heatmap, HER2, report..." className="flex-1 h-11 rounded-xl border border-slate-200 px-3 bg-slate-50"/><button onClick={ask} className="h-11 px-5 rounded-xl bg-cyan-600 text-white font-semibold">Send</button></div></div><div className="bg-white rounded-2xl border border-slate-200 shadow-soft p-5 h-fit"><div className="text-xs text-slate-400 uppercase">Current Case</div><div className="text-xl font-bold mt-1">{result.patientId}</div><div className="mt-4 text-sm font-semibold">{result.prediction}</div><div className="text-3xl font-bold mt-1">{Number(result.confidence||0).toFixed(1)}%</div><div className="mt-5 p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900">The assistant explains model output only. It does not provide a definitive diagnosis or treatment recommendation.</div></div></div></div>}

function Settings({api,setApi,testBackend,backend}){return <div className="fade max-w-4xl"><PageTitle eyebrow="Configuration" title="Settings" subtitle="Prototype hospital, backend, and model settings."/><div className="bg-white border border-slate-200 rounded-2xl shadow-soft p-6 space-y-6"><div><div className="font-semibold">Backend Connection</div><div className="flex gap-2 mt-3"><input value={api} onChange={e=>setApi(e.target.value)} placeholder="https://xxxx.ngrok-free.app" className="flex-1 h-11 rounded-xl border border-slate-200 px-3 bg-slate-50"/><button onClick={testBackend} className="h-11 px-4 rounded-xl bg-cyan-600 text-white font-semibold text-sm">Test</button></div><div className="text-xs text-slate-400 mt-2">Status: {backend}</div></div><div className="grid md:grid-cols-2 gap-4"><label className="text-sm font-medium">Hospital Name<input defaultValue="Apex Institute of Oncology" className="mt-2 w-full h-11 rounded-xl border border-slate-200 px-3 bg-slate-50"/></label><label className="text-sm font-medium">Current User<input defaultValue="Dr. Kavya Mehra" className="mt-2 w-full h-11 rounded-xl border border-slate-200 px-3 bg-slate-50"/></label></div><div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-sm"><b>Model:</b> Phikon-v2 + Attention-MIL when a compatible checkpoint is loaded; otherwise demo fallback mode.</div></div></div>}

function SpecialistModal({close}){return <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm grid place-items-center p-4"><div className="w-full max-w-3xl bg-white rounded-2xl shadow-soft border border-slate-200 overflow-hidden"><div className="p-5 border-b border-slate-100 flex justify-between"><div><div className="font-bold">Find Specialist</div><div className="text-xs text-slate-400">Demo directory — replace with verified provider integration later.</div></div><button onClick={close}>✕</button></div><div className="p-5 grid md:grid-cols-2 gap-4">{demoSpecialists.map(s=><div key={s.name} className="border border-slate-200 rounded-xl p-4"><div className="flex gap-3"><div className="w-10 h-10 rounded-full bg-cyan-50 text-cyan-700 grid place-items-center font-bold">{s.name.split(" ").slice(1).map(x=>x[0]).join("").slice(0,2)}</div><div><div className="font-semibold text-sm">{s.name}</div><div className="text-xs text-cyan-700">{s.specialty}</div><div className="text-xs text-slate-400">{s.hospital} • {s.distance}</div></div></div><div className="flex gap-2 mt-4"><button className="flex-1 h-8 rounded-lg border border-slate-200 text-xs font-semibold">Call</button><button className="flex-1 h-8 rounded-lg bg-cyan-600 text-white text-xs font-semibold">Request Consult</button></div></div>)}</div></div></div>}

ReactDOM.createRoot(document.getElementById("root")).render(<App/>);
</script>
</body>
</html>
'''

(frontend_dir / "index.html").write_text(html, encoding="utf-8")

readme = """# OncoLens V2 — Final Hackathon Frontend + Existing Backend

## What this V2 adds
- Lovable-style fixed left sidebar + top header
- Dashboard
- New Patient
- Existing Patients
- 5-step New Analysis workflow
- Case History
- Compare Reports
- Hospital-format Reports
- Print / Save as PDF
- Analytics demo
- Hospital Integration demo
- Cloud Storage demo
- Case-aware AI Assistant demo
- Specialist / doctor connection demo directory
- Settings page with Ngrok backend URL
- Existing FastAPI / Phikon-v2 / MIL backend copied into this package

## Fastest demo setup

### Windows teammate
1. Open `backend`
2. In CMD:
   `python -m venv .venv`
   `.venv\\Scripts\\activate`
   `pip install -r requirements.txt`
   `python -m uvicorn server:app --host 0.0.0.0 --port 8000`
3. Test `http://127.0.0.1:8000/health`
4. In second CMD:
   `ngrok http 8000`
5. Send the HTTPS Ngrok URL to the Mac teammate.

### Mac teammate
1. Open `frontend/index.html` in Chrome.
2. Sign in with any demo email/password.
3. Paste the Ngrok URL in the top bar or Settings.
4. Click Test.
5. Open New Analysis.
6. Upload an H&E image.
7. Click Run AI Analysis.
8. Open Reports -> Print / Save as PDF.
9. Demo AI Assistant and Find Specialist.

## Important
The AI Assistant, specialist directory, hospital integration, analytics and cloud storage are polished demo modules for the hackathon.
The real end-to-end module is the slide upload -> FastAPI -> model/fallback -> heatmap -> biomarkers -> report flow.

The product must be described as AI-assisted decision support and pathologist-in-the-loop.
"""
(root / "README_FIRST.md").write_text(readme, encoding="utf-8")

zip_path = Path("/mnt/data/OncoLens_V2_Full_Hackathon_App.zip")
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for p in root.rglob("*"):
        if p.is_file():
            z.write(p, p.relative_to(root.parent))
print(zip_path)
print(frontend_dir / "index.html")
