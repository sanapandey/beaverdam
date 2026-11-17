"""BeaverDam local synthetic-data demonstration API.

Not an authentication service or deployable privacy boundary. Runs the project's
real scoring functions on synthetic check-in data, and returns only coarse results.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import json
import re
import threading
from uuid import uuid4

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from beaverdam.data import CATEGORIES, build_slots, load_checkins, load_friendships, load_students
from beaverdam.matching import gap_aware_normalized_scores, gap_aware_scores, overlap_reference_scores
from beaverdam.profiles import PROFILES, shares_matrix, disclose

ROOT = Path(__file__).resolve().parent
DATASETS = ('v2_weak','v2_medium','v2_strong')
DAYS = ('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')
LOCK = threading.RLock()
STATE_PATH = ROOT / '.beaverdam-demo-state.json'
DEFAULT_SHARING = {c: c in PROFILES['P2_no_dining'] for c in CATEGORIES}
app = FastAPI(title='BeaverDam synthetic demo API', version='0.2.0')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],allow_credentials=True,allow_methods=['GET','PUT','POST'],allow_headers=['Content-Type'])

class Zone(BaseModel):
    id: str = Field(max_length=100)
    label: str = Field(max_length=100)
    kind: str
    value: str = Field(max_length=120)

class Privacy(BaseModel):
    sharing: dict[str,bool]
    visibility: str = 'everyone'
    hiddenRoutineIds: list[str] = Field(default_factory=list)
    blindZones: list[Zone] = Field(default_factory=list)

class Routine(BaseModel):
    id: str = Field(max_length=100)
    title: str = Field(max_length=90)
    category: str
    day: str
    start: str
    end: str
    place: str = ''
    excluded: bool = False

@lru_cache(maxsize=4)
def dataset(name: str):
    if name not in DATASETS: raise HTTPException(404,'Unknown dataset')
    folder = ROOT / 'data' / name
    checkins = load_checkins(folder)
    students = load_students(folder)
    edges = load_friendships(folder)
    activities = pd.read_csv(folder/'activities_full.csv',dtype=str,keep_default_na=False)
    return checkins, students, edges, activities

def empty_privacy():
    return {'sharing':dict(DEFAULT_SHARING),'visibility':'everyone','hiddenRoutineIds':[],'blindZones':[]}

def default_state():
    return {'student':'S001','dataset':'v2_medium','privacy':{},'routines':{},'deleted':{},'connections':{},'messages':{}}

def read_state():
    if not STATE_PATH.exists(): return default_state()
    try: return {**default_state(),**json.loads(STATE_PATH.read_text())}
    except (OSError, ValueError): return default_state()

def save_state(state):
    tmp = STATE_PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(state,indent=2))
    tmp.replace(STATE_PATH)

def current(state): return state['student']

def privacy_for(state, student): return state['privacy'].get(student,empty_privacy())

def parse_time_zone(value):
    found = re.fullmatch(r'\s*(\d\d:\d\d)\s*[-–—]\s*(\d\d:\d\d)\s*',value)
    if not found: return None
    a,b = found.groups()
    if any(int(v[:2])>23 or int(v[3:])>59 for v in [a,b]): return None
    return a,b

def filter_user_checkins(frame, state, student):
    """Apply demo withholding BEFORE constructing the algorithm's slot matrix.

    This is synthetic server-held ground truth; not a device-side privacy guarantee.
    """
    p = privacy_for(state,student)
    allowed = [k for k,v in p['sharing'].items() if v]
    subset = frame[(frame.student_id==student)&frame.activity_category.isin(allowed)].copy()
    omitted = set(p.get('hiddenRoutineIds',[])) | set(state['deleted'].get(student,[]))
    if omitted: subset = subset[~subset.event_id.isin(omitted)]
    for zone in p.get('blindZones',[]):
        if zone['kind']=='Place':
            # Exact venue identifier only: cannot silently assume fuzzy place names.
            subset=subset[subset.venue_id != zone['value'].strip()]
        elif zone['kind']=='Time':
            times=parse_time_zone(zone['value'])
            if times:
                a,b=times
                hh=subset.timestamp.str.slice(11,16)
                masked=((hh>=a)&(hh<b)) if a<=b else ((hh>=a)|(hh<b))
                subset=subset[~masked]
    return subset

def score_results(state):
    name=state['dataset']; user=state['student']
    frame,students,edges,_=dataset(name)
    idx={student:i for i,student in enumerate(students)}
    # Fixed, documented synthetic assignments: a quarter of accounts per P1-P4.
    names=list(PROFILES)
    pvals=[]
    for i,student in enumerate(students):
        sharing=privacy_for(state,student)['sharing'] if student==user or student in state['privacy'] else {c:c in PROFILES[names[i%4]] for c in CATEGORIES}
        pvals.append(frozenset(c for c in CATEGORIES if sharing.get(c,False)))
    shares=shares_matrix(pvals)
    # Filter all student records to their actual disclosed categories, and also
    # apply each student's individual event / zone exclusions before scoring.
    visible=pd.concat([filter_user_checkins(frame,state,s) if s in state['privacy'] or s in state['deleted'] else frame[(frame.student_id==s)&(frame.activity_category.isin(pvals[i]))] for i,s in enumerate(students)],ignore_index=True)
    slots=build_slots(visible,students)
    X_disclosed=disclose(slots.X,slots.slot_cat,shares)
    # tau=32 is a demonstration configuration, not a seed-tuned parameter.
    scores=gap_aware_normalized_scores(X_disclosed,slots.slot_cat,shares,tau=32.0)
    scores=np.nan_to_num(scores,nan=0,posinf=0,neginf=0)
    u=idx[user]
    friends=set(other for a,b in edges for other in ([b] if a==user else [a] if b==user else []))
    selected=[]
    for v,student in enumerate(students):
        if v==u or student in friends or scores[u,v]<=0: continue
        if privacy_for(state,student)['visibility']=='hidden':continue
        if privacy_for(state,student)['visibility']=='recommended' and scores[v,u]<=0: continue
        selected.append(v)
    # Internal ranking is exact, but no numeric scores are ever returned to client.
    selected.sort(key=lambda v:(-scores[u,v],students[v]))
    selected=selected[:10]
    rng=np.random.default_rng(2026+int(user[1:]))
    # Thresholds are ranks of selected top-k, not calibrated security thresholds.
    # Labels are expressly qualitative demo bins, NOT research-validated cutoffs.
    rank_groups=[selected[:3],selected[3:7],selected[7:]]
    result=[]
    for strength,group in zip(('Strong','Moderate','Weak'),rank_groups):
        group=list(group);rng.shuffle(group)
        for v in group:
            both=shares[u]&shares[v]
            # Do not reveal actual shared venue/time; show broad mutually allowed
            # categories that have at least one coincident slot.
            cats=[]
            for c in range(len(CATEGORIES)):
                if both[c] and np.any(X_disclosed[u,slots.slot_cat==c]&X_disclosed[v,slots.slot_cat==c]):cats.append(CATEGORIES[c])
            student=students[v]
            result.append({'id':student,'name':f'Student {student}','initials':student[-2:],
                           'year':'2027','major':'MIT student · synthetic profile',
                           'bio':'Synthetic student account used for the BeaverDam matching demonstration.',
                           'interests':[],'categories':cats,'strength':strength,
                           'color':['#e4e9d9','#ece2d9','#e4e1f1','#d7e6e0'][v%4]})
    return result

def user_routines(state):
    _,_,_,activities=dataset(state['dataset'])
    user=state['student']
    excluded=set(privacy_for(state,user)['hiddenRoutineIds'])
    deleted=set(state['deleted'].get(user,[]))
    records=[]
    for row in activities[activities.student_id==user].itertuples(index=False):
        if row.event_id in deleted: continue
        records.append({'id':row.event_id,'title':row.activity_category.capitalize()+' activity',
                        'category':row.activity_category,'day':DAYS[datetime.fromisoformat(row.date).weekday()],
                        'start':row.start_time,'end':row.end_time,'place':row.venue_id,
                        'excluded':row.event_id in excluded})
    # New manually entered routines are a local organizer in this demo; without
    # authenticated check-in observations they cannot contribute matching slots.
    records += state['routines'].get(user,[])
    return records

def connection_state(state, user, other):
    directed=state['connections']
    if other in directed.get(user,[]):
        return 'connected' if user in directed.get(other,[]) else 'requested'
    if user in directed.get(other,[]):return 'incoming'
    return 'none'

def dashboard(state):
    user=state['student']
    recs=score_results(state)
    targets=set(state['connections'].get(user,[]))|{s for s,others in state['connections'].items() if user in others}
    return {'recommendations':recs,'routines':user_routines(state),'privacy':privacy_for(state,user),
            'connections':{s:connection_state(state,user,s) for s in targets},
            'demo':{'student':user,'dataset':state['dataset'],'datasets':list(DATASETS)}}

def validated_privacy(p:Privacy):
    if set(p.sharing)!=set(CATEGORIES):raise HTTPException(422,'Sharing must specify exactly five categories')
    if p.visibility not in ('everyone','recommended','hidden'):raise HTTPException(422,'Invalid visibility')
    for z in p.blindZones:
        if z.kind not in ('Place','Time'):raise HTTPException(422,'Invalid zone kind')
        if z.kind=='Time' and parse_time_zone(z.value) is None:raise HTTPException(422,'Time zone must be HH:MM–HH:MM')
    return p.model_dump()

@app.get('/api/v1/health')
def health():return {'status':'ok','mode':'synthetic-demo','datasets':list(DATASETS)}

@app.get('/api/v1/me/dashboard')
def get_dashboard():
    with LOCK:return dashboard(read_state())

@app.get('/api/v1/me/recommendations')
def get_recommendations():
    with LOCK:return score_results(read_state())

@app.put('/api/v1/me/privacy')
def set_privacy(p:Privacy):
    clean=validated_privacy(p)
    with LOCK:
        state=read_state();state['privacy'][current(state)]=clean;save_state(state)
    return clean

@app.put('/api/v1/me/routines')
def set_routines(routines:list[Routine]):
    with LOCK:
        state=read_state();user=current(state)
        _,_,_,activities=dataset(state['dataset'])
        original_ids=set(activities.loc[activities.student_id==user,'event_id'])
        submitted={r.id:r for r in routines}
        hidden=[id for id in original_ids if id in submitted and submitted[id].excluded]
        deleted=[id for id in original_ids if id not in submitted]
        p=privacy_for(state,user).copy();p['hiddenRoutineIds']=hidden
        state['privacy'][user]=p
        state['deleted'][user]=deleted
        state['routines'][user]=[r.model_dump() for r in routines if r.id not in original_ids]
        save_state(state)
        return user_routines(state)

@app.post('/api/v1/connections/{other}')
def connect(other:str):
    with LOCK:
        state=read_state();user=current(state)
        if other==user or other not in dataset(state['dataset'])[1]:raise HTTPException(404,'Student not found')
        if other not in state['connections'].get(user,[]):state['connections'].setdefault(user,[]).append(other)
        save_state(state)
        return {'state':connection_state(state,user,other)}

# Conversations are restricted to mutually connected synthetic accounts.
# This file-backed demo is intentionally NOT an authenticated messaging service.
class OutgoingMessage(BaseModel):
    text: str = Field(min_length=1, max_length=2000)

def thread_key(dataset_name: str, a: str, b: str) -> str:
    return dataset_name + ':' + ':'.join(sorted((a,b)))

def require_mutual(state, other: str) -> str:
    user = current(state)
    if other == user or other not in dataset(state['dataset'])[1]:
        raise HTTPException(404, 'Student not found')
    if connection_state(state, user, other) != 'connected':
        raise HTTPException(403, 'Both students must accept before messaging')
    return thread_key(state['dataset'], user, other)

@app.get('/api/v1/me/conversations')
def list_conversations():
    with LOCK:
        state = read_state()
        user = current(state)
        others = sorted(s for s in state['connections'].get(user, [])
                        if connection_state(state,user,s) == 'connected')
        out = []
        for other in others:
            history = state['messages'].get(thread_key(state['dataset'],user,other), [])
            last = history[-1] if history else None
            out.append({'student':other,'lastMessage':last,'messageCount':len(history)})
        return out

@app.get('/api/v1/messages/{other}')
def get_messages(other: str):
    with LOCK:
        state = read_state()
        key = require_mutual(state,other)
        return {'student':other,'messages':state['messages'].get(key, [])}

@app.post('/api/v1/messages/{other}',status_code=201)
def send_message(other: str, payload: OutgoingMessage):
    body = payload.text.strip()
    if not body: raise HTTPException(422, 'Message cannot be blank')
    with LOCK:
        state = read_state()
        key = require_mutual(state,other)
        message = {'id':str(uuid4()), 'sender':current(state), 'text':body,
                   'createdAt':datetime.now(timezone.utc).isoformat()}
        state['messages'].setdefault(key, []).append(message)
        save_state(state)
        return message

class DemoSelection(BaseModel):
    student: str
    dataset: str

@app.post('/api/v1/demo/select')
def select_demo(selection:DemoSelection):
    if selection.dataset not in DATASETS:raise HTTPException(422,'Dataset unavailable')
    if selection.student not in dataset(selection.dataset)[1]:raise HTTPException(422,'Unknown synthetic student')
    with LOCK:
        state=read_state();state['student']=selection.student;state['dataset']=selection.dataset;save_state(state)
        return dashboard(state)
