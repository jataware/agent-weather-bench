"""Docker-only agent tools; private references and model credentials never mount."""
import os
import subprocess
import time
import uuid
from pathlib import Path


# Runs only inside Docker. Traverse writable /work with no symlink following;
# an agent-created link can never redirect a controller transfer outside it.
NATIVE_TRANSFER = r'''
import hashlib,json,os,stat,sys,uuid
from pathlib import PurePosixPath
phase,destination,expected,size=sys.argv[1:]
parts=PurePosixPath(destination).parts
if parts[0]!='/' or len(parts)<3 or parts[1]!='work' or parts[2]=='inputs' or '..' in parts:
    raise ValueError('Unsafe acquisition destination')
parent=os.open('/work',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
for component in parts[2:-1]:
    try: os.mkdir(component,dir_fd=parent)
    except FileExistsError: pass
    child=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
    os.close(parent); parent=child
name=parts[-1]
try:
    fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
except FileNotFoundError:
    fd=None
if fd is not None:
    if not stat.S_ISREG(os.fstat(fd).st_mode): raise ValueError('Destination is not a regular file')
    with os.fdopen(fd,'rb') as stream:
        actual=hashlib.file_digest(stream,'sha256').hexdigest()
    if actual!=expected: raise ValueError('Destination already contains different bytes; choose a new path')
    print(json.dumps({'cache_hit':True,'transfer_bytes':0,'sha256':actual}));sys.exit(0)
if phase=='probe':
    print(json.dumps({'cache_hit':False}));sys.exit(0)
data=sys.stdin.buffer.read(int(size)+1)
if len(data)!=int(size) or hashlib.sha256(data).hexdigest()!=expected:
    raise ValueError('Acquisition transfer hash/length mismatch')
temporary='.weatherbench-acquire-'+uuid.uuid4().hex
fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
try:
    with os.fdopen(fd,'wb') as stream: stream.write(data)
    os.link(temporary,name,src_dir_fd=parent,dst_dir_fd=parent,follow_symlinks=False)
finally: os.unlink(temporary,dir_fd=parent)
print(json.dumps({'cache_hit':False,'transfer_bytes':len(data),'sha256':expected}))
'''


class InfrastructureUnavailable(RuntimeError):
    """The controller could not start or validate its scientific runtime."""


def docker(*args, timeout=120, check=True):
    try:
        result = subprocess.run(["docker", *map(str,args)], capture_output=True, text=True, timeout=timeout)
    except OSError as error:
        raise InfrastructureUnavailable("Docker controller unavailable: " + str(error)[:500]) from error
    if check and result.returncode:
        raise InfrastructureUnavailable("Docker command failed: " + result.stderr[-1500:])
    return result


def preflight(image):
    result = docker("image", "inspect", image, "--format", "{{.Id}}")
    if result.stdout.strip() != image:
        raise InfrastructureUnavailable("Runtime image content ID mismatch")


class ToolSandbox:
    def __init__(self, image, work, task, substrate, inputs, memory="4g", cpus=2, acquisition=None, feedback=None):
        self.image, self.work = image, Path(work).resolve()
        self.name = "weatherbench-" + uuid.uuid4().hex[:12]
        self.task, self.substrate, self.inputs = map(lambda p: Path(p).resolve(), (task,substrate,inputs))
        self.memory, self.cpus = memory, cpus
        self.acquisition = acquisition
        self.feedback = feedback

    def __enter__(self):
        preflight(self.image)
        self.work.mkdir(parents=True, exist_ok=True)
        (self.work / "inputs").mkdir(exist_ok=True)
        docker("run", "--detach", "--name", self.name, "--network", "none", "--read-only", "--cap-drop", "ALL",
               "--security-opt", "no-new-privileges", "--pids-limit", "128", "--memory", self.memory, "--cpus", self.cpus,
               "--user", f"{os.getuid() or 65534}:{os.getgid() or 65534}", "--tmpfs", "/tmp:rw,nosuid,size=512m",
               "--mount", f"type=bind,src={self.work},dst=/work",
               "--mount", f"type=bind,src={self.task},dst=/task,readonly",
               "--mount", f"type=bind,src={self.substrate},dst=/substrate,readonly",
               "--mount", f"type=bind,src={self.inputs},dst=/work/inputs,readonly",
               "--workdir", "/work", "--entrypoint", "/bin/sh", self.image, "-c", "while :; do sleep 60; done")
        try:
            self.boundary = self.inspect()
            return self
        except Exception:
            self.__exit__(None,None,None)
            raise

    def inspect(self):
        import json
        config = json.loads(docker("inspect", self.name).stdout)[0]
        host = config["HostConfig"]
        allowed = {str(self.work):("/work",True), str(self.task):("/task",False),
                   str(self.substrate):("/substrate",False), str(self.inputs):("/work/inputs",False)}
        mounts = {m["Source"]:(m["Destination"],m["RW"]) for m in config["Mounts"] if m["Type"] == "bind"}
        passed = (config["Image"] == self.image and host["NetworkMode"] == "none" and host["ReadonlyRootfs"]
                  and not host["Privileged"] and config["Config"]["User"].split(":")[0] != "0" and mounts == allowed
                  and "ALL" in [x.upper() for x in host.get("CapDrop",[])])
        if not passed:
            raise ValueError("Sandbox boundary mismatch")
        return {"passed":True, "network":"none", "runtime_image":self.image,
                "mounts": [{"destination":v[0],"writable":v[1]} for v in allowed.values()], "private_references_mounted":False,
                "model_credentials_mounted":False, "trusted_controller_adapter":True}

    def execute(self, command, timeout):
        start = time.monotonic()
        try:
            result = docker("exec", self.name, "/bin/sh", "-lc", command, timeout=timeout, check=False)
            return {"exit_code":result.returncode, "stdout":result.stdout[-24000:], "stderr":result.stderr[-8000:],
                    "seconds":time.monotonic()-start, "truncated":len(result.stdout)>24000 or len(result.stderr)>8000}
        except subprocess.TimeoutExpired:
            docker("kill", self.name, check=False)
            return {"exit_code":124, "stdout":"", "stderr":"Tool deadline; whole container stopped", "seconds":time.monotonic()-start}

    def receive_native(self, destination, data, sha256, timeout):
        import json
        started = time.monotonic()
        command = ["docker","exec",self.name,"python","-c",NATIVE_TRANSFER,"probe",destination,sha256,str(len(data))]
        try:
            probe = subprocess.run(command,capture_output=True,text=True,timeout=timeout)
            if probe.returncode:
                return {"exit_code":probe.returncode,"stdout":"","stderr":probe.stderr[-2000:]}
            result = json.loads(probe.stdout)
            if not result["cache_hit"]:
                command[2:2] = ["-i"]
                command[-4] = "write"
                transfer = subprocess.run(command,input=data,capture_output=True,timeout=max(.1,timeout-(time.monotonic()-started)))
                if transfer.returncode:
                    return {"exit_code":transfer.returncode,"stdout":"","stderr":transfer.stderr.decode(errors="replace")[-2000:]}
                result = json.loads(transfer.stdout)
                # stdin bytes were transferred even if another process filled
                # the destination between the probe and the atomic write.
                result["transfer_bytes"] = len(data)
            if result["sha256"] != sha256:
                raise ValueError("Native transfer returned a different hash")
            return {"exit_code":0,"stdout":f"Native source available at {destination}","stderr":"",
                    "seconds":time.monotonic()-started,**result}
        except subprocess.TimeoutExpired:
            docker("kill",self.name,check=False)
            return {"exit_code":124,"stdout":"","stderr":"Acquisition deadline; whole container stopped"}

    def acquire(self, url, destination, request=None, timeout=60):
        if self.acquisition is None:
            return {"exit_code":1,"stdout":"","stderr":"Acquisition is unavailable for this task"}
        return self.acquisition.acquire(url,destination,request,self.receive_native,timeout)

    def score_development(self, prediction_file, timeout=60):
        if self.feedback is None:
            return {'exit_code': 1, 'stdout': '', 'stderr': 'Development score feedback is unavailable for this task'}
        return self.feedback.query(prediction_file, timeout)

    def __exit__(self, *_):
        docker("rm", "--force", self.name, check=False)


def offline(image, frozen, output, argv, seconds=120, forecast=None, memory="4g", cpus=2):
    """Execute the declared scientific command, never through a host shell."""
    preflight(image)
    output.mkdir(parents=True, exist_ok=False)
    name = "weatherbench-replay-" + uuid.uuid4().hex[:12]
    arguments = ["run","--name",name,"--network","none","--read-only","--cap-drop","ALL",
                 "--security-opt","no-new-privileges","--pids-limit","128","--memory",memory,"--cpus",str(cpus),
                 "--user",f"{os.getuid() or 65534}:{os.getgid() or 65534}","--tmpfs","/tmp:rw,nosuid,size=512m",
                 "--mount",f"type=bind,src={frozen.resolve()},dst=/work,readonly",
                 "--mount",f"type=bind,src={output.resolve()},dst=/output","--workdir","/work"]
    if forecast:
        arguments += ["--mount",f"type=bind,src={forecast.resolve()},dst=/inputs/forecast.nc,readonly"]
    try:
        result = docker(*arguments,"--entrypoint",argv[0],image,*argv[1:],timeout=seconds,check=False)
        return {"exit_code":result.returncode,"stdout":result.stdout[-16000:],"stderr":result.stderr[-8000:],"network":"none",
                "image":image,"private_observations_mounted":False,"infrastructure_unavailable":result.returncode==125}
    except subprocess.TimeoutExpired:
        return {"exit_code":124,"stdout":"","stderr":"Offline deadline exceeded","network":"none"}
    finally:
        docker("rm","--force",name,check=False)
