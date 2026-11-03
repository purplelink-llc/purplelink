# python3 aka-spot-bed.py out/aka/aka-spot-bed.wav  (then node build-aka-spot.mjs muxes it into aka-spot-music.mp4)
# 120 BPM synth bed for the AKA spot, 18 s, laid on the cut grid: intro 4 beats, cuts 22 beats, strobe 2, end 8.
import numpy as np, wave, sys
SR=48000; BPM=120; B=60/BPM; TOTAL=52*B
O=12  # problem beats before the old intro; cuts run beats O+4..O+30, strobe to O+32, end card from O+32
n=int(TOTAL*SR); L=np.zeros(n); R=np.zeros(n)
t=np.arange(n)/SR
def add(sig,start,pan=0.0,g=1.0):
    i=int(start*SR); j=min(n,i+len(sig)); s=sig[:j-i]*g
    L[i:j]+=s*(1-pan)*0.5*2**0.5/1.41; R[i:j]+=s*(1+pan)*0.5*2**0.5/1.41
def env(d,a=0.005,r=None):
    m=int(d*SR); e=np.ones(m); ai=max(1,int(a*SR)); e[:ai]=np.linspace(0,1,ai)
    rr=r if r else d; e*=np.exp(-np.arange(m)/SR/(rr/5)); return e
def kick():
    d=0.45; tt=np.arange(int(d*SR))/SR; f=45+110*np.exp(-tt*28)
    return np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-tt*7)
def hat(d=0.05):
    m=int(d*SR); x=np.random.randn(m); x=np.diff(np.concatenate([[0],x])); return x*np.exp(-np.arange(m)/SR*70)*0.25
def clap():
    m=int(0.25*SR); x=np.random.randn(m)
    e=np.exp(-np.arange(m)/SR*18)
    for k in (0.0,0.012,0.024): e[int(k*SR):]+=0.6*np.exp(-np.arange(m-int(k*SR))/SR*60)
    return np.convolve(x,[1,-0.9],'same')*e*0.35
def saw(f,d):
    tt=np.arange(int(d*SR))/SR; s=sum(np.sin(2*np.pi*f*k*tt)/k for k in range(1,9)); return s
def pad(freqs,d):
    s=sum(saw(f*(1+dt),d) for f in freqs for dt in (-0.004,0.004))
    m=len(s); a=int(0.08*SR); e=np.ones(m); e[:a]=np.linspace(0,1,a); e[-int(0.2*SR):]*=np.linspace(1,0,int(0.2*SR))
    return s*e*0.035
def bass(f,d):
    tt=np.arange(int(d*SR))/SR; s=np.sin(2*np.pi*f*tt)+0.3*np.sin(2*np.pi*2*f*tt); return s*np.exp(-tt*6)*0.5
def nf(m): return 440*2**((m-69)/12)
chords=[[57,60,64],[53,57,60],[48,52,55],[55,59,62]]  # Am F C G
roots=[45,41,48,43]
pump=np.ones(n)
beats=int(TOTAL/B)
# The problem: a ticking clock over a low drone, a riser into the fold, a hit when AKA appears.
for b in range(8):
    for h in range(2): add(hat(0.03),b*B+h*B/2,pan=-0.2,g=0.35 if h else 0.6)
add(pad([nf(m) for m in [45,52,57]],8*B)*0.7,0)
riser=np.random.randn(int(4*B*SR))*np.linspace(0,1,int(4*B*SR))**2*0.12
add(np.convolve(riser,np.ones(6)/6,'same'),4*B)
add(kick(),8*B,g=1.1); add(clap(),8*B,g=0.5)
add(pad([nf(m) for m in [57,60,64,69]],4*B),8*B,g=0.9)
for b0 in range(beats-O):
    b=b0; st=(b0+O)*B
    if b<4:  # intro: a hit on every word
        add(kick(),st,g=0.9); add(clap(),st,g=0.4)
    elif b<30:
        add(kick(),st,g=1.0)
        if b%2==1: add(clap(),st)
        sub=4 if b>=28 else 2
        for h in range(sub): add(hat(),st+h*B/sub,pan=0.3,g=0.8 if h%2 else 0.5)
        root=roots[(b-4)//2%4]
        for e8 in range(2): add(bass(nf(root),B/2),st+e8*B/2)
        k=int(st*SR); m=int(0.35*SR); pump[k:k+m]=np.minimum(pump[k:k+m],0.35+0.65*np.linspace(0,1,min(m,n-k)))
    if b==32: add(kick(),st,g=1.1); add(clap(),st,g=0.6)
# pads: two beats per chord from beat 4, a held chord over the end card
for b in range(4,32,2): add(pad([nf(m) for m in chords[(b-4)//2%4]],2*B),(b+O)*B)
add(pad([nf(m) for m in [57,60,64,69]],8*B)*np.linspace(1,0,int(8*B*SR))**0.5,(32+O)*B,g=1.6)
add(pad([nf(m) for m in [57,60,64]],4*B),O*B,g=0.6)
mixL=L*np.where(np.arange(n)<int(28*B*SR),1,1); 
# sidechain only the pads/bass is approximated by pumping the whole bed lightly
L*=0.6+0.4*pump; R*=0.6+0.4*pump
fade=int(1.0*SR); L[-fade:]*=np.linspace(1,0,fade); R[-fade:]*=np.linspace(1,0,fade)
peak=max(abs(L).max(),abs(R).max()); L/=peak/0.89; R/=peak/0.89
data=(np.stack([L,R],1)*32767).astype(np.int16)
w=wave.open(sys.argv[1],'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(data.tobytes()); w.close()
print('bed', TOTAL,'s')
