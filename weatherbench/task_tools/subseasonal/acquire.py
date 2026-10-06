"""Bounded public Azure HDF5 range extraction; SAS tokens stay memory-only."""
from __future__ import annotations
import io,json,urllib.request,hashlib
from pathlib import Path
import h5py
import numpy as np

BLOB='https://subseasonalusa.blob.core.windows.net/subseasonalusa'
TOKEN='https://planetarycomputer.microsoft.com/api/sas/v1/token/subseasonalusa/subseasonalusa'

class RangeFile(io.RawIOBase):
    def __init__(self,url,max_bytes=100_000_000,block_size=262144):
        self.url=url; self.position=0;self.cache={};self.bytes_read=0;self.requests=0;self.maximum=max_bytes;self.block_size=block_size
        request=urllib.request.Request(url,method='HEAD')
        with urllib.request.urlopen(request,timeout=60) as response:
            self.size=int(response.headers['Content-Length']);self.etag=response.headers.get('ETag')
    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.position
    def seek(self,offset,whence=0):
        self.position=offset if whence==0 else self.position+offset if whence==1 else self.size+offset
        return self.position
    def readinto(self,buffer):
        data=self.read(len(buffer));buffer[:len(data)]=data;return len(data)
    def read(self,n=-1):
        if n<0:n=self.size-self.position
        end=min(self.size,self.position+n);result=[]
        while self.position<end:
            index=self.position//self.block_size
            if index not in self.cache:
                start=index*self.block_size;stop=min(self.size,start+self.block_size)-1
                if self.bytes_read+stop-start+1>self.maximum:raise ValueError('Bounded download exceeded')
                req=urllib.request.Request(self.url,headers={'Range':f'bytes={start}-{stop}','If-Match':self.etag})
                with urllib.request.urlopen(req,timeout=60) as response:
                    if response.status!=206:raise ValueError('Server did not honor Range')
                    body=response.read(stop-start+2)
                if len(body)!=stop-start+1:raise ValueError('Unexpected range length')
                self.cache[index]=body;self.bytes_read+=len(body);self.requests+=1
            offset=self.position%self.block_size;take=min(end-self.position,len(self.cache[index])-offset)
            result.append(self.cache[index][offset:offset+take]);self.position+=take
        return b''.join(result)

def open_public(name,max_bytes=100_000_000):
    token=json.load(urllib.request.urlopen(TOKEN,timeout=30))['token']
    return RangeFile(BLOB+'/dataframes/'+name+'?'+token,max_bytes=max_bytes)

if __name__=='__main__':
    import sys
    rf=open_public(sys.argv[1])
    with h5py.File(rf,'r') as f:
        def describe(name,item):
            if isinstance(item,h5py.Dataset):
                print(name,item.shape,item.dtype,dict(item.attrs));print(item[tuple(slice(0,min(5,s)) for s in item.shape)])
        f.visititems(describe)
    print('bytes',rf.bytes_read,'requests',rf.requests)
