"""Shared bounded native-damage emulator; no attachment to the game."""
import sys
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
import flash_v4 as pe

class Machine:
 def __init__(self,data):
  self.u=Uc(UC_ARCH_X86,UC_MODE_32);self.u.mem_map(0,0x1000)
  self.u.mem_map(0x400000,0x300000);self.u.mem_map(0x800000,0x200000)
  for _,vs,rva,rs,rp in pe.pe_info(data)[2]:self.u.mem_write(0x400000+rva,data[rp:rp+rs])
  self.attrs={};self.next=0x880000;self.roll=0;self.hooks={}
  self.stub(0x4ddd60,lambda:self.attrs.get((self.arg(0),self.arg(1)),0))
  self.stub(0x4ddd00,lambda:self.attr(self.arg(0),self.arg(1)))
  self.stub(0x4dfc50,lambda:self.attr(self.arg(0),self.arg(1),self.arg(2)))
  self.stub(0x4d89d0,self.inc);self.stub(0x4ef8d0,lambda:self.roll)
  self.stub(0x4d8f50,lambda:0 if 2000<=self.arg(0)<3000 else 1)
  self.u.hook_add(UC_HOOK_CODE,self.hook)
 def w(self,p,v):self.u.mem_write(p,pe.u32(v&0xffffffff))
 def r(self,p):return int.from_bytes(self.u.mem_read(p,4),'little')
 def arg(self,i):return self.r(self.u.reg_read(UC_X86_REG_ESP)+4+i*4)
 def attr(self,obj,id,value=None):
  if (obj,id) not in self.attrs:self.attrs[(obj,id)]=self.next;self.next+=4
  p=self.attrs[(obj,id)]
  if value is not None:self.w(p,value)
  return p
 def inc(self):
  p=self.attr(self.arg(0),self.arg(1));self.w(p,self.r(p)+self.arg(2));return 0
 def stub(self,addr,fn):self.hooks[addr]=fn;self.u.mem_write(addr,b'\xc3')
 def hook(self,u,pc,size,_):
  if pc in self.hooks:u.reg_write(UC_X86_REG_EAX,self.hooks[pc]()&0xffffffff)
 def party(self,stats):
  roles=[0x810000+i*0x100 for i in range(len(stats))];nodes=[0x820000+i*0x20 for i in range(len(stats))]
  self.w(0x599894,0x830000);self.w(0x830000,nodes[0]);self.w(0x830004,len(stats))
  for i,(role,node,(attack,spirit,level)) in enumerate(zip(roles,nodes,stats)):
   self.w(role,2000+i);self.w(node+4,role);self.w(node+0xc,nodes[i-1] if i else 0);self.w(node+0x10,nodes[i+1] if i+1<len(nodes) else 0)
   for id,val in ((5,level),(0x11,1000),(0x1a,attack),(0x1d,0),(0x20,spirit),(0x23,0),(0xb4,0x2a7)):self.attr(role,id,val)
  self.w(0x840000,336);return roles,0x840000
 def damage(self,actor,target,type,roll=0,active=True,power=-9):
  self.w(0x5998a8,type);self.w(0x5998ac,power);self.w(0x59943c,0x40000 if active else 0);self.roll=roll
  sp=0x9ef000;self.w(sp,0x9ff000);self.w(sp+4,actor);self.w(sp+8,target)
  for r,v in ((UC_X86_REG_EBX,123),(UC_X86_REG_ESI,234),(UC_X86_REG_EDI,345),(UC_X86_REG_EBP,0x9ed000)):self.u.reg_write(r,v)
  self.u.reg_write(UC_X86_REG_ESP,sp)
  self.u.emu_start(0x4d9580,0x9ff000,count=50000)
  assert self.u.reg_read(UC_X86_REG_EIP)==0x9ff000
  assert self.u.reg_read(UC_X86_REG_ESP)==sp+4
  for r,v in ((UC_X86_REG_EBX,123),(UC_X86_REG_ESI,234),(UC_X86_REG_EDI,345),(UC_X86_REG_EBP,0x9ed000)):assert self.u.reg_read(r)==v
  v=self.u.reg_read(UC_X86_REG_EAX);return -(v-0x100000000 if v&0x80000000 else v)

