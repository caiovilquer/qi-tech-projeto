#!/usr/bin/env python3
"""Host harness: build Linux containers, run HTTP tests, restart without deleting data.
No Docker socket is ever mounted in runner. Only the named project's services
are controlled. A new project name creates a separate database volume.
"""
import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--project',default='qit-verification')
parser.add_argument('--port',default='3300')
parser.add_argument('--suite-only',action='store_true')
args=parser.parse_args()
if not re.fullmatch(r'[a-z0-9][a-z0-9-]*',args.project): raise SystemExit('Invalid project name')
env=dict(os.environ,APP_ENV='test',TEST_CLOCK='2026-10-11T12:00:00Z',API_PORT=args.port,
         BANKING_IMAGE=args.project+'-api:local',SANDBOX_DEPOSITS='true',
         FEE_PF_INTERNAL='200',FEE_PJ_INTERNAL='500',
         FEE_PF_PIX_SIMULATED='0',FEE_PJ_PIX_SIMULATED='100',
         PIX_DAY_LIMIT='1000000',PIX_NIGHT_LIMIT='100000')
# Credentials come from the shell or the sandbox defaults. The shell wins
# over .env in Compose, so the log scan searches the values the APIs used.
env.setdefault('INTERNAL_TOKEN','sandbox-integrator-only')
env.setdefault('MONITORING_TOKEN','sandbox-monitoring-only')
base=['docker','compose','-p',args.project,'--profile','test','--profile','fault']
state={}
collected=[]
started=time.monotonic()


def command(arguments, capture=False, expected_failure=False):
    result=subprocess.run(base+arguments,cwd=root,env=env,text=True,stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,timeout=240)
    if not capture or result.returncode:
        print(result.stdout,flush=True)
    if expected_failure:
        assert result.returncode!=0 and 'TEST_CLOCK is only permitted' in result.stdout,result.stdout
    else:
        if result.returncode: raise RuntimeError('Compose command failed: '+str(arguments))
    return result.stdout


def keep_logs():
    # Recreating a container discards its logs; keep them for the final scan.
    collected.append(command(['logs','--no-color','api','api-fee0'],capture=True))


def restart_at(clock, fee='200'):
    keep_logs()
    env.update(TEST_CLOCK=clock,FEE_PF_INTERNAL=fee)
    command(['up','-d','--wait','api','api-fee0'])


def scenario(phase):
    global state
    output=command(['run','--rm','--no-deps','-e','SCENARIO_STATE='+json.dumps(state),
                    '-e','EXPECTED_CLOCK='+env['TEST_CLOCK'],'runner','python','scenarios.py',phase],capture=True)
    lines=output.splitlines()
    data=[line[6:] for line in lines if line.startswith('STATE:')]
    if len(data)!=1: raise RuntimeError(output)
    state=json.loads(data[0])
    print(next(line for line in lines if line.startswith('SCENARIO:')),flush=True)


try:
    command(['build','api','runner','db','db-proxy'])
    command(['up','-d','--wait','api','api-fee0'])
    command(['run','--rm','--no-deps','runner'])
    if args.suite_only: raise SystemExit(0)
    command(['up','-d','--wait','api-fault'])
    command(['run','--rm','--no-deps','runner','pytest','-q','fault_transport.py','-p','no:cacheprovider'])
    # Real packaging fault in the disposable test API. No source-tree edit or
    # public failpoint: its first customer request has no cached JSON schema.
    command(['exec','-T','api-fault','python','-c',
             'from pathlib import Path; Path("/app/schemas/post_customer.json").rename("/app/schemas/post_customer.json.test-backup")'])
    try:
        command(['run','--rm','--no-deps','runner','pytest','-q',
                 'operational_errors.py::test_unexpected_failure_returns_safe_500_with_request_id','-p','no:cacheprovider'])
    finally:
        command(['exec','-T','api-fault','python','-c',
                 'from pathlib import Path; Path("/app/schemas/post_customer.json.test-backup").rename("/app/schemas/post_customer.json")'])
    initial_logs=command(['logs','--no-color','api','api-fee0','api-fault'],capture=True)
    # Third API is unnecessary in calendar/restart scenarios.
    command(['stop','api-fault','db-proxy'])
    for clock,phase in [('2026-10-11T22:59:59Z','seed'),('2026-10-11T23:00:00Z','night'),
                        ('2026-10-12T03:00:00Z','midnight'),('2026-10-12T08:59:59Z','before_dawn'),
                        ('2026-10-12T09:00:00Z','dawn')]:
        restart_at(clock)
        scenario(phase)
    scenario('resume_bureau_rule')
    restart_at('2026-10-13T09:00:00Z',fee='999')
    scenario('after_24h')
    command(['restart','db','api','api-fee0'])
    scenario('persist')
    command(['stop','db'])
    command(['run','--rm','--no-deps','-e','SCENARIO_STATE='+json.dumps(state),'runner','pytest','-q',
             'operational_errors.py::test_database_outage_returns_safe_503','-p','no:cacheprovider'])
    command(['start','db'])
    scenario('persist')
    command(['stop','bureau'])
    scenario('bureau_down')
    command(['start','bureau'])
    # MockServer may take a few seconds to boot. The API itself has no retries.
    command(['run','--rm','--no-deps','runner','python','-c',
             'import time; time.sleep(5)'])
    scenario('bureau_recovered')
    keep_logs()
    env['SANDBOX_DEPOSITS']='false'
    command(['up','-d','--wait','api','api-fee0'])
    command(['run','--rm','--no-deps','-e','SCENARIO_STATE='+json.dumps(state),'runner','pytest','-q',
             'operational_errors.py::test_disabled_sandbox_returns_403_without_financial_effects','-p','no:cacheprovider'])
    command(['run','--rm','--no-deps','-e','APP_ENV=sandbox','-e','TEST_CLOCK=2026-10-11T12:00:00Z','api'],expected_failure=True)
    # Scan only application logs, never raw SQL, passwords or bodies.
    logs=initial_logs+''.join(collected)+command(['logs','--no-color','api','api-fee0','api-fault'],capture=True)
    secrets=[env['INTERNAL_TOKEN'],env['MONITORING_TOKEN'],state['pending_body']['document_number']]
    assert all(secret not in logs for secret in secrets),'Sensitive data in API logs'
    assert '"result": "desconhecido"' in logs and 'QIT001027' in logs
    assert '"result": "replay"' in logs and '"result": "confirmado"' in logs
    print('LOGS: credentials/document absent; confirmed/replay/unknown classified',flush=True)
    print(f'VERIFIED: suite, transport, calendar, >24h, restarts and outages in {time.monotonic()-started:.1f}s',flush=True)
except Exception:
    command(['logs','--no-color','--tail','30','api','api-fee0','db'])
    raise
finally:
    # Restore the test configuration used by the main suite and stop fault tools.
    command(['stop','api-fault','db-proxy'])
    env.update(TEST_CLOCK='2026-10-11T12:00:00Z',FEE_PF_INTERNAL='200',SANDBOX_DEPOSITS='true')
    command(['up','-d','--wait','api','api-fee0'])
