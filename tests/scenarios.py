"""Host-controlled restart/calendar scenarios; runner uses only public HTTP."""
import json
import os
import sys
import time
import requests
from helpers import *
from conftest import MONITOR


def wait_ready():
    deadline=time.monotonic()+90
    for url in [API,FEE0]:
        while time.monotonic()<deadline:
            try:
                if requests.get(url+'/readiness',headers={'MONITORING-TOKEN':MONITOR},timeout=(3,30)).status_code==204: break
            except requests.RequestException:
                pass
            time.sleep(.5)
        else: raise AssertionError('Readiness failed')


def run(phase, state):
    if phase!='database_down': wait_ready()
    if phase=='seed':
        c,p=customer(); d,_=customer(); a=account(c); b=account(c); dest=account(d)
        ok(deposit(c,a,3000000),201); ok(deposit(c,b,3000000),201)
        pix_key=uid(); pix=ok(transfer(c,a,dest,1000000,pix_key,modality='PIX_SIMULATED'),201)
        internal_key=uid(); internal=ok(transfer(c,a,dest,600000,internal_key),201)
        pending,pending_body=customer(); bureau_rule(pending_body['document_number'],http=503)
        creation_key=uid(); r=call('POST','/accounts',pending,{'customer_key':pending},creation_key)
        error(r,'QIT001031',503)
        state={'c':c,'a':a,'b':b,'d':d,'dest':dest,'pix_key':pix_key,'pix':pix,
               'internal_key':internal_key,'internal':internal,
               'pending':pending,'pending_body':pending_body,'creation_key':creation_key,
               'pending_account':r.json()['details']['account_key']}
        assert detail(c,a,pix['operation_key'])['created_at']==os.environ['EXPECTED_CLOCK']
    elif phase in ('night','midnight','before_dawn','dawn','after_24h','persist','sandbox_off'):
        c,a,b,d,dest=[state[k] for k in ('c','a','b','d','dest')]
        if phase=='night':
            prior=balance(d,dest)
            attempts=parallel([lambda:transfer(c,a,dest,60000,modality='PIX_SIMULATED'),
                               lambda:transfer(c,b,dest,60000,modality='PIX_SIMULATED',url=FEE0)])
            assert sorted(r.status_code for r in attempts)==[201,409],[r.text for r in attempts]
            error(next(r for r in attempts if r.status_code==409),'QIT001032',409)
            assert balance(d,dest)==prior+60000
        elif phase=='midnight':
            error(transfer(c,b,dest,60000,modality='PIX_SIMULATED'),'QIT001032',409)
            ok(transfer(c,b,dest,40000,modality='PIX_SIMULATED'),201)
        elif phase=='before_dawn':
            error(transfer(c,b,dest,1,modality='PIX_SIMULATED'),'QIT001032',409)
        elif phase=='dawn':
            ok(transfer(c,b,dest,1000000,modality='PIX_SIMULATED'),201)
            error(transfer(c,b,dest,1,modality='PIX_SIMULATED'),'QIT001032',409)
        elif phase=='after_24h':
            prior=history(c,a); funds=balance(c,a)
            assert ok(transfer(c,a,dest,1000000,state['pix_key'],modality='PIX_SIMULATED'),201)==state['pix']
            assert ok(transfer(c,a,dest,600000,state['internal_key']),201)==state['internal']
            assert balance(c,a)==funds and history(c,a)==prior
            assert detail(c,a,state['internal']['operation_key'])['entries'][1]['delta_cents']==-200
            new=ok(transfer(c,a,dest,100),201)
            assert detail(c,a,new['operation_key'])['entries'][1]['delta_cents']==-999
            assert account(state['pending'],state['creation_key'])==state['pending_account']
        elif phase=='persist':
            assert [balance(c,a),balance(c,b),balance(d,dest)]==state['balances']
            assert ok(transfer(c,a,dest,600000,state['internal_key'],url=FEE0),201)==state['internal']
            assert account(state['pending'],state['creation_key'])==state['pending_account']
        elif phase=='sandbox_off':
            before=history(c,a)
            error(deposit(c,a,1),'QIT001035',403)
            assert history(c,a)==before
        if phase in ('night','midnight','before_dawn','dawn'):
            # Pending GET remains read-only through every host restart.
            assert ok(call('GET','/accounts/'+state['pending_account'],state['pending']))['status']=='PENDING'
            # Immutable replay disregards consumed quota/current window.
            assert ok(transfer(c,a,dest,1000000,state['pix_key'],modality='PIX_SIMULATED'),201)==state['pix']
        for owner,acc in [(c,a),(c,b),(d,dest)]: reconcile(owner,acc)
        state['balances']=[balance(c,a),balance(c,b),balance(d,dest)]
    elif phase=='resume_bureau_rule':
        bureau_rule(state['pending_body']['document_number'],priority=200)
    elif phase=='database_down':
        assert requests.get(API+'/health_check',timeout=(3,30)).status_code==204
        r=requests.get(API+'/readiness',headers={'MONITORING-TOKEN':MONITOR},timeout=(3,30))
        error(r,'QIT001014',503)
        error(deposit(state['c'],state['a'],1),'QIT001014',503)
    elif phase=='bureau_down':
        c,_=customer(); key=uid()
        r=call('POST','/accounts',c,{'customer_key':c},key)
        error(r,'QIT001031',503)
        state['outage']={'customer':c,'key':key,'account':r.json()['details']['account_key']}
        assert ok(call('GET','/accounts/'+state['outage']['account'],c))['status']=='PENDING'
    elif phase=='bureau_recovered':
        outage=state['outage']
        assert account(outage['customer'],outage['key'])==outage['account']
    else: raise AssertionError('Unknown phase '+phase)
    print('STATE:'+json.dumps(state),flush=True)
    print('SCENARIO:'+phase+' passed',flush=True)


if __name__=='__main__':
    run(sys.argv[1],json.loads(os.getenv('SCENARIO_STATE','{}')))
