import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { ResponsiveContainer, LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from "recharts";
import "./styles.css";

const API = (import.meta.env.VITE_API_BASE_URL || `${window.location.protocol}//${window.location.hostname}:8000/api/v1`).replace(/\/$/, "");

async function api(path, opts = {}) {
  const token = localStorage.getItem("token");
  const headers = { ...(opts.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  let res;
  try {
    res = await fetch(API + path, { cache: "no-store", ...opts, headers });
  } catch (networkError) {
    const err = new Error(`Cannot reach RetailPulse API at ${API}. Make sure FastAPI is running on port 8000.`);
    err.cause = networkError;
    err.status = 0;
    throw err;
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const err = new Error(data.detail || `Request failed (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

function Header({ title, sub }) {
  return <header><div><h1>{title}</h1><p>{sub}</p></div><div className="status">● System online</div></header>;
}

function Badge({ x }) {
  const cls = String(x || "WATCH").toLowerCase();
  return <span className={`badge ${cls}`}>{x}</span>;
}
function useVoiceInput(setValue){
  const [listening,setListening]=useState(false);
  const supported=typeof window!=="undefined" && ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);
  function start(){
    if(!supported) return;
    const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;
    const recognition=new Recognition();
    recognition.lang="en-IN"; recognition.interimResults=false; recognition.maxAlternatives=1;
    recognition.onstart=()=>setListening(true); recognition.onend=()=>setListening(false);
    recognition.onerror=()=>setListening(false);
    recognition.onresult=(e)=>setValue(e.results?.[0]?.[0]?.transcript||"");
    recognition.start();
  }
  return {listening,supported,start};
}
function simpleLabel(label){
  const map={"Command Center":"Home","Product Intelligence":"My Products","Data Intelligence":"Add Sales","ARIMA Lab":"Forecast","LSTM Lab":"Forecast","Model Evaluation":"Compare Forecasts","Seasonality & Anomalies":"Sales Patterns","Inventory Intelligence":"My Stock","Restock Center":"What to Buy","Scenario Planner":"What-If Plan","Action Center":"Important Alerts","Reports & Analytics":"My Sales","Sunny AI":"Ask Sunny","Settings & Access":"Settings"};
  return map[label]||label;
}

function Login() {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("owner@retailpulse.ai");
  const [password, setPassword] = useState("owner123");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);
  const nav = useNavigate();

  function switchMode(next) {
    setMode(next);
    setError("");
    setSuccess("");
    if (next === "register") {
      setEmail("");
      setPassword("");
      setConfirmPassword("");
    } else {
      setEmail("owner@retailpulse.ai");
      setPassword("owner123");
      setConfirmPassword("");
    }
  }

  async function submit(e) {
    e.preventDefault();
    setError("");
    setSuccess("");
    setLoading(true);
    try {
      const path = mode === "login" ? "/auth/login" : "/auth/register";
      const body = mode === "login"
        ? { email: email.trim(), password }
        : { email: email.trim(), password, confirm_password: confirmPassword };
      const x = await api(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      localStorage.setItem("token", x.access_token);
      localStorage.setItem("role", x.role);
      if (mode === "register") {
        setSuccess("Account created. Opening your workspace…");
        setTimeout(() => nav("/", { replace: true }), 450);
      } else {
        nav("/", { replace: true });
      }
    } catch (e) {
      setError(e.message || (mode === "login" ? "Unable to sign in." : "Unable to create account."));
    } finally {
      setLoading(false);
    }
  }

  const capabilityCards = [
    ["01","FORECAST","ARIMA + LSTM demand intelligence"],
    ["02","INVENTORY","Stock risk & replenishment"],
    ["03","ANALYTICS","Daily → yearly performance"],
    ["04","SUNNY","Grounded AI decisions"],
    ["05","CONTROL","Enterprise roles & access"]
  ];

  return <div className="login-shell">
    <div className="login-noise"/>
    <div className="login-orbit orbit-1"/><div className="login-orbit orbit-2"/>
    <section className="login-visual">
      <div className="login-brand-lockup">
        <div className="brand-symbol">R<span>AI</span></div>
        <div><b>RetailPulse AI</b><small>RETAIL INTELLIGENCE PLATFORM</small></div>
      </div>
      <div className="login-hero-copy">
        <div className="eyebrow">A SIMPLE HELPER FOR YOUR SHOP</div>
        <h1 className="project-title">AI-Driven Demand Forecasting for Indian Retail using Time Series Learning Models</h1>
        <p>See what you sold, what you have, what you may need to buy, and ask Sunny questions in everyday language.</p>
      </div>
      <div className="login-capabilities">
        {capabilityCards.map(([n,title,desc],i)=><div className={`cap-card cap-${i+1}`} key={n}>
          <div className="cap-number">{n}</div>
          <div className="mini-robot"><i/><i/><i/></div>
          <b>{title}</b><span>{desc}</span>
        </div>)}
      </div>
      <div className="login-footnote">Made for shop owners · Simple to use · Your shop data stays in your account</div>
    </section>

    <section className="login-panel">
      <div className="login-panel-inner">
        <div className="mobile-brand"><div className="brand-symbol">R<span>AI</span></div><b>RetailPulse AI</b></div>
        <div className="login-kicker">{mode === "login" ? "WELCOME BACK" : "GET STARTED"}</div>
        <h2>{mode === "login" ? "Sign in to your workspace" : "Create your workspace account"}</h2>
        <p className="login-subtitle">{mode === "login" ? "See your shop sales, stock and helpful suggestions." : "Create your shop account and get started."}</p>

        <div className="login-tabs">
          <button type="button" className={mode === "login" ? "selected" : ""} onClick={() => switchMode("login")}>Sign in</button>
          <button type="button" className={mode === "register" ? "selected" : ""} onClick={() => switchMode("register")}>Create account</button>
        </div>

        <form onSubmit={submit} className="login-form">
          <label>Work email<input required type="email" autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@company.com"/></label>
          <label>Password<div className="password-wrap"><input required minLength={8} autoComplete={mode === "login" ? "current-password" : "new-password"} type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder={mode === "login" ? "Enter your password" : "Create a password (8+ characters)"}/><span>•••</span></div></label>
          {mode === "register" && <label>Confirm password<div className="password-wrap"><input required minLength={8} autoComplete="new-password" type="password" value={confirmPassword} onChange={e=>setConfirmPassword(e.target.value)} placeholder="Re-enter your password"/><span>•••</span></div></label>}
          {mode === "login" && <div className="login-options"><label className="remember"><input type="checkbox"/> <span>Remember me</span></label><span>Secure access</span></div>}
          <button className="login-submit" disabled={loading}>{loading ? (mode === "login" ? "Signing in…" : "Creating account…") : <>{mode === "login" ? "Sign in" : "Create account"} <span>→</span></>}</button>
        </form>

        {error && <div className="error login-error">{error}</div>}
        {success && <div className="success login-success">{success}</div>}
        {mode === "login" && <div className="demo-box"><span>DEMO WORKSPACE</span><b>owner@retailpulse.ai</b><small>owner123</small></div>}
        {mode === "register" && <div className="demo-box signup-note"><span>NEW ACCOUNTS</span><b>Customer access by default</b><small>An owner can change your role later from Settings & Access.</small></div>}
        <div className="login-legal">By continuing, you agree to your organization's workspace policies.</div>
      </div>
    </section>
  </div>;
}

function RequireAuth({ children }) {
  return localStorage.getItem("token") ? children : <Navigate to="/login" replace />;
}

const navGroups = [
  {label:"My Shop", items:[
    ["/", "Home", "dashboard", "⌂"],
    ["/products", "My Products", "products", "◈"],
    ["/inventory", "My Stock", "inventory", "▥"],
    ["/restock-center", "What to Buy", "restock", "↗"],
    ["/reports", "My Sales", "reports", "▤"],
    ["/data", "Add Sales", "data_upload", "＋"],
    ["/copilot", "Ask Sunny", "copilot", "✦"]
  ]},
  {label:"More Tools", items:[
    ["/arima", "Forecast with ARIMA", "arima", "∿"],
    ["/lstm", "Forecast with LSTM", "lstm", "⌁"],
    ["/evaluation", "Compare Forecasts", "model_center", "◎"],
    ["/seasonality", "Sales Patterns", "seasonality", "◌"],
    ["/scenarios", "What-If Plan", "scenarios", "◇"],
    ["/alerts", "Important Alerts", "alerts", "!"]
  ]}
];

function AmbientScene(){return <div className="ambient-scene" aria-hidden="true"><div className="orb orb-a"/><div className="orb orb-b"/><div className="orb orb-c"/><div className="ring ring-a"/><div className="ring ring-b"/><div className="cube cube-a"/><div className="cube cube-b"/><div className="grid-floor"/></div>}

function SunnyWidget(){
  const [open,setOpen]=useState(false);
  const [q,setQ]=useState("");
  const [messages,setMessages]=useState([
    {role:"assistant",content:"Hi, I’m Sunny. You can ask me about your shop in simple words. I’ll answer here."}
  ]);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState("");
  const voice=useVoiceInput(setQ);

  async function ask(text=q){
    const question=String(text||"").trim();
    if(!question||loading)return;
    const next=[...messages,{role:"user",content:question}];
    setMessages(next);setQ("");setLoading(true);setError("");
    try{
      const r=await api("/copilot",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({question,history:next.slice(-8),simple_mode:localStorage.getItem("simpleMode")!=="false",language:"en"})
      });
      setMessages(prev=>[...prev,{role:"assistant",content:r.answer,action:r.action,sources:r.sources||[]}]);
    }catch(e){setError(e.message||"Sunny could not answer right now.")}
    finally{setLoading(false)}
  }

  const suggestions=["What should I buy?","What sold the most?","Do I have enough stock?","How much did I sell?"];

  return <>
    <button className="copilot-fab sunny-fab" onClick={()=>setOpen(v=>!v)} aria-label="Open Sunny">
      <span className="spark">✦</span><span>Sunny</span>
    </button>
    {open&&<section className="copilot-drawer sunny-drawer">
      <div className="copilot-head">
        <div className="sunny-title"><span className="sunny-avatar">✦</span><div><b>Sunny</b><small>Your shop helper</small></div></div>
        <button className="icon-btn" onClick={()=>setOpen(false)}>×</button>
      </div>
      <div className="sunny-messages">
        {messages.map((msg,i)=><div className={`sunny-message ${msg.role}`} key={i}>
          <div className="sunny-message-avatar">{msg.role==="assistant"?"✦":"You"}</div>
          <div><p>{msg.content}</p>{msg.action&&<small className="sunny-action">→ {msg.action}</small>}</div>
        </div>)}
        {loading&&<div className="sunny-message assistant"><div className="sunny-message-avatar">✦</div><div className="sunny-typing"><i/><i/><i/></div></div>}
      </div>
      {messages.length<=1&&<div className="suggestions sunny-suggestions">{suggestions.map(x=><button className="chip" key={x} onClick={()=>ask(x)}>{x}</button>)}</div>}
      {error&&<div className="error">{error}</div>}
      <div className="copilot-input sunny-input">
        <textarea value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();ask()}}} placeholder="Ask Sunny in simple words…" rows="1"/>
        {voice.supported&&<button className="voice-btn" onClick={voice.start} disabled={loading}>{voice.listening?"●":"🎙"}</button>}
        <button onClick={()=>ask()} disabled={!q.trim()||loading}>{loading?"…":"↑"}</button>
      </div>
    </section>}
  </>
}


function Layout({ children }) {
  const [me,setMe]=useState(null),[permissions,setPermissions]=useState([]),[dbStatus,setDbStatus]=useState("checking"),[dark,setDark]=useState(localStorage.getItem("theme")==="dark"),[mobileOpen,setMobileOpen]=useState(false),[simpleMode,setSimpleMode]=useState(localStorage.getItem("simpleMode")!=="false");
  const nav=useNavigate(),location=useLocation();
  useEffect(()=>{api("/auth/me").then(setMe).catch(()=>{});api("/auth/permissions").then(x=>setPermissions(x.permissions||[])).catch(()=>{});api("/health").then(x=>setDbStatus(x.database||"connected")).catch(()=>setDbStatus("offline"))},[]);
  useEffect(()=>{document.documentElement.dataset.theme=dark?"dark":"light";localStorage.setItem("theme",dark?"dark":"light")},[dark]);
  useEffect(()=>{document.documentElement.dataset.simple=simpleMode?"true":"false";localStorage.setItem("simpleMode",String(simpleMode))},[simpleMode]);
  useEffect(()=>{setMobileOpen(false);window.scrollTo({top:0,left:0,behavior:"auto"})},[location.pathname]);
  function signOut(){localStorage.removeItem("token");localStorage.removeItem("role");nav("/login",{replace:true})}
  const visibleGroups=navGroups.map((g,i)=>({...g,items:g.items.filter(([, ,perm])=>permissions.includes(perm)),hiddenInSimple:i===1})).filter(g=>g.items.length && (!simpleMode || !g.hiddenInSimple));
  return <div className={`app ${simpleMode?"simple-user-mode":""}`}><AmbientScene/>
    <button className="mobile-menu" onClick={()=>setMobileOpen(v=>!v)} aria-label="Toggle navigation">☰</button>
    {mobileOpen&&<div className="nav-backdrop" onClick={()=>setMobileOpen(false)}/>} 
    <aside className={mobileOpen?"sidebar-open":""}>
      <div className="brand-mark" onClick={()=>nav("/")} role="button" tabIndex="0"><span>R</span><div><b>RetailPulse <em>AI</em></b><small>{simpleMode?"YOUR SHOP HELPER":"AI RETAIL PLATFORM"}</small></div></div>
      {me&&<div className="identity"><span className="online-dot"/><div><b>{simpleMode?"Shop account":me.role}</b><small>{me.store?.name||"My shop"}</small></div></div>}
      <div className="sidebar-scroll">
        {visibleGroups.map(group=><section className="nav-group" key={group.label}>
          <div className="nav-label">{simpleMode && group.label==="My Shop" ? "MY SHOP" : group.label}</div>
          <nav className="side-nav">{group.items.map(([u,label,perm,icon])=><Link key={u} to={u} title={label} className={location.pathname===u?"active":""}><span className="nav-icon">{icon}</span><span>{simpleMode?simpleLabel(label):label}</span>{location.pathname===u&&<i className="nav-active-dot"/>}</Link>)}</nav>
        </section>)}
        {permissions.includes("settings")&&<section className="nav-group"><div className="nav-label">Administration</div><nav className="side-nav"><Link to="/settings" className={location.pathname==="/settings"?"active":""}><span className="nav-icon">⚙</span><span>Settings & Access</span>{location.pathname==="/settings"&&<i className="nav-active-dot"/>}</Link></nav></section>}
      </div>
      <div className="side-bottom"><button onClick={()=>setDark(v=>!v)}>{dark?"☀  Light mode":"☾  Dark mode"}</button><button onClick={signOut}>↪  Sign out</button></div>
    </aside>
    <main><div className="topbar"><div className="breadcrumbs"><b>RetailPulse AI</b><span>/</span>{me?.store?.name||"Store"}<span className="workspace-context">{simpleMode?"My shop":"Live workspace"}</span></div><div className="top-actions"><button className="simple-toggle" onClick={()=>setSimpleMode(v=>!v)}>{simpleMode?"✓ Simple view":"⚙ Detailed view"}</button>{!simpleMode&&<span className="quick-search">⌘ K <small>Quick navigation</small></span>}<span className="system-pill"><i/> {dbStatus === "offline" ? "Not connected" : dbStatus === "checking" ? "Checking…" : "All data saved"}</span>{permissions.includes("copilot")&&<Link className="top-copilot" to="/copilot">✦ Ask Sunny</Link>}</div></div>{children}</main>
    {permissions.includes("copilot")&&<SunnyWidget/>}
  </div>;
}

function RoleGate({permission,children}){const [allowed,setAllowed]=useState(null);useEffect(()=>{api("/auth/permissions").then(x=>setAllowed((x.permissions||[]).includes(permission))).catch(()=>setAllowed(false))},[permission]);if(allowed===null)return <Layout><div className="loading">Checking access…</div></Layout>;if(!allowed)return <Layout><Header title="Access restricted" sub="Your role does not have access to this feature."/><div className="access-denied"><div className="access-icon">🔒</div><h2>Permission required</h2><p>Ask the workspace owner to grant access if you need this capability.</p></div></Layout>;return children;}

function useLoad(path, deps = []) {
  const [data, setData] = useState(null), [error, setError] = useState(""), [loading, setLoading] = useState(true);
  useEffect(() => { let alive = true; setLoading(true); api(path).then(x => alive && setData(x)).catch(e => alive && setError(e.message)).finally(() => alive && setLoading(false)); return () => { alive = false; }; }, deps);
  return { data, error, loading, setData };
}

function Dashboard(){
  const { data:d, error, loading } = useLoad("/dashboard", []);
  if (loading) return <Layout><div className="loading">Loading your shop summary…</div></Layout>;
  if (error) return <Layout><Header title="Home" sub="Your shop at a glance"/><div className="error">{error}</div></Layout>;
  const k=d?.kpis||{};
  const trend=(d?.trend||[]).map(x=>({date:String(x.date).slice(5),units:Number(x.units)||0}));
  return <Layout><Header title="Home" sub="Simple view of sales, stock and demand"/>
    <div className="simple-welcome"><div><span className="eyebrow">YOUR SHOP</span><h2>Here is what needs attention.</h2><p>Everything here comes from the sales and stock you added.</p></div><Link className="sunny-big-action" to="/copilot">✦ Ask Sunny a question</Link></div>
    <div className="cards simple-kpis">{[["Products",k.products,"items"],["Sold in 30 days",k.sales_units_30d,"units"],["Stock now",k.stock_units,"units"],["Low stock",k.low_stock_products,"items"]].map(([a,b,c])=><div className="card" key={a}><small>{a}</small><strong>{b??"—"}</strong><span className="kpi-helper">{c}</span></div>)}</div>
    <div className="panel chart-panel accurate-chart"><div className="panel-title"><div><h2>How much did I sell?</h2><p>Move your mouse over the line to see the exact number sold on each date.</p></div></div>
      <ResponsiveContainer width="100%" height={330}><LineChart data={trend} margin={{top:15,right:20,left:5,bottom:15}}><CartesianGrid strokeDasharray="3 3" opacity={.18}/><XAxis dataKey="date" tick={{fontSize:11}}/><YAxis allowDecimals={false} tick={{fontSize:11}}/><Tooltip formatter={(v)=>[Number(v).toLocaleString("en-IN"),"Units sold"]}/><Line type="monotone" dataKey="units" name="Units sold" stroke="currentColor" strokeWidth={3} dot={false}/></LineChart></ResponsiveContainer>
    </div>
    <div className="comparison"><div className="panel"><h2>Top-selling products</h2><Table headers={["Product","SKU","Units sold"]} rows={(d?.top_products||[]).map(x=>[x.product,x.sku,x.units])}/></div>
      <div className="panel"><h2>Forecast summary</h2><Table headers={["Product","Model","Error","Expected units"]} rows={(d?.forecast_summary||[]).map(x=>[x.product_id,x.model,x.mape==null?"—":`${Number(x.mape).toFixed(2)}%`,x.forecast_total])}/></div></div>
  </Layout>;
}

function Table({ headers, rows }) { return <div className="table-scroll"><table><thead><tr>{headers.map(h => <th key={h}>{h}</th>)}</tr></thead><tbody>{rows.length ? rows.map((r,i)=><tr key={i}>{r.map((v,j)=><td key={j}>{v}</td>)}</tr>) : <tr><td colSpan={headers.length} className="empty">No data available</td></tr>}</tbody></table></div>; }

function Products() {
  const { data, error, loading } = useLoad("/products", []);
  const [query,setQuery]=useState("");
  const [company,setCompany]=useState("ALL");
  const [category,setCategory]=useState("ALL");
  const rows=data||[];
  const companies=["ALL",...Array.from(new Set(rows.map(p=>p.company).filter(Boolean))).sort()];
  const categories=["ALL",...Array.from(new Set(rows.map(p=>p.category).filter(Boolean))).sort()];
  const filtered=rows.filter(p=>{
    const q=query.trim().toLowerCase();
    const text=`${p.name||""} ${p.brand||""} ${p.company||""} ${p.sku||""}`.toLowerCase();
    return (!q||text.includes(q))&&(company==="ALL"||p.company===company)&&(category==="ALL"||p.category===category);
  });
  if (loading) return <Layout><div className="loading">Loading global product catalog…</div></Layout>;
  return <Layout><Header title="My Products" sub="See your products, prices and how much is left."/>
    {error&&<div className="error">{error}</div>}
    <div className="catalog-hero">
      <div><span className="eyebrow">MY PRODUCTS</span><h2>Everything I sell</h2><p>Find a product, see its price and check how many are left.</p></div>
      <div className="catalog-count"><strong>{filtered.length}</strong><span>products</span></div>
    </div>
    <div className="catalog-toolbar">
      <input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Find a product…"/>
      <select value={company} onChange={e=>setCompany(e.target.value)}>{companies.map(x=><option key={x}>{x}</option>)}</select>
      <select value={category} onChange={e=>setCategory(e.target.value)}>{categories.map(x=><option key={x}>{x}</option>)}</select>
      <Link className="outline" to="/restock-center">View replenishment →</Link>
    </div>
    <div className="catalog-grid">{filtered.map(p=><article className="product premium-product" key={p.id}>
      <div className="product-company"><span>{p.company||"Imported Catalog"}</span><span className="brand-pill">{p.brand||"—"}</span></div>
      <div className="product-top"><span>{p.sku}</span><span>{p.category||"General"} · {p.subcategory||"Product"}</span></div>
      <h2>{p.name}</h2>
      <div className="price-line"><strong>{p.currency||"INR"} {Number(p.unit_price||0).toLocaleString("en-IN")}</strong><span>Price each</span></div>
      <div className="mini"><span>Left<b>{Number(p.current_stock||0).toLocaleString("en-IN")}</b></span><span>Keep aside<b>{Number(p.safety_stock||0).toLocaleString("en-IN")}</b></span><span>Delivery<b>{p.lead_time_days}d</b></span></div>
      <div className="product-meta"><span>Earning</span><b>{p.unit_price&&p.unit_cost?`${Math.max(0,((p.unit_price-p.unit_cost)/p.unit_price*100)).toFixed(1)}%`:"—"}</b><span>Seller</span><b>{p.supplier||"—"}</b></div>
      <Link className="outline" to="/restock-center">See what to buy →</Link>
    </article>)}</div>
    {!filtered.length&&<div className="empty panel">No products match your filters.</div>}
  </Layout>;
}

function Data() {
  const [file,setFile]=useState(null),[result,setResult]=useState(null),[msg,setMsg]=useState(""),[loading,setLoading]=useState(false),[clearing,setClearing]=useState(false),[me,setMe]=useState(null),[dragging,setDragging]=useState(false),[diagnostic,setDiagnostic]=useState(null);
  useEffect(()=>{
    Promise.allSettled([api("/auth/me"),api("/system/diagnostics")]).then(([meResult,diagResult])=>{
      if(meResult.status==="fulfilled") setMe(meResult.value);
      if(diagResult.status==="fulfilled") setDiagnostic(diagResult.value);
      else if(diagResult.reason?.status===401) setMsg("Your session has expired. Sign in again.");
    });
  },[]);
  async function replaceDataset(){
    if(!file){setMsg("Choose a CSV or Excel dataset first.");return}
    if(!window.confirm("Replace ALL products, sales, forecasts and alerts for this store with this dataset? This cannot be undone."))return;
    setLoading(true);setMsg("");setResult(null);
    try{
      const fd=new FormData();fd.append("file",file);
      const role=me?.role || localStorage.getItem("role");
      const endpoint=role==="OWNER"?"/data/replace":"/data/upload";
      const x=await api(endpoint,{method:"POST",body:fd});
      if(x.status!=="success"){
        setResult(x);setMsg(x.message||"Dataset was analyzed but not imported. Check the required columns.");return;
      }
      const verification=await api("/system/diagnostics");
      setDiagnostic(verification);
      const expected=Number(x.products_detected||0);
      const actual=Number(verification.products||0);
      if(expected>0 && actual<expected){
        setMsg(`Import verification failed: API reported ${expected} products but the database currently has ${actual}.`);
        return;
      }
      setResult(x);
      setMsg(`Dataset imported and verified: ${actual} products and ${Number(verification.sales||0)} sales records are now in PostgreSQL.`);
    }catch(e){setMsg(e.message||"Dataset import failed. Check the backend terminal.")}finally{setLoading(false)}
  }
  async function clearDataset(){
    if(!window.confirm("DELETE ALL PRODUCTS and all related sales, forecasts and alerts for this store? This cannot be undone."))return;
    setClearing(true);setMsg("");setResult(null);
    try{
      const x=await api("/data/reset",{method:"POST"});
      const verification=await api("/system/diagnostics");
      setDiagnostic(verification);
      setMsg(`${x.products_deleted} products removed. PostgreSQL now has ${verification.products??0} products and ${verification.sales??0} sales.`);
    }catch(e){setMsg(e.message)}finally{setClearing(false)}
  }
  const a=result?.analysis;
  return <Layout><Header title="Add Sales" sub="Add your sales file so Sunny can understand your shop."/>
    <div className="panel upload"><h2>Dataset Manager</h2><p className="muted">Upload CSV or Excel. The system validates columns, cleans records, analyzes demand, then replaces the current store dataset.</p>
      <div className="pipeline"><div><b>1. ADD</b><br/>Your sales file</div><div className="pipe-line" aria-hidden="true">→</div><div><b>2. CHECK</b><br/>We check it</div><div className="pipe-line" aria-hidden="true">→</div><div><b>3. UNDERSTAND</b><br/>We read your sales</div><div className="pipe-line" aria-hidden="true">→</div><div><b>4. READY</b><br/>Ask Sunny</div></div>
      <div className={`dropzone ${dragging?"dragging":""}`}
        onDragOver={e=>{e.preventDefault();setDragging(true)}}
        onDragLeave={()=>setDragging(false)}
        onDrop={e=>{e.preventDefault();setDragging(false);const f=e.dataTransfer.files?.[0];if(f)setFile(f)}}>
        <input id="dataset-file" type="file" accept=".csv,.xlsx,.xls" onChange={e=>setFile(e.target.files?.[0]||null)}/>
        <label htmlFor="dataset-file"><span className="upload-icon">↑</span><b>{file?file.name:"Drop your retail dataset here"}</b><small>CSV, XLSX or XLS · up to 25 MB</small></label>
      </div>
      {file&&<p className="note">Selected: <b>{file.name}</b> · {Math.max(0.01,file.size/1024/1024).toFixed(2)} MB</p>}
      <div className="actions"><button onClick={replaceDataset} disabled={loading||clearing||!file}>{loading?(me?.role==="OWNER"?"Analyzing & replacing…":"Analyzing & importing…"):(me?.role==="OWNER"?"Upload & Replace Dataset":"Upload & Analyze Dataset")}</button>{me?.role==="OWNER"&&<button className="danger-btn" onClick={clearDataset} disabled={loading||clearing}>{clearing?"Removing…":"Remove All Products"}</button>}</div>
      {diagnostic&&<div className="data-db-status"><span>● PostgreSQL</span><b>{diagnostic.products??0}</b> products <b>{diagnostic.sales??0}</b> sales · schema {diagnostic.schema_ready?"ready":"needs migration"}{diagnostic.date_start&&<> · {diagnostic.date_start} → {diagnostic.date_end}</>}</div>}
      {msg&&<p className={/imported|verified|removed/i.test(msg)?"success":"note"}>{msg}</p>}
      {result?.status==="success"&&<div className="dataset-control-plane">
        <div><span className="eyebrow">YOUR SHOP DATA</span><b>Sunny and your shop screens use the same sales information.</b><small>Add your latest file whenever you want to update your shop.</small></div>
        <div className="dataset-links">
          <Link to="/inventory">Inventory</Link><Link to="/scenarios">Scenarios</Link><Link to="/reports">Reports</Link><Link to="/copilot">Sunny</Link>
        </div>
      </div>}
    </div>
    {result&&<>
      <div className="cards"><div className="card"><small>File check</small><strong>{result.quality?.score ?? "—"}/100</strong></div><div className="card"><small>Products</small><strong>{a?.products ?? result.products_detected}</strong></div><div className="card"><small>Sales entries</small><strong>{a?.sales_records ?? result.records_inserted}</strong></div><div className="card"><small>Total sold</small><strong>{a?.total_units ?? "—"}</strong></div><div className="card"><small>Sales dates</small><strong>{a?`${a.date_start} → ${a.date_end}`:"—"}</strong></div><div className="card"><small>Ready</small><strong>{result.readiness?.ready?"YES":"NO"}</strong></div></div>
      <div className="comparison"><div className="panel"><h2>File check</h2><Table headers={["Check","Score"]} rows={[["Completeness",`${result.quality?.completeness??0}%`],["Validity",`${result.quality?.validity??0}%`],["Consistency",`${result.quality?.consistency??0}%`],["Duplicates",`${result.quality?.duplicates??0}%`]]}/>{result.quality?.issues?.length>0&&<p className="note">Issues: {result.quality.issues.join(" · ")}</p>}</div><div className="panel"><h2>Can Sunny use this?</h2><Table headers={["Requirement","Status"]} rows={(result.readiness?.checks||[]).map(x=>[x.name,x.passed?"✓ Passed":"✕ Needs attention"])}/><p className={result.readiness?.ready?"success":"note"}>{result.readiness?.message}</p></div></div>
      <div className="panel"><h2>Dataset Analysis</h2><p>Average daily units: <b>{a?.average_daily_units ?? "—"}</b></p><p>Products with at least 45 days of history: <b>{a?.forecast_ready_products ?? 0}</b></p><h3>Top Products</h3><Table headers={["Product","Units"]} rows={(a?.top_products||[]).map(x=>[x.product,x.units])}/></div>
    </>}
  </Layout>;
}

function ModelLab({ type }) {
  const [products,setProducts]=useState([]),[pid,setPid]=useState(""),[h,setH]=useState(30),[r,setR]=useState(null),[error,setError]=useState(""),[loading,setLoading]=useState(false);
  useEffect(()=>{api("/products").then(x=>{setProducts(x);if(x[0])setPid(String(x[0].id))}).catch(e=>setError(e.message))},[]);
  async function run(){setLoading(true);setError("");try{setR(await api(`/forecast/${type.toLowerCase()}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:Number(pid),horizon:Number(h),models:[type]})}))}catch(e){setError(e.message)}finally{setLoading(false)}}
  return <Layout><Header title={`${type} Lab`} sub={`${type} forecasting engine`}/><div className="panel controls"><select value={pid} onChange={e=>setPid(e.target.value)}>{products.map(p=><option value={p.id} key={p.id}>{p.name}</option>)}</select><select value={h} onChange={e=>setH(e.target.value)}><option>7</option><option>30</option><option>60</option><option>90</option></select><button onClick={run} disabled={!pid||loading}>{loading?"Training…":`Run ${type}`}</button></div>{error&&<div className="error">{error}</div>}{r&&<><div className="cards"><div className="card"><small>MAE</small><strong>{Number(r.metrics.mae).toFixed(2)}</strong></div><div className="card"><small>RMSE</small><strong>{Number(r.metrics.rmse).toFixed(2)}</strong></div><div className="card"><small>MAPE</small><strong>{Number(r.metrics.mape).toFixed(2)}%</strong></div><div className="card"><small>Validation Days</small><strong>{r.validation?.validation_days??"—"}</strong></div></div><div className="panel"><div className="panel-title"><div><h2>{type} Forecast</h2><p>{type==="LSTM"?`Neural sequence model · lookback ${r.lookback??"—"} · ${r.training?.epochs_ran??r.epochs_requested??"—"} epochs`: `Statistical model · order ${(r.order||[]).join(",")||"—"} · AIC ${Number(r.aic??0).toFixed(2)}`}</p></div></div><Table headers={["Date","Forecast"]} rows={r.forecast.map(x=>[x.date,Number(x.value).toFixed(2)])}/></div></>}</Layout>;
}

function Evaluation(){
  const [products,setProducts]=useState([]),[pid,setPid]=useState(""),[r,setR]=useState(null),[error,setError]=useState(""),[loading,setLoading]=useState(false);
  useEffect(()=>{api("/products").then(x=>{setProducts(x);if(x[0])setPid(String(x[0].id))}).catch(e=>setError(e.message))},[]);
  async function run(){
    setLoading(true);setError("");
    try{
      setR(await api("/evaluation/compare",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:Number(pid),horizon:30,models:["ARIMA","LSTM"]})}));
    }catch(e){setError(e.message)}finally{setLoading(false)}
  }
  const winner=(r?.models||[]).find(x=>x.model===r?.winner);
  return <Layout>
    <Header title="Model Evaluation" sub="Leakage-safe ARIMA vs LSTM comparison on the same chronological holdout"/>
    <div className="panel controls">
      <select value={pid} onChange={e=>{setPid(e.target.value);setR(null)}}>{products.map(p=><option value={p.id} key={p.id}>{p.name}</option>)}</select>
      <button onClick={run} disabled={!pid||loading}>{loading?"Running strict backtest…":"Compare Models"}</button>
    </div>
    {error&&<div className="error">{error}</div>}
    {r&&<>
      <div className="cards">
        <div className="card"><small>Winner</small><strong>{r.winner}</strong></div>
        <div className="card"><small>Primary Metric</small><strong>{r.primary_metric}</strong></div>
        <div className="card"><small>Forecast Accuracy*</small><strong>{Number(r.best_accuracy_pct??0).toFixed(2)}%</strong></div>
        <div className="card"><small>Validation</small><strong>{r.validation_protocol_short||"Same chronological holdout"}</strong></div>
      </div>
      <div className="panel">
        <div className="panel-title"><div><h2>Executive Model Scorecard</h2><p>Both models are judged on exactly the same future dates. Lower sMAPE, MAPE, RMSE, MAE and WMAPE are better.</p></div></div>
        <div className="accuracy-bars">
          {(r.models||[]).map(x=><div className="accuracy-row" key={x.model}>
            <div><b>{x.model}</b><span>{Number(x.accuracy_pct??0).toFixed(2)}% derived forecast score · sMAPE {Number(x.smape??0).toFixed(2)}%</span></div>
            <div className="accuracy-track"><i style={{width:`${Math.max(0,Math.min(100,Number(x.accuracy_pct??0)))}%`}}/></div>
          </div>)}
        </div>
        {r.relative_error_improvement_pct!=null&&<p className="note"><b>Winner advantage:</b> {Number(r.relative_error_improvement_pct).toFixed(2)}% lower sMAPE than the runner-up on the same holdout.</p>}
      </div>
      <div className="panel">
        <Table headers={["Rank","Model","Score","sMAPE","WMAPE","MAPE","RMSE","MAE","Validation Days"]} rows={(r.models||[]).map(x=>[
          x.rank,x.model,`${Number(x.accuracy_pct??0).toFixed(2)}%`,`${Number(x.smape??0).toFixed(2)}%`,`${Number(x.wmape??0).toFixed(2)}%`,`${Number(x.mape??0).toFixed(2)}%`,Number(x.rmse??0).toFixed(2),Number(x.mae??0).toFixed(2),x.validation_days
        ])}/>
      </div>
      {r.validation_series&&<div className="panel">
        <div className="panel-title"><div><h2>Validation Reality Check</h2><p>Actual demand vs ARIMA and LSTM predictions for the identical holdout window.</p></div></div>
        <ValidationChart series={r.validation_series}/>
      </div>}
      {winner&&<div className="panel">
        <div className="panel-title"><div><h2>Why {winner.model} won</h2><p>{r.recommendation}</p></div></div>
        <div className="comparison"><div><div className="metric-row"><span>Validation window</span><b>{r.validation_start} → {r.validation_end}</b></div><div className="metric-row"><span>Training data ends</span><b>{r.training_end}</b></div><div className="metric-row"><span>Model selection</span><b>Training-side tuning only</b></div></div><div><div className="metric-row"><span>Best sMAPE</span><b>{Number(winner.smape).toFixed(2)}%</b></div><div className="metric-row"><span>Best WMAPE</span><b>{Number(winner.wmape).toFixed(2)}%</b></div><div className="metric-row"><span>Selection rule</span><b>sMAPE → WMAPE → RMSE → MAE</b></div></div></div>
      </div>}
      <div className="panel"><p className="note"><b>* Forecast Accuracy:</b> this dashboard score is derived as <code>100 − sMAPE</code>. It is a forecasting error-derived score, not classification accuracy. In Reports & Analytics, the X-axis is the date/reporting period and the Y-axis is units sold.</p></div>
    </>}
  </Layout>;
}

function ValidationChart({series}){
  const dates=series?.dates||[], actual=series?.actual||[], arima=series?.ARIMA||[], lstm=series?.LSTM||[];
  const all=[...actual,...arima,...lstm].map(Number).filter(Number.isFinite); const max=Math.max(...all,1),min=Math.min(...all,0),range=Math.max(max-min,1);
  const w=980,h=330,p={l:62,r:24,t:28,b:62};
  const x=i=>p.l+i*(w-p.l-p.r)/Math.max(dates.length-1,1);
  const y=v=>h-p.b-((Number(v)-min)/range)*(h-p.t-p.b);
  const path=vals=>vals.map((v,i)=>(i?'L':'M')+x(i).toFixed(1)+','+y(v).toFixed(1)).join(' ');
  const ticks=[0,.25,.5,.75,1].map(t=>min+t*range);
  return <div className="report-chart-wrap"><svg className="report-chart" viewBox={`0 0 ${w} ${h}`} role="img" aria-label="Validation chart with date on X axis and units sold on Y axis">
    {ticks.map((v,i)=><g key={i}><line x1={p.l} y1={y(v)} x2={w-p.r} y2={y(v)} stroke="currentColor" opacity=".10"/><text x={p.l-10} y={y(v)+4} textAnchor="end">{Number(v).toFixed(0)}</text></g>)}
    <path d={path(actual)} fill="none" stroke="currentColor" strokeWidth="2.5" opacity=".95"/>
    <path d={path(arima)} fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="7 5" opacity=".58"/>
    <path d={path(lstm)} fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="2 5" opacity=".75"/>
    {(dates.length?dates.filter((_,i)=>i===0||i===dates.length-1||i%Math.max(1,Math.ceil(dates.length/5))===0):[]).map((d,i)=>{const idx=dates.indexOf(d);return <text key={d} x={x(idx)} y={h-24} textAnchor="middle">{d}</text>})}
    <text x={w/2} y={h-5} textAnchor="middle">Date / Reporting Period (X-axis)</text>
    <text x="16" y={h/2} transform={`rotate(-90 16 ${h/2})`} textAnchor="middle">Units Sold (Y-axis)</text>
  </svg><div className="chart-legend"><span>● Actual</span><span>┄ ARIMA</span><span>·· LSTM</span></div></div>;
}

function Seasonality(){const [products,setProducts]=useState([]),[pid,setPid]=useState(""),[s,setS]=useState(null),[a,setA]=useState(null),[error,setError]=useState(""),[loading,setLoading]=useState(false);useEffect(()=>{api("/products").then(x=>{setProducts(x);if(x[0])setPid(String(x[0].id))}).catch(e=>setError(e.message))},[]);async function run(){setLoading(true);setError("");try{const [x,y]=await Promise.all([api(`/seasonality?product_id=${pid}`),api(`/anomalies?product_id=${pid}`)]);setS(x);setA(y)}catch(e){setError(e.message)}finally{setLoading(false)}}return <Layout><Header title="Seasonality & Anomalies" sub="Recurring demand patterns and unusual sales behavior"/><div className="panel controls"><select value={pid} onChange={e=>setPid(e.target.value)}>{products.map(p=><option value={p.id} key={p.id}>{p.name}</option>)}</select><button onClick={run} disabled={!pid||loading}>{loading?"Analyzing…":"Analyze"}</button></div>{error&&<div className="error">{error}</div>}{s&&a&&<><div className="cards"><div className="card"><small>Baseline</small><strong>{s.baseline_daily_demand}</strong></div><div className="card"><small>Strongest Day</small><strong>{s.strongest_weekday.label}</strong></div><div className="card"><small>Anomalies</small><strong>{a.anomaly_count}</strong></div></div><div className="comparison"><div className="panel"><h2>Weekly Pattern</h2><Table headers={["Day","Average","Index"]} rows={s.weekday_pattern.map(x=>[x.label,x.average,x.index])}/></div><div className="panel"><h2>Anomalies</h2><Table headers={["Date","Type","Actual","Z-score"]} rows={a.anomalies.map(x=>[x.date,x.type,x.actual,x.z_score])}/></div></div></>}</Layout>}

function RestockCenter(){const {data:d,error,loading}=useLoad("/restock/center",[]);if(loading)return <Layout><div className="loading">Calculating replenishment recommendations…</div></Layout>;return <Layout><Header title="What to Buy" sub="See what you may need to buy next."/>{error&&<div className="error">{error}</div>}<div className="cards">{[["Urgent",d?.urgent],["High",d?.high],["Normal",d?.normal],["Products to Order",d?.products_needing_order],["Recommended Units",d?.recommended_units]].map(([a,b])=><div className="card" key={a}><small>{a}</small><strong>{b??"—"}</strong></div>)}</div><div className="panel"><Table headers={["Priority","Product","Stock","Daily Demand","Reorder Point","Recommended Order"]} rows={(d?.items||[]).map(x=>[<Badge x={x.priority}/>,x.product,x.current_stock,x.planning_daily_demand,x.reorder_point,x.recommended_order])}/></div></Layout>}

function Inventory(){
  const {data:d,error,loading}=useLoad("/inventory",[]);
  if(loading)return <Layout><div className="loading">Building inventory intelligence…</div></Layout>;
  return <Layout><Header title="My Stock" sub="See what you have and what may run out soon."/>
    {error&&<div className="error">{error}</div>}
    <div className="cards">{[["Products",d?.total_products],["Stock Units",d?.total_stock_units],["Critical",d?.critical],["Attention",d?.attention],["Health Score",d?.health_score==null?"—":`${d.health_score}%`]].map(([a,b])=><div className="card" key={a}><small>{a}</small><strong>{b??"—"}</strong></div>)}</div>
    <div className="panel"><div className="panel-title"><div><h2>What may run out?</h2><p>We compare what you have with what you usually sell.</p></div><Link className="outline" to="/restock-center">Open Restock Center →</Link></div>
      <Table headers={["Risk","Product","Stock","Daily Demand","Reorder Point","Days Cover"]} rows={(d?.items||[]).map(x=>[<Badge x={x.inventory_risk}/>,x.product,x.current_stock,x.average_daily_demand,x.reorder_point,x.days_of_cover??"—"])}/>
    </div>
  </Layout>
}

function Scenarios(){
  const [products,setProducts]=useState([]),[pid,setPid]=useState(""),[demand,setDemand]=useState(0),[stock,setStock]=useState(0),[lead,setLead]=useState(0),[safety,setSafety]=useState(0),[h,setH]=useState(30),[r,setR]=useState(null),[error,setError]=useState(""),[loading,setLoading]=useState(false);
  useEffect(()=>{api("/products").then(x=>{setProducts(x);if(x[0])setPid(String(x[0].id))}).catch(e=>setError(e.message))},[]);
  async function run(){
    if(!pid){setError("No product is available. Upload a dataset in Data Intelligence first.");return}
    setLoading(true);setError("");setR(null);
    try{
      const x=await api("/scenarios",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({
        product_id:Number(pid),horizon:Number(h),demand_change_percent:Number(demand)||0,
        stock_change_percent:Number(stock)||0,lead_time_days:Number(lead)||0,
        safety_stock_change_percent:Number(safety)||0
      })});
      setR(x);
    }catch(e){setError(e.message)}
    finally{setLoading(false)}
  }
  return <Layout>
    <Header title="What-If Plan" sub="Try a simple change and see what could happen."/>
    <div className="panel scenario-panel">
      <div className="scenario-panel-head"><div><span className="eyebrow">LIVE DATASET SCENARIO ENGINE</span><h2>Model the impact before you act.</h2><p>Every calculation uses the product and sales data currently loaded in PostgreSQL.</p></div><span className="dataset-live">● Active dataset</span></div>
      <div className="scenario-controls">
        <label>Product<select value={pid} onChange={e=>setPid(e.target.value)} disabled={!products.length}>{products.length?products.map(p=><option value={p.id} key={p.id}>{p.name}</option>):<option value="">No products loaded</option>}</select></label>
        <label>Horizon<select value={h} onChange={e=>setH(e.target.value)}><option>7</option><option>30</option><option>60</option><option>90</option></select></label>
        <label>Demand change %<input type="number" value={demand} onChange={e=>setDemand(e.target.value)}/></label>
        <label>Stock change %<input type="number" value={stock} onChange={e=>setStock(e.target.value)}/></label>
        <label>Lead-time days<input type="number" min="0" value={lead} onChange={e=>setLead(e.target.value)} placeholder="0 = current"/></label>
        <label>Safety-stock %<input type="number" value={safety} onChange={e=>setSafety(e.target.value)}/></label>
      </div>
      <div className="scenario-actions"><button onClick={run} disabled={!pid||loading}>{loading?"Calculating scenario…":"Run Scenario"}</button><span>Tip: try +20% demand or +7 lead-time days.</span></div>
    </div>
    {error&&<div className="error">{error}</div>}
    {r&&<div className="scenario-result">
      <div className="cards">{[["Scenario Demand / Day",r.scenario_daily_demand],["Reorder Point",r.reorder_point],["Recommended Order",r.recommended_order],["Days of Cover",r.days_of_cover??"—"],["Risk",r.risk]].map(([a,b])=><div className="card" key={a}><small>{a}</small><strong>{b}</strong></div>)}</div>
      <div className="comparison"><div className="panel"><h2>Scenario Decision</h2><Table headers={["Metric","Value"]} rows={[["Product",r.product],["Base demand/day",r.base_daily_demand],["Scenario demand/day",r.scenario_daily_demand],["Available stock",r.available_stock],["Lead time",`${r.scenario_lead_time_days} days`],["Safety stock",r.scenario_safety_stock],["Target stock",r.target_stock],["Risk",<Badge x={r.risk}/>]]}/></div><div className="panel scenario-insight"><span className="eyebrow">SUNNY-READY INSIGHT</span><h2>{r.risk==="CRITICAL"?"Action required":r.risk==="ATTENTION"?"Monitor closely":"Inventory position is healthy"}</h2><p>{r.recommended_order>0?`The scenario suggests ordering approximately ${Number(r.recommended_order).toFixed(0)} units to reach the modeled target stock.`:"No additional order is required under this scenario."}</p><Link to="/copilot" className="report-action">Ask Sunny about this scenario →</Link></div></div>
    </div>}
    {!r&&!error&&<div className="empty-state"><div className="empty-icon">◇</div><h2>Ready for a what-if analysis</h2><p>Select a product and change one assumption. Sunny and the rest of the platform will use the same active dataset.</p></div>}
  </Layout>;
}

function Alerts(){const {data:d,error,loading}=useLoad("/alerts",[]);if(loading)return <Layout><div className="loading">Loading action center…</div></Layout>;return <Layout><Header title="Important Alerts" sub="Things you may want to look at now."/>{error&&<div className="error">{error}</div>}<div className="cards">{[["Critical",d?.critical],["High",d?.high],["Medium",d?.medium],["Total",d?.total]].map(([a,b])=><div className="card" key={a}><small>{a}</small><strong>{b??"—"}</strong></div>)}</div><div className="panel"><Table headers={["Severity","Type","Alert","SKU"]} rows={(d?.alerts||[]).map(a=>[<Badge x={a.severity}/>,a.type,<><b>{a.title}</b><br/><span className="muted">{a.message}</span></>,a.sku])}/></div></Layout>}

function MiniLineChart({series=[]}){
  const data=(series||[]).map(x=>({
    date:String(x.label||"").slice(0,16),
    units:Number(x.units)||0
  }));
  return <div className="report-chart-wrap accurate-chart">
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{top:15,right:20,left:5,bottom:20}}>
        <CartesianGrid strokeDasharray="3 3" opacity={.18}/>
        <XAxis dataKey="date" tick={{fontSize:10}}/>
        <YAxis allowDecimals={false} tick={{fontSize:10}}/>
        <Tooltip formatter={(v)=>[Number(v).toLocaleString("en-IN"),"Units sold"]}/>
        <Line type="monotone" dataKey="units" name="Units sold" stroke="currentColor" strokeWidth={3} dot={false}/>
      </LineChart>
    </ResponsiveContainer>
    <div className="chart-axis-note">Sales trend · X-axis: reporting period · Y-axis: units sold</div>
  </div>;
}

function MiniBarChart({series=[]}){
  const data=(series||[]).map(x=>({
    label:String(x.label||"").slice(0,16),
    units:Number(x.units)||0
  }));
  return <div className="report-chart-wrap accurate-chart">
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{top:15,right:20,left:5,bottom:35}}>
        <CartesianGrid strokeDasharray="3 3" opacity={.18}/>
        <XAxis dataKey="label" tick={{fontSize:9}} interval={data.length>16?Math.ceil(data.length/12):0}
          angle={data.length>12?-35:0} textAnchor={data.length>12?"end":"middle"}/>
        <YAxis allowDecimals={false} tick={{fontSize:10}}/>
        <Tooltip formatter={(v)=>[Number(v).toLocaleString("en-IN"),"Units sold"]}/>
        <Bar dataKey="units" name="Units sold" fill="currentColor" radius={[4,4,0,0]}/>
      </BarChart>
    </ResponsiveContainer>
    <div className="chart-axis-note">Period comparison · X-axis: reporting period · Y-axis: units sold</div>
  </div>;
}

function SalesCategoryChart({categories=[]}){
  const data=(categories||[]).map(x=>({
    name:String(x.category||"Other"),
    units:Number(x.units)||0
  }));
  if(!data.length) return <div className="empty-state compact"><p>No category sales data available.</p></div>;
  return <div className="report-chart-wrap accurate-chart">
    <ResponsiveContainer width="100%" height={320}>
      <PieChart>
        <Pie data={data} dataKey="units" nameKey="name" cx="50%" cy="48%" outerRadius={105}
          label={({name,percent})=>`${name} ${(percent*100).toFixed(0)}%`}>
          {data.map((_,i)=><Cell key={`slice-${i}`}/>)}
        </Pie>
        <Tooltip formatter={(v)=>[Number(v).toLocaleString("en-IN"),"Units sold"]}/>
        <Legend/>
      </PieChart>
    </ResponsiveContainer>
    <div className="chart-axis-note">Sales mix by product category</div>
  </div>;
}

function TopProductsChart({products=[]}){
  const data=(products||[]).slice(0,8).map(x=>({
    product:String(x.product||"Product").length>20?String(x.product).slice(0,20)+"…":String(x.product||"Product"),
    units:Number(x.units)||0
  }));
  if(!data.length) return <div className="empty-state compact"><p>No product sales data available.</p></div>;
  return <div className="report-chart-wrap accurate-chart">
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={data} layout="vertical" margin={{top:10,right:25,left:10,bottom:10}}>
        <CartesianGrid strokeDasharray="3 3" opacity={.18}/>
        <XAxis type="number" allowDecimals={false} tick={{fontSize:10}}/>
        <YAxis type="category" dataKey="product" width={125} tick={{fontSize:10}}/>
        <Tooltip formatter={(v)=>[Number(v).toLocaleString("en-IN"),"Units sold"]}/>
        <Bar dataKey="units" name="Units sold" fill="currentColor" radius={[0,4,4,0]}/>
      </BarChart>
    </ResponsiveContainer>
    <div className="chart-axis-note">Top products ranked by units sold</div>
  </div>;
}

function Reports(){
  const [period,setPeriod]=useState("daily"),[r,setR]=useState(null),[error,setError]=useState(""),[loading,setLoading]=useState(false);
  async function load(p=period){
    setLoading(true);setError("");
    try{setR(await api(`/reports/periodic?period=${p}`))}
    catch(e){setError(e.message)}
    finally{setLoading(false)}
  }
  useEffect(()=>{load(period)},[period]);

  return <Layout>
    <Header title="My Sales" sub="See your sales trend, best-selling products and category mix."/>
    <div className="report-tabs">
      {[["daily","Daily"],["weekly","Weekly"],["monthly","Monthly"],["yearly","Yearly"]].map(([v,l])=>
        <button key={v} className={period===v?"active":""} onClick={()=>setPeriod(v)}>{l} Report</button>
      )}
    </div>
    {error&&<div className="error">{error}</div>}
    {loading&&!r?<div className="loading">Building {period} report…</div>:r&&<>
      <div className="cards report-kpis">
        {[["Total Units",r.kpis.total_units,"Σ"],["Average Period Units",r.kpis.average_units,"AVG"],["Peak Units",r.kpis.peak_units,"PEAK"],["Growth",r.kpis.growth_pct==null?"—":`${r.kpis.growth_pct}%`,"Δ"],["Records",r.kpis.records,"ROWS"]]
          .map(([a,b,c])=><div className="kpi-card" key={a}><span>{c}</span><small>{a}</small><strong>{b}</strong></div>)}
      </div>

      <div className="report-grid">
        <div className="panel chart-panel">
          <div className="panel-title">
            <div><h2>{period[0].toUpperCase()+period.slice(1)} Sales Trend</h2><p>Recorded sales units by reporting period</p></div>
            <button className="secondary" onClick={()=>load()}>↻ Refresh</button>
          </div>
          <MiniLineChart series={r.series}/>
          <MiniBarChart series={r.series}/>
        </div>

        <div className="panel">
          <div className="panel-title"><div><h2>Top Products</h2><p>Highest recorded unit volume</p></div></div>
          <TopProductsChart products={r.top_products}/>
        </div>
      </div>

      <div className="report-grid sales-visual-grid">
        <div className="panel">
          <div className="panel-title"><div><h2>Sales by Category</h2><p>Which product categories contribute most of your sales?</p></div></div>
          <SalesCategoryChart categories={r.categories}/>
        </div>
        <div className="panel">
          <div className="panel-title"><div><h2>Best-Selling Products</h2><p>Quick ranking for purchase and stock decisions</p></div></div>
          <Table headers={["Product","Units"]} rows={(r.top_products||[]).map(x=>[x.product,x.units])}/>
        </div>
      </div>

      <div className="report-footer-grid">
        <div className="insight-card"><span>✦</span><div><b>Sunny says</b>
          <p>{r.kpis.growth_pct==null?"More history is needed to calculate period-over-period growth.":r.kpis.growth_pct>=0?`Demand is trending up ${r.kpis.growth_pct}% versus the previous period.`:`Demand is trending down ${Math.abs(r.kpis.growth_pct)}% versus the previous period.`}</p>
        </div></div>
        <Link className="report-action" to="/copilot">Ask Sunny about this report →</Link>
      </div>
    </>}
  </Layout>;
}

function SunnyAssistant(){
  const [q,setQ]=useState("");
  const [messages,setMessages]=useState([
    {role:"assistant",content:"Hi, I’m Sunny. I’m connected to your active RetailPulse store dataset. Ask me a question in natural language — I can analyze demand, inventory, forecasts, scenarios, reports and explain the project."}
  ]);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  const bottomRef=React.useRef(null);
  const voice=useVoiceInput(setQ);

  useEffect(()=>{bottomRef.current?.scrollIntoView({behavior:"smooth"})},[messages,loading]);

  async function ask(text=q){
    const question=String(text||"").trim();
    if(!question||loading)return;
    const next=[...messages,{role:"user",content:question}];
    setMessages(next);setQ("");setLoading(true);setError("");
    try{
      const r=await api("/copilot",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({question,history:next.slice(-10),simple_mode:localStorage.getItem("simpleMode")!=="false",language:"en"})
      });
      setMessages(prev=>[...prev,{role:"assistant",content:r.answer,data:r.data,sources:r.sources||[],action:r.action}]);
    }catch(e){setError(e.message||"Sunny could not answer right now.")}
    finally{setLoading(false)}
  }

  function clearChat(){
    setMessages([{role:"assistant",content:"Chat cleared. I’m Sunny, ready to analyze your active RetailPulse dataset."}]);
    setError("");
  }

  const prompts=[
    "Give me a summary of this project",
    "Analyze my uploaded dataset",
    "What should I restock first?",
    "Explain ARIMA vs LSTM simply",
    "Teach me MAPE, MAE and RMSE",
    "Explain the architecture step by step",
    "What is overfitting?",
    "How can I improve this project?"
  ];

  return <Layout>
    <Header title="Ask Sunny" sub="Ask a question in your own words. Sunny answers you here."/>
    <div className="sunny-page">
      <div className="sunny-page-hero">
        <div className="sunny-brand">
          <div className="sunny-avatar large">✦</div>
          <div><span className="eyebrow">YOUR SHOP HELPER</span><h2>Just ask Sunny.</h2><p>You do not need special words. Ask the same way you would ask another person in your shop.</p><div className="sunny-capability-strip"><span>Sales</span><span>Stock</span><span>What to buy</span><span>Simple answers</span></div></div>
        </div>
        <button className="secondary sunny-clear" onClick={clearChat}>↻ New chat</button>
      </div>

      <div className="sunny-chat-shell">
        <div className="sunny-chat-header"><div><b>Sunny</b><span>● Ready to help</span></div><small>Type or speak</small></div>
        <div className="sunny-chat-body">
          {messages.map((msg,i)=><div className={`sunny-message full ${msg.role}`} key={i}>
            <div className="sunny-message-avatar">{msg.role==="assistant"?"✦":"You"}</div>
            <div className="sunny-message-content">
              <p>{msg.content}</p>
              {Array.isArray(msg.data)&&msg.data.length>0&&<div className="sunny-data-card">
                <div className="sunny-data-title">DATA FROM YOUR WORKSPACE</div>
                <Table headers={Object.keys(msg.data[0]||{}).slice(0,6).map(x=>x.replaceAll("_"," "))} rows={msg.data.slice(0,10).map(row=>Object.values(row).slice(0,6))}/>
              </div>}
              {msg.sources?.length>0&&<div className="sunny-sources">Sources · {msg.sources.join(" · ")}</div>}
              {msg.action&&<div className="sunny-next"><b>Next step</b><span>{msg.action}</span></div>}
            </div>
          </div>)}
          {loading&&<div className="sunny-message full assistant"><div className="sunny-message-avatar">✦</div><div className="sunny-message-content"><div className="sunny-typing"><i/><i/><i/></div></div></div>}
          <div ref={bottomRef}/>
        </div>

        <div className="sunny-prompt-row">{prompts.map(x=><button className="chip" key={x} onClick={()=>ask(x)} disabled={loading}>{x}</button>)}</div>
        {error&&<div className="error sunny-error">{error}</div>}
        <div className="sunny-composer">
          <textarea value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();ask()}}} placeholder="Example: What should I buy tomorrow?" rows="2"/>
          <div className="sunny-composer-foot"><span>{voice.supported?"You can type or speak. Sunny answers here.":"Sunny answers here using your active dataset."}</span>{voice.supported&&<button className="voice-btn secondary" onClick={voice.start} disabled={loading}>{voice.listening?"Listening…":"🎙 Speak"}</button>}<button onClick={()=>ask()} disabled={!q.trim()||loading}>{loading?"Thinking…":"Send ↑"}</button></div>
        </div>
      </div>
    </div>
  </Layout>;
}

function Settings(){
  const [d,setD]=useState(null);
  const [error,setError]=useState("");
  const [form,setForm]=useState({email:"",password:"",role:"STAFF"});
  const [created,setCreated]=useState("");
  const [loading,setLoading]=useState(true);

  async function load(){
    setLoading(true); setError("");
    try{
      const x=await api("/settings/overview");
      setD(x);
    }catch(e){
      setError(e.message||"Unable to load settings.");
    }finally{setLoading(false);}
  }

  useEffect(()=>{load()},[]);

  async function create(){
    setCreated("");
    if(!form.email||!form.password){setCreated("Email and password are required.");return;}
    try{
      await api("/users",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify(form)
      });
      setCreated("User created successfully.");
      setForm({email:"",password:"",role:"STAFF"});
      await load();
    }catch(e){setCreated(e.message||"Unable to create user.");}
  }

  if(loading)return <Layout><Header title="Settings & Access" sub="Owner administration"/><div className="loading">Loading owner settings…</div></Layout>;
  if(error)return <Layout><Header title="Settings & Access" sub="Owner administration"/><div className="error">Settings API error: {error}<br/><span className="muted">Check the backend terminal for the exact exception.</span></div></Layout>;

  const tenant=d?.tenant||{name:"RetailPulse AI"};
  const stores=Array.isArray(d?.stores)?d.stores:[];
  const users=Array.isArray(d?.users)?d.users:[];
  const roles=Array.isArray(d?.roles)?d.roles:["OWNER","MANAGER","STAFF","ANALYST","CUSTOMER"];
  const matrix=d?.permission_matrix||{};

  return <Layout>
    <Header title="Settings" sub="Manage your shop account."/>
    <div className="settings-hero">
      <div><span className="eyebrow">OWNER CONTROL CENTER</span><h2>{tenant.name}</h2><p>Manage users, roles, stores and feature access.</p></div>
      <div className="security-badge">🔐 OWNER ACCESS</div>
    </div>

    <div className="settings-grid">
      <div className="panel">
        <h2>Workspace</h2>
        <div className="metric-row"><span>Tenant</span><b>{tenant.name}</b></div>
        <div className="metric-row"><span>Stores</span><b>{stores.length}</b></div>
        <div className="metric-row"><span>Users</span><b>{users.length}</b></div>
        <div className="metric-row"><span>Roles</span><b>{roles.join(" · ")}</b></div>
      </div>

      <div className="panel">
        <h2>Create User</h2>
        <div className="form-grid">
          <input placeholder="Email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/>
          <input type="password" placeholder="Temporary password" value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/>
          <select value={form.role} onChange={e=>setForm({...form,role:e.target.value})}>
            {roles.map(r=><option key={r}>{r}</option>)}
          </select>
        </div>
        <button onClick={create}>Create User</button>
        {created&&<p className={created.includes("successfully")?"success":"error"}>{created}</p>}
      </div>
    </div>

    <div className="panel">
      <h2>User Directory</h2>
      <Table headers={["Email","Role","Store","Status"]} rows={users.map(u=>[
        u.email,<Badge x={u.role}/>,stores.find(s=>s.id===u.store_id)?.name||"All stores",
        u.active?"Active":"Disabled"
      ])}/>
    </div>

    <div className="panel">
      <h2>Role Access Matrix</h2>
      <div className="permission-grid">
        {Object.entries(matrix).map(([role,perms])=>
          <div className="permission-card" key={role}>
            <div className="permission-title"><Badge x={role}/><b>{role}</b></div>
            <div className="permission-list">{(perms||[]).map(p=><span key={p}>✓ {p.replaceAll("_"," ")}</span>)}</div>
          </div>
        )}
      </div>
    </div>
  </Layout>
}

class AppErrorBoundary extends React.Component{
  constructor(props){super(props);this.state={error:null}}
  static getDerivedStateFromError(error){return {error}}
  componentDidCatch(error,info){console.error("RetailPulse UI error",error,info)}
  render(){
    if(this.state.error){
      return <div style={{padding:"40px",fontFamily:"system-ui",background:"#070b16",color:"#fff",minHeight:"100vh"}}>
        <h1>RetailPulse AI</h1>
        <h2>UI error</h2>
        <pre style={{whiteSpace:"pre-wrap",color:"#ff9b9b"}}>{String(this.state.error?.stack||this.state.error)}</pre>
        <button onClick={()=>location.reload()}>Reload application</button>
      </div>
    }
    return this.props.children
  }
}

function Protected({ children }) { return <RequireAuth>{children}</RequireAuth>; }
function App(){return <Routes><Route path="/login" element={<Login/>}/><Route path="/" element={<Protected><Dashboard/></Protected>}/><Route path="/products" element={<Protected><Products/></Protected>}/><Route path="/data" element={<Protected><RoleGate permission="data_upload"><Data/></RoleGate></Protected>}/><Route path="/arima" element={<Protected><RoleGate permission="arima"><ModelLab type="ARIMA"/></RoleGate></Protected>}/><Route path="/lstm" element={<Protected><RoleGate permission="lstm"><ModelLab type="LSTM"/></RoleGate></Protected>}/><Route path="/evaluation" element={<Protected><RoleGate permission="model_center"><Evaluation/></RoleGate></Protected>}/><Route path="/seasonality" element={<Protected><RoleGate permission="seasonality"><Seasonality/></RoleGate></Protected>}/><Route path="/inventory" element={<Protected><RoleGate permission="inventory"><Inventory/></RoleGate></Protected>}/><Route path="/restock-center" element={<Protected><RoleGate permission="restock"><RestockCenter/></RoleGate></Protected>}/><Route path="/scenarios" element={<Protected><RoleGate permission="scenarios"><Scenarios/></RoleGate></Protected>}/><Route path="/alerts" element={<Protected><RoleGate permission="alerts"><Alerts/></RoleGate></Protected>}/><Route path="/reports" element={<Protected><RoleGate permission="reports"><Reports/></RoleGate></Protected>}/><Route path="/copilot" element={<Protected><RoleGate permission="copilot"><SunnyAssistant/></RoleGate></Protected>}/><Route path="/settings" element={<Protected><RoleGate permission="settings"><Settings/></RoleGate></Protected>}/><Route path="*" element={<Navigate to="/" replace/>}/></Routes>}

createRoot(document.getElementById("root")).render(<AppErrorBoundary><BrowserRouter><App/></BrowserRouter></AppErrorBoundary>);
