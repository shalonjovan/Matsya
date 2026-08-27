#!/usr/bin/env python3
"""Big square V0 with velocity storage for click-inspect"""
import pathlib, json, rasterio, numpy as np, time
BASE=pathlib.Path(__file__).parent.parent
INPUT=BASE/"input"
OUTPUT=BASE/"output/V0"
DEM_TIF=INPUT/"dem_clipped.tif"
DRAIN_MASK_NPY=INPUT/"drain_mask.npy"
ROUGH_NPY=INPUT/"roughness.npy"
DX=30.0; G=9.81; DT=0.8  # slightly larger dt for big domain speed, still stable
RAIN_INTENSITY=50.0; RAIN_DURATION=3600; SIM_DURATION=21600; REPORT_STEP=300

def load():
    import rasterio
    with rasterio.open(DEM_TIF) as ds:
        dem=ds.read(1).astype(np.float32)
        dem[dem==-32768]=np.nan
        dem=np.nan_to_num(dem, nan=np.nanmean(dem))
        # pit fill 3 iters
        filled=dem.copy()
        for _ in range(3):
            pad=np.pad(filled,1,mode='edge')
            for i in range(filled.shape[0]):
                for j in range(filled.shape[1]):
                    c=filled[i,j]
                    neigh=pad[i:i+3,j:j+3]
                    m=np.min(neigh)
                    if c < m-0.05:
                        filled[i,j]=m+0.01
        dem=filled
    drain=np.load(DRAIN_MASK_NPY) if DRAIN_MASK_NPY.exists() else np.zeros_like(dem,dtype=np.uint8)
    rough=np.load(ROUGH_NPY)
    return dem, drain, rough

def run():
    dem,drain_mask,rough=load()
    rows,cols=dem.shape
    print(f"Big domain {rows}x{cols}={rows*cols} cells drain {drain_mask.sum()} rough mean {rough.mean():.3f}")
    h=np.zeros((rows,cols),dtype=np.float32)
    qx=np.zeros((rows,cols+1),dtype=np.float32)
    qy=np.zeros((rows+1,cols),dtype=np.float32)
    n_qx=np.zeros_like(qx); n_qy=np.zeros_like(qy)
    for j in range(cols+1):
        if j==0: n_qx[:,j]=rough[:,0]
        elif j==cols: n_qx[:,j]=rough[:,-1]
        else: n_qx[:,j]=(rough[:,j-1]+rough[:,j])/2
    for i in range(rows+1):
        if i==0: n_qy[i,:]=rough[0,:]
        elif i==rows: n_qy[i,:]=rough[-1,:]
        else: n_qy[i,:]=(rough[i-1,:]+rough[i,:])/2
    z=dem
    rain_rate=RAIN_INTENSITY/1000/3600
    n_steps=int(SIM_DURATION/DT)
    report_every=int(REPORT_STEP/DT)
    snapshots=[]; vel_u_snap=[]; vel_v_snap=[]; times=[]; stats=[]
    start=time.time()
    for step in range(n_steps+1):
        t=step*DT
        rain=rain_rate if t<RAIN_DURATION else 0.0
        eta=z+h
        # padded for boundaries outside z-0.5 free outflow
        eta_pad=np.pad(eta,1,mode='edge')
        z_pad=np.pad(z,1,mode='edge')
        eta_pad[0,1:-1]=z[0,:]-0.5; z_pad[0,1:-1]=z[0,:]-0.5
        eta_pad[-1,1:-1]=z[-1,:]-0.5; z_pad[-1,1:-1]=z[-1,:]-0.5
        eta_pad[1:-1,0]=z[:,0]-0.5; z_pad[1:-1,0]=z[:,0]-0.5
        eta_pad[1:-1,-1]=z[:,-1]-0.5; z_pad[1:-1,-1]=z[:,-1]-0.5
        eta_pad[0,0]=z[0,0]-0.5; z_pad[0,0]=z[0,0]-0.5
        eta_pad[0,-1]=z[0,-1]-0.5; z_pad[0,-1]=z[0,-1]-0.5
        eta_pad[-1,0]=z[-1,0]-0.5; z_pad[-1,0]=z[-1,0]-0.5
        eta_pad[-1,-1]=z[-1,-1]-0.5; z_pad[-1,-1]=z[-1,-1]-0.5

        eta_left=eta_pad[1:-1,0:cols+1]; eta_right=eta_pad[1:-1,1:cols+2]
        z_left=z_pad[1:-1,0:cols+1]; z_right=z_pad[1:-1,1:cols+2]
        slope_qx=(eta_right-eta_left)/DX
        h_flow_qx=np.maximum(0, np.maximum(eta_left, eta_right)-np.maximum(z_left, z_right))
        h_flow_qx=np.clip(h_flow_qx,0,10)
        mask_qx=h_flow_qx>0.001
        denom=np.ones_like(qx)
        denom[mask_qx]+=G*DT*(n_qx[mask_qx]**2)*np.abs(qx[mask_qx])/(h_flow_qx[mask_qx]**(7/3)+1e-8)
        qx_new=np.where(mask_qx, (qx - G*h_flow_qx*DT*slope_qx)/denom, 0)
        q_limit=h_flow_qx*DX/DT*0.25
        qx_new=np.clip(qx_new, -q_limit, q_limit)
        qx=qx_new

        eta_top=eta_pad[0:rows+1,1:-1]; eta_bottom=eta_pad[1:rows+2,1:-1]
        z_top=z_pad[0:rows+1,1:-1]; z_bottom=z_pad[1:rows+2,1:-1]
        slope_qy=(eta_bottom-eta_top)/DX
        h_flow_qy=np.maximum(0, np.maximum(eta_top, eta_bottom)-np.maximum(z_top, z_bottom))
        h_flow_qy=np.clip(h_flow_qy,0,10)
        mask_qy=h_flow_qy>0.001
        denom_qy=np.ones_like(qy)
        denom_qy[mask_qy]+=G*DT*(n_qy[mask_qy]**2)*np.abs(qy[mask_qy])/(h_flow_qy[mask_qy]**(7/3)+1e-8)
        qy_new=np.where(mask_qy, (qy - G*h_flow_qy*DT*slope_qy)/denom_qy, 0)
        q_limit_y=h_flow_qy*DX/DT*0.25
        qy_new=np.clip(qy_new, -q_limit_y, q_limit_y)
        qy=qy_new

        div=(qx[:,:-1]-qx[:,1:] + qy[:-1,:]-qy[1:,:])/DX
        h_new=h + DT*(div + rain)
        h_new=np.maximum(0,h_new)
        h_new[h_new<1e-8]=0
        h_new=np.clip(h_new,0,5)
        h=h_new

        if step%report_every==0:
            max_h=np.max(h)
            flooded=(h>0.05).sum()
            vol=np.sum(h)*DX*DX
            # velocity at centers
            u=np.where(h>0.01, 0.5*(qx[:,:-1]+qx[:,1:])/np.maximum(h,0.01), 0)
            v=np.where(h>0.01, 0.5*(qy[:-1,:]+qy[1:,:])/np.maximum(h,0.01), 0)
            max_vel=np.max(np.sqrt(u*u+v*v)) if np.any(h>0) else 0
            print(f"[{t/3600:.2f}hr] max {max_h:.3f} mean {h[h>0].mean() if np.any(h>0) else 0:.3f} flood {flooded}/{h.size} vol {vol:.1f} vel {max_vel:.2f}")
            snapshots.append(h.copy())
            # store velocity for click (u,v)
            vel_u_snap.append(u.copy().astype(np.float32))
            vel_v_snap.append(v.copy().astype(np.float32))
            times.append(t)
            stats.append({'t':t,'max_h':float(max_h),'flooded':int(flooded),'vol':float(vol),'max_vel':float(max_vel)})

    # Save
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with rasterio.open(DEM_TIF) as src:
        prof=src.profile
    prof.update(dtype='float32',count=1,compress='lzw',nodata=-9999)
    with rasterio.open(OUTPUT/"depth_final.tif",'w',**prof) as dst:
        dst.write(h.astype(np.float32),1)
    np.save(OUTPUT/"snapshots.npy", np.array(snapshots))
    np.save(OUTPUT/"vel_u.npy", np.array(vel_u_snap))
    np.save(OUTPUT/"vel_v.npy", np.array(vel_v_snap))
    np.save(OUTPUT/"times.npy", np.array(times))
    with open(OUTPUT/"stats.json",'w') as f:
        json.dump(stats,f,indent=2)
    print(f"Saved big square {len(snapshots)} snapshots to {OUTPUT}")

if __name__=="__main__":
    run()
