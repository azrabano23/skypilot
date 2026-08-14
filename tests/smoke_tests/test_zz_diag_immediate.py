"""Throwaway diagnostic, not a test: does the driver refuse without a pod?

The rejecting-StorageClass fixture was confirmed under WaitForFirstConsumer,
where a pod triggers the driver. Four tests need the refusal to arrive *before*
any launch, i.e. under Immediate binding, where the driver is called when the
claim is created. This prints whether it is, and what SkyPilot records for such
a volume -- the status and message those tests read. Always passes: its output
is the result.
"""
import subprocess
import time

import pytest

_SC = 'diag-immediate-reject'
_VOL = 'diag-immediate-vol'


def _run(cmd: str) -> str:
    print(f'\n$ {cmd}', flush=True)
    proc = subprocess.run(cmd,
                          shell=True,
                          capture_output=True,
                          text=True,
                          check=False)
    if proc.stdout.strip():
        print(proc.stdout[-6000:], flush=True)
    if proc.stderr.strip():
        print(f'STDERR: {proc.stderr[-3000:]}', flush=True)
    return proc.stdout


@pytest.mark.kubernetes
@pytest.mark.no_remote_server
def test_diag_immediate_rejection():
    provisioner = _run(
        'kubectl get sc nfs-rwx -o jsonpath={.provisioner}').strip()
    print(f'\n=== provisioner under test: {provisioner!r}', flush=True)
    assert provisioner, 'no nfs-rwx class on this cluster'

    # Same recipe as the WaitForFirstConsumer fixture -- no parameters, so the
    # driver has no server to provision against -- but bound Immediately, so it
    # is called without waiting for a pod.
    _run(f'kubectl apply -f - <<\'EOF\'\n'
         f'apiVersion: storage.k8s.io/v1\n'
         f'kind: StorageClass\n'
         f'metadata:\n'
         f'  name: {_SC}\n'
         f'provisioner: {provisioner}\n'
         f'volumeBindingMode: Immediate\n'
         f'EOF')
    try:
        _run(f'cat > /tmp/{_VOL}.yaml <<\'EOF\'\n'
             f'name: {_VOL}\n'
             f'type: k8s-pvc\n'
             f'size: 1Gi\n'
             f'config:\n'
             f'  access_mode: ReadWriteMany\n'
             f'  storage_class_name: {_SC}\n'
             f'EOF')
        _run(f'sky volumes apply -y --infra '
             f'k8s/$(kubectl config current-context) /tmp/{_VOL}.yaml')
        # What the four tests read: the recorded status and reason. Printed
        # repeatedly because the driver's answer and the status refresh land at
        # their own pace.
        for _ in range(6):
            _run(f'sky volumes ls | grep -E "NAME|{_VOL}"')
            time.sleep(15)
        pvc = _run(f'kubectl get pvc -l skypilot-name={_VOL} '
                   f'-o jsonpath={{.items[0].metadata.name}}').strip()
        print(f'\n=== claim: {pvc!r}', flush=True)
        if pvc:
            _run(f'kubectl describe pvc {pvc}')
    finally:
        _run(f'sky volumes delete {_VOL} -y || true')
        _run(f'kubectl delete sc {_SC} --ignore-not-found')
