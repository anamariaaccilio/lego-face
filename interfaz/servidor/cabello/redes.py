"""Arquitecturas compatibles con los checkpoints de cabello de Kaggle."""
import math
import torch
from torch import nn
def gn(c):return nn.GroupNorm(4 if c%4==0 else 2,c)

class Residual(nn.Module):
    def __init__(self,c):
        super().__init__();self.net=nn.Sequential(gn(c),nn.SiLU(),nn.Conv3d(c,c,3,padding=1),gn(c),nn.SiLU(),nn.Conv3d(c,c,3,padding=1))
    def forward(self,x):return x+self.net(x)

class VAE1(nn.Module):
    def __init__(self,head):
        super().__init__();ch=[1,12,20,32,48]
        self.encoder=nn.Sequential(*[nn.Sequential(nn.Conv3d(a,b,4,2,1),gn(b),nn.SiLU(),Residual(b)) for a,b in zip(ch[:-1],ch[1:])])
        self.stats=nn.Conv3d(48,16,1)
        self.from_z=nn.Sequential(nn.Conv3d(8,48,1),Residual(48))
        self.decoder=nn.Sequential(nn.ConvTranspose3d(48,32,4,2,1),Residual(32),
            nn.ConvTranspose3d(32,20,4,2,1),Residual(20),nn.ConvTranspose3d(20,12,4,2,1),Residual(12),
            nn.ConvTranspose3d(12,6,4,2,1),gn(6),nn.SiLU(),nn.Conv3d(6,1,3,padding=1))
        self.register_buffer('head',torch.as_tensor(head,dtype=torch.bool)[None,None])
    def encode(self,x):
        mu,lv=self.stats(self.encoder(x)).chunk(2,dim=1)
        return mu,lv.clamp(-8,3)
    def decode(self,z):return self.decoder(self.from_z(z)).masked_fill(self.head,-20.)
    def forward(self,x,sample=True):
        mu,lv=self.encode(x);z=mu+torch.exp(.5*lv)*torch.randn_like(mu) if sample else mu
        return self.decode(z),mu,lv

class Bloque(nn.Module):
    def __init__(self,d):
        super().__init__()
        self.norm_local=nn.LayerNorm(d)
        self.local=nn.MultiheadAttention(d,4,batch_first=True)
        self.norm_cruzada=nn.LayerNorm(d)
        self.cruzada=nn.MultiheadAttention(d,4,batch_first=True)
        self.mlp=nn.Sequential(nn.LayerNorm(d),nn.Linear(d,3*d),nn.GELU(),nn.Linear(3*d,d))
    def forward(self,h,c):
        q=self.norm_local(h)
        h=h+self.local(q,q,q,need_weights=False)[0]
        h=h+self.cruzada(self.norm_cruzada(h),c,c,need_weights=False)[0]
        return h+self.mlp(h)

class Flow1(nn.Module):
    def __init__(self,dim_foto,d=96):
        super().__init__()
        self.in_vox=nn.Linear(8,d)
        self.in_foto=nn.Linear(dim_foto,d)
        self.pos=nn.Parameter(torch.randn(1,252,d)*.02)
        self.pos_foto=nn.Parameter(torch.randn(1,64,d)*.02)
        self.tiempo=nn.Sequential(nn.Linear(16,d),nn.SiLU(),nn.Linear(d,d))
        self.register_buffer("frecuencias",torch.arange(1,9)*math.pi)
        self.bloques=nn.ModuleList([Bloque(d) for _ in range(3)])
        self.salida=nn.Sequential(nn.LayerNorm(d),nn.Linear(d,8))
    def forward(self,x,t,foto):
        a=t[:,None]*self.frecuencias[None]
        h=self.in_vox(x.flatten(2).transpose(1,2))+self.pos
        h=h+self.tiempo(torch.cat((a.sin(),a.cos()),dim=1))[:,None,:]
        c=self.in_foto(foto)+self.pos_foto
        for bloque in self.bloques:
            h=bloque(h,c)
        return self.salida(h).transpose(1,2).reshape_as(x)
