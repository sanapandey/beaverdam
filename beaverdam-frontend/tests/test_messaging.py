"""Messages are visible only after mutual acceptance in the synthetic demo."""
from fastapi.testclient import TestClient
import server


def test_mutual_conversation_and_dataset_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'STATE_PATH', tmp_path / 'state.json')
    client = TestClient(server.app)
    def choose(student, dataset='v2_medium'):
        assert client.post('/api/v1/demo/select',json={'student':student,'dataset':dataset}).status_code==200

    assert client.get('/api/v1/messages/S002').status_code==403
    assert client.post('/api/v1/messages/S002',json={'text':'hello'}).status_code==403
    assert client.post('/api/v1/connections/S002').json()['state']=='requested'
    assert client.get('/api/v1/messages/S002').status_code==403
    choose('S002')
    assert client.get('/api/v1/messages/S001').status_code==403
    assert client.post('/api/v1/connections/S001').json()['state']=='connected'
    assert client.post('/api/v1/messages/S001',json={'text':'  Hello there!  '}).status_code==201
    choose('S001')
    conversation=client.get('/api/v1/messages/S002').json()['messages']
    assert len(conversation)==1
    assert conversation[0]['sender']=='S002' and conversation[0]['text']=='Hello there!'
    assert client.post('/api/v1/messages/S002',json={'text':'Hi!'}).status_code==201
    assert len(client.get('/api/v1/messages/S002').json()['messages'])==2
    assert client.get('/api/v1/me/conversations').json()[0]['messageCount']==2
    assert client.post('/api/v1/messages/S002',json={'text':'   '}).status_code==422
    assert client.post('/api/v1/messages/S002',json={'text':'a'*2001}).status_code==422
    assert client.get('/api/v1/messages/S099').status_code==403
    choose('S001','v2_weak')
    assert client.get('/api/v1/messages/S002').json()['messages']==[]
    choose('S001','v2_medium')
    assert len(client.get('/api/v1/messages/S002').json()['messages'])==2
