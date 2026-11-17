"""Integration smoke tests for the local synthetic demo API."""
from fastapi.testclient import TestClient
import server


def test_demo_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'STATE_PATH', tmp_path / 'state.json')
    client = TestClient(server.app)
    response=client.get('/api/v1/me/dashboard')
    assert response.status_code==200
    first=response.json()
    assert first['demo']['dataset']=='v2_medium'
    assert len(first['recommendations'])<=10
    assert len(first['routines'])>0
    for match in first['recommendations']:
        assert 'score' not in match and 'venue_id' not in match and 'timestamp' not in match
        assert match['strength'] in ('Strong','Moderate','Weak')
    # Category preferences affect the real matching input and are persisted.
    p=first['privacy'];p['sharing']={c:(c=='academic') for c in server.CATEGORIES}
    assert client.put('/api/v1/me/privacy',json=p).status_code==200
    after=client.get('/api/v1/me/dashboard').json()
    assert after['privacy']['sharing']['study'] is False
    assert all(x['categories']==['academic'] for x in after['recommendations'])
    # Withholding individual recorded activity excludes its events.
    routines=after['routines'];routines[0]['excluded']=True
    assert client.put('/api/v1/me/routines',json=routines).status_code==200
    assert client.get('/api/v1/me/dashboard').json()['routines'][0]['excluded'] is True
    # Students can reciprocate a request in synthetic demo mode.
    other=after['recommendations'][0]['id']
    assert client.post('/api/v1/connections/'+other).json()['state']=='requested'
    assert client.post('/api/v1/demo/select',json={'student':other,'dataset':'v2_medium'}).status_code==200
    assert client.get('/api/v1/me/dashboard').json()['connections']['S001']=='incoming'
    assert client.post('/api/v1/connections/S001').json()['state']=='connected'
    assert client.get('/api/v1/me/dashboard').json()['connections']['S001']=='connected'
    assert client.post('/api/v1/demo/select',json={'student':'S001','dataset':'v2_medium'}).status_code==200
    assert client.get('/api/v1/me/dashboard').json()['connections'][other]=='connected'
    assert client.post('/api/v1/demo/select',json={'student':'S001','dataset':'v2_strong'}).status_code==200
