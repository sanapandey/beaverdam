import {useEffect, useMemo, useState} from 'react';
import type {FormEvent} from 'react';
import {ArrowRight, BookOpen, CalendarDays, Check, ChevronDown, Clock3, Coffee, Dumbbell, Eye, EyeOff, GraduationCap, Heart, Info, LockKeyhole, MapPin, Menu, MessageCircle, Plus, RefreshCw, Search, Settings2, ShieldCheck, ShieldOff, Sparkles, Trash2, Users, X} from 'lucide-react';
import {api, DEMO_MODE} from './api';
import {CATEGORIES, PROFILE_SHARING} from './types';
import type {AppSnapshot, Category, Recommendation, Routine, PrivacySettings, BlindZone, ChatMessage, Conversation} from './types';

type Page='discover'|'routine'|'privacy'|'connections';
const categoryInfo: Record<Category,{name:string;short:string;description:string;Icon:typeof BookOpen}>={
  academic:{name:'Classes',short:'Classes',description:'Lectures, labs, and seminars',Icon:GraduationCap},
  study:{name:'Study spaces',short:'Study',description:'Libraries and study sessions',Icon:BookOpen},
  dining:{name:'Dining',short:'Dining',description:'Meals and coffee breaks',Icon:Coffee},
  gym:{name:'Fitness',short:'Fitness',description:'Workouts and recreation',Icon:Dumbbell},
  leisure:{name:'Social & leisure',short:'Leisure',description:'Clubs, events, and downtime',Icon:Heart},
};
const profileOptions=[
  {key:'P1_all_but_leisure',title:'Mostly open',desc:'Share classes, study, dining & fitness'},
  {key:'P2_no_dining',title:'Balanced',desc:'Share classes, study & fitness'},
  {key:'P3_no_dining_gym',title:'More private',desc:'Share classes & study only'},
  {key:'P4_academic_only',title:'Classes only',desc:'Share only academic activities'},
];
const DAYS=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
const INITIAL_NEW={title:'',category:'study' as Category,day:'Monday',start:'13:00',end:'14:00',place:''};

function App(){
  const [page,setPage]=useState<Page>('discover');
  const [data,setData]=useState<AppSnapshot|null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const [saving,setSaving]=useState(false);
  const [search,setSearch]=useState('');
  const [filter,setFilter]=useState('All');
  const [selected,setSelected]=useState<Recommendation|null>(null);
  const [showAdd,setShowAdd]=useState(false);
  const [draft,setDraft]=useState(INITIAL_NEW);
  const [zoneDraft,setZoneDraft]=useState<{label:string;kind:'Place'|'Time';value:string}>({label:'',kind:'Place',value:''});
  const [showZone,setShowZone]=useState(false);
  const [mobileNav,setMobileNav]=useState(false);
  const [conversations,setConversations]=useState<Conversation[]>([]);
  const [activeChat,setActiveChat]=useState<string|null>(null);
  const [chatMessages,setChatMessages]=useState<ChatMessage[]>([]);
  const [chatDraft,setChatDraft]=useState('');
  const [chatBusy,setChatBusy]=useState(false);
  useEffect(()=>{api.load().then(setData).catch(e=>setError(String(e))).finally(()=>setLoading(false));},[]);
  useEffect(()=>{if(!notice)return;const timer=setTimeout(()=>setNotice(''),4000);return ()=>clearTimeout(timer);},[notice]);
  const privacy=data?.privacy;
  const activeCount=privacy? CATEGORIES.filter(k=>privacy.sharing[k]).length:0;
  const profile=privacy ? profileOptions.find(p=>CATEGORIES.every(c=>PROFILE_SHARING[p.key][c]===privacy.sharing[c])) : undefined;
  const recommendations=useMemo(()=>{
    if(!data)return [];
    // Demo recommendations are illustrative fixtures. Do not infer matches or disclose hidden schedules in-browser.
    return data.recommendations.filter(r=>(filter==='All'||r.strength===filter) && `${r.name} ${r.major} ${r.interests.join(' ')}`.toLowerCase().includes(search.toLowerCase()));
  },[data,filter,search]);
  async function updatePrivacy(next:PrivacySettings){
    if(!data)return;
    const previous=data.privacy;
    setData({...data,privacy:next});setSaving(true);setError('');
    try{const confirmed=await api.savePrivacy(next);const recs=DEMO_MODE ? data.recommendations : await api.refreshRecommendations();setData(current=>current?{...current,privacy:confirmed,recommendations:recs}:current);setNotice(DEMO_MODE?'Demo preference updated on this screen':'Preferences saved · matches recomputed');}
    catch(e){setData(current=>current?{...current,privacy:previous}:current);setError(`Privacy settings were not saved: ${String(e)}`);}
    finally{setSaving(false);}
  }
  async function updateRoutines(next:Routine[]){
    if(!data)return;
    const previous=data.routines;setData({...data,routines:next});setSaving(true);setError('');
    try{const confirmed=await api.saveRoutines(next);const recs=DEMO_MODE ? data.recommendations : await api.refreshRecommendations();setData(current=>current?{...current,routines:confirmed,recommendations:recs}:current);setNotice(DEMO_MODE?'Demo routine updated on this screen':'Routine saved · matches recomputed');}
    catch(e){setData(current=>current?{...current,routines:previous}:current);setError(`Routine was not saved: ${String(e)}`);}
    finally{setSaving(false);}
  }
  async function loadConversations(){
    if(DEMO_MODE)return;
    try{setConversations(await api.conversations());}
    catch(e){setError(`Could not load conversations: ${String(e)}`);}
  }
  async function openChat(id:string){
    setActiveChat(id);setChatBusy(true);setError('');
    try{setChatMessages((await api.messages(id)).messages);}
    catch(e){setError(`Could not open conversation: ${String(e)}`);setActiveChat(null);}
    finally{setChatBusy(false);}
  }
  async function sendChat(e:FormEvent<HTMLFormElement>){
    e.preventDefault();if(!activeChat||!chatDraft.trim()||chatBusy)return;
    setChatBusy(true);setError('');
    try{const sent=await api.sendMessage(activeChat,chatDraft.trim());setChatMessages(old=>[...old,sent]);setChatDraft('');await loadConversations();}
    catch(e){setError(`Message was not sent: ${String(e)}`);}
    finally{setChatBusy(false);}
  }
  async function chooseDemo(student:string,dataset:string){setSaving(true);setError('');try{const updated=await api.selectDemo(student,dataset);setData(updated);setSelected(null);setActiveChat(null);setChatMessages([]);setConversations([]);setPage('discover');setNotice('Synthetic demo account and dataset loaded');}catch(e){setError(`Cannot load demo selection: ${String(e)}`);}finally{setSaving(false);}}
  async function connect(id:string){
    if(!data)return;
    try{const {state}=await api.connect(id);setData(current=>current?{...current,connections:{...current.connections,[id]:state}}:current);if(state==='connected')await loadConversations();setNotice(state==='connected'?'You are connected! Messaging is now available.':DEMO_MODE?'Demo request sent (not delivered to another person)':'Connection request sent');}
    catch(e){setError(`Could not connect: ${String(e)}`);}
  }
  async function refresh(){
    if(!data)return;
    if(DEMO_MODE){setNotice('Demo recommendations are fixed examples, not calculated matches');return;}
    setSaving(true);
    try{const recs=await api.refreshRecommendations();setData({...data,recommendations:recs});setNotice('Recommendations refreshed');}
    catch(e){setError(`Could not refresh matches: ${String(e)}`);}finally{setSaving(false);}
  }
  function nav(next:Page){if(next==='connections')void loadConversations();setPage(next);setMobileNav(false);setSelected(null);window.scrollTo({top:0,behavior:'smooth'});}
  if(loading)return <div className="loading"><div className="logo-mark"><ShieldCheck size={26}/></div>Opening BeaverDam…</div>;
  if(!data||!privacy)return <div className="loading">Unable to load BeaverDam. {error}</div>;
  const requested=Object.values(data.connections).filter(x=>x==='requested'||x==='incoming'||x==='connected').length;
  const menu: {page:Page; label:string;Icon:typeof Users}[]=[{page:'discover',label:'Discover',Icon:Sparkles},{page:'routine',label:'My routine',Icon:CalendarDays},{page:'privacy',label:'Privacy settings',Icon:ShieldCheck},{page:'connections',label:'Connections',Icon:Users}];
  return <div className="shell">
    <aside className={`sidebar ${mobileNav?'open':''}`}>
      <button className="brand" onClick={()=>nav('discover')} aria-label="BeaverDam home"><span className="brand-icon"><span className="beaver-symbol">b.</span></span><span>beaver<span className="brand-medium">dam</span><small>find your people</small></span></button>
      <div className="sidebar-heading">YOUR SPACE</div>
      <nav className="side-links" aria-label="Main navigation">{menu.map(({page:p,label,Icon})=><button key={p} className={`side-link ${page===p?'active':''}`} onClick={()=>nav(p)}><Icon size={19} strokeWidth={1.9}/><span>{label}</span>{p==='connections'&&requested>0?<span className="nav-count">{requested}</span>:null}</button>)}</nav>
      <div className="sidebar-bottom"><div className="sidebar-privacy"><div className="sidebar-privacy-top"><ShieldCheck size={19}/><span>Your privacy comes first</span></div><p>You're in control of what helps make your matches.</p><button onClick={()=>nav('privacy')}>Manage sharing <ArrowRight size={14}/></button></div><div className="account"><div className="avatar account-avatar">SM</div><div><b>Demo student</b><small>MIT community · Preview</small></div><ChevronDown size={16}/></div></div>
    </aside>
    <main className="main">
      <header className="topbar"><button className="mobile-menu" onClick={()=>setMobileNav(!mobileNav)} aria-label="Toggle menu"><Menu size={23}/></button><span className="crumb">Your community <span>/</span> <b>{menu.find(x=>x.page===page)?.label}</b></span><div className="top-actions"><span className="demo-pill"><span className="live-dot"/> {DEMO_MODE?'ILLUSTRATIVE DEMO':'SYNTHETIC DATA · REAL MATCHER'}</span><button className="icon-button" onClick={()=>nav('privacy')} aria-label="Privacy settings"><Settings2 size={20}/></button><div className="avatar small-avatar">SM</div></div></header>
      {error&&<div className="error-banner" role="alert">{error}<button onClick={()=>setError('')} aria-label="Dismiss error"><X size={16}/></button></div>}
      {notice&&<div className="toast" role="status"><Check size={17}/>{notice}</div>}
      <div className="content">{data.demo&&<div className="demo-controls"><div><b>Research prototype</b><span>Switch synthetic students or datasets to test privacy-sensitive recommendations. No real MIT accounts.</span></div><label>Dataset <select aria-label="Synthetic dataset" value={data.demo.dataset} disabled={saving} onChange={e=>chooseDemo(data.demo!.student,e.target.value)}>{data.demo.datasets.map(d=><option key={d} value={d}>{d.replace('v2_','V2 · ')}</option>)}</select></label><label>Student <select aria-label="Synthetic student" value={data.demo.student} disabled={saving} onChange={e=>chooseDemo(e.target.value,data.demo!.dataset)}>{Array.from({length:100},(_,i)=>'S'+String(i+1).padStart(3,'0')).map(x=><option key={x} value={x}>{x}</option>)}</select></label></div>}
      {page==='discover'&&<>
        <div className="eyebrow"><span className="eyebrow-line"/> THE GOOD KIND OF OVERLAP</div>
        <div className="page-title-row"><div><h1>Find your kind of people<span className="period">.</span></h1><p className="page-subtitle">New connections might already be part of your everyday routine.</p></div><button className="button subtle refresh" disabled={saving} onClick={refresh}><RefreshCw size={16}/> Refresh matches</button></div>
        <div className="hero"><div className="hero-content"><div className="hero-label"><Sparkles size={14}/> THE IDEA BEHIND BEAVERDAM</div><h2>Same campus.<br/><em>Shared rhythms.</em><br/>New friendships.</h2><p>Meet fellow MIT students whose routines overlap with yours, without having to share the details of where you've been.</p><button onClick={()=>nav('privacy')} className="hero-link">Explore your privacy controls <ArrowRight size={17}/></button></div><div className="hero-art" aria-hidden="true"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="orbit orbit-three"/><span className="orbit-person orbit-a">A</span><span className="orbit-person orbit-b">J</span><span className="orbit-person orbit-c">P</span><span className="orbit-person orbit-d">S</span><span className="orbit-center"><Heart size={31} fill="currentColor"/></span><span className="orbit-star star-a">✳</span><span className="orbit-star star-b">✳</span></div></div>
        <div className="stats-row"><div className="stat"><span className="stat-icon lilac"><Users size={21}/></span><div><b>{data.recommendations.length}</b><span>People to discover</span></div></div><div className="stat"><span className="stat-icon mint"><ShieldCheck size={21}/></span><div><b>{activeCount} <small>/ 5</small></b><span>Categories shared</span></div></div><div className="stat"><span className="stat-icon peach"><Heart size={21}/></span><div><b>{requested}</b><span>Connection requests</span></div></div></div>
        <div className="section-header"><div><div className="section-kicker">EXPLORE</div><h2>People you might click with <span className="count-pill">{recommendations.length}</span></h2><p>Matches are shown by strength, never by exact similarity scores.</p></div></div>
        <div className="filters"><div className="tabs" role="group" aria-label="Filter by match strength">{['All','Strong','Moderate','Weak'].map(k=><button key={k} className={filter===k?'selected':''} onClick={()=>setFilter(k)}>{k==='All'?'All matches':`${k} matches`}</button>)}</div><div className="search"><Search size={18}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search by name or interest" aria-label="Search recommendations"/></div></div>
        <div className="match-grid">{recommendations.map(r=><article className="match-card" key={r.id}><div className="match-top"><div className="avatar match-avatar" style={{background:r.color}}>{r.initials}</div><span className={`strength ${r.strength.toLowerCase()}`}><span className="strength-dot"/>{r.strength} match</span></div><h3>{r.name}</h3><div className="candidate-meta">MIT '{r.year.slice(2)} <span>·</span> {r.major}</div><p className="candidate-bio">{r.bio}</p><div className="tiny-label">SHARED ROUTINE CATEGORIES</div><div className="chips">{r.categories.map(c=><span key={c} className="chip">{categoryInfo[c].short}</span>)}</div><div className="match-bottom"><button className="button secondary" onClick={()=>setSelected(r)}>View profile <ArrowRight size={16}/></button><button className={`round-connect ${data.connections[r.id]==='requested'?'sent':''}`} onClick={()=>connect(r.id)} disabled={Boolean(data.connections[r.id])} aria-label={`Connect with ${r.name}`}>{data.connections[r.id]==='requested'?<Check size={19}/>:<Plus size={19}/>}</button></div></article>)}</div>
        {!recommendations.length&&<div className="empty"><Search size={30}/><h3>No matches found</h3><p>Try another search or change the match filter.</p><button className="button secondary" onClick={()=>{setFilter('All');setSearch('');}}>Clear filters</button></div>}
        <div className="privacy-note"><LockKeyhole size={21}/><p><strong>What you see is intentionally limited.</strong> Matching categories are broad labels, not individual classes, locations, schedules, or exact scores. {DEMO_MODE?'These profiles and strengths are illustrative demo data.':''}</p><button onClick={()=>nav('privacy')}>Privacy settings <ArrowRight size={15}/></button></div>
      </>}
      {page==='privacy'&&<>
        <div className="eyebrow"><span className="eyebrow-line"/> YOUR INFORMATION, YOUR RULES</div><div className="page-title-row"><div><h1>Privacy, on your terms<span className="period">.</span></h1><p className="page-subtitle">Choose which parts of your routine contribute to finding friends.</p></div><span className="save-status"><ShieldCheck size={17}/>{saving?'Saving…':DEMO_MODE?'Local preview':'Privacy preferences'}</span></div>
        <div className="privacy-hero"><div className="privacy-hero-icon"><ShieldCheck size={29}/></div><div><h3>Being private shouldn't mean being left out.</h3><p>BeaverDam's matching method compares only categories both people choose to share. Hidden categories aren't treated as places you never visit.</p></div></div>
        <div className="section-kicker">01 — START WITH A PRESET</div><div className="heading-help"><h2>Choose your comfort level</h2><p>Pick a starting point, then customize your choices below.</p></div>
        <div className="preset-grid">{profileOptions.map((opt,i)=><button key={opt.key} className={`preset ${profile?.key===opt.key?'active':''}`} onClick={()=>updatePrivacy({...privacy,sharing:{...PROFILE_SHARING[opt.key]}})}><div className="preset-top"><span className="preset-number">0{i+1}</span><span className="preset-radio">{profile?.key===opt.key&&<Check size={13}/>}</span></div><b>{opt.title}</b><small>{opt.desc}</small><div className="preset-bars">{CATEGORIES.map(c=><span className={PROFILE_SHARING[opt.key][c]?'on':''} key={c}/>)}</div></button>)}</div>
        <div className="section-kicker stacked">02 — MAKE IT YOURS</div><div className="heading-help"><h2>Activity categories</h2><p>Only allowed categories can be used to find your matches.</p></div>
        <div className="category-panel">{CATEGORIES.map(c=>{const {Icon,name,description}=categoryInfo[c];const active=privacy.sharing[c];return <div className="category-row" key={c}><div className={`category-icon ${active?'':'muted'}`}><Icon size={21}/></div><div className="category-copy"><b>{name}</b><span>{description}</span></div><span className={`share-status ${active?'active':''}`}>{active?<><Eye size={15}/> Shared</>:<><EyeOff size={15}/> Hidden</>}</span><button role="switch" aria-checked={active} className={`toggle ${active?'on':''}`} onClick={()=>updatePrivacy({...privacy,sharing:{...privacy.sharing,[c]:!active}})} aria-label={`${active?'Hide':'Share'} ${name}`}><span/></button></div>;})}</div>
        <div className="privacy-detail-grid"><div className="panel"><div className="panel-title"><h3>Profile visibility</h3><Eye size={19}/></div><p>Control whether other students can discover you. A verified account is not implemented in this demo.</p><div className="visibility-options">{([{value:'everyone',label:'Appear in recommendations',desc:'Other eligible students may discover your profile'},{value:'hidden',label:'Pause discovery',desc:'Keep your profile out of new recommendations'}] as const).map(x=><button className={`visibility-option ${privacy.visibility===x.value?'chosen':''}`} key={x.value} onClick={()=>updatePrivacy({...privacy,visibility:x.value})}><span className="option-radio">{privacy.visibility===x.value?<span/>:null}</span><span><b>{x.label}</b><small>{x.desc}</small></span></button>)}</div></div>
        <div className="panel"><div className="panel-title"><h3>Blind zones</h3><MapPin size={19}/></div><p>Exclude additional places or time windows from your shared routine. A production device filter is still needed.</p>{privacy.blindZones.map(z=><div className="zone-row" key={z.id}><div><b>{z.label}</b><span>{z.kind}: {z.value}</span></div><button aria-label={`Remove ${z.label}`} onClick={()=>updatePrivacy({...privacy,blindZones:privacy.blindZones.filter(x=>x.id!==z.id)})}><Trash2 size={17}/></button></div>)}{showZone?<form className="zone-form" onSubmit={e=>{e.preventDefault();if(!zoneDraft.label.trim()||!zoneDraft.value.trim())return;const zone:BlindZone={...zoneDraft,id:crypto.randomUUID()};updatePrivacy({...privacy,blindZones:[...privacy.blindZones,zone]});setShowZone(false);setZoneDraft({label:'',kind:'Place',value:''});}}><input required placeholder="Label (e.g. quiet hours)" value={zoneDraft.label} onChange={e=>setZoneDraft({...zoneDraft,label:e.target.value})}/><select value={zoneDraft.kind} onChange={e=>setZoneDraft({...zoneDraft,kind:e.target.value as 'Place'|'Time'})}><option>Place</option><option>Time</option></select><input required placeholder={zoneDraft.kind==='Place'?'Place or venue identifier':'Time range (e.g. 22:00–07:00)'} value={zoneDraft.value} onChange={e=>setZoneDraft({...zoneDraft,value:e.target.value})}/><div className="form-actions"><button type="button" className="button subtle" onClick={()=>setShowZone(false)}>Cancel</button><button className="button primary">Add zone</button></div></form>:<button className="text-action" onClick={()=>setShowZone(true)}><Plus size={17}/> Add blind zone</button>}</div></div>
        <div className="disclaimer"><Info size={19}/><p>Privacy controls here demonstrate the proposed UI. In production, category and blind-zone filtering must happen <b>on the device before upload</b>, and the server must delete previously shared data when permissions are revoked. The provided Python prototype does not implement that full lifecycle.</p></div>
      </>}
      {page==='routine'&&<>
        <div className="eyebrow"><span className="eyebrow-line"/> THE PLACES YOUR WEEK TAKES YOU</div><div className="page-title-row"><div><h1>Your weekly rhythm<span className="period">.</span></h1><p className="page-subtitle">Add routines to organize your week, and decide what stays private.</p></div><button className="button primary" onClick={()=>setShowAdd(true)}><Plus size={18}/> Add activity</button></div>
        <div className="routine-summary"><div className="routine-summary-icon"><CalendarDays size={25}/></div><div><h3>A little routine can lead to a lot of connection.</h3><p>{DEMO_MODE?'These activities are illustrative and reset on refresh.':'These are synthetic dataset activities. Hiding or removing one excludes its check-ins from future matching; newly entered activities are personal notes until observed check-ins exist.'} Production requires on-device filtering.</p></div><span>{data.routines.length} activities</span></div>
        <div className="section-kicker">YOUR ACTIVITIES</div><div className="routine-list">{data.routines.slice().sort((a,b)=>DAYS.indexOf(a.day)-DAYS.indexOf(b.day)||a.start.localeCompare(b.start)).map(r=>{const {Icon}=categoryInfo[r.category];const isShared=privacy.sharing[r.category]&&!r.excluded;return <div className="routine-item" key={r.id}><div className="routine-day"><b>{r.day.slice(0,3).toUpperCase()}</b><span>{r.start}</span></div><div className="routine-icon"><Icon size={22}/></div><div className="routine-main"><b>{r.title}</b><span><Clock3 size={14}/>{r.start} – {r.end}<span className="sep-dot">·</span>{categoryInfo[r.category].name}</span></div><span className={`routine-state ${isShared?'shared':'private'}`}>{isShared?<><Eye size={15}/> Can be matched</>:<><EyeOff size={15}/> Not shared</>}</span><button className="routine-action" title={r.excluded?'Allow this event':'Withhold this event'} onClick={()=>updateRoutines(data.routines.map(x=>x.id===r.id?{...x,excluded:!x.excluded}:x))}><ShieldOff size={18}/></button><button className="routine-action" title="Remove activity" onClick={()=>updateRoutines(data.routines.filter(x=>x.id!==r.id))}><Trash2 size={18}/></button></div>;})}{!data.routines.length&&<div className="empty"><CalendarDays size={30}/><h3>No activities yet</h3><p>Add a routine to get started.</p></div>}</div>
        <div className="privacy-note"><ShieldCheck size={21}/><p><strong>You can hide any individual activity.</strong> You can also turn off sharing for its whole category in your privacy settings.</p><button onClick={()=>nav('privacy')}>Manage privacy <ArrowRight size={15}/></button></div>
      </>}
      {page==='connections'&&<>
        <div className="eyebrow"><span className="eyebrow-line"/> CONNECTIONS START HERE</div><div className="page-title-row"><div><h1>Make it a connection<span className="period">.</span></h1><p className="page-subtitle">Getting to know someone starts with a simple hello.</p></div></div>
        <div className="connection-banner"><MessageCircle size={32}/><div><h3>A conversation takes two.</h3><p>Messaging unlocks only after both students choose to connect. In this research demo, requests can be reciprocated by switching synthetic students; messages can be exchanged in a local synthetic conversation after mutual acceptance. No real accounts are involved.</p></div></div>
        <div className="section-kicker">YOUR CONVERSATIONS</div>
        {Object.entries(data.connections).filter(([,status])=>status==='connected').length>0 ? <div className="messenger">
          <div className="chat-list"><div className="chat-list-title">Messages <span>{Object.values(data.connections).filter(s=>s==='connected').length}</span></div>
            {Object.entries(data.connections).filter(([,status])=>status==='connected').map(([id])=>{const summary=conversations.find(c=>c.student===id);return <button key={id} className={`chat-person ${activeChat===id?'active':''}`} onClick={()=>openChat(id)}><span className="avatar">{id.slice(-2)}</span><span><b>Student {id}</b><small>{summary?.lastMessage?.text || 'You are connected · Say hello!'}</small></span><MessageCircle size={17}/></button>;})}
          </div>
          <div className="chat-panel">{activeChat ? <>
            <div className="chat-header"><div className="avatar">{activeChat.slice(-2)}</div><div><b>Student {activeChat}</b><small>Mutually connected · Synthetic demo</small></div><button className="button subtle" disabled={chatBusy} onClick={()=>openChat(activeChat)}><RefreshCw size={16}/> Refresh</button></div>
            <div className="chat-history" aria-live="polite">{chatMessages.length ? chatMessages.map(m=><div key={m.id} className={`chat-bubble ${m.sender===data.demo?.student?'mine':'theirs'}`}><p>{m.text}</p><small>{m.sender===data.demo?.student?'You':`Student ${m.sender}`} · {new Date(m.createdAt).toLocaleString([], {month:'short',day:'numeric',hour:'numeric',minute:'2-digit'})}</small></div>) : <div className="chat-empty"><MessageCircle size={29}/><b>Start the conversation</b><p>You both accepted the connection. Send a message to say hello!</p></div>}</div>
            <form className="chat-compose" onSubmit={sendChat}><input aria-label="Message" maxLength={2000} placeholder={`Message Student ${activeChat}…`} value={chatDraft} onChange={e=>setChatDraft(e.target.value)} disabled={chatBusy||DEMO_MODE}/><button type="submit" className="button primary" disabled={!chatDraft.trim()||chatBusy||DEMO_MODE}>Send <ArrowRight size={17}/></button></form>
          </> : <div className="chat-empty"><MessageCircle size={37}/><b>Select a conversation</b><p>Messages are only available after both students accept.</p></div>}</div>
        </div> : <div className="chat-intro"><MessageCircle size={19}/> Once two students connect, their conversation will appear here.</div>}
        <div className="section-kicker">YOUR REQUESTS</div>{requested? <div className="request-list">{Object.entries(data.connections).filter(([,status])=>status!=='none').map(([id,status])=><div key={id} className="request-item"><div className="avatar">{id.slice(-2)}</div><div><b>Student {id}</b><small>Synthetic MIT profile</small></div><span className="request-label"><Clock3 size={15}/>{status==='connected'?'Mutually connected':status==='incoming'?'Incoming request':'Awaiting response'}</span>{status==='connected'&&<button className="button secondary" onClick={()=>openChat(id)}><MessageCircle size={16}/> Message</button>}{status==='incoming'&&<button className="button primary" onClick={()=>connect(id)}>Accept</button>}</div>)}</div>:<div className="empty"><Users size={35}/><h3>No connection requests yet</h3><p>When someone seems interesting, send a connection request from Discover.</p><button className="button primary" onClick={()=>nav('discover')}>Explore people <ArrowRight size={16}/></button></div>}
      </>}
      <footer className="footer"><span><b>beaverdam</b> · MIT student research prototype</span><span>Built for thoughtful connections <Heart size={13}/></span></footer>
      </div>
    </main>
    {mobileNav&&<button className="scrim mobile-scrim" onClick={()=>setMobileNav(false)} aria-label="Close navigation"/>}
    {selected&&<div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)setSelected(null);}}><div className="modal" role="dialog" aria-modal="true" aria-label={`${selected.name}'s profile`}><button className="modal-close" onClick={()=>setSelected(null)} aria-label="Close"><X size={20}/></button><div className="profile-banner"><div className="avatar profile-avatar" style={{background:selected.color}}>{selected.initials}</div></div><div className="profile-content"><span className={`strength ${selected.strength.toLowerCase()}`}><span className="strength-dot"/>{selected.strength} match</span><h2>{selected.name}</h2><p className="profile-sub">MIT '{selected.year.slice(2)} · {selected.major}</p><p className="profile-bio">{selected.bio}</p><h4>Interests</h4><div className="chips">{selected.interests.map(i=><span className="chip" key={i}>{i}</span>)}</div><div className="profile-divider"/><h4>What you have in common</h4><p className="profile-explain">You may have routines in similar broad categories. Exact locations, times, and numerical scores aren't displayed.</p><div className="chips">{selected.categories.map(c=><span className="chip" key={c}>{categoryInfo[c].name}</span>)}</div><button className="button primary full" disabled={Boolean(data.connections[selected.id])} onClick={()=>{connect(selected.id);setSelected(null);}}>{data.connections[selected.id]==='requested'?<><Check size={17}/> Request sent</>:<><Plus size={17}/> Send connection request</>}</button></div></div></div>}
    {showAdd&&<div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)setShowAdd(false);}}><div className="modal add-modal" role="dialog" aria-modal="true" aria-label="Add an activity"><button className="modal-close" onClick={()=>setShowAdd(false)} aria-label="Close"><X size={20}/></button><div className="add-content"><div className="eyebrow">YOUR WEEK, YOUR WAY</div><h2>Add an activity</h2><p>Add an activity for your personal routine. The category-level privacy switch determines whether it can be shared.</p><form onSubmit={e=>{e.preventDefault();if(draft.end<=draft.start){setError('End time must be after start time');return;}updateRoutines([...data.routines,{...draft,id:crypto.randomUUID(),excluded:false}]);setDraft(INITIAL_NEW);setShowAdd(false);}}><label>Activity name<input required maxLength={90} placeholder="e.g. Weekly study group" value={draft.title} onChange={e=>setDraft({...draft,title:e.target.value})}/></label><label>Category<select value={draft.category} onChange={e=>setDraft({...draft,category:e.target.value as Category})}>{CATEGORIES.map(c=><option key={c} value={c}>{categoryInfo[c].name}</option>)}</select></label><label>Day of week<select value={draft.day} onChange={e=>setDraft({...draft,day:e.target.value})}>{DAYS.map(d=><option key={d}>{d}</option>)}</select></label><div className="input-row"><label>Starts<input type="time" required value={draft.start} onChange={e=>setDraft({...draft,start:e.target.value})}/></label><label>Ends<input type="time" required value={draft.end} onChange={e=>setDraft({...draft,end:e.target.value})}/></label></div><label>Place (optional)<input maxLength={90} placeholder="Your own private reference" value={draft.place} onChange={e=>setDraft({...draft,place:e.target.value})}/></label><div className="form-actions"><button type="button" className="button secondary" onClick={()=>setShowAdd(false)}>Cancel</button><button className="button primary" type="submit">Add to my routine <ArrowRight size={17}/></button></div></form></div></div></div>}
  </div>;
}
export default App;
