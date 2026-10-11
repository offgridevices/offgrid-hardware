import numpy as np,sys
d=np.genfromtxt(sys.argv[1] if len(sys.argv)>1 else 'work/c3.dat',names=True)
t=d['time']*1e6
for tt in [9.9,10.2,10.5,11,11.5,12,12.3,12.6,13,13.5,14,15,17,20,25,30]:
    i=min(np.searchsorted(t,tt),len(t)-1)
    print(tt, ' '.join('%s=%.1f'%(n[:6],d[n][i]) for n in ['vvin','vvout','vsrc','vgate','iq1','iq2','vds1','vds2','vgs','vscp','ivxppvtvs','vdrn']))
for n in ['vvin','vds1','vds2','iq1','pq1','pq2','vsrc','vvout','vxppvsf','vaux']:
    print(n,'max %.1f min %.1f'%(d[n].max(), d[n].min()))
print('E q1 %.4f q2 %.4f'%(np.trapezoid(d['pq1'],d['time']),np.trapezoid(d['pq2'],d['time'])))
