# -*- coding: utf-8 -*-
"""Example photon counting script."""
import os
from pathlib import Path
import warnings

import numpy as np
import matplotlib.pyplot as plt

from emccd_detect.emccd_detect import EMCCDDetect
# from PhotonCount.corr_photon_count import get_count_rate
from corr_photon_count_DCN import get_count_rate

here = Path(os.path.abspath(os.path.dirname(__file__)))


def imagesc(data, title=None, vmin=None, vmax=None, cmap='viridis',
            aspect='equal', colorbar=True):
    """Plot a scaled colormap."""
    fig, ax = plt.subplots()
    im = ax.imshow(data, vmin=vmin, vmax=vmax, cmap=cmap, aspect=aspect)

    if title:
        ax.set_title(title)
    if colorbar:
        fig.colorbar(im, ax=ax)

    return fig, ax


if __name__ == '__main__':
    # Specify relevant detector properties
    emccd = EMCCDDetect(
        em_gain=5000.,
        full_well_image=60000.,  # e-
        full_well_serial=100000.,  # e-
        dark_current=3e-5,  # e-/pix/s
        cic=1.3e-3,  # e-/pix/frame
        read_noise=100.,  # e-/pix/frame
        bias=10000.,  # e-
        qe=0.8,
        cr_rate=0.,  # hits/cm^2/s
        pixel_pitch=13e-6,
        eperdn=7.,
        nbits=14,
        numel_gain_register=604
    )

    fluxmap = np.load(Path(here, '..', 'fluxmap.npy'))
    # fluxmap = 0.01*np.ones(100)

    # Simulate frames
    # Set frametime to get a good output, like 0.1 phot/pix or less
    frametime = 10 # s
    frame_e_list = []
    frame_e_dark_list = []
    nframes = 100
    for i in range(nframes):
        # Simulate bright
        frame_dn = emccd.sim_sub_frame(fluxmap, frametime)
        # Simulate dark
        frame_dn_dark = emccd.sim_sub_frame(np.zeros_like(fluxmap), frametime)

        # Convert from dn to e- and bias subtract
        frame_e = frame_dn * emccd.eperdn - emccd.bias
        frame_e_dark = frame_dn_dark * emccd.eperdn - emccd.bias

        frame_e_list.append(frame_e)
        frame_e_dark_list.append(frame_e_dark)

    niter = 30
    
    frame_e_cube = np.stack(frame_e_list)

    # Photon count, co-add, and correct for photometric error
    thresh = 300.  # see warnings below
    # if emccd.read_noise <=0:
    #    warnings.warn('read noise should be greater than 0 for effective '
    #    'photon counting')
    # if thresh < 4*emccd.read_noise:
    #    warnings.warn('thresh should be at least 4 or 5 times read_noise for '
    #    'accurate photon counting')
    xmax = 20000
    ymax = 1500
    frame_e_flat = frame_e_cube.flatten()
    
    # plt.hist(frame_e_flat, bins=int(40/(xmax/frame_e_flat.max())), edgecolor='black')
    # plt.xlabel('Electrons')
    # plt.title('Electron Counts Histogram')
    # plt.xlim(None,xmax)
    # plt.ylim(None,ymax)
    # plt.show()
    mean_rate = get_count_rate(frame_e_cube, thresh, emccd.em_gain, niter)

    # Plot images
    # imagesc(fluxmap, 'input flux map')
    # imagesc(np.max(frame_e_cube, axis=0), 'max frame (pixel-by-pixel)')
    # imagesc(frame_e_cube[0], 'random frame')
    imagesc(mean_rate, 'get_count_rate')
    plt.show()

