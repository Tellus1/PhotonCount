"""Photon count a stack of analog images and return a mean expected rate array
with photometric corrections.

"""
import warnings
import ipdb
import numpy as np

from PhotonCount.photon_count import photon_count


class CorrPhotonCountException(Exception):
    """Exception class for corr_photon_count module."""


def get_count_rate(frames, thresh, em_gain, niter=1, SNR=1000):
    """Take a stack of analog images and return the mean expected rate.

    This algorithm will photon count each frame in the stack individually,
    then co-add the photon counted frames. The co-added frame is then averaged
    and corrected for thresholding and coincidence loss, returning the mean
    expected rate in units of e-/pix/frame.

    Parameters
    ----------
    frames : array_like
        Bias subtracted frames in units of electrons (not dark subtracted or
        gain divided) (e-/pix/frame).
    thresh : float
        Photon counting threshold (e-).
    em_gain : float
        EM gain used when taking images.
    niter : int, optional
        Number of Newton's method iterations. Defaults to 2.
    SNR  : float, optional
        Desired level of precision.

    Returns
    -------
    mean_expected_rate : array_like
        Mean expected, per pixel per frame electron count rate (lambda)
        (e-/pix/frame).

    Notes
    -----
    Note that the output frame is in units of electrons, not photons. Photon
    counting is still happening though; units of electrons are only used
    becuase by definition all photon counting is still in units of electrons.

    References
    ----------
    [1] https://www.spiedigitallibrary.org/conference-proceedings-of-spie/11443/114435F/Photon-counting-and-precision-photometry-for-the-Roman-Space-Telescope/10.1117/12.2575983.full

    B Nemati, S Miller - UAH - 13-Dec-2020

    """
    # Check if input is an array/castable to one
    frames = np.array(frames).astype(float)
    if len(frames.shape) == 0:
        raise CorrPhotonCountException('frames must have length > 0')

    # Check other inputs
    if thresh < 0:
        raise CorrPhotonCountException('thresh must be nonnegative')
    if em_gain <= 0:
        raise CorrPhotonCountException('em_gain must be greater than 0')
    if not isinstance(niter, (int, np.integer)) or niter < 1:
        raise CorrPhotonCountException('niter must be an integer greater than '
                                       '0')
    if thresh >= em_gain:
        warnings.warn('thresh should be less than em_gain for effective '
        'photon counting')

    # Photon count stack of frames
    if len(frames.shape) > 2:
        nframes = len(frames)
        frames_pc = np.array([photon_count(frame, thresh) for frame in frames])
    if len(frames.shape) <= 2:
        nframes = 1
        frames_pc = photon_count(frames, thresh)

    # Co-add frames
    if nframes > 1:
        frame_pc_coadded = np.sum(frames_pc, axis=0)
    else:
        frame_pc_coadded = frames_pc

    # Correct for thresholding and coincidence loss
    mean_expected_rate = corr_photon_count(frame_pc_coadded, nframes, thresh,
                                           em_gain, niter, SNR)

    return mean_expected_rate

def get_counts_uncorrected(frames, thresh, em_gain):
    """Take a stack of analog images and return the photon-counted stack.

    This algorithm will photon count each frame in the stack individually,
    then return the stack without correcting for thresholding and coincidence
    loss, returning the stack in units of e-/pix/frame.
    ----------
    frames : array_like
        Bias subtracted frames in units of electrons (not dark subtracted or
        gain divided) (e-/pix/frame).
    thresh : float
        Photon counting threshold (e-).
    em_gain : float
        EM gain used when taking images.
    Returns
    -------
    frames_pc : array_like
        photon-counted using threshold without correction
        (e-/pix/frame).
    Notes
    -----
    Note that the output frame is in units of electrons, not photons. Photon
    counting is still happening though; units of electrons are only used
    becuase by definition all photon counting is still in units of electrons.
    References
    ----------
    [1] https://www.spiedigitallibrary.org/conference-proceedings-of-spie/11443/114435F/Photon-counting-and-precision-photometry-for-the-Roman-Space-Telescope/10.1117/12.2575983.full
    B Nemati, S Miller - UAH - 13-Dec-2020
    """
    # Check if input is an array/castable to one
    frames = np.array(frames).astype(float)
    if len(frames.shape) == 0:
        raise CorrPhotonCountException('frames must have length > 0')

    # Check other inputs
    if thresh < 0:
        raise CorrPhotonCountException('thresh must be nonnegative')
    if em_gain <= 0:
        raise CorrPhotonCountException('em_gain must be greater than 0')

    if thresh >= em_gain:
        warnings.warn('thresh should be less than em_gain for effective '
        'photon counting')

    # Photon count stack of frames
    if len(frames.shape) > 2:
        #nframes = len(frames)
        frames_pc = np.array([photon_count(frame, thresh) for frame in frames])
    if len(frames.shape) <= 2:
        #nframes = 1
        frames_pc = photon_count(frames, thresh)

    # Co-add and take the mean
    #if nframes > 1:
    #    frames_pc = np.mean(frames_pc, axis=0)

    return frames_pc

def corr_photon_count(nobs, nfr, t, g, niter=1, SNR=1000):
    """Correct photon counted images.

    Parameters
    ----------
    nobs : array_like
        Number of observations (Co-added photon counted frame).
    nfr : int
        Number of coadded frames.
    t : float
        Photon counting threshold.
    g : float
        EM gain used when taking images.
    niter : int, optional
        Number of Newton's method iterations. Defaults to 2.
    SNR : float, optional
        Desired level of precision.

    Returns
    -------
    lam : array_like
        Mean expeted rate (lambda).

    """
    # Get an approximate value of lambda for the first guess of the Newton fit
    lam0 = calc_lam_approx(nobs, nfr, t, g)

    # Use Newton's method to converge at a value for lambda
    lam = lam_newton_fit(nobs, nfr, t, g, lam0, niter, SNR)
    
    # Troubleshoot: find lam0 values that produce negative lam
    naughty = lam0[lam < 0]
    if any(naughty):
        print("Things screw up at Nbr = "+str(naughty))

    return lam


def calc_lam_approx(nobs, nfr, t, g):
    """Approximate lambda calculation.

    This will calculate the first order approximation of lambda, and for values
    that are out of bounds (e.g. from statistical fluctuations) it will revert
    to the zeroth order.

    Parameters
    ----------
    nobs : array_like
        Number of observations (Co-added photon counted frame).
    nfr : int
        Number of coadded frames.
    t : float
        Photon counting threshold.
    g : float
        EM gain used when taking images.

    Returns
    -------
    array_like
        Mean expeted rate (lambda).

    """
    # First step of equation (before taking log)
    init = 1 - (nobs/nfr) * np.exp(t/g)
    # Mask out all values less than or equal to 0
    lam_m = np.zeros_like(init).astype(bool)
    lam_m[init > 0] = True

    # Use the first order approximation on all values greater than zero
    lam1 = np.zeros_like(init)
    lam1[lam_m] = -np.log(init[lam_m])

    # For any values less than zero, revert to the zeroth order approximation
    lam0 = nobs / nfr
    lam1[~lam_m] = lam0[~lam_m]

    return lam1


def lam_newton_fit(nobs, nfr, t, g, lam0, niter, SNR):
    """Newton fit for finding lambda.

    Parameters
    ----------
    nobs : array_like
        Number of observations (Co-added photon counted frame).
    nfr : int
        Number of coadded frames.
    t : float
        Photon counting threshold.
    g : float
        EM gain used when taking images.
    lam0 : array_like
        Initial guess for lambda.
    niter : int
        Number of Newton's fit iterations to take.
    SNR : float, optional
        Desired level of precision.

    Returns
    -------
    lam : array_like
        Mean expeted rate (lambda).

    """
    # Mask out zero values to avoid divide by zero
    lam_est_m = np.ma.masked_where(lam0 == 0, lam0)
    nobs_m = np.ma.masked_where(nobs == 0, nobs)

    # Iterate Newton's method
    for i in range(niter):
        func = _calc_func(nobs_m, nfr, t, g, lam_est_m)
        dfunc = _calc_dfunc(nfr, t, g, lam_est_m)
        delta_lam = func / dfunc
        lam_est_m -= delta_lam
    
    tally = 0
    cutoff = 1000
    # Iterate Newton's method more, if need be, until desired precision is reached
    while np.any(np.abs(delta_lam/lam_est_m) > 1/SNR):
        func = _calc_func(nobs_m, nfr, t, g, lam_est_m)
        dfunc = _calc_dfunc(nfr, t, g, lam_est_m)
        delta_lam = func / dfunc
        lam_est_m -= delta_lam
        tally += 1
        if tally > cutoff:
            print('Cutting off at '+str(cutoff)+' iterations')
            break
    
    if tally <= cutoff:
        print('Reached desired SNR in '+str(tally)+' iterations')
    # if lam_est_m.min() < 0:
    #     raise CorrPhotonCountException('negative number of photon counts; '
    #     'try decreasing the frametime')

    # Fill zero values back in
    lam = lam_est_m.filled(0)

    return lam


def _calc_func(nobs, nfr, t, g, lam):
    """Objective function for lambda."""
    e_thresh = (
        np.exp(-t/g)
        * (
            t**2 * lam**2
            + 2*g * t * lam * (3 + lam)
            + 2*g**2 * (6 + 3*lam + lam**2)
        )
        / (2*g**2 * (6 + 3*lam + lam**2))
    )

    e_coinloss = (1 - np.exp(-lam)) / lam

    #if (lam * nfr * e_thresh * e_coinloss).any() > nobs.any():
    #    warnings.warn('Input photon flux is too high; decrease frametime')
    # This warning isn't necessary; could have a negative func but still
    # close enough to 0 for Newton's method
    func = lam * nfr * e_thresh * e_coinloss - nobs

    return func


def _calc_dfunc(nfr, t, g, lam):
    """Derivative wrt lambda of objective function."""
    # overflow_indices = []
    # with warnings.catch_warnings():
    #     warnings.simplefilter("error", RuntimeWarning)
            
    #     for index in np.ndindex(lam.shape):
    #         try:
    #             _ = np.exp(lam[index])
    #         except RuntimeWarning:
    #             overflow_indices.append(index)
    #             print(overflow_indices)
    #             ipdb.set_trace() 
    dfunc = (
        (np.exp(-t/g - lam) * nfr)
        / (2 * g**2 * (6 + 3*lam + lam**2)**2)
        * (
            2*g**2 * (6 + 3*lam + lam**2)**2
            + t**2 * lam * (
                -12 + 3*lam + 3*lam**2 + lam**3 + 3*np.exp(lam)*(4 + lam)
                )
            + 2*g*t * (
                -18 + 6*lam + 15*lam**2 + 6*lam**3 + lam**4
                + 6*np.exp(lam)*(3 + 2*lam)
                )
        )
    )

    return dfunc